import sys
import os
import json
import random

# Ensure we can find the sibling package 'llm_linear_executor'
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QSplitter, QGroupBox, QFormLayout, 
                             QLineEdit, QCheckBox, QDoubleSpinBox, QSpinBox, QTextEdit, 
                             QComboBox, QPushButton, QGraphicsView, QGraphicsScene, 
                             QGraphicsItem, QGraphicsRectItem, QGraphicsTextItem,
                             QGraphicsLineItem, QGraphicsPathItem, QMenu, QLabel, 
                             QFrame, QSizePolicy, QToolBar, QAction, 
                             QGraphicsDropShadowEffect, QFileDialog, QMessageBox,
                             QTabWidget, QScrollArea, QTextBrowser, QListWidget, 
                             QListWidgetItem, QAbstractScrollArea)
from PyQt5.QtCore import Qt, QRectF, QPointF, pyqtSignal
from PyQt5.QtGui import QPen, QBrush, QColor, QWheelEvent, QPainter, QPainterPath, QFont

# Import execution control panel
from .execution_panel import ExecutionControlPanel

try:
    from config import BACKEND_PORT
except ImportError:
    # Try relative import if running as package
    try:
        from ..config import BACKEND_PORT
    except ImportError:
        BACKEND_PORT = 8001

# Import schemas to ensure we match the data structure
try:
    from .data_driving_schemas import ALL_NODE_TYPES
except ImportError:
    # Fallback/Mock if direct import fails (e.g. running script directly from subfolder)
    # Using list for stable ordering in UI
    ALL_NODE_TYPES = ["llm-first", "tool-first"]  # plan 未实现

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
QScrollBar:vertical {
    border: none;
    background: #1e1e1e;
    width: 10px;
    margin: 0px;
}
QScrollBar::handle:vertical {
    background: #424242;
    min-height: 20px;
    border-radius: 5px;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
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


class NodeContextPanel(QGroupBox):
    """Panel to display node thread context information"""
    def __init__(self):
        super().__init__("Node Context")
        self.main_layout = QVBoxLayout()
        self.main_layout.setContentsMargins(10, 15, 10, 10)
        self.main_layout.setSpacing(8)
        
        # Context Messages Section
        self.context_section = CollapsibleSection("Context Information")
        self.context_browser = QTextBrowser()
        self.context_browser.setMinimumHeight(200)
        self.context_browser.setMaximumHeight(1200)
        self.context_browser.setPlaceholderText("No context data available")
        self.context_section.set_content(self.context_browser)
        self.main_layout.addWidget(self.context_section)
        
        # LLM Input Prompt Section
        self.prompt_section = CollapsibleSection("LLM Input Prompt")
        self.prompt_browser = QTextBrowser()
        self.prompt_browser.setMinimumHeight(300)
        self.prompt_browser.setMaximumHeight(1200)
        self.prompt_browser.setPlaceholderText("No prompt data available")
        self.prompt_section.set_content(self.prompt_browser)
        self.main_layout.addWidget(self.prompt_section)
        
        # Node Output Section
        self.output_section = CollapsibleSection("Node Output")
        self.output_browser = QTextBrowser()
        self.output_browser.setMinimumHeight(300)
        self.output_browser.setMaximumHeight(1200)
        self.output_browser.setPlaceholderText("No output data available")
        self.output_section.set_content(self.output_browser)
        self.main_layout.addWidget(self.output_section)
        
        # Add stretch to push sections to top
        self.main_layout.addStretch()
        
        self.setLayout(self.main_layout)
    
    def load_node_context(self, node_data):
        """Load and display context information for a node"""
        # For now, just display placeholder text
        # In the future, this will be populated with actual execution data
        
        node_name = node_data.get("node_name", "Unknown")
        thread_id = node_data.get("thread_id", "main")
        
        # Context info
        context_html = f"""
        <b>Node:</b> {node_name}<br>
        <b>Thread ID:</b> {thread_id}<br>
        <b>Status:</b> <i>Not executed yet</i><br>
        <br>
        <i>Context messages will appear here during execution</i>
        """
        self.context_browser.setHtml(context_html)
        
        # Prompt info
        prompt_html = f"""
        <i>LLM input prompt will appear here during execution</i>
        """
        self.prompt_browser.setHtml(prompt_html)
        
        # Output info
        output_html = f"""
        <i>Node output will appear here after execution</i>
        """
        self.output_browser.setHtml(output_html)
    
    def clear_context(self):
        """Clear all context information"""
        self.context_browser.clear()
        self.prompt_browser.clear()
        self.output_browser.clear()
    
    def load_node_context_from_api(self, context_data: dict):
        """
        Load and display context information from API response
        
        Args:
            context_data: Dict containing node_id, node_name, thread_id,
                         thread_messages_before, thread_messages_after,
                         llm_input, llm_output, tool_calls, data_out_content
        """
        node_name = context_data.get("node_name", "Unknown")
        node_id = context_data.get("node_id", "?")
        thread_id = context_data.get("thread_id", "main")
        
        # Format context messages
        messages_before = context_data.get("thread_messages_before", [])
        messages_after = context_data.get("thread_messages_after", [])
        
        context_html = f"""
        <b>Node:</b> {node_name} (ID: {node_id})<br>
        <b>Thread ID:</b> {thread_id}<br>
        <b>Status:</b> <span style="color: #4CAF50;">✓ Executed</span><br><br>
        <b>Messages Before Execution:</b>
        <div style="background-color: #2d2d2d; padding: 8px; margin: 4px 0; border-radius: 4px;">
        """
        
        if messages_before:
            for msg in messages_before:
                role = msg.get("role", "unknown")
                content = msg.get("content", "")[:200]  # Truncate for preview
                role_color = "#4CAF50" if role == "assistant" else "#2196F3"
                context_html += f'<span style="color: {role_color};">[{role}]</span> {content}<br>'
        else:
            context_html += "<i>No messages</i>"
        
        context_html += "</div>"
        self.context_browser.setHtml(context_html)
        
        # LLM Input Prompt
        llm_input = context_data.get("llm_input", "")
        prompt_html = f"""
        <div style="background-color: #2d2d2d; padding: 8px; border-radius: 4px; white-space: pre-wrap;">
        {llm_input if llm_input else '<i>No LLM input</i>'}
        </div>
        """
        self.prompt_browser.setHtml(prompt_html)
        
        # Node Output (LLM output + tool calls)
        llm_output = context_data.get("llm_output", "")
        tool_calls = context_data.get("tool_calls", [])
        data_out = context_data.get("data_out_content")
        
        output_html = f"""
        <b>LLM Output:</b>
        <div style="background-color: #2d2d2d; padding: 8px; margin: 4px 0; border-radius: 4px; white-space: pre-wrap;">
        {llm_output if llm_output else '<i>No LLM output</i>'}
        </div>
        """
        
        if tool_calls:
            output_html += "<br><b>Tool Calls:</b>"
            for tc in tool_calls:
                tool_name = tc.get("name", "unknown")
                tool_args = tc.get("args", {})
                tool_result = tc.get("result", "")
                output_html += f"""
                <div style="background-color: #3d3d2d; padding: 8px; margin: 4px 0; border-radius: 4px;">
                <span style="color: #FFC107;">🔧 {tool_name}</span><br>
                <b>Args:</b> {tool_args}<br>
                <b>Result:</b> {str(tool_result)[:100]}...
                </div>
                """
        
        if data_out:
            output_html += f"""
            <br><b>Data Output:</b>
            <div style="background-color: #2d3d2d; padding: 8px; margin: 4px 0; border-radius: 4px;">
            {data_out}
            </div>
            """
        
        self.output_browser.setHtml(output_html)

class NodeItem(QGraphicsItem):
    """
    Custom Node Item with rounded corners, header, and shadow.
    """
    def __init__(self, node_data, x=0, y=0, w=180, h=80, thread_color=None):
        super().__init__()
        self.setPos(x, y)
        self.width = w
        self.height = h
        self.node_data = node_data
        self.thread_color = thread_color  # Color for thread distinction
        
        # Output anchor for drag connections (right side)
        self.output_anchor_rect = QRectF(self.width - 12, self.height/2 - 6, 12, 12)
        
        # Swap buttons (left and right arrows next to ID)
        # These will be positioned dynamically in paint method
        self.left_swap_rect = QRectF(0, 0, 0, 0)  # Will be set in paint
        self.right_swap_rect = QRectF(0, 0, 0, 0)  # Will be set in paint
        self.hover_swap_button = None  # Track which button is hovered: 'left', 'right', 'up', 'down', or None
        
        # Thread swap buttons (up and down arrows for thread position)
        self.up_thread_rect = QRectF(0, 0, 0, 0)  # Will be set in paint
        self.down_thread_rect = QRectF(0, 0, 0, 0)  # Will be set in paint
        
        # Rule 1: Fixed positions. Disable Movable flag always.
        self.is_fixed = True 
        
        flags = QGraphicsItem.ItemIsSelectable
        # if not self.is_fixed: flags |= QGraphicsItem.ItemIsMovable # Disabled
        
        # Enable hover events for swap buttons
        self.setAcceptHoverEvents(True)
            
        self.setFlags(flags)
        
        # Execution status tracking
        self.execution_status = "pending"  # pending/running/completed/failed
        self.STATUS_COLORS = {
            "pending": QColor("#666666"),
            "running": QColor("#FFC107"),
            "completed": QColor("#4CAF50"),
            "failed": QColor("#F44336")
        }
        
        # Cache colors
        self._update_colors()

    def _update_colors(self):
        # Header color priority: thread_color > custom color > node type color
        if self.thread_color:
            self.header_color = self.thread_color
        elif "color" in self.node_data:
            self.header_color = QColor(self.node_data["color"])
        else:
            ntype = self.node_data.get("node_type", "default")
            self.header_color = NODE_COLORS.get(ntype, NODE_COLORS["default"])
            
        self.body_color = QColor("#2d2d2d")
        self.text_color = QColor("#ffffff")
        self.subtext_color = QColor("#b0b0b0")

    def boundingRect(self):
        return QRectF(-2, -2, self.width + 4, self.height + 4)

    def get_output_anchor_center(self) -> QPointF:
        """Get the center of output anchor in scene coordinates"""
        return self.mapToScene(self.output_anchor_rect.center())
    
    def get_input_point(self) -> QPointF:
        """Get the input connection point (left side)"""
        return self.mapToScene(QPointF(0, self.height / 2))

    def paint(self, painter, option, widget):
        # Update color in case data changed
        self._update_colors()
        
        path = QPainterPath()
        path.addRoundedRect(0, 0, self.width, self.height, 8, 8)
        
        # Border: black by default, blue when selected
        if self.isSelected():
            painter.setPen(QPen(QColor("#4a90e2"), 3))
        else:
            painter.setPen(QPen(QColor("#111111"), 1))
            
        # Fill Body
        painter.setBrush(self.body_color)
        painter.drawPath(path)
        
        # Header (Top part) - Slanted Design
        # Taller on the right side
        h_left = 24
        h_right = 38
        
        header_path = QPainterPath()
        header_path.moveTo(0, h_left)
        header_path.lineTo(0, 8)
        header_path.arcTo(0, 0, 16, 16, 180, 90) # Top-left corner
        header_path.lineTo(self.width - 8, 0)
        header_path.arcTo(self.width - 16, 0, 16, 16, 90, -90) # Top-right corner
        header_path.lineTo(self.width, h_right)
        header_path.lineTo(0, h_left)
        
        painter.fillPath(header_path, self.header_color)
        
        # Text (Name)
        painter.setPen(self.text_color)
        font = QFont("Segoe UI", 10, QFont.Bold)
        painter.setFont(font)
        # Position slightly adjusted for slant
        painter.drawText(QRectF(10, 0, self.width - 20, 30), 
                         Qt.AlignLeft | Qt.AlignVCenter, 
                         self.node_data.get("node_name", "Node"))
        
        # Type Label (Body)
        painter.setPen(self.subtext_color)
        font_small = QFont("Segoe UI", 8)
        painter.setFont(font_small)
        type_text = f"Type: {self.node_data.get('node_type', 'unknown')}"
        
        # Start drawing type text below the lowest part of header
        text_y_start = max(h_left, h_right) + 8
        painter.drawText(QRectF(10, text_y_start, self.width - 20, 20),
                         Qt.AlignLeft, type_text)
        
        # Draw ID with swap buttons
        node_id = self.node_data.get('id', '?')
        thread_id = self.node_data.get('thread_id', 'main')
        
        # Calculate button positions
        button_size = 14
        button_y = text_y_start + 15
        
        # Left arrow button (only show if ID > 1)
        if isinstance(node_id, int) and node_id > 1:
            self.left_swap_rect = QRectF(10, button_y, button_size, button_size)
            # Draw button background
            if self.hover_swap_button == 'left':
                painter.setBrush(QColor("#4a90e2"))
            else:
                painter.setBrush(QColor("#3e3e3e"))
            painter.setPen(QPen(QColor("#555555"), 1))
            painter.drawRoundedRect(self.left_swap_rect, 3, 3)
            
            # Draw left arrow
            painter.setPen(QPen(QColor("#ffffff"), 2))
            arrow_center_x = self.left_swap_rect.center().x()
            arrow_center_y = self.left_swap_rect.center().y()
            painter.drawLine(int(arrow_center_x + 2), int(arrow_center_y),
                           int(arrow_center_x - 2), int(arrow_center_y))
            painter.drawLine(int(arrow_center_x - 2), int(arrow_center_y),
                           int(arrow_center_x), int(arrow_center_y - 3))
            painter.drawLine(int(arrow_center_x - 2), int(arrow_center_y),
                           int(arrow_center_x), int(arrow_center_y + 3))
        else:
            self.left_swap_rect = QRectF(0, 0, 0, 0)
        
        # ID text
        id_x_offset = 10 + (button_size + 4 if isinstance(node_id, int) and node_id > 1 else 0)
        id_text = f"ID: {node_id}"
        painter.setPen(self.subtext_color)
        painter.setFont(font_small)
        id_text_rect = QRectF(id_x_offset, button_y, 50, button_size)
        painter.drawText(id_text_rect, Qt.AlignLeft | Qt.AlignVCenter, id_text)
        
        # Right arrow button (always show, will check validity on click)
        right_button_x = id_x_offset + 52
        self.right_swap_rect = QRectF(right_button_x, button_y, button_size, button_size)
        # Draw button background
        if self.hover_swap_button == 'right':
            painter.setBrush(QColor("#4a90e2"))
        else:
            painter.setBrush(QColor("#3e3e3e"))
        painter.setPen(QPen(QColor("#555555"), 1))
        painter.drawRoundedRect(self.right_swap_rect, 3, 3)
        
        # Draw right arrow
        painter.setPen(QPen(QColor("#ffffff"), 2))
        arrow_center_x = self.right_swap_rect.center().x()
        arrow_center_y = self.right_swap_rect.center().y()
        painter.drawLine(int(arrow_center_x - 2), int(arrow_center_y),
                       int(arrow_center_x + 2), int(arrow_center_y))
        painter.drawLine(int(arrow_center_x + 2), int(arrow_center_y),
                       int(arrow_center_x), int(arrow_center_y - 3))
        painter.drawLine(int(arrow_center_x + 2), int(arrow_center_y),
                       int(arrow_center_x), int(arrow_center_y + 3))
        
        # Thread ID text (after buttons)
        thread_x_offset = right_button_x + button_size + 4
        # Calculate thread button area first to avoid overlap
        thread_button_size = 14
        thread_button_x = self.width - 50  # Position before output anchor, leave more space
        # Limit thread ID text to not overlap with buttons
        thread_text_width = thread_button_x - thread_x_offset - 4  # Leave 4px gap before buttons
        painter.setPen(self.subtext_color)
        painter.drawText(QRectF(thread_x_offset, button_y, max(thread_text_width, 50), button_size),
                         Qt.AlignLeft | Qt.AlignVCenter, f"| {thread_id}")
        
        # Draw thread swap buttons (up and down arrows on the right side, before output anchor)
        # Position buttons to avoid overlap with output anchor (which is at width-12, height/2)
        thread_button_y_start = button_y
        
        # #region agent log
        import json
        try:
            with open(r'd:\desktop\simple-llm-playground\.cursor\debug.log', 'a', encoding='utf-8') as f:
                f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"A","location":"debugger_ui.py:563","message":"Button position calculation","data":{"thread_button_x":thread_button_x,"thread_button_y_start":thread_button_y_start,"button_y":button_y,"thread_x_offset":thread_x_offset,"width":self.width,"thread_id":thread_id},"timestamp":int(__import__('time').time()*1000)}) + '\n')
        except: pass
        # #endregion
        
        # Up button (only show if thread_view_index > 0, meaning not the topmost thread)
        thread_view_index = self.node_data.get("thread_view_index", 0)
        if thread_view_index > 0:
            self.up_thread_rect = QRectF(thread_button_x, thread_button_y_start, thread_button_size, thread_button_size)
            # Draw button background
            if self.hover_swap_button == 'up':
                painter.setBrush(QColor("#4a90e2"))
            else:
                painter.setBrush(QColor("#3e3e3e"))
            painter.setPen(QPen(QColor("#555555"), 1))
            painter.drawRoundedRect(self.up_thread_rect, 3, 3)
            
            # Draw up arrow
            painter.setPen(QPen(QColor("#ffffff"), 2))
            arrow_center_x = self.up_thread_rect.center().x()
            arrow_center_y = self.up_thread_rect.center().y()
            painter.drawLine(int(arrow_center_x), int(arrow_center_y + 2),
                           int(arrow_center_x), int(arrow_center_y - 2))
            painter.drawLine(int(arrow_center_x), int(arrow_center_y - 2),
                           int(arrow_center_x - 3), int(arrow_center_y))
            painter.drawLine(int(arrow_center_x), int(arrow_center_y - 2),
                           int(arrow_center_x + 3), int(arrow_center_y))
        else:
            self.up_thread_rect = QRectF(0, 0, 0, 0)
        
        # Down button (always show, will check validity on click)
        # Position down button below up button with proper spacing
        # If up button exists, place down button below it; otherwise use same Y as up button would be
        if thread_view_index > 0:
            down_button_y = thread_button_y_start + thread_button_size + 2
        else:
            # No up button, so down button can be at the same Y position
            down_button_y = thread_button_y_start
        
        # Ensure down button doesn't exceed node bounds
        max_y = self.height - thread_button_size - 4
        if down_button_y > max_y:
            down_button_y = max_y
        
        self.down_thread_rect = QRectF(thread_button_x, down_button_y, thread_button_size, thread_button_size)
        
        # #region agent log
        try:
            with open(r'd:\desktop\simple-llm-playground\.cursor\debug.log', 'a', encoding='utf-8') as f:
                f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"A","location":"debugger_ui.py:615","message":"Down button rect calculated","data":{"down_button_y":down_button_y,"thread_button_x":thread_button_x,"thread_button_size":thread_button_size,"thread_x_offset":thread_x_offset,"thread_view_index":thread_view_index,"node_height":self.height},"timestamp":int(__import__('time').time()*1000)}) + '\n')
        except: pass
        # #endregion
        
        # Draw button background
        if self.hover_swap_button == 'down':
            painter.setBrush(QColor("#4a90e2"))
        else:
            painter.setBrush(QColor("#3e3e3e"))
        painter.setPen(QPen(QColor("#555555"), 1))
        painter.drawRoundedRect(self.down_thread_rect, 3, 3)
        
        # Draw down arrow
        painter.setPen(QPen(QColor("#ffffff"), 2))
        arrow_center_x = self.down_thread_rect.center().x()
        arrow_center_y = self.down_thread_rect.center().y()
        painter.drawLine(int(arrow_center_x), int(arrow_center_y - 2),
                       int(arrow_center_x), int(arrow_center_y + 2))
        painter.drawLine(int(arrow_center_x), int(arrow_center_y + 2),
                       int(arrow_center_x - 3), int(arrow_center_y))
        painter.drawLine(int(arrow_center_x), int(arrow_center_y + 2),
                       int(arrow_center_x + 3), int(arrow_center_y))
        
        # Draw output anchor (green circle)
        painter.setBrush(QColor("#4CAF50"))
        painter.setPen(QPen(QColor("#2E7D32"), 1))
        painter.drawEllipse(self.output_anchor_rect)
        
        # Draw execution status indicator (top-right corner)
        if self.execution_status != "pending":
            status_color = self.STATUS_COLORS.get(self.execution_status, QColor("#666666"))
            status_size = 12
            status_x = self.width - status_size - 4
            status_y = 4
            painter.setBrush(status_color)
            painter.setPen(QPen(status_color.darker(120), 1))
            painter.drawEllipse(int(status_x), int(status_y), status_size, status_size)
            
            # Draw icon inside status indicator
            painter.setPen(QPen(QColor("#ffffff"), 2))
            center_x = status_x + status_size / 2
            center_y = status_y + status_size / 2
            
            if self.execution_status == "completed":
                # Draw checkmark
                painter.drawLine(int(center_x - 3), int(center_y), int(center_x - 1), int(center_y + 2))
                painter.drawLine(int(center_x - 1), int(center_y + 2), int(center_x + 3), int(center_y - 2))
            elif self.execution_status == "running":
                # Draw dot
                painter.setBrush(QColor("#ffffff"))
                painter.drawEllipse(int(center_x - 2), int(center_y - 2), 4, 4)
            elif self.execution_status == "failed":
                # Draw X
                painter.drawLine(int(center_x - 2), int(center_y - 2), int(center_x + 2), int(center_y + 2))
                painter.drawLine(int(center_x + 2), int(center_y - 2), int(center_x - 2), int(center_y + 2))


    def mouseDoubleClickEvent(self, event):
        super().mouseDoubleClickEvent(event)
    
    def hoverMoveEvent(self, event):
        """Track hover over swap buttons"""
        local_pos = event.pos()
        
        old_hover = self.hover_swap_button
        
        # #region agent log
        try:
            import json
            with open(r'd:\desktop\simple-llm-playground\.cursor\debug.log', 'a', encoding='utf-8') as f:
                f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"E","location":"debugger_ui.py:592","message":"Hover move event","data":{"local_pos_x":local_pos.x(),"local_pos_y":local_pos.y(),"down_thread_rect":str(self.down_thread_rect),"old_hover":old_hover},"timestamp":int(__import__('time').time()*1000)}) + '\n')
        except: pass
        # #endregion
        
        if self.left_swap_rect.contains(local_pos):
            self.hover_swap_button = 'left'
        elif self.right_swap_rect.contains(local_pos):
            self.hover_swap_button = 'right'
        elif self.up_thread_rect.contains(local_pos):
            self.hover_swap_button = 'up'
        elif self.down_thread_rect.contains(local_pos):
            self.hover_swap_button = 'down'
        else:
            self.hover_swap_button = None
        
        # Repaint if hover state changed
        if old_hover != self.hover_swap_button:
            # #region agent log
            try:
                with open(r'd:\desktop\simple-llm-playground\.cursor\debug.log', 'a', encoding='utf-8') as f:
                    f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"E","location":"debugger_ui.py:610","message":"Hover state changed","data":{"old_hover":old_hover,"new_hover":self.hover_swap_button},"timestamp":int(__import__('time').time()*1000)}) + '\n')
            except: pass
            # #endregion
            self.update()
        
        super().hoverMoveEvent(event)
    
    def hoverLeaveEvent(self, event):
        """Clear hover state when mouse leaves"""
        if self.hover_swap_button is not None:
            self.hover_swap_button = None
            self.update()
        super().hoverLeaveEvent(event)
    
    def set_execution_status(self, status: str):
        """Set execution status and trigger repaint"""
        if status in self.STATUS_COLORS:
            self.execution_status = status
            self.update()  # Trigger repaint


class ConnectionLine(QGraphicsPathItem):
    """
    Connection line between nodes.
    
    Types:
    - thread: Same thread sequential connection (solid line)
    - data_in: Data input connection (dashed line)
    - data_out: Data output to merge node (dashed line)
    """
    def __init__(self, start_item, end_item, connection_type="thread", color=None):
        super().__init__()
        self.start_item = start_item
        self.end_item = end_item
        self.connection_type = connection_type
        self.line_color = color or QColor("#666666")
        
        self._update_path()
        self._update_style()
        self.setZValue(-1)  # Behind nodes
    
    def _update_style(self):
        if self.connection_type == "thread":
            pen = QPen(self.line_color, 2, Qt.SolidLine)
        else:  # data_in or data_out
            pen = QPen(self.line_color, 2, Qt.DashLine)
        pen.setCapStyle(Qt.RoundCap)
        self.setPen(pen)
    
    def _update_path(self):
        path = QPainterPath()
        
        if isinstance(self.start_item, NodeItem):
            start_pos = self.start_item.get_output_anchor_center()
        else:
            start_pos = self.start_item.get_output_point()
            
        if isinstance(self.end_item, NodeItem):
            end_pos = self.end_item.get_input_point()
        else:
            end_pos = self.end_item.get_input_point()
        
        # Bezier curve for smooth connection
        path.moveTo(start_pos)
        ctrl_offset = abs(end_pos.x() - start_pos.x()) / 2
        ctrl1 = QPointF(start_pos.x() + ctrl_offset, start_pos.y())
        ctrl2 = QPointF(end_pos.x() - ctrl_offset, end_pos.y())
        path.cubicTo(ctrl1, ctrl2, end_pos)
        
        self.setPath(path)
    
    def update_position(self):
        self._update_path()


class MergeNodeItem(QGraphicsItem):
    """
    Merge node (+) - Virtual display node showing where child thread data merges to parent.
    This is not a real node, just a visual indicator.
    """
    def __init__(self, x, y, parent_thread_id, child_thread_id, color=None):
        super().__init__()
        self.setPos(x, y)
        self.size = 36
        self.parent_thread_id = parent_thread_id
        self.child_thread_id = child_thread_id
        self.color = color or QColor("#4CAF50")
        self.setZValue(0)
    
    def boundingRect(self):
        return QRectF(-2, -2, self.size + 4, self.size + 4)
    
    def get_input_point(self) -> QPointF:
        """Get the input connection point"""
        return self.mapToScene(QPointF(0, self.size / 2))
    
    def get_output_point(self) -> QPointF:
        """Get the output connection point"""
        return self.mapToScene(QPointF(self.size, self.size / 2))
    
    def paint(self, painter, option, widget):
        # Draw circle background
        painter.setBrush(self.color)
        painter.setPen(QPen(self.color.darker(120), 2))
        painter.drawEllipse(0, 0, self.size, self.size)
        
        # Draw + sign
        painter.setPen(QPen(QColor("#ffffff"), 3))
        center = self.size / 2
        margin = 8
        painter.drawLine(int(center), int(margin), int(center), int(self.size - margin))
        painter.drawLine(int(margin), int(center), int(self.size - margin), int(center))
        
        # Draw label below
        painter.setPen(QColor("#b0b0b0"))
        font = QFont("Segoe UI", 7)
        painter.setFont(font)
        painter.drawText(QRectF(-20, self.size + 2, self.size + 40, 15),
                        Qt.AlignCenter, f"← {self.child_thread_id}")


class NodeGraphScene(QGraphicsScene):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSceneRect(-2500, -2500, 5000, 5000)
        self.grid_size = 20
        self.grid_color = QColor("#2d2d2d")
        self.connection_lines = []
        self.merge_nodes = []

    def drawBackground(self, painter, rect):
        # Fill background
        painter.fillRect(rect, QColor("#1e1e1e"))
        
        # Draw Grid
        left = int(rect.left()) - (int(rect.left()) % self.grid_size)
        top = int(rect.top()) - (int(rect.top()) % self.grid_size)
        
        lines = []
        # Vertical lines
        for x in range(left, int(rect.right()), self.grid_size):
            lines.append(QGraphicsLineItem(x, rect.top(), x, rect.bottom()).line())
        # Horizontal lines
        for y in range(top, int(rect.bottom()), self.grid_size):
            lines.append(QGraphicsLineItem(rect.left(), y, rect.right(), y).line())
            
        painter.setPen(QPen(self.grid_color, 1))
        painter.drawLines(lines)

class NodeGraphView(QGraphicsView):
    nodeSelected = pyqtSignal(dict) # Emit node data when selected

    def __init__(self):
        super().__init__()
        self.scene = NodeGraphScene()
        self.setScene(self.scene)
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        self.next_node_id = 1
        self.node_gap_x = 220
        
        # Thread color management
        self.thread_color_map = {}  # thread_id -> QColor
        
        # Drag connection state
        self.dragging_connection = False
        self.drag_start_item = None
        self.drag_temp_line = None
        
        # Thread View Index Management
        self.thread_view_indices = {} # thread_id -> index (int)
        
        # Test Data - Position at bottom-left area (positive Y goes down in Qt)
        # Use Y=200 as baseline for main thread (appears in lower area of screen)
        self.main_y_baseline = 200
        self.add_node({"node_name": "main", "node_type": "llm-first", "thread_id": "main", "task_prompt": "", "fixed": True, "thread_view_index": 0}, 0, self.main_y_baseline)
        
        # Center view on bottom-left area to show first node at screen's bottom-left
        # Offset the center to the right and down to position first node at bottom-left
        self.center_to_bottom_left()
        
        # Add overlay button
        self.add_btn = QPushButton("+", self)
        self.add_btn.setGeometry(20, 20, 40, 40)
        self.add_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196f3;
                color: white;
                border-radius: 20px;
                font-family: Arial;
                font-weight: bold;
                font-size: 24px;
                border: 1px solid #1e88e5;
                padding-bottom: 2px;
            }
            QPushButton:hover {
                background-color: #42a5f5;
            }
            QPushButton:pressed {
                background-color: #1976d2;
            }
        """)
        self.add_btn.setCursor(Qt.PointingHandCursor)
        self.add_btn.clicked.connect(self.add_node_at_center)
        
        # Add shadow to button
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(15)
        shadow.setColor(QColor(0, 0, 0, 100))
        shadow.setOffset(0, 4)
        self.add_btn.setGraphicsEffect(shadow)
    
    def center_to_bottom_left(self):
        """Center view to show first node at bottom-left of screen"""
        # Get the visible viewport size
        viewport_rect = self.viewport().rect()
        viewport_width = viewport_rect.width()
        viewport_height = viewport_rect.height()
        
        # Calculate offset to position node (at 0, main_y_baseline) at bottom-left of viewport
        # We want the node to appear with some margin from the edges
        margin_x = 150  # Horizontal margin from left edge
        margin_y = 150  # Vertical margin from bottom edge
        
        # Center point calculation: we want the node at (0, main_y_baseline) to appear
        # at (margin_x, viewport_height - margin_y) in viewport coordinates
        # So the center of the view should be at:
        center_x = 0 + (viewport_width / 2 - margin_x)
        center_y = self.main_y_baseline + (viewport_height / 2 - margin_y)
        
        self.centerOn(-center_x + margin_x, center_y - margin_y)

    def get_thread_color(self, thread_id: str) -> QColor:
        """Get or create a color for a thread_id"""
        if thread_id not in self.thread_color_map:
            idx = len(self.thread_color_map)
            color_hex = THREAD_COLORS[idx % len(THREAD_COLORS)]
            self.thread_color_map[thread_id] = QColor(color_hex)
        return self.thread_color_map[thread_id]
    
    def update_connections(self):
        """Rebuild all connection lines based on current nodes"""
        # Clear existing connections
        for line in self.scene.connection_lines:
            self.scene.removeItem(line)
        self.scene.connection_lines.clear()
        
        for merge in self.scene.merge_nodes:
            self.scene.removeItem(merge)
        self.scene.merge_nodes.clear()
        
        # Get all nodes sorted by ID
        nodes = [i for i in self.scene.items() if isinstance(i, NodeItem)]
        nodes.sort(key=lambda n: n.node_data.get("id", 0))
        
        # Build node lookup by id
        node_by_id = {n.node_data.get("id"): n for n in nodes}
        
        # Group nodes by thread_id
        threads = {}
        for node in nodes:
            tid = node.node_data.get("thread_id", "main")
            if tid not in threads:
                threads[tid] = []
            threads[tid].append(node)
        
        # Draw same-thread connections (solid lines)
        for tid, thread_nodes in threads.items():
            thread_nodes.sort(key=lambda n: n.node_data.get("id", 0))
            color = self.get_thread_color(tid)
            
            for i in range(len(thread_nodes) - 1):
                start_node = thread_nodes[i]
                end_node = thread_nodes[i + 1]
                line = ConnectionLine(start_node, end_node, "thread", color)
                self.scene.addItem(line)
                self.scene.connection_lines.append(line)
        
        # Draw data_in connections (dashed lines) and merge nodes for data_out
        for node in nodes:
            # data_in connection
            data_in_thread = node.node_data.get("data_in_thread")
            if data_in_thread and data_in_thread in threads:
                source_nodes = threads[data_in_thread]
                target_id = node.node_data.get("id", 0)
                # Find the last node in source thread that has id < target_id
                valid_sources = [n for n in source_nodes if n.node_data.get("id", 0) < target_id]
                if valid_sources:
                    # Connect from the last valid source node
                    source_node = max(valid_sources, key=lambda n: n.node_data.get("id", 0))
                    line = ConnectionLine(source_node, node, "data_in", 
                                         self.get_thread_color(data_in_thread))
                    self.scene.addItem(line)
                    self.scene.connection_lines.append(line)
            
            # data_out - create merge node on parent thread
            if node.node_data.get("data_out"):
                parent_tid = node.node_data.get("parent_thread_id", "main")
                child_tid = node.node_data.get("thread_id", "main")
                
                if parent_tid and parent_tid != child_tid and parent_tid in threads:
                    # Place merge node at appropriate X position (after this node)
                    merge_x = node.x() + self.node_gap_x / 2
                    # Y position on parent thread (Y=0 for main)
                    parent_y = 0
                    if threads[parent_tid]:
                        parent_y = threads[parent_tid][0].y()
                    
                    merge_node = MergeNodeItem(
                        merge_x, parent_y + 20,
                        parent_tid, child_tid,
                        self.get_thread_color(child_tid)
                    )
                    self.scene.addItem(merge_node)
                    self.scene.merge_nodes.append(merge_node)
                    
                    # Draw line from node to merge node
                    line = ConnectionLine(node, merge_node, "data_out",
                                         self.get_thread_color(child_tid))
                    self.scene.addItem(line)
                    self.scene.connection_lines.append(line)
        
    def get_all_nodes_data(self):
        nodes = []
        # Sort by x position to maintain some logical order if needed
        items = [i for i in self.scene.items() if isinstance(i, NodeItem)]
        items.sort(key=lambda item: item.x())
        
        for item in items:
            # Update position in data just in case we want to persist it later (custom field)
            item.node_data["_ui_pos"] = [item.x(), item.y()]
            nodes.append(item.node_data)
        return nodes

    def clear_nodes(self):
        self.scene.clear()

    def auto_layout_nodes(self, nodes_data):
        self.clear_nodes()
        self.next_node_id = 1
        
        # ID re-mapping for parent/child consistency
        old_id_map = {}
        
        # Map existing thread indices if present
        for node in nodes_data:
            tid = node.get("thread_id", "main")
            tidx = node.get("thread_view_index")
            if tidx is not None and tid not in self.thread_view_indices:
                self.thread_view_indices[tid] = tidx

        # First pass: Assign new IDs and Map
        for node in nodes_data:
            # Ensure thread_view_index
            tid = node.get("thread_id", "main")
            if tid not in self.thread_view_indices:
                # Assign new index: max + 1
                current_indices = self.thread_view_indices.values()
                next_idx = max(current_indices) + 1 if current_indices else 0
                self.thread_view_indices[tid] = next_idx
            
            node["thread_view_index"] = self.thread_view_indices[tid]

            old_id = node.get("id")
            new_id = self.next_node_id
            
            node["id"] = new_id
            if old_id is not None:
                old_id_map[old_id] = new_id
            
            # Auto-assign color for existing planning nodes if missing
            if node.get("node_type") == "planning" and "color" not in node:
                # Assign a deterministic but unique-looking color based on ID to be stable? 
                # Or just random? User said "different". Random is fine but changes on reload if not saved.
                # Let's use random but it will be saved next time they save.
                node["color"] = QColor.fromHsv(random.randint(0, 359), 200, 200).name()

            self.next_node_id += 1
            
        # Second pass: Update parent pointers if they exist (assuming 'parent_id' key)
        # and Add to Scene
        
        # Reset counter for adding to scene (add_node increments it if we don't provide force_id, 
        # but here we want to trust our pre-calculated IDs or just let add_node handle it if we pass processed data)
        # Actually easier: just call add_node sequentially.
        
        # Wait, add_node logic below handles X based on ID. 
        # So we just need to respect the Y from saved layout if available.
        # But we MUST rewrite IDs in the data to be sequential 1..N based on list order.
        
        # Reset ID again so add_node starts from 1 matching our loop
        self.next_node_id = 1
        
        for node in nodes_data:
            # Fix parent_id if needed
            pid = node.get("parent_id")
            if pid in old_id_map:
                node["parent_id"] = old_id_map[pid]
            
            # Determine Y based on thread_view_index (Top-Down per requirement)
            # "One vertical coordinate can only have one thread"
            # User Feedback: "id越大应该是往上的" (Larger ID should be upwards).
            # In Qt, Up is negative Y relative to baseline.
            # So we SUBTRACT the offset.
            
            tidx = node.get("thread_view_index", 0)
            thread_gap_y = 120 # Vertical spacing between threads
            
            y = self.main_y_baseline - (tidx * thread_gap_y)
            
            # Override with saved _ui_pos ONLY for X (dragged horizontally?) 
            # Or ignore Y completely to enforce strict layout.
            if "_ui_pos" in node:
                # node["_ui_pos"][1] = y # Force Y to match thread
                pass 
            
            
            # X is determined by ID in add_node
            self.add_node(node, 0, y)
        
        # Draw connections after all nodes are placed
        self.update_connections()
    
    def update_node_color(self, node_data):
        """Update the color of a specific node when its thread_id changes"""
        # Find the node item with matching data
        nodes = [i for i in self.scene.items() if isinstance(i, NodeItem)]
        for node in nodes:
            if node.node_data.get("id") == node_data.get("id"):
                # Get new thread color
                thread_id = node_data.get("thread_id", "main")
                new_color = self.get_thread_color(thread_id)
                node.thread_color = new_color
                # Force repaint
                node.update()
                break
        
        # Update all connections since thread relationships may have changed
        self.update_connections()
    
    def update_node_status(self, node_id: int, status: str):
        """
        Update the execution status of a specific node by ID
        
        Args:
            node_id: The ID of the node to update
            status: One of 'pending', 'running', 'completed', 'failed'
        """
        nodes = [i for i in self.scene.items() if isinstance(i, NodeItem)]
        for node in nodes:
            if node.node_data.get("id") == node_id:
                node.set_execution_status(status)
                break

    def add_node(self, node_data, x, y, force_id=None):
        # Enforce ID
        if force_id is not None:
            node_id = force_id
            # Ensure next_node_id is ahead of forced one to avoid collision if mixed usage
            if node_id >= self.next_node_id:
                self.next_node_id = node_id + 1
        else:
            # Check if data already has an ID (e.g. from file load but not forced via arg)
            # But requirements say "If reading, then according to reading order".
            # So we usually just overwrite/assign based on current counter.
            node_id = self.next_node_id
            self.next_node_id += 1
        
        node_data["id"] = node_id
        
        # Ensure thread_id exists
        if "thread_id" not in node_data:
            node_data["thread_id"] = "main"
            
        # Ensure thread_view_index exists
        tid = node_data["thread_id"]
        if "thread_view_index" not in node_data:
            if tid in self.thread_view_indices:
                node_data["thread_view_index"] = self.thread_view_indices[tid]
            else:
                # New thread dynamic assignment
                # Warning: adding a simple node shouldn't usually create a new thread index unless it IS a new thread.
                # If it's a new thread_id not seen before, assign next index.
                current_indices = self.thread_view_indices.values()
                next_idx = max(current_indices) + 1 if current_indices else 0
                self.thread_view_indices[tid] = next_idx
                node_data["thread_view_index"] = next_idx
        else:
             # Sync back to manager if not present
             if tid not in self.thread_view_indices:
                 self.thread_view_indices[tid] = node_data["thread_view_index"]

        # Enforce X Coordinate based on ID
        # ID 1 -> 0
        # ID 2 -> GAP
        # ...
        calculated_x = (node_id - 1) * self.node_gap_x
        
        # Enforce Y Coordinate based on thread_view_index
        thread_gap_y = 120
        tidx = node_data["thread_view_index"]
        # Larger Index = Higher Up = Smaller Y value
        calculated_y = self.main_y_baseline - (tidx * thread_gap_y)
        
        # Ignore passed 'y' argument in favor of strict thread layout?
        # The 'y' arg is often calculated from parent.y() - 120 etc.
        # We should use strict calculation.
        y = calculated_y
        
        # Get thread color
        thread_color = self.get_thread_color(node_data["thread_id"])
        
        item = NodeItem(node_data, calculated_x, y, thread_color=thread_color)
        self.scene.addItem(item)
    
    def wheelEvent(self, event: QWheelEvent):
        # Zoom
        zoomInFactor = 1.1
        zoomOutFactor = 1 / zoomInFactor
        if event.angleDelta().y() > 0:
            zoomFactor = zoomInFactor
        else:
            zoomFactor = zoomOutFactor
        self.scale(zoomFactor, zoomFactor)

    def mousePressEvent(self, event):
        item = self.itemAt(event.pos())
        
        # Check if clicking on swap buttons or output anchor of a NodeItem
        if isinstance(item, NodeItem):
            local_pos = item.mapFromScene(self.mapToScene(event.pos()))
            
            # Check swap buttons first (higher priority than anchor)
            if item.left_swap_rect.contains(local_pos):
                # Swap with left neighbor
                self.swap_nodes(item, -1)
                return
            elif item.right_swap_rect.contains(local_pos):
                # Swap with right neighbor
                self.swap_nodes(item, 1)
                return
            elif item.up_thread_rect.contains(local_pos):
                # Move thread up
                self.swap_threads(item, -1)
                return
            elif item.down_thread_rect.contains(local_pos):
                # Move thread down
                self.swap_threads(item, 1)
                return
            elif item.output_anchor_rect.contains(local_pos):
                # Start connection drag
                self.dragging_connection = True
                self.drag_start_item = item
                self.drag_temp_line = QGraphicsLineItem()
                self.drag_temp_line.setPen(QPen(QColor("#4CAF50"), 2, Qt.DashLine))
                self.drag_temp_line.setZValue(10)
                self.scene.addItem(self.drag_temp_line)
                start_pos = item.get_output_anchor_center()
                self.drag_temp_line.setLine(start_pos.x(), start_pos.y(),
                                           start_pos.x(), start_pos.y())
                return
            else:
                self.nodeSelected.emit(item.node_data)
        
        super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event):
        if self.dragging_connection and self.drag_temp_line:
            start_pos = self.drag_start_item.get_output_anchor_center()
            end_pos = self.mapToScene(event.pos())
            self.drag_temp_line.setLine(start_pos.x(), start_pos.y(),
                                       end_pos.x(), end_pos.y())
            return
        super().mouseMoveEvent(event)
    
    def mouseReleaseEvent(self, event):
        if self.dragging_connection:
            # Hide temp line to find actual item underneath
            if self.drag_temp_line:
                self.drag_temp_line.hide()
            
            # Find target node at release position
            scene_pos = self.mapToScene(event.pos())
            items_at_pos = self.scene.items(scene_pos)
            target = None
            for item in items_at_pos:
                if isinstance(item, NodeItem) and item != self.drag_start_item:
                    target = item
                    break
            
            if target:
                # Validate: source.id < target.id
                source_id = self.drag_start_item.node_data.get("id", 0)
                target_id = target.node_data.get("id", 0)
                
                if source_id < target_id:
                    # Create data_in connection
                    source_thread = self.drag_start_item.node_data.get("thread_id", "main")
                    target.node_data["data_in_thread"] = source_thread
                    target.node_data["data_in_slice"] = (-1, None)  # Default: last message
                    print(f"Created connection: {source_thread} -> Node {target_id}")
                    self.update_connections()
                else:
                    print(f"Invalid connection: source ID ({source_id}) must be < target ID ({target_id})")
            
            # Clean up drag state
            if self.drag_temp_line:
                self.scene.removeItem(self.drag_temp_line)
                self.drag_temp_line = None
            self.dragging_connection = False
            self.drag_start_item = None
            return
        
        super().mouseReleaseEvent(event)

    def contextMenuEvent(self, event):
        item = self.itemAt(event.pos())
        if isinstance(item, NodeItem):
            menu = QMenu(self)
            add_node_action = menu.addAction("Add Node")
            add_branch_action = menu.addAction("Create Branch Point")
            menu.addSeparator()
            delete_thread_action = menu.addAction("Delete Thread")
            delete_action = menu.addAction("Delete Node")
            
            action = menu.exec_(self.mapToGlobal(event.pos()))
            
            if action == add_node_action:
                self.add_new_node_from(item)
            elif action == add_branch_action:
                self.add_branch_from(item)
            elif action == delete_action:
                self.delete_node(item)
            elif action == delete_thread_action:
                self.delete_thread(item)

    def add_new_node_from(self, parent_item):
        # Extension: Same Y level, same thread
        new_y = parent_item.y()
        parent_thread = parent_item.node_data.get("thread_id", "main")
        
        new_data = {
            "node_name": "New Node", 
            "node_type": "llm-first", 
            "thread_id": parent_thread,
            "task_prompt": "",
            "parent_id": parent_item.node_data.get("id")
        }
        self.add_node(new_data, 0, new_y)
        self.update_connections()

    def add_branch_from(self, parent_item):
        # Branch: Position UPWARDS (negative Y in Qt)
        new_y = parent_item.y() - 120
        parent_thread = parent_item.node_data.get("thread_id", "main")
        
        # Create new thread id for branch
        new_thread_id = f"branch_{self.next_node_id}"

        # Use next available index
        current_indices = self.thread_view_indices.values()
        next_idx = max(current_indices) + 1 if current_indices else 1 # 0 is main
        
        # Register new thread
        self.thread_view_indices[new_thread_id] = next_idx
        
        new_data = {
            "node_name": "Branch", 
            "node_type": "llm-first",
            "thread_id": new_thread_id,
            "parent_thread_id": parent_thread,
            "task_prompt": "",
            "parent_id": parent_item.node_data.get("id"),
            "thread_view_index": next_idx
        }
        # Y will be calculated by add_node
        self.add_node(new_data, 0, 0)
        self.update_connections()

    def delete_node(self, item):
        deleted_id = item.node_data.get("id", 0)
        self.scene.removeItem(item)
        
        # Renumber all nodes with ID > deleted_id
        nodes = [i for i in self.scene.items() if isinstance(i, NodeItem)]
        for node in nodes:
            node_id = node.node_data.get("id", 0)
            if node_id > deleted_id:
                new_id = node_id - 1
                node.node_data["id"] = new_id
                # Recalculate X position based on new ID
                node.setPos((new_id - 1) * self.node_gap_x, node.y())
        
        # Decrement next_node_id counter
        self.next_node_id = max(1, self.next_node_id - 1)
        
        self.update_connections()
    
    def delete_thread(self, item):
        """
        Delete the entire thread that this node belongs to.
        Apply specific shift logic: 'others smaller than his thread coordinate id + 1'
        """
        thread_id = item.node_data.get("thread_id", "main")
        if thread_id == "main":
            print("Cannot delete main thread yet")
            return
            
        deleted_idx = self.thread_view_indices.get(thread_id)
        if deleted_idx is None:
            return
            
        # 1. Remove all nodes of this thread
        nodes_to_remove = []
        for i in self.scene.items():
            if isinstance(i, NodeItem) and i.node_data.get("thread_id") == thread_id:
                nodes_to_remove.append(i)
        
        for node in nodes_to_remove:
            self.scene.removeItem(node)
            
        # 2. Update Indices
        # Rule: "Delete that thread's all IDs, others smaller than his thread coordinate id + 1"
        del self.thread_view_indices[thread_id]
        
        for tid, idx in self.thread_view_indices.items():
            if idx < deleted_idx:
                self.thread_view_indices[tid] = idx + 1
        
        # 3. Update all remaining nodes positions
        remaining_nodes = [i for i in self.scene.items() if isinstance(i, NodeItem)]
        for node in remaining_nodes:
            tid = node.node_data.get("thread_id", "main")
            if tid in self.thread_view_indices:
                new_idx = self.thread_view_indices[tid]
                node.node_data["thread_view_index"] = new_idx
                # Recalculate Y (Larger Index = Upwards = Negative Offset)
                node.setPos(node.x(), self.main_y_baseline - (new_idx * 120))
        
        self.update_connections()

    def swap_nodes(self, item, direction):
        """
        Swap node with its neighbor.
        
        Args:
            item: The NodeItem to swap
            direction: -1 for left swap, 1 for right swap
        """
        current_id = item.node_data.get("id", 0)
        target_id = current_id + direction
        
        # Protect ID=1 node - it cannot be swapped
        if current_id == 1:
            print("Cannot swap: Node ID 1 (main) is protected and cannot be swapped")
            return
        
        # Cannot swap with ID=1 node
        if target_id == 1:
            print("Cannot swap: Cannot swap with Node ID 1 (main) - it is protected")
            return
        
        # Validate target ID
        if target_id < 1:
            print(f"Cannot swap: target ID {target_id} is invalid (must be >= 1)")
            return
        
        # Get all nodes
        nodes = [i for i in self.scene.items() if isinstance(i, NodeItem)]
        
        # Find target node
        target_node = None
        for node in nodes:
            if node.node_data.get("id") == target_id:
                target_node = node
                break
        
        if not target_node:
            print(f"Cannot swap: no node found with ID {target_id}")
            return
        
        # Swap IDs
        item.node_data["id"] = target_id
        target_node.node_data["id"] = current_id
        
        # Recalculate positions based on new IDs
        item.setPos((target_id - 1) * self.node_gap_x, item.y())
        target_node.setPos((current_id - 1) * self.node_gap_x, target_node.y())
        
        # Force repaint
        item.update()
        target_node.update()
        
        # Update all connections
        self.update_connections()
        
        print(f"Swapped nodes: {current_id} ↔ {target_id}")

    def swap_threads(self, item, direction):
        """
        Swap thread position with adjacent thread.
        
        Args:
            item: The NodeItem whose thread should be moved
            direction: -1 for up (move thread up), 1 for down (move thread down)
        """
        current_thread_id = item.node_data.get("thread_id", "main")
        current_thread_index = item.node_data.get("thread_view_index", 0)
        target_thread_index = current_thread_index + direction
        
        # Validate target index
        if target_thread_index < 0:
            print(f"Cannot move thread: target index {target_thread_index} is invalid (must be >= 0)")
            return
        
        # Find target thread (thread with target_thread_index)
        target_thread_id = None
        for tid, idx in self.thread_view_indices.items():
            if idx == target_thread_index:
                target_thread_id = tid
                break
        
        if not target_thread_id:
            print(f"Cannot move thread: no thread found with index {target_thread_index}")
            return
        
        # Swap thread_view_indices
        self.thread_view_indices[current_thread_id] = target_thread_index
        self.thread_view_indices[target_thread_id] = current_thread_index
        
        # Get all nodes
        nodes = [i for i in self.scene.items() if isinstance(i, NodeItem)]
        
        # Update all nodes in both threads
        thread_gap_y = 120
        for node in nodes:
            node_thread_id = node.node_data.get("thread_id", "main")
            if node_thread_id == current_thread_id:
                # Update thread_view_index for all nodes in current thread
                node.node_data["thread_view_index"] = target_thread_index
                # Recalculate Y position
                new_y = self.main_y_baseline - (target_thread_index * thread_gap_y)
                node.setPos(node.x(), new_y)
                # #region agent log
                try:
                    import json
                    with open(r'd:\desktop\simple-llm-playground\.cursor\debug.log', 'a', encoding='utf-8') as f:
                        f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"C","location":"debugger_ui.py:1506","message":"Node position updated after thread swap","data":{"node_id":node.node_data.get("id"),"thread_id":node_thread_id,"new_thread_view_index":target_thread_index,"new_y":new_y,"old_y":node.y()},"timestamp":int(__import__('time').time()*1000)}) + '\n')
                except: pass
                # #endregion
                node.update()
            elif node_thread_id == target_thread_id:
                # Update thread_view_index for all nodes in target thread
                node.node_data["thread_view_index"] = current_thread_index
                # Recalculate Y position
                new_y = self.main_y_baseline - (current_thread_index * thread_gap_y)
                node.setPos(node.x(), new_y)
                # #region agent log
                try:
                    with open(r'd:\desktop\simple-llm-playground\.cursor\debug.log', 'a', encoding='utf-8') as f:
                        f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"C","location":"debugger_ui.py:1514","message":"Node position updated after thread swap","data":{"node_id":node.node_data.get("id"),"thread_id":node_thread_id,"new_thread_view_index":current_thread_index,"new_y":new_y},"timestamp":int(__import__('time').time()*1000)}) + '\n')
                except: pass
                # #endregion
                node.update()
        
        # Update all connections
        self.update_connections()
        
        print(f"Swapped threads: {current_thread_id} (index {current_thread_index}) ↔ {target_thread_id} (index {target_thread_index})")

    def add_node_at_center(self):
        # Always add to main axis at main_y_baseline
        new_data = {
            "node_name": "New Node", 
            "node_type": "llm-first", 
            "task_prompt": ""
        }
        self.add_node(new_data, 0, self.main_y_baseline)

class NodePropertyEditor(QGroupBox):
    nodeDataChanged = pyqtSignal()  # Signal emitted when node data is saved
    branchChanged = pyqtSignal(dict)  # Signal emitted when branch (thread_id) is changed
    
    def __init__(self):
        super().__init__("Node Properties")
        
        # Main Layout
        self.main_layout = QVBoxLayout()
        self.main_layout.setContentsMargins(15, 20, 15, 15)
        self.main_layout.setSpacing(10)
        
        # Create Tab Widget
        self.tab_widget = QTabWidget()
        self.main_layout.addWidget(self.tab_widget)
        
        # --- Node Setting Tab ---
        self.node_setting_tab = QWidget()
        node_setting_layout = QVBoxLayout(self.node_setting_tab)
        node_setting_layout.setContentsMargins(10, 10, 10, 10)
        
        # Horizontal container for two columns in node setting
        self.columns_layout = QHBoxLayout()
        self.columns_layout.setSpacing(20)
        node_setting_layout.addLayout(self.columns_layout)
        
        # Left Column Form
        self.left_form = QFormLayout()
        self.left_form.setSpacing(10)
        
        # Right Column Form
        self.right_form = QFormLayout()
        self.right_form.setSpacing(10)
        
        self.columns_layout.addLayout(self.left_form, 1)
        self.columns_layout.addLayout(self.right_form, 1)
        
        self.current_node_data = None
        self._loading_data = False  # Flag to prevent auto-save during load
        self._available_tools = {}  # Cache for available tools from backend
        
        # --- Core Identifiers ---
        self.name_edit = QLineEdit()
        self.type_combo = QComboBox()
        self.type_combo.addItems(list(ALL_NODE_TYPES))
        
        # --- Branch Settings ---
        self.branch_name_edit = QLineEdit()
        self.branch_name_edit.setPlaceholderText("Branch name (thread_id)")
        
        # --- Task Prompt (will be in separate tab) ---
        self.prompt_edit = QTextEdit()
        self.prompt_edit.setPlaceholderText("Task Prompt (leave empty for tool-only)")
        
        # --- Tools Config (will be in separate Tools tab) ---
        # Tools selection using checkboxes in a list widget
        # Tools selection using properties checkboxes container
        self.tools_container = QWidget()
        self.tools_container_layout = QVBoxLayout(self.tools_container)
        self.tools_container_layout.setContentsMargins(20, 0, 0, 0)
        self.tools_container_layout.setSpacing(5)
        self.tool_checkboxes = {} # name -> QCheckBox
        
        self.enable_tool_loop_cb = QCheckBox("Enable Tool Loop")
        
        # --- Tool First Specific ---
        # Init Tool selection using dropdown
        self.initial_tool_combo = NoScrollComboBox()
        self.initial_tool_combo.addItem("Select initial tool...")
        self.initial_tool_combo.currentTextChanged.connect(self._on_init_tool_selected)
        
        self.initial_tool_args_edit = QTextEdit()
        self.initial_tool_args_edit.setPlaceholderText('Initial Args e.g. {"arg": "val"}')
        self.initial_tool_args_edit.setMinimumHeight(300)

        # --- Data Flow Input ---
        self.data_in_thread_edit = QLineEdit()
        self.data_in_thread_edit.setPlaceholderText("Source Thread ID (Optional)")
        
        self.data_in_slice_edit = QLineEdit()
        self.data_in_slice_edit.setPlaceholderText("Slice: start,end (e.g. -5, or 0,2)")

        # --- Data Flow Output ---
        self.data_out_cb = QCheckBox("Output Data to Parent")
        self.data_out_thread_edit = QLineEdit()
        self.data_out_thread_edit.setPlaceholderText("Target Thread ID (defaults to main)")
        self.desc_edit = QLineEdit()
        self.desc_edit.setPlaceholderText("Description of output data")
        
        # Connect type change to visibility toggle
        self.type_combo.currentTextChanged.connect(self.update_field_visibility)
        
        # --- Layout Assembly for Node Setting Tab ---
        # Node Setting tab now only contains: name, type, branch, data input, data output
        
        # LEFT COLUMN
        self.left_form.addRow("Name:", self.name_edit)
        self.left_form.addRow("Type:", self.type_combo)
        self.left_form.addRow("Branch:", self.branch_name_edit)
        
        # RIGHT COLUMN
        # Data Input Section
        self.right_form.addRow(QLabel("--- Data Input ---"))
        self.right_form.addRow("Src Thread:", self.data_in_thread_edit)
        self.right_form.addRow("Slice:", self.data_in_slice_edit)
        
        # Data Output Section
        self.right_form.addRow(QLabel("--- Data Output ---"))
        self.right_form.addRow("", self.data_out_cb)
        self.right_form.addRow("Out Thread:", self.data_out_thread_edit)
        self.right_form.addRow("Out Desc:", self.desc_edit)
        
        # --- Task Prompt Tab ---
        self.task_prompt_tab = QWidget()
        task_prompt_layout = QVBoxLayout(self.task_prompt_tab)
        task_prompt_layout.setContentsMargins(0, 0, 0, 0)  # No margins for full screen
        task_prompt_layout.setSpacing(0)
        
        # Add the prompt editor to fill the entire tab
        task_prompt_layout.addWidget(self.prompt_edit)
        
        # --- Tools Tab ---
        self.tools_tab = QWidget()
        tools_main_layout = QHBoxLayout(self.tools_tab)
        tools_main_layout.setContentsMargins(15, 20, 15, 15)
        tools_main_layout.setSpacing(15)
        
        # Left side: Tools selection
        left_tools_widget = QWidget()
        tools_layout = QVBoxLayout(left_tools_widget)
        tools_layout.setContentsMargins(0, 0, 0, 0)
        tools_layout.setSpacing(10)
        
        # Tools Selection (for LLM binding)
        tools_label = QLabel("Tools (LLM可调用的工具):")
        tools_label.setStyleSheet("font-weight: bold;")
        tools_layout.addWidget(tools_label)

        tools_layout.addWidget(self.tools_container)
        
        # Enable Tool Loop
        tools_layout.addWidget(self.enable_tool_loop_cb)
        
        # Separator
        separator1 = QFrame()
        separator1.setFrameShape(QFrame.Shape.HLine)
        separator1.setFrameShadow(QFrame.Shadow.Sunken)
        tools_layout.addWidget(separator1)
        
        # Tool First Settings
        self.tool_first_label = QLabel("--- Tool First Settings ---")
        tools_layout.addWidget(self.tool_first_label)
        
        init_tool_label = QLabel("Initial Tool (首次运行工具):")
        tools_layout.addWidget(init_tool_label)
        tools_layout.addWidget(self.initial_tool_combo)
        
        init_args_label = QLabel("Initial Args (初始参数):")
        tools_layout.addWidget(init_args_label)
        tools_layout.addWidget(self.initial_tool_args_edit)
        
        # Add stretch to push to top
        tools_layout.addStretch()
        
        # Right side: Tool parameter information
        right_tools_widget = QGroupBox("Tool Parameters")
        right_tools_layout = QVBoxLayout(right_tools_widget)
        right_tools_layout.setContentsMargins(10, 10, 10, 10)
        right_tools_layout.setSpacing(5)
        
        # Tool info display area
        self.tool_info_display = QTextEdit()
        self.tool_info_display.setReadOnly(True)
        self.tool_info_display.setPlaceholderText("选择一个工具查看其参数信息...")
        right_tools_layout.addWidget(self.tool_info_display)
        
        # Wrap left side in Scroll Area
        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setWidget(left_tools_widget)
        left_scroll.setFrameShape(QFrame.NoFrame) # Optional: remove border if desired
        
        # Add to main layout with 1:1 ratio
        tools_main_layout.addWidget(left_scroll, 1)
        tools_main_layout.addWidget(right_tools_widget, 1)

        
        # --- LLM Setting Tab ---
        self.llm_setting_tab = QWidget()
        llm_setting_layout = QFormLayout(self.llm_setting_tab)
        llm_setting_layout.setContentsMargins(15, 20, 15, 15)
        llm_setting_layout.setSpacing(10)
        
        # LLM Parameters
        self.temp_spin = QDoubleSpinBox()
        self.temp_spin.setRange(0.0, 2.0)
        self.temp_spin.setSingleStep(0.1)
        self.temp_spin.setValue(0.7)
        self.temp_spin.setSuffix(" ")
        
        self.topp_spin = QDoubleSpinBox()
        self.topp_spin.setRange(0.0, 1.0)
        self.topp_spin.setSingleStep(0.05)
        self.topp_spin.setValue(0.9)
        self.topp_spin.setSuffix(" ")
        
        self.enable_search_cb = QCheckBox("Enable Search")
        self.enable_thinking_cb = QCheckBox("Enable Thinking")
        
        llm_setting_layout.addRow("Temperature:", self.temp_spin)
        llm_setting_layout.addRow("Top-P:", self.topp_spin)
        llm_setting_layout.addRow(self.enable_search_cb)
        llm_setting_layout.addRow(self.enable_thinking_cb)
        
        # Add stretch to push fields to top
        llm_setting_layout.addRow(QWidget())  # Spacer
        
        # Add tabs to tab widget
        self.tab_widget.addTab(self.node_setting_tab, "Node Setting")
        self.tab_widget.addTab(self.task_prompt_tab, "Task Prompt")
        self.tab_widget.addTab(self.tools_tab, "Tools")
        self.tab_widget.addTab(self.llm_setting_tab, "LLM Setting")
        
        # Save Button (kept for manual trigger if needed)
        self.save_btn = QPushButton("Save & Update Connections")
        self.save_btn.clicked.connect(self.save_node_data)
        self.main_layout.addWidget(self.save_btn)
        
        self.setLayout(self.main_layout)
        self.setEnabled(False) # Disable until node selected
        
        # Group widgets for visibility toggling
        self.tool_first_widgets = [
            self.tool_first_label,
            self.initial_tool_combo,
            self.initial_tool_args_edit,
        ]
        
        # --- Connect Auto-Save Signals ---
        # All input fields will auto-save on change
        self.name_edit.textChanged.connect(self._auto_save)
        self.type_combo.currentTextChanged.connect(self._auto_save)
        self.branch_name_edit.textChanged.connect(self._auto_save)
        self.prompt_edit.textChanged.connect(self._auto_save)
        self.prompt_edit.textChanged.connect(self._auto_save)
        # self.tools_list_widget.itemChanged.connect(self._on_tools_list_changed) # Removed, connected individually
        self.enable_tool_loop_cb.stateChanged.connect(self._auto_save)
        self.enable_tool_loop_cb.stateChanged.connect(self._auto_save)
        # initial_tool_combo is handled in _on_init_tool_selected
        self.initial_tool_args_edit.textChanged.connect(self._auto_save)
        self.data_in_thread_edit.textChanged.connect(self._auto_save)
        self.data_in_slice_edit.textChanged.connect(self._auto_save)
        self.data_out_cb.stateChanged.connect(self._auto_save)
        self.data_out_thread_edit.textChanged.connect(self._auto_save)
        self.desc_edit.textChanged.connect(self._auto_save)
        # LLM settings
        self.temp_spin.valueChanged.connect(self._auto_save)
        self.topp_spin.valueChanged.connect(self._auto_save)
        self.enable_search_cb.stateChanged.connect(self._auto_save)
        self.enable_thinking_cb.stateChanged.connect(self._auto_save)
        
        # Load available tools from backend
        self.load_available_tools()

    def _auto_save(self):
        """Automatically save data when any field changes"""
        if not self._loading_data and self.current_node_data is not None:
            self._save_to_node_data()
    
    def load_available_tools(self):
        """Load available tools from backend API"""
        try:
            import requests
            response = requests.get(f"http://localhost:{BACKEND_PORT}/api/tools", timeout=2)
            if response.status_code == 200:
                data = response.json()
                tools = data.get("tools", [])
                
                # Clear existing items
                self.tool_checkboxes = {}
                while self.tools_container_layout.count():
                    child = self.tools_container_layout.takeAt(0)
                    if child.widget():
                        child.widget().deleteLater()
                
                self.initial_tool_combo.clear()
                self.initial_tool_combo.addItem("Select initial tool...")
                
                # Store tool details for later use
                self._available_tools = {}
                self.tool_limit_spinboxes = {}
                
                for tool in tools:
                    tool_name = tool.get("name", "")
                    self._available_tools[tool_name] = tool
                    
                    # Add to tools container
                    row_widget = QWidget()
                    row_layout = QHBoxLayout(row_widget)
                    row_layout.setContentsMargins(0, 0, 0, 0)
                    
                    cb = QCheckBox(tool_name)
                    cb.stateChanged.connect(self._on_tools_list_changed)
                    
                    limit_spin = QSpinBox()
                    limit_spin.setRange(0, 999)
                    limit_spin.setSpecialValueText("Default")
                    limit_spin.setPrefix("Limit: ")
                    limit_spin.setToolTip("Max calls for this tool (0=Executor Default)")
                    limit_spin.setFixedWidth(120)
                    limit_spin.valueChanged.connect(self._auto_save)
                    
                    row_layout.addWidget(cb)
                    row_layout.addStretch()
                    row_layout.addWidget(limit_spin)
                    
                    self.tools_container_layout.addWidget(row_widget)
                    self.tool_checkboxes[tool_name] = cb
                    self.tool_limit_spinboxes[tool_name] = limit_spin
                    
                    # Add to init tool dropdown
                    self.initial_tool_combo.addItem(tool_name)
                    
                print(f"Loaded {len(tools)} tools from backend")
            else:
                print(f"Failed to load tools: HTTP {response.status_code}")
        except Exception as e:
            print(f"Error loading tools: {e}")
            # Initialize empty dict if loading fails
            self._available_tools = {}
    
    def _on_tools_list_changed(self):
        """Handle when tool checkboxes are changed in the list"""
        # Auto-save when tools selection changes
        if not self._loading_data and self.current_node_data is not None:
            self._save_to_node_data()
    
    def _on_init_tool_selected(self, tool_name: str):
        """Handle init tool selection from dropdown"""
        # Show tool parameters in right panel
        if tool_name and tool_name != "Select initial tool...":
            self._display_tool_info(tool_name)
        else:
            self.tool_info_display.clear()
        
        # Auto-save when init tool changes
        if not self._loading_data and self.current_node_data is not None:
            self._save_to_node_data()
    
    def _display_tool_info(self, tool_name: str):
        """Display tool parameter information"""
        if hasattr(self, '_available_tools') and tool_name in self._available_tools:
            tool_info = self._available_tools[tool_name]
            
            # Format and display tool information
            info_text = f"Tool Name: {tool_name}\n"
            info_text += "=" * 60 + "\n\n"
            
            description = tool_info.get("description", "No description available")
            info_text += f"Description:\n{description}\n\n"
            
            # Display parameters if available
            parameters = tool_info.get("parameters", {})
            if parameters:
                info_text += "Parameters:\n"
                info_text += "-" * 60 + "\n"
                
                for param_name, param_info in parameters.items():
                    param_type = param_info.get("type", "Any")
                    param_required = param_info.get("required", False)
                    param_desc = param_info.get("description", "")
                    
                    # Clean up type string
                    if "typing." in param_type:
                        param_type = param_type.replace("typing.", "")
                    if "<class '" in param_type:
                        param_type = param_type.split("'")[1] if "'" in param_type else param_type
                    
                    required_marker = " (required)" if param_required else " (optional)"
                    info_text += f"\n  • {param_name}: {param_type}{required_marker}\n"
                    
                    if param_desc:
                        info_text += f"    Description: {param_desc}\n"
                
                info_text += "\n"
            else:
                info_text += "Parameters: No parameter information available\n\n"
            
            self.tool_info_display.setPlainText(info_text)
        else:
            self.tool_info_display.setPlainText(f"Tool '{tool_name}' information not available.")
    
    def update_field_visibility(self, type_text):
        is_tool_first = (type_text == "tool-first")
        
        # Show/Hide Tool First fields
        for w in self.tool_first_widgets:
            if w: w.setVisible(is_tool_first)


    def load_node(self, node_data, is_first_in_thread=False):
        # Disable auto-save during loading
        self._loading_data = True
        
        self.current_node_data = node_data
        self.setEnabled(True)
        
        # Check if this is node ID 1 (protected main node)
        is_main_node = node_data.get("id") == 1
        
        self.name_edit.setText(node_data.get("node_name", ""))
        # Lock name field for ID=1 node
        self.name_edit.setReadOnly(is_main_node)
        self.name_edit.setStyleSheet("background-color: #3e3e3e;" if is_main_node else "")
        
        ntype = node_data.get("node_type", "llm-first")
        # Handle legacy types map
        if ntype == "llm_auto": ntype = "llm-first"
        if ntype == "tool": ntype = "tool-first"
        self.type_combo.setCurrentText(ntype)
        
        # Load branch name (thread_id)
        self.branch_name_edit.setText(node_data.get("thread_id", "main"))
        # Lock branch field for ID=1 node (must stay as 'main')
        self.branch_name_edit.setReadOnly(is_main_node)
        self.branch_name_edit.setStyleSheet("background-color: #3e3e3e;" if is_main_node else "")
        
        self.prompt_edit.setText(node_data.get("task_prompt", ""))
        
        # Load tools - check the items
        tools = node_data.get("tools")
        tools_limit = node_data.get("tools_limit") or {}
        
        for name, cb in self.tool_checkboxes.items():
            if tools and name in tools:
                cb.setChecked(True)
            else:
                cb.setChecked(False)
            
            # Load limit
            if hasattr(self, 'tool_limit_spinboxes') and name in self.tool_limit_spinboxes:
                limit_val = tools_limit.get(name, 0)
                self.tool_limit_spinboxes[name].setValue(limit_val)
        
        self.enable_tool_loop_cb.setChecked(node_data.get("enable_tool_loop", False))
        
        # Tool First - set init tool combo
        initial_tool = node_data.get("initial_tool_name") or ""
        if initial_tool:
            index = self.initial_tool_combo.findText(initial_tool)
            if index >= 0:
                self.initial_tool_combo.setCurrentIndex(index)
            else:
                self.initial_tool_combo.setCurrentIndex(0)
        else:
            self.initial_tool_combo.setCurrentIndex(0)
            
        args = node_data.get("initial_tool_args")
        if args:
            try:
                self.initial_tool_args_edit.setText(json.dumps(args, indent=2, ensure_ascii=False))
            except:
                self.initial_tool_args_edit.setText(str(args))
        else:
            self.initial_tool_args_edit.clear()
            
        # Data Input - RESTRICTED: Only first node in thread can edit
        self.data_in_thread_edit.setText(node_data.get("data_in_thread") or "")
        
        slice_val = node_data.get("data_in_slice")
        if slice_val:
            # slice_val is tuple (start, end)
            s, e = slice_val
            s_str = str(s) if s is not None else ""
            e_str = str(e) if e is not None else ""
            self.data_in_slice_edit.setText(f"{s_str},{e_str}")
        else:
            self.data_in_slice_edit.clear()
            
        # Apply restrictions
        self.data_in_thread_edit.setEnabled(is_first_in_thread)
        self.data_in_slice_edit.setEnabled(is_first_in_thread)
        if not is_first_in_thread:
            self.data_in_thread_edit.setToolTip("Only the first node of a thread can edit Data Input.")
            self.data_in_slice_edit.setToolTip("Only the first node of a thread can edit Data Input.")
        else:
            self.data_in_thread_edit.setToolTip("")
            self.data_in_slice_edit.setToolTip("")
            
        # Data Output
        self.data_out_cb.setChecked(node_data.get("data_out", False))
        self.data_out_thread_edit.setText(node_data.get("data_out_thread") or "")
        self.desc_edit.setText(node_data.get("data_out_description", ""))
        
        # LLM Settings
        self.temp_spin.setValue(node_data.get("temperature", 0.7))
        self.topp_spin.setValue(node_data.get("top_p", 0.9))
        self.enable_search_cb.setChecked(node_data.get("enable_search", False))
        self.enable_thinking_cb.setChecked(node_data.get("enable_thinking", False))
            
        self.update_field_visibility(ntype)
        
        # Re-enable auto-save after loading is complete
        self._loading_data = False

    def _save_to_node_data(self):
        """Internal method to save all fields to node data (used by auto-save)"""
        if self.current_node_data is None:
            return
            
        # Check if this is node ID 1 (protected main node)
        is_main_node = self.current_node_data.get("id") == 1
        
        # For ID=1 node, keep original name
        if not is_main_node:
            self.current_node_data["node_name"] = self.name_edit.text()
        
        self.current_node_data["node_type"] = self.type_combo.currentText()
        
        # For ID=1 node, force thread_id to be 'main'
        if is_main_node:
            self.current_node_data["thread_id"] = "main"
        else:
            self.current_node_data["thread_id"] = self.branch_name_edit.text().strip() or "main"
        
        self.current_node_data["task_prompt"] = self.prompt_edit.toPlainText()
        
        # Save tools from list widget
        checked_tools = []
        # Save tools from checkboxes
        checked_tools = []
        for name, cb in self.tool_checkboxes.items():
            if cb.isChecked():
                checked_tools.append(name)
        self.current_node_data["tools"] = checked_tools if checked_tools else None
        
        # Save tools limit
        tools_limit = {}
        if hasattr(self, 'tool_limit_spinboxes'):
             for name, spin in self.tool_limit_spinboxes.items():
                 if spin.value() > 0:
                     tools_limit[name] = spin.value()
        
        self.current_node_data["tools_limit"] = tools_limit if tools_limit else None
        
        self.current_node_data["enable_tool_loop"] = self.enable_tool_loop_cb.isChecked()
        
        # Save Tool First Data
        is_tool_first = (self.type_combo.currentText() == "tool-first")
        if is_tool_first:
            init_tool = self.initial_tool_combo.currentText()
            if init_tool != "Select initial tool...":
                self.current_node_data["initial_tool_name"] = init_tool
            else:
                self.current_node_data["initial_tool_name"] = None
            
            args_str = self.initial_tool_args_edit.toPlainText().strip()
            if args_str:
                try:
                    self.current_node_data["initial_tool_args"] = json.loads(args_str)
                except json.JSONDecodeError:
                    # Keep previous value if JSON is invalid during typing
                    pass
            else:
                self.current_node_data["initial_tool_args"] = None
        else:
            self.current_node_data["initial_tool_name"] = None
            self.current_node_data["initial_tool_args"] = None

        # Data Input
        self.current_node_data["data_in_thread"] = self.data_in_thread_edit.text() or None
        
        slice_str = self.data_in_slice_edit.text().strip()
        if slice_str:
            try:
                parts = slice_str.split(',')
                if len(parts) >= 1:
                    s_txt = parts[0].strip()
                    e_txt = parts[1].strip() if len(parts) > 1 else ""
                    
                    s = int(s_txt) if s_txt else None
                    e = int(e_txt) if e_txt else None
                    self.current_node_data["data_in_slice"] = (s, e)
                else:
                    self.current_node_data["data_in_slice"] = None
            except ValueError:
                # Keep previous value if parsing fails during typing
                pass
        else:
            self.current_node_data["data_in_slice"] = None

        # Data Output
        self.current_node_data["data_out"] = self.data_out_cb.isChecked()
        self.current_node_data["data_out_thread"] = self.data_out_thread_edit.text() or None
        self.current_node_data["data_out_description"] = self.desc_edit.text()
        
        # LLM Settings
        self.current_node_data["temperature"] = self.temp_spin.value()
        self.current_node_data["top_p"] = self.topp_spin.value()
        self.current_node_data["enable_search"] = self.enable_search_cb.isChecked()
        self.current_node_data["enable_thinking"] = self.enable_thinking_cb.isChecked()
    
    def save_node_data(self):
        """Manual save - updates data and triggers connection updates"""
        if self.current_node_data is not None:
            # Check if branch (thread_id) changed
            old_thread_id = self.current_node_data.get("thread_id", "main")
            
            # Save all data first
            self._save_to_node_data()
            
            new_thread_id = self.current_node_data.get("thread_id", "main")
            branch_changed = (old_thread_id != new_thread_id)
            
            print(f"Saved Node: {self.current_node_data}")
            self.nodeDataChanged.emit()  # Notify graph to update connections
            
            # If branch changed, emit signal to update node color
            if branch_changed:
                self.branchChanged.emit(self.current_node_data)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Simple LLM Playground")
        self.resize(1300, 850)
        
        # Apply Stylesheet
        self.setStyleSheet(DARK_STYLESHEET)
        
        # Main Layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Main Splitter (Left vs Right)
        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.main_splitter.setHandleWidth(2)
        main_layout.addWidget(self.main_splitter)
        
        # --- Left Panel Container ---
        left_container = QWidget()
        left_layout = QVBoxLayout(left_container)
        left_layout.setContentsMargins(10, 10, 10, 10)
        left_layout.setSpacing(10)
        
        # Execution Control Panel
        self.execution_panel = ExecutionControlPanel()
        left_layout.addWidget(self.execution_panel)
        
        # Node Context Panel
        self.context_panel = NodeContextPanel()
        left_layout.addWidget(self.context_panel)
        
        # Wrap left container in ScrollArea
        left_scroll = QScrollArea()
        left_scroll.setWidget(left_container)
        left_scroll.setWidgetResizable(True)
        left_scroll.setFrameShape(QFrame.NoFrame) # Clean look
        left_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        left_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        self.main_splitter.addWidget(left_scroll)
        
        # --- Right Panel (Graph + Props) ---
        self.right_splitter = QSplitter(Qt.Orientation.Vertical)
        self.right_splitter.setHandleWidth(2)
        self.main_splitter.addWidget(self.right_splitter)
        
        # Top Right: Graph
        self.graph_view = NodeGraphView()
        self.right_splitter.addWidget(self.graph_view)
        
        # Bottom Right: Properties
        prop_container = QWidget()
        prop_layout = QVBoxLayout(prop_container)
        prop_layout.setContentsMargins(5, 5, 5, 5)
        self.prop_editor = NodePropertyEditor()
        prop_layout.addWidget(self.prop_editor)
        
        self.right_splitter.addWidget(prop_container)
        
        # Connect signals
        self.graph_view.nodeSelected.connect(self.on_node_selected)
        self.prop_editor.nodeDataChanged.connect(self.graph_view.update_connections)
        self.prop_editor.nodeDataChanged.connect(self._update_execution_plan)
        self.prop_editor.branchChanged.connect(self.graph_view.update_node_color)
        
        # Connect execution panel signals
        self.execution_panel.stepExecuted.connect(self._on_step_executed)
        self.execution_panel.nodeStatesUpdated.connect(self._on_node_states_updated)
        self.execution_panel.executionError.connect(self._on_execution_error)
        self.execution_panel.saveRequested.connect(self.prop_editor.save_node_data)
        
        # Connect context loaded signal for node selection
        self.execution_panel.controller.contextLoaded.connect(self._on_context_loaded)
        self.execution_panel.controller.contextFailed.connect(self._on_context_failed)
        
        # Set initial sizes
        self.main_splitter.setSizes([300, 1000])
        self.right_splitter.setSizes([600, 250])

        # --- Toolbar ---
        self.setup_toolbar()
        
        # Data container for full plan (to preserve extra fields like 'tools_limit')
        self.current_plan_data = {"custom": {"nodes": []}}

    def setup_toolbar(self):
        toolbar = QToolBar("Main Toolbar")
        self.addToolBar(toolbar)
        
        load_action = QAction("Load JSON Plan", self)
        load_action.triggered.connect(self.load_json_plan)
        toolbar.addAction(load_action)
        
        save_action = QAction("Save JSON Plan", self)
        save_action.triggered.connect(self.save_json_plan)
        toolbar.addAction(save_action)
    
    def on_node_selected(self, node_data):
        """Handle node selection - update both property editor and context panel"""
        # Determine if this is the first node in its thread
        all_nodes = self.graph_view.get_all_nodes_data()
        current_tid = node_data.get("thread_id", "main")
        current_id = node_data.get("id", 0)
        
        is_first = True
        for n in all_nodes:
            if n.get("thread_id", "main") == current_tid:
                if n.get("id", 0) < current_id:
                    is_first = False
                    break
        
        self.prop_editor.load_node(node_data, is_first_in_thread=is_first)
        
        # Always show placeholder first
        self.context_panel.load_node_context(node_data)
        
        # Try to load context from API if executor is initialized
        executor_id = getattr(self.execution_panel.controller, "current_executor_id", None)
        node_id = node_data.get("id")
        
        if executor_id and node_id:
            # Executor is active, try to get context from API (will override placeholder if successful)
            self.execution_panel.controller.get_node_context(node_id)
    
    def _update_execution_plan(self):
        """Update the execution plan when node data changes"""
        nodes_data = self.graph_view.get_all_nodes_data()
        plan = self.execution_panel.get_plan_from_nodes(nodes_data)
        self.execution_panel.set_plan(plan)
    
    def _on_step_executed(self, node_context: dict):
        """Handle step execution - update node context panel and node states"""
        # Update context panel with the executed node's context
        self.context_panel.load_node_context_from_api(node_context)
        
        # Update node visual state
        node_id = node_context.get("node_id")
        if node_id:
            self.graph_view.update_node_status(node_id, "completed")
    
    def _on_node_states_updated(self, node_states: list):
        """Handle node states update from executor"""
        for state in node_states:
            node_id = state.get("node_id")
            status = state.get("status", "pending")
            self.graph_view.update_node_status(node_id, status)
    
    def _on_execution_error(self, error: str):
        """Handle execution error"""
        QMessageBox.warning(self, "Execution Error", error)
    
    def _on_context_loaded(self, context_data: dict):
        """Handle context loaded from API - update context panel"""
        self.context_panel.load_node_context_from_api(context_data)
    
    def _on_context_failed(self, error: str):
        """Handle context load failure - node may not be executed yet"""
        # Show placeholder for unexecuted nodes - context_panel already shows placeholder by default
        pass

    def load_json_plan(self):
        file_name, _ = QFileDialog.getOpenFileName(self, "Open Plan JSON", "", "JSON Files (*.json)")
        if file_name:
            try:
                # 1. Load Main Data
                with open(file_name, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # 2. Try Load Layout Data
                layout_data = {}
                # Construct layout filename: file.json -> file.layout.json
                base_path, ext = os.path.splitext(file_name)
                layout_file_name = f"{base_path}.layout{ext}"
                
                if os.path.exists(layout_file_name):
                    try:
                        with open(layout_file_name, 'r', encoding='utf-8') as f:
                            layout_data = json.load(f)
                    except Exception as e:
                        print(f"Warning: Failed to load layout file: {e}")

                # Check structure
                if "custom" in data and "nodes" in data["custom"]:
                    self.current_plan_data = data
                    nodes = data["custom"]["nodes"]

                    # Auto-prepend main node if missing (for data flow clarity)
                    needs_main_node = True
                    if nodes and nodes[0].get("thread_id") == "main" and nodes[0].get("node_name") == "main":
                        needs_main_node = False

                    if needs_main_node:
                        # Create empty main node as data entry point
                        main_node = {
                            "node_name": "main",
                            "node_type": "llm-first",
                            "thread_id": "main",
                            "task_prompt": "",  # Empty = no operation, just data relay
                            "fixed": True,
                            "thread_view_index": 0,
                        }
                        nodes.insert(0, main_node)

                        # Shift existing layout positions to make room for main node
                        new_layout_data = {}
                        new_layout_data["main"] = [0.0, 200.0]  # Default main position
                        for name, pos in layout_data.items():
                            new_layout_data[name] = [pos[0] + 220.0, pos[1]]
                        layout_data = new_layout_data

                    # 3. Inject Layout Data Back into Nodes
                    for node in nodes:
                        name = node.get("node_name")
                        if name and name in layout_data:
                            node["_ui_pos"] = layout_data[name]
                    
                    self.graph_view.auto_layout_nodes(nodes)
                    print(f"Loaded {len(nodes)} nodes from {file_name}")
                else:
                    QMessageBox.warning(self, "Error", "Invalid JSON format. Expected root 'custom' with 'nodes'.")
            
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to load file: {str(e)}")

    def save_json_plan(self):
        file_name, _ = QFileDialog.getSaveFileName(self, "Save Plan JSON", "", "JSON Files (*.json)")
        if file_name:
            try:
                # Update current nodes into the plan data
                current_nodes = self.graph_view.get_all_nodes_data()
                
                # Separation: Clean Data vs Layout Data
                clean_nodes = []
                layout_data = {}
                
                for node in current_nodes:
                    # Create a copy to avoid modifying the in-memory object logic (if referenced elsewhere)
                    # primarily to remove _ui_pos for saving
                    node_copy = node.copy()
                    
                    # Extract Position
                    if "_ui_pos" in node_copy:
                        name = node_copy.get("node_name")
                        if name:
                            layout_data[name] = node_copy["_ui_pos"]
                        del node_copy["_ui_pos"]
                    
                    clean_nodes.append(node_copy)
                
                # We need to preserve the wrapper structure
                if "custom" not in self.current_plan_data:
                    self.current_plan_data = {"custom": {}}
                
                self.current_plan_data["custom"]["nodes"] = clean_nodes
                
                # 1. Save Main Data
                with open(file_name, 'w', encoding='utf-8') as f:
                    json.dump(self.current_plan_data, f, indent=4, ensure_ascii=False)
                
                # 2. Save Layout Data
                base_path, ext = os.path.splitext(file_name)
                layout_file_name = f"{base_path}.layout{ext}"
                
                with open(layout_file_name, 'w', encoding='utf-8') as f:
                    json.dump(layout_data, f, indent=4, ensure_ascii=False)
                
                print(f"Saved plan to {file_name}")
                print(f"Saved layout to {layout_file_name}")
                
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save file: {str(e)}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion") # Good base for coloring
    
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
