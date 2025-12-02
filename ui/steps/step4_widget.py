"""
Step4: 匹配任务管理Widget
左右分栏布局：左侧任务组列表 + 右侧任务组配置详情
"""
import os
from typing import Callable, Dict, Optional, List
from qgis.PyQt.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTableWidget, QTableWidgetItem, QCheckBox,
    QProgressBar, QHeaderView, QSplitter, QAbstractItemView,
    QListWidget, QListWidgetItem, QFrame, QGroupBox
)
from qgis.PyQt.QtGui import QColor
from qgis.PyQt.QtCore import Qt
from ..widgets.base_step_widget import BaseStepWidget
from ..widgets.no_wheel_combo_box import NoWheelComboBox


class Step4Widget(BaseStepWidget):
    """Step4: 匹配任务管理 - 左右分栏布局"""
    
    def __init__(self, parent=None, log_callback: Optional[Callable[[str, str], None]] = None, 
                 task_manager=None, open_filter_modal: Optional[Callable[[str], None]] = None,
                 open_match_modal: Optional[Callable[[str], None]] = None,
                 global_config=None):
        self.open_filter_modal = open_filter_modal or (lambda x: None)
        self.open_match_modal = open_match_modal or (lambda x: None)
        self.global_config = global_config
        self._task_groups: List[Dict] = []
        self._current_group_idx = -1
        self._available_files: List[str] = []  # 可用文件列表
        super().__init__(parent, log_callback, task_manager)
        self._build_ui()
        self._load_available_files()
        self._load_demo_data()
    
    def _get_global_config(self):
        """获取全局配置组件"""
        if self.global_config:
            return self.global_config
        parent = self.parent()
        while parent:
            if hasattr(parent, 'global_config'):
                return parent.global_config
            parent = parent.parent()
        return None
    
    def _load_available_files(self):
        """从全局配置加载可用文件列表"""
        self._available_files = []
        
        global_config = self._get_global_config()
        if not global_config:
            self._log("[Step4] 未获取到全局配置", "warning")
            return
        
        region_info = global_config.get_region_info()
        customer_folder = region_info.get('customer_folder', '')
        shp_folder = region_info.get('shp_folder', '')
        
        # 扫描客户数据文件夹
        if customer_folder and os.path.isdir(customer_folder):
            for f in os.listdir(customer_folder):
                if f.lower().endswith(('.csv', '.xlsx', '.xls')):
                    self._available_files.append(f)
        
        # 扫描SHP数据文件夹
        if shp_folder and os.path.isdir(shp_folder):
            for f in os.listdir(shp_folder):
                if f.lower().endswith(('.csv', '.xlsx', '.xls')):
                    self._available_files.append(f)
        
        self._log(f"[Step4] 加载可用文件: {len(self._available_files)} 个", "info")
        
        # 更新下拉框
        self._update_file_combos()
    
    def _update_file_combos(self):
        """更新源表和目标表的下拉框选项"""
        if hasattr(self, 'combo_src'):
            current_src = self.combo_src.currentText()
            self.combo_src.clear()
            self.combo_src.addItems(self._available_files)
            if current_src in self._available_files:
                self.combo_src.setCurrentText(current_src)
    
    def _build_ui(self):
        """构建UI - 左右分栏"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # 使用 QSplitter 实现左右分栏
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setObjectName("step4_splitter")
        
        # 左侧面板：任务组列表
        left_panel = self._build_left_panel()
        left_panel.setMinimumWidth(240)
        left_panel.setMaximumWidth(340)
        splitter.addWidget(left_panel)
        
        # 右侧面板：任务组配置详情
        right_panel = self._build_right_panel()
        splitter.addWidget(right_panel)
        
        # 设置初始比例
        splitter.setSizes([280, 720])
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        
        layout.addWidget(splitter)
    
    def _build_left_panel(self) -> QWidget:
        """构建左侧面板：任务组列表"""
        panel = QFrame()
        panel.setObjectName("step4_left_panel")
        
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)
        
        # 标题
        title = QLabel("任务组列表")
        title.setObjectName("step4_panel_title")
        layout.addWidget(title)
        
        # 任务组列表
        self.task_list = QListWidget()
        self.task_list.setObjectName("step4_task_list")
        self.task_list.currentRowChanged.connect(self._on_task_selected)
        layout.addWidget(self.task_list, 1)
        
        # 新增按钮
        btn_add = QPushButton("+ 新增任务组")
        btn_add.setObjectName("step4_btn_add")
        btn_add.clicked.connect(self._add_task_group)
        layout.addWidget(btn_add)
        
        # 分隔线
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setObjectName("step4_separator")
        layout.addWidget(line)
        
        # 批量操作
        batch_label = QLabel("批量操作")
        batch_label.setObjectName("step4_batch_label")
        layout.addWidget(batch_label)
        
        btn_run_all = QPushButton("执行选中")
        btn_run_all.setObjectName("step4_btn_batch_run")
        btn_run_all.clicked.connect(self._run_selected_groups)
        layout.addWidget(btn_run_all)
        
        btn_stop_all = QPushButton("全部终止")
        btn_stop_all.setObjectName("step4_btn_batch_stop")
        btn_stop_all.clicked.connect(self._stop_all_groups)
        layout.addWidget(btn_stop_all)
        
        return panel
    
    def _build_right_panel(self) -> QWidget:
        """构建右侧面板：任务组配置详情"""
        panel = QFrame()
        panel.setObjectName("step4_right_panel")
        
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(12)
        
        # 标题
        self.config_title = QLabel("请选择一个任务组")
        self.config_title.setObjectName("step4_config_title")
        layout.addWidget(self.config_title)
        
        # 配置内容容器
        self.config_container = QWidget()
        self.config_container.setVisible(False)
        config_layout = QVBoxLayout(self.config_container)
        config_layout.setContentsMargins(0, 0, 0, 0)
        config_layout.setSpacing(12)
        
        # ===== 源表配置区域 =====
        src_group = QGroupBox("源表配置 (From)")
        src_group.setObjectName("step4_group")
        src_layout = QVBoxLayout(src_group)
        src_layout.setSpacing(10)
        
        # 源表选择行
        src_row = QHBoxLayout()
        lbl_src = QLabel("源表:")
        lbl_src.setMinimumWidth(70)
        src_row.addWidget(lbl_src)
        self.combo_src = NoWheelComboBox()
        self.combo_src.setObjectName("step4_combo")
        self.combo_src.setMinimumHeight(32)
        src_row.addWidget(self.combo_src, 1)
        src_layout.addLayout(src_row)
        
        # 过滤条件行
        filter_row = QHBoxLayout()
        lbl_filter = QLabel("过滤条件:")
        lbl_filter.setMinimumWidth(70)
        filter_row.addWidget(lbl_filter)
        self.lbl_src_filter = QLabel("无")
        self.lbl_src_filter.setObjectName("step4_filter_status")
        self.lbl_src_filter.setMinimumHeight(28)
        filter_row.addWidget(self.lbl_src_filter, 1)
        btn_src_filter = QPushButton("设置过滤条件...")
        btn_src_filter.setObjectName("step4_btn_config")
        btn_src_filter.setMinimumHeight(28)
        btn_src_filter.clicked.connect(self._open_src_filter_dialog)
        filter_row.addWidget(btn_src_filter)
        src_layout.addLayout(filter_row)
        
        config_layout.addWidget(src_group)
        
        # ===== 目标表列表区域 =====
        tgt_group = QGroupBox("目标表列表 (To, 按优先级排序)")
        tgt_group.setObjectName("step4_group")
        tgt_layout = QVBoxLayout(tgt_group)
        tgt_layout.setSpacing(10)
        
        # 目标表表格 - 6列
        self.tgt_table = QTableWidget(0, 6)
        self.tgt_table.setObjectName("step4_target_table")
        self.tgt_table.setHorizontalHeaderLabels([
            "序", "目标表", "过滤条件", "匹配字段", "匹配方式说明", "操作"
        ])
        self.tgt_table.verticalHeader().setVisible(False)
        self.tgt_table.verticalHeader().setDefaultSectionSize(40)
        self.tgt_table.setMinimumHeight(180)
        self.tgt_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tgt_table.setAlternatingRowColors(True)
        
        header = self.tgt_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(0, 30)  # 序
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)  # 目标表
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(2, 60)  # 过滤条件
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(3, 60)  # 匹配字段
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)  # 匹配方式说明
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(5, 90)  # 操作
        
        tgt_layout.addWidget(self.tgt_table)
        
        # 新增目标表按钮
        btn_add_tgt = QPushButton("+ 新增目标表")
        btn_add_tgt.setObjectName("step4_btn_add_target")
        btn_add_tgt.clicked.connect(self._add_target_row)
        tgt_layout.addWidget(btn_add_tgt)
        
        config_layout.addWidget(tgt_group, 1)
        
        # ===== 备注区域 =====
        remark_row = QHBoxLayout()
        lbl_remark = QLabel("备注:")
        lbl_remark.setMinimumWidth(70)
        remark_row.addWidget(lbl_remark)
        self.txt_remark = QLineEdit()
        self.txt_remark.setObjectName("step4_remark")
        self.txt_remark.setMinimumHeight(32)
        self.txt_remark.setPlaceholderText("输入任务组说明...")
        remark_row.addWidget(self.txt_remark, 1)
        config_layout.addLayout(remark_row)
        
        # ===== 操作按钮区域 =====
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        
        btn_save = QPushButton("保存配置")
        btn_save.setObjectName("step4_btn_save")
        btn_save.setMinimumHeight(36)
        btn_save.clicked.connect(self._save_current_config)
        btn_row.addWidget(btn_save)
        
        btn_run = QPushButton("执行任务")
        btn_run.setObjectName("step4_btn_run")
        btn_run.setMinimumHeight(36)
        btn_run.clicked.connect(self._run_current_group)
        btn_row.addWidget(btn_run)
        
        btn_delete = QPushButton("删除任务组")
        btn_delete.setObjectName("step4_btn_delete")
        btn_delete.setMinimumHeight(36)
        btn_delete.clicked.connect(self._delete_current_group)
        btn_row.addWidget(btn_delete)
        
        config_layout.addLayout(btn_row)
        
        layout.addWidget(self.config_container, 1)
        
        # 空状态提示
        self.empty_hint = QLabel("← 请从左侧选择或新建一个任务组")
        self.empty_hint.setObjectName("step4_empty_hint")
        self.empty_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.empty_hint, 1)
        
        return panel
    
    def _load_demo_data(self):
        """初始化任务组数据"""
        # 初始化为空列表，由用户手动添加
        self._task_groups = []
        self._refresh_task_list()
    
    def _refresh_task_list(self):
        """刷新左侧任务组列表"""
        self.task_list.clear()
        
        for i, group in enumerate(self._task_groups):
            # 格式：任务名称 + 源表→目标数
            target_count = len(group.get("targets", []))
            source_name = group.get('source', '未配置')
            if len(source_name) > 20:
                source_name = source_name[:18] + "..."
            text = f"{group['name']}\n{source_name} → {target_count}个目标表\n[{group['status']}]"
            
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, i)
            
            # 根据状态设置颜色
            if group["status"] == "执行中":
                item.setForeground(QColor("#0284c7"))
            elif group["status"] == "已完成":
                item.setForeground(QColor("#16a34a"))
            elif group["status"] == "已终止":
                item.setForeground(QColor("#dc2626"))
            
            self.task_list.addItem(item)
        
        # 恢复选中状态
        if 0 <= self._current_group_idx < len(self._task_groups):
            self.task_list.setCurrentRow(self._current_group_idx)
    
    def _on_task_selected(self, row: int):
        """任务组选中事件"""
        if row < 0 or row >= len(self._task_groups):
            self._current_group_idx = -1
            self.config_container.setVisible(False)
            self.empty_hint.setVisible(True)
            self.config_title.setText("请选择一个任务组")
            return
        
        self._current_group_idx = row
        self._load_group_config(row)
    
    def _load_group_config(self, idx: int):
        """加载任务组配置到右侧面板"""
        if idx < 0 or idx >= len(self._task_groups):
            return
        
        group = self._task_groups[idx]
        
        # 显示配置面板
        self.config_container.setVisible(True)
        self.empty_hint.setVisible(False)
        
        # 更新标题
        self.config_title.setText(f"任务组配置：{group['name']}")
        
        # 更新源表
        src = group.get("source", "")
        if src in self._available_files:
            self.combo_src.setCurrentText(src)
        elif src:
            # 如果文件不在列表中，添加它
            self.combo_src.addItem(src)
            self.combo_src.setCurrentText(src)
        
        # 更新源表过滤条件
        src_filter = group.get("source_filter", "")
        self.lbl_src_filter.setText(src_filter if src_filter else "无")
        
        # 更新备注
        self.txt_remark.setText(group.get("remark", ""))
        
        # 更新目标表列表
        self._refresh_target_table(group.get("targets", []))
        
        self._log(f"[Step4] 加载任务组配置: {group['name']}", "info")
    
    def _refresh_target_table(self, targets: List[Dict]):
        """刷新目标表表格"""
        self.tgt_table.setRowCount(len(targets))
        
        for r, target in enumerate(targets):
            # 序号
            seq_item = QTableWidgetItem(str(r + 1))
            seq_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            seq_item.setFlags(seq_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.tgt_table.setItem(r, 0, seq_item)
            
            # 目标表（下拉框）
            combo = NoWheelComboBox()
            combo.setEditable(False)
            combo.addItems(self._available_files)
            tgt_table_name = target.get("table", "")
            if tgt_table_name and tgt_table_name in self._available_files:
                combo.setCurrentText(tgt_table_name)
            self.tgt_table.setCellWidget(r, 1, combo)
            
            # 过滤条件按钮
            filter_cond = target.get("filter", "")
            btn_filter = QPushButton("已设置" if filter_cond else "设置")
            btn_filter.setObjectName("step4_btn_set" if not filter_cond else "step4_btn_done")
            if filter_cond:
                btn_filter.setToolTip(filter_cond)
            btn_filter.clicked.connect(lambda checked, row=r: self._open_target_filter(row))
            self.tgt_table.setCellWidget(r, 2, btn_filter)
            
            # 匹配字段按钮
            match_fields = target.get("match_fields", "")
            btn_match = QPushButton(match_fields if match_fields else "设置")
            btn_match.setObjectName("step4_btn_set" if not match_fields else "step4_btn_done")
            btn_match.clicked.connect(lambda checked, row=r: self._open_target_match(row))
            self.tgt_table.setCellWidget(r, 3, btn_match)
            
            # 匹配方式说明
            desc = target.get("match_desc", "")
            desc_item = QTableWidgetItem(desc)
            desc_item.setForeground(QColor("#6b7280"))
            desc_item.setFlags(desc_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.tgt_table.setItem(r, 4, desc_item)
            
            # 操作按钮
            op_widget = QWidget()
            op_layout = QHBoxLayout(op_widget)
            op_layout.setContentsMargins(2, 2, 2, 2)
            op_layout.setSpacing(4)
            
            btn_up = QPushButton("上")
            btn_up.setObjectName("step4_btn_op")
            btn_up.setFixedWidth(28)
            btn_up.clicked.connect(lambda checked, row=r: self._move_target(row, -1))
            op_layout.addWidget(btn_up)
            
            btn_down = QPushButton("下")
            btn_down.setObjectName("step4_btn_op")
            btn_down.setFixedWidth(28)
            btn_down.clicked.connect(lambda checked, row=r: self._move_target(row, 1))
            op_layout.addWidget(btn_down)
            
            btn_del = QPushButton("删")
            btn_del.setObjectName("step4_btn_del")
            btn_del.setFixedWidth(28)
            btn_del.clicked.connect(lambda checked, row=r: self._delete_target(row))
            op_layout.addWidget(btn_del)
            
            self.tgt_table.setCellWidget(r, 5, op_widget)
    
    def _add_task_group(self):
        """新增任务组"""
        new_group = {
            "name": f"新任务组{len(self._task_groups) + 1}",
            "enabled": True,
            "source": "",
            "source_filter": "",
            "remark": "",
            "targets": [],
            "status": "待配置",
            "progress": 0
        }
        self._task_groups.append(new_group)
        self._refresh_task_list()
        
        # 选中新任务组
        self.task_list.setCurrentRow(len(self._task_groups) - 1)
        self._log(f"[Step4] 新增任务组: {new_group['name']}", "info")
    
    def _add_target_row(self):
        """新增目标表"""
        if self._current_group_idx < 0:
            return
        
        group = self._task_groups[self._current_group_idx]
        group["targets"].append({
            "table": "",
            "filter": "",
            "match_fields": "",
            "match_desc": ""
        })
        self._refresh_target_table(group["targets"])
        self._log("[Step4] 新增目标表", "info")
    
    def _move_target(self, row: int, direction: int):
        """移动目标表"""
        if self._current_group_idx < 0:
            return
        
        # 查找实际行号
        sender = self.sender()
        if sender:
            for r in range(self.tgt_table.rowCount()):
                widget = self.tgt_table.cellWidget(r, 5)
                if widget and sender in widget.findChildren(QPushButton):
                    row = r
                    break
        
        group = self._task_groups[self._current_group_idx]
        targets = group["targets"]
        new_row = row + direction
        
        if 0 <= new_row < len(targets):
            targets[row], targets[new_row] = targets[new_row], targets[row]
            self._refresh_target_table(targets)
            self._log(f"[Step4] 移动目标表 {row+1} → {new_row+1}", "info")
    
    def _delete_target(self, row: int):
        """删除目标表"""
        if self._current_group_idx < 0:
            return
        
        # 查找实际行号
        sender = self.sender()
        if sender:
            for r in range(self.tgt_table.rowCount()):
                widget = self.tgt_table.cellWidget(r, 5)
                if widget and sender in widget.findChildren(QPushButton):
                    row = r
                    break
        
        group = self._task_groups[self._current_group_idx]
        if 0 <= row < len(group["targets"]):
            del group["targets"][row]
            self._refresh_target_table(group["targets"])
            self._log(f"[Step4] 删除目标表 {row+1}", "info")
    
    def _open_src_filter_dialog(self):
        """打开源表过滤条件对话框"""
        if self._current_group_idx < 0:
            return
        # 直接从下拉框获取当前选择的源表（而不是从未保存的配置中获取）
        src_table = self.combo_src.currentText()
        if not src_table:
            self._log("[Step4] 请先选择源表", "warning")
            return
        condition = self.open_filter_modal(src_table)
        # 更新显示
        if condition:
            self.lbl_src_filter.setText(condition)
            # 保存到任务组配置
            self._task_groups[self._current_group_idx]["source_filter"] = condition
        else:
            self.lbl_src_filter.setText("无")
    
    def _open_target_filter(self, row: int):
        """打开目标表过滤条件对话框"""
        # 从表格中获取实际行的下拉框
        combo = self.tgt_table.cellWidget(row, 1)
        if combo:
            tgt_name = combo.currentText()
            if tgt_name:
                condition = self.open_filter_modal(tgt_name)
                # 更新按钮文字
                btn_filter = self.tgt_table.cellWidget(row, 2)
                if btn_filter and isinstance(btn_filter, QPushButton):
                    btn_filter.setText("已配置" if condition else "配置")
                # 保存到任务组配置
                if self._current_group_idx >= 0:
                    targets = self._task_groups[self._current_group_idx].get("targets", [])
                    if 0 <= row < len(targets):
                        targets[row]["filter"] = condition or ""
            else:
                self._log("[Step4] 请先选择目标表", "warning")
    
    def _open_target_match(self, row: int):
        """打开目标表字段匹配对话框"""
        # 从表格中获取实际行的下拉框
        combo = self.tgt_table.cellWidget(row, 1)
        if combo:
            tgt_name = combo.currentText()
            if tgt_name:
                self.open_match_modal(tgt_name)
            else:
                self._log("[Step4] 请先选择目标表", "warning")
    
    def _save_current_config(self):
        """保存当前任务组配置"""
        if self._current_group_idx < 0:
            return
        
        group = self._task_groups[self._current_group_idx]
        group["source"] = self.combo_src.currentText()
        group["remark"] = self.txt_remark.text()
        
        # 更新目标表
        targets = []
        for r in range(self.tgt_table.rowCount()):
            combo = self.tgt_table.cellWidget(r, 1)
            desc_item = self.tgt_table.item(r, 4)
            if combo:
                targets.append({
                    "table": combo.currentText(),
                    "filter": "",
                    "match_fields": "",
                    "match_desc": desc_item.text() if desc_item else ""
                })
        group["targets"] = targets
        group["status"] = "待执行"
        
        self._refresh_task_list()
        self._log(f"[Step4] 保存任务组配置: {group['name']}", "info")
    
    def _run_current_group(self):
        """执行当前任务组"""
        if self._current_group_idx < 0:
            return
        
        group = self._task_groups[self._current_group_idx]
        group["status"] = "执行中"
        self._refresh_task_list()
        self._log(f"[Step4] 开始执行任务组: {group['name']}", "info")
    
    def _delete_current_group(self):
        """删除当前任务组"""
        if self._current_group_idx < 0:
            return
        
        group = self._task_groups[self._current_group_idx]
        del self._task_groups[self._current_group_idx]
        self._current_group_idx = -1
        self._refresh_task_list()
        
        # 隐藏配置面板
        self.config_container.setVisible(False)
        self.empty_hint.setVisible(True)
        self.config_title.setText("请选择一个任务组")
        
        self._log(f"[Step4] 删除任务组: {group['name']}", "info")
    
    def _run_selected_groups(self):
        """执行选中的任务组"""
        for group in self._task_groups:
            if group.get("enabled", True):
                group["status"] = "执行中"
        self._refresh_task_list()
        self._log("[Step4] 开始执行所有启用的任务组", "info")
    
    def _stop_all_groups(self):
        """终止所有任务组"""
        for group in self._task_groups:
            if group["status"] == "执行中":
                group["status"] = "已终止"
                group["progress"] = 0
        self._refresh_task_list()
        self._log("[Step4] 终止所有任务组", "warn")
    
    def showEvent(self, event):
        """显示时刷新文件列表"""
        super().showEvent(event)
        self._load_available_files()
