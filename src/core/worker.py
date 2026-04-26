import os
import re
import traceback
import logging
import shutil
from PySide6.QtCore import QRunnable, Slot, QObject, Signal

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
        self.output_format = output_format
        self.signals = WorkerSignals()
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True
        logger.info(f"Worker {self.item_id} marked for cancellation.")

    @Slot()
    def run(self):
        if self._is_cancelled: return
        
        logger.info(f"Worker started: {self.item_id}")
        temp_file = None
        try:
            # Stage 1: Metadata
            self.signals.progress.emit(self.item_id, "Fetching metadata...", 10)
            meta = self.media_service.get_metadata(self.url)
            if self._is_cancelled: return
            self.signals.metadata.emit(self.item_id, meta)
            
            safe_title = re.sub(r'[<>:"/\\|?*]', '', meta['title']).strip()
            if not safe_title: safe_title = f"media_{self.item_id}"
            
            format_mapping = {
                "MIDI": "MIDI", "OPUS": "Opus", "AAC": "AAC", "MP3": "MP3", "FLAC": "FLAC", "WAV": "WAV",
                "MP4_FULL": "MP4 Full", "MP4_1080P": "MP4 1080p", "MP4_720P": "MP4 720p", "MP4_VIDEO_ONLY": "MP4 Video Only"
            }
            format_name = format_mapping.get(self.output_format, self.output_format)
            format_folder = os.path.join(self.output_dir, format_name)
            if not os.path.exists(format_folder): os.makedirs(format_folder)

            # Stage 2: Download
            self.signals.progress.emit(self.item_id, f"Downloading {format_name}...", 30)
            
            if self.output_format == "MIDI":
                temp_path = os.path.join("temp", f"temp_{self.item_id}")
                temp_file = self.media_service.download(self.url, temp_path, "MIDI")
                if self._is_cancelled: return
                
                # Lazy load AI with memory safety
                from ..services.transcriber import TranscriptionService
                if self.transcriber_service is None:
                    self.signals.progress.emit(self.item_id, "Loading AI (High RAM)...", 45)
                    self.transcriber_service = TranscriptionService(device='cpu')
                    self.signals.service_initialized.emit(self.transcriber_service)
                
                if self._is_cancelled: return
                self.signals.progress.emit(self.item_id, "Transcribing to MIDI...", 70)
                final_path = self.media_service.get_unique_path(format_folder, safe_title, "mid")
                self.transcriber_service.transcribe(temp_file, final_path)
            else:
                ext_map = {"OPUS": "opus", "AAC": "m4a", "MP3": "mp3", "FLAC": "flac", "WAV": "wav", 
                           "MP4_FULL": "mp4", "MP4_1080P": "mp4", "MP4_720P": "mp4", "MP4_VIDEO_ONLY": "mp4"}
                ext = ext_map.get(self.output_format, "media")
                unique_target = self.media_service.get_unique_path(format_folder, safe_title, ext)
                target_no_ext = os.path.splitext(unique_target)[0]
                self.media_service.download(self.url, target_no_ext, self.output_format)

            if not self._is_cancelled:
                self.signals.progress.emit(self.item_id, "Finished", 100)
                self.signals.finished.emit(self.item_id)
            
        except Exception as e:
            if not self._is_cancelled:
                logger.error(f"Worker failed: {str(e)}")
                self.signals.error.emit(self.item_id, str(e))
        finally:
            if temp_file and os.path.exists(temp_file):
                try: os.remove(temp_file)
                except: pass
            # Release local reference to service
            self.transcriber_service = None
