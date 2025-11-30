"""
Step4: 匹配任务管理Widget
包含：任务组列表、任务组配置
"""
from typing import Callable, Dict, Optional
from qgis.PyQt.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel, QLineEdit,
    QPushButton, QComboBox, QTableWidget, QTableWidgetItem, QCheckBox,
    QProgressBar, QAbstractItemView
)
from qgis.PyQt.QtGui import QColor
from qgis.PyQt.QtCore import Qt
from ..utils import safe_select_rows, set_resize_mode, safe_get_item_flag_enabled
from ..widgets.base_step_widget import BaseStepWidget


class Step4Widget(BaseStepWidget):
    """Step4: 匹配任务管理"""
    
    def __init__(self, parent=None, log_callback: Optional[Callable[[str, str], None]] = None, 
                 task_manager=None, open_filter_modal: Optional[Callable[[str], None]] = None,
                 open_match_modal: Optional[Callable[[str], None]] = None):
        self.open_filter_modal = open_filter_modal or (lambda x: None)
        self.open_match_modal = open_match_modal or (lambda x: None)
        self.group_bars: Dict[str, QProgressBar] = {}
        self.group_labels: Dict[str, QLabel] = {}
        super().__init__(parent, log_callback, task_manager)
        self._build_ui()
    
    def _build_ui(self):
        """构建UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        
        layout.addWidget(self._card_task_groups())
        layout.addWidget(self._card_group_config())
        layout.addStretch()
    
    def _card_task_groups(self) -> QGroupBox:
        """匹配任务组列表"""
        box = QGroupBox("匹配任务组列表（多源表）")
        v = QVBoxLayout(box)
        v.addWidget(QLabel("每个任务组定义：一个源表 → 若干目标表（带优先级）。任务组之间可以并行执行。"))
        
        self.task_groups_table = QTableWidget(2, 7)
        self.task_groups_table.setHorizontalHeaderLabels(["启用", "任务组名称", "源表", "目标表数量", "状态", "进度", "操作"])
        safe_select_rows(self.task_groups_table)
        from ..utils import safe_no_edit
        safe_no_edit(self.task_groups_table)
        header = self.task_groups_table.horizontalHeader()
        for i in range(7):
            set_resize_mode(header, i, prefer_contents=(i in (0, 6)))
        
        rows = [
            ("g1", "任务组1：客户地址 ↔ 门牌库 & 小区库", "客户采集数据_2025Q1_std.csv", "2", "未执行", 100),
            ("g2", "任务组2：补录地址 ↔ 小区库 & GIS 点位", "补录地址库_std.csv", "2", "未执行", 0),
        ]
        
        for r, row in enumerate(rows):
            gid, name, src, tgt_count, status, prog = row
            
            chk = QCheckBox()
            chk.setChecked(True)
            self.task_groups_table.setCellWidget(r, 0, chk)
            
            self.task_groups_table.setItem(r, 1, QTableWidgetItem(name))
            self.task_groups_table.setItem(r, 2, QTableWidgetItem(src))
            self.task_groups_table.setItem(r, 3, QTableWidgetItem(tgt_count))
            self.task_groups_table.setItem(r, 4, QTableWidgetItem(status))
            
            bar = QProgressBar()
            bar.setValue(prog)
            bar.setStyleSheet("""
                QProgressBar {
                    border: 1px solid #d1d5db;
                    border-radius: 3px;
                    text-align: center;
                    height: 7px;
                }
                QProgressBar::chunk {
                    background: linear-gradient(90deg, #2563eb, #1d4ed8);
                    border-radius: 3px;
                }
            """)
            self.group_bars[gid] = bar
            self.task_groups_table.setCellWidget(r, 5, bar)
            
            op_widget = QWidget()
            op_layout = QVBoxLayout(op_widget)
            op_layout.setContentsMargins(2, 2, 2, 2)
            op_layout.setSpacing(2)
            
            lbl = QLabel("空闲" if prog == 0 else "执行任务组1... 完成 (100%)")
            lbl.setStyleSheet("font-size: 11px; color: #6b7280;")
            self.group_labels[gid] = lbl
            op_layout.addWidget(lbl)
            
            btn_row = QHBoxLayout()
            btn_row.setSpacing(2)
            
            task_mgr = self.get_task_manager()
            btn_run = QPushButton("执行")
            btn_run.setStyleSheet("font-size: 11px; padding: 3px 7px; background-color: #2563eb; color: white;")
            btn_run.clicked.connect(lambda checked, g=gid: task_mgr.start_task(g, self.group_bars[g], self.group_labels[g], f"执行{g}..."))
            
            btn_pause = QPushButton("暂停")
            btn_pause.setStyleSheet("font-size: 11px; padding: 3px 7px;")
            btn_pause.clicked.connect(lambda checked, g=gid: task_mgr.pause_task(g, self.group_labels[g]))
            
            btn_stop = QPushButton("终止")
            btn_stop.setStyleSheet("font-size: 11px; padding: 3px 7px; background-color: #ef4444; color: white;")
            btn_stop.clicked.connect(lambda checked, g=gid: task_mgr.stop_task(g, self.group_bars[g], self.group_labels[g]))
            
            btn_row.addWidget(btn_run)
            btn_row.addWidget(btn_pause)
            btn_row.addWidget(btn_stop)
            op_layout.addLayout(btn_row)
            
            btn_config = QPushButton("配置")
            btn_config.setStyleSheet("font-size: 11px; color: #2563eb; text-decoration: underline; border: none; background: transparent;")
            btn_config.clicked.connect(lambda checked, g=gid: self._open_group_config(g))
            op_layout.addWidget(btn_config)
            
            self.task_groups_table.setCellWidget(r, 6, op_widget)
        
        v.addWidget(self.task_groups_table)
        
        btn_add = QPushButton("+ 新增任务组")
        btn_add.setStyleSheet("""
            QPushButton {
                padding: 4px 8px;
                font-size: 12px;
                background-color: #2563eb;
                color: white;
                border: none;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #1d4ed8;
            }
        """)
        btn_add.clicked.connect(lambda: self._log("[Step4] 新增匹配任务组（示意）"))
        v.addWidget(btn_add)
        return box
    
    def _card_group_config(self) -> QGroupBox:
        """当前任务组配置"""
        box = QGroupBox("当前任务组配置：任务组1（示例）")
        self.group_config_title = box
        v = QVBoxLayout(box)
        
        row = QHBoxLayout()
        row.addWidget(QLabel("源表（From，仅一个）"))
        self.combo_src_table = QComboBox()
        self.combo_src_table.addItems(
            ["客户采集数据_2025Q1_std.csv", "补录地址库_std.csv", "小区地址库_std.xlsx"]
        )
        row.addWidget(self.combo_src_table)
        row.addStretch()
        v.addLayout(row)
        
        v.addWidget(QLabel("源表过滤条件（可多条，类似 WHERE）"))
        self.src_cond_table = QTableWidget(1, 5)
        self.src_cond_table.setHorizontalHeaderLabels(["字段", "运算符", "值", "逻辑", "操作"])
        safe_select_rows(self.src_cond_table)
        from ..utils import safe_set_edit_triggers
        safe_set_edit_triggers(self.src_cond_table, allow_edit=True)
        src_header = self.src_cond_table.horizontalHeader()
        for i in range(5):
            set_resize_mode(src_header, i, prefer_contents=False)
        
        r = 0
        self.src_cond_table.setItem(r, 0, QTableWidgetItem("cust_district"))
        op_combo = QComboBox()
        op_combo.addItems(["=", "IN", "LIKE", "!=", ">", "<", ">=", "<="])
        op_combo.setCurrentText("=")
        self.src_cond_table.setCellWidget(r, 1, op_combo)
        self.src_cond_table.setItem(r, 2, QTableWidgetItem("鼓楼区"))
        logic_combo = QComboBox()
        logic_combo.addItems(["AND", "OR"])
        logic_combo.setCurrentText("AND")
        self.src_cond_table.setCellWidget(r, 3, logic_combo)
        btn_del = QPushButton("删")
        btn_del.setStyleSheet("font-size: 11px; padding: 2px 6px; background-color: #ef4444; color: white;")
        btn_del.clicked.connect(lambda checked, row=r: self._delete_src_cond_row(row))
        self.src_cond_table.setCellWidget(r, 4, btn_del)
        
        v.addWidget(self.src_cond_table)
        
        btn_add_src_cond = QPushButton("+ 新增条件")
        btn_add_src_cond.setStyleSheet("font-size: 11px; padding: 3px 7px;")
        btn_add_src_cond.clicked.connect(self._add_src_cond_row)
        v.addWidget(btn_add_src_cond)
        
        v.addWidget(QLabel("目标表列表（优先级从上到下）"))
        self.tgt_table = QTableWidget(2, 6)
        self.tgt_table.setHorizontalHeaderLabels(["序", "目标表", "过滤条件", "字段匹配对", "匹配方式说明", "操作"])
        safe_select_rows(self.tgt_table)
        safe_set_edit_triggers(self.tgt_table, allow_edit=True)
        tgt_header = self.tgt_table.horizontalHeader()
        for i in range(6):
            set_resize_mode(tgt_header, i, prefer_contents=(i == 0 or i == 5))
        
        tgt_data = [
            {"table": "门牌库_市政_std.csv", "match_desc": "std_full_addr ↔ mp_full_addr"},
            {"table": "小区地址库_std.xlsx", "match_desc": "community_name ↔ community_name"},
        ]
        
        for r, data in enumerate(tgt_data):
            self.tgt_table.setItem(r, 0, QTableWidgetItem(str(r + 1)))
            self.tgt_table.item(r, 0).setFlags(safe_get_item_flag_enabled())
            
            table_combo = QComboBox()
            table_combo.setEditable(True)
            table_combo.addItems(["门牌库_市政_std.csv", "小区地址库_std.xlsx", "GIS_小区点位_std.shp"])
            table_combo.setCurrentText(data["table"])
            self.tgt_table.setCellWidget(r, 1, table_combo)
            
            btn_filter = QPushButton("配置过滤条件")
            btn_filter.setStyleSheet("""
                QPushButton {
                    font-size: 11px;
                    color: #2563eb;
                    text-decoration: underline;
                    border: none;
                    background: transparent;
                }
                QPushButton:hover {
                    color: #1d4ed8;
                }
            """)
            btn_filter.clicked.connect(lambda checked, name=data["table"]: self.open_filter_modal(name))
            self.tgt_table.setCellWidget(r, 2, btn_filter)
            
            btn_match = QPushButton("配置字段匹配对")
            btn_match.setStyleSheet("""
                QPushButton {
                    font-size: 11px;
                    color: #2563eb;
                    text-decoration: underline;
                    border: none;
                    background: transparent;
                }
                QPushButton:hover {
                    color: #1d4ed8;
                }
            """)
            btn_match.clicked.connect(lambda checked, name=data["table"]: self.open_match_modal(name))
            self.tgt_table.setCellWidget(r, 3, btn_match)
            
            self.tgt_table.setItem(r, 4, QTableWidgetItem(data["match_desc"]))
            self.tgt_table.item(r, 4).setForeground(QColor("#6b7280"))
            
            btn_widget = QWidget()
            btn_layout = QHBoxLayout(btn_widget)
            btn_layout.setContentsMargins(2, 2, 2, 2)
            btn_layout.setSpacing(2)
            
            btn_up = QPushButton("上")
            btn_up.setStyleSheet("font-size: 11px; padding: 2px 6px;")
            btn_up.clicked.connect(lambda checked, row=r: self._move_target_row(row, -1))
            
            btn_down = QPushButton("下")
            btn_down.setStyleSheet("font-size: 11px; padding: 2px 6px;")
            btn_down.clicked.connect(lambda checked, row=r: self._move_target_row(row, 1))
            
            btn_del = QPushButton("删")
            btn_del.setStyleSheet("font-size: 11px; padding: 2px 6px; background-color: #ef4444; color: white;")
            btn_del.clicked.connect(lambda checked, row=r: self._delete_target_row(row))
            
            btn_layout.addWidget(btn_up)
            btn_layout.addWidget(btn_down)
            btn_layout.addWidget(btn_del)
            self.tgt_table.setCellWidget(r, 5, btn_widget)
        
        v.addWidget(self.tgt_table)
        
        btn_add_target = QPushButton("+ 新增目标表")
        btn_add_target.setStyleSheet("""
            QPushButton {
                padding: 4px 8px;
                font-size: 12px;
                background-color: #2563eb;
                color: white;
                border: none;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #1d4ed8;
            }
        """)
        btn_add_target.clicked.connect(self._add_target_row)
        v.addWidget(btn_add_target)
        return box
    
    def _open_group_config(self, group_id: str):
        """打开任务组配置"""
        if hasattr(self, 'group_config_title'):
            if group_id == "g1":
                self.group_config_title.setTitle("当前任务组配置：任务组1（客户地址 ↔ 门牌库 & 小区库）")
            elif group_id == "g2":
                self.group_config_title.setTitle("当前任务组配置：任务组2（补录地址 ↔ 小区库 & GIS 点位）")
        self._log(f"[Step4] 打开 {group_id} 配置（示意）")
    
    def _add_src_cond_row(self):
        """添加源表过滤条件行"""
        row = self.src_cond_table.rowCount()
        self.src_cond_table.insertRow(row)
        
        self.src_cond_table.setItem(row, 0, QTableWidgetItem(""))
        op_combo = QComboBox()
        op_combo.addItems(["=", "IN", "LIKE", "!=", ">", "<", ">=", "<="])
        self.src_cond_table.setCellWidget(row, 1, op_combo)
        self.src_cond_table.setItem(row, 2, QTableWidgetItem(""))
        logic_combo = QComboBox()
        logic_combo.addItems(["AND", "OR"])
        self.src_cond_table.setCellWidget(row, 3, logic_combo)
        btn_del = QPushButton("删")
        btn_del.setStyleSheet("font-size: 11px; padding: 2px 6px; background-color: #ef4444; color: white;")
        btn_del.clicked.connect(lambda checked, r=row: self._delete_src_cond_row(r))
        self.src_cond_table.setCellWidget(row, 4, btn_del)
    
    def _delete_src_cond_row(self, row: int):
        """删除源表过滤条件行"""
        self.src_cond_table.removeRow(row)
    
    def _move_target_row(self, row: int, direction: int):
        """移动目标表行"""
        new_row = row + direction
        if new_row < 0 or new_row >= self.tgt_table.rowCount():
            return
        
        self.tgt_table.insertRow(new_row + (1 if direction > 0 else 0))
        for col in range(self.tgt_table.columnCount()):
            item = self.tgt_table.takeItem(row, col)
            widget = self.tgt_table.cellWidget(row, col)
            if item:
                self.tgt_table.setItem(new_row, col, item)
            elif widget:
                self.tgt_table.setCellWidget(new_row, col, widget)
        self.tgt_table.removeRow(row + (0 if direction > 0 else 1))
        
        for r in range(self.tgt_table.rowCount()):
            self.tgt_table.item(r, 0).setText(str(r + 1))
        
        self._log(f"[Step4] 移动目标表行 {row} -> {new_row}")
    
    def _delete_target_row(self, row: int):
        """删除目标表行"""
        self.tgt_table.removeRow(row)
        for r in range(self.tgt_table.rowCount()):
            self.tgt_table.item(r, 0).setText(str(r + 1))
        self._log(f"[Step4] 删除目标表行 {row}")
    
    def _add_target_row(self):
        """添加目标表行"""
        row = self.tgt_table.rowCount()
        self.tgt_table.insertRow(row)
        
        self.tgt_table.setItem(row, 0, QTableWidgetItem(str(row + 1)))
        self.tgt_table.item(row, 0).setFlags(safe_get_item_flag_enabled())
        
        table_combo = QComboBox()
        table_combo.setEditable(True)
        table_combo.addItems(["门牌库_市政_std.csv", "小区地址库_std.xlsx", "GIS_小区点位_std.shp"])
        self.tgt_table.setCellWidget(row, 1, table_combo)
        
        btn_filter = QPushButton("配置过滤条件")
        btn_filter.setStyleSheet("font-size: 11px; color: #2563eb; text-decoration: underline; border: none; background: transparent;")
        btn_filter.clicked.connect(lambda checked, name="新目标表": self.open_filter_modal(name))
        self.tgt_table.setCellWidget(row, 2, btn_filter)
        
        btn_match = QPushButton("配置字段匹配对")
        btn_match.setStyleSheet("font-size: 11px; color: #2563eb; text-decoration: underline; border: none; background: transparent;")
        btn_match.clicked.connect(lambda checked, name="新目标表": self.open_match_modal(name))
        self.tgt_table.setCellWidget(row, 3, btn_match)
        
        self.tgt_table.setItem(row, 4, QTableWidgetItem(""))
        
        btn_widget = QWidget()
        btn_layout = QHBoxLayout(btn_widget)
        btn_layout.setContentsMargins(2, 2, 2, 2)
        btn_layout.setSpacing(2)
        
        btn_up = QPushButton("上")
        btn_up.setStyleSheet("font-size: 11px; padding: 2px 6px;")
        btn_up.clicked.connect(lambda checked, r=row: self._move_target_row(r, -1))
        
        btn_down = QPushButton("下")
        btn_down.setStyleSheet("font-size: 11px; padding: 2px 6px;")
        btn_down.clicked.connect(lambda checked, r=row: self._move_target_row(r, 1))
        
        btn_del = QPushButton("删")
        btn_del.setStyleSheet("font-size: 11px; padding: 2px 6px; background-color: #ef4444; color: white;")
        btn_del.clicked.connect(lambda checked, r=row: self._delete_target_row(r))
        
        btn_layout.addWidget(btn_up)
        btn_layout.addWidget(btn_down)
        btn_layout.addWidget(btn_del)
        self.tgt_table.setCellWidget(row, 5, btn_widget)
        
        self._log(f"[Step4] 新增目标表行")

