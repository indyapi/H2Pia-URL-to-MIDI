import os
import re
import traceback
import logging
import time
import math
from PySide6.QtCore import QRunnable, Slot, QObject, Signal

logger = logging.getLogger(__name__)

class WorkerSignals(QObject):
    finished = Signal(str)
    error = Signal(str, str)
    progress = Signal(str, str, int)
    metadata = Signal(str, dict)

class TranscriptionWorker(QRunnable):
    def __init__(self, item_id, url, media_service, transcriber_service, output_dir, output_format, resource_manager):
        super().__init__()
        self.item_id = item_id
        self.url = url
        self.media_service = media_service
        self.transcriber_service = transcriber_service
        self.output_dir = output_dir
        self.output_format = output_format
        self.resource_manager = resource_manager
        self.signals = WorkerSignals()
        self._is_cancelled = False
        self._ai_process = None

    def cancel(self):
        self._is_cancelled = True
        self._cleanup_process()

    def _cleanup_process(self):
        if self._ai_process and self._ai_process.is_alive():
            try:
                logger.info(f"Terminating AI Process {self.item_id}")
                self._ai_process.terminate()
                self._ai_process.join(timeout=2)
                if self._ai_process.is_alive():
                    self._ai_process.kill() # Force kill if terminate fails
            except: pass
        self._ai_process = None

    @Slot()
    def run(self):
        if self._is_cancelled: return
        temp_file = None
        try:
            # Helper to check for pause
            def wait_if_paused():
                while self.resource_manager.is_paused:
                    if self._is_cancelled: break
                    time.sleep(1)

            # Stage 1: Metadata
            wait_if_paused()
            self.signals.progress.emit(self.item_id, "Fetching metadata...", 5)
            try:
                meta = self.media_service.get_metadata(self.url)
            except Exception as e:
                raise Exception(f"Metadata failed: {str(e)}")
                
            if self._is_cancelled: return
            self.signals.metadata.emit(self.item_id, meta)
            
            duration = meta.get('duration', 60)
            safe_title = re.sub(r'[<>:"/\\|?*]', '', meta['title']).strip()
            if not safe_title: safe_title = f"media_{self.item_id}"
            
            mapping = {"MIDI": "MIDI", "MP4_FULL": "MP4 Full", "MP4_1080P": "MP4 1080p", "MP4_720P": "MP4 720p", "MP4_VIDEO_ONLY": "MP4 Video Only"}
            format_name = mapping.get(self.output_format, self.output_format)
            format_folder = os.path.join(self.output_dir, format_name)
            if not os.path.exists(format_folder): os.makedirs(format_folder)

            # Stage 2: Processing
            if self.output_format == "MIDI":
                wait_if_paused()
                self.signals.progress.emit(self.item_id, "Downloading audio...", 15)
                temp_path = os.path.join("temp", f"temp_{self.item_id}")
                try:
                    temp_file = self.media_service.download(self.url, temp_path, "MIDI")
                except Exception as e:
                    raise Exception(f"Download failed: {str(e)}")
                    
                if self._is_cancelled: return
                
                # Start AI Sub-process
                wait_if_paused()
                # Progress stays at 30% while processing in background
                self.signals.progress.emit(self.item_id, "Processing...", 30)
                final_path = self.media_service.get_unique_path(format_folder, safe_title, "mid")
                self._ai_process = self.transcriber_service.transcribe(temp_file, final_path)
                
                while self._ai_process.is_alive():
                    if self._is_cancelled: break
                    wait_if_paused()
                    time.sleep(1)
                
                self._ai_process.join()
                if self._ai_process.exitcode != 0 and not self._is_cancelled:
                    if os.path.exists(final_path):
                        try: os.remove(final_path)
                        except: pass
                    raise Exception("AI Transcription failed internally.")
                
                if not self._is_cancelled:
                    wait_if_paused()
                    # Progress jumps only after background process is complete
                    self.signals.progress.emit(self.item_id, "Completing...", 95)
            else:
                # Other formats (Direct Download)
                wait_if_paused()
                self.signals.progress.emit(self.item_id, f"Downloading {format_name}...", 20)
                ext_map = {"OPUS": "opus", "AAC": "m4a", "MP3": "mp3", "FLAC": "flac", "WAV": "wav", "MP4_FULL": "mp4", "MP4_1080P": "mp4", "MP4_720P": "mp4", "MP4_VIDEO_ONLY": "mp4"}
                ext = ext_map.get(self.output_format, "media")
                unique_target = self.media_service.get_unique_path(format_folder, safe_title, ext)
                try:
                    self.media_service.download(self.url, os.path.splitext(unique_target)[0], self.output_format)
                except Exception as e:
                    if os.path.exists(unique_target): os.remove(unique_target)
                    raise Exception("Media download failed.")

            if not self._is_cancelled:
                wait_if_paused()
                self.signals.progress.emit(self.item_id, "Finished", 100)
                self.signals.finished.emit(self.item_id)
            
        except Exception as e:
            if not self._is_cancelled:
                logger.error(f"Worker {self.item_id} failed: {str(e)}")
                self.signals.error.emit(self.item_id, str(e))
        finally:
            # Absolute Cleanup on any exit (Success, Error, or Cancel)
            self._cleanup_process()
            if temp_file and os.path.exists(temp_file):
                try: os.remove(temp_file)
                except: pass
            import gc
            gc.collect()
