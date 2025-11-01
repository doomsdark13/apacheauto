# apache_monitor/config_loader.py
import yaml
import os
import logging

logger = logging.getLogger("ConfigLoader")

_config = None

def get_config():
    """Load dan cache konfigurasi dari config.yaml"""
    global _config
    if _config is None:
        config_path = os.getenv("CONFIG_PATH", "config.yaml")
        try:
            if not os.path.exists(config_path):
                raise FileNotFoundError(f"Config file tidak ditemukan: {config_path}")
            
            with open(config_path, 'r', encoding='utf-8') as f:
                _config = yaml.safe_load(f)
            
            if _config is None:
                _config = {}
                logger.warning(f"Config file {config_path} kosong atau tidak valid")
            else:
                logger.info(f"Config loaded from: {config_path}")
        except FileNotFoundError as e:
            logger.error(str(e))
            raise
        except yaml.YAMLError as e:
            logger.error(f"Error parsing YAML config: {e}")
            raise ValueError(f"Invalid YAML format in {config_path}: {e}") from e
        except Exception as e:
            logger.error(f"Error loading config: {e}")
            raise
    
    return _config

def reload_config():
    """Force reload config dari file"""
    global _config
    _config = None
    return get_config()