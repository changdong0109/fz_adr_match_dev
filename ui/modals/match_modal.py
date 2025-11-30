"""
字段匹配对模态对话框
"""
from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget, QTableWidgetItem,
    QPushButton, QComboBox, QAbstractItemView
)
from ..utils import safe_select_rows, set_resize_mode


class MatchModal(QDialog):
    """字段匹配对配置对话框"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("字段匹配对配置")
        self.setModal(True)
        self.resize(520, 400)
        self._build_ui()
    
    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 12, 10, 12)
        
        self.title_label = QLabel("字段匹配对配置：")
        self.title_label.setStyleSheet("font-size: 13px; font-weight: 600; margin-bottom: 4px;")
        layout.addWidget(self.title_label)
        
        subtitle = QLabel("多对字段完全由你选；\"匹配方式\"只是告诉后端采用精确/模糊/混合策略，具体算法你决定。")
        subtitle.setStyleSheet("font-size: 12px; color: #6b7280; margin-bottom: 6px;")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)
        
        # 匹配对表格
        self.table = QTableWidget(2, 4)
        self.table.setHorizontalHeaderLabels(["源表字段", "匹配方式", "目标表字段", "操作"])
        self.table.setStyleSheet("font-size: 12px;")
        safe_select_rows(self.table)
        from ..utils import safe_set_edit_triggers
        safe_set_edit_triggers(self.table, allow_edit=True)
        
        header = self.table.horizontalHeader()
        for i in range(4):
            set_resize_mode(header, i, prefer_contents=(i == 3))
        
        # 示例行
        self.add_row("std_full_addr", "模糊", "mp_full_addr")
        self.add_row("std_city", "精确", "city")
        layout.addWidget(self.table)
        
        btn_add = QPushButton("+ 新增字段对")
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
        self.title_label.setText(f"字段匹配对配置：{name}")
    
    def add_row(self, src_field="", match_type="模糊", tgt_field=""):
        """添加匹配对行"""
        row = self.table.rowCount()
        self.table.insertRow(row)
        
        self.table.setItem(row, 0, QTableWidgetItem(src_field))
        
        match_combo = QComboBox()
        match_combo.addItems(["精确", "模糊", "精确+模糊"])
        match_combo.setCurrentText(match_type)
        self.table.setCellWidget(row, 1, match_combo)
        
        self.table.setItem(row, 2, QTableWidgetItem(tgt_field))
        
        btn_del = QPushButton("删")
        btn_del.setStyleSheet("font-size: 11px; padding: 2px 6px; background-color: #ef4444; color: white;")
        btn_del.clicked.connect(lambda checked, r=row: self._delete_row(r))
        self.table.setCellWidget(row, 3, btn_del)
    
    def _on_add_row(self):
        """添加新行"""
        self.add_row()
    
    def _delete_row(self, row: int):
        """删除行"""
        self.table.removeRow(row)

