import psutil
import time
import os
import logging
from PySide6.QtCore import QThread, Signal, QObject

logger = logging.getLogger(__name__)

class ResourceManager(QThread):
    resource_paused = Signal(bool)
    toast_notification = Signal(str)
    stats_updated = Signal(dict)

    def __init__(self):
        super().__init__()
        self.cpu_mode = "default"
        self.cpu_limit = 100
        self.ram_mode = "default"
        self.ram_limit = 100
        
        self.running = True
        self.is_paused = False
        self.process = psutil.Process(os.getpid())
        
        self.stats = {
            "total_cpu": 0, "total_ram": 0,
            "app_cpu": 0, "app_ram": 0,
            "net_down": 0, "net_up": 0
        }
        
        self.last_net_io = psutil.net_io_counters()
        self.last_net_time = time.time()

    def set_cpu_settings(self, mode, limit):
        self.cpu_mode = mode
        self.cpu_limit = limit
        self._apply_priority()

    def set_ram_settings(self, mode, limit):
        self.ram_mode = mode
        self.ram_limit = limit

    def _apply_priority(self):
        try:
            if self.cpu_mode == "default":
                self.process.nice(psutil.IDLE_PRIORITY_CLASS)
            else:
                self.process.nice(psutil.NORMAL_PRIORITY_CLASS)
        except: pass

    def can_start_task(self):
        """Pure settings-based check."""
        remaining_cpu = 100 - self.stats["total_cpu"]
        remaining_ram = 100 - self.stats["total_ram"]
        
        # Rule: If remaining < 20%, app must not exceed (remaining - 7%)
        if remaining_cpu < 20:
            cpu_safe = max(0, remaining_cpu - 7)
            if self.stats["app_cpu"] > cpu_safe:
                return False, "Waiting: CPU Safe Limit"

        if remaining_ram < 20:
            ram_safe = max(0, remaining_ram - 7)
            if self.stats["app_ram"] > ram_safe:
                return False, "Waiting: RAM Safe Limit"

        # Custom lock check
        if self.cpu_mode == "custom" and self.stats["app_cpu"] >= self.cpu_limit:
            return False, "Waiting: CPU Custom Lock"
        if self.ram_mode == "custom" and self.stats["app_ram"] >= self.ram_limit:
            return False, "Waiting: RAM Custom Lock"

        return True, "OK"

    def run(self):
        while self.running:
            try:
                # 1. Capture Stats
                total_cpu = psutil.cpu_percent(interval=0.5)
                ram_info = psutil.virtual_memory()
                total_ram_pct = ram_info.percent
                remaining_cpu = 100 - total_cpu
                remaining_ram = 100 - total_ram_pct
                
                with self.process.oneshot():
                    app_cpu = self.process.cpu_percent() / psutil.cpu_count()
                    app_ram = self.process.memory_percent()

                # 2. Network
                current_net_io = psutil.net_io_counters()
                current_time = time.time()
                time_delta = current_time - self.last_net_time
                net_down = (current_net_io.bytes_recv - self.last_net_io.bytes_recv) / time_delta if time_delta > 0 else 0
                net_up = (current_net_io.bytes_sent - self.last_net_io.bytes_sent) / time_delta if time_delta > 0 else 0
                self.last_net_io, self.last_net_time = current_net_io, current_time

                self.stats.update({
                    "total_cpu": total_cpu, "total_ram": total_ram_pct,
                    "app_cpu": app_cpu, "app_ram": app_ram,
                    "net_down": net_down, "net_up": net_up
                })
                self.stats_updated.emit(self.stats)

                # 3. Critical Safety (< 7% triggers Toast + Pause)
                critical_reason = None
                if remaining_cpu < 7: critical_reason = "CPU"
                elif remaining_ram < 7: critical_reason = "RAM"

                if critical_reason:
                    if not self.is_paused:
                        self.is_paused = True
                        self.resource_paused.emit(True)
                        self.toast_notification.emit(f"Critically low {critical_reason} (<7%). Pausing process.")
                elif self.is_paused:
                    if remaining_cpu >= 8 and remaining_ram >= 8:
                        self.is_paused = False
                        self.resource_paused.emit(False)
                        self.toast_notification.emit("Resources restored. Resuming.")

                # Eco-mode priority
                if not self.is_paused and remaining_cpu < 20:
                    self.process.nice(psutil.IDLE_PRIORITY_CLASS)
                elif not self.is_paused:
                    self._apply_priority()

            except Exception as e:
                logger.error(f"Resource Manager error: {e}")
            time.sleep(0.5)

    def stop(self):
        self.running = False
