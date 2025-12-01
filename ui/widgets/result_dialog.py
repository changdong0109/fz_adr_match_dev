"""
通用结果弹窗组件
用于显示操作结果（成功/失败/警告/信息）
"""
from typing import Optional
from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QWidget
)
from qgis.PyQt.QtCore import Qt


class ResultDialog(QDialog):
    """
    通用结果弹窗
    
    用法:
        # 成功弹窗
        ResultDialog.show_success(parent, "操作成功", "数据已保存")
        
        # 失败弹窗
        ResultDialog.show_error(parent, "操作失败", "文件不存在")
        
        # 警告弹窗
        ResultDialog.show_warning(parent, "注意", "部分数据未处理")
        
        # 信息弹窗
        ResultDialog.show_info(parent, "提示", "请先配置参数")
    """
    
    # 弹窗类型
    TYPE_SUCCESS = "success"
    TYPE_ERROR = "error"
    TYPE_WARNING = "warning"
    TYPE_INFO = "info"
    
    # 图标映射
    ICONS = {
        TYPE_SUCCESS: "✅",
        TYPE_ERROR: "❌",
        TYPE_WARNING: "⚠️",
        TYPE_INFO: "ℹ️",
    }
    
    def __init__(
        self,
        parent: Optional[QWidget] = None,
        dialog_type: str = TYPE_INFO,
        title: str = "",
        message: str = "",
        detail: str = "",
        window_title: str = "提示"
    ):
        super().__init__(parent)
        
        self.dialog_type = dialog_type
        self.title_text = title
        self.message_text = message
        self.detail_text = detail
        
        self._setup_ui(window_title)
    
    def _setup_ui(self, window_title: str):
        """构建 UI"""
        self.setObjectName("common_result_dialog")
        self.setWindowTitle(window_title)
        self.setMinimumWidth(360)
        
        # 移除帮助按钮
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 20)
        
        # 图标和标题行
        header_layout = QHBoxLayout()
        header_layout.setSpacing(12)
        
        # 图标
        icon_text = self.ICONS.get(self.dialog_type, "ℹ️")
        icon_label = QLabel(icon_text)
        icon_label.setObjectName("result_dialog_icon")
        header_layout.addWidget(icon_label)
        
        # 标题
        title_label = QLabel(self.title_text)
        title_label.setObjectName(f"result_dialog_title_{self.dialog_type}")
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        
        layout.addLayout(header_layout)
        
        # 消息
        if self.message_text:
            msg_label = QLabel(self.message_text)
            msg_label.setObjectName("result_dialog_message")
            msg_label.setWordWrap(True)
            layout.addWidget(msg_label)
        
        # 详细信息（可选）
        if self.detail_text:
            detail_label = QLabel(self.detail_text)
            detail_label.setObjectName("result_dialog_detail")
            detail_label.setWordWrap(True)
            layout.addWidget(detail_label)
        
        # 确定按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_ok = QPushButton("确定")
        btn_ok.setObjectName("result_dialog_ok_btn")
        btn_ok.clicked.connect(self.accept)
        btn_ok.setDefault(True)
        btn_layout.addWidget(btn_ok)
        layout.addLayout(btn_layout)
    
    @classmethod
    def show_success(
        cls,
        parent: Optional[QWidget] = None,
        title: str = "成功",
        message: str = "",
        detail: str = "",
        window_title: str = "成功"
    ):
        """显示成功弹窗"""
        dialog = cls(parent, cls.TYPE_SUCCESS, title, message, detail, window_title)
        dialog.exec()
    
    @classmethod
    def show_error(
        cls,
        parent: Optional[QWidget] = None,
        title: str = "错误",
        message: str = "",
        detail: str = "",
        window_title: str = "错误"
    ):
        """显示错误弹窗"""
        dialog = cls(parent, cls.TYPE_ERROR, title, message, detail, window_title)
        dialog.exec()
    
    @classmethod
    def show_warning(
        cls,
        parent: Optional[QWidget] = None,
        title: str = "警告",
        message: str = "",
        detail: str = "",
        window_title: str = "警告"
    ):
        """显示警告弹窗"""
        dialog = cls(parent, cls.TYPE_WARNING, title, message, detail, window_title)
        dialog.exec()
    
    @classmethod
    def show_info(
        cls,
        parent: Optional[QWidget] = None,
        title: str = "提示",
        message: str = "",
        detail: str = "",
        window_title: str = "提示"
    ):
        """显示信息弹窗"""
        dialog = cls(parent, cls.TYPE_INFO, title, message, detail, window_title)
        dialog.exec()

