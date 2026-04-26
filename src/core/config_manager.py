import json
import os
import logging

logger = logging.getLogger(__name__)

class ConfigManager:
    def __init__(self, config_path="config_app.json"):
        self.config_path = config_path
        self.default_config = {
            "cpu_mode": "default",
            "cpu_limit": 50,
            "ram_mode": "default",
            "ram_limit": 50,
            "queue_size_limit": 10,
            "concurrency_limit": 3,
            "output_dir": "output",
            "theme": "dark"
        }
        self.config = self.load_config()

    def load_config(self):
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # Merge with defaults to ensure all keys exist
                    return {**self.default_config, **data}
            except Exception as e:
                logger.error(f"Failed to load config: {e}")
                return self.default_config
        return self.default_config

    def save_config(self, new_config=None):
        if new_config:
            self.config.update(new_config)
        
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=4, ensure_ascii=False)
            logger.info("Configuration saved successfully.")
        except Exception as e:
            logger.error(f"Failed to save config: {e}")

    def get(self, key, default=None):
        return self.config.get(key, default)
