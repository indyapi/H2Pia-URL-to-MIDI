import os
import re
import traceback
import logging
from PySide6.QtCore import QRunnable, Slot, QObject, Signal
from ..services.transcriber import TranscriptionService

logger = logging.getLogger(__name__)

class WorkerSignals(QObject):
    """
    Defines the signals available from a running worker thread.
    """
    finished = Signal(str)      # id
    error = Signal(str, str)    # id, error message
    progress = Signal(str, str, int) # id, status_text, progress_value
    metadata = Signal(str, dict) # id, metadata_dict
    service_initialized = Signal(object) # service instance

class TranscriptionWorker(QRunnable):
    def __init__(self, item_id, url, media_service, transcriber_service, output_dir):
        super().__init__()
        self.item_id = item_id
        self.url = url
        self.media_service = media_service
        self.transcriber_service = transcriber_service
        self.output_dir = output_dir
        self.signals = WorkerSignals()
        logger.info(f"Worker initialized for {url} (ID: {item_id})")

    @Slot()
    def run(self):
        logger.info(f"Worker started: {self.item_id}")
        audio_path = None
        try:
            # 1. Fetch Metadata
            logger.info(f"[{self.item_id}] Fetching metadata...")
            self.signals.progress.emit(self.item_id, "Fetching metadata...", 10)
            meta = self.media_service.get_metadata(self.url)
            self.signals.metadata.emit(self.item_id, meta)
            
            # Sanitize title
            safe_title = re.sub(r'[<>:"/\\|?*]', '', meta['title']).strip()
            if not safe_title:
                safe_title = f"video_{self.item_id}"
                
            audio_filename = f"{self.item_id}_{safe_title}"
            
            # 2. Download Audio
            logger.info(f"[{self.item_id}] Downloading audio...")
            self.signals.progress.emit(self.item_id, "Downloading audio...", 30)
            audio_path = self.media_service.download_audio(self.url, audio_filename)
            
            # 3. Transcribe
            # Lazy init service in background to avoid UI freeze
            if self.transcriber_service is None:
                logger.info(f"[{self.item_id}] Initializing AI Model in background...")
                self.signals.progress.emit(self.item_id, "Initializing AI Model (once)...", 40)
                self.transcriber_service = TranscriptionService(device='cpu')
                self.signals.service_initialized.emit(self.transcriber_service)

            logger.info(f"[{self.item_id}] Transcribing...")
            self.signals.progress.emit(self.item_id, "Transcribing (this may take a while)...", 60)
            midi_path = os.path.join(self.output_dir, f"{safe_title}.mid")
            self.transcriber_service.transcribe(audio_path, midi_path)
            
            # 4. Immediate Cleanup after Success
            if audio_path and os.path.exists(audio_path):
                logger.info(f"[{self.item_id}] Deleting temp audio: {audio_path}")
                os.remove(audio_path)
                audio_path = None # Mark as deleted
                
            logger.info(f"[{self.item_id}] Finished successfully.")
            self.signals.progress.emit(self.item_id, "Finished", 100)
            self.signals.finished.emit(self.item_id)
            
        except Exception as e:
            logger.error(f"[{self.item_id}] Worker failed: {str(e)}")
            logger.error(traceback.format_exc())
            self.signals.error.emit(self.item_id, str(e))
        finally:
            # Ensure cleanup happens even on failure
            if audio_path and os.path.exists(audio_path):
                try:
                    logger.info(f"[{self.item_id}] Cleaning up temp file after error.")
                    os.remove(audio_path)
                except:
                    pass
