import sys
import os
import shutil
from pathlib import Path
from PySide6.QtGui import QFontDatabase

def setup_ffmpeg():
    """Ensures ffmpeg/ffprobe are in PATH."""
    if shutil.which("ffmpeg") and shutil.which("ffprobe"):
        return True
    
    # Common winget location
    winget_base = Path(os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WinGet\Packages"))
    if winget_base.exists():
        for package_dir in winget_base.glob("Gyan.FFmpeg*"):
            for bin_dir in package_dir.rglob("bin"):
                if (bin_dir / "ffmpeg.exe").exists():
                    os.environ["PATH"] = str(bin_dir) + os.pathsep + os.environ["PATH"]
                    return True
    return False

# Setup ffmpeg before importing services that might depend on it
setup_ffmpeg()

from PySide6.QtWidgets import QApplication
from src.ui.main_window import MainWindow
from src.core.queue_manager import QueueManager
from src.services.media import MediaService
from src.services.transcriber import TranscriptionService
from src.core.cpu_manager import CpuManager

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
    
    # Initialize CPU Manager
    cpu_manager = CpuManager()
    cpu_manager.start()
    
    # Load Thai-compatible font for 100% language support
    font_dir = os.path.join(base_dir, "assets", "font", "Sarabun")
    if os.path.exists(font_dir):
        for font_file in os.listdir(font_dir):
            if font_file.endswith(".ttf"):
                QFontDatabase.addApplicationFont(os.path.join(font_dir, font_file))
        
        # Set Sarabun as default font
        app.setFont("Sarabun")
    
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # 2. Initialize Services
    media_service = MediaService(temp_dir=temp_dir)
    # We pass None initially and will initialize it when needed or in background
    transcriber_service = None 
    
    queue_manager = QueueManager(
        media_service=media_service,
        transcriber_service=transcriber_service,
        output_dir=output_dir,
        max_concurrent=10
    )
    
    # 3. Apply Style
    if os.path.exists(qss_path):
        with open(qss_path, "r") as f:
            app.setStyleSheet(f.read())
            
    # 4. Launch UI
    window = MainWindow(queue_manager, cpu_manager, config={})
    window.show()
    
    exit_code = app.exec()
    
    # Cleanup
    cpu_manager.stop()
    cpu_manager.wait()
    
    sys.exit(exit_code)

if __name__ == "__main__":
    main()
