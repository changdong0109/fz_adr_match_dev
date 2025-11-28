"""
可折叠部分组件 - 基于 QTreeWidget 的专业折叠实现

使用 QTreeWidget 提供原生的展开/折叠交互：
  - 三角形箭头指示器（自动方向切换）
  - 无需复选框，更专业
  - 平滑的交互体验
  - 轻量级，性能好

使用示例：
    section = CollapsibleSection("部分标题")
    section.add_widget(your_widget)
    layout.addWidget(section)
"""

try:
    from qgis.PyQt.QtWidgets import (
        QTreeWidget, QTreeWidgetItem, QWidget, QVBoxLayout, QHeaderView
    )
    from qgis.PyQt.QtCore import Qt
    QGIS_AVAILABLE = True
except ImportError:
    QGIS_AVAILABLE = False


class CollapsibleSection(QTreeWidget):
    """
    可折叠的部分容器 - 基于 QTreeWidget 的专业实现
    
    提供一个单一的折叠项，用户点击三角形箭头即可展开/折叠。
    内部通过 add_widget() 添加的 widget 会显示在树项下方。
    """

    def __init__(self, title: str, expanded: bool = True, parent=None):
        """
        初始化可折叠部分
        
        Args:
            title: 部分的标题文本
            expanded: 初始是否展开（默认展开）
            parent: 父 widget
        """
        super().__init__(parent)
        self.setColumnCount(1)
        self.setHeaderHidden(True)
        self.setRootIsDecorated(True)
        self.setAnimated(True)
        self.setIndentation(0)
        
        # 隐藏滚动条和边框以获得更清洁的外观
        self.setStyleSheet("""
            QTreeWidget {
                border: none;
                background-color: transparent;
            }
            QTreeWidget::item {
                padding: 4px;
                border: none;
            }
            QTreeWidget::item:hover {
                background-color: #f5f5f5;
            }
        """)
        
        # 创建根项（标题）
        self.root_item = QTreeWidgetItem(self)
        self.root_item.setText(0, title)
        self.root_item.setExpanded(expanded)
        
        # 创建容器项 - 用来放置用户的 widget
        self.container_item = QTreeWidgetItem(self.root_item)
        self.container_item.setText(0, "")
        # 注意：container_item 本身是不可见的，因为我们用 setItemWidget 来显示内容
        
        # 存储用户添加的 widget
        self._user_widget = None

    def add_widget(self, widget: QWidget):
        """
        向可折叠部分添加 widget
        
        Args:
            widget: 要添加的 QWidget
        """
        self._user_widget = widget
        # 使用 setItemWidget 将 widget 绑定到容器项
        self.setItemWidget(self.container_item, 0, widget)

    def add_content_widget(self, widget: QWidget):
        """
        向可折叠部分添加内容 widget（add_widget 的别名）
        
        Args:
            widget: 要添加的 QWidget
        """
        self.add_widget(widget)

    def set_expanded(self, expanded: bool):
        """
        设置展开/折叠状态
        
        Args:
            expanded: True 为展开，False 为折叠
        """
        self.root_item.setExpanded(expanded)

    def is_expanded(self) -> bool:
        """
        获取当前展开状态
        
        Returns:
            bool: True 表示已展开，False 表示已折叠
        """
        return self.root_item.isExpanded()

    def set_title(self, title: str):
        """
        设置部分标题
        
        Args:
            title: 新标题文本
        """
        self.root_item.setText(0, title)

    def get_title(self) -> str:
        """
        获取部分标题
        
        Returns:
            str: 当前标题
        """
        return self.root_item.text(0)
