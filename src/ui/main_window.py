import os
import uuid
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QLineEdit, QPushButton, QScrollArea, QLabel, 
    QFileDialog, QMessageBox
)
from PySide6.QtCore import Qt
from .queue_item import QueueItem

class MainWindow(QMainWindow):
    def __init__(self, queue_manager, config):
        super().__init__()
        self.queue_manager = queue_manager
        self.config = config
        self.items = {}

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
        header = QLabel("U2M: Piano Transcription")
        header.setObjectName("Header")
        header.setStyleSheet("font-size: 24px; margin-bottom: 10px;")
        main_layout.addWidget(header)

        # Input Area
        input_layout = QHBoxLayout()
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("Paste YouTube URL here...")
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

    def add_url(self):
        url = self.url_input.text().strip()
        if not url:
            return
        
        if "youtube.com" not in url and "youtu.be" not in url:
            QMessageBox.warning(self, "Invalid URL", "Please enter a valid YouTube URL.")
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
