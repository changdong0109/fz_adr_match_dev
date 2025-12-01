"""
禁用滚轮的下拉框组件
避免用户在滚动页面时意外修改下拉框的选项
"""

from qgis.PyQt.QtWidgets import QComboBox
from qgis.PyQt.QtGui import QWheelEvent


class NoWheelComboBox(QComboBox):
    """禁用滚轮的下拉框"""
    
    def wheelEvent(self, event: QWheelEvent):
        """忽略滚轮事件，防止意外修改"""
        event.ignore()

