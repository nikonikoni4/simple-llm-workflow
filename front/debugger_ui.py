import sys
import os
import json
import random

# Ensure we can find the sibling package 'data_driving_agent_v2'
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QSplitter, QGroupBox, QFormLayout, 
                             QLineEdit, QCheckBox, QDoubleSpinBox, QTextEdit, 
                             QComboBox, QPushButton, QGraphicsView, QGraphicsScene, 
                             QGraphicsItem, QGraphicsRectItem, QGraphicsTextItem,
                             QGraphicsLineItem, QMenu, QLabel, QFrame, QSizePolicy,
                             QToolBar, QAction, QGraphicsDropShadowEffect, QFileDialog, QMessageBox)
from PyQt5.QtCore import Qt, QRectF, QPointF, pyqtSignal
from PyQt5.QtGui import QPen, QBrush, QColor, QWheelEvent, QPainter, QPainterPath, QFont

# Import schemas to ensure we match the data structure
# Adjust import path if needed based on execution context
try:
    from data_driving_agent_v2.data_driving_schemas import ALL_NODE_TYPES
except ImportError:
    # Fallback/Mock if direct import fails (e.g. running script directly from subfolder)
    # Using list for stable ordering in UI
    ALL_NODE_TYPES = ["llm-first", "tool-first", "planning"]

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
}
QCheckBox::indicator {
    width: 16px;
    height: 16px;
}
"""

NODE_COLORS = {
    "llm-first": QColor("#7b1fa2"),   # Purple
    "planning": QColor("#f57c00"),   # Orange
    "tool-first": QColor("#1976d2"), # Blue
    "default": QColor("#616161")     # Grey
}

class LLMParamPanel(QGroupBox):
    def __init__(self):
        super().__init__("LLM Settings")
        self.layout = QFormLayout()
        self.layout.setContentsMargins(15, 20, 15, 15)
        self.layout.setSpacing(10)
        
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
        
        self.layout.addRow("Temperature:", self.temp_spin)
        self.layout.addRow("Top-P:", self.topp_spin)
        self.layout.addRow(self.enable_search_cb)
        self.layout.addRow(self.enable_thinking_cb)
        
        self.setLayout(self.layout)
        # Fix height to be compact at top
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)

class NodeItem(QGraphicsItem):
    """
    Custom Node Item with rounded corners, header, and shadow.
    """
    def __init__(self, node_data, x=0, y=0, w=180, h=80):
        super().__init__()
        self.setPos(x, y)
        self.width = w
        self.height = h
        self.node_data = node_data
        
        
        # Rule 1: Fixed positions. Disable Movable flag always.
        self.is_fixed = True 
        
        flags = QGraphicsItem.ItemIsSelectable
        # if not self.is_fixed: flags |= QGraphicsItem.ItemIsMovable # Disabled
            
        self.setFlags(flags)
        
        # Cache colors
        self._update_colors()

    def _update_colors(self):
        if "color" in self.node_data:
            self.header_color = QColor(self.node_data["color"])
        else:
            ntype = self.node_data.get("node_type", "default")
            self.header_color = NODE_COLORS.get(ntype, NODE_COLORS["default"])
            
        self.body_color = QColor("#2d2d2d")
        self.text_color = QColor("#ffffff")
        self.subtext_color = QColor("#b0b0b0")

    def boundingRect(self):
        return QRectF(0, 0, self.width, self.height)

    def paint(self, painter, option, widget):
        # Update color in case data changed
        self._update_colors()
        
        path = QPainterPath()
        path.addRoundedRect(0, 0, self.width, self.height, 8, 8)
        
        # Draw Shadow/Selection
        if self.isSelected():
            painter.setPen(QPen(QColor("#4a90e2"), 2))
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
        
        # Draw ID
        id_text = f"ID: {self.node_data.get('id', '?')}"
        painter.drawText(QRectF(10, text_y_start + 15, self.width - 20, 20),
                         Qt.AlignLeft, id_text)

    def mouseDoubleClickEvent(self, event):
        super().mouseDoubleClickEvent(event)
        # Signal to edit this node - Logic handled by view/scene finding selection

class NodeGraphScene(QGraphicsScene):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSceneRect(-2500, -2500, 5000, 5000)
        self.grid_size = 20
        self.grid_color = QColor("#2d2d2d")

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
        
        # Test Data
        self.add_node({"node_name": "Start", "node_type": "llm-first", "task_prompt": "Start task", "fixed": True}, 0, 0)
        self.centerOn(0, 0)
        
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
        
        # First pass: Assign new IDs and Map
        for node in nodes_data:
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
            
            # Determine Y
            y = 0
            if "_ui_pos" in node:
                y = node["_ui_pos"][1]
            
            # X is determined by ID in add_node
            self.add_node(node, 0, y)

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
        
        # Enforce X Coordinate based on ID
        # ID 1 -> 0
        # ID 2 -> GAP
        # ...
        calculated_x = (node_id - 1) * self.node_gap_x
        
        item = NodeItem(node_data, calculated_x, y)
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
        super().mousePressEvent(event)
        item = self.itemAt(event.pos())
        if isinstance(item, NodeItem):
            self.nodeSelected.emit(item.node_data)
        else:
            # If clicked on empty space, maybe clear selection?
            pass

    def contextMenuEvent(self, event):
        item = self.itemAt(event.pos())
        if isinstance(item, NodeItem):
            menu = QMenu(self)
            add_node_action = menu.addAction("Add Node")
            add_branch_action = menu.addAction("Create Branch Point")
            menu.addSeparator()
            delete_action = menu.addAction("Delete Node")
            
            action = menu.exec_(self.mapToGlobal(event.pos()))
            
            if action == add_node_action:
                self.add_new_node_from(item)
            elif action == add_branch_action:
                self.add_branch_from(item)
            elif action == delete_action:
                self.delete_node(item)

    def add_new_node_from(self, parent_item):
        # Extension: Same Y level
        new_y = parent_item.y()
        
        # X is auto-calc in add_node
        
        new_data = {
            "node_name": "New Node", 
            "node_type": "llm-first", 
            "task_prompt": "New task...",
            "parent_id": parent_item.node_data.get("id")
        }
        self.add_node(new_data, 0, new_y)

    def add_branch_from(self, parent_item):
        # Branch: Position UPWARDS (negative Y in Qt)
        new_y = parent_item.y() - 120
        
        # Rule 2: Unique color for branch point
        # Generate a random hue, keeping saturation/value high for visibility
        rand_color = QColor.fromHsv(random.randint(0, 359), 200, 200).name()
        
        new_data = {
            "node_name": "Branch", 
            "node_type": "planning", 
            "task_prompt": "Branch logic...",
            "parent_id": parent_item.node_data.get("id"),
            "color": rand_color
        }
        self.add_node(new_data, 0, new_y)

    def delete_node(self, item):
        self.scene.removeItem(item)

    def add_node_at_center(self):
        # Always add to main axis Y=0
        new_data = {
            "node_name": "New Node", 
            "node_type": "llm-first", 
            "task_prompt": "New task..."
        }
        self.add_node(new_data, 0, 0)

class NodePropertyEditor(QGroupBox):
    def __init__(self):
        super().__init__("Node Properties")
        
        # Main Layout (Vertical) to hold Columns and Save Button
        self.main_layout = QVBoxLayout()
        self.main_layout.setContentsMargins(15, 20, 15, 15)
        self.main_layout.setSpacing(10)
        
        # Horizontal container for two columns
        self.columns_layout = QHBoxLayout()
        self.columns_layout.setSpacing(20)
        self.main_layout.addLayout(self.columns_layout)
        
        # Left Column Form
        self.left_form = QFormLayout()
        self.left_form.setSpacing(10)
        
        # Right Column Form
        self.right_form = QFormLayout()
        self.right_form.setSpacing(10)
        
        self.columns_layout.addLayout(self.left_form, 1)
        self.columns_layout.addLayout(self.right_form, 1)
        
        self.current_node_data = None
        
        # --- Core Identifiers ---
        self.name_edit = QLineEdit()
        self.type_combo = QComboBox()
        self.type_combo.addItems(list(ALL_NODE_TYPES))
        
        # --- LLM Config ---
        self.prompt_edit = QTextEdit()
        self.prompt_edit.setMaximumHeight(80)
        self.prompt_edit.setPlaceholderText("Task Prompt (leave empty for tool-only)")
        
        # --- Tools Config ---
        self.tools_edit = QLineEdit()
        self.tools_edit.setPlaceholderText("Comma separated tool names")
        
        self.enable_tool_loop_cb = QCheckBox("Enable Tool Loop")
        
        # --- Tool First Specific ---
        self.initial_tool_name_edit = QLineEdit()
        self.initial_tool_name_edit.setPlaceholderText("Initial Tool Name (Required for tool-first)")
        
        self.initial_tool_args_edit = QTextEdit()
        self.initial_tool_args_edit.setPlaceholderText('Initial Args e.g. {"arg": "val"}')
        self.initial_tool_args_edit.setMaximumHeight(60)

        # --- Data Flow Input ---
        self.data_in_thread_edit = QLineEdit()
        self.data_in_thread_edit.setPlaceholderText("Source Thread ID (Optional)")
        
        self.data_in_slice_edit = QLineEdit()
        self.data_in_slice_edit.setPlaceholderText("Slice: start,end (e.g. -5, or 0,2)")

        # --- Data Flow Output ---
        self.data_out_cb = QCheckBox("Output Data to Parent")
        self.desc_edit = QLineEdit()
        self.desc_edit.setPlaceholderText("Description of output data")

        self.save_btn = QPushButton("Save Changes")
        self.save_btn.clicked.connect(self.save_node_data)
        
        # Connect type change to visibility toggle
        self.type_combo.currentTextChanged.connect(self.update_field_visibility)
        
        # --- Layout Assembly ---
        
        # LEFT COLUMN
        self.left_form.addRow("Name:", self.name_edit)
        self.left_form.addRow("Type:", self.type_combo)
        self.left_form.addRow("Task Prompt:", self.prompt_edit)
        self.left_form.addRow("Tools:", self.tools_edit)
        self.left_form.addRow("", self.enable_tool_loop_cb)
        
        # RIGHT COLUMN
        # Tool First Section
        self.tool_first_group_label = QLabel("--- Tool First Settings ---")
        self.right_form.addRow(self.tool_first_group_label)
        self.right_form.addRow("Init Tool:", self.initial_tool_name_edit)
        self.right_form.addRow("Init Args:", self.initial_tool_args_edit)
        
        # Data Input Section
        self.right_form.addRow(QLabel("--- Data Input ---"))
        self.right_form.addRow("Src Thread:", self.data_in_thread_edit)
        self.right_form.addRow("Slice:", self.data_in_slice_edit)
        
        # Data Output Section
        self.right_form.addRow(QLabel("--- Data Output ---"))
        self.right_form.addRow("", self.data_out_cb)
        self.right_form.addRow("Out Desc:", self.desc_edit)
        
        # Add Save Button to Main Layout (at bottom)
        self.main_layout.addWidget(self.save_btn)
        
        self.setLayout(self.main_layout)
        self.setEnabled(False) # Disable until node selected
        
        # Group widgets for visibility toggling
        self.tool_first_widgets = [
            self.tool_first_group_label,
            self.initial_tool_name_edit,
            self.initial_tool_args_edit,
            self.right_form.labelForField(self.initial_tool_name_edit),
            self.right_form.labelForField(self.initial_tool_args_edit)
        ]

    def update_field_visibility(self, type_text):
        is_tool_first = (type_text == "tool-first")
        
        # Show/Hide Tool First fields
        for w in self.tool_first_widgets:
            if w: w.setVisible(is_tool_first)

    def load_node(self, node_data):
        self.current_node_data = node_data
        self.setEnabled(True)
        self.name_edit.setText(node_data.get("node_name", ""))
        
        ntype = node_data.get("node_type", "llm-first")
        # Handle legacy types map
        if ntype == "llm_auto": ntype = "llm-first"
        if ntype == "tool": ntype = "tool-first"
        self.type_combo.setCurrentText(ntype)
        
        self.prompt_edit.setText(node_data.get("task_prompt", ""))
        
        tools = node_data.get("tools")
        self.tools_edit.setText(", ".join(tools) if tools else "")
        
        self.enable_tool_loop_cb.setChecked(node_data.get("enable_tool_loop", False))
        
        # Tool First
        self.initial_tool_name_edit.setText(node_data.get("initial_tool_name") or "")
        args = node_data.get("initial_tool_args")
        if args:
            try:
                self.initial_tool_args_edit.setText(json.dumps(args, indent=2, ensure_ascii=False))
            except:
                self.initial_tool_args_edit.setText(str(args))
        else:
            self.initial_tool_args_edit.clear()
            
        # Data Input
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
            
        # Data Output
        self.data_out_cb.setChecked(node_data.get("data_out", False))
        self.desc_edit.setText(node_data.get("data_out_description", ""))
            
        self.update_field_visibility(ntype)

    def save_node_data(self):
        if self.current_node_data is not None:
            self.current_node_data["node_name"] = self.name_edit.text()
            self.current_node_data["node_type"] = self.type_combo.currentText()
            self.current_node_data["task_prompt"] = self.prompt_edit.toPlainText()
            
            tools_str = self.tools_edit.text()
            self.current_node_data["tools"] = [t.strip() for t in tools_str.split(",") if t.strip()] if tools_str else None
            
            self.current_node_data["enable_tool_loop"] = self.enable_tool_loop_cb.isChecked()
            
            # Save Tool First Data
            is_tool_first = (self.type_combo.currentText() == "tool-first")
            if is_tool_first:
                self.current_node_data["initial_tool_name"] = self.initial_tool_name_edit.text() or None
                
                args_str = self.initial_tool_args_edit.toPlainText().strip()
                if args_str:
                    try:
                        self.current_node_data["initial_tool_args"] = json.loads(args_str)
                    except json.JSONDecodeError:
                        print("Warning: Invalid JSON in tool args, saving as None")
                        self.current_node_data["initial_tool_args"] = None
                else:
                    self.current_node_data["initial_tool_args"] = None
            else:
                self.current_node_data["initial_tool_name"] = None
                self.current_node_data["initial_tool_args"] = None

            # Data Input
            self.current_node_data["data_in_thread"] = self.data_in_thread_edit.text() or None
            
            slice_str = self.data_in_slice_edit.text().strip()
            if slice_str:
                parts = slice_str.split(',')
                if len(parts) >= 1:
                    s_txt = parts[0].strip()
                    e_txt = parts[1].strip() if len(parts) > 1 else ""
                    
                    s = int(s_txt) if s_txt else None
                    e = int(e_txt) if e_txt else None
                    self.current_node_data["data_in_slice"] = (s, e)
                else:
                    self.current_node_data["data_in_slice"] = None
            else:
                self.current_node_data["data_in_slice"] = None

            # Data Output
            self.current_node_data["data_out"] = self.data_out_cb.isChecked()
            self.current_node_data["data_out_description"] = self.desc_edit.text()
            
            print(f"Saved Node: {self.current_node_data}")
            pass

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Data Driven Agent Debugger (Dark Mode)")
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
        
        self.left_panel = LLMParamPanel()
        left_layout.addWidget(self.left_panel)
        left_layout.addStretch() # Push panel to top
        
        self.main_splitter.addWidget(left_container)
        
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
        self.graph_view.nodeSelected.connect(self.prop_editor.load_node)
        
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
