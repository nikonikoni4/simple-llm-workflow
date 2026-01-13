from typing import Optional

from PyQt5.QtWidgets import (QGroupBox, QVBoxLayout, QWidget, QHBoxLayout, QFormLayout, 
                             QLineEdit, QComboBox, QTextEdit, QCheckBox, QLabel, QFrame, 
                             QSpinBox, QScrollArea, QTabWidget, QPushButton, QDoubleSpinBox)
from PyQt5.QtCore import pyqtSignal
from simple_llm_playground.qt_front.utils import NoScrollComboBox
import json

# 配置导入
from simple_llm_playground.config import BACKEND_PORT

# Schema 导入
from simple_llm_playground.schemas import ALL_NODE_TYPES, NodeProperties


class NodePropertyEditor(QGroupBox):
    nodeDataChanged = pyqtSignal()  # 保存节点数据时发出的信号
    branchChanged = pyqtSignal(dict)  # 分支 (thread_id) 更改时发出的信号
    
    def __init__(self):
        super().__init__("节点属性")
        
        # 主布局
        self.main_layout = QVBoxLayout()
        self.main_layout.setContentsMargins(15, 20, 15, 15)
        self.main_layout.setSpacing(10)
        
        # 创建标签页挂件
        self.tab_widget = QTabWidget()
        self.main_layout.addWidget(self.tab_widget)
        
        # --- 节点设置标签页 ---
        self.node_setting_tab = QWidget()
        node_setting_layout = QVBoxLayout(self.node_setting_tab)
        node_setting_layout.setContentsMargins(10, 10, 10, 10)
        
        # 用于节点设置中两列的水平容器
        self.columns_layout = QHBoxLayout()
        self.columns_layout.setSpacing(20)
        node_setting_layout.addLayout(self.columns_layout)
        
        # 左列表单
        self.left_form = QFormLayout()
        self.left_form.setSpacing(10)
        
        # 右列表单
        self.right_form = QFormLayout()
        self.right_form.setSpacing(10)
        
        self.columns_layout.addLayout(self.left_form, 1)
        self.columns_layout.addLayout(self.right_form, 1)
        
        self.current_node_data: Optional[NodeProperties] = None
        self._loading_data = False  # 用于防止加载期间自动保存的标志
        self._available_tools = {}  # 缓存从后端获取的可用工具
        
        # --- 核心标识符 ---
        self.name_edit = QLineEdit()
        self.type_combo = QComboBox()
        self.type_combo.addItems(list(ALL_NODE_TYPES))
        
        # --- 分支设置 ---
        self.branch_name_edit = QLineEdit()
        self.branch_name_edit.setPlaceholderText("分支名称 (thread_id)")
        
        # --- 任务提示词 (将在单独的标签页中) ---
        self.prompt_edit = QTextEdit()
        self.prompt_edit.setPlaceholderText("任务提示词 (仅工具模式请留空)")
        
        # --- 工具配置 (将在单独的“工具”标签页中) ---
        # 使用列表挂件中的复选框选择工具
        # 使用属性复选框容器选择工具
        self.tools_container = QWidget()
        self.tools_container_layout = QVBoxLayout(self.tools_container)
        self.tools_container_layout.setContentsMargins(20, 0, 0, 0)
        self.tools_container_layout.setSpacing(5)
        self.tool_checkboxes = {} # 名称 -> QCheckBox
        
        self.enable_tool_loop_cb = QCheckBox("启用工具循环")
        
        # --- 工具优先 (Tool First) 特定设置 ---
        # 使用下拉菜单选择初始工具
        self.initial_tool_combo = NoScrollComboBox()
        self.initial_tool_combo.addItem("选择初始工具...")
        self.initial_tool_combo.currentTextChanged.connect(self._on_init_tool_selected)
        
        self.initial_tool_args_edit = QTextEdit()
        self.initial_tool_args_edit.setPlaceholderText('初始参数，例如 {"arg": "val"}')
        self.initial_tool_args_edit.setMinimumHeight(300)

        # --- 数据流输入 ---
        self.data_in_thread_edit = QLineEdit()
        self.data_in_thread_edit.setPlaceholderText("源线程 ID (可选)")
        
        self.data_in_slice_edit = QLineEdit()
        self.data_in_slice_edit.setPlaceholderText("切片: start,end (例如 -5, 或 0,2)")

        # --- 数据流输出 ---
        self.data_out_cb = QCheckBox("输出数据到父级")
        self.data_out_thread_edit = QLineEdit()
        self.data_out_thread_edit.setPlaceholderText("目标线程 ID (默认为 main)")
        self.desc_edit = QLineEdit()
        self.desc_edit.setPlaceholderText("输出数据描述")
        
        # 将类型更改连接到可见性切换
        self.type_combo.currentTextChanged.connect(self.update_field_visibility)
        
        # --- 节点设置标签页的布局组装 ---
        # “节点设置”标签页现在仅包含：名称、类型、分支、数据输入、数据输出
        
        # 左列
        self.left_form.addRow("名称:", self.name_edit)
        self.left_form.addRow("类型:", self.type_combo)
        self.left_form.addRow("分支:", self.branch_name_edit)
        
        # 右列
        # 数据输入部分
        self.right_form.addRow(QLabel("--- 数据输入 ---"))
        self.right_form.addRow("源线程:", self.data_in_thread_edit)
        self.right_form.addRow("切片:", self.data_in_slice_edit)
        
        # 数据输出部分
        self.right_form.addRow(QLabel("--- 数据输出 ---"))
        self.right_form.addRow("", self.data_out_cb)
        self.right_form.addRow("输出线程:", self.data_out_thread_edit)
        self.right_form.addRow("输出描述:", self.desc_edit)
        
        # --- 任务提示词标签页 ---
        self.task_prompt_tab = QWidget()
        task_prompt_layout = QVBoxLayout(self.task_prompt_tab)
        task_prompt_layout.setContentsMargins(0, 0, 0, 0)  # 全屏无边距
        task_prompt_layout.setSpacing(0)
        
        # 添加提示词编辑器以填充整个标签页
        task_prompt_layout.addWidget(self.prompt_edit)
        
        # --- 工具标签页 ---
        self.tools_tab = QWidget()
        tools_main_layout = QHBoxLayout(self.tools_tab)
        tools_main_layout.setContentsMargins(15, 20, 15, 15)
        tools_main_layout.setSpacing(15)
        
        # 左侧：工具选择
        left_tools_widget = QWidget()
        tools_layout = QVBoxLayout(left_tools_widget)
        tools_layout.setContentsMargins(0, 0, 0, 0)
        tools_layout.setSpacing(10)
        
        # 工具选择 (用于 LLM 绑定)
        tools_label = QLabel("Tools (LLM可调用的工具):")
        tools_label.setStyleSheet("font-weight: bold;")
        tools_layout.addWidget(tools_label)

        tools_layout.addWidget(self.tools_container)
        
        # 启用工具循环
        tools_layout.addWidget(self.enable_tool_loop_cb)
        
        # 分隔线
        separator1 = QFrame()
        separator1.setFrameShape(QFrame.Shape.HLine)
        separator1.setFrameShadow(QFrame.Shadow.Sunken)
        tools_layout.addWidget(separator1)
        
        # 工具优先特定设置 (Tool First Settings)
        self.tool_first_label = QLabel("--- Tool First Settings ---")
        tools_layout.addWidget(self.tool_first_label)
        
        init_tool_label = QLabel("Initial Tool (首次运行工具):")
        tools_layout.addWidget(init_tool_label)
        tools_layout.addWidget(self.initial_tool_combo)
        
        init_args_label = QLabel("Initial Args (初始参数):")
        tools_layout.addWidget(init_args_label)
        tools_layout.addWidget(self.initial_tool_args_edit)
        
        # 添加拉伸量以推向顶部
        tools_layout.addStretch()
        
        # 右侧：工具参数信息
        right_tools_widget = QGroupBox("工具参数")
        right_tools_layout = QVBoxLayout(right_tools_widget)
        right_tools_layout.setContentsMargins(10, 10, 10, 10)
        right_tools_layout.setSpacing(5)
        
        # 工具信息显示区域
        self.tool_info_display = QTextEdit()
        self.tool_info_display.setReadOnly(True)
        self.tool_info_display.setPlaceholderText("选择一个工具查看其参数信息...")
        right_tools_layout.addWidget(self.tool_info_display)
        
        # 将左侧包裹在滚动区域内
        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setWidget(left_tools_widget)
        left_scroll.setFrameShape(QFrame.NoFrame) # 可选：如需要则删除边框
        
        # 以 1:1 的比例添加到主布局
        tools_main_layout.addWidget(left_scroll, 1)
        tools_main_layout.addWidget(right_tools_widget, 1)

        
        # --- LLM 设置标签页 ---
        self.llm_setting_tab = QWidget()
        llm_setting_layout = QFormLayout(self.llm_setting_tab)
        llm_setting_layout.setContentsMargins(15, 20, 15, 15)
        llm_setting_layout.setSpacing(10)
        
        # LLM 参数
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
        
        self.enable_search_cb = QCheckBox("启用搜索")
        self.enable_thinking_cb = QCheckBox("启用思考")
        
        llm_setting_layout.addRow("温度 (Temperature):", self.temp_spin)
        llm_setting_layout.addRow("Top-P:", self.topp_spin)
        llm_setting_layout.addRow(self.enable_search_cb)
        llm_setting_layout.addRow(self.enable_thinking_cb)
        
        # 添加拉伸量以将字段推向顶部
        llm_setting_layout.addRow(QWidget())  # 占位符
        
        # 将标签页添加到标签页挂件
        self.tab_widget.addTab(self.node_setting_tab, "节点设置")
        self.tab_widget.addTab(self.task_prompt_tab, "任务提示词")
        self.tab_widget.addTab(self.tools_tab, "工具")
        self.tab_widget.addTab(self.llm_setting_tab, "LLM 设置")
        
        # 保存按钮
        self.save_btn = QPushButton("保存并更新连接")
        self.save_btn.clicked.connect(self.save_node_data)
        self.main_layout.addWidget(self.save_btn)
        
        self.setLayout(self.main_layout)
        self.setEnabled(False) # 在选中节点前禁用
        
        # 用于可见性切换的打组挂件
        self.tool_first_widgets = [
            self.tool_first_label,
            self.initial_tool_combo,
            self.initial_tool_args_edit,
        ]
        
        # --- 连接自动保存信号 ---
        # 所有输入字段在更改时都会自动保存
        self.name_edit.textChanged.connect(self._auto_save)
        self.type_combo.currentTextChanged.connect(self._auto_save)
        self.branch_name_edit.textChanged.connect(self._auto_save)
        self.prompt_edit.textChanged.connect(self._auto_save)
        self.prompt_edit.textChanged.connect(self._auto_save)
        # self.tools_list_widget.itemChanged.connect(self._on_tools_list_changed) # 已删除，改为单独连接
        self.enable_tool_loop_cb.stateChanged.connect(self._auto_save)
        self.enable_tool_loop_cb.stateChanged.connect(self._auto_save)
        # initial_tool_combo 在 _on_init_tool_selected 中处理
        self.initial_tool_args_edit.textChanged.connect(self._auto_save)
        self.data_in_thread_edit.textChanged.connect(self._auto_save)
        self.data_in_slice_edit.textChanged.connect(self._auto_save)
        self.data_out_cb.stateChanged.connect(self._auto_save)
        self.data_out_thread_edit.textChanged.connect(self._auto_save)
        self.desc_edit.textChanged.connect(self._auto_save)
        # LLM 设置
        self.temp_spin.valueChanged.connect(self._auto_save)
        self.topp_spin.valueChanged.connect(self._auto_save)
        self.enable_search_cb.stateChanged.connect(self._auto_save)
        self.enable_thinking_cb.stateChanged.connect(self._auto_save)
        
        # 从后端加载可用工具
        self.load_available_tools()

    def _get_node_val(self, key: str, default=None):
        """
        从 NodeProperties 模型获取属性值
        
        支持向后兼容字典类型，但主要用于 NodeProperties Pydantic 模型
        """
        if self.current_node_data is None:
            return default
        if isinstance(self.current_node_data, dict):
            # 向后兼容：支持旧的字典格式
            return self.current_node_data.get(key, default)
        else:
            # NodeProperties Pydantic 模型
            return getattr(self.current_node_data, key, default)

    def _set_node_val(self, key: str, value):
        """
        设置 NodeProperties 模型的属性值
        
        支持向后兼容字典类型，但主要用于 NodeProperties Pydantic 模型
        """
        if self.current_node_data is None:
            return
        if isinstance(self.current_node_data, dict):
            # 向后兼容：支持旧的字典格式
            self.current_node_data[key] = value
        else:
            # NodeProperties Pydantic 模型 setter
            if hasattr(self.current_node_data, key):
                setattr(self.current_node_data, key, value)
            # else: 忽略模型中不存在的字段

    def _auto_save(self):
        """当任何字段更改时自动保存数据"""
        if not self._loading_data and self.current_node_data is not None:
            self._save_to_node_data()
    
    def load_available_tools(self):
        """从后端 API 加载可用工具"""
        try:
            import requests
            response = requests.get(f"http://localhost:{BACKEND_PORT}/api/tools", timeout=2)
            if response.status_code == 200:
                data = response.json()
                tools = data.get("tools", [])
                
                # 清除现有项
                self.tool_checkboxes = {}
                while self.tools_container_layout.count():
                    child = self.tools_container_layout.takeAt(0)
                    if child.widget():
                        child.widget().deleteLater()
                
                self.initial_tool_combo.clear()
                self.initial_tool_combo.addItem("选择初始工具...")
                
                # 存储工具详情以备后用
                self._available_tools = {}
                self.tool_limit_spinboxes = {}
                
                for tool in tools:
                    tool_name = tool.get("name", "")
                    self._available_tools[tool_name] = tool
                    
                    # 添加到工具容器
                    row_widget = QWidget()
                    row_layout = QHBoxLayout(row_widget)
                    row_layout.setContentsMargins(0, 0, 0, 0)
                    
                    cb = QCheckBox(tool_name)
                    cb.stateChanged.connect(self._on_tools_list_changed)
                    
                    limit_spin = QSpinBox()
                    limit_spin.setRange(0, 999)
                    limit_spin.setSpecialValueText("默认")
                    limit_spin.setPrefix("限制: ")
                    limit_spin.setToolTip("此工具的最大调用次数 (0 = 执行器默认值)")
                    limit_spin.setFixedWidth(120)
                    limit_spin.valueChanged.connect(self._auto_save)
                    
                    row_layout.addWidget(cb)
                    row_layout.addStretch()
                    row_layout.addWidget(limit_spin)
                    
                    self.tools_container_layout.addWidget(row_widget)
                    self.tool_checkboxes[tool_name] = cb
                    self.tool_limit_spinboxes[tool_name] = limit_spin
                    
                    # 添加到初始工具下拉菜单
                    self.initial_tool_combo.addItem(tool_name)
                    
                print(f"Loaded {len(tools)} tools from backend")
            else:
                print(f"Failed to load tools: HTTP {response.status_code}")
        except Exception as e:
            print(f"Error loading tools: {e}")
            # 如果加载失败，则初始化为空字典
            self._available_tools = {}
    
    def _on_tools_list_changed(self):
        """处理列表中工具复选框的更改"""
        # 工具选择更改时自动保存
        if not self._loading_data and self.current_node_data is not None:
            self._save_to_node_data()
    
    def _on_init_tool_selected(self, tool_name: str):
        """处理从下拉菜单中选择的初始工具"""
        # 在右侧面板显示工具参数
        if tool_name and tool_name != "Select initial tool...":
            self._display_tool_info(tool_name)
        else:
            self.tool_info_display.clear()
        
        # 初始工具更改时自动保存
        if not self._loading_data and self.current_node_data is not None:
            self._save_to_node_data()
    
    def _display_tool_info(self, tool_name: str):
        """显示工具参数信息"""
        if hasattr(self, '_available_tools') and tool_name in self._available_tools:
            tool_info = self._available_tools[tool_name]
            
            # 格式化并显示工具信息
            info_text = f"Tool Name: {tool_name}\n"
            info_text += "=" * 60 + "\n\n"
            
            description = tool_info.get("description", "No description available")
            info_text += f"Description:\n{description}\n\n"
            
            # 如果可用，则显示参数
            parameters = tool_info.get("parameters", {})
            if parameters:
                info_text += "Parameters:\n"
                info_text += "-" * 60 + "\n"
                
                for param_name, param_info in parameters.items():
                    param_type = param_info.get("type", "Any")
                    param_required = param_info.get("required", False)
                    param_desc = param_info.get("description", "")
                    
                    # 清理类型字符串
                    if "typing." in param_type:
                        param_type = param_type.replace("typing.", "")
                    if "<class '" in param_type:
                        param_type = param_type.split("'")[1] if "'" in param_type else param_type
                    
                    required_marker = " (必填)" if param_required else " (可选)"
                    info_text += f"\n  • {param_name}: {param_type}{required_marker}\n"
                    
                    if param_desc:
                        info_text += f"    描述: {param_desc}\n"
                
                info_text += "\n"
            else:
                info_text += "Parameters: No parameter information available\n\n"
            
            self.tool_info_display.setPlainText(info_text)
        else:
            self.tool_info_display.setPlainText(f"Tool '{tool_name}' information not available.")
    
    def update_field_visibility(self, type_text):
        is_tool_first = (type_text == "tool-first")
        
        # 显示/隐藏工具优先相关的字段
        for w in self.tool_first_widgets:
            if w: w.setVisible(is_tool_first)


    def load_node(self, node_data: NodeProperties, is_first_in_thread: bool = False):
        # 加载期间禁用自动保存
        self._loading_data = True
        
        self.current_node_data = node_data
        self.setEnabled(True)
        
        # 兼容 node_id (new) 和 id (old)
        nid = self._get_node_val("node_id")
        if nid is None:
            nid = self._get_node_val("id")
            
        # 检查这是否是节点 ID 1 (受保护的主节点)
        is_main_node = (nid == 1)
        
        self.name_edit.setText(self._get_node_val("node_name", ""))
        # 为 ID=1 的节点锁定名称字段
        self.name_edit.setReadOnly(is_main_node)
        self.name_edit.setStyleSheet("background-color: #3e3e3e;" if is_main_node else "")
        
        ntype = self._get_node_val("node_type", "llm-first")
        # 处理旧版类型映射
        if ntype == "llm_auto": ntype = "llm-first"
        if ntype == "tool": ntype = "tool-first"
        self.type_combo.setCurrentText(ntype)
        
        # 加载分支名称 (thread_id)
        self.branch_name_edit.setText(self._get_node_val("thread_id", "main"))
        # 为 ID=1 的节点锁定分支字段 (必须保持为 'main')
        self.branch_name_edit.setReadOnly(is_main_node)
        self.branch_name_edit.setStyleSheet("background-color: #3e3e3e;" if is_main_node else "")
        
        self.prompt_edit.setText(self._get_node_val("task_prompt", ""))
        
        # 加载工具 - 检查项
        tools = self._get_node_val("tools")
        tools_limit = self._get_node_val("tools_limit") or {}
        
        for name, cb in self.tool_checkboxes.items():
            if tools and name in tools:
                cb.setChecked(True)
            else:
                cb.setChecked(False)
            
            # 加载限制
            if hasattr(self, 'tool_limit_spinboxes') and name in self.tool_limit_spinboxes:
                limit_val = tools_limit.get(name, 0)
                self.tool_limit_spinboxes[name].setValue(limit_val)
        
        self.enable_tool_loop_cb.setChecked(self._get_node_val("enable_tool_loop", False))
        
        # 工具优先 - 设置初始工具下拉菜单
        initial_tool = self._get_node_val("initial_tool_name") or ""
        if initial_tool:
            index = self.initial_tool_combo.findText(initial_tool)
            if index >= 0:
                self.initial_tool_combo.setCurrentIndex(index)
            else:
                self.initial_tool_combo.setCurrentIndex(0)
        else:
            self.initial_tool_combo.setCurrentIndex(0)
            
        args = self._get_node_val("initial_tool_args")
        if args:
            try:
                self.initial_tool_args_edit.setText(json.dumps(args, indent=2, ensure_ascii=False))
            except:
                self.initial_tool_args_edit.setText(str(args))
        else:
            self.initial_tool_args_edit.clear()
            
        # 数据输入 - 受限：只有线程中的第一个节点可以编辑
        self.data_in_thread_edit.setText(self._get_node_val("data_in_thread") or "")
        
        slice_val = self._get_node_val("data_in_slice")
        if slice_val:
            # slice_val 是一个元组 (start, end)
            s, e = slice_val
            s_str = str(s) if s is not None else ""
            e_str = str(e) if e is not None else ""
            self.data_in_slice_edit.setText(f"{s_str},{e_str}")
        else:
            self.data_in_slice_edit.clear()
            
        # 应用限制
        self.data_in_thread_edit.setEnabled(is_first_in_thread)
        self.data_in_slice_edit.setEnabled(is_first_in_thread)
        if not is_first_in_thread:
            self.data_in_thread_edit.setToolTip("只有线程的第一个节点可以编辑数据输入。")
            self.data_in_slice_edit.setToolTip("只有线程的第一个节点可以编辑数据输入。")
        else:
            self.data_in_thread_edit.setToolTip("")
            self.data_in_slice_edit.setToolTip("")
            
        # 数据输出
        self.data_out_cb.setChecked(self._get_node_val("data_out", False))
        self.data_out_thread_edit.setText(self._get_node_val("data_out_thread") or "")
        self.desc_edit.setText(self._get_node_val("data_out_description", ""))
        
        # LLM 设置
        self.temp_spin.setValue(self._get_node_val("temperature", 0.7))
        self.topp_spin.setValue(self._get_node_val("top_p", 0.9))
        self.enable_search_cb.setChecked(self._get_node_val("enable_search", False))
        self.enable_thinking_cb.setChecked(self._get_node_val("enable_thinking", False))
            
        self.update_field_visibility(ntype)
        
        # 加载完成后重新启用自动保存
        self._loading_data = False


    def _save_to_node_data(self):
        """内部方法，用于将所有字段保存到节点数据 (被自动保存使用)"""
        if self.current_node_data is None:
            return
            
        # 兼容 node_id / id
        nid = self._get_node_val("node_id")
        if nid is None: nid = self._get_node_val("id")
        
        is_main_node = (nid == 1)
        
        # 对于 ID=1 的节点，保留原始名称
        if not is_main_node:
            self._set_node_val("node_name", self.name_edit.text())
        
        self._set_node_val("node_type", self.type_combo.currentText())
        
        # 对于 ID=1 的节点，强制 thread_id 为 'main'
        if is_main_node:
            self._set_node_val("thread_id", "main")
        else:
            self._set_node_val("thread_id", self.branch_name_edit.text().strip() or "main")
        
        self._set_node_val("task_prompt", self.prompt_edit.toPlainText())
        
        # 保存工具
        checked_tools = []
        for name, cb in self.tool_checkboxes.items():
            if cb.isChecked():
                checked_tools.append(name)
        self._set_node_val("tools", checked_tools if checked_tools else None)
        
        # 保存工具限制
        tools_limit = {}
        if hasattr(self, 'tool_limit_spinboxes'):
             for name, spin in self.tool_limit_spinboxes.items():
                 if spin.value() > 0:
                     tools_limit[name] = spin.value()
        
        self._set_node_val("tools_limit", tools_limit if tools_limit else None)
        
        self._set_node_val("enable_tool_loop", self.enable_tool_loop_cb.isChecked())
        
        # 保存工具优先数据
        is_tool_first = (self.type_combo.currentText() == "tool-first")
        if is_tool_first:
            init_tool = self.initial_tool_combo.currentText()
            val = init_tool if init_tool != "Select initial tool..." else None
            self._set_node_val("initial_tool_name", val)
            
            args_str = self.initial_tool_args_edit.toPlainText().strip()
            if args_str:
                try:
                    self._set_node_val("initial_tool_args", json.loads(args_str))
                except json.JSONDecodeError:
                    pass # 保留旧值
            else:
                self._set_node_val("initial_tool_args", None)
        else:
            self._set_node_val("initial_tool_name", None)
            self._set_node_val("initial_tool_args", None)

        # 数据输入
        self._set_node_val("data_in_thread", self.data_in_thread_edit.text() or None)
        
        slice_str = self.data_in_slice_edit.text().strip()
        if slice_str:
            try:
                parts = slice_str.split(',')
                if len(parts) >= 1:
                    s_txt = parts[0].strip()
                    e_txt = parts[1].strip() if len(parts) > 1 else ""
                    
                    s = int(s_txt) if s_txt else None
                    e = int(e_txt) if e_txt else None
                    self._set_node_val("data_in_slice", (s, e))
                else:
                    self._set_node_val("data_in_slice", None)
            except ValueError:
                pass
        else:
            self._set_node_val("data_in_slice", None)

        # 数据输出
        self._set_node_val("data_out", self.data_out_cb.isChecked())
        self._set_node_val("data_out_thread", self.data_out_thread_edit.text() or None)
        self._set_node_val("data_out_description", self.desc_edit.text())
        
        # LLM 设置
        self._set_node_val("temperature", self.temp_spin.value())
        self._set_node_val("top_p", self.topp_spin.value())
        self._set_node_val("enable_search", self.enable_search_cb.isChecked())
        self._set_node_val("enable_thinking", self.enable_thinking_cb.isChecked())
    
    def save_node_data(self):
        """手动保存 - 更新数据并触发连接更新"""
        if self.current_node_data is not None:
            # 检查分支 (thread_id) 是否已更改
            old_thread_id = self._get_node_val("thread_id", "main")
            
            # 首先保存所有数据
            self._save_to_node_data()
            
            new_thread_id = self._get_node_val("thread_id", "main")
            branch_changed = (old_thread_id != new_thread_id)
            
            print(f"Saved Node: {self.current_node_data}")
            self.nodeDataChanged.emit()  # 通知图表更新连接
            
            # 如果分支改变，发出信号以更新节点颜色
            if branch_changed:
                self.branchChanged.emit(self.current_node_data if isinstance(self.current_node_data, dict) else self.current_node_data.model_dump())
