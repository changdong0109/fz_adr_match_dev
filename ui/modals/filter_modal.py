"""
过滤条件模态对话框
"""
from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit, QPushButton
)
from qgis.PyQt.QtCore import Qt


class FilterModal(QDialog):
    """目标表过滤条件对话框"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("目标表过滤条件")
        self.setModal(True)
        self.resize(500, 280)
        self._target_name = ""
        self._conditions = {}  # 存储每个目标表的条件
        self._build_ui()
    
    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)
        
        self.title_label = QLabel("目标表过滤条件 -")
        self.title_label.setStyleSheet("font-size: 13px; font-weight: 600;")
        layout.addWidget(self.title_label)
        
        subtitle = QLabel("输入SQL WHERE条件（不含WHERE关键字）：")
        subtitle.setStyleSheet("font-size: 12px; color: #374151;")
        layout.addWidget(subtitle)
        
        example = QLabel("例如: type = '住宅' AND valid = 1")
        example.setStyleSheet("font-size: 11px; color: #9ca3af;")
        layout.addWidget(example)
        
        # 条件文本框
        self.txt_condition = QTextEdit()
        self.txt_condition.setPlaceholderText("输入过滤条件...")
        self.txt_condition.setStyleSheet("""
            QTextEdit {
                font-size: 12px;
                font-family: Consolas, monospace;
                padding: 8px;
                border: 1px solid #d1d5db;
                border-radius: 4px;
                background-color: #ffffff;
            }
        """)
        self.txt_condition.setMinimumHeight(100)
        layout.addWidget(self.txt_condition)
        
        layout.addStretch()
        
        # 按钮行
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        
        btn_ok = QPushButton("确定")
        btn_ok.setStyleSheet("""
            QPushButton {
                font-size: 12px;
                padding: 6px 16px;
                background-color: #3b82f6;
                color: white;
                border: none;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #2563eb;
            }
        """)
        btn_ok.clicked.connect(self._on_ok)
        btn_row.addWidget(btn_ok)
        
        btn_cancel = QPushButton("取消")
        btn_cancel.setStyleSheet("""
            QPushButton {
                font-size: 12px;
                padding: 6px 16px;
                background-color: #f3f4f6;
                color: #374151;
                border: 1px solid #d1d5db;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #e5e7eb;
            }
        """)
        btn_cancel.clicked.connect(self.close)
        btn_row.addWidget(btn_cancel)
        
        layout.addLayout(btn_row)
    
    def set_target_name(self, name: str):
        """设置目标表名称"""
        self._target_name = name
        self.title_label.setText(f"目标表过滤条件 - {name}")
        # 恢复之前保存的条件
        self.txt_condition.setPlainText(self._conditions.get(name, ""))
    
    def get_condition(self) -> str:
        """获取当前条件"""
        return self.txt_condition.toPlainText().strip()
    
    def get_condition_for(self, target_name: str) -> str:
        """获取指定目标表的条件"""
        return self._conditions.get(target_name, "")
    
    def _on_ok(self):
        """确定按钮"""
        # 保存条件
        if self._target_name:
            self._conditions[self._target_name] = self.txt_condition.toPlainText().strip()
        self.accept()
