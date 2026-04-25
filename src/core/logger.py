import logging
import os
from datetime import datetime

def setup_logging(base_dir):
    """Configures logging for the entire application."""
    log_dir = os.path.join(base_dir, "logs")
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    # Create a unique log file for each session
    log_file = os.path.join(log_dir, f"u2m_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")

    # Configure root logger
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    # Formatter
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # File Handler
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # Console Handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    logging.info(f"Logging initialized. Saving to: {log_file}")
