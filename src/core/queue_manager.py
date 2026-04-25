import logging
from PySide6.QtCore import QObject, QThreadPool, Signal
from .worker import TranscriptionWorker
from ..services.transcriber import TranscriptionService

logger = logging.getLogger(__name__)

class QueueManager(QObject):
    # Signals for the UI
    task_started = Signal(str)      # id
    task_progress = Signal(str, str, int) # id, status, progress
    task_finished = Signal(str)     # id
    task_error = Signal(str, str)   # id, error
    task_metadata = Signal(str, dict) # id, metadata

    def __init__(self, youtube_service, transcriber_service, output_dir, max_concurrent=10):
        super().__init__()
        self.yt_service = youtube_service
        self.transcriber_service = transcriber_service
        self.output_dir = output_dir
        
        self.threadpool = QThreadPool()
        self.threadpool.setMaxThreadCount(max_concurrent)
        self.active_tasks = {}
        logger.info(f"QueueManager initialized with max_concurrent={max_concurrent}")

    def add_task(self, item_id, url):
        """Creates and starts a new transcription worker."""
        logger.info(f"Adding task to queue: {url} (ID: {item_id})")
        
        # Lazy initialization of transcriber service
        if self.transcriber_service is None:
            logger.info("First task added. Initializing TranscriptionService...")
            self.task_progress.emit(item_id, "Initializing AI Model...", 0)
            try:
                self.transcriber_service = TranscriptionService(device='cpu')
            except Exception as e:
                logger.error(f"Failed to initialize TranscriptionService: {e}")
                self.handle_error(item_id, f"Model Init Failed: {e}")
                return

        worker = TranscriptionWorker(
            item_id, url, 
            self.yt_service, 
            self.transcriber_service, 
            self.output_dir
        )
        
        # Connect worker signals to QueueManager signals
        worker.signals.progress.connect(self.task_progress.emit)
        worker.signals.finished.connect(self.handle_finished)
        worker.signals.error.connect(self.handle_error)
        worker.signals.metadata.connect(self.task_metadata.emit)
        
        self.active_tasks[item_id] = worker
        self.threadpool.start(worker)
        self.task_started.emit(item_id)

    def handle_finished(self, item_id):
        logger.info(f"Task finished: {item_id}")
        if item_id in self.active_tasks:
            del self.active_tasks[item_id]
        self.task_finished.emit(item_id)

    def handle_error(self, item_id, error_msg):
        logger.error(f"Task error (ID: {item_id}): {error_msg}")
        if item_id in self.active_tasks:
            del self.active_tasks[item_id]
        self.task_error.emit(item_id, error_msg)
