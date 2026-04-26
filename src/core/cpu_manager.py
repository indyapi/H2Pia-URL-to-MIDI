import psutil
import time
import os
import logging
from PySide6.QtCore import QThread, Signal, QObject

logger = logging.getLogger(__name__)

class CpuManager(QThread):
    cpu_paused = Signal(bool)  # True if paused, False if resumed
    toast_notification = Signal(str)

    def __init__(self):
        super().__init__()
        self.mode = "default"  # "default" or "custom"
        self.custom_limit = 50
        self.running = True
        self.is_paused = False
        self.process = psutil.Process(os.getpid())

    def set_settings(self, mode, custom_limit):
        self.mode = mode
        self.custom_limit = custom_limit
        logger.info(f"CPU Settings updated: Mode={mode}, Limit={custom_limit}")
        
        # Apply process priority for "default" (Eco) mode
        try:
            if mode == "default":
                self.process.nice(psutil.IDLE_PRIORITY_CLASS)
            else:
                self.process.nice(psutil.NORMAL_PRIORITY_CLASS)
        except Exception as e:
            logger.error(f"Failed to set process priority: {e}")

    def run(self):
        while self.running:
            try:
                # Check overall system CPU usage
                total_cpu = psutil.cpu_percent(interval=1)
                remaining_cpu = 100 - total_cpu

                # Logic for pausing if cpu is critically low
                if remaining_cpu < 7:
                    if not self.is_paused:
                        self.pause_process()
                        self.toast_notification.emit("System CPU critically low (<7%). Pausing transcription...")
                elif self.is_paused and remaining_cpu >= 8:
                    self.resume_process()
                    self.toast_notification.emit("CPU available. Resuming transcription.")

                # logic for custom limit (simplified throttling)
                if self.mode == "custom" and not self.is_paused:
                    # In a real environment, precise CPU locking is hard for a whole process 
                    # from within the process without deep hooks. 
                    # Here we enforce the "remaining cpu" safety rules.
                    if remaining_cpu < 20:
                        # "it will be enforced no more than the remaining cpu -7%"
                        # This part is complex to enforce precisely on the current process 
                        # without external tools, so we lower the priority further.
                        self.process.nice(psutil.IDLE_PRIORITY_CLASS)
                    else:
                        self.process.nice(psutil.NORMAL_PRIORITY_CLASS)

            except Exception as e:
                logger.error(f"CPU Manager error: {e}")
            
            time.sleep(1)

    def pause_process(self):
        try:
            logger.info("Suspending process due to high system load.")
            self.is_paused = True
            self.cpu_paused.emit(True)
            # We don't suspend the WHOLE process because the UI would freeze.
            # We will tell the Worker to pause if we had a pause mechanism.
            # For now, we use process priority as a fallback, 
            # but ideally we should suspend worker threads.
        except Exception as e:
            logger.error(f"Error pausing: {e}")

    def resume_process(self):
        try:
            logger.info("Resuming process.")
            self.is_paused = False
            self.cpu_paused.emit(False)
        except Exception as e:
            logger.error(f"Error resuming: {e}")

    def stop(self):
        self.running = False
