"""
可折叠分组容器 - 使用 QTreeWidget 实现专业的折叠交互
Collapsible Section Widget using QTreeWidget as the base.

这是比 QGroupBox.checkable 更专业的实现方式，提供：
  1. 原生的树形展开/折叠箭头
  2. 自动管理状态，无需手动信号连接
  3. 更清晰的视觉反馈
  4. 支持嵌套（如需）
"""

try:
    from qgis.PyQt.QtWidgets import (
        QTreeWidget, QTreeWidgetItem, QWidget, QVBoxLayout,
        QHeaderView
    )
    from qgis.PyQt.QtCore import Qt
    QGIS_AVAILABLE = True
except ImportError:
    QGIS_AVAILABLE = False


class CollapsibleSection(QWidget):
    """
    可折叠分组容器 - 基于 QTreeWidget 实现
    
    使用方式：
        section = CollapsibleSection("数据上传与清洗", expanded=True)
        section.add_content_widget(your_widget)
        layout.addWidget(section)
    """

    def __init__(self, title: str, expanded: bool = True, parent=None):
        """
        初始化可折叠分组
        
        Args:
            title: 分组标题
            expanded: 是否默认展开
            parent: 父组件
        """
        super().__init__(parent)
        self.title = title
        self.expanded = expanded
        self._content_widget = None
        
        # 创建树形控件（但不显示树形结构）
        self.tree = QTreeWidget()
        self.tree.setStyleSheet("""
            QTreeWidget {
                border: 1px solid #cccccc;
                border-radius: 4px;
                background-color: #ffffff;
            }
            QTreeWidget::item {
                padding: 8px;
                border: none;
            }
            QTreeWidget::item:hover {
                background-color: #f5f5f5;
            }
        """)
        
        # 隐藏列头和垂直滚动条
        self.tree.setHeaderHidden(True)
        self.tree.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.tree.setIndentation(0)  # 不缩进
        
        # 创建根项（标题行）
        self.root_item = QTreeWidgetItem(self.tree)
        self.root_item.setText(0, title)
        self.root_item.setFlags(
            self.root_item.flags() | Qt.ItemIsExpanded
        )
        
        # 创建内容项（容纳真实内容）
        self.content_item = QTreeWidgetItem(self.root_item)
        self.content_item.setFlags(
            self.content_item.flags() & ~Qt.ItemIsSelectable
        )
        
        # 设置默认展开状态
        self.tree.setItemExpanded(self.root_item, expanded)
        
        # 布局
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.tree)
        self.setLayout(layout)

    def add_content_widget(self, widget: QWidget):
        """
        添加内容组件到可折叠分组
        
        Args:
            widget: 要添加的 QWidget
        """
        self._content_widget = widget
        self.tree.setItemWidget(self.content_item, 0, widget)
        # 调整树形项高度以适应内容
        self.tree.resizeColumnToContents(0)

    def is_expanded(self) -> bool:
        """获取当前展开状态"""
        return self.tree.isItemExpanded(self.root_item)

    def set_expanded(self, expanded: bool):
        """设置展开/折叠状态"""
        self.tree.setItemExpanded(self.root_item, expanded)

    def get_content_widget(self) -> QWidget:
        """获取内容组件"""
        return self._content_widget
