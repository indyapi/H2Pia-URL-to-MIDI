import os
import uuid
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QLineEdit, QPushButton, QScrollArea, QLabel, 
    QFileDialog, QMessageBox, QDialog, QRadioButton,
    QButtonGroup, QSpinBox, QGraphicsOpacityEffect, 
    QFrame, QGridLayout, QComboBox
)
from PySide6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, QPoint, Signal, Slot
from .queue_item import QueueItem

class SettingsDialog(QDialog):
    def __init__(self, parent=None, current_settings=None):
        super().__init__(parent)
        self.setWindowTitle("Settings"); self.setFixedWidth(450)
        self.settings = current_settings or {
            "cpu_mode": "default", "cpu_limit": 50, 
            "ram_mode": "default", "ram_limit": 50, 
            "queue_size_limit": 10, "concurrency_limit": 3
        }
        self.setStyleSheet("""
            QDialog { background-color: #0A192F; }
            QLabel { color: #CCD6F6; }
            QSpinBox {
                background-color: #112240;
                color: #64E8FF;
                border: 1px solid #233554;
                border-radius: 4px;
                padding: 4px;
                min-width: 60px;
                font-weight: bold;
            }
            QSpinBox::up-button, QSpinBox::down-button {
                background-color: #1d2d50;
                border: none;
                width: 16px;
            }
            QSpinBox::up-arrow { image: none; border-left: 4px solid transparent; border-right: 4px solid transparent; border-bottom: 5px solid #2EC1CC; }
            QSpinBox::down-arrow { image: none; border-left: 4px solid transparent; border-right: 4px solid transparent; border-top: 5px solid #2EC1CC; }
        """)
        self.init_ui()
    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("<b>CPU Limit Mode</b>"))
        self.cpu_group = QButtonGroup(self); self.cpu_default_rb = QRadioButton("Default (Background / Eco Mode)"); self.cpu_group.addButton(self.cpu_default_rb); layout.addWidget(self.cpu_default_rb)
        lbl_cpu = QLabel("Uses idle priority. Safety limits if remaining CPU < 20%."); lbl_cpu.setStyleSheet("color: #9DB3D1; font-size: 11px; margin-left: 20px;"); layout.addWidget(lbl_cpu)
        self.cpu_custom_rb = QRadioButton("Custom CPU Limit (%)"); self.cpu_group.addButton(self.cpu_custom_rb); layout.addWidget(self.cpu_custom_rb)
        cpu_custom_layout = QHBoxLayout(); cpu_custom_layout.setContentsMargins(20, 0, 0, 10); self.cpu_limit_spin = QSpinBox(); self.cpu_limit_spin.setRange(1, 100); self.cpu_limit_spin.setValue(self.settings.get("cpu_limit", 50))
        cpu_custom_layout.addWidget(QLabel("Max CPU Lock:")); cpu_custom_layout.addWidget(self.cpu_limit_spin); cpu_custom_layout.addWidget(QLabel("%")); cpu_custom_layout.addStretch(); layout.addLayout(cpu_custom_layout)
        layout.addWidget(QLabel("<b>RAM Restricted Mode</b>"))
        self.ram_group = QButtonGroup(self); self.ram_default_rb = QRadioButton("Default (Eco Mode)"); self.ram_group.addButton(self.ram_default_rb); layout.addWidget(self.ram_default_rb)
        lbl_ram = QLabel("Safety limits if remaining RAM < 20%."); lbl_ram.setStyleSheet("color: #9DB3D1; font-size: 11px; margin-left: 20px;"); layout.addWidget(lbl_ram)
        self.ram_custom_rb = QRadioButton("Custom RAM Limit (%)"); self.ram_group.addButton(self.ram_custom_rb); layout.addWidget(self.ram_custom_rb)
        ram_custom_layout = QHBoxLayout(); ram_custom_layout.setContentsMargins(20, 0, 0, 10); self.ram_limit_spin = QSpinBox(); self.ram_limit_spin.setRange(1, 100); self.ram_limit_spin.setValue(self.settings.get("ram_limit", 50))
        ram_custom_layout.addWidget(QLabel("Max RAM Lock:")); ram_custom_layout.addWidget(self.ram_limit_spin); ram_custom_layout.addWidget(QLabel("%")); ram_custom_layout.addStretch(); layout.addLayout(ram_custom_layout)
        layout.addWidget(QLabel("<b>Queue Settings</b>"))
        grid = QGridLayout()
        grid.addWidget(QLabel("Max Total Queue Size:"), 0, 0); self.queue_limit_spin = QSpinBox(); self.queue_limit_spin.setRange(1, 100); self.queue_limit_spin.setValue(self.settings.get("queue_size_limit", 10)); grid.addWidget(self.queue_limit_spin, 0, 1)
        grid.addWidget(QLabel("Max Simultaneous Tasks:"), 1, 0); self.concurrency_limit_spin = QSpinBox(); self.concurrency_limit_spin.setRange(1, 10); self.concurrency_limit_spin.setValue(self.settings.get("concurrency_limit", 3)); grid.addWidget(self.concurrency_limit_spin, 1, 1)
        layout.addLayout(grid)
        if self.settings.get("cpu_mode") == "default": self.cpu_default_rb.setChecked(True)
        else: self.cpu_custom_rb.setChecked(True)
        if self.settings.get("ram_mode") == "default": self.ram_default_rb.setChecked(True)
        else: self.ram_custom_rb.setChecked(True)
        layout.addSpacing(10); buttons = QHBoxLayout(); save_btn = QPushButton("Save Settings"); save_btn.setObjectName("Primary"); save_btn.clicked.connect(self.accept); cancel_btn = QPushButton("Cancel"); cancel_btn.clicked.connect(self.reject); buttons.addWidget(save_btn); buttons.addWidget(cancel_btn); layout.addLayout(buttons)
    def get_settings(self):
        return {"cpu_mode": "default" if self.cpu_default_rb.isChecked() else "custom", "cpu_limit": self.cpu_limit_spin.value(), "ram_mode": "default" if self.ram_default_rb.isChecked() else "custom", "ram_limit": self.ram_limit_spin.value(), "queue_size_limit": self.queue_limit_spin.value(), "concurrency_limit": self.concurrency_limit_spin.value()}

class FormatPopupMenu(QFrame):
    formatSelected = Signal(str, str)
    def __init__(self, parent):
        super().__init__(parent); self.setWindowFlags(Qt.Popup | Qt.FramelessWindowHint); self.setFixedWidth(280); self.setObjectName("FormatMenu")
        self.setStyleSheet("QFrame#FormatMenu { background-color: #112240; border: 2px solid #2EC1CC; border-radius: 12px; } QLabel#MenuHeader { color: #2EC1CC; font-weight: bold; font-size: 11px; padding: 10px 10px 5px 10px; background-color: transparent; } QPushButton#MenuButton { background-color: transparent; color: #CCD6F6; text-align: left; padding: 8px 15px; border: none; border-radius: 0px; font-size: 13px; } QPushButton#MenuButton:hover { background-color: #233554; color: #64E8FF; } QFrame#Separator { background-color: #233554; max-height: 1px; }")
        layout = QVBoxLayout(self); layout.setContentsMargins(5, 5, 5, 5); layout.setSpacing(0)
        layout.addWidget(self.create_header("PIANO TRANSCRIPTION")); self.add_option(layout, "MIDI File", "MIDI"); layout.addWidget(self.create_separator())
        layout.addWidget(self.create_header("AUDIO (SOUND)")); audio_opts = [("MP3 Audio", "MP3"), ("WAV (High Quality)", "WAV"), ("Opus (Web)", "OPUS"), ("AAC (M4A)", "AAC"), ("FLAC (Lossless)", "FLAC")]
        for label, key in audio_opts: self.add_option(layout, label, key)
        layout.addWidget(self.create_separator()); layout.addWidget(self.create_header("VIDEO")); video_opts = [("MP4 Full Quality", "MP4_FULL"), ("MP4 1080p", "MP4_1080P"), ("MP4 720p", "MP4_720P"), ("MP4 Video (No Audio)", "MP4_VIDEO_ONLY")]
        for label, key in video_opts: self.add_option(layout, label, key)
    def create_header(self, text):
        lbl = QLabel(text); lbl.setObjectName("MenuHeader"); return lbl
    def create_separator(self):
        sep = QFrame(); sep.setObjectName("Separator"); return sep
    def add_option(self, layout, label, key):
        btn = QPushButton(label); btn.setObjectName("MenuButton"); btn.clicked.connect(lambda: self.on_click(key, label)); layout.addWidget(btn)
    def on_click(self, key, label):
        self.formatSelected.emit(key, label); self.close()

class Toast(QLabel):
    closed = Signal(object)
    def __init__(self, parent, message):
        super().__init__(message, parent); self.setAlignment(Qt.AlignCenter); self.setWordWrap(True)
        self.setStyleSheet("background-color: #1E293B; color: #64E8FF; border: 2px solid #2EC1CC; border-radius: 12px; padding: 12px; font-size: 13px; font-weight: bold;")
        self.setFixedWidth(350); self.setFixedHeight(60); self.opacity_effect = QGraphicsOpacityEffect(self); self.opacity_effect.setOpacity(0); self.setGraphicsEffect(self.opacity_effect); self.show()
        self.fade_in_anim = QPropertyAnimation(self.opacity_effect, b"opacity"); self.fade_in_anim.setDuration(400); self.fade_in_anim.setStartValue(0.0); self.fade_in_anim.setEndValue(1.0); self.fade_in_anim.setEasingCurve(QEasingCurve.OutCubic); self.fade_in_anim.start()
        self.timer = QTimer(); self.timer.singleShot(5000, self.fade_out)
    def fade_out(self):
        self.anim = QPropertyAnimation(self.opacity_effect, b"opacity"); self.anim.setDuration(800); self.anim.setStartValue(1.0); self.anim.setEndValue(0.0); self.anim.finished.connect(self.on_closed); self.anim.start()
    def on_closed(self): self.closed.emit(self); self.deleteLater()

class MainWindow(QMainWindow):
    def __init__(self, queue_manager, resource_manager, config_manager):
        super().__init__(); self.queue_manager = queue_manager; self.resource_manager = resource_manager; self.config_manager = config_manager; self.items = {}; self.active_toasts = []; self.settings = self.config_manager.config
        self.setWindowTitle("U2M - YouTube to MIDI"); self.resize(900, 650); self.init_ui(); self.connect_signals()
        fmt_key = self.settings.get("output_format", "MIDI"); self.update_format_display(fmt_key)
    def init_ui(self):
        central_widget = QWidget(); self.setCentralWidget(central_widget); main_layout = QVBoxLayout(central_widget); main_layout.setContentsMargins(20, 20, 20, 20); main_layout.setSpacing(15)
        header_layout = QHBoxLayout()
        header = QLabel("U2M: Media Converter"); header.setObjectName("Header"); header.setStyleSheet("font-size: 24px;")
        header_layout.addWidget(header); header_layout.addStretch()
        self.settings_btn = QPushButton("⚙"); self.settings_btn.setFixedSize(40, 40); self.settings_btn.setStyleSheet("font-size: 20px; padding: 0;"); self.settings_btn.clicked.connect(self.show_settings); header_layout.addWidget(self.settings_btn)
        main_layout.addLayout(header_layout)
        input_layout = QHBoxLayout()
        self.url_input = QLineEdit(); self.url_input.setPlaceholderText("Paste URL here..."); self.url_input.setFixedHeight(40); self.url_input.returnPressed.connect(self.add_url)
        input_layout.addWidget(self.url_input)
        self.format_btn = QPushButton("Format: MIDI"); self.format_btn.setFixedHeight(40); self.format_btn.setMinimumWidth(160); self.format_btn.setStyleSheet("QPushButton { background-color: #112240; color: #64E8FF; border: 2px solid #233554; border-radius: 8px; padding: 0 15px; font-weight: bold; text-align: left; } QPushButton:hover { border-color: #2EC1CC; background-color: #1d2d50; }"); self.format_btn.clicked.connect(self.show_format_menu); input_layout.addWidget(self.format_btn)
        self.add_btn = QPushButton("Add Queue"); self.add_btn.setObjectName("Primary"); self.add_btn.setFixedHeight(40); self.add_btn.clicked.connect(self.add_url); input_layout.addWidget(self.add_btn); main_layout.addLayout(input_layout)
        queue_label = QLabel("Transcription & Download Queue"); queue_label.setObjectName("Header"); main_layout.addWidget(queue_label)
        self.scroll_area = QScrollArea(); self.scroll_area.setWidgetResizable(True); self.scroll_area.setObjectName("StepCard")
        self.queue_container = QWidget(); self.queue_layout = QVBoxLayout(self.queue_container); self.queue_layout.setAlignment(Qt.AlignTop); self.queue_layout.setSpacing(10); self.scroll_area.setWidget(self.queue_container); main_layout.addWidget(self.scroll_area)
        footer_layout = QHBoxLayout()
        self.stats_label = QLabel("Ready"); self.stats_label.setStyleSheet("font-weight: bold; color: #64E8FF;"); footer_layout.addWidget(self.stats_label)
        footer_layout.addStretch(); self.open_output_btn = QPushButton("Open Output Folder"); self.open_output_btn.clicked.connect(self.open_output); footer_layout.addWidget(self.open_output_btn); main_layout.addLayout(footer_layout)
    def show_format_menu(self):
        menu = FormatPopupMenu(self); menu.formatSelected.connect(self.on_format_selected); pos = self.format_btn.mapToGlobal(QPoint(0, 0))
        menu.move(pos.x(), pos.y() - menu.height() - 5 if pos.y() > 400 else pos.y() + self.format_btn.height() + 5); menu.show()
    def on_format_selected(self, key, label):
        self.settings["output_format"] = key; self.queue_manager.set_output_format(key); self.format_btn.setText(f"Format: {key}"); self.config_manager.save_config(self.settings); self.update_stats(); self.show_toast(f"Selected: {label}")
    def update_format_display(self, key):
        self.format_btn.setText(f"Format: {key}"); self.queue_manager.set_output_format(key)
    def connect_signals(self):
        self.queue_manager.task_metadata.connect(self.on_task_metadata); self.queue_manager.task_progress.connect(self.on_task_progress); self.queue_manager.task_error.connect(self.on_task_error); self.queue_manager.task_finished.connect(self.on_task_finished)
        self.resource_manager.toast_notification.connect(self.show_toast)
    def show_toast(self, message):
        toast = Toast(self, message); start_x = (self.width() - toast.width()) // 2; toast.move(start_x, self.height()); toast.closed.connect(self.on_toast_closed); self.active_toasts.append(toast); self.reposition_toasts()
    def on_toast_closed(self, toast):
        if toast in self.active_toasts: self.active_toasts.remove(toast); self.reposition_toasts()
    def reposition_toasts(self):
        bottom_margin = 80; spacing = 10; current_y = self.height() - bottom_margin
        for toast in reversed(self.active_toasts):
            current_y -= toast.height(); target_x = (self.width() - toast.width()) // 2
            anim = QPropertyAnimation(toast, b"pos"); anim.setDuration(500); anim.setStartValue(toast.pos()); anim.setEndValue(QPoint(target_x, current_y)); anim.setEasingCurve(QEasingCurve.OutCubic); anim.start(); toast.move_anim = anim; current_y -= spacing
    def resizeEvent(self, event): super().resizeEvent(event); self.reposition_toasts()
    def show_settings(self):
        dialog = SettingsDialog(self, self.settings)
        if dialog.exec():
            new_settings = dialog.get_settings(); self.settings.update(new_settings); self.resource_manager.set_cpu_settings(self.settings["cpu_mode"], self.settings["cpu_limit"]); self.resource_manager.set_ram_settings(self.settings["ram_mode"], self.settings["ram_limit"]); self.queue_manager.set_concurrency_limit(self.settings["concurrency_limit"]); self.config_manager.save_config(self.settings); self.update_stats(); self.show_toast("Settings saved.")
    def add_url(self):
        url = self.url_input.text().strip()
        if not url: return
        limit = self.settings.get("queue_size_limit", 10)
        if len(self.items) >= limit: self.show_toast(f"Queue full! Limit: {limit}"); return
        current_fmt = self.settings.get("output_format", "MIDI")
        item_id = str(uuid.uuid4())[:8]; item_widget = QueueItem(item_id, url, current_fmt); item_widget.remove_requested.connect(self.remove_item); self.queue_layout.insertWidget(0, item_widget); self.items[item_id] = item_widget; self.queue_manager.add_task(item_id, url); self.url_input.clear(); self.update_stats()
    def remove_item(self, item_id):
        if item_id in self.items: self.queue_manager.cancel_task(item_id); widget = self.items.pop(item_id); self.queue_layout.removeWidget(widget); widget.deleteLater(); self.update_stats()
    def on_task_metadata(self, item_id, meta):
        if item_id in self.items: self.items[item_id].update_metadata(meta)
    def on_task_progress(self, item_id, status, progress):
        if item_id in self.items: self.items[item_id].update_status(status, progress)
    def on_task_error(self, item_id, error_msg):
        if item_id in self.items: self.items[item_id].update_status(f"Error: {error_msg}", 0)
    def on_task_finished(self, item_id):
        if item_id in self.items: self.items[item_id].update_status("Finished", 100)
        self.update_stats()
    def update_stats(self):
        count = len(self.items); limit = self.settings.get("queue_size_limit", 10); fmt = self.settings.get("output_format", "MIDI")
        self.stats_label.setText(f"Queue: {count}/{limit} | Concurrency: {self.settings.get('concurrency_limit', 3)}")
    def open_output(self):
        output_path = os.path.abspath(self.queue_manager.output_dir)
        if not os.path.exists(output_path): os.makedirs(output_path)
        os.startfile(output_path)
