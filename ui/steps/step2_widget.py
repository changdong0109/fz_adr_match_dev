"""
Step2: 字段映射与清洗Widget
包含：文件配置进度、字段组合配置、批量清洗
"""
from typing import Callable, Dict, List, Optional
from qgis.PyQt.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel, QLineEdit,
    QPushButton, QComboBox, QTableWidget, QTableWidgetItem, QCheckBox,
    QProgressBar, QRadioButton, QScrollArea, QFrame, QMessageBox,
    QAbstractItemView
)
from qgis.PyQt.QtGui import QColor
from qgis.PyQt.QtCore import Qt
from ..utils import safe_select_rows, safe_no_edit, set_resize_mode, safe_get_item_flag_enabled
from ..widgets.base_step_widget import BaseStepWidget


class Step2Widget(BaseStepWidget):
    """Step2: 字段映射与清洗"""
    
    def __init__(self, parent=None, log_callback: Optional[Callable[[str, str], None]] = None, 
                 task_manager=None):
        # 文件配置数据
        self.file_configs = {
            "file1": {"name": "客户采集数据_2025Q1.csv", "combos": 2, "configured": "是", "cleaned": "已清洗"},
            "file2": {"name": "小区地址库.xlsx", "combos": 1, "configured": "是", "cleaned": "未清洗"},
            "file3": {"name": "补录地址库_现场.csv", "combos": 1, "configured": "部分", "cleaned": "未清洗"},
        }
        self.current_file_id = "file2"
        
        # 字段组合配置
        self.file_combo_configs = {
            "file1": [
                {
                    "title": "组合 1：标准地址组合",
                    "subtitle": "（城市+小区+详细地址）",
                    "fields": [
                        {"role": "城市", "field": "std_city"},
                        {"role": "小区名", "field": "community_name"},
                        {"role": "详细地址", "field": "addr_detail"},
                    ]
                },
                {
                    "title": "组合 2：小区+门牌号",
                    "subtitle": "",
                    "fields": [
                        {"role": "小区名", "field": "community_name"},
                        {"role": "门牌号", "field": "door_no"},
                    ]
                }
            ],
            "file2": [
                {
                    "title": "组合 1：小区+详细地址",
                    "subtitle": "",
                    "fields": [
                        {"role": "小区名", "field": "community_name"},
                        {"role": "详细地址", "field": "addr_detail"},
                    ]
                }
            ],
            "file3": [
                {
                    "title": "组合 1：街道+门牌",
                    "subtitle": "",
                    "fields": [
                        {"role": "街道", "field": "street_name"},
                        {"role": "门牌号", "field": "door_no"},
                    ]
                }
            ]
        }
        
        super().__init__(parent, log_callback, task_manager)
        self._build_ui()
    
    def _build_ui(self):
        """构建UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        
        layout.addWidget(self._card_cfg_progress())
        layout.addWidget(self._card_field_combos())
        layout.addWidget(self._card_clean())
        layout.addStretch()
    
    def _card_cfg_progress(self) -> QGroupBox:
        """参与任务文件配置进度"""
        box = QGroupBox("参与任务文件配置进度")
        v = QVBoxLayout(box)
        v.addWidget(QLabel("每个文件可以配置多个\"字段组合\"；配置好后统一批量清洗。"))
        
        self.cfg_progress_table = QTableWidget(3, 5)
        self.cfg_progress_table.setHorizontalHeaderLabels(["当前", "文件名", "字段组合数", "已配置", "清洗状态"])
        safe_select_rows(self.cfg_progress_table)
        safe_no_edit(self.cfg_progress_table)
        header = self.cfg_progress_table.horizontalHeader()
        for i in range(5):
            set_resize_mode(header, i, prefer_contents=(i == 0))
        
        for r, (fid, data) in enumerate(self.file_configs.items()):
            radio = QRadioButton()
            radio.setObjectName(fid)
            if fid == self.current_file_id:
                radio.setChecked(True)
            radio.toggled.connect(lambda checked, f=fid: self._on_file_selected(f) if checked else None)
            self.cfg_progress_table.setCellWidget(r, 0, radio)
            
            self.cfg_progress_table.setItem(r, 1, QTableWidgetItem(data["name"]))
            self.cfg_progress_table.setItem(r, 2, QTableWidgetItem(str(data["combos"])))
            
            config_item = QTableWidgetItem(data["configured"])
            if data["configured"] == "是":
                config_item.setForeground(QColor("#15803d"))
            elif data["configured"] == "部分":
                config_item.setForeground(QColor("#92400e"))
            self.cfg_progress_table.setItem(r, 3, config_item)
            
            clean_item = QTableWidgetItem(data["cleaned"])
            if data["cleaned"] == "已清洗":
                clean_item.setForeground(QColor("#15803d"))
            self.cfg_progress_table.setItem(r, 4, clean_item)
        
        v.addWidget(self.cfg_progress_table)
        return box
    
    def _card_field_combos(self) -> QGroupBox:
        """字段组合与字段顺序"""
        box = QGroupBox("字段组合与字段顺序（当前文件）")
        v = QVBoxLayout(box)
        v.addWidget(QLabel("一个文件可以有多个\"组合\"；每个组合下的字段顺序定义拼接顺序，系统不做智能推荐，只按你选的字段 & 顺序执行清洗。"))
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("border: 1px dashed #d1d5db; border-radius: 4px; background: #f9fafb;")
        scroll.setMinimumHeight(400)
        
        self.file_config_container = QWidget()
        self.file_config_layout = QVBoxLayout(self.file_config_container)
        self.file_config_layout.setContentsMargins(6, 6, 6, 6)
        self.file_config_layout.setSpacing(6)
        
        scroll.setWidget(self.file_config_container)
        v.addWidget(scroll)
        
        self._refresh_file_config_display()
        return box
    
    def _card_clean(self) -> QGroupBox:
        """批量执行清洗"""
        box = QGroupBox("批量执行清洗")
        v = QVBoxLayout(box)
        v.addWidget(QLabel("对所有参与且已配置组合的文件统一执行清洗。"))
        
        row = QHBoxLayout()
        self.bar_clean = QProgressBar()
        self.lbl_clean = QLabel("空闲")
        row.addWidget(self.bar_clean)
        row.addWidget(self.lbl_clean)
        btn_run = QPushButton("执行清洗")
        btn_pause = QPushButton("暂停")
        btn_stop = QPushButton("终止")
        row.addWidget(btn_run)
        row.addWidget(btn_pause)
        row.addWidget(btn_stop)
        row.addStretch()
        v.addLayout(row)
        
        task_mgr = self.get_task_manager()
        btn_run.clicked.connect(lambda: task_mgr.start_task("clean", self.bar_clean, self.lbl_clean, "批量清洗..."))
        btn_pause.clicked.connect(lambda: task_mgr.pause_task("clean", self.lbl_clean))
        btn_stop.clicked.connect(lambda: task_mgr.stop_task("clean", self.bar_clean, self.lbl_clean))
        
        return box
    
    def _on_file_selected(self, file_id: str):
        """文件选择事件"""
        self.current_file_id = file_id
        self._refresh_file_config_display()
    
    def _refresh_file_config_display(self):
        """刷新当前文件的配置显示"""
        while self.file_config_layout.count():
            child = self.file_config_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        
        if self.current_file_id not in self.file_combo_configs:
            return
        
        current_file_name = self.file_configs.get(self.current_file_id, {}).get("name", "")
        file_label = QLabel(f"当前文件：{current_file_name}")
        file_label.setStyleSheet("font-size: 12px; color: #6b7280; margin-bottom: 4px;")
        self.file_config_layout.addWidget(file_label)
        
        combos = self.file_combo_configs[self.current_file_id]
        for combo_idx, combo in enumerate(combos):
            combo_widget = self._create_combo_block(combo, combo_idx)
            self.file_config_layout.addWidget(combo_widget)
        
        btn_add_combo = QPushButton("+ 新增字段组合")
        btn_add_combo.setStyleSheet("""
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
        btn_add_combo.clicked.connect(lambda: self._add_combo(self.current_file_id))
        self.file_config_layout.addWidget(btn_add_combo)
        
        tip_label = QLabel("拼接顺序 = 行顺序；你后端只拿字段名 & 顺序去做清洗，角色名称只是备注。")
        tip_label.setStyleSheet("font-size: 11px; color: #9ca3af; margin-top: 4px;")
        self.file_config_layout.addWidget(tip_label)
        
        self.file_config_layout.addStretch()
    
    def _create_combo_block(self, combo: Dict, combo_idx: int) -> QWidget:
        """创建一个组合块"""
        combo_frame = QFrame()
        combo_frame.setStyleSheet("""
            QFrame {
                border: 1px dashed #d1d5db;
                border-radius: 4px;
                padding: 6px;
                background: #f9fafb;
                margin-bottom: 6px;
            }
        """)
        combo_layout = QVBoxLayout(combo_frame)
        combo_layout.setContentsMargins(6, 6, 6, 6)
        combo_layout.setSpacing(4)
        
        header_layout = QHBoxLayout()
        title_label = QLabel(f"{combo['title']}{combo.get('subtitle', '')}")
        title_label.setStyleSheet("font-size: 12px; font-weight: 500;")
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        
        btn_delete_combo = QPushButton("删除组合")
        btn_delete_combo.setStyleSheet("""
            QPushButton {
                padding: 3px 7px;
                font-size: 11px;
                background-color: #ef4444;
                color: white;
                border: none;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #dc2626;
            }
        """)
        btn_delete_combo.clicked.connect(lambda: self._delete_combo(self.current_file_id, combo_idx))
        header_layout.addWidget(btn_delete_combo)
        combo_layout.addLayout(header_layout)
        
        field_table = QTableWidget(len(combo['fields']), 4)
        field_table.setHorizontalHeaderLabels(["顺序", "角色名称（备注）", "字段（当前文件列）", "操作"])
        field_table.setStyleSheet("font-size: 12px;")
        safe_select_rows(field_table)
        from ..utils import safe_set_edit_triggers
        safe_set_edit_triggers(field_table, allow_edit=True)
        
        header = field_table.horizontalHeader()
        set_resize_mode(header, 0, prefer_contents=True)
        set_resize_mode(header, 1, prefer_contents=False)
        set_resize_mode(header, 2, prefer_contents=False)
        set_resize_mode(header, 3, prefer_contents=True)
        
        for r, field_data in enumerate(combo['fields']):
            field_table.setItem(r, 0, QTableWidgetItem(str(r + 1)))
            field_table.item(r, 0).setFlags(safe_get_item_flag_enabled())
            
            role_item = QTableWidgetItem(field_data['role'])
            field_table.setItem(r, 1, role_item)
            
            field_combo = QComboBox()
            field_combo.setEditable(True)
            field_options = ["std_city", "province", "community_name", "estate_name", 
                           "addr_detail", "door_info", "door_no", "street_name"]
            field_combo.addItems(field_options)
            field_combo.setCurrentText(field_data['field'])
            field_table.setCellWidget(r, 2, field_combo)
            
            btn_widget = QWidget()
            btn_layout = QHBoxLayout(btn_widget)
            btn_layout.setContentsMargins(2, 2, 2, 2)
            btn_layout.setSpacing(2)
            
            btn_up = QPushButton("上移")
            btn_up.setStyleSheet("font-size: 11px; padding: 2px 6px;")
            btn_up.clicked.connect(lambda checked, row=r: self._move_field_row(field_table, row, -1))
            
            btn_down = QPushButton("下移")
            btn_down.setStyleSheet("font-size: 11px; padding: 2px 6px;")
            btn_down.clicked.connect(lambda checked, row=r: self._move_field_row(field_table, row, 1))
            
            btn_del = QPushButton("删")
            btn_del.setStyleSheet("font-size: 11px; padding: 2px 6px; background-color: #ef4444; color: white;")
            btn_del.clicked.connect(lambda checked, row=r: self._delete_field_row(field_table, row))
            
            btn_layout.addWidget(btn_up)
            btn_layout.addWidget(btn_down)
            btn_layout.addWidget(btn_del)
            field_table.setCellWidget(r, 3, btn_widget)
        
        combo_layout.addWidget(field_table)
        
        btn_add_field = QPushButton("+ 新增字段")
        btn_add_field.setStyleSheet("font-size: 11px; padding: 3px 7px;")
        btn_add_field.clicked.connect(lambda: self._add_field_row(field_table))
        combo_layout.addWidget(btn_add_field)
        
        return combo_frame
    
    def _move_field_row(self, table: QTableWidget, row: int, direction: int):
        """移动字段行"""
        new_row = row + direction
        if new_row < 0 or new_row >= table.rowCount():
            return
        
        for col in range(table.columnCount()):
            item1 = table.item(row, col) or table.cellWidget(row, col)
            item2 = table.item(new_row, col) or table.cellWidget(new_row, col)
            
            if isinstance(item1, QTableWidgetItem) and isinstance(item2, QTableWidgetItem):
                temp = item1.text()
                item1.setText(item2.text())
                item2.setText(temp)
        
        table.item(row, 0).setText(str(new_row + 1))
        table.item(new_row, 0).setText(str(row + 1))
        
        self._log(f"[Step2] 移动字段行 {row} -> {new_row}")
    
    def _delete_field_row(self, table: QTableWidget, row: int):
        """删除字段行"""
        if table.rowCount() <= 1:
            QMessageBox.warning(self, "提示", "至少保留一行。")
            return
        table.removeRow(row)
        for r in range(table.rowCount()):
            table.item(r, 0).setText(str(r + 1))
        self._log(f"[Step2] 删除字段行 {row}")
    
    def _add_field_row(self, table: QTableWidget):
        """添加字段行"""
        row = table.rowCount()
        table.insertRow(row)
        
        table.setItem(row, 0, QTableWidgetItem(str(row + 1)))
        table.item(row, 0).setFlags(safe_get_item_flag_enabled())
        table.setItem(row, 1, QTableWidgetItem(""))
        
        field_combo = QComboBox()
        field_combo.setEditable(True)
        field_combo.addItems(["std_city", "province", "community_name", "estate_name", 
                             "addr_detail", "door_info", "door_no", "street_name"])
        table.setCellWidget(row, 2, field_combo)
        
        btn_widget = QWidget()
        btn_layout = QHBoxLayout(btn_widget)
        btn_layout.setContentsMargins(2, 2, 2, 2)
        btn_layout.setSpacing(2)
        
        btn_up = QPushButton("上移")
        btn_up.setStyleSheet("font-size: 11px; padding: 2px 6px;")
        btn_up.clicked.connect(lambda checked, r=row: self._move_field_row(table, r, -1))
        
        btn_down = QPushButton("下移")
        btn_down.setStyleSheet("font-size: 11px; padding: 2px 6px;")
        btn_down.clicked.connect(lambda checked, r=row: self._move_field_row(table, r, 1))
        
        btn_del = QPushButton("删")
        btn_del.setStyleSheet("font-size: 11px; padding: 2px 6px; background-color: #ef4444; color: white;")
        btn_del.clicked.connect(lambda checked, r=row: self._delete_field_row(table, r))
        
        btn_layout.addWidget(btn_up)
        btn_layout.addWidget(btn_down)
        btn_layout.addWidget(btn_del)
        table.setCellWidget(row, 3, btn_widget)
        
        self._log(f"[Step2] 新增字段行")
    
    def _add_combo(self, file_id: str):
        """添加新组合"""
        if file_id not in self.file_combo_configs:
            self.file_combo_configs[file_id] = []
        
        new_combo = {
            "title": f"组合 {len(self.file_combo_configs[file_id]) + 1}",
            "subtitle": "",
            "fields": [{"role": "", "field": "std_city"}]
        }
        self.file_combo_configs[file_id].append(new_combo)
        self._refresh_file_config_display()
        self._log(f"[Step2] 新增字段组合（示意）")
    
    def _delete_combo(self, file_id: str, combo_idx: int):
        """删除组合"""
        if file_id in self.file_combo_configs and len(self.file_combo_configs[file_id]) > 1:
            self.file_combo_configs[file_id].pop(combo_idx)
            self._refresh_file_config_display()
            self._log(f"[Step2] 删除字段组合")
        else:
            QMessageBox.warning(self, "提示", "至少保留一个组合。")

