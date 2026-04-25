from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, 
    QProgressBar, QPushButton, QFrame
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap, QImage
import requests

class QueueItem(QFrame):
    remove_requested = Signal(str) # item_id

    def __init__(self, item_id, url):
        super().__init__()
        self.item_id = item_id
        self.url = url
        self.setObjectName("Card") # Matches QSS
        
        self.init_ui()

    def init_ui(self):
        self.layout = QHBoxLayout(self)
        
        # Thumbnail placeholder
        self.thumbnail = QLabel()
        self.thumbnail.setFixedSize(120, 68)
        self.thumbnail.setStyleSheet("background-color: #0F172A; border-radius: 4px;")
        self.thumbnail.setAlignment(Qt.AlignCenter)
        self.layout.addWidget(self.thumbnail)
        
        # Details layout
        self.details_layout = QVBoxLayout()
        
        self.title_label = QLabel("Fetching metadata...")
        self.title_label.setObjectName("Header")
        self.title_label.setWordWrap(True)
        self.details_layout.addWidget(self.title_label)
        
        self.status_label = QLabel("Queued")
        self.status_label.setStyleSheet("color: #9DB3D1; font-size: 11px;")
        self.details_layout.addWidget(self.status_label)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(6)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.details_layout.addWidget(self.progress_bar)
        
        self.layout.addLayout(self.details_layout, 1)
        
        # Remove button
        self.remove_btn = QPushButton("✕")
        self.remove_btn.setFixedSize(30, 30)
        self.remove_btn.setObjectName("Danger")
        self.remove_btn.clicked.connect(lambda: self.remove_requested.emit(self.item_id))
        self.layout.addWidget(self.remove_btn)

    def update_metadata(self, meta):
        self.title_label.setText(meta.get('title', 'Unknown Title'))
        
        # Load thumbnail asynchronously (simplified here for brevity)
        thumb_url = meta.get('thumbnail')
        if thumb_url:
            try:
                response = requests.get(thumb_url, stream=True, timeout=5)
                if response.status_code == 200:
                    image = QImage()
                    image.loadFromData(response.content)
                    pixmap = QPixmap.fromImage(image)
                    self.thumbnail.setPixmap(pixmap.scaled(120, 68, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            except:
                pass

    def update_status(self, status, progress):
        self.status_label.setText(status)
        self.progress_bar.setValue(progress)
        
        if status == "Finished":
            self.progress_bar.setStyleSheet("QProgressBar::chunk { background-color: #2ECC71; }")
        elif "Error" in status:
            self.progress_bar.setStyleSheet("QProgressBar::chunk { background-color: #E74C3C; }")
