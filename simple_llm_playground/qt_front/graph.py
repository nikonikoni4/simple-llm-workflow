from PyQt5.QtWidgets import QGraphicsView, QGraphicsScene, QGraphicsItem, QGraphicsLineItem, QGraphicsPathItem, QPushButton, QGraphicsDropShadowEffect, QMenu
from PyQt5.QtCore import Qt, QRectF, QPointF, pyqtSignal
from PyQt5.QtGui import QPen, QBrush, QColor, QWheelEvent, QPainter, QPainterPath, QFont
import random
import json
from simple_llm_playground.qt_front.utils import NODE_COLORS, THREAD_COLORS
from simple_llm_playground.schemas import NodeProperties, GuiExecutionPlan
from typing import Union, Dict, Optional, List
class NodeItem(QGraphicsItem):
    """
    自定义节点项，具有圆角、页眉和阴影。
    """
    def __init__(self, node_data: NodeProperties, w=180, h=80, thread_color=None):
        super().__init__()
        # 直接从 node_data 中读取坐标
        self.setPos(node_data.x, node_data.y)
        self.width = w
        self.height = h
        self.node_data: NodeProperties = node_data
        self.thread_color = thread_color  # 用于区分线程的颜色
        
        # 用于拖拽连接的输出锚点 (右侧)
        self.output_anchor_rect = QRectF(self.width - 12, self.height/2 - 6, 12, 12)
        
        # 交换按钮 (ID 旁边的左右箭头)
        # 它们在 paint 方法中动态定位
        self.left_swap_rect = QRectF(0, 0, 0, 0)  # 将在 paint 中设置
        self.right_swap_rect = QRectF(0, 0, 0, 0)  # 将在 paint 中设置
        self.hover_swap_button = None  # 追踪悬停在哪个按钮上: 'left', 'right', 'up', 'down', 或 None
        
        # 线程交换按钮 (用于线程位置的上下箭头)
        self.up_thread_rect = QRectF(0, 0, 0, 0)  # 将在 paint 中设置
        self.down_thread_rect = QRectF(0, 0, 0, 0)  # 将在 paint 中设置
        
        # 规则 1: 固定位置。始终禁用可移动标志。
        self.is_fixed = True 
        
        flags = QGraphicsItem.ItemIsSelectable
        # if not self.is_fixed: flags |= QGraphicsItem.ItemIsMovable # 已禁用
        
        # 为交换按钮启用悬停事件
        self.setAcceptHoverEvents(True)
            
        self.setFlags(flags)
        
        # 执行状态追踪
        self.execution_status = "pending"  # pending/running/completed/failed
        self.STATUS_COLORS = {
            "pending": QColor("#666666"),
            "running": QColor("#FFC107"),
            "completed": QColor("#4CAF50"),
            "failed": QColor("#F44336")
        }
        
        # 缓存颜色
        self.header_color = QColor()
        self._update_colors()

    def _update_colors(self):
        # 页眉颜色优先级: 线程颜色 > 节点类型颜色
        if self.thread_color:
            self.header_color = self.thread_color
        else:
            ntype = self.node_data.node_type or "default"
            self.header_color = NODE_COLORS.get(ntype, NODE_COLORS["default"])
            
        self.body_color = QColor("#2d2d2d")
        self.text_color = QColor("#ffffff")
        self.subtext_color = QColor("#b0b0b0")

    def boundingRect(self):
        # 扩展边界以包含上下箭头按钮
        # 向上按钮: 延伸到上方 (如果 index > 0)
        # 向下按钮: 延伸到下方 (始终)
        
        top = -2
        bottom = self.height + 2
        
        thread_view_index = self.node_data.thread_view_index
        if thread_view_index > 0:
            # 包含向上按钮区域: 20 按钮 + 4 间距
            top = -28
            
        # 包含向下按钮区域: 20 按钮 + 4 间距
        bottom = self.height + 28
            
        return QRectF(-2, top, self.width + 4, bottom - top)

    def get_output_anchor_center(self) -> QPointF:
        """获取场景坐标中输出锚点的中心点"""
        return self.mapToScene(self.output_anchor_rect.center())
    
    def get_input_point(self) -> QPointF:
        """获取输入连接点 (左侧)"""
        return self.mapToScene(QPointF(0, self.height / 2))

    def paint(self, painter, option, widget):
        # 更新颜色，以防数据发生变化
        self._update_colors()
        
        path = QPainterPath()
        path.addRoundedRect(0, 0, self.width, self.height, 8, 8)
        
        # 边框: 默认黑色，选中时蓝色
        if self.isSelected():
            painter.setPen(QPen(QColor("#4a90e2"), 3))
        else:
            painter.setPen(QPen(QColor("#111111"), 1))
            
        # 填充主体
        painter.setBrush(self.body_color)
        painter.drawPath(path)
        
        # 页眉 (顶部) - 斜体设计
        # 右侧更高
        h_left = 24
        h_right = 38
        
        header_path = QPainterPath()
        header_path.moveTo(0, h_left)
        header_path.lineTo(0, 8)
        header_path.arcTo(0, 0, 16, 16, 180, 90) # 左上角
        header_path.lineTo(self.width - 8, 0)
        header_path.arcTo(self.width - 16, 0, 16, 16, 90, -90) # 右上角
        header_path.lineTo(self.width, h_right)
        header_path.lineTo(0, h_left)
        
        painter.fillPath(header_path, self.header_color)
        
        # 文本 (名称)
        painter.setPen(self.text_color)
        font = QFont("Segoe UI", 10, QFont.Bold)
        painter.setFont(font)
        # 位置根据斜体进行微调
        painter.drawText(QRectF(10, 0, self.width - 20, 30), 
                         Qt.AlignLeft | Qt.AlignVCenter, 
                         self.node_data.node_name or "Node")
        
        # 类型标签 (主体)
        painter.setPen(self.subtext_color)
        font_small = QFont("Segoe UI", 8)
        painter.setFont(font_small)
        type_text = f"Type: {self.node_data.node_type or 'unknown'}"
        
        # 在页眉最低处下方开始绘制类型文本
        text_y_start = max(h_left, h_right) + 8
        painter.drawText(QRectF(10, text_y_start, self.width - 20, 20),
                         Qt.AlignLeft, type_text)
        
        # 绘制 ID 及交换按钮
        node_id = self.node_data.node_id
        thread_id = self.node_data.thread_id or 'main'
        
        # 计算按钮位置
        button_size = 14
        button_y = text_y_start + 15
        
        # 左箭头按钮 (仅当 ID > 1 时显示)
        if isinstance(node_id, int) and node_id > 1:
            self.left_swap_rect = QRectF(10, button_y, button_size, button_size)
            # 绘制按钮背景
            if self.hover_swap_button == 'left':
                painter.setBrush(QColor("#4a90e2"))
            else:
                painter.setBrush(QColor("#3e3e3e"))
            painter.setPen(QPen(QColor("#555555"), 1))
            painter.drawRoundedRect(self.left_swap_rect, 3, 3)
            
            # 绘制左箭头
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
        
        # ID 文本
        id_x_offset = 10 + (button_size + 4 if isinstance(node_id, int) and node_id > 1 else 0)
        id_text = f"ID: {node_id}"
        painter.setPen(self.subtext_color)
        painter.setFont(font_small)
        id_text_rect = QRectF(id_x_offset, button_y, 50, button_size)
        painter.drawText(id_text_rect, Qt.AlignLeft | Qt.AlignVCenter, id_text)
        
        # 右箭头按钮 (始终显示，点击时检查有效性)
        right_button_x = id_x_offset + 52
        self.right_swap_rect = QRectF(right_button_x, button_y, button_size, button_size)
        # 绘制按钮背景
        if self.hover_swap_button == 'right':
            painter.setBrush(QColor("#4a90e2"))
        else:
            painter.setBrush(QColor("#3e3e3e"))
        painter.setPen(QPen(QColor("#555555"), 1))
        painter.drawRoundedRect(self.right_swap_rect, 3, 3)
        
        # 绘制右箭头
        painter.setPen(QPen(QColor("#ffffff"), 2))
        arrow_center_x = self.right_swap_rect.center().x()
        arrow_center_y = self.right_swap_rect.center().y()
        painter.drawLine(int(arrow_center_x - 2), int(arrow_center_y),
                       int(arrow_center_x + 2), int(arrow_center_y))
        painter.drawLine(int(arrow_center_x + 2), int(arrow_center_y),
                       int(arrow_center_x), int(arrow_center_y - 3))
        painter.drawLine(int(arrow_center_x + 2), int(arrow_center_y),
                       int(arrow_center_x), int(arrow_center_y + 3))
        
        # 线程 ID 文本 (按钮之后)
        thread_x_offset = right_button_x + button_size + 4
        # 计算线程按钮区域，以防重叠
        thread_button_size = 20  # 从 14 增大以获得更好的可见性
        thread_button_x = self.width - 56  # 为更大的按钮调整位置
        # 限制线程 ID 文本，使其不与按钮重叠
        thread_text_width = thread_button_x - thread_x_offset - 4  # 在按钮前留出 4px 间隙
        painter.setPen(self.subtext_color)
        painter.drawText(QRectF(thread_x_offset, button_y, max(thread_text_width, 50), button_size),
                         Qt.AlignLeft | Qt.AlignVCenter, f"| {thread_id}")
        
        # 绘制线程交换按钮
        # 向上按钮: 位于节点上方 (负 Y)
        # 向下按钮: 位于节点下方下方
        
        # 向上按钮 (仅在 thread_view_index > 0 时显示，表示不是最顶层的线程)
        thread_view_index = self.node_data.thread_view_index
        if thread_view_index > 0:
            # 将向上按钮放置在节点上方 (在节点边界之外)
            up_button_y = -thread_button_size - 4  # 节点上方 4px 间隙
            up_button_x = self.width / 2 - thread_button_size / 2  # 水平居中
            self.up_thread_rect = QRectF(up_button_x, up_button_y, thread_button_size, thread_button_size)
            # 使用更明显的颜色绘制按钮背景
            if self.hover_swap_button == 'up':
                painter.setBrush(QColor("#5a9fd4"))
            else:
                painter.setBrush(QColor("#4a7ba7"))  # 更明显的蓝灰色
            painter.setPen(QPen(QColor("#6ab7ff"), 2))  # 更亮的边框
            painter.drawRoundedRect(self.up_thread_rect, 4, 4)
            
            # 绘制向上箭头 - 更大且更明显
            painter.setPen(QPen(QColor("#ffffff"), 3))  # 更粗的笔
            arrow_center_x = self.up_thread_rect.center().x()
            arrow_center_y = self.up_thread_rect.center().y()
            # 垂直线 (更长)
            painter.drawLine(int(arrow_center_x), int(arrow_center_y + 4),
                           int(arrow_center_x), int(arrow_center_y - 4))
            # 箭头头部 (更宽)
            painter.drawLine(int(arrow_center_x), int(arrow_center_y - 4),
                           int(arrow_center_x - 5), int(arrow_center_y + 1))
            painter.drawLine(int(arrow_center_x), int(arrow_center_y - 4),
                           int(arrow_center_x + 5), int(arrow_center_y + 1))
        else:
            self.up_thread_rect = QRectF(0, 0, 0, 0)
        
        # 向下按钮 (始终显示，点击时检查有效性)
        # 将向下按钮放置在节点底部中央 (在节点边界之外)
        down_button_y = self.height + 4  # 底部 4px 间隙
        down_button_x = self.width / 2 - thread_button_size / 2  # 水平居中
        self.down_thread_rect = QRectF(down_button_x, down_button_y, thread_button_size, thread_button_size)
        
        # 使用更明显的颜色绘制按钮背景
        if self.hover_swap_button == 'down':
            painter.setBrush(QColor("#5a9fd4"))
        else:
            painter.setBrush(QColor("#4a7ba7"))  # 更明显的蓝灰色
        painter.setPen(QPen(QColor("#6ab7ff"), 2))  # 更亮的边框
        painter.drawRoundedRect(self.down_thread_rect, 4, 4)
        
        # 绘制向下箭头 - 更大且更明显
        painter.setPen(QPen(QColor("#ffffff"), 3))  # 更粗的笔
        arrow_center_x = self.down_thread_rect.center().x()
        arrow_center_y = self.down_thread_rect.center().y()
        # 垂直线 (更长)
        painter.drawLine(int(arrow_center_x), int(arrow_center_y - 4),
                       int(arrow_center_x), int(arrow_center_y + 4))
        # 箭头头部 (更宽)
        painter.drawLine(int(arrow_center_x), int(arrow_center_y + 4),
                       int(arrow_center_x - 5), int(arrow_center_y - 1))
        painter.drawLine(int(arrow_center_x), int(arrow_center_y + 4),
                       int(arrow_center_x + 5), int(arrow_center_y - 1))
        
        # 绘制输出锚点 (绿色圆圈)
        painter.setBrush(QColor("#4CAF50"))
        painter.setPen(QPen(QColor("#2E7D32"), 1))
        painter.drawEllipse(self.output_anchor_rect)
        
        # 绘制执行状态指示器 (右上角)
        if self.execution_status != "pending":
            status_color = self.STATUS_COLORS.get(self.execution_status, QColor("#666666"))
            status_size = 12
            status_x = self.width - status_size - 4
            status_y = 4
            painter.setBrush(status_color)
            painter.setPen(QPen(status_color.darker(120), 1))
            painter.drawEllipse(int(status_x), int(status_y), status_size, status_size)
            
            # 在状态指示器内绘制图标
            painter.setPen(QPen(QColor("#ffffff"), 2))
            center_x = status_x + status_size / 2
            center_y = status_y + status_size / 2
            
            if self.execution_status == "completed":
                # 绘制勾选标记
                painter.drawLine(int(center_x - 3), int(center_y), int(center_x - 1), int(center_y + 2))
                painter.drawLine(int(center_x - 1), int(center_y + 2), int(center_x + 3), int(center_y - 2))
            elif self.execution_status == "running":
                # 绘制圆点
                painter.setBrush(QColor("#ffffff"))
                painter.drawEllipse(int(center_x - 2), int(center_y - 2), 4, 4)
            elif self.execution_status == "failed":
                # 绘制 X
                painter.drawLine(int(center_x - 2), int(center_y - 2), int(center_x + 2), int(center_y + 2))
                painter.drawLine(int(center_x + 2), int(center_y - 2), int(center_x - 2), int(center_y + 2))


    def mouseDoubleClickEvent(self, event):
        super().mouseDoubleClickEvent(event)
    
    def hoverMoveEvent(self, event):
        """追踪交换按钮上的悬停状态"""
        local_pos = event.pos()
        
        old_hover = self.hover_swap_button
        

        
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
        
        # 如果悬停状态改变，则重绘
        if old_hover != self.hover_swap_button:

            self.update()
        
        super().hoverMoveEvent(event)
    
    def hoverLeaveEvent(self, event):
        """当鼠标离开时清除悬停状态"""
        if self.hover_swap_button is not None:
            self.hover_swap_button = None
            self.update()
        super().hoverLeaveEvent(event)
    
    def set_execution_status(self, status: str):
        """设置执行状态并触发重绘"""
        if status in self.STATUS_COLORS:
            self.execution_status = status
            self.update()  # 触发重绘


class ConnectionLine(QGraphicsPathItem):
    """
    节点间的连接线。
    
    类型:
    - thread: 同一线程的顺序连接 (实线)
    - data_in: 数据输入连接 (虚线)
    - data_out: 向合并节点的数据输出 (虚线)
    """
    def __init__(self, start_item, end_item, connection_type="thread", color=None):
        super().__init__()
        self.start_item = start_item
        self.end_item = end_item
        self.connection_type = connection_type
        self.line_color = color or QColor("#666666")
        
        self._update_path()
        self._update_style()
        self.setZValue(-1)  # 位于节点后方
    
    def _update_style(self):
        if self.connection_type == "thread":
            pen = QPen(self.line_color, 2, Qt.SolidLine)
        else:  # data_in 或 data_out
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
        
        # 使用贝塞尔曲线实现平滑连接
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
    合并节点 (+) - 虚拟显示节点，显示子线程数据合并到父线程的位置。
    这不是一个真实的节点，仅作为一个视觉指示器。
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
        """获取输入连接点"""
        return self.mapToScene(QPointF(0, self.size / 2))
    
    def get_output_point(self) -> QPointF:
        """获取输出连接点"""
        return self.mapToScene(QPointF(self.size, self.size / 2))
    
    def paint(self, painter, option, widget):
        # 绘制圆形背景
        painter.setBrush(self.color)
        painter.setPen(QPen(self.color.darker(120), 2))
        painter.drawEllipse(0, 0, self.size, self.size)
        
        # 绘制 + 号
        painter.setPen(QPen(QColor("#ffffff"), 3))
        center = self.size / 2
        margin = 8
        painter.drawLine(int(center), int(margin), int(center), int(self.size - margin))
        painter.drawLine(int(margin), int(center), int(self.size - margin), int(center))
        
        # 在下方绘制标签
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
        # 填充背景
        painter.fillRect(rect, QColor("#1e1e1e"))
        
        # 绘制网格
        left = int(rect.left()) - (int(rect.left()) % self.grid_size)
        top = int(rect.top()) - (int(rect.top()) % self.grid_size)
        
        lines = []
        # 垂直线
        for x in range(left, int(rect.right()), self.grid_size):
            lines.append(QGraphicsLineItem(x, rect.top(), x, rect.bottom()).line())
        # 水平线
        for y in range(top, int(rect.bottom()), self.grid_size):
            lines.append(QGraphicsLineItem(rect.left(), y, rect.right(), y).line())
            
        painter.setPen(QPen(self.grid_color, 1))
        painter.drawLines(lines)

class NodeGraphView(QGraphicsView):
    nodeSelected = pyqtSignal(NodeProperties)  # 选中节点时发送节点数据
    patternListChanged = pyqtSignal(list)  # 加载文件后发送 pattern 名称列表
    currentPatternChanged = pyqtSignal(str, object)  # 切换 pattern 时发送 (pattern_name, plan)

    def __init__(self):
        super().__init__()
        self.scene = NodeGraphScene()
        self.setScene(self.scene)
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        self.next_node_id = 1
        self.node_gap_x = 220
        
        # 线程颜色管理
        self.thread_color_map = {}  # thread_id -> QColor
        
        # 拖拽连接状态
        self.dragging_connection = False
        self.drag_start_item = None
        self.drag_temp_line = None
        
        # 线程视图索引管理
        self.thread_view_indices = {}  # thread_id -> index (int)
        
        # === 多 Pattern 数据存储 ===
        self.all_plans: Dict[str, GuiExecutionPlan] = {}  # pattern_name -> GuiExecutionPlan
        self.current_pattern: str = ""  # 当前显示的 pattern 名称
        self.current_file_path: Optional[str] = None  # 当前加载的文件路径
        
        # 主线程基准线
        self.main_y_baseline = 200
        
        # 不再硬编码初始节点，由 load_from_file 或手动添加
        # 将视图中心对准左下角区域
        self.center_to_bottom_left()
        
        # 添加覆盖按钮
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
        
        # 为按钮添加阴影
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(15)
        shadow.setColor(QColor(0, 0, 0, 100))
        shadow.setOffset(0, 4)
        self.add_btn.setGraphicsEffect(shadow)
    
    def center_to_bottom_left(self):
        """居中视图，使第一个节点显示在屏幕左下角"""
        # 获取可见视口大小
        viewport_rect = self.viewport().rect()
        viewport_width = viewport_rect.width()
        viewport_height = viewport_rect.height()
        
        # 计算偏移量，将节点 (位于 0, main_y_baseline) 定位在视口的左下角
        # 我们希望节点在距离边缘一定间距的位置显示
        margin_x = 150  # 距离左边缘的水平间距
        margin_y = 150  # 距离底边缘的垂直间距
        
        # 中心点计算: 我们希望节点 (0, main_y_baseline) 显示在
        # 视口坐标的 (margin_x, viewport_height - margin_y) 位置
        # 因此视图中心应位于:
        center_x = 0 + (viewport_width / 2 - margin_x)
        center_y = self.main_y_baseline + (viewport_height / 2 - margin_y)
        
        self.centerOn(-center_x + margin_x, center_y - margin_y)

    def get_thread_color(self, thread_id: str) -> QColor:
        """获取或为 thread_id 创建颜色"""
        if thread_id not in self.thread_color_map:
            idx = len(self.thread_color_map)
            color_hex = THREAD_COLORS[idx % len(THREAD_COLORS)]
            self.thread_color_map[thread_id] = QColor(color_hex)
        return self.thread_color_map[thread_id]
    
    def update_connections(self):
        """基于当前节点重新构建所有连接线"""
        # 清除现有连接
        # 注意：需要检查对象是否仍然有效，因为 scene.clear() 可能已删除底层 C++ 对象
        import sip
        for line in self.scene.connection_lines:
            try:
                if not sip.isdeleted(line):
                    self.scene.removeItem(line)
            except RuntimeError:
                pass  # 对象已被删除，忽略
        self.scene.connection_lines.clear()
        
        for merge in self.scene.merge_nodes:
            try:
                if not sip.isdeleted(merge):
                    self.scene.removeItem(merge)
            except RuntimeError:
                pass  # 对象已被删除，忽略
        self.scene.merge_nodes.clear()
        
        # 策略：全量刷新。先清空场景中所有旧线和合并节点，再根据最新数据模型重建。
        # 这样做能确保 UI 状态与数据模型绝对同步，且大幅简化了处理节点移动、删除、跨线程连接时的判断逻辑。
        
        # 获取所有按 ID 排序的节点
        nodes = [i for i in self.scene.items() if isinstance(i, NodeItem)]
        nodes.sort(key=lambda n: n.node_data.node_id)
        
        # 建立 ID 到节点的查找表
        node_by_id = {n.node_data.node_id: n for n in nodes}
        
        # 将节点按 thread_id 分组
        threads = {}
        for node in nodes:
            tid = node.node_data.thread_id or "main"
            if tid not in threads:
                threads[tid] = []
            threads[tid].append(node)
        
        # 绘制同线程连接 (实线)
        for tid, thread_nodes in threads.items():
            thread_nodes.sort(key=lambda n: n.node_data.node_id)
            color = self.get_thread_color(tid)
            
            for i in range(len(thread_nodes) - 1):
                start_node = thread_nodes[i]
                end_node = thread_nodes[i + 1]
                line = ConnectionLine(start_node, end_node, "thread", color)
                self.scene.addItem(line)
                self.scene.connection_lines.append(line)
        
        # 绘制 data_in 连接 (虚线)
        # 规则：对于每个非 main 线程，找到该线程的第一个节点（最小 ID），
        # 然后从其 data_in_thread 中找到 ID 最接近且小于该节点的源节点，绘制连线
        # print(f"[DEBUG] threads: {list(threads.keys())}")
        for tid, thread_nodes in threads.items():
            if tid == "main":
                continue  # main 线程不需要输入连线
            
            # 找到该线程的第一个节点（最小 ID）
            first_node = min(thread_nodes, key=lambda n: n.node_data.node_id)
            target_id = first_node.node_data.node_id
            
            # 获取源线程 ID
            data_in_thread = first_node.node_data.data_in_thread or "main"
            # print(f"[DEBUG] Thread '{tid}': first_node_id={target_id}, data_in_thread='{data_in_thread}'")
            
            if data_in_thread not in threads:
                # print(f"[DEBUG]   -> SKIP: source thread '{data_in_thread}' not in threads")
                continue  # 源线程不存在，跳过
            
            source_nodes = threads[data_in_thread]
            # 在源线程中找 ID < target_id 的最后一个节点
            valid_sources = [n for n in source_nodes if n.node_data.node_id < target_id]
            # print(f"[DEBUG]   -> valid_sources count: {len(valid_sources)}")
            if valid_sources:
                # 连线起点：源线程中 ID 最接近且小于目标节点的节点
                source_node = max(valid_sources, key=lambda n: n.node_data.node_id)
                # print(f"[DEBUG]   -> Drawing line: Node {source_node.node_data.node_id} -> Node {target_id}")
                line = ConnectionLine(source_node, first_node, "data_in", 
                                     self.get_thread_color(tid))
                self.scene.addItem(line)
                self.scene.connection_lines.append(line)
            # else:
            #     print(f"[DEBUG]   -> SKIP: no valid source nodes found")
        
        # 绘制 data_out 连接 (虚线) 及合并节点
        for node in nodes:
            if node.node_data.data_out:
                parent_tid = node.node_data.data_out_thread or "main"
                child_tid = node.node_data.thread_id or "main"
                
                if parent_tid and parent_tid != child_tid and parent_tid in threads:
                    # 将合并节点放置在合适的 X 位置 (该节点之后)
                    merge_x = node.x() + self.node_gap_x / 2
                    # 父线程上的 Y 位置 (主线程 Y=0)
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
                    
                    # 从节点绘制线到合并节点
                    line = ConnectionLine(node, merge_node, "data_out",
                                         self.get_thread_color(child_tid))
                    self.scene.addItem(line)
                    self.scene.connection_lines.append(line)

    def get_all_nodes_data(self) -> list[NodeProperties]:
        nodes = []
        # 如果需要，按 x 位置排序以维持某种逻辑顺序
        items = [i for i in self.scene.items() if isinstance(i, NodeItem)]
        items.sort(key=lambda item: item.x())
        
        for item in items:
            # 更新 schema 兼容的坐标
            item.node_data.x = int(item.x())
            item.node_data.y = int(item.y())
            nodes.append(item.node_data)
        return nodes

    def clear_nodes(self):
        self.scene.clear()

    def auto_layout_nodes(self, nodes_data):
        self.clear_nodes()
        self.next_node_id = 1
        
        # 用于父/子一致性的 ID 重映射
        old_id_map = {}
        
        # 如果存在，映射现有的线程索引
        for node in nodes_data:
            tid = node.get("thread_id", "main")
            tidx = node.get("thread_view_index")
            if tidx is not None and tid not in self.thread_view_indices:
                self.thread_view_indices[tid] = tidx

        # 第一遍: 分配新 ID 并映射
        for node in nodes_data:
            # 确保 thread_view_index
            tid = node.get("thread_id", "main")
            if tid not in self.thread_view_indices:
                # 分配新索引: max + 1
                current_indices = self.thread_view_indices.values()
                next_idx = max(current_indices) + 1 if current_indices else 0
                self.thread_view_indices[tid] = next_idx
            
            node["thread_view_index"] = self.thread_view_indices[tid]

            old_id = node.get("id")
            new_id = self.next_node_id
            
            node["id"] = new_id
            if old_id is not None:
                old_id_map[old_id] = new_id
            
            # 如果缺失，为现有规划节点自动分配颜色
            if node.get("node_type") == "planning" and "color" not in node:
                # 根据 ID 分配确定但唯一的颜色以保持稳定？
                # 或者仅仅随机？用户说 "不同"。随机也可以，但如果不保存，重新加载时会变。
                # 让我们使用随机，下次保存时会被保存下来。
                node["color"] = QColor.fromHsv(random.randint(0, 359), 200, 200).name()

            self.next_node_id += 1
            
        # 第二遍: 如果存在父指针，则进行更新 (假设键名为 'parent_id')，并添加到场景中
        
        # 重置添加到场景的计数器 (如果我们不提供 force_id，add_node 会递增它，
        # 但这里我们希望信任预计算的 ID，或者如果是传递处理后的数据，就让 add_node 处理)
        # 实际上更简单: 直接顺序调用 add_node。
        
        # 等等，后文的 add_node 逻辑会根据 ID 处理 X。
        # 因此我们只需要尊重保存好的布局中的 Y (如果可用)。
        # 但我们必须将数据中的 ID 重写为基于列表顺序的 1..N 序列。
        
        # 再次重置 ID，使 add_node 从 1 开始，以匹配循环
        self.next_node_id = 1
        
        for node in nodes_data:
            # 如果需要，修复 parent_id
            pid = node.get("parent_id")
            if pid in old_id_map:
                node["parent_id"] = old_id_map[pid]
            
            # 根据 thread_view_index 确定 Y (按要求从上到下)
            # "一个纵坐标只能有一个线程"
            # 用户反馈: "id越大应该是往上的"
            # 在 Qt 中，上方向是相对于基准线的负 Y。
            # 所以我们要减去偏移量。
            
            tidx = node.get("thread_view_index", 0)
            thread_gap_y = 120 # 线程间的垂直间距
            
            y = self.main_y_baseline - (tidx * thread_gap_y)
            
            # 如果存在 _ui_pos，仅覆盖 X (水平拖动了？)
            # 或完全忽略 Y 以强制严格布局。
            if "_ui_pos" in node:
                # node["_ui_pos"][1] = y # 强制 Y 与线程匹配
                pass 
            
            
            # X 在 add_node 中由 ID 决定
            self.add_node(node, 0, y)
        
        # 放置所有节点后绘制连接线
        self.update_connections()
    
    def update_node_color(self, node_data):
        """当节点的 thread_id 改变时更新特定节点的颜色"""
        # 查找匹配数据的节点项
        nodes = [i for i in self.scene.items() if isinstance(i, NodeItem)]
        for node in nodes:
            if node.node_data.node_id == node_data.node_id:
                # 获取新线程颜色
                thread_id = node_data.thread_id
                new_color = self.get_thread_color(thread_id)
                node.thread_color = new_color
                # 强制重绘
                node.update()
                break
        
        # 更新所有连接，因为线程关系可能已改变
        self.update_connections()
    
    def update_node_status(self, node_id: int, status: str):
        """
        通过 ID 更新特定节点的执行状态
        
        参数:
            node_id: 要更新的节点 ID
            status: 'pending', 'running', 'completed', 'failed' 之一
        """
        nodes = [i for i in self.scene.items() if isinstance(i, NodeItem)]
        for node in nodes:
            if node.node_data.node_id == node_id:
                node.set_execution_status(status)
                break

    def add_node(self, node_data: NodeProperties, x, y, force_id=None):
        # 强制 ID
        if force_id is not None:
            node_id = force_id
            # 确保 next_node_id 领先于强制分配的 ID，以防混合使用时发生冲突
            if node_id >= self.next_node_id:
                self.next_node_id = node_id + 1
        else:
            # 检查数据是否已有 ID (例如从文件加载但未通过 arg 强制)
            # 但要求说 "如果读取，则按照读取顺序"。
            # 所以我们通常只是根据当前计数器覆盖/分配。
            node_id = self.next_node_id
            self.next_node_id += 1
        
        node_data.node_id = node_id
        
        # 确保 thread_id 存在
        if "thread_id" not in node_data:
            node_data.thread_id = "main"
            
        # 确保 thread_view_index 存在
        tid = node_data.thread_id

        if "thread_view_index" not in node_data:
            if tid in self.thread_view_indices:
                node_data.thread_view_index = self.thread_view_indices[tid]
            else:
                # 新线程动态分配
                # 警告: 除非确实是一个新线程，否则添加简单节点通常不应创建新的线程索引。
                # 如果是以前没见过的 thread_id，则分配下一个索引。
                current_indices = self.thread_view_indices.values()
                next_idx = max(current_indices) + 1 if current_indices else 0
                self.thread_view_indices[tid] = next_idx
                node_data.thread_view_index = next_idx

        else:
             # 如果管理器中不存在，则同步回去
             if tid not in self.thread_view_indices:
                 self.thread_view_indices[tid] = node_data.thread_view_index


        # 基于 ID 强制 X 坐标
        # ID 1 -> 0
        # ID 2 -> GAP
        # ...
        calculated_x = (node_id - 1) * self.node_gap_x
        
        # 基于 thread_view_index 强制 Y 坐标
        thread_gap_y = 120
        tidx = node_data.thread_view_index
        # 索引大 = 更靠上 = Y 值更小
        calculated_y = self.main_y_baseline - (tidx * thread_gap_y)
        
        # 直接修改 node_data 的坐标
        node_data.x = calculated_x
        node_data.y = calculated_y
        
        # 获取线程颜色
        thread_color = self.get_thread_color(node_data.thread_id)
        
        # 创建节点项，坐标从 node_data 中读取
        item = NodeItem(node_data, thread_color=thread_color)
        self.scene.addItem(item)
    
    def wheelEvent(self, event: QWheelEvent):
        # 缩放
        zoomInFactor = 1.1
        zoomOutFactor = 1 / zoomInFactor
        if event.angleDelta().y() > 0:
            zoomFactor = zoomInFactor
        else:
            zoomFactor = zoomOutFactor
        self.scale(zoomFactor, zoomFactor)

    def mousePressEvent(self, event):
        item = self.itemAt(event.pos())
        
        # 检查是否点击了 NodeItem 的交换按钮或输出锚点
        if isinstance(item, NodeItem):
            local_pos = item.mapFromScene(self.mapToScene(event.pos()))
            
            # 首先检查交换按钮 (优先级高于锚点)
            if item.left_swap_rect.contains(local_pos):
                # 与左侧邻居交换
                self.swap_nodes(item, -1)
                return
            elif item.right_swap_rect.contains(local_pos):
                # 与右侧邻居交换
                self.swap_nodes(item, 1)
                return
            elif item.up_thread_rect.contains(local_pos):
                # 线程上移
                self.swap_threads(item, -1)
                return
            elif item.down_thread_rect.contains(local_pos):
                # 线程下移
                self.swap_threads(item, 1)
                return
            elif item.output_anchor_rect.contains(local_pos):
                # 开始拖拽连接线
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
            # 隐藏临时线以找到底部的实际项
            if self.drag_temp_line:
                self.drag_temp_line.hide()
            
            # 在释放位置寻找目标节点
            scene_pos = self.mapToScene(event.pos())
            items_at_pos = self.scene.items(scene_pos)
            target = None
            for item in items_at_pos:
                if isinstance(item, NodeItem) and item != self.drag_start_item:
                    target = item
                    break
            
            if target:
                # 校验: source.id < target.id
                source_id = self.drag_start_item.node_data.node_id
                target_id = target.node_data.node_id
                
                if source_id < target_id:
                    # 创建 data_in 连接
                    source_thread = self.drag_start_item.node_data.thread_id
                    target.node_data.data_in_thread = source_thread
                    target.node_data.data_in_slice = (0, 1)  # 默认: 第一条消息 [0:1]
                    print(f"Created connection: {source_thread} -> Node {target_id}")
                    self.update_connections()
                else:
                    print(f"Invalid connection: source ID ({source_id}) must be < target ID ({target_id})")
            
            # 清理拖拽状态
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
        # 扩展: 同一 Y 层级，同一线程
        new_y = parent_item.y()
        parent_thread = parent_item.node_data.thread_id
        
        new_data = {
            "node_name": "New Node", 
            "node_type": "llm-first", 
            "thread_id": parent_thread,
            "task_prompt": "",
            "parent_id": parent_item.node_data.node_id
        }
        self.add_node(new_data, 0, new_y)
        self.update_connections()

    def add_branch_from(self, parent_item):
        # 分支: 向上放置 (在 Qt 中为负 Y)
        new_y = parent_item.y() - 120
        parent_thread = parent_item.node_data.thread_id
        
        # 为分支创建新的线程 ID
        new_thread_id = f"branch_{self.next_node_id}"

        # 使用下一个可用索引
        current_indices = self.thread_view_indices.values()
        next_idx = max(current_indices) + 1 if current_indices else 1 # 0 是 main 线程
        
        # 注册新线程
        self.thread_view_indices[new_thread_id] = next_idx
        
        new_data = {
            "node_name": "Branch", 
            "node_type": "llm-first",
            "thread_id": new_thread_id,
            "parent_thread_id": parent_thread,
            "task_prompt": "",
            "parent_id": parent_item.node_data.node_id,
            "thread_view_index": next_idx
        }

        # Y 将在 add_node 中计算
        self.add_node(new_data, 0, 0)
        self.update_connections()

    def delete_node(self, item):
        deleted_id = item.node_data.node_id
        self.scene.removeItem(item)
        
        # 重新对 ID > deleted_id 的所有节点进行编号
        nodes = [i for i in self.scene.items() if isinstance(i, NodeItem)]
        for node in nodes:
            node_id = node.node_data.node_id
            if node_id > deleted_id:
                new_id = node_id - 1
                node.node_data.node_id = new_id
                # 根据新 ID 重新计算 X 位置
                node.setPos((new_id - 1) * self.node_gap_x, node.y())
        
        # 递减 next_node_id 计数器
        self.next_node_id = max(1, self.next_node_id - 1)
        
        self.update_connections()
    
    def delete_thread(self, item):
        """
        删除该节点所属的整个线程。
        应用特定的偏移逻辑: '其他小于其线程坐标 ID 的 ID + 1'
        """
        thread_id = item.node_data.thread_id
        if thread_id == "main":
            print("Cannot delete main thread yet")
            return
            
        deleted_idx = self.thread_view_indices.get(thread_id)
        if deleted_idx is None:
            return
            
        # 1. 移除该线程的所有节点
        nodes_to_remove = []
        for i in self.scene.items():
            if isinstance(i, NodeItem) and i.node_data.thread_id == thread_id:
                nodes_to_remove.append(i)
        
        for node in nodes_to_remove:
            self.scene.removeItem(node)
            
        # 2. 更新索引
        # 规则: "删除该线程的所有 ID，其他小于其线程坐标 ID 的 ID + 1"
        del self.thread_view_indices[thread_id]
        
        for tid, idx in self.thread_view_indices.items():
            if idx < deleted_idx:
                self.thread_view_indices[tid] = idx + 1
        
        # 3. 更新所有剩余节点的位置
        remaining_nodes = [i for i in self.scene.items() if isinstance(i, NodeItem)]
        for node in remaining_nodes:
            tid = node.node_data.thread_id
            if tid in self.thread_view_indices:
                new_idx = self.thread_view_indices[tid]
                node.node_data.thread_view_index= new_idx
                # 重新计算 Y (索引越大 = 越靠上 = 负偏移)
                node.setPos(node.x(), self.main_y_baseline - (new_idx * 120))
        
        self.update_connections()

    def swap_nodes(self, item, direction):
        """
        与邻居交换节点。
        
        参数:
            item: 要交换的 NodeItem
            direction: -1 代表向左交换, 1 代表向右交换
        """
        current_id = item.node_data.node_id
        target_id = current_id + direction
        
        # 保护 ID=1 的节点 - 它不能被交换
        if current_id == 1:
            print("Cannot swap: Node ID 1 (main) is protected and cannot be swapped")
            return
        
        # 不能与 ID=1 的节点交换
        if target_id == 1:
            print("Cannot swap: Cannot swap with Node ID 1 (main) - it is protected")
            return
        
        # 验证目标 ID
        if target_id < 1:
            print(f"Cannot swap: target ID {target_id} is invalid (must be >= 1)")
            return
        
        # 获取所有节点
        nodes = [i for i in self.scene.items() if isinstance(i, NodeItem)]
        
        # 查找目标节点
        target_node = None
        for node in nodes:
            if node.node_data.node_id == target_id:
                target_node = node
                break
        
        if not target_node:
            print(f"Cannot swap: no node found with ID {target_id}")
            return
        
        # 交换 ID
        item.node_data.node_id = target_id
        target_node.node_data.node_id = current_id
        
        # 根据新 ID 重新计算位置
        item.setPos((target_id - 1) * self.node_gap_x, item.y())
        target_node.setPos((current_id - 1) * self.node_gap_x, target_node.y())
        
        # 强制重绘
        item.update()
        target_node.update()
        
        # 更新所有连接
        self.update_connections()
        
        print(f"Swapped nodes: {current_id} ↔ {target_id}")

    def swap_threads(self, item, direction):
        """
        与相邻线程交换线程位置。
        
        参数:
            item: 线程应被移动的 NodeItem
            direction: -1 代表向上 (线程上移), 1 代表向下 (线程下移)
        """
        current_thread_id = item.node_data.thread_id
        current_thread_index = item.node_data.thread_view_index
        target_thread_index = current_thread_index + direction
        
        # 验证目标索引
        if target_thread_index < 0:
            print(f"Cannot move thread: target index {target_thread_index} is invalid (must be >= 0)")
            return
        
        # 查找目标线程 (具有 target_thread_index 的线程)
        target_thread_id = None
        for tid, idx in self.thread_view_indices.items():
            if idx == target_thread_index:
                target_thread_id = tid
                break
        
        if not target_thread_id:
            print(f"Cannot move thread: no thread found with index {target_thread_index}")
            return
        
        # 交换 thread_view_indices
        self.thread_view_indices[current_thread_id] = target_thread_index
        self.thread_view_indices[target_thread_id] = current_thread_index
        
        # 获取所有节点
        nodes = [i for i in self.scene.items() if isinstance(i, NodeItem)]
        
        # 更新两个线程中的所有节点
        thread_gap_y = 120
        for node in nodes:
            node_thread_id = node.node_data.thread_id
            if node_thread_id == current_thread_id:
                # 为当前线程中的所有节点更新 thread_view_index
                node.node_data.thread_view_index = target_thread_index
                # 重新计算 Y 位置轮廓
                new_y = self.main_y_baseline - (target_thread_index * thread_gap_y)
                node.setPos(node.x(), new_y)

                node.update()
            elif node_thread_id == target_thread_id:
                # 为目标线程中的所有节点更新 thread_view_index轮廓
                node.node_data.thread_view_index = current_thread_index
                # 重新计算 Y 位置轮廓
                new_y = self.main_y_baseline - (current_thread_index * thread_gap_y)
                node.setPos(node.x(), new_y)

                node.update()
        
        # 更新所有连接线轮廓
        self.update_connections()
        
        print(f"Swapped threads: {current_thread_id} (index {current_thread_index}) ↔ {target_thread_id} (index {target_thread_index})")

    def add_node_at_center(self):
        # 始终将其添加到 main_y_baseline 的主轴上轮廓
        new_data = {
            "node_name": "New Node", 
            "node_type": "llm-first", 
            "task_prompt": ""
        }
        self.add_node(new_data, 0, self.main_y_baseline)

    # ==================== 多 Pattern 数据管理 ====================
    
    def load_from_file(self, file_path: str) -> List[str]:
        """
        从文件加载所有 patterns
        
        参数:
            file_path: JSON 文件路径
            
        返回:
            pattern 名称列表（用于填充 ComboBox）
        """
        from llm_linear_executor.os_plan import load_plans_from_templates
        
        self.all_plans = load_plans_from_templates(file_path, schema=GuiExecutionPlan)
        self.current_file_path = file_path
        patterns = list(self.all_plans.keys())
        
        # 自动加载第一个 pattern
        if patterns:
            self._load_plan_to_scene(self.all_plans[patterns[0]])
            self.current_pattern = patterns[0]
        
        # 发送信号通知 pattern 列表已更新
        self.patternListChanged.emit(patterns)
        return patterns
    
    def switch_pattern(self, pattern_name: str) -> bool:
        """
        切换到指定的 pattern
        会先保存当前 pattern 的修改
        
        参数:
            pattern_name: 要切换到的 pattern 名称
            
        返回:
            是否切换成功
        """
        if pattern_name not in self.all_plans:
            print(f"Warning: Pattern '{pattern_name}' not found")
            return False
        
        if pattern_name == self.current_pattern:
            return True  # 已经是当前 pattern，无需操作
        
        # 1. 保存当前 pattern 的最新数据
        self._save_current_to_plans()
        
        # 2. 切换到新 pattern
        self.current_pattern = pattern_name
        plan = self.all_plans[pattern_name]
        self._load_plan_to_scene(plan)
        
        # 3. 发送信号
        self.currentPatternChanged.emit(pattern_name, plan)
        return True
    
    def _save_current_to_plans(self):
        """将当前场景中的节点数据保存回 all_plans"""
        if self.current_pattern and self.current_pattern in self.all_plans:
            nodes = self.get_all_nodes_data()
            self.all_plans[self.current_pattern].nodes = nodes
            # 同步 thread_view_indices
            self.all_plans[self.current_pattern].thread_view_indices = self.thread_view_indices.copy()
    
    def _load_plan_to_scene(self, plan: GuiExecutionPlan):
        """
        将 plan 中的节点加载到场景中
        
        直接使用 plan 中预计算好的坐标，不重新计算布局
        """
        # 清空场景（保留按钮等 UI 元素）
        self.clear_nodes()
        
        # 重置颜色映射
        self.thread_color_map.clear()
        
        # 同步 thread_view_indices
        self.thread_view_indices = plan.thread_view_indices.copy()
        
        # 创建节点
        for node in plan.nodes:
            thread_color = self.get_thread_color(node.thread_id)
            item = NodeItem(node, thread_color=thread_color)
            self.scene.addItem(item)
        
        # 更新 next_node_id 为 max + 1
        if plan.nodes:
            self.next_node_id = max(n.node_id for n in plan.nodes) + 1
        else:
            self.next_node_id = 1
        
        # 更新连接线
        self.update_connections()
        
        # 居中视图到第一个节点
        self.center_to_bottom_left()
    
    def get_current_plan(self) -> Optional[GuiExecutionPlan]:
        """
        获取当前 pattern 的 plan（包含最新修改）
        
        返回:
            当前的 GuiExecutionPlan，如果没有则返回 None
        """
        self._save_current_to_plans()
        return self.all_plans.get(self.current_pattern)
    
    def get_all_plans(self) -> Dict[str, GuiExecutionPlan]:
        """
        获取所有 plans（包含当前 pattern 的最新修改）
        
        返回:
            pattern_name -> GuiExecutionPlan 的字典
        """
        self._save_current_to_plans()
        return self.all_plans
    
    def save_to_file(self, file_path: Optional[str] = None) -> bool:
        """
        保存所有 plans 到文件
        
        参数:
            file_path: 保存路径，如果为 None 则使用原加载路径
            
        返回:
            是否保存成功
        """
        path = file_path or self.current_file_path
        if not path:
            print("Error: No file path specified for saving")
            return False
        
        # 确保当前 pattern 的数据已更新
        self._save_current_to_plans()
        
        try:
            # 构建保存格式：将所有 plans 合并到一个 JSON 中
            # 格式: {"patterns": {"pattern1": {...}, "pattern2": {...}}}
            all_data = {}
            for pattern_name, plan in self.all_plans.items():
                all_data[pattern_name] = plan.model_dump(exclude_none=True)
            
            output = {"patterns": all_data}
            
            with open(path, "w", encoding="utf-8") as f:
                json.dump(output, f, indent=2, ensure_ascii=False)
            
            self.current_file_path = path
            print(f"Saved {len(self.all_plans)} patterns to {path}")
            return True
        except Exception as e:
            print(f"Error saving to file: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def update_current_task(self, task: str):
        """
        更新当前 pattern 的 task
        
        参数:
            task: 新的 task 内容
        """
        if self.current_pattern and self.current_pattern in self.all_plans:
            self.all_plans[self.current_pattern].task = task
    
    def get_current_task(self) -> str:
        """
        获取当前 pattern 的 task
        
        返回:
            task 字符串，如果没有则返回空字符串
        """
        if self.current_pattern and self.current_pattern in self.all_plans:
            return self.all_plans[self.current_pattern].task or ""
        return ""


