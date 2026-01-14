import sys
import json
import requests
from PyQt5.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, QWidget, QHBoxLayout, 
                             QAction, QFileDialog, QSplitter, QLabel, QLineEdit, QComboBox, 
                             QMessageBox, QPushButton, QInputDialog)
from PyQt5.QtCore import Qt, QThread, pyqtSignal

# 本地导入
from simple_llm_playground.qt_front.utils import DARK_STYLESHEET
from simple_llm_playground.qt_front.context_panel import NodeContextPanel
from simple_llm_playground.qt_front.graph import NodeGraphView
from simple_llm_playground.qt_front.node_properties import NodePropertyEditor

# 应用配置
from simple_llm_playground.config import BACKEND_PORT

# 逻辑/后端导入
from simple_llm_playground.schemas import ALL_NODE_TYPES, NodeProperties, GuiExecutionPlan

from simple_llm_playground.qt_front.execution_panel import ExecutionControlPanel


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Simple LLM Playground")
        self.resize(1600, 1000)
        
        # 中心组件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # 工具栏
        toolbar = self.addToolBar("Main")
        
        load_action = QAction("Load JSON Plan", self)
        load_action.triggered.connect(self.load_plans)
        toolbar.addAction(load_action)
        
        save_action = QAction("Save JSON Plan", self)
        save_action.triggered.connect(self.save_plan)
        toolbar.addAction(save_action)
        
        # 主分割器 (水平逻辑)
        main_h_splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(main_h_splitter)
        
        # --- 左侧面板: Task 输入及上下文信息 ---
        left_panel_widget = QWidget()
        left_panel_layout = QVBoxLayout(left_panel_widget)
        left_panel_layout.setContentsMargins(5, 5, 5, 5)
        left_panel_layout.setSpacing(5)
        
        # Pattern 选择部分
        pattern_layout = QHBoxLayout()
        pattern_label = QLabel("Pattern:")
        self.pattern_combo = QComboBox()
        self.pattern_combo.setEditable(True)  # 允许编辑以重命名 pattern
        self.pattern_combo.setInsertPolicy(QComboBox.NoInsert)  # 不自动插入新项
        # 初始为空，加载文件后会动态填充
        self._editing_pattern_name = None  # 用于跟踪编辑前的名称
        
        # 添加新 Pattern 的按钮
        self.add_pattern_btn = QPushButton("+")
        self.add_pattern_btn.setFixedSize(28, 28)
        self.add_pattern_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border-radius: 14px;
                font-weight: bold;
                font-size: 20px;
                padding-bottom: 3px;
            }
            QPushButton:hover {
                background-color: #42A5F5;
            }
            QPushButton:pressed {
                background-color: #1976D2;
            }
        """)
        self.add_pattern_btn.clicked.connect(self.on_add_pattern_clicked)
        
        pattern_layout.addWidget(pattern_label)
        pattern_layout.addWidget(self.pattern_combo)
        pattern_layout.addWidget(self.add_pattern_btn)
        
        left_panel_layout.addLayout(pattern_layout)

        # Task 输入部分
        task_layout = QHBoxLayout()
        task_label = QLabel("Task:")
        self.task_input = QLineEdit()
        task_layout.addWidget(task_label)
        task_layout.addWidget(self.task_input)
        
        left_panel_layout.addLayout(task_layout)
        
        # 执行控制面板
        self.execution_panel = ExecutionControlPanel()
        left_panel_layout.addWidget(self.execution_panel)
        
        # 上下文/执行面板
        self.context_panel = NodeContextPanel()
        left_panel_layout.addWidget(self.context_panel)
        
        main_h_splitter.addWidget(left_panel_widget)
        
        # --- 右侧: 用于图表和属性的垂直分割器 ---
        right_v_splitter = QSplitter(Qt.Vertical)
        main_h_splitter.addWidget(right_v_splitter)
        
        # --- 右上: 图形视图 ---
        self.graph_view = NodeGraphView()
        right_v_splitter.addWidget(self.graph_view)
        
        # --- 右下: 属性 ---
        self.prop_editor = NodePropertyEditor()
        right_v_splitter.addWidget(self.prop_editor)
        
        # 设置分割器大小
        main_h_splitter.setSizes([450, 1150])
        right_v_splitter.setSizes([600, 400])
        
        # === 连接信号 ===
        # 节点选择信号
        self.graph_view.nodeSelected.connect(self.on_node_selected)
        
        # 属性编辑器信号
        self.prop_editor.nodeDataChanged.connect(self.on_node_data_changed)
        self.prop_editor.branchChanged.connect(self.on_branch_changed)
        
        # 多 Pattern 管理信号
        self.graph_view.patternListChanged.connect(self.on_patterns_loaded)
        self.graph_view.currentPatternChanged.connect(self.on_current_pattern_changed)
        self.pattern_combo.currentTextChanged.connect(self.on_pattern_combo_changed)
        
        # Pattern 名称编辑信号
        self.pattern_combo.lineEdit().editingFinished.connect(self.on_pattern_name_edited)
        
        # Task 输入变化时同步到 Graph 并更新执行计划
        self.task_input.textChanged.connect(self.on_task_changed)
        self.task_input.textChanged.connect(self._update_execution_plan)
        
        # === 执行面板信号 ===
        self.execution_panel.stepExecuted.connect(self._on_step_executed)
        self.execution_panel.nodeStatesUpdated.connect(self._on_node_states_updated)
        self.execution_panel.executionError.connect(self._on_execution_error)
        self.execution_panel.saveRequested.connect(self._update_execution_plan)
        
        # 上下文相关信号
        self.execution_panel.controller.contextLoaded.connect(self._on_context_loaded)
        self.execution_panel.controller.contextFailed.connect(self._on_context_failed)

        # 初始状态
        self._switching_pattern = False  # 防止循环触发
        
        # 自动创建默认的 "custom" pattern
        self.graph_view.create_new_pattern("custom")


    def _update_execution_plan(self):
        """当节点数据或任务变更时，更新 execution_panel 的计划"""
        nodes = self.graph_view.get_all_nodes_data() # List[NodeProperties]
        # Pydantic 转 dict
        nodes_dicts = [n.model_dump() for n in nodes]
        
        current_task = self.task_input.text()
        
        plan_data = {
            "task": current_task,
            "nodes": nodes_dicts
        }
        self.execution_panel.set_plan(plan_data)

    def _on_step_executed(self, node_context: dict):
        """单步执行完成回调"""
        # 更新该节点的上下文显示
        self.context_panel.load_node_context_from_api(node_context)
        
        # 更新节点状态为完成
        node_id = node_context.get("node_id")
        if node_id:
            self.graph_view.update_node_status(node_id, "completed")

    def _on_node_states_updated(self, node_states: list):
        """批量更新节点状态"""
        for state in node_states:
            node_id = state.get("node_id")
            status = state.get("status", "pending")
            self.graph_view.update_node_status(node_id, status)

    def _on_execution_error(self, error: str):
        QMessageBox.warning(self, "Execution Error", error)

    def _on_context_loaded(self, context_data: dict):
        self.context_panel.load_node_context_from_api(context_data)

    def _on_context_failed(self, error: str):
        # 简单处理：仅打印或忽略，用户点其他节点会重试
        print(f"Failed to load context: {error}")

    def on_node_selected(self, node_data):
        # 1. 转换数据为 NodeProperties 对象 (如果是字典则转换)
        if isinstance(node_data, NodeProperties):
            node_props = node_data
            thread_id = node_props.thread_id
            current_id = node_props.node_id
        else:
            thread_id = node_data.get("thread_id", "main")
            current_id = node_data.get("id")
            try:
                # 准备数据，确保必需字段存在
                node_props_data = {
                    "node_id": node_data.get("id", 0),
                    "thread_view_index": node_data.get("thread_view_index", 0),
                    "node_type": node_data.get("node_type", "llm-first"),
                    "node_name": node_data.get("node_name", ""),
                    "thread_id": thread_id,
                    "x": node_data.get("x", 0),
                    "y": node_data.get("y", 0),
                    # 可选字段
                    "task_prompt": node_data.get("task_prompt", ""),
                    "tools": node_data.get("tools"),
                    "enable_tool_loop": node_data.get("enable_tool_loop", False),
                    "tools_limit": node_data.get("tools_limit"),
                    "initial_tool_name": node_data.get("initial_tool_name"),
                    "initial_tool_args": node_data.get("initial_tool_args"),
                    "data_in_thread": node_data.get("data_in_thread", "main"),
                    "data_in_slice": node_data.get("data_in_slice", (0, 1)),
                    "data_out_thread": node_data.get("data_out_thread", "main"),
                    "data_out": node_data.get("data_out", False),
                    "data_out_description": node_data.get("data_out_description", ""),
                }
                node_props = NodeProperties(**node_props_data)
            except Exception as e:
                print(f"Warning: Failed to create NodeProperties, using dict fallback: {e}")
                node_props = node_data  # 回退到字典

        # 2. 确定该节点是否为其线程中的第一个节点
        # 从图表场景获取所有节点以检查 ID
        all_nodes = self.graph_view.get_all_nodes_data()
        thread_nodes = [n for n in all_nodes if n.thread_id == thread_id]
        
        if thread_nodes:
             min_id = min(n.node_id for n in thread_nodes)
             is_first = (current_id == min_id)
        else:
             is_first = True 
             
        self.prop_editor.load_node(node_props, is_first_in_thread=is_first)
        
        # 3. 加载 UI 显示相关的上下文 (占位符)
        self.context_panel.load_node_context(node_props)
        
        # 4. 如果执行器已初始化，尝试从后端加载真实上下文
        executor_id = getattr(self.execution_panel.controller, "current_executor_id", None)
        if executor_id:
            # 确保使用正确的 node_id
            nid = getattr(node_props, "node_id", None)
            if nid is None and isinstance(node_props, dict):
                 nid = node_props.get("id")
            
            if nid is not None:
                self.execution_panel.controller.get_node_context(nid)

    def on_node_data_changed(self):
        # 如果数据更改影响了连接（如 thread_id），则更新图形视图中的连接
        self.graph_view.update_connections()
        # 更新执行计划
        self._update_execution_plan()
        
    def on_branch_changed(self, node_data):
        """处理分支 (thread_id) 更改以更新节点颜色"""
        self.graph_view.update_node_color(node_data)

    # ==================== 多 Pattern 管理 ====================
    
    def on_patterns_loaded(self, patterns: list):
        """当 Graph 加载完文件后，更新 ComboBox"""
        self._switching_pattern = True
        self.pattern_combo.clear()
        self.pattern_combo.addItems(patterns)
        if patterns:
            # 优先选中当前正在显示的 pattern，否则选中第一个
            current = self.graph_view.current_pattern
            if current and current in patterns:
                self.pattern_combo.setCurrentText(current)
            else:
                self.pattern_combo.setCurrentText(patterns[0])
            # 同步 task 输入框
            self.task_input.setText(self.graph_view.get_current_task())
        self._switching_pattern = False
    
    def on_current_pattern_changed(self, pattern_name: str, plan):
        """当 Graph 内部切换 pattern 后的回调"""
        # 同步 task 输入框
        self.task_input.setText(plan.task or "")
        # 更新执行面板的计划
        self._update_execution_plan()
    
    def on_pattern_combo_changed(self, pattern_name: str):
        """当用户从 ComboBox 选择不同 pattern 时"""
        if self._switching_pattern or not pattern_name:
            return
        
        # 记录当前选中的 pattern 名称，用于后续重命名判断
        self._editing_pattern_name = self.graph_view.current_pattern
        
        # 检查是否是选择了一个已存在的 pattern
        if pattern_name in self.graph_view.all_plans:
            self.graph_view.switch_pattern(pattern_name)
    
    def on_pattern_name_edited(self):
        """当用户编辑完 pattern 名称后（按下回车或失去焦点）"""
        if self._switching_pattern:
            return
            
        new_name = self.pattern_combo.currentText().strip()
        old_name = self.graph_view.current_pattern
        
        # 如果名称没有变化或为空，恢复原名称
        if not new_name or new_name == old_name:
            if old_name:
                self._switching_pattern = True
                self.pattern_combo.setCurrentText(old_name)
                self._switching_pattern = False
            return
        
        # 尝试重命名
        success = self.graph_view.rename_pattern(old_name, new_name)
        if not success:
            # 重命名失败，恢复原名称
            self._switching_pattern = True
            self.pattern_combo.setCurrentText(old_name)
            self._switching_pattern = False
            QMessageBox.warning(
                self, 
                "Error", 
                f"Failed to rename pattern. '{new_name}' may already exist."
            )
    
    def on_task_changed(self, text: str):
        """当 task 输入框内容变化时，同步到 Graph"""
        self.graph_view.update_current_task(text)
    
    def on_add_pattern_clicked(self):
        """点击添加 pattern 按钮时弹出对话框"""
        pattern_name, ok = QInputDialog.getText(
            self, 
            "Create New Pattern", 
            "Enter pattern name:",
            QLineEdit.Normal,
            ""
        )
        
        if ok and pattern_name.strip():
            # 调用 graph_view 创建新 pattern
            success = self.graph_view.create_new_pattern(pattern_name.strip())
            if success:
                # 更新 ComboBox 选中项
                self._switching_pattern = True
                # ComboBox 会被 patternListChanged 信号自动更新
                # 这里只需要设置当前选中项
                self.pattern_combo.setCurrentText(pattern_name.strip())
                self._switching_pattern = False
            else:
                QMessageBox.warning(
                    self, 
                    "Error", 
                    f"Failed to create pattern '{pattern_name}'. It may already exist."
                )

    def load_plans(self):
        """加载 JSON 计划文件"""
        path, _ = QFileDialog.getOpenFileName(self, "Load Plan JSON", "", "JSON Files (*.json)")
        if path:
            try:
                patterns = self.graph_view.load_from_file(path)
                print(f"Loaded {len(patterns)} patterns: {patterns}")
            except Exception as e:
                print(f"Error loading plans: {e}")
                import traceback
                traceback.print_exc()

    def save_plan(self):
        """保存 JSON 计划文件"""
        # 如果没有加载过文件，则询问保存路径
        if not self.graph_view.current_file_path:
            path, _ = QFileDialog.getSaveFileName(self, "Save Plan JSON", "", "JSON Files (*.json)")
            if not path:
                return
        else:
            path = self.graph_view.current_file_path
        
        try:
            success = self.graph_view.save_to_file(path)
            if success:
                print(f"Plan saved successfully to {path}")
        except Exception as e:
            print(f"Error saving plan: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyleSheet(DARK_STYLESHEET)
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec_())
