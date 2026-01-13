import sys
import json
import requests
from PyQt5.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, QWidget, QHBoxLayout, 
                             QAction, QFileDialog, QSplitter, QLabel, QLineEdit, QComboBox)
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


class ContextLoaderThread(QThread):
    contextLoaded = pyqtSignal(dict)
    
    def __init__(self, port, run_id, node_id):
        super().__init__()
        self.port = port
        self.run_id = run_id
        self.node_id = node_id
        
    def run(self):
        try:
            url = f"http://localhost:{self.port}/api/context/{self.run_id}/{self.node_id}"
            # 超时时间较短，以避免线程滞留，但对于本地后端来说足够了
            resp = requests.get(url, timeout=1.0) 
            if resp.status_code == 200:
                self.contextLoaded.emit(resp.json())
        except Exception:
            # 静默失败或干脆不发送信号轮廓
            pass


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
        # 初始为空，加载文件后会动态填充
        pattern_layout.addWidget(pattern_label)
        pattern_layout.addWidget(self.pattern_combo)
        
        left_panel_layout.addLayout(pattern_layout)

        # Task 输入部分
        task_layout = QHBoxLayout()
        task_label = QLabel("Task:")
        self.task_input = QLineEdit()
        task_layout.addWidget(task_label)
        task_layout.addWidget(self.task_input)
        
        left_panel_layout.addLayout(task_layout)
        
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
        
        # Task 输入变化时同步到 Graph
        self.task_input.textChanged.connect(self.on_task_changed)
        
        # 初始状态
        self._switching_pattern = False  # 防止循环触发


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
        
        # 如果之前的加载器处于活动状态，则取消/断开连接
        if hasattr(self, 'ctx_loader') and self.ctx_loader is not None:
            if self.ctx_loader.isRunning():
                # 断开信号以忽略之前选择的结果
                try: 
                    self.ctx_loader.contextLoaded.disconnect() 
                except TypeError: 
                    pass # 尚未连接
            self.ctx_loader = None

        # 尝试在后台从后端获取上下文
        run_id = "run1" # TODO: 使其动态化
        
        self.ctx_loader = ContextLoaderThread(BACKEND_PORT, run_id, node_data.node_id)
        self.ctx_loader.contextLoaded.connect(self.context_panel.load_node_context_from_api)
        self.ctx_loader.start()



    def on_node_data_changed(self):
        # 如果数据更改影响了连接（如 thread_id），则更新图形视图中的连接
        self.graph_view.update_connections()
        
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
            self.pattern_combo.setCurrentText(patterns[0])
            # 同步 task 输入框
            self.task_input.setText(self.graph_view.get_current_task())
        self._switching_pattern = False
    
    def on_current_pattern_changed(self, pattern_name: str, plan):
        """当 Graph 内部切换 pattern 后的回调"""
        # 同步 task 输入框
        self.task_input.setText(plan.task or "")
    
    def on_pattern_combo_changed(self, pattern_name: str):
        """当用户从 ComboBox 选择不同 pattern 时"""
        if self._switching_pattern or not pattern_name:
            return
        self.graph_view.switch_pattern(pattern_name)
    
    def on_task_changed(self, text: str):
        """当 task 输入框内容变化时，同步到 Graph"""
        self.graph_view.update_current_task(text)

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
