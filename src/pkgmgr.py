import subprocess, sys, importlib
import logging
log = logging.getLogger(__name__)
from omegaconf import OmegaConf
def install_import(install_name, import_path=None, from_module=None):
    """
    install_name: name used in pip install, may be different from the import name/path
    import_path: full module path to import (e.g., "bs4.BeautifulSoup")
    from_module: if set, return only the object from module (e.g., BeautifulSoup class)
    """
    import_path = import_path or install_name
    try: module = importlib.import_module(import_path)
    except ImportError:
        log.info(f'{import_path} not found. Installing {install_name}...')
        process = subprocess.run([sys.executable, '-m', 'pip', 'install'] + install_name.split(), text=True, capture_output=True)#-m makes the pip to work as module inside env, not the system pip!
        log.info(process.stdout)
        #if process.stderr: log.info(process.stderr)
        if process.returncode != 0: raise ImportError(f'Failed to install package: {install_name}\n{process.stderr}')
        module = importlib.import_module(import_path)

    if from_module: return getattr(module, from_module)
    return module

def cfg2str(cfg): return '.'.join([f'{k}{v}' for k, v in OmegaConf.to_container(cfg, resolve=True).items()])

def str2cfg(s): #dot seperated kv, e.g., x1.y2.z3 --> x:1 y:2 z:3
    items = s.split(".")
    config = {}
    for item in items:
        key = ''.join(filter(str.isalpha, item))
        value = ''.join(filter(str.isdigit, item))
        config[key] = int(value) if value.isdigit() else value
    return OmegaConf.create(config)


# #samples
# install_import('hydra-core==1.3.2', 'hydra')
# # Importing a submodule/class/function: from bs4 import BeautifulSoup
# BeautifulSoup = install_and_import('beautifulsoup4', 'bs4', 'BeautifulSoup')
# soup = BeautifulSoup('<html><body><p>Hello</p></body></html>', 'html.parser')
# print(soup.p.text)  # -> "Hello"