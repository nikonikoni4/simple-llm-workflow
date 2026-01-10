# 执行控制面板
# 提供执行器初始化、单步执行、全量执行等控制功能

import sys
import os

# 确保可以找到兄弟包
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QLineEdit, QTextEdit, QGroupBox, QProgressBar, QSpinBox,
    QDoubleSpinBox, QCheckBox, QFormLayout, QMessageBox, QComboBox
)
from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtGui import QFont

from .api_client import ExecutorController, APIError


class ExecutionControlPanel(QWidget):
    """
    执行控制面板
    
    提供：
    - 用户消息输入
    - 模型配置（可选展开）
    - 执行控制按钮（初始化、单步、全量、停止）
    - 执行状态和进度显示
    """
    
    # 信号
    executorInitialized = pyqtSignal(str)       # executor_id
    stepExecuted = pyqtSignal(dict)             # node_context
    executionCompleted = pyqtSignal(dict)       # result
    executionError = pyqtSignal(str)            # error message
    nodeStatesUpdated = pyqtSignal(list)        # node_states list
    saveRequested = pyqtSignal()                # Request to save current state
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.controller = ExecutorController()
        self.current_executor_id = None
        self.is_executing = False
        self._plan_data = None  # 保存当前执行计划
        
        self._init_ui()
        self._connect_signals()
    
    def _init_ui(self):
        """初始化 UI"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)
        
        # === 用户消息区域 ===
        message_group = QGroupBox("User Message")
        message_layout = QVBoxLayout(message_group)
        
        self.message_input = QTextEdit()
        self.message_input.setPlaceholderText("Enter the user message to start execution...")
        self.message_input.setMaximumHeight(80)
        message_layout.addWidget(self.message_input)
        
        main_layout.addWidget(message_group)
        
        main_layout.addWidget(message_group)
        
        # === 控制按钮区域 ===
        control_group = QGroupBox("Execution Control")
        control_layout = QVBoxLayout(control_group)
        
        # 第一行：初始化和停止
        row1 = QHBoxLayout()
        
        self.init_btn = QPushButton("🚀 Initialize")
        self.init_btn.setToolTip("Initialize executor with current plan")
        self.init_btn.clicked.connect(self.init_executor)
        row1.addWidget(self.init_btn)
        
        self.stop_btn = QPushButton("⏹ Stop")
        self.stop_btn.setToolTip("Stop current execution")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self.stop_executor)
        row1.addWidget(self.stop_btn)
        
        control_layout.addLayout(row1)
        
        # 第二行：单步执行和全量执行
        row2 = QHBoxLayout()
        
        self.step_btn = QPushButton("⏯ Step")
        self.step_btn.setToolTip("Execute next node")
        self.step_btn.setEnabled(False)
        self.step_btn.clicked.connect(self.step_execute)
        row2.addWidget(self.step_btn)
        
        self.run_btn = QPushButton("▶ Run All")
        self.run_btn.setToolTip("Execute all remaining nodes")
        self.run_btn.setEnabled(False)
        self.run_btn.clicked.connect(self.run_execute)
        row2.addWidget(self.run_btn)
        
        control_layout.addLayout(row2)
        
        main_layout.addWidget(control_group)
        
        # === 状态显示区域 ===
        status_group = QGroupBox("Execution Status")
        status_layout = QVBoxLayout(status_group)
        
        # 状态标签
        status_row = QHBoxLayout()
        status_row.addWidget(QLabel("Status:"))
        self.status_label = QLabel("Not initialized")
        self.status_label.setStyleSheet("font-weight: bold;")
        status_row.addWidget(self.status_label)
        status_row.addStretch()
        status_layout.addLayout(status_row)
        
        # 进度条
        progress_row = QHBoxLayout()
        progress_row.addWidget(QLabel("Progress:"))
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        progress_row.addWidget(self.progress_bar)
        status_layout.addLayout(progress_row)
        
        # 节点统计
        stats_row = QHBoxLayout()
        self.completed_label = QLabel("Completed: 0")
        self.running_label = QLabel("Running: 0")
        self.pending_label = QLabel("Pending: 0")
        self.failed_label = QLabel("Failed: 0")
        stats_row.addWidget(self.completed_label)
        stats_row.addWidget(self.running_label)
        stats_row.addWidget(self.pending_label)
        stats_row.addWidget(self.failed_label)
        status_layout.addLayout(stats_row)
        
        # Tokens 使用统计
        tokens_row = QHBoxLayout()
        tokens_row.addWidget(QLabel("Tokens:"))
        self.tokens_label = QLabel("Input: 0 | Output: 0 | Total: 0")
        tokens_row.addWidget(self.tokens_label)
        tokens_row.addStretch()
        status_layout.addLayout(tokens_row)
        
        main_layout.addWidget(status_group)
        
        # 添加弹簧
        main_layout.addStretch()
    
    def _connect_signals(self):
        """连接控制器信号"""
        self.controller.initCompleted.connect(self._on_init_completed)
        self.controller.initFailed.connect(self._on_init_failed)
        self.controller.stepCompleted.connect(self._on_step_completed)
        self.controller.stepFailed.connect(self._on_step_failed)
        self.controller.runCompleted.connect(self._on_run_completed)
        self.controller.runFailed.connect(self._on_run_failed)
        self.controller.statusUpdated.connect(self._on_status_updated)
    
    def set_plan(self, plan_data: dict):
        """设置要执行的计划"""
        self._plan_data = plan_data
    
    def get_plan_from_nodes(self, nodes_data: list) -> dict:
        """从节点数据构建执行计划"""
        return {
            "task": "debug_execution",
            "nodes": nodes_data
        }
    
    def init_executor(self):
        """初始化执行器"""
        # Request save before initialization to ensure plan is up to date
        self.saveRequested.emit()
        
        if not self._plan_data:
            QMessageBox.warning(self, "Warning", "No execution plan set. Please design your flow first.")
            return
        
        user_message = self.message_input.toPlainText().strip()
        if not user_message:
            QMessageBox.warning(self, "Warning", "Please enter a user message.")
            return
        
        # 更新 UI 状态
        self.init_btn.setEnabled(False)
        self.status_label.setText("Initializing...")
        self.status_label.setStyleSheet("color: #FFC107; font-weight: bold;")
        
        # 调用控制器初始化
        self.controller.init_executor(self._plan_data, user_message)
    
    def step_execute(self):
        """单步执行"""
        if not self.current_executor_id:
            return
        
        self.step_btn.setEnabled(False)
        self.run_btn.setEnabled(False)
        self.status_label.setText("Executing step...")
        self.status_label.setStyleSheet("color: #FFC107; font-weight: bold;")
        
        self.controller.step_executor()
    
    def run_execute(self):
        """全量执行"""
        if not self.current_executor_id:
            return
        
        self.is_executing = True
        self.step_btn.setEnabled(False)
        self.run_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.status_label.setText("Running...")
        self.status_label.setStyleSheet("color: #2196F3; font-weight: bold;")
        
        self.controller.run_executor(sync=True)
    
    def stop_executor(self):
        """停止执行"""
        if self.current_executor_id:
            self.controller.terminate()
            self.current_executor_id = None
            self._reset_ui()
    
    def _reset_ui(self):
        """重置 UI 状态"""
        self.init_btn.setEnabled(True)
        self.step_btn.setEnabled(False)
        self.run_btn.setEnabled(False)
        self.stop_btn.setEnabled(False)
        self.status_label.setText("Not initialized")
        self.status_label.setStyleSheet("font-weight: bold;")
        self.progress_bar.setValue(0)
        self.is_executing = False
    
    def _update_progress(self, progress: dict):
        """更新进度显示"""
        total = progress.get("total", 0)
        completed = progress.get("completed", 0)
        running = progress.get("running", 0)
        pending = progress.get("pending", 0)
        failed = progress.get("failed", 0)
        
        self.completed_label.setText(f"Completed: {completed}")
        self.running_label.setText(f"Running: {running}")
        self.pending_label.setText(f"Pending: {pending}")
        self.failed_label.setText(f"Failed: {failed}")
        
        if total > 0:
            percent = int((completed / total) * 100)
            self.progress_bar.setValue(percent)
    
    def _update_tokens(self, tokens_usage: dict):
        """更新 tokens 统计"""
        input_tokens = tokens_usage.get("input_tokens", 0)
        output_tokens = tokens_usage.get("output_tokens", 0)
        total = input_tokens + output_tokens
        self.tokens_label.setText(f"Input: {input_tokens} | Output: {output_tokens} | Total: {total}")

    def _check_session_error(self, error: str) -> bool:
        """检查是否为会话失效错误 (404)"""
        # API Error 404: Executor not found
        if "404" in str(error) and "not found" in str(error).lower():
            # 会话失效，重置状态
            self.controller.reset_session()
            self._reset_ui()
            # 提示用户
            self.status_label.setText("Session Expired")
            self.status_label.setStyleSheet("color: #F44336; font-weight: bold;")
            return True
        return False
    
    # === 信号处理 ===
    
    def _on_init_completed(self, result: dict):
        """初始化完成"""
        self.current_executor_id = result.get("executor_id")
        self.status_label.setText("Initialized")
        self.status_label.setStyleSheet("color: #4CAF50; font-weight: bold;")
        
        self.init_btn.setEnabled(False)
        self.step_btn.setEnabled(True)
        self.run_btn.setEnabled(True)
        self.stop_btn.setEnabled(True)
        
        node_count = result.get("node_count", 0)
        self.progress_bar.setRange(0, node_count)
        self.progress_bar.setValue(0)
        
        self.executorInitialized.emit(self.current_executor_id)
    
    def _on_init_failed(self, error: str):
        """初始化失败"""
        self.init_btn.setEnabled(True)
        self.status_label.setText("Init failed")
        self.status_label.setStyleSheet("color: #F44336; font-weight: bold;")
        
        self.executionError.emit(error)
        QMessageBox.critical(self, "Initialization Failed", error)
    
    def _on_step_completed(self, result: dict):
        """单步执行完成"""
        status = result.get("status")
        node_context = result.get("node_context")
        progress = result.get("progress", {})
        
        self._update_progress(progress)
        
        if status == "completed":
            self.status_label.setText("All nodes executed")
            self.status_label.setStyleSheet("color: #4CAF50; font-weight: bold;")
            self.step_btn.setEnabled(False)
            self.run_btn.setEnabled(False)
        else:
            self.status_label.setText("Step completed")
            self.status_label.setStyleSheet("color: #4CAF50; font-weight: bold;")
            self.step_btn.setEnabled(True)
            self.run_btn.setEnabled(True)
        
        if node_context:
            self.stepExecuted.emit(node_context)
    
    def _on_step_failed(self, error: str):
        """单步执行失败"""
        # 检查是否为会话失效
        if self._check_session_error(error):
             self.executionError.emit("Session expired (Backend restarted). Please re-initialize.")
             return

        self.step_btn.setEnabled(True)
        self.run_btn.setEnabled(True)
        self.status_label.setText("Step failed")
        self.status_label.setStyleSheet("color: #F44336; font-weight: bold;")
        
        self.executionError.emit(error)
    
    def _on_run_completed(self, result: dict):
        """全量执行完成"""
        self.is_executing = False
        status = result.get("status")
        
        if status == "completed":
            self.status_label.setText("Execution completed")
            self.status_label.setStyleSheet("color: #4CAF50; font-weight: bold;")
            self.progress_bar.setValue(self.progress_bar.maximum())
        else:
            self.status_label.setText(f"Execution {status}")
        
        self.stop_btn.setEnabled(False)
        self.step_btn.setEnabled(False)
        self.run_btn.setEnabled(False)
        
        self.executionCompleted.emit(result)
        
        # 获取最终状态
        self.controller.get_status()
    
    def _on_run_failed(self, error: str):
        """全量执行失败"""
        self.is_executing = False
        
        # 检查是否为会话失效
        if self._check_session_error(error):
             self.executionError.emit("Session expired (Backend restarted). Please re-initialize.")
             return

        self.step_btn.setEnabled(True)
        self.run_btn.setEnabled(True)
        self.stop_btn.setEnabled(True)
        self.status_label.setText("Execution failed")
        self.status_label.setStyleSheet("color: #F44336; font-weight: bold;")
        
        self.executionError.emit(error)
    
    def _on_status_updated(self, status: dict):
        """状态更新"""
        progress = status.get("progress", {})
        node_states = status.get("node_states", [])
        
        self._update_progress(progress)
        self.nodeStatesUpdated.emit(node_states)
    
    def cleanup(self):
        """清理资源"""
        if self.controller:
            self.controller.cleanup()


# =============================================================================
# 测试代码
# =============================================================================

if __name__ == "__main__":
    from PyQt5.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    
    # 应用暗色主题
    app.setStyle("Fusion")
    
    panel = ExecutionControlPanel()
    panel.setWindowTitle("Execution Control Panel - Test")
    panel.resize(400, 500)
    
    # 设置测试计划
    test_plan = {
        "task": "test",
        "nodes": [
            {
                "id": 1,
                "node_type": "llm-first",
                "node_name": "Test Node",
                "task_prompt": "Say hello",
                "thread_id": "main",
                "parent_thread_id": None
            }
        ]
    }
    panel.set_plan(test_plan)
    
    panel.show()
    sys.exit(app.exec())
