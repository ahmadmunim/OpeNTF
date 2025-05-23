
import argparse, pickle, os, time, sys

sys.path.append("..")
sys.path.append("../..")
sys.path.append("../../..")
import torch

import params
from t2v import T2v

def addargs(parser):
    embedding = parser.add_argument_group('Team Embedding')
    embedding.add_argument('-teamsvecs', nargs='+', type=str, required=True, help='The path to the teamsvecs.pkl and indexes.pkl files; e.g., ../data/preprocessed/dblp/toy.dblp.v12.json/')
    embedding.add_argument('-model', type=str, required=True, help='The embedding model; e.g., w2v, n2v, ...')
    embedding.add_argument('--output', nargs='+', type=str, required=False, help='Output folder; e.g., ../data/preprocessed/dblp/toy.dblp.v12.json/')
    embedding.add_argument('--graph_only', type=int, required=False, help='if true, then only generates graph files and returns')

    # args for gnn methods
    gnn_args = parser.add_argument_group('Gnn Settings')
    gnn_args.add_argument('--agg', type=str, nargs = '+', required=False, help='The aggregation method used for the graph data; e.g : mean, none, max, min etc.')
    gnn_args.add_argument('--d', type=int, nargs='+', required=False, help='Embedding dimension; e.g : 4, 8, 16, 32 etc.')
    gnn_args.add_argument('--e', type=int, required=False, help='Train epochs ; e.g : 5, 100 etc.')
    gnn_args.add_argument('--ns', type=int, required=False, help='Train epochs ; e.g : 2, 3, 5 etc.')
    gnn_args.add_argument('--graph_types',  type=str, nargs = '+', required=False, help='Graph types used for the training; e.g : sm, stm, sm.en, stm.en etc.') # including this will skip the training for any graph type from the mentioned edge types which are not in this list
    gnn_args.add_argument('--pt', type=int, required=False, help='If true, then takes similar sized d2v pretrained vectors as initial node features; e.g : for --d 8, will take the word vectors from skill.emb.d8.w1.dm1.mdl')

    # args for d2v
    d2v_args = parser.add_argument_group('D2V Settings')
    d2v_args.add_argument('--embtype', type=str, required=False,help='What type of vectors to produce, joint makes skill+member paragraph vector for each team e.g : member, skill or joint')


def run(teamsvecs_file, indexes_file, model, output, emb_output = None):
    if not os.path.isdir(output): os.makedirs(output)
    with open(teamsvecs_file, 'rb') as teamsvecs_f, open(indexes_file, 'rb') as indexes_f:
        teamsvecs, indexes = pickle.load(teamsvecs_f), pickle.load(indexes_f)

        if model == 'w2v':
            import d2v
            # for d in params.settings['model'][model]['d']: # this is specific to w2v for now
            settings = {'d': params.settings['model'][model]['d'],
                        'e': params.settings['model']['e'],
                        'dm': params.settings['model'][model]['dm'],
                        'dbow_words': params.settings['model'][model]['dbow_words'],
                        'window': params.settings['model'][model]['dbow_words'],
                        'embtype': params.settings['model'][model]['embtype'],
                        'max_epochs' : params.settings['model'][model]['max_epochs']
                        }
            output_ = output + f'{settings["embtype"]}.'
            # wnn.run(teamsvecs_file, indexes_file, settings, output_)

            t2v = dnn.Dnn(teamsvecs, indexes, settings, output_)
            t2v.init()
            t2v.train()
            return

        # general init section for any
        # gnn methods
        import gnn
        output_ = output + f'{params.settings["graph"]["edge_types"][1]}.{"dir" if params.settings["graph"]["dir"] else "undir"}.{str(params.settings["graph"]["dup_edge"]).lower()}/'
        t2v = gnn.Gnn(teamsvecs, indexes, params.settings['graph'], output_)

        t2v.init() # call the t2v's init, this will lazy load the graph data e.g = "{domain}/gnn/stm.undir.mean.data.pkl"

        # replace the 1 dimensional node features with pretrained d2v skill vectors of required dimension
        if params.settings['model']['pt']:
            from gensim.models import Doc2Vec
            for node_type in t2v.data.node_types:
                d2v_embtype = 'joint' if params.settings["graph"]["graph_types"] == 'stm' and node_type == 'team' else node_type
                d2v_output = output.split('gnn')[0] + f'/w2v/{d2v_embtype}.emb.d{params.settings["model"][model]["d"]}.w1.dm1.mdl'
                node_type_vecs = Doc2Vec.load(d2v_output).dv.vectors if d2v_embtype == 'joint' else Doc2Vec.load(d2v_output).wv.vectors # team vectors (dv) for 'team' nodes, else individual node vectors (wv)
                t2v.data[node_type].x = torch.tensor(node_type_vecs)

        if(args.graph_only):
            return


        if model == 'gnn.n2v':
            from torch_geometric.nn import Node2Vec
            t2v.device = 'cuda' if torch.cuda.is_available() else 'cpu'
            t2v.model = Node2Vec(t2v.data.edge_index,
                                 embedding_dim=params.settings['model']['d'],
                                 walk_length=params.settings['model'][model]['walk_length'],
                                 context_size=params.settings['model'][model]['context_size'],
                                 walks_per_node=params.settings['model'][model]['walks_per_node'],
                                 num_negative_samples=params.settings['model'][model]['num_negative_samples']).to(t2v.device)


            t2v.loader = t2v.model.loader(batch_size=params.settings['model']['b'],

                                       shuffle=params.settings['model']['loader_shuffle'],
                                       num_workers=params.settings['model']['num_workers'])
            t2v.optimizer = torch.optim.Adam(list(t2v.model.parameters()), lr=params.settings['model']['lr'])
            t2v.model_name = 'n2v'

        elif model == 'gnn.m2v':

            from _m2v import M2V
            from torch_geometric.nn import MetaPath2Vec

            # initialize all settings inside m2v class
            t2v = M2V(teamsvecs, indexes, params.settings, output_, emb_output)
            t2v.model_name = 'm2v'
            t2v.init() # call the m2v's init
            t2v.model = MetaPath2Vec(t2v.data.edge_index_dict, embedding_dim=t2v.settings['d'],
                                     metapath=t2v.settings['metapath'][edge_type[1]], walk_length=t2v.settings['walk_length'],
                                     context_size=t2v.settings['context_size'],
                                     walks_per_node=t2v.settings['walks_per_node'],
                                     num_negative_samples=t2v.settings['ns'],
                                     sparse=True).to(t2v.device)
            t2v.init_model()
            t2v.train(t2v.settings['e'])
            t2v.model.eval()
            emb = {}
            node_types = t2v.data._node_store_dict.keys()
            for node_type in node_types:
                emb[node_type] = t2v.model(node_type)  # output of embeddings
            embedding_output = f'{t2v.emb_output}.emb.pt'
            torch.save(emb, embedding_output, pickle_protocol=4)
            return

        # gcn (for homogeneous only)
        elif model == 'gnn.gcn':
            from gcn_old import Gcn as GCNModel
            t2v.model = GCNModel(hidden_channels=10, data=t2v.data)
            t2v.optimizer = torch.optim.Adam(t2v.model.parameters(), lr=params.settings['model']['lr'])
            t2v.model_name = 'gcn'

        elif model in {"gnn.gs", "gnn.gin", "gnn.gat", "gnn.gatv2", "gnn.han", "gnn.gine", "gnn.lant"}:
            t2v.settings = params.settings['model'][model]
            t2v.model_name = model.split(".")[1]
            t2v.init_model(emb_output)
            t2v.train(t2v.settings['e'])

            return

        t2v.train(params.settings['model']['max_epochs'], params.settings['model']['save_per_epoch'])
        t2v.plot_points()
        print(t2v)

def test_toys(args):
    # test for all valid combinations on toys
    for args.teamsvecs in ['./../../../data/preprocessed/dblp/toy.dblp.v12.json/',
                           './../../../data/preprocessed/imdb/toy.title.basics.tsv/',
                           './../../../data/preprocessed/gith/toy.data.csv/',
                           './../../../data/preprocessed/uspt/toy.patent.tsv/']:
        args.output = args.teamsvecs
        args.model = 'gnn.n2v'

        # for edge_type in [('member', 'm')]: #n2v is only for homo, [([('skill', '-', 'team'), ('member', '-', 'team')], 'stm'), ([('skill', '-', 'member')], 'sm')]:
        for edge_type in [([('skill', 'to', 'team'), ('member', 'to', 'team')], 'stm')]:
            # for dir in [True, False]:
            for dir in [False]:
                for dup in [None, 'mean']:#add', 'mean', 'min', 'max', 'mul']:
                    params.settings['graph'] = {'edge_types': edge_type, 'dir': dir, 'dup_edge': dup}
                    run(f'{args.teamsvecs}teamsvecs.pkl', f'{args.teamsvecs}indexes.pkl', args.model, f'{args.output}/{args.model.split(".")[0]}/', f'{args.output}/emb/')

# we can ignore mentioning the --output argument
#python -u main.py -teamsvecs ./../../../data/preprocessed/dblp/toy.dblp.v12.json/ -model gnn.w2v --output ./../../../data/preprocessed/dblp/toy.dblp.v12.json/

# with gnn args
#python -u main.py -teamsvecs ./../../../data/preprocessed/dblp/toy.dblp.v12.json/ -model gnn.gs --agg mean --e 100 --d 8


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Team Embedding')
    addargs(parser)
    args = parser.parse_args()

    # run(f'{args.teamsvecs}teamsvecs.pkl', f'{args.teamsvecs}indexes.pkl', args.model, f'{args.output}/{args.model.split(".")[0]}/')


    for teamsvecs in args.teamsvecs:
        args.output = teamsvecs

        edge_types = params.settings['graph']['edge_types'] # take the edge types defined in the params
        supervision_edge_types = params.settings['graph']['supervision_edge_types'] if params.settings['graph']['custom_supervision'] else edge_types # if yes then apply the selected edge_types as supervision edges
        if args.agg is None: args.agg = params.settings['graph']['dup_edge']
        if args.d is None: args.d = [params.settings['model'][args.model]['d']] # loop through all the d's

        # for edge_type in [([('skill', 'to', 'member')], 'sm')]:
        # for edge_type in [([('skill', 'to', 'skill'), ('member', 'to', 'member'), ('skill', 'to', 'member')], 'sm')]: # sm enhanced
        # for edge_type in [([('skill', 'to', 'member')], 'sm'), ([('skill', 'to', 'team'), ('member', 'to', 'team')], 'stm')]:
        # for edge_type in [([('skill', 'to', 'skill'), ('member', 'to', 'member'), ('skill', 'to', 'team'), ('member', 'to', 'team')], 'stm')]: # stm enhanced
        # for edge_type in [([('skill', 'to', 'team'), ('member', 'to', 'team')], 'stm')]:
        for id, edge_type in enumerate(edge_types):
            for dir in [False]:
                # for dup in ['mean']:  # ['add', 'mean', 'min', 'max', 'mul']:
                for agg in args.agg:  # ['add', 'mean', 'min', 'max', 'mul']: # merge strategy of duplicate edges
                    for d in args.d:
                        if args.graph_types is not None and edge_type[1] not in args.graph_types:
                            print(f"Skipping for graph type : {edge_type[1]}, ")
                            continue

                        supervision_edge_type = supervision_edge_types[id][0] # select the corresponding supervision edge_type from the list
                        params.settings['graph'] = {
                            # set the params with the current settings
                            'edge_types': edge_type,
                            'dir': dir,
                            'dup_edge': agg,                                    # merging strategy for duplicate edges
                            'supervision_edge_types':supervision_edge_type      # select one single supervision edge type for this loop
                        }
                        params.settings['model'][args.model]['graph_types'] = edge_type[1]  # take the value from the current loop
                        params.settings['model'][args.model]['agg'] = agg # this is the same value as agg
                        params.settings['model'][args.model]['dir'] = dir # this is the same value as dir
                        params.settings['model'][args.model]['d'] = d

                        # change the relevant parameter in the params file based on the gnn args
                        if args.e is not None: params.settings['model'][args.model]['e'] = args.e
                        if args.ns is not None: params.settings['model'][args.model]['ns'] = args.ns
                        if args.pt is not None: params.settings['model']['pt'] = args.pt
                        if args.embtype is not None: params.settings['model'][args.model]['embtype'] = args.embtype

                        run(f'{teamsvecs}teamsvecs.pkl', f'{teamsvecs}indexes.pkl', args.model,
                            f'{args.output}/{args.model.split(".")[0]}/', f'{args.output}/emb/')

