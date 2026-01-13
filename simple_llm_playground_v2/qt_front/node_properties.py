from PyQt5.QtWidgets import (QGroupBox, QVBoxLayout, QWidget, QHBoxLayout, QFormLayout, 
                             QLineEdit, QComboBox, QTextEdit, QCheckBox, QLabel, QFrame, 
                             QSpinBox, QScrollArea, QTabWidget, QPushButton, QDoubleSpinBox)
from PyQt5.QtCore import pyqtSignal
from utils import NoScrollComboBox
import json

# Configuration Imports
try:
    from config import BACKEND_PORT
except ImportError:
    try:
        from ..config import BACKEND_PORT
    except ImportError:
        BACKEND_PORT = 8001

# Schema Imports
try:
    from llm_linear_executor.schemas import ALL_NODE_TYPES
except ImportError:
    # Fallback/Mock if direct import fails
    ALL_NODE_TYPES = ["llm-first", "tool-first"]


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
        self.save_btn = QPushButton("Save _Update Connections")
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
