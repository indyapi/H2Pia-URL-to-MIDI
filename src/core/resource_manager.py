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
            "app_ram": 0,
            "net_down": 0,
            "net_up": 0
        }
        
        # Network tracking
        self.last_net_io = psutil.net_io_counters()
        self.last_net_time = time.time()

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
        if self.stats["app_cpu"] > 60 or self.stats["app_ram"] > 60:
            return False, "App using > 60% resources"
        if self.stats["total_cpu"] > 85 or self.stats["total_ram"] > 85:
            return False, "System resources < 15% available"
        return True, "OK"

    def run(self):
        while self.running:
            try:
                # 1. Resource Monitoring (Internal Safety)
                total_cpu = psutil.cpu_percent(interval=0.5)
                remaining_cpu = 100 - total_cpu
                ram_info = psutil.virtual_memory()
                total_ram_pct = ram_info.percent
                remaining_ram = 100 - total_ram_pct
                
                with self.process.oneshot():
                    app_cpu = self.process.cpu_percent() / psutil.cpu_count()
                    app_ram = self.process.memory_percent()

                # 2. Network Monitoring (Real-time)
                current_net_io = psutil.net_io_counters()
                current_time = time.time()
                time_delta = current_time - self.last_net_time
                
                if time_delta > 0:
                    net_down = (current_net_io.bytes_recv - self.last_net_io.bytes_recv) / time_delta
                    net_up = (current_net_io.bytes_sent - self.last_net_io.bytes_sent) / time_delta
                else:
                    net_down, net_up = 0, 0
                
                self.last_net_io = current_net_io
                self.last_net_time = current_time

                self.stats = {
                    "total_cpu": total_cpu,
                    "total_ram": total_ram_pct,
                    "app_cpu": app_cpu,
                    "app_ram": app_ram,
                    "net_down": net_down,
                    "net_up": net_up
                }
                self.stats_updated.emit(self.stats)

                # Safety Logic
                critical_reason = None
                if remaining_cpu < 7:
                    critical_reason = f"System CPU critically low ({remaining_cpu:.1f}%)."
                if remaining_ram < 7:
                    critical_reason = f"System RAM critically low ({remaining_ram:.1f}%)."

                if critical_reason:
                    if not self.is_paused:
                        self.pause_process()
                        self.toast_notification.emit(f"{critical_reason} Pausing...")
                elif self.is_paused:
                    if remaining_cpu >= 8 and remaining_ram >= 8:
                        self.resume_process()
                        self.toast_notification.emit("Resources available. Resuming.")

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
