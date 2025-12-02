"""
字段匹配对模态对话框
遵循文档规范：样式通过 objectName + QSS 管理
"""
from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget, QTableWidgetItem,
    QPushButton, QHeaderView
)
from ..utils import safe_select_rows, set_resize_mode
from ..widgets.no_wheel_combo_box import NoWheelComboBox


class MatchModal(QDialog):
    """字段匹配对配置对话框"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("字段匹配对配置")
        self.setObjectName("match_modal")
        self.setModal(True)
        self.resize(560, 420)
        self._build_ui()
    
    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)
        
        self.title_label = QLabel("字段匹配对配置：")
        self.title_label.setObjectName("match_modal_title")
        layout.addWidget(self.title_label)
        
        subtitle = QLabel("多对字段完全由你选；\"匹配方式\"只是告诉后端采用精确/模糊/混合策略，具体算法你决定。")
        subtitle.setObjectName("match_modal_subtitle")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)
        
        # 匹配对表格
        self.table = QTableWidget(0, 4)
        self.table.setObjectName("match_modal_table")
        self.table.setHorizontalHeaderLabels(["源表字段", "匹配方式", "目标表字段", "操作"])
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(36)
        self.table.setMinimumHeight(200)
        self.table.setAlternatingRowColors(True)
        safe_select_rows(self.table)
        from ..utils import safe_set_edit_triggers
        safe_set_edit_triggers(self.table, allow_edit=True)
        
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(1, 100)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(3, 50)
        
        # 示例行
        self.add_row("std_full_addr", "模糊", "mp_full_addr")
        self.add_row("std_city", "精确", "city")
        layout.addWidget(self.table)
        
        btn_add = QPushButton("+ 新增字段对")
        btn_add.setObjectName("match_modal_btn_add")
        btn_add.clicked.connect(self._on_add_row)
        layout.addWidget(btn_add)
        
        layout.addStretch()
        
        # 按钮行
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        
        btn_ok = QPushButton("确定")
        btn_ok.setObjectName("match_modal_btn_ok")
        btn_ok.clicked.connect(self.accept)
        btn_row.addWidget(btn_ok)
        
        btn_cancel = QPushButton("取消")
        btn_cancel.setObjectName("match_modal_btn_cancel")
        btn_cancel.clicked.connect(self.close)
        btn_row.addWidget(btn_cancel)
        
        layout.addLayout(btn_row)
    
    def set_target_name(self, name: str):
        """设置目标表名称"""
        self.title_label.setText(f"字段匹配对配置：{name}")
    
    def add_row(self, src_field="", match_type="模糊", tgt_field=""):
        """添加匹配对行"""
        row = self.table.rowCount()
        self.table.insertRow(row)
        
        self.table.setItem(row, 0, QTableWidgetItem(src_field))
        
        match_combo = NoWheelComboBox()
        match_combo.addItems(["精确", "模糊", "精确+模糊"])
        match_combo.setCurrentText(match_type)
        self.table.setCellWidget(row, 1, match_combo)
        
        self.table.setItem(row, 2, QTableWidgetItem(tgt_field))
        
        btn_del = QPushButton("删")
        btn_del.setObjectName("match_modal_btn_del")
        btn_del.clicked.connect(lambda checked, r=row: self._delete_row(r))
        self.table.setCellWidget(row, 3, btn_del)
    
    def _on_add_row(self):
        """添加新行"""
        self.add_row()
    
    def _delete_row(self, row: int):
        """删除行"""
        # 查找实际行号
        sender = self.sender()
        if sender:
            for r in range(self.table.rowCount()):
                widget = self.table.cellWidget(r, 3)
                if widget is sender:
                    row = r
                    break
        
        self.table.removeRow(row)
