import os
import re
import traceback
import logging
import shutil
from PySide6.QtCore import QRunnable, Slot, QObject, Signal
from ..services.transcriber import TranscriptionService

logger = logging.getLogger(__name__)

class WorkerSignals(QObject):
    finished = Signal(str)
    error = Signal(str, str)
    progress = Signal(str, str, int)
    metadata = Signal(str, dict)
    service_initialized = Signal(object)

class TranscriptionWorker(QRunnable):
    def __init__(self, item_id, url, media_service, transcriber_service, output_dir, output_format):
        super().__init__()
        self.item_id = item_id
        self.url = url
        self.media_service = media_service
        self.transcriber_service = transcriber_service
        self.output_dir = output_dir
        self.output_format = output_format # Internal code: MIDI, MP4_FULL, etc.
        self.signals = WorkerSignals()

    def get_format_display_name(self):
        # Map internal code to nice folder names
        mapping = {
            "MIDI": "MIDI",
            "OPUS": "Opus", "AAC": "AAC", "MP3": "MP3", "FLAC": "FLAC", "WAV": "WAV",
            "MP4_FULL": "MP4 Full", "MP4_1080P": "MP4 1080p", 
            "MP4_720P": "MP4 720p", "MP4_VIDEO_ONLY": "MP4 Video Only"
        }
        return mapping.get(self.output_format, self.output_format)

    @Slot()
    def run(self):
        logger.info(f"Worker started: {self.item_id} (Format: {self.output_format})")
        temp_file = None
        try:
            # 1. Metadata
            self.signals.progress.emit(self.item_id, "Fetching metadata...", 10)
            meta = self.media_service.get_metadata(self.url)
            self.signals.metadata.emit(self.item_id, meta)
            
            safe_title = re.sub(r'[<>:"/\\|?*]', '', meta['title']).strip()
            if not safe_title: safe_title = f"media_{self.item_id}"
            
            # 2. Setup format folder (Precise naming)
            format_name = self.get_format_display_name()
            format_folder = os.path.join(self.output_dir, format_name)
            if not os.path.exists(format_folder): os.makedirs(format_folder)
            
            # 3. Download / Transcribe
            self.signals.progress.emit(self.item_id, f"Processing {format_name}...", 30)
            
            if self.output_format == "MIDI":
                temp_path = os.path.join("temp", f"temp_{self.item_id}")
                temp_file = self.media_service.download(self.url, temp_path, "MIDI")
                
                if self.transcriber_service is None:
                    self.signals.progress.emit(self.item_id, "Initializing AI...", 40)
                    self.transcriber_service = TranscriptionService(device='cpu')
                    self.signals.service_initialized.emit(self.transcriber_service)
                
                self.signals.progress.emit(self.item_id, "Transcribing...", 60)
                # Apply versioning for MIDI
                final_path = self.media_service.get_unique_path(format_folder, safe_title, "mid")
                self.transcriber_service.transcribe(temp_file, final_path)
            else:
                # Audio/Video Download
                # First, get a unique path
                ext = "mp4" if "MP4" in self.output_format else self.output_format.lower()
                if ext == "opus": ext = "opus"
                elif ext == "aac": ext = "m4a"
                
                # Logic for extension mapping
                ext_map = {"OPUS": "opus", "AAC": "m4a", "MP3": "mp3", "FLAC": "flac", "WAV": "wav", 
                           "MP4_FULL": "mp4", "MP4_1080P": "mp4", "MP4_720P": "mp4", "MP4_VIDEO_ONLY": "mp4"}
                ext = ext_map.get(self.output_format, "media")
                
                unique_target = self.media_service.get_unique_path(format_folder, safe_title, ext)
                target_no_ext = os.path.splitext(unique_target)[0]
                
                self.media_service.download(self.url, target_no_ext, self.output_format)
            
            self.signals.progress.emit(self.item_id, "Finished", 100)
            self.signals.finished.emit(self.item_id)
            
        except Exception as e:
            logger.error(f"Worker failed: {str(e)}")
            self.signals.error.emit(self.item_id, str(e))
        finally:
            if temp_file and os.path.exists(temp_file):
                try: os.remove(temp_file)
                except: pass
