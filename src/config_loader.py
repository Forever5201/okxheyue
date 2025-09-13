import yaml
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
