# -*- coding: utf-8 -*-
"""
通用进度弹窗组件
用于显示耗时操作的进度
"""
from typing import Optional, Callable
from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QProgressBar, QWidget
)
from qgis.PyQt.QtCore import Qt


class ProgressDialog(QDialog):
    """
    通用进度弹窗
    
    用法:
        dialog = ProgressDialog(parent, "导出数据", "正在处理...")
        dialog.set_progress(50, "已处理 50%")
        dialog.on_cancel = lambda: worker.cancel()
        dialog.show()
        
        # 完成后
        dialog.close()
    """
    
    def __init__(
        self,
        parent: Optional[QWidget] = None,
        title: str = "处理中",
        message: str = "请稍候...",
        cancelable: bool = True
    ):
        super().__init__(parent)
        
        self.title_text = title
        self.message_text = message
        self.cancelable = cancelable
        self.on_cancel: Optional[Callable] = None
        self._cancelled = False
        
        self._setup_ui()
    
    def _setup_ui(self):
        """构建 UI"""
        self.setObjectName("common_progress_dialog")
        self.setWindowTitle(self.title_text)
        self.setMinimumWidth(400)
        self.setModal(True)
        
        # 移除帮助按钮，禁止关闭
        self.setWindowFlags(
            self.windowFlags() 
            & ~Qt.WindowType.WindowContextHelpButtonHint
            & ~Qt.WindowType.WindowCloseButtonHint
        )
        
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 20)
        
        # 标题
        self.title_label = QLabel(self.title_text)
        self.title_label.setObjectName("progress_dialog_title")
        layout.addWidget(self.title_label)
        
        # 消息
        self.message_label = QLabel(self.message_text)
        self.message_label.setObjectName("progress_dialog_message")
        self.message_label.setWordWrap(True)
        layout.addWidget(self.message_label)
        
        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setObjectName("progress_dialog_bar")
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("%p%")
        layout.addWidget(self.progress_bar)
        
        # 按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        if self.cancelable:
            self.btn_cancel = QPushButton("取消")
            self.btn_cancel.setObjectName("progress_dialog_cancel_btn")
            self.btn_cancel.clicked.connect(self._on_cancel)
            btn_layout.addWidget(self.btn_cancel)
        
        layout.addLayout(btn_layout)
    
    def set_progress(self, value: int, message: str = None):
        """设置进度"""
        self.progress_bar.setValue(value)
        if message:
            self.message_label.setText(message)
    
    def set_message(self, message: str):
        """设置消息"""
        self.message_label.setText(message)
    
    def _on_cancel(self):
        """取消按钮点击"""
        self._cancelled = True
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.setText("取消中...")
        if self.on_cancel:
            self.on_cancel()
    
    @property
    def is_cancelled(self) -> bool:
        return self._cancelled

