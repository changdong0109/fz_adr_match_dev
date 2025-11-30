"""
过滤条件模态对话框
"""
from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget, QTableWidgetItem,
    QPushButton, QComboBox, QAbstractItemView
)
from ..utils import safe_select_rows, set_resize_mode


class FilterModal(QDialog):
    """目标表过滤条件对话框"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("目标表过滤条件")
        self.setModal(True)
        self.resize(520, 400)
        self._build_ui()
    
    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 12, 10, 12)
        
        self.title_label = QLabel("目标表过滤条件：")
        self.title_label.setStyleSheet("font-size: 13px; font-weight: 600; margin-bottom: 4px;")
        layout.addWidget(self.title_label)
        
        subtitle = QLabel("这里只是配置 UI，具体 SQL/表达式由你后端实现。")
        subtitle.setStyleSheet("font-size: 12px; color: #6b7280; margin-bottom: 6px;")
        layout.addWidget(subtitle)
        
        # 过滤条件表格
        self.table = QTableWidget(1, 5)
        self.table.setHorizontalHeaderLabels(["字段", "运算符", "值", "逻辑", "操作"])
        self.table.setStyleSheet("font-size: 12px;")
        safe_select_rows(self.table)
        from ..utils import safe_set_edit_triggers
        safe_set_edit_triggers(self.table, allow_edit=True)
        
        header = self.table.horizontalHeader()
        for i in range(5):
            set_resize_mode(header, i, prefer_contents=False)
        
        # 示例行
        self.add_row("city", "=", "南京市", "AND")
        layout.addWidget(self.table)
        
        btn_add = QPushButton("+ 新增条件")
        btn_add.setStyleSheet("font-size: 11px; padding: 3px 7px;")
        btn_add.clicked.connect(self._on_add_row)
        layout.addWidget(btn_add)
        
        layout.addStretch()
        
        # 按钮行
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_close = QPushButton("关闭")
        btn_close.setStyleSheet("font-size: 12px; padding: 4px 8px;")
        btn_close.clicked.connect(self.close)
        btn_row.addWidget(btn_close)
        layout.addLayout(btn_row)
    
    def set_target_name(self, name: str):
        """设置目标表名称"""
        self.title_label.setText(f"目标表过滤条件：{name}")
    
    def add_row(self, field="", op="=", value="", logic="AND"):
        """添加过滤条件行"""
        row = self.table.rowCount()
        self.table.insertRow(row)
        
        self.table.setItem(row, 0, QTableWidgetItem(field))
        
        op_combo = QComboBox()
        op_combo.addItems(["=", "IN", "LIKE", "!=", ">", "<", ">=", "<="])
        op_combo.setCurrentText(op)
        self.table.setCellWidget(row, 1, op_combo)
        
        self.table.setItem(row, 2, QTableWidgetItem(value))
        
        logic_combo = QComboBox()
        logic_combo.addItems(["AND", "OR"])
        logic_combo.setCurrentText(logic)
        self.table.setCellWidget(row, 3, logic_combo)
        
        btn_del = QPushButton("删")
        btn_del.setStyleSheet("font-size: 11px; padding: 2px 6px; background-color: #ef4444; color: white;")
        btn_del.clicked.connect(lambda checked, r=row: self._delete_row(r))
        self.table.setCellWidget(row, 4, btn_del)
    
    def _on_add_row(self):
        """添加新行"""
        self.add_row()
    
    def _delete_row(self, row: int):
        """删除行"""
        self.table.removeRow(row)

