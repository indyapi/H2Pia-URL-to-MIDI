import psutil
import time
import os
import logging
from PySide6.QtCore import QThread, Signal, QObject

logger = logging.getLogger(__name__)

class ResourceManager(QThread):
    resource_paused = Signal(bool)  # True if paused, False if resumed
    toast_notification = Signal(str)
    stats_updated = Signal(dict)

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
        
        # Current Stats
        self.stats = {
            "total_cpu": 0,
            "total_ram": 0,
            "app_cpu": 0,
            "app_ram": 0
        }

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

    def can_start_task(self):
        """
        Check if we can start a new task based on:
        - App usage < 60%
        - Total available > 15% (Total usage < 85%)
        """
        # App usage rules
        if self.stats["app_cpu"] > 60 or self.stats["app_ram"] > 60:
            return False, "App using > 60% resources"
            
        # Availability rules
        if self.stats["total_cpu"] > 85 or self.stats["total_ram"] > 85:
            return False, "System resources < 15% available"
            
        return True, "OK"

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
                
                # 3. App Specific
                with self.process.oneshot():
                    app_cpu = self.process.cpu_percent() / psutil.cpu_count()
                    app_ram = self.process.memory_percent()

                self.stats = {
                    "total_cpu": total_cpu,
                    "total_ram": total_ram_pct,
                    "app_cpu": app_cpu,
                    "app_ram": app_ram
                }
                self.stats_updated.emit(self.stats)

                critical_reason = None
                
                # Safety checks (Critical)
                if remaining_cpu < 7:
                    critical_reason = f"System CPU critically low ({remaining_cpu:.1f}%)."
                if remaining_ram < 7:
                    critical_reason = f"System RAM critically low ({remaining_ram:.1f}%)."

                if critical_reason:
                    if not self.is_paused:
                        self.pause_process()
                        self.toast_notification.emit(f"{critical_reason} Pausing transcription...")
                elif self.is_paused:
                    if remaining_cpu >= 8 and remaining_ram >= 8:
                        self.resume_process()
                        self.toast_notification.emit("System resources available. Resuming transcription.")

                # logic for custom limits / safety rules
                if not self.is_paused:
                    if remaining_cpu < 20:
                        self.process.nice(psutil.IDLE_PRIORITY_CLASS)
                    else:
                        self._apply_priority()

            except Exception as e:
                logger.error(f"Resource Manager error: {e}")
            
            time.sleep(0.5)

    def pause_process(self):
        self.is_paused = True
        self.resource_paused.emit(True)

    def resume_process(self):
        self.is_paused = False
        self.resource_paused.emit(False)

    def stop(self):
        self.running = False
