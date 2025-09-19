import yaml
import os
from src.logger import setup_logger

logger = setup_logger()

class ConfigLoader:
    def __init__(self, config_path):
        self.config_path = config_path

    def load_config(self):
        logger.info(f"Loading configuration from {self.config_path}")
        try:
            with open(self.config_path, "r", encoding="utf-8") as file:
                config = yaml.safe_load(file)
                logger.info("Configuration loaded successfully.")
                return config
        except Exception as e:
            logger.error(f"Error loading configuration: {e}")
            raise

def load_config(config_path=None):
    """
    向后兼容的配置加载函数
    :param config_path: 配置文件路径，默认为config/config.yaml
    :return: 配置字典
    """
    if config_path is None:
        config_path = "config/config.yaml"
    
    # 如果文件不存在，尝试其他配置文件
    if not os.path.exists(config_path):
        alternative_configs = [
            "config/enhanced_config.yaml",
            "config/tool_classification.json",
            "config/session_config.json"
        ]
        
        for alt_config in alternative_configs:
            if os.path.exists(alt_config):
                config_path = alt_config
                break
    
    try:
        with open(config_path, "r", encoding="utf-8") as file:
            if config_path.endswith('.json'):
                import json
                config = json.load(file)
            else:
                config = yaml.safe_load(file)
            
            logger.info(f"Configuration loaded successfully from {config_path}")
            return config
    except Exception as e:
        logger.error(f"Error loading configuration from {config_path}: {e}")
        # 返回默认配置而不是抛出异常
        return {
            "version": "2.1",
            "default_config": True,
            "message": "Using default configuration due to loading error"
        }
