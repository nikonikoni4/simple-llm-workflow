from PyQt5.QtWidgets import QComboBox, QWidget, QVBoxLayout, QPushButton, QSizePolicy
from PyQt5.QtGui import QColor

# --- Dark Theme Stylesheet ---
DARK_STYLESHEET = """
QMainWindow, QWidget {
    background-color: #1e1e1e;
    color: #dcdcdc;
    font-family: "Segoe UI", sans-serif;
    font-size: 10pt;
}
QGroupBox {
    border: 1px solid #3e3e3e;
    border-radius: 6px;
    margin-top: 12px;
    padding-top: 10px;
    font-weight: bold;
    color: #e0e0e0;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 5px;
    left: 10px;
}
QLineEdit, QTextEdit, QPlainTextEdit, QDoubleSpinBox, QComboBox {
    background-color: #2d2d2d;
    border: 1px solid #3e3e3e;
    border-radius: 4px;
    color: #ffffff;
    padding: 4px;
    selection-background-color: #4a90e2;
}
QLineEdit:focus, QTextEdit:focus, QDoubleSpinBox:focus, QComboBox:focus {
    border: 1px solid #4a90e2;
}
QPushButton {
    background-color: #0d47a1;
    color: white;
    border: none;
    border-radius: 4px;
    padding: 6px 12px;
    font-weight: bold;
}
QPushButton:hover {
    background-color: #1565c0;
}
QPushButton:pressed {
    background-color: #0d47a1;
}
QSplitter::handle {
    background-color: #2d2d2d;
    width: 2px;
}
QTabWidget::pane {
    border: 1px solid #3e3e3e;
    background: #1e1e1e;
    margin-top: -1px; 
}
QTabWidget::tab-bar {
    left: 5px; 
}
QTabBar::tab {
    background: #2d2d2d;
    color: #a0a0a0;
    border: 1px solid #3e3e3e;
    border-bottom-color: #3e3e3e; 
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    min-width: 80px;
    padding: 6px 12px;
}
QTabBar::tab:selected {
    background: #1e1e1e;
    color: #ffffff;
    border-bottom-color: #1e1e1e; 
}
QTabBar::tab:!selected {
    margin-top: 2px; 
}
QTabBar::tab:hover {
    background: #3e3e3e;
}
QScrollBar:vertical {
    border: none;
    background: #1e1e1e;
    width: 6px;
    margin: 0px;
}
QScrollBar::handle:vertical {
    background: #424242;
    min-height: 20px;
    border-radius: 3px;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: none;
}
QScrollBar:horizontal {
    border: none;
    background: #1e1e1e;
    height: 6px;
    margin: 0px;
}
QScrollBar::handle:horizontal {
    background: #424242;
    min-width: 20px;
    border-radius: 3px;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0px;
}
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
    background: none;
}
QGraphicsView {
    border: 1px solid #3e3e3e;
    background-color: #1e1e1e;
}
QCheckBox {
    spacing: 5px;
    color: #ffffff;
}
QCheckBox::indicator {
    width: 16px;
    height: 16px;
    background-color: #2d2d2d;
    border: 1px solid #3e3e3e;
    border-radius: 3px;
}
QCheckBox::indicator:checked {
    background-color: #4a90e2;
    border: 1px solid #4a90e2;
}
"""

NODE_COLORS = {
    "llm-first": QColor("#7b1fa2"),   # Purple
    "planning": QColor("#f57c00"),   # Orange
    "tool-first": QColor("#1976d2"), # Blue
    "default": QColor("#616161")     # Grey
}

# Thread color palette for visual distinction
THREAD_COLORS = [
    "#2196F3",  # Blue (typically main)
    "#4CAF50",  # Green
    "#FF9800",  # Orange
    "#9C27B0",  # Purple
    "#00BCD4",  # Cyan
    "#E91E63",  # Pink
    "#8BC34A",  # Light Green
    "#FF5722",  # Deep Orange
]

class NoScrollComboBox(QComboBox):
    """A QComboBox that ignores wheel events (scrolling) so parent widgets can scroll instead"""
    def wheelEvent(self, event):
        event.ignore()

class CollapsibleSection(QWidget):
    """A collapsible section widget with a header that can be clicked to expand/collapse"""
    def __init__(self, title="Section", parent=None):
        super().__init__(parent)
        self.is_collapsed = False
        
        # Main layout
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)
        
        # Header button
        self.toggle_button = QPushButton(f"▼ {title}")
        self.toggle_button.setStyleSheet("""
            QPushButton {
                text-align: left;
                padding: 8px;
                background-color: #2d2d2d;
                border: 1px solid #3e3e3e;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #3e3e3e;
            }
        """)
        self.toggle_button.clicked.connect(self.toggle)
        self.main_layout.addWidget(self.toggle_button)
        
        # Content area
        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(5, 5, 5, 5)
        self.main_layout.addWidget(self.content_widget)
    
    def toggle(self):
        self.is_collapsed = not self.is_collapsed
        self.content_widget.setVisible(not self.is_collapsed)
        # Update arrow
        title = self.toggle_button.text()[2:]  # Remove arrow
        arrow = "▶" if self.is_collapsed else "▼"
        self.toggle_button.setText(f"{arrow} {title}")
    
    def set_content(self, widget):
        # Clear existing content
        while self.content_layout.count():
            child = self.content_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        self.content_layout.addWidget(widget)
