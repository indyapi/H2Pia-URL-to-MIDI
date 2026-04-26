import logging
import gc
from PySide6.QtCore import QObject, QThreadPool, Signal, QTimer
from .worker import TranscriptionWorker

logger = logging.getLogger(__name__)

class QueueManager(QObject):
    task_started = Signal(str)
    task_progress = Signal(str, str, int)
    task_finished = Signal(str)
    task_error = Signal(str, str)
    task_metadata = Signal(str, dict)

    def __init__(self, media_service, transcriber_service, output_dir, resource_manager, max_concurrent=3):
        super().__init__()
        self.media_service = media_service
        self.transcriber_service = transcriber_service
        self.output_dir = output_dir
        self.resource_manager = resource_manager
        self.output_format = "MIDI"
        
        self.threadpool = QThreadPool()
        self.threadpool.setMaxThreadCount(max_concurrent)
        self.active_tasks = {} # item_id -> worker
        self.pending_tasks = []
        
        self.queue_timer = QTimer()
        self.queue_timer.timeout.connect(self.process_queue)
        self.queue_timer.start(2000)

    def set_output_format(self, fmt):
        self.output_format = fmt

    def set_concurrency_limit(self, limit):
        self.threadpool.setMaxThreadCount(limit)
        logger.info(f"Concurrency limit updated to: {limit}")
        self.process_queue()

    def add_task(self, item_id, url):
        self.pending_tasks.append((item_id, url))
        self.task_progress.emit(item_id, "Waiting in queue...", 0)
        self.process_queue()

    def cancel_task(self, item_id):
        for i, (pid, _) in enumerate(self.pending_tasks):
            if pid == item_id:
                self.pending_tasks.pop(i)
                return
        if item_id in self.active_tasks:
            worker = self.active_tasks[item_id]
            worker.cancel()
            worker.transcriber_service = None
            del self.active_tasks[item_id]
            if not self.active_tasks and self.transcriber_service:
                self.transcriber_service.cleanup()
                self.transcriber_service = None
            gc.collect()
            self.process_queue() # Try to start next immediately

    def process_queue(self):
        if not self.pending_tasks:
            if not self.active_tasks and self.transcriber_service:
                self.transcriber_service.cleanup()
                self.transcriber_service = None
                gc.collect()
            return

        # Check if we can start more work
        if len(self.active_tasks) >= self.threadpool.maxThreadCount():
            # Update labels for items waiting for concurrency slot
            for item_id, _ in self.pending_tasks:
                self.task_progress.emit(item_id, "Waiting (Queue full)...", 0)
            return

        can_start, reason = self.resource_manager.can_start_task()
        if not can_start:
            for item_id, _ in self.pending_tasks:
                self.task_progress.emit(item_id, f"Waiting: {reason}", 0)
            return

        # Start the next task
        item_id, url = self.pending_tasks.pop(0)
        worker = TranscriptionWorker(
            item_id, url, self.media_service, 
            self.transcriber_service, self.output_dir, self.output_format
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
            for w in self.active_tasks.values():
                if w.transcriber_service is None: w.transcriber_service = service

    def handle_finished(self, item_id):
        if item_id in self.active_tasks:
            self.active_tasks[item_id].transcriber_service = None
            del self.active_tasks[item_id]
        gc.collect()
        self.process_queue()

    def handle_error(self, item_id, error_msg):
        if item_id in self.active_tasks:
            self.active_tasks[item_id].transcriber_service = None
            del self.active_tasks[item_id]
        gc.collect()
        self.process_queue()
