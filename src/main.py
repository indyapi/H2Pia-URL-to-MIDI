import sys
import os
from PySide6.QtWidgets import QApplication
from src.ui.main_window import MainWindow
from src.core.queue_manager import QueueManager
from src.services.youtube import YoutubeService
from src.services.transcriber import TranscriptionService

from src.core.logger import setup_logging
import logging

def main():
    app = QApplication(sys.argv)
    
    # 1. Setup Paths
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    setup_logging(base_dir)
    logging.info("Starting U2M Application")
    output_dir = os.path.join(base_dir, "output")
    temp_dir = os.path.join(base_dir, "temp")
    qss_path = os.path.join(base_dir, "assets", "styles", "dark.qss")
    
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # 2. Initialize Services
    yt_service = YoutubeService(temp_dir=temp_dir)
    # We pass None initially and will initialize it when needed or in background
    transcriber_service = None 
    
    queue_manager = QueueManager(
        youtube_service=yt_service,
        transcriber_service=transcriber_service,
        output_dir=output_dir,
        max_concurrent=10
    )
    
    # 3. Apply Style
    if os.path.exists(qss_path):
        with open(qss_path, "r") as f:
            app.setStyleSheet(f.read())
            
    # 4. Launch UI
    window = MainWindow(queue_manager, config={})
    window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
