"""
Step4: 匹配任务管理Widget
按原型设计：任务组列表 + 当前任务组配置
"""
from typing import Callable, Dict, Optional, List
from qgis.PyQt.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTableWidget, QTableWidgetItem, QCheckBox,
    QProgressBar, QAbstractItemView, QHeaderView, QTextEdit
)
from qgis.PyQt.QtGui import QColor
from qgis.PyQt.QtCore import Qt
from ..utils import safe_select_rows
from ..widgets.base_step_widget import BaseStepWidget
from ..collapsible_section import CollapsibleSection
from ..widgets.no_wheel_combo_box import NoWheelComboBox


class Step4Widget(BaseStepWidget):
    """Step4: 匹配任务管理"""
    
    def __init__(self, parent=None, log_callback: Optional[Callable[[str, str], None]] = None, 
                 task_manager=None, open_filter_modal: Optional[Callable[[str], None]] = None,
                 open_match_modal: Optional[Callable[[str], None]] = None,
                 global_config=None):
        self.open_filter_modal = open_filter_modal or (lambda x: None)
        self.open_match_modal = open_match_modal or (lambda x: None)
        self.global_config = global_config
        self._task_groups: List[Dict] = []
        self._current_group_id = None
        super().__init__(parent, log_callback, task_manager)
        self._build_ui()
        self._load_demo_data()
    
    def _build_ui(self):
        """构建UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 6, 0, 6)
        layout.setSpacing(12)
        
        layout.addWidget(self._card_task_groups())
        layout.addWidget(self._card_group_config())
        layout.addStretch(1)
    
    def _card_task_groups(self) -> QWidget:
        """匹配任务组列表（多源表）"""
        section = CollapsibleSection("匹配任务组列表（多源表）", expanded=True)
        
        content = QWidget()
        v = QVBoxLayout(content)
        v.setContentsMargins(16, 12, 16, 12)
        v.setSpacing(8)
        
        tip = QLabel("每个任务组定义：一个源表 → 若干目标表（带优先级）。任务组之间可以并行执行。")
        tip.setWordWrap(True)
        tip.setObjectName("step4_tip")
        v.addWidget(tip)
        
        # 任务组表格
        self.task_groups_table = QTableWidget(0, 7)
        self.task_groups_table.setObjectName("step4_task_table")
        self.task_groups_table.setHorizontalHeaderLabels([
            "启用", "任务组名称", "源表", "目标表数量", "状态", "进度", "操作"
        ])
        self.task_groups_table.setMinimumHeight(140)
        self.task_groups_table.verticalHeader().setDefaultSectionSize(50)
        self.task_groups_table.verticalHeader().setVisible(False)
        
        header = self.task_groups_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(0, 40)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(3, 80)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(4, 70)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(5, 100)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(6, 180)
        
        v.addWidget(self.task_groups_table)
        
        btn_add = QPushButton("+ 新增任务组")
        btn_add.setObjectName("step4_btn_add")
        btn_add.clicked.connect(self._add_task_group)
        v.addWidget(btn_add)
        
        section.add_widget(content)
        return section
    
    def _card_group_config(self) -> QWidget:
        """当前任务组配置"""
        self.config_section = CollapsibleSection("当前任务组配置", expanded=True)
        
        content = QWidget()
        v = QVBoxLayout(content)
        v.setContentsMargins(16, 12, 16, 12)
        v.setSpacing(10)
        
        # 源表配置
        src_row = QHBoxLayout()
        src_row.addWidget(QLabel("源表（From，仅一个）:"))
        self.combo_src_table = NoWheelComboBox()
        self.combo_src_table.setMinimumWidth(300)
        src_row.addWidget(self.combo_src_table)
        src_row.addStretch()
        v.addLayout(src_row)
        
        # 源表过滤条件
        v.addWidget(QLabel("源表过滤条件（可多条，类似 WHERE）:"))
        
        self.src_cond_table = QTableWidget(0, 5)
        self.src_cond_table.setObjectName("step4_cond_table")
        self.src_cond_table.setHorizontalHeaderLabels(["字段", "运算符", "值", "逻辑", "操作"])
        self.src_cond_table.setMinimumHeight(80)
        self.src_cond_table.setMaximumHeight(120)
        self.src_cond_table.verticalHeader().setDefaultSectionSize(32)
        self.src_cond_table.verticalHeader().setVisible(False)
        
        cond_header = self.src_cond_table.horizontalHeader()
        cond_header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        cond_header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        cond_header.resizeSection(1, 80)
        cond_header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        cond_header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        cond_header.resizeSection(3, 70)
        cond_header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        cond_header.resizeSection(4, 50)
        
        v.addWidget(self.src_cond_table)
        
        btn_add_cond = QPushButton("+ 新增条件")
        btn_add_cond.setObjectName("step4_btn_secondary")
        btn_add_cond.clicked.connect(self._add_src_cond_row)
        v.addWidget(btn_add_cond)
        
        # 说明/备注
        remark_row = QHBoxLayout()
        remark_row.addWidget(QLabel("说明/备注:"))
        remark_row.addStretch()
        v.addLayout(remark_row)
        
        self.txt_remark = QTextEdit()
        self.txt_remark.setMaximumHeight(60)
        self.txt_remark.setPlaceholderText("输入任务组说明...")
        v.addWidget(self.txt_remark)
        
        # 目标表列表
        v.addWidget(QLabel("目标表列表（优先级从上到下）:"))
        
        self.tgt_table = QTableWidget(0, 6)
        self.tgt_table.setObjectName("step4_target_table")
        self.tgt_table.setHorizontalHeaderLabels([
            "序", "目标表", "过滤条件", "字段匹配对", "匹配方式说明", "操作"
        ])
        self.tgt_table.setMinimumHeight(120)
        self.tgt_table.verticalHeader().setDefaultSectionSize(36)
        self.tgt_table.verticalHeader().setVisible(False)
        
        tgt_header = self.tgt_table.horizontalHeader()
        tgt_header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        tgt_header.resizeSection(0, 35)
        tgt_header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        tgt_header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        tgt_header.resizeSection(2, 90)
        tgt_header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        tgt_header.resizeSection(3, 100)
        tgt_header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        tgt_header.setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)
        tgt_header.resizeSection(5, 100)
        
        v.addWidget(self.tgt_table)
        
        btn_add_target = QPushButton("+ 新增目标表")
        btn_add_target.setObjectName("step4_btn_add")
        btn_add_target.clicked.connect(self._add_target_row)
        v.addWidget(btn_add_target)
        
        self.config_section.add_widget(content)
        return self.config_section
    
    def _load_demo_data(self):
        """加载示例数据"""
        self._task_groups = [
            {
                "id": "g1",
                "name": "任务组1：客户地址 ↔ 门牌库 & 小区库",
                "enabled": True,
                "source": "客户采集数据_2025Q1_std.csv",
                "source_conditions": [
                    {"field": "cust_district", "op": "=", "value": "鼓楼区", "logic": "AND"}
                ],
                "remark": "示例：\n1）只匹配鼓楼区的居民/商业客户；\n2）先用门牌库匹配，剩余未命中再用小区库；",
                "targets": [
                    {"table": "门牌库_市政_std.csv", "match_desc": "std_full_addr ↔ mp_full_addr"},
                    {"table": "小区地址库_std.xlsx", "match_desc": "community_name ↔ community_name"}
                ],
                "status": "未执行",
                "progress": 0
            },
            {
                "id": "g2",
                "name": "任务组2：补录地址 ↔ 小区库 & GIS",
                "enabled": True,
                "source": "补录地址库_std.csv",
                "source_conditions": [],
                "remark": "",
                "targets": [
                    {"table": "小区地址库_std.xlsx", "match_desc": ""},
                    {"table": "GIS_小区点位_std.shp", "match_desc": ""}
                ],
                "status": "未执行",
                "progress": 0
            }
        ]
        
        # 初始化源表下拉框
        self.combo_src_table.clear()
        self.combo_src_table.addItems([
            "客户采集数据_2025Q1_std.csv",
            "补录地址库_std.csv",
            "小区地址库_std.xlsx"
        ])
        
        self._refresh_task_groups_table()
        
        # 默认显示第一个任务组配置
        if self._task_groups:
            self._open_group_config(self._task_groups[0]["id"])
    
    def _refresh_task_groups_table(self):
        """刷新任务组列表"""
        self.task_groups_table.setRowCount(len(self._task_groups))
        
        for r, group in enumerate(self._task_groups):
            gid = group["id"]
            
            # 启用复选框
            chk = QCheckBox()
            chk.setChecked(group.get("enabled", True))
            chk_widget = QWidget()
            chk_layout = QHBoxLayout(chk_widget)
            chk_layout.addWidget(chk)
            chk_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            chk_layout.setContentsMargins(0, 0, 0, 0)
            self.task_groups_table.setCellWidget(r, 0, chk_widget)
            
            # 任务组名称
            self.task_groups_table.setItem(r, 1, QTableWidgetItem(group["name"]))
            
            # 源表
            self.task_groups_table.setItem(r, 2, QTableWidgetItem(group["source"]))
            
            # 目标表数量
            self.task_groups_table.setItem(r, 3, QTableWidgetItem(str(len(group.get("targets", [])))))
            
            # 状态
            status = group.get("status", "未执行")
            status_item = QTableWidgetItem(status)
            self.task_groups_table.setItem(r, 4, status_item)
            
            # 进度条
            bar = QProgressBar()
            bar.setValue(group.get("progress", 0))
            bar.setTextVisible(False)
            bar.setMaximumHeight(10)
            self.task_groups_table.setCellWidget(r, 5, bar)
            
            # 操作列
            op_widget = QWidget()
            op_layout = QVBoxLayout(op_widget)
            op_layout.setContentsMargins(2, 2, 2, 2)
            op_layout.setSpacing(2)
            
            # 进度标签
            lbl = QLabel("空闲" if group.get("progress", 0) == 0 else f"{group.get('progress', 0)}%")
            lbl.setStyleSheet("font-size: 10px; color: #6b7280;")
            op_layout.addWidget(lbl)
            
            # 按钮行
            btn_row = QHBoxLayout()
            btn_row.setSpacing(2)
            
            btn_run = QPushButton("执行")
            btn_run.setObjectName("step4_btn_small_run")
            btn_run.clicked.connect(lambda checked, g=gid: self._run_task_group(g))
            btn_row.addWidget(btn_run)
            
            btn_pause = QPushButton("暂停")
            btn_pause.setObjectName("step4_btn_small")
            btn_pause.clicked.connect(lambda checked, g=gid: self._pause_task_group(g))
            btn_row.addWidget(btn_pause)
            
            btn_stop = QPushButton("终止")
            btn_stop.setObjectName("step4_btn_small_del")
            btn_stop.clicked.connect(lambda checked, g=gid: self._stop_task_group(g))
            btn_row.addWidget(btn_stop)
            
            op_layout.addLayout(btn_row)
            
            # 配置链接
            btn_config = QPushButton("配置")
            btn_config.setObjectName("step4_btn_link")
            btn_config.clicked.connect(lambda checked, g=gid: self._open_group_config(g))
            op_layout.addWidget(btn_config)
            
            self.task_groups_table.setCellWidget(r, 6, op_widget)
    
    def _open_group_config(self, group_id: str):
        """打开任务组配置"""
        self._current_group_id = group_id
        group = None
        for g in self._task_groups:
            if g["id"] == group_id:
                group = g
                break
        
        if not group:
            return
        
        # 更新标题
        self.config_section.set_title(f"当前任务组配置：{group['name']}")
        
        # 更新源表
        idx = self.combo_src_table.findText(group.get("source", ""))
        if idx >= 0:
            self.combo_src_table.setCurrentIndex(idx)
        
        # 更新源表过滤条件
        conditions = group.get("source_conditions", [])
        self.src_cond_table.setRowCount(len(conditions))
        for r, cond in enumerate(conditions):
            self.src_cond_table.setItem(r, 0, QTableWidgetItem(cond.get("field", "")))
            
            op_combo = NoWheelComboBox()
            op_combo.addItems(["=", "IN", "LIKE", "!=", ">", "<"])
            op_combo.setCurrentText(cond.get("op", "="))
            self.src_cond_table.setCellWidget(r, 1, op_combo)
            
            self.src_cond_table.setItem(r, 2, QTableWidgetItem(cond.get("value", "")))
            
            logic_combo = NoWheelComboBox()
            logic_combo.addItems(["AND", "OR"])
            logic_combo.setCurrentText(cond.get("logic", "AND"))
            self.src_cond_table.setCellWidget(r, 3, logic_combo)
            
            btn_del = QPushButton("删")
            btn_del.setObjectName("step4_btn_small_del")
            btn_del.clicked.connect(lambda checked, row=r: self._del_src_cond_row(row))
            self.src_cond_table.setCellWidget(r, 4, btn_del)
        
        # 更新备注
        self.txt_remark.setPlainText(group.get("remark", ""))
        
        # 更新目标表列表
        targets = group.get("targets", [])
        self.tgt_table.setRowCount(len(targets))
        for r, target in enumerate(targets):
            self.tgt_table.setItem(r, 0, QTableWidgetItem(str(r + 1)))
            
            tgt_combo = NoWheelComboBox()
            tgt_combo.setEditable(True)
            tgt_combo.addItems(["门牌库_市政_std.csv", "小区地址库_std.xlsx", "GIS_小区点位_std.shp"])
            tgt_combo.setCurrentText(target.get("table", ""))
            self.tgt_table.setCellWidget(r, 1, tgt_combo)
            
            btn_filter = QPushButton("配置过滤条件")
            btn_filter.setObjectName("step4_btn_link")
            btn_filter.clicked.connect(lambda checked, t=target.get("table", ""): self.open_filter_modal(t))
            self.tgt_table.setCellWidget(r, 2, btn_filter)
            
            btn_match = QPushButton("配置字段匹配对")
            btn_match.setObjectName("step4_btn_link")
            btn_match.clicked.connect(lambda checked, t=target.get("table", ""): self.open_match_modal(t))
            self.tgt_table.setCellWidget(r, 3, btn_match)
            
            desc_item = QTableWidgetItem(target.get("match_desc", ""))
            desc_item.setForeground(QColor("#6b7280"))
            self.tgt_table.setItem(r, 4, desc_item)
            
            # 操作按钮
            op_widget = QWidget()
            op_layout = QHBoxLayout(op_widget)
            op_layout.setContentsMargins(2, 2, 2, 2)
            op_layout.setSpacing(2)
            
            btn_up = QPushButton("上")
            btn_up.setObjectName("step4_btn_tiny")
            btn_up.clicked.connect(lambda checked, row=r: self._move_target_row(row, -1))
            op_layout.addWidget(btn_up)
            
            btn_down = QPushButton("下")
            btn_down.setObjectName("step4_btn_tiny")
            btn_down.clicked.connect(lambda checked, row=r: self._move_target_row(row, 1))
            op_layout.addWidget(btn_down)
            
            btn_del = QPushButton("删")
            btn_del.setObjectName("step4_btn_tiny_del")
            btn_del.clicked.connect(lambda checked, row=r: self._del_target_row(row))
            op_layout.addWidget(btn_del)
            
            self.tgt_table.setCellWidget(r, 5, op_widget)
        
        self._log(f"[Step4] 打开 {group_id} 配置", "info")
    
    def _add_task_group(self):
        """新增任务组"""
        new_id = f"g{len(self._task_groups) + 1}"
        new_group = {
            "id": new_id,
            "name": f"新任务组{len(self._task_groups) + 1}",
            "enabled": True,
            "source": "",
            "source_conditions": [],
            "remark": "",
            "targets": [],
            "status": "未配置",
            "progress": 0
        }
        self._task_groups.append(new_group)
        self._refresh_task_groups_table()
        self._open_group_config(new_id)
        self._log(f"[Step4] 新增任务组: {new_group['name']}", "info")
    
    def _run_task_group(self, group_id: str):
        """执行任务组"""
        for group in self._task_groups:
            if group["id"] == group_id:
                group["status"] = "执行中"
                self._log(f"[Step4] 开始执行任务组: {group['name']}", "info")
                break
        self._refresh_task_groups_table()
    
    def _pause_task_group(self, group_id: str):
        """暂停任务组"""
        for group in self._task_groups:
            if group["id"] == group_id:
                group["status"] = "已暂停"
                self._log(f"[Step4] 暂停任务组: {group['name']}", "warn")
                break
        self._refresh_task_groups_table()
    
    def _stop_task_group(self, group_id: str):
        """终止任务组"""
        for group in self._task_groups:
            if group["id"] == group_id:
                group["status"] = "已终止"
                group["progress"] = 0
                self._log(f"[Step4] 终止任务组: {group['name']}", "warn")
                break
        self._refresh_task_groups_table()
    
    def _add_src_cond_row(self):
        """添加源表过滤条件行"""
        row = self.src_cond_table.rowCount()
        self.src_cond_table.insertRow(row)
        
        self.src_cond_table.setItem(row, 0, QTableWidgetItem(""))
        
        op_combo = NoWheelComboBox()
        op_combo.addItems(["=", "IN", "LIKE", "!=", ">", "<"])
        self.src_cond_table.setCellWidget(row, 1, op_combo)
        
        self.src_cond_table.setItem(row, 2, QTableWidgetItem(""))
        
        logic_combo = NoWheelComboBox()
        logic_combo.addItems(["AND", "OR"])
        self.src_cond_table.setCellWidget(row, 3, logic_combo)
        
        btn_del = QPushButton("删")
        btn_del.setObjectName("step4_btn_small_del")
        btn_del.clicked.connect(lambda checked, r=row: self._del_src_cond_row(r))
        self.src_cond_table.setCellWidget(row, 4, btn_del)
    
    def _del_src_cond_row(self, row: int):
        """删除源表过滤条件行"""
        # 获取当前行的按钮
        sender = self.sender()
        if sender:
            # 查找按钮所在的行
            for r in range(self.src_cond_table.rowCount()):
                widget = self.src_cond_table.cellWidget(r, 4)
                if widget is sender:
                    row = r
                    break
        
        self.src_cond_table.removeRow(row)
    
    def _add_target_row(self):
        """添加目标表行"""
        row = self.tgt_table.rowCount()
        self.tgt_table.insertRow(row)
        
        self.tgt_table.setItem(row, 0, QTableWidgetItem(str(row + 1)))
        
        tgt_combo = NoWheelComboBox()
        tgt_combo.setEditable(True)
        tgt_combo.addItems(["门牌库_市政_std.csv", "小区地址库_std.xlsx", "GIS_小区点位_std.shp"])
        self.tgt_table.setCellWidget(row, 1, tgt_combo)
        
        btn_filter = QPushButton("配置过滤条件")
        btn_filter.setObjectName("step4_btn_link")
        btn_filter.clicked.connect(lambda checked: self.open_filter_modal("新目标表"))
        self.tgt_table.setCellWidget(row, 2, btn_filter)
        
        btn_match = QPushButton("配置字段匹配对")
        btn_match.setObjectName("step4_btn_link")
        btn_match.clicked.connect(lambda checked: self.open_match_modal("新目标表"))
        self.tgt_table.setCellWidget(row, 3, btn_match)
        
        self.tgt_table.setItem(row, 4, QTableWidgetItem(""))
        
        op_widget = QWidget()
        op_layout = QHBoxLayout(op_widget)
        op_layout.setContentsMargins(2, 2, 2, 2)
        op_layout.setSpacing(2)
        
        btn_up = QPushButton("上")
        btn_up.setObjectName("step4_btn_tiny")
        btn_up.clicked.connect(lambda checked, r=row: self._move_target_row(r, -1))
        op_layout.addWidget(btn_up)
        
        btn_down = QPushButton("下")
        btn_down.setObjectName("step4_btn_tiny")
        btn_down.clicked.connect(lambda checked, r=row: self._move_target_row(r, 1))
        op_layout.addWidget(btn_down)
        
        btn_del = QPushButton("删")
        btn_del.setObjectName("step4_btn_tiny_del")
        btn_del.clicked.connect(lambda checked, r=row: self._del_target_row(r))
        op_layout.addWidget(btn_del)
        
        self.tgt_table.setCellWidget(row, 5, op_widget)
        
        self._log("[Step4] 添加目标表", "info")
    
    def _move_target_row(self, row: int, direction: int):
        """移动目标表行"""
        # 获取当前行的按钮
        sender = self.sender()
        if sender:
            # 查找按钮所在的行
            for r in range(self.tgt_table.rowCount()):
                widget = self.tgt_table.cellWidget(r, 5)
                if widget:
                    for child in widget.findChildren(QPushButton):
                        if child is sender:
                            row = r
                            break
        
        new_row = row + direction
        if new_row < 0 or new_row >= self.tgt_table.rowCount():
            return
        
        # 更新数据模型
        if self._current_group_id:
            for group in self._task_groups:
                if group["id"] == self._current_group_id:
                    targets = group.get("targets", [])
                    if 0 <= row < len(targets) and 0 <= new_row < len(targets):
                        targets[row], targets[new_row] = targets[new_row], targets[row]
                        self._open_group_config(self._current_group_id)
                        self._log(f"[Step4] 移动目标表行 {row+1} -> {new_row+1}", "info")
                    break
    
    def _del_target_row(self, row: int):
        """删除目标表行"""
        # 获取当前行的按钮
        sender = self.sender()
        if sender:
            # 查找按钮所在的行
            for r in range(self.tgt_table.rowCount()):
                widget = self.tgt_table.cellWidget(r, 5)
                if widget:
                    for child in widget.findChildren(QPushButton):
                        if child is sender:
                            row = r
                            break
        
        # 更新数据模型
        if self._current_group_id:
            for group in self._task_groups:
                if group["id"] == self._current_group_id:
                    targets = group.get("targets", [])
                    if 0 <= row < len(targets):
                        del targets[row]
                        self._open_group_config(self._current_group_id)
                        self._log(f"[Step4] 删除目标表行 {row+1}", "info")
                    break
