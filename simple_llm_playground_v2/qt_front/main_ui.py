import sys
import json
import requests
from PyQt5.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, QWidget, QHBoxLayout, 
                             QAction, QFileDialog, QSplitter)
from PyQt5.QtCore import Qt

# Local Imports
from utils import DARK_STYLESHEET
from context_panel import NodeContextPanel
from graph import NodeGraphView
from node_properties import NodePropertyEditor

# App Configuration
try:
    from config import BACKEND_PORT
except ImportError:
    try:
        from ..config import BACKEND_PORT
    except ImportError:
        BACKEND_PORT = 8001

# Logic/Backend Imports
try:
    from llm_linear_executor.schemas import ALL_NODE_TYPES, ExecutionPlan, NodeDefinition
    from llm_linear_executor.os_plan import load_plan_from_dict, save_plan_to_template
except ImportError:
    # Fallback/Mock if imports fail (e.g. running outside of structure)
    ALL_NODE_TYPES = []
    class ExecutionPlan: pass
    class NodeDefinition: pass
    def load_plan_from_dict(*args): return None
    def save_plan_to_template(*args): return None


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Simple LLM Playground")
        self.resize(1600, 1000)
        
        # Central Widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Toolbar
        toolbar = self.addToolBar("Main")
        
        load_action = QAction("Load JSON Plan", self)
        load_action.triggered.connect(self.load_plan)
        toolbar.addAction(load_action)
        
        save_action = QAction("Save JSON Plan", self)
        save_action.triggered.connect(self.save_plan)
        toolbar.addAction(save_action)
        
        # Main Splitter (Horizontal logic)
        main_h_splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(main_h_splitter)
        
        # --- Left Panel: Context & Exec Info ---
        self.context_panel = NodeContextPanel()
        main_h_splitter.addWidget(self.context_panel)
        
        # --- Right Side: Vertical Splitter for Graph and Properties ---
        right_v_splitter = QSplitter(Qt.Vertical)
        main_h_splitter.addWidget(right_v_splitter)
        
        # --- Top Right: Graph View ---
        self.graph_view = NodeGraphView()
        right_v_splitter.addWidget(self.graph_view)
        
        # --- Bottom Right: Properties ---
        self.prop_editor = NodePropertyEditor()
        right_v_splitter.addWidget(self.prop_editor)
        
        # Set splitter sizes
        # Left panel ~30% width, Right side ~70%
        main_h_splitter.setSizes([450, 1150])
        # Top (Graph) ~60% height, Bottom (Properties) ~40%
        right_v_splitter.setSizes([600, 400])
        
        # Connect Signals
        self.graph_view.nodeSelected.connect(self.on_node_selected)
        
        # Connect manual save button AND auto-save updates
        self.prop_editor.nodeDataChanged.connect(self.on_node_data_changed)
        
        # Connect branch change signal to update node color
        self.prop_editor.branchChanged.connect(self.on_branch_changed) # NEW connection
        
        # Initial State
        self.current_file_path = None

    def on_node_selected(self, node_data):
        # 1. Load data into Property Editor
        # Determine if this node is first in its thread
        # Find all nodes in this thread, check if this node has lowest ID
        thread_id = node_data.get("thread_id", "main")
        current_id = node_data.get("id")
        
        # Get all nodes from graph scene to check IDs
        all_nodes = self.graph_view.get_all_nodes_data()
        thread_nodes = [n for n in all_nodes if n.get("thread_id") == thread_id]
        
        if thread_nodes:
             min_id = min(n.get("id", 999999) for n in thread_nodes)
             is_first = (current_id == min_id)
        else:
             is_first = True # Should be unique if it's the only one found?
             
        self.prop_editor.load_node(node_data, is_first_in_thread=is_first)
        
        # 2. Load Context from API
        # Only if we have execution context/logs? 
        # For now, just clear or load mock
        self.context_panel.load_node_context(node_data)
        
        # Try fetch context from backend
        run_id = "run1" # TODO: Make dynamic
        try:
             url = f"http://localhost:{BACKEND_PORT}/api/context/{run_id}/{node_data['id']}"
             resp = requests.get(url, timeout=0.5)
             if resp.status_code == 200:
                 self.context_panel.load_node_context_from_api(resp.json())
             else:
                 self.context_panel.clear_context()
        except:
             self.context_panel.clear_context()

    def on_node_data_changed(self):
        # Update connections in graph view if data changed affecting them (like thread_id)
        self.graph_view.update_connections()
        
    def on_branch_changed(self, node_data):
        """Handle branch (thread_id) change to update node color"""
        self.graph_view.update_node_color(node_data)

    def load_plan(self):
        path, _ = QFileDialog.getOpenFileName(self, "Load Plan JSON", "", "JSON Files (*.json)")
        if path:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                
                # Check format (List or Dict with 'nodes')
                nodes = []
                if isinstance(data, list):
                    nodes = data
                elif isinstance(data, dict) and "nodes" in data:
                    nodes = data["nodes"]
                
                self.graph_view.auto_layout_nodes(nodes)
                self.current_file_path = path
                print(f"Loaded {len(nodes)} nodes from {path}")
            except Exception as e:
                print(f"Error loading plan: {e}")

    def save_plan(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save Plan JSON", "", "JSON Files (*.json)")
        if path:
            try:
                nodes = self.graph_view.get_all_nodes_data()
                
                # Clean up UI-specific fields before saving? 
                # Or keep them for layout persistence.
                # If we want clean export:
                clean_nodes = []
                for n in nodes:
                    n_copy = n.copy()
                    # Remove internal UI flags if any (like _ui_pos if not wanted)
                    # But we usually want _ui_pos if we support drag persistence.
                    clean_nodes.append(n_copy)
                
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(clean_nodes, f, indent=2, ensure_ascii=False)
                
                print(f"Saved {len(nodes)} nodes to {path}")
            except Exception as e:
                print(f"Error saving plan: {e}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyleSheet(DARK_STYLESHEET)
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec_())
