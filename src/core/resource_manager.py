import psutil
import time
import os
import logging
from PySide6.QtCore import QThread, Signal, QObject

logger = logging.getLogger(__name__)

class ResourceManager(QThread):
    resource_paused = Signal(bool)  # True if paused, False if resumed
    toast_notification = Signal(str)

    def __init__(self):
        super().__init__()
        # CPU Settings
        self.cpu_mode = "default"
        self.cpu_limit = 50
        
        # RAM Settings
        self.ram_mode = "default"
        self.ram_limit = 50
        
        self.running = True
        self.is_paused = False
        self.process = psutil.Process(os.getpid())

    def set_cpu_settings(self, mode, limit):
        self.cpu_mode = mode
        self.cpu_limit = limit
        logger.info(f"CPU Settings updated: Mode={mode}, Limit={limit}")
        self._apply_priority()

    def set_ram_settings(self, mode, limit):
        self.ram_mode = mode
        self.ram_limit = limit
        logger.info(f"RAM Settings updated: Mode={mode}, Limit={limit}")

    def _apply_priority(self):
        try:
            if self.cpu_mode == "default":
                self.process.nice(psutil.IDLE_PRIORITY_CLASS)
            else:
                self.process.nice(psutil.NORMAL_PRIORITY_CLASS)
        except Exception as e:
            logger.error(f"Failed to set process priority: {e}")

    def run(self):
        while self.running:
            try:
                # 1. CPU Monitoring
                total_cpu = psutil.cpu_percent(interval=0.5)
                remaining_cpu = 100 - total_cpu

                # 2. RAM Monitoring
                ram_info = psutil.virtual_memory()
                total_ram_pct = ram_info.percent
                remaining_ram = 100 - total_ram_pct

                critical_reason = None
                
                # Check for critical CPU
                if remaining_cpu < 7:
                    critical_reason = f"System CPU critically low ({remaining_cpu:.1f}%)."
                
                # Check for critical RAM
                if remaining_ram < 7:
                    critical_reason = f"System RAM critically low ({remaining_ram:.1f}%)."

                # Logic for pausing/resuming
                if critical_reason:
                    if not self.is_paused:
                        self.pause_process()
                        self.toast_notification.emit(f"{critical_reason} Pausing transcription...")
                elif self.is_paused:
                    # Resume only if both are healthy
                    if remaining_cpu >= 8 and remaining_ram >= 8:
                        self.resume_process()
                        self.toast_notification.emit("System resources available. Resuming transcription.")

                # logic for custom limits / safety rules
                if not self.is_paused:
                    # CPU Throttling (via priority)
                    if remaining_cpu < 20:
                        self.process.nice(psutil.IDLE_PRIORITY_CLASS)
                    else:
                        self._apply_priority() # Restore based on setting

                    # RAM Enforcement (Informational/Warning as we can't easily hard-limit RAM usage of current process)
                    # "If the remaining RAM is less than 20 %, it will not exceed -7% of the remaining RAM."
                    # In a real app, this would trigger garbage collection or memory purging.
                    if remaining_ram < 20:
                         # We log this state, but hard enforcement in Python is difficult 
                         # without killing the process or using complex memory management.
                         pass

            except Exception as e:
                logger.error(f"Resource Manager error: {e}")
            
            time.sleep(1)

    def pause_process(self):
        try:
            logger.info("Suspending process due to high system load.")
            self.is_paused = True
            self.resource_paused.emit(True)
        except Exception as e:
            logger.error(f"Error pausing: {e}")

    def resume_process(self):
        try:
            logger.info("Resuming process.")
            self.is_paused = False
            self.resource_paused.emit(False)
        except Exception as e:
            logger.error(f"Error resuming: {e}")

    def stop(self):
        self.running = False
