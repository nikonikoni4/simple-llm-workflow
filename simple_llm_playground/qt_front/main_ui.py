import sys
import json
import requests
from PyQt5.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, QWidget, QHBoxLayout, 
                             QAction, QFileDialog, QSplitter, QLabel, QLineEdit)
from PyQt5.QtCore import Qt, QThread, pyqtSignal

# 本地导入
from utils import DARK_STYLESHEET
from context_panel import NodeContextPanel
from graph import NodeGraphView
from node_properties import NodePropertyEditor

# 应用配置
try:
    from config import BACKEND_PORT
except ImportError:
    try:
        from ..config import BACKEND_PORT
    except ImportError:
        BACKEND_PORT = 8001

# 逻辑/后端导入
# 逻辑/后端导入
try:
    from ..schemas import ALL_NODE_TYPES, ExecutionPlan, NodeDefinition, GuiExecutionPlan
    from llm_linear_executor.os_plan import load_plan_from_dict, save_plan_to_template
except ImportError:
    try:
        from simple_llm_playground_v2.schemas import ALL_NODE_TYPES, ExecutionPlan, NodeDefinition, GuiExecutionPlan
        from llm_linear_executor.os_plan import load_plan_from_dict, save_plan_to_template
    except ImportError:
        # 如果导入失败，则使用回退/模拟 (例如在结构之外运行)
        ALL_NODE_TYPES = []
        class ExecutionPlan: pass
        class NodeDefinition: pass
        class GuiExecutionPlan: pass
        def load_plan_from_dict(*args): return None
        def save_plan_to_template(*args): return None



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
        load_action.triggered.connect(self.load_plan)
        toolbar.addAction(load_action)
        
        save_action = QAction("Save JSON Plan", self)
        save_action.triggered.connect(self.save_plan)
        toolbar.addAction(save_action)
        
        # 主分割器 (水平逻辑)
        main_h_splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(main_h_splitter)
        
        # --- 左侧面板: Task 输入及上下文信息 ---
        # --- 左侧面板: Task 输入及上下文信息 ---
        left_panel_widget = QWidget()
        left_panel_layout = QVBoxLayout(left_panel_widget)
        left_panel_layout.setContentsMargins(5, 5, 5, 5)
        left_panel_layout.setSpacing(5)
        
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
        # 左面板约 30% 宽度，右侧约 70%
        main_h_splitter.setSizes([450, 1150])
        # 顶部 (图表) 约 60% 高度，底部 (属性) 约 40%
        right_v_splitter.setSizes([600, 400])
        
        # 连接信号
        self.graph_view.nodeSelected.connect(self.on_node_selected)
        
        # 连接手动保存按钮以及自动保存更新
        self.prop_editor.nodeDataChanged.connect(self.on_node_data_changed)
        
        # 连接分支更改信号以更新节点颜色
        self.prop_editor.branchChanged.connect(self.on_branch_changed)
        
        # 初始状态轮廓
        self.current_file_path = None

    def on_node_selected(self, node_data):
        # 1. 将数据加载到属性编辑器中
        # 确定该节点是否为其线程中的第一个节点
        # 查找该线程中的所有节点，检查该节点是否具有最低 ID
        thread_id = node_data.get("thread_id", "main")
        current_id = node_data.get("id")
        
        # 从图表场景获取所有节点以检查 ID
        all_nodes = self.graph_view.get_all_nodes_data()
        thread_nodes = [n for n in all_nodes if n.get("thread_id") == thread_id]
        
        if thread_nodes:
             min_id = min(n.get("id", 999999) for n in thread_nodes)
             is_first = (current_id == min_id)
        else:
             is_first = True # 如果只找到这一个，那它应该是唯一的？
             
        self.prop_editor.load_node(node_data, is_first_in_thread=is_first)
        
        # 2. 从 API 加载上下文 (异步)
        # 首先清除/加载占位符
        self.context_panel.load_node_context(node_data)
        
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
        
        self.ctx_loader = ContextLoaderThread(BACKEND_PORT, run_id, node_data['id'])
        self.ctx_loader.contextLoaded.connect(self.context_panel.load_node_context_from_api)
        self.ctx_loader.start()



    def on_node_data_changed(self):
        # 如果数据更改影响了连接（如 thread_id），则更新图性格视图中的连接
        self.graph_view.update_connections()
        
    def on_branch_changed(self, node_data):
        """处理分支 (thread_id) 更改以更新节点颜色"""
        self.graph_view.update_node_color(node_data)

    def load_plan(self):
        path, _ = QFileDialog.getOpenFileName(self, "Load Plan JSON", "", "JSON Files (*.json)")
        if path:
            try:
                # 1. 使用 os_plan 的 load_plan_from_template (这里我们没有 template pattern，直接加载文件内容)
                # 但 os_plan.load_plan_from_template 实际上是加载 模版+变量. 
                # 这里我们直接加载 dict, 模拟 os_plan.load_plan_from_dict 的行为 (如果存在) 或者直接用 load_plan_from_dict
                
                with open(path, "r", encoding="utf-8") as f:
                    raw_data = json.load(f)
                
                # 兼容旧格式 list
                if isinstance(raw_data, list):
                    raw_data = {"task": "Imported Task", "nodes": raw_data}
                
                # 2. 转换为 GuiExecutionPlan (Pydantic 验证 + 坐标解析)
                plan_model = GuiExecutionPlan(**raw_data)
                
                # 更新 task 输入
                self.task_input.setText(plan_model.task)
                
                # 3. 转换为 dict 列表供 graph 使用 (model_dump)
                nodes = [n.model_dump() for n in plan_model.nodes]
                
                self.graph_view.auto_layout_nodes(nodes)
                self.current_file_path = path
                print(f"Loaded {len(nodes)} nodes from {path}")
            except Exception as e:
                print(f"Error loading plan: {e}")
                import traceback
                traceback.print_exc()


    def save_plan(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save Plan JSON", "", "JSON Files (*.json)")
        if path:
            try:
                nodes = self.graph_view.get_all_nodes_data()
                task_name = self.task_input.text() or "untitled_task"
                
                # 使用 GuiExecutionPlan 构建和验证
                plan = GuiExecutionPlan(
                    task=task_name,
                    nodes=nodes
                )
                
                # 保存为 JSON
                with open(path, "w", encoding="utf-8") as f:
                    # exclude_none=True 可以保持整洁，但要确保 backend 不依赖 null
                    f.write(plan.model_dump_json(indent=2, ensure_ascii=False))
                
                print(f"Saved {len(nodes)} nodes to {path}")
            except Exception as e:
                print(f"Error saving plan: {e}")
                # 可以在这里弹窗提示错误
                import traceback
                traceback.print_exc()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyleSheet(DARK_STYLESHEET)
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec_())
