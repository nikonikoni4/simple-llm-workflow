from PyQt5.QtWidgets import QGroupBox, QVBoxLayout, QTextBrowser
from simple_llm_playground.qt_front.utils import CollapsibleSection
from simple_llm_playground.schemas import NodeProperties
class NodeContextPanel(QGroupBox):
    """用于显示节点线程上下文信息的面板"""
    def __init__(self):
        super().__init__("Node Context")
        self.main_layout = QVBoxLayout()
        self.main_layout.setContentsMargins(10, 15, 10, 10)
        self.main_layout.setSpacing(8)
        
        # 上下文消息部分
        self.context_section = CollapsibleSection("Context Information")
        self.context_browser = QTextBrowser()
        self.context_browser.setMinimumHeight(50)
        self.context_browser.setMaximumHeight(1200)
        self.context_browser.setPlaceholderText("No context data available")
        self.context_section.set_content(self.context_browser)
        self.main_layout.addWidget(self.context_section)
        
        # LLM 输入提示词部分
        self.prompt_section = CollapsibleSection("LLM Input Prompt")
        self.prompt_browser = QTextBrowser()
        self.prompt_browser.setMinimumHeight(50)
        self.prompt_browser.setMaximumHeight(1200)
        self.prompt_browser.setPlaceholderText("No prompt data available")
        self.prompt_section.set_content(self.prompt_browser)
        self.main_layout.addWidget(self.prompt_section)
        
        # 节点输出部分
        self.output_section = CollapsibleSection("Node Output")
        self.output_browser = QTextBrowser()
        self.output_browser.setMinimumHeight(50)
        self.output_browser.setMaximumHeight(1200)
        self.output_browser.setPlaceholderText("No output data available")
        self.output_section.set_content(self.output_browser)
        self.main_layout.addWidget(self.output_section)
        
        # 添加拉伸量以将各部分推向顶部
        self.main_layout.addStretch()
        
        self.setLayout(self.main_layout)
    
    def load_node_context(self, node_data: NodeProperties):
        """加载并显示节点的上下文信息"""
        # 目前仅显示占位文本
        # 未来将填充真实的执行数据
        
        node_name = node_data.node_name
        thread_id = node_data.thread_id
        
        # 上下文信息
        context_html = f"""
        <b>Node:</b> {node_name}<br>
        <b>Thread ID:</b> {thread_id}<br>
        <b>Status:</b> <i>Not executed yet</i><br>
        <br>
        <i>Context messages will appear here during execution</i>
        """
        self.context_browser.setHtml(context_html)
        
        # 提示词信息
        prompt_html = f"""
        <i>LLM input prompt will appear here during execution</i>
        """
        self.prompt_browser.setHtml(prompt_html)
        
        # 输出信息
        output_html = f"""
        <i>Node output will appear here after execution</i>
        """
        self.output_browser.setHtml(output_html)
    
    def clear_context(self):
        """清除所有上下文信息"""
        self.context_browser.clear()
        self.prompt_browser.clear()
        self.output_browser.clear()
    
    def load_node_context_from_api(self, context_data: dict):
        """
        从 API 响应中加载并显示上下文信息
        
        参数:
            context_data: 包含 node_id, node_name, thread_id,
                         thread_messages_before, thread_messages_after,
                         llm_input, llm_output, tool_calls, data_out_content 的字典
        """
        node_name = context_data.get("node_name", "Unknown")
        node_id = context_data.get("node_id", "?")
        thread_id = context_data.get("thread_id", "main")
        
        # 格式化上下文消息
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
        
        # LLM 输入提示词
        llm_input = context_data.get("llm_input", "")
        prompt_html = f"""
        <div style="background-color: #2d2d2d; padding: 8px; border-radius: 4px; white-space: pre-wrap;">
        {llm_input if llm_input else '<i>No LLM input</i>'}
        </div>
        """
        self.prompt_browser.setHtml(prompt_html)
        
        # 节点输出 (LLM 输出 + 工具调用)
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
