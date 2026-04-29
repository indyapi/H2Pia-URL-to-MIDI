import sys
import os
import shutil
import warnings
import multiprocessing
from pathlib import Path
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import QApplication

# Windows fix for multiprocessing
if __name__ == "__main__":
    multiprocessing.freeze_support()

warnings.filterwarnings("ignore", category=DeprecationWarning, module="pkg_resources")
warnings.filterwarnings("ignore", message=".*pkg_resources is deprecated as an API.*")

def setup_ffmpeg(config_manager=None):
    if shutil.which("ffmpeg") and shutil.which("ffprobe"): return True
    if config_manager:
        cached_path = config_manager.get("ffmpeg_path")
        if cached_path and os.path.exists(cached_path):
            os.environ["PATH"] = cached_path + os.pathsep + os.environ["PATH"]
            if shutil.which("ffmpeg"): return True
    winget_base = Path(os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WinGet\Packages"))
    if winget_base.exists():
        for package_dir in winget_base.glob("Gyan.FFmpeg*"):
            for bin_dir in package_dir.rglob("bin"):
                if (bin_dir / "ffmpeg.exe").exists():
                    bin_path = str(bin_dir); os.environ["PATH"] = bin_path + os.pathsep + os.environ["PATH"]
                    if config_manager: config_manager.save_config({"ffmpeg_path": bin_path})
                    return True
    return False

from src.ui.main_window import MainWindow
from src.core.queue_manager import QueueManager
from src.services.media import MediaService
from src.services.transcriber import TranscriptionService
from src.core.resource_manager import ResourceManager
from src.core.config_manager import ConfigManager
from src.core.logger import setup_logging
import logging

def main():
    app = QApplication(sys.argv)
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    setup_logging(base_dir)
    config_path = os.path.join(base_dir, "config_app.json")
    config_manager = ConfigManager(config_path)
    setup_ffmpeg(config_manager)
    
    output_dir = os.path.join(base_dir, config_manager.get("output_dir", "output"))
    temp_dir = os.path.join(base_dir, "temp")
    qss_path = os.path.join(base_dir, "assets", "styles", "dark.qss")
    
    resource_manager = ResourceManager()
    resource_manager.set_cpu_settings(config_manager.get("cpu_mode"), config_manager.get("cpu_limit"))
    resource_manager.set_ram_settings(config_manager.get("ram_mode"), config_manager.get("ram_limit"))
    resource_manager.start()
    
    font_dir = os.path.join(base_dir, "assets", "font", "Sarabun")
    if os.path.exists(font_dir):
        font_path = os.path.join(font_dir, "Sarabun-Regular.ttf")
        if os.path.exists(font_path): QFontDatabase.addApplicationFont(font_path)
        app.setFont("Sarabun")
    
    if not os.path.exists(output_dir): os.makedirs(output_dir)
    
    import torch
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    if device == 'cuda':
        gpu_name = torch.cuda.get_device_name(0)
        logging.info(f"GPU detected: {gpu_name}. Using CUDA acceleration.")
    else:
        logging.info("No GPU detected or CUDA not available. Using CPU.")

    media_service = MediaService(temp_dir=temp_dir)
    transcriber_service = TranscriptionService(device=device)
    
    queue_manager = QueueManager(
        media_service=media_service,
        transcriber_service=transcriber_service,
        output_dir=output_dir,
        resource_manager=resource_manager,
        max_concurrent=config_manager.get("concurrency_limit", 3)
    )
    
    if os.path.exists(qss_path):
        with open(qss_path, "r") as f: app.setStyleSheet(f.read())
            
    window = MainWindow(queue_manager, resource_manager, config_manager)
    window.show()
    
    exit_code = app.exec()
    
    # Proper cleanup sequence
    queue_manager.cancel_all()
    resource_manager.stop()
    resource_manager.wait(3000) # Wait up to 3 seconds for the thread to finish
    
    sys.exit(exit_code)

if __name__ == "__main__":
    main()
