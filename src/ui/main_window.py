import os
import uuid
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QLineEdit, QPushButton, QScrollArea, QLabel, 
    QFileDialog, QMessageBox, QDialog, QRadioButton,
    QButtonGroup, QSpinBox, QGraphicsOpacityEffect
)
from PySide6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, QPoint
from .queue_item import QueueItem

class SettingsDialog(QDialog):
    def __init__(self, parent=None, current_settings=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setFixedWidth(400)
        self.settings = current_settings or {"mode": "default", "limit": 50}
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        
        layout.addWidget(QLabel("<b>CPU Limit Mode</b>"))
        
        self.group = QButtonGroup(self)
        
        self.default_rb = QRadioButton("Default (Background / Eco Mode)")
        self.default_rb.setToolTip("Will not compete for CPU. Uses remaining capacity. Safety limits applied.")
        self.group.addButton(self.default_rb)
        layout.addWidget(self.default_rb)
        
        default_desc = QLabel("Uses idle priority. Limits usage if remaining CPU < 20%.")
        default_desc.setStyleSheet("color: #9DB3D1; font-size: 11px; margin-left: 20px; margin-bottom: 10px;")
        layout.addWidget(default_desc)

        self.custom_rb = QRadioButton("Custom CPU Limit (%)")
        self.group.addButton(self.custom_rb)
        layout.addWidget(self.custom_rb)
        
        custom_layout = QHBoxLayout()
        custom_layout.setContentsMargins(20, 0, 0, 10)
        self.limit_spin = QSpinBox()
        self.limit_spin.setRange(1, 100)
        self.limit_spin.setValue(self.settings.get("limit", 50))
        custom_layout.addWidget(QLabel("Max CPU Lock:"))
        custom_layout.addWidget(self.limit_spin)
        custom_layout.addWidget(QLabel("%"))
        custom_layout.addStretch()
        layout.addLayout(custom_layout)

        if self.settings["mode"] == "default":
            self.default_rb.setChecked(True)
        else:
            self.custom_rb.setChecked(True)

        buttons = QHBoxLayout()
        save_btn = QPushButton("Save Settings")
        save_btn.setObjectName("Primary")
        save_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        buttons.addWidget(save_btn)
        buttons.addWidget(cancel_btn)
        layout.addLayout(buttons)

    def get_settings(self):
        return {
            "mode": "default" if self.default_rb.isChecked() else "custom",
            "limit": self.limit_spin.value()
        }

class Toast(QLabel):
    def __init__(self, parent, message):
        super().__init__(message, parent)
        self.setAlignment(Qt.AlignCenter)
        self.setWordWrap(True)
        self.setStyleSheet("""
            background-color: #1E293B;
            color: #64E8FF;
            border: 1px solid #2EC1CC;
            border-radius: 10px;
            padding: 10px;
            font-size: 13px;
            font-weight: bold;
        """)
        self.setFixedWidth(300)
        self.move((parent.width() - self.width()) // 2, 50)
        
        self.opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.opacity_effect)
        
        self.show()
        
        # Fade out
        self.timer = QTimer()
        self.timer.singleShot(4000, self.fade_out)

    def fade_out(self):
        self.anim = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.anim.setDuration(1000)
        self.anim.setStartValue(1.0)
        self.anim.setEndValue(0.0)
        self.anim.finished.connect(self.deleteLater)
        self.anim.start()

class MainWindow(QMainWindow):
    def __init__(self, queue_manager, cpu_manager, config):
        super().__init__()
        self.queue_manager = queue_manager
        self.cpu_manager = cpu_manager
        self.config = config
        self.items = {}
        self.settings = {"mode": "default", "limit": 50}

        self.setWindowTitle("U2M - YouTube to MIDI")
        self.resize(800, 600)
        
        self.init_ui()
        self.connect_signals()

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)

        # Header
        header_layout = QHBoxLayout()
        header = QLabel("U2M: Piano Transcription")
        header.setObjectName("Header")
        header.setStyleSheet("font-size: 24px;")
        header_layout.addWidget(header)
        
        header_layout.addStretch()
        
        self.settings_btn = QPushButton("⚙") # Gear icon
        self.settings_btn.setFixedSize(40, 40)
        self.settings_btn.setStyleSheet("font-size: 20px; padding: 0;")
        self.settings_btn.clicked.connect(self.show_settings)
        header_layout.addWidget(self.settings_btn)
        
        main_layout.addLayout(header_layout)

        # Input Area
        input_layout = QHBoxLayout()
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("Paste video or audio URL here (YouTube, TikTok, SoundCloud, etc.)...")
        self.url_input.setFixedHeight(40)
        input_layout.addWidget(self.url_input)

        self.add_btn = QPushButton("Add to Queue")
        self.add_btn.setObjectName("Primary")
        self.add_btn.setFixedHeight(40)
        self.add_btn.clicked.connect(self.add_url)
        input_layout.addWidget(self.add_btn)
        
        main_layout.addLayout(input_layout)

        # Queue Area
        queue_label = QLabel("Transcription Queue")
        queue_label.setObjectName("Header")
        main_layout.addWidget(queue_label)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setObjectName("StepCard")
        
        self.queue_container = QWidget()
        self.queue_layout = QVBoxLayout(self.queue_container)
        self.queue_layout.setAlignment(Qt.AlignTop)
        self.queue_layout.setSpacing(10)
        
        self.scroll_area.setWidget(self.queue_container)
        main_layout.addWidget(self.scroll_area)

        # Footer
        footer_layout = QHBoxLayout()
        
        self.stats_label = QLabel("Ready")
        footer_layout.addWidget(self.stats_label)
        
        footer_layout.addStretch()
        
        self.open_output_btn = QPushButton("Open Output Folder")
        self.open_output_btn.clicked.connect(self.open_output)
        footer_layout.addWidget(self.open_output_btn)
        
        main_layout.addLayout(footer_layout)

    def connect_signals(self):
        self.queue_manager.task_metadata.connect(self.on_task_metadata)
        self.queue_manager.task_progress.connect(self.on_task_progress)
        self.queue_manager.task_error.connect(self.on_task_error)
        self.queue_manager.task_finished.connect(self.on_task_finished)
        
        # CPU Manager signals
        self.cpu_manager.toast_notification.connect(self.show_toast)

    def show_toast(self, message):
        Toast(self, message)

    def show_settings(self):
        dialog = SettingsDialog(self, self.settings)
        if dialog.exec():
            self.settings = dialog.get_settings()
            self.cpu_manager.set_settings(self.settings["mode"], self.settings["limit"])
            self.show_toast("Settings saved and applied.")

    def add_url(self):
        url = self.url_input.text().strip()
        if not url:
            return
        
        item_id = str(uuid.uuid4())[:8]
        
        # Create UI Item
        item_widget = QueueItem(item_id, url)
        item_widget.remove_requested.connect(self.remove_item)
        self.queue_layout.insertWidget(0, item_widget)
        self.items[item_id] = item_widget
        
        # Start Task
        self.queue_manager.add_task(item_id, url)
        self.url_input.clear()
        self.update_stats()

    def remove_item(self, item_id):
        if item_id in self.items:
            widget = self.items.pop(item_id)
            self.queue_layout.removeWidget(widget)
            widget.deleteLater()
            self.update_stats()

    def on_task_metadata(self, item_id, meta):
        if item_id in self.items:
            self.items[item_id].update_metadata(meta)

    def on_task_progress(self, item_id, status, progress):
        if item_id in self.items:
            self.items[item_id].update_status(status, progress)

    def on_task_error(self, item_id, error_msg):
        if item_id in self.items:
            self.items[item_id].update_status(f"Error: {error_msg}", 0)

    def on_task_finished(self, item_id):
        if item_id in self.items:
            self.items[item_id].update_status("Finished", 100)
        self.update_stats()

    def update_stats(self):
        count = len(self.items)
        self.stats_label.setText(f"Queue size: {count}")

    def open_output(self):
        output_path = os.path.abspath(self.queue_manager.output_dir)
        if not os.path.exists(output_path):
            os.makedirs(output_path)
        os.startfile(output_path)
