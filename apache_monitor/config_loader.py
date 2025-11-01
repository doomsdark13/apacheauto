# apache_monitor/config_loader.py
import yaml
import os

_config = None

def get_config():
    global _config
    if _config is None:
        config_path = os.getenv("CONFIG_PATH", "config.yaml")
        with open(config_path) as f:
            _config = yaml.safe_load(f)
    return _config