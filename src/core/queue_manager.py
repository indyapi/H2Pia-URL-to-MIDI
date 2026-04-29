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
        self.active_tasks = {}
        self.pending_tasks = []
        
        self.queue_timer = QTimer()
        self.queue_timer.timeout.connect(self.process_queue)
        self.queue_timer.start(2000)

    def set_output_format(self, fmt):
        self.output_format = fmt

    def set_concurrency_limit(self, limit):
        self.threadpool.setMaxThreadCount(limit)
        self.process_queue()

    def add_task(self, item_id, url):
        self.pending_tasks.append((item_id, url))
        self.task_progress.emit(item_id, "Waiting in queue...", 0)
        self.process_queue()

    def cancel_task(self, item_id):
        # Remove from pending
        for i, (pid, _) in enumerate(self.pending_tasks):
            if pid == item_id:
                self.pending_tasks.pop(i)
                return
        # Remove from active
        if item_id in self.active_tasks:
            worker = self.active_tasks[item_id]
            worker.cancel()
            del self.active_tasks[item_id]
            gc.collect()
            self.process_queue()

    def cancel_all(self):
        """Stops all pending and active tasks."""
        self.pending_tasks.clear()
        active_ids = list(self.active_tasks.keys())
        for item_id in active_ids:
            worker = self.active_tasks[item_id]
            worker.cancel()
            del self.active_tasks[item_id]
        self.threadpool.clear() # Prevent new threads from starting
        self.threadpool.waitForDone(1000) # Wait up to 1 second
        gc.collect()

    def process_queue(self):
        if not self.pending_tasks:
            return

        if len(self.active_tasks) >= self.threadpool.maxThreadCount():
            return

        can_start, reason = self.resource_manager.can_start_task()
        if not can_start:
            for item_id, _ in self.pending_tasks:
                self.task_progress.emit(item_id, f"Waiting: {reason}", 0)
            return

        item_id, url = self.pending_tasks.pop(0)
        worker = TranscriptionWorker(
            item_id, url, self.media_service, 
            self.transcriber_service, self.output_dir, self.output_format,
            self.resource_manager
        )
        
        worker.signals.progress.connect(self.task_progress.emit)
        worker.signals.finished.connect(self.handle_finished)
        worker.signals.error.connect(self.handle_error)
        worker.signals.metadata.connect(self.task_metadata.emit)
        
        self.active_tasks[item_id] = worker
        self.threadpool.start(worker)
        self.task_started.emit(item_id)

    def handle_finished(self, item_id):
        if item_id in self.active_tasks:
            del self.active_tasks[item_id]
        gc.collect()
        self.process_queue()

    def handle_error(self, item_id, error_msg):
        logger.error(f"Queue Error (ID: {item_id}): {error_msg}")
        if item_id in self.active_tasks:
            del self.active_tasks[item_id]
        
        self.task_error.emit(item_id, error_msg)
        
        # Trigger immediate resource cleanup on error
        gc.collect()
        # Continue with next items in queue
        self.process_queue()
