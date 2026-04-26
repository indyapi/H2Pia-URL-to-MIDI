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

    def __init__(self, media_service, transcriber_service, output_dir, max_concurrent=10):
        super().__init__()
        self.media_service = media_service
        self.transcriber_service = transcriber_service
        self.output_dir = output_dir
        
        self.threadpool = QThreadPool()
        self.threadpool.setMaxThreadCount(max_concurrent)
        self.active_tasks = {}
        logger.info(f"QueueManager initialized with max_concurrent={max_concurrent}")

    def add_task(self, item_id, url):
        """Creates and starts a new transcription worker."""
        logger.info(f"Adding task to queue: {url} (ID: {item_id})")
        
        # We now move the lazy initialization into the Worker thread itself 
        # or handle it differently to avoid UI freeze.
        # But TranscriptionWorker needs the service.
        # Strategy: Pass the class/params and let the worker init it if None.

        worker = TranscriptionWorker(
            item_id, url, 
            self.media_service, 
            self.transcriber_service, # Might be None
            self.output_dir
        )
        
        # Connect worker signals
        worker.signals.progress.connect(self.task_progress.emit)
        worker.signals.finished.connect(self.handle_finished)
        worker.signals.error.connect(self.handle_error)
        worker.signals.metadata.connect(self.task_metadata.emit)
        # Add a signal for when the worker initializes the global service
        if hasattr(worker.signals, 'service_initialized'):
            worker.signals.service_initialized.connect(self.on_service_initialized)
        
        self.active_tasks[item_id] = worker
        self.threadpool.start(worker)
        self.task_started.emit(item_id)

    def on_service_initialized(self, service):
        """Global service is shared once the first worker creates it."""
        if self.transcriber_service is None:
            self.transcriber_service = service
            # Update all existing workers with the new service
            for worker in self.active_tasks.values():
                worker.transcriber_service = service

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
