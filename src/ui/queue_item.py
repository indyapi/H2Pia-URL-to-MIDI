from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, 
    QProgressBar, QPushButton, QFrame
)
from PySide6.QtCore import Qt, Signal, QThread, Slot
from PySide6.QtGui import QPixmap, QImage
import requests
import logging

logger = logging.getLogger(__name__)

class ThumbnailWorker(QThread):
    finished = Signal(QImage)

    def __init__(self, url):
        super().__init__()
        self.url = url

    def run(self):
        try:
            response = requests.get(self.url, stream=True, timeout=5)
            if response.status_code == 200:
                image = QImage()
                image.loadFromData(response.content)
                self.finished.emit(image)
        except Exception as e:
            logger.error(f"Failed to download thumbnail: {e}")

class QueueItem(QFrame):
    remove_requested = Signal(str) # item_id

    def __init__(self, item_id, url, format_name="MIDI"):
        super().__init__()
        self.item_id = item_id
        self.url = url
        self.format_name = format_name
        self.setObjectName("Card") 
        self.thumb_worker = None
        
        self.init_ui()

    def init_ui(self):
        self.main_layout = QHBoxLayout(self)
        self.main_layout.setContentsMargins(10, 10, 10, 10)
        
        # Thumbnail placeholder
        self.thumbnail = QLabel()
        self.thumbnail.setFixedSize(120, 68)
        self.thumbnail.setStyleSheet("background-color: #0F172A; border-radius: 4px;")
        self.thumbnail.setAlignment(Qt.AlignCenter)
        self.main_layout.addWidget(self.thumbnail)
        
        # Details layout
        self.details_layout = QVBoxLayout()
        self.details_layout.setSpacing(4)
        
        # Title Container (to handle the tag better)
        self.title_container = QHBoxLayout()
        
        self.title_label = QLabel("Fetching metadata...")
        self.title_label.setObjectName("Header")
        self.title_label.setWordWrap(True)
        self.title_label.setStyleSheet("font-size: 14px; font-weight: bold; margin-right: 60px;")
        self.title_container.addWidget(self.title_label, 1)
        
        self.details_layout.addLayout(self.title_container)
        
        self.status_label = QLabel("Queued")
        self.status_label.setStyleSheet("color: #9DB3D1; font-size: 11px;")
        self.details_layout.addWidget(self.status_label)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(6)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.update_progress_style(0)
        self.details_layout.addWidget(self.progress_bar)
        
        self.main_layout.addLayout(self.details_layout, 1)
        
        # Format Tag (positioned overlay in top-right)
        self.format_tag = QLabel(self.format_name, self)
        self.format_tag.setAlignment(Qt.AlignCenter)
        self.format_tag.setStyleSheet("""
            background-color: rgba(46, 193, 204, 0.15);
            color: #2EC1CC;
            border: 1px solid #2EC1CC;
            border-radius: 10px;
            padding: 2px 8px;
            font-size: 10px;
            font-weight: bold;
        """)
        self.format_tag.adjustSize()
        
        # Remove button
        self.remove_btn = QPushButton("✕")
        self.remove_btn.setFixedSize(28, 28)
        self.remove_btn.setObjectName("Danger")
        self.remove_btn.setToolTip("Remove from queue")
        self.remove_btn.clicked.connect(lambda: self.remove_requested.emit(self.item_id))
        self.main_layout.addWidget(self.remove_btn)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Position tag and remove button manually for better control
        padding = 10
        self.remove_btn.move(self.width() - self.remove_btn.width() - padding, padding)
        self.format_tag.move(self.width() - self.remove_btn.width() - self.format_tag.width() - padding - 8, padding + 4)

    def update_metadata(self, meta):
        self.title_label.setText(meta.get('title', 'Unknown Title'))
        thumb_url = meta.get('thumbnail')
        if thumb_url:
            self.thumb_worker = ThumbnailWorker(thumb_url)
            self.thumb_worker.finished.connect(self.on_thumbnail_downloaded)
            self.thumb_worker.start()

    @Slot(QImage)
    def on_thumbnail_downloaded(self, image):
        if not image.isNull():
            pixmap = QPixmap.fromImage(image)
            self.thumbnail.setPixmap(pixmap.scaled(120, 68, Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def update_progress_style(self, value):
        color = "#FF8C00" # Orange
        if value > 75: color = "#00BFFF" # Blue
        elif value > 50: color = "#2ECC71" # Green
        elif value > 25: color = "#F1C40F" # Yellow
            
        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{ background-color: #1E293B; border: none; border-radius: 3px; }}
            QProgressBar::chunk {{ background-color: {color}; border_radius: 3px; }}
        """)

    def update_status(self, status, progress):
        self.status_label.setText(status)
        self.progress_bar.setValue(progress)
        self.update_progress_style(progress)
        if status == "Finished": self.update_progress_style(100)
        elif "Error" in status:
            self.progress_bar.setStyleSheet("QProgressBar::chunk { background-color: #E74C3C; }")
