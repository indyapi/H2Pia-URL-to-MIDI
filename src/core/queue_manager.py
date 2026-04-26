import logging
from PySide6.QtCore import QObject, QThreadPool, Signal, QTimer
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

    def __init__(self, media_service, transcriber_service, output_dir, resource_manager, max_concurrent=10):
        super().__init__()
        self.media_service = media_service
        self.transcriber_service = transcriber_service
        self.output_dir = output_dir
        self.resource_manager = resource_manager
        self.output_format = "MIDI" # Default
        
        self.threadpool = QThreadPool()
        self.threadpool.setMaxThreadCount(max_concurrent)
        
        self.active_tasks = {}
        self.pending_tasks = [] # List of (item_id, url)
        
        # Check resources periodically to start pending tasks
        self.queue_timer = QTimer()
        self.queue_timer.timeout.connect(self.process_queue)
        self.queue_timer.start(2000) 
        
        logger.info(f"QueueManager initialized with max_concurrent={max_concurrent}")

    def set_output_format(self, fmt):
        self.output_format = fmt
        logger.info(f"QueueManager format set to: {fmt}")

    def add_task(self, item_id, url):
        """Adds a task to the pending list."""
        logger.info(f"Task added to pending queue: {url} (ID: {item_id})")
        self.pending_tasks.append((item_id, url))
        self.task_progress.emit(item_id, "Waiting for resources...", 0)
        self.process_queue()

    def process_queue(self):
        """Starts tasks from the pending list if resources are available."""
        if not self.pending_tasks:
            return

        # Check if we have slot in threadpool
        if len(self.active_tasks) >= self.threadpool.maxThreadCount():
            return

        # Check ResourceManager conditions
        can_start, reason = self.resource_manager.can_start_task()
        
        if not can_start:
            for item_id, _ in self.pending_tasks:
                self.task_progress.emit(item_id, f"Waiting: {reason}", 0)
            return

        # Start the next task
        item_id, url = self.pending_tasks.pop(0)
        
        worker = TranscriptionWorker(
            item_id, url, 
            self.media_service, 
            self.transcriber_service,
            self.output_dir,
            self.output_format # Pass the format
        )
        
        worker.signals.progress.connect(self.task_progress.emit)
        worker.signals.finished.connect(self.handle_finished)
        worker.signals.error.connect(self.handle_error)
        worker.signals.metadata.connect(self.task_metadata.emit)
        worker.signals.service_initialized.connect(self.on_service_initialized)
        
        self.active_tasks[item_id] = worker
        self.threadpool.start(worker)
        self.task_started.emit(item_id)

    def on_service_initialized(self, service):
        if self.transcriber_service is None:
            self.transcriber_service = service
            for worker in self.active_tasks.values():
                worker.transcriber_service = service

    def handle_finished(self, item_id):
        logger.info(f"Task finished: {item_id}")
        if item_id in self.active_tasks:
            del self.active_tasks[item_id]
        self.task_finished.emit(item_id)
        self.process_queue()

    def handle_error(self, item_id, error_msg):
        logger.error(f"Task error (ID: {item_id}): {error_msg}")
        if item_id in self.active_tasks:
            del self.active_tasks[item_id]
        self.task_error.emit(item_id, error_msg)
        self.process_queue()
