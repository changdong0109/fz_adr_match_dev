"""
Step4: 匹配任务管理Widget
左右分栏布局：左侧任务组列表 + 右侧任务组配置详情

产品化功能：
- 任务组配置持久化（保存到cache_folder/match_tasks.json）
- 支持匹配结果预览
- 使用 POIMatcher 作为核心匹配引擎
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

# 导入任务管理器
from ...core.match_executor import MatchTaskManager


class Step4Widget(BaseStepWidget):
    """Step4: 匹配任务管理 - 左右分栏布局"""
    
    def __init__(self, parent=None, log_callback: Optional[Callable[[str, str], None]] = None, 
                 task_manager=None, open_filter_modal: Optional[Callable[[str], str]] = None,
                 open_match_modal: Optional[Callable[[str, str], str]] = None,
                 global_config=None):
        self.open_filter_modal = open_filter_modal or (lambda x: "")
        self.open_match_modal = open_match_modal or (lambda x, y: "")
        self.global_config = global_config
        self._task_groups: List[Dict] = []
        self._current_group_idx = -1
        self._available_files: List[str] = []
        self._persist_manager: Optional[MatchTaskManager] = None
        super().__init__(parent, log_callback, task_manager)
        self._init_persist_manager()
        self._build_ui()
        self._load_available_files()
        self._load_persisted_tasks()
    
    def _init_persist_manager(self):
        """初始化任务持久化管理器"""
        if self._persist_manager:
            return  # 已初始化
        
        global_config = self._get_global_config()
        if global_config:
            region_info = global_config.get_region_info()
            cache_folder = region_info.get('cache_folder', '')
            if cache_folder:
                self._persist_manager = MatchTaskManager(global_config)
                self._log(f"[Step4] 任务持久化管理器初始化完成，缓存目录: {cache_folder}", "info")
            else:
                self._log("[Step4] 缓存目录未配置，任务组暂不持久化", "debug")
    
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
        """
        从全局配置加载可用文件列表
        
        只加载 Step3 标准化后的文件（*_标准化.csv），包含 POI 列
        """
        self._available_files = []
        self._file_paths = {}  # 文件名 -> 完整路径的映射
        
        global_config = self._get_global_config()
        if not global_config:
            self._log("[Step4] 未获取到全局配置", "warning")
            return
        
        region_info = global_config.get_region_info()
        base_folder = region_info.get('base_folder', '')
        province = region_info.get('province', '')
        city = region_info.get('city', '')
        county = region_info.get('county', '')
        
        region_prefix = f"{province}{city}{county}" if county else f"{province}{city}"
        
        # 只扫描标准化结果文件（Step3 解析后的文件）
        clean_folders = [
            os.path.join(base_folder, f"{region_prefix}_客户数据清洗", "清洗后数据"),
            os.path.join(base_folder, f"{region_prefix}_GIS数据清洗", "清洗后数据"),
        ]
        
        for folder in clean_folders:
            if os.path.isdir(folder):
                for f in os.listdir(folder):
                    # 只加载标准化文件
                    if f.lower().endswith('.csv') and '_标准化' in f:
                        full_path = os.path.join(folder, f)
                        if f not in self._file_paths:  # 避免重复
                            self._available_files.append(f)
                            self._file_paths[f] = full_path
        
        if self._available_files:
            self._log(f"[Step4] 加载 Step3 标准化结果: {len(self._available_files)} 个文件", "info")
        else:
            self._log("[Step4] ⚠️ 未找到标准化文件，请先在 Step3 执行解析", "warning")
        
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
        
        btn_export_all = QPushButton("批量导出")
        btn_export_all.setObjectName("step4_btn_batch_export")
        btn_export_all.setToolTip("导出所有已完成任务组的匹配结果")
        btn_export_all.clicked.connect(self._export_all_results)
        layout.addWidget(btn_export_all)
        
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
        
        # ===== 执行进度区域 =====
        progress_group = QGroupBox("执行进度")
        progress_group.setObjectName("step4_progress_group")
        progress_layout = QVBoxLayout(progress_group)
        progress_layout.setSpacing(8)
        
        # 进度条
        self.match_progress = QProgressBar()
        self.match_progress.setObjectName("step4_match_progress")
        self.match_progress.setMinimumHeight(24)
        self.match_progress.setValue(0)
        self.match_progress.setTextVisible(True)
        self.match_progress.setFormat("%p%")
        progress_layout.addWidget(self.match_progress)
        
        # 状态标签
        self.lbl_match_status = QLabel("就绪")
        self.lbl_match_status.setObjectName("step4_match_status")
        progress_layout.addWidget(self.lbl_match_status)
        
        config_layout.addWidget(progress_group)
        
        # ===== 操作按钮区域 =====
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        
        self.btn_save = QPushButton("保存配置")
        self.btn_save.setObjectName("step4_btn_save")
        self.btn_save.setMinimumHeight(36)
        self.btn_save.clicked.connect(self._save_current_config)
        btn_row.addWidget(self.btn_save)
        
        self.btn_preview = QPushButton("预览(10条)")
        self.btn_preview.setObjectName("step4_btn_preview")
        self.btn_preview.setMinimumHeight(36)
        self.btn_preview.setToolTip("匹配前10条记录预览，确认匹配逻辑是否正确")
        self.btn_preview.clicked.connect(self._preview_match)
        btn_row.addWidget(self.btn_preview)
        
        self.btn_run = QPushButton("执行任务")
        self.btn_run.setObjectName("step4_btn_run")
        self.btn_run.setMinimumHeight(36)
        self.btn_run.clicked.connect(self._run_current_group)
        btn_row.addWidget(self.btn_run)
        
        self.btn_export = QPushButton("导出结果")
        self.btn_export.setObjectName("step4_btn_export")
        self.btn_export.setMinimumHeight(36)
        self.btn_export.setToolTip("导出当前任务组的匹配结果")
        self.btn_export.clicked.connect(self._export_current_group_results)
        btn_row.addWidget(self.btn_export)
        
        self.btn_delete = QPushButton("删除任务组")
        self.btn_delete.setObjectName("step4_btn_delete")
        self.btn_delete.setMinimumHeight(36)
        self.btn_delete.clicked.connect(self._delete_current_group)
        btn_row.addWidget(self.btn_delete)
        
        config_layout.addLayout(btn_row)
        
        layout.addWidget(self.config_container, 1)
        
        # 空状态提示
        self.empty_hint = QLabel("← 请从左侧选择或新建一个任务组")
        self.empty_hint.setObjectName("step4_empty_hint")
        self.empty_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.empty_hint, 1)
        
        return panel
    
    def _load_persisted_tasks(self):
        """从持久化存储加载任务组数据"""
        if self._persist_manager:
            persisted = self._persist_manager.load_tasks()
            if persisted:
                self._task_groups = persisted
                self._log(f"[Step4] 加载已保存的任务组: {len(self._task_groups)} 个", "info")
            else:
                self._task_groups = []
        else:
            self._task_groups = []
        self._refresh_task_list()
    
    def _persist_tasks(self):
        """保存任务组到持久化存储"""
        if self._persist_manager:
            self._persist_manager.save_tasks(self._task_groups)
            self._log(f"[Step4] 已保存 {len(self._task_groups)} 个任务组到本地缓存", "debug")
        else:
            # 尝试重新初始化
            self._init_persist_manager()
            if self._persist_manager:
                self._persist_manager.save_tasks(self._task_groups)
                self._log(f"[Step4] 已保存 {len(self._task_groups)} 个任务组到本地缓存", "debug")
            else:
                self._log("[Step4] 无法保存任务组：持久化管理器未初始化", "warning")
    
    def _load_demo_data(self):
        """[兼容] 初始化任务组数据"""
        self._load_persisted_tasks()
    
    def _refresh_task_list(self):
        """刷新左侧任务组列表"""
        # 保存当前选中的索引（clear() 会触发 currentRowChanged(-1) 导致 _current_group_idx 被重置）
        saved_idx = self._current_group_idx
        
        # 阻止信号，避免 clear() 触发 _on_task_selected(-1) 导致选中状态丢失
        self.task_list.blockSignals(True)
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
            elif group["status"] == "失败":
                item.setForeground(QColor("#dc2626"))
            
            self.task_list.addItem(item)
        
        self.task_list.blockSignals(False)
        
        # 恢复选中状态（使用保存的索引）
        if 0 <= saved_idx < len(self._task_groups):
            self.task_list.setCurrentRow(saved_idx)
            self._current_group_idx = saved_idx
    
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
        self._persist_tasks()  # 持久化
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
        # 直接从下拉框获取当前选择的源表
        src_table = self.combo_src.currentText()
        if not src_table:
            self._log("[Step4] 请先选择源表", "warning")
            return
        # 使用前缀区分源表和目标表的条件（避免同名文件条件混淆）
        filter_key = f"[源表]{src_table}"
        condition = self.open_filter_modal(filter_key)
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
                # 使用前缀区分目标表的条件
                filter_key = f"[目标表{row+1}]{tgt_name}"
                condition = self.open_filter_modal(filter_key)
                # 更新按钮文字
                btn_filter = self.tgt_table.cellWidget(row, 2)
                if btn_filter and isinstance(btn_filter, QPushButton):
                    btn_filter.setText("已设置" if condition else "设置")
                # 保存到任务组配置
                if self._current_group_idx >= 0:
                    targets = self._task_groups[self._current_group_idx].get("targets", [])
                    if 0 <= row < len(targets):
                        targets[row]["filter"] = condition or ""
            else:
                self._log("[Step4] 请先选择目标表", "warning")
    
    def _open_target_match(self, row: int):
        """打开目标表字段关联对话框"""
        if self._current_group_idx < 0:
            return
        
        # 获取源表名称
        src_name = self.combo_src.currentText()
        if not src_name:
            self._log("[Step4] 请先选择源表", "warning")
            return
        
        # 获取目标表名称
        combo = self.tgt_table.cellWidget(row, 1)
        if not combo:
            return
        
        tgt_name = combo.currentText()
        if not tgt_name:
            self._log("[Step4] 请先选择目标表", "warning")
            return
        
        # 使用带前缀的 key
        src_key = f"[源表]{src_name}"
        tgt_key = f"[目标表{row+1}]{tgt_name}"
        
        # 调用并获取返回值
        summary = self.open_match_modal(src_key, tgt_key)
        
        # 更新按钮状态
        btn_match = self.tgt_table.cellWidget(row, 3)
        if btn_match:
            if summary:
                btn_match.setText(summary)
                btn_match.setObjectName("step4_btn_config_done")
            else:
                btn_match.setText("设置")
                btn_match.setObjectName("step4_btn_config")
            btn_match.style().unpolish(btn_match)
            btn_match.style().polish(btn_match)
        
        # 保存到任务组
        group = self._task_groups[self._current_group_idx]
        targets = group.get("targets", [])
        if row < len(targets):
            targets[row]["match_fields"] = summary
    
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
        
        self._persist_tasks()  # 持久化
        self._refresh_task_list()
        self._log(f"[Step4] 保存任务组配置: {group['name']}", "info")
    
    def _run_current_group(self):
        """执行当前任务组 - 弹出进度对话框，后台线程执行"""
        from ..workers.match_worker import MatchWorker
        from ..widgets.result_dialog import ResultDialog
        from ..widgets.progress_dialog import ProgressDialog
        
        # 检查是否已有任务在运行
        if hasattr(self, '_match_worker') and self._match_worker is not None and self._match_worker.isRunning():
            ResultDialog.show_warning(self, "任务进行中", "请等待当前匹配任务完成")
            return
        
        if self._current_group_idx < 0:
            return
        
        group = self._task_groups[self._current_group_idx]
        
        # 验证配置
        if not group.get("source"):
            ResultDialog.show_warning(self, "配置不完整", "请先选择源表")
            return
        
        targets = group.get("targets", [])
        valid_targets = [t for t in targets if t.get("table")]
        if not valid_targets:
            ResultDialog.show_warning(self, "配置不完整", "请先添加目标表")
            return
        
        # 获取全局配置
        global_config = self._get_global_config()
        if not global_config:
            ResultDialog.show_error(self, "配置错误", "无法获取全局配置")
            return
        
        # 更新状态
        group["status"] = "执行中"
        group["progress"] = 0
        self._refresh_task_list()
        
        # 更新面板进度条
        self.match_progress.setValue(0)
        self.match_progress.setMaximum(100)
        self.lbl_match_status.setText("执行中...")
        
        self._log(f"[Step4] 开始后台执行任务组: {group['name']}", "info")
        
        # === 创建进度对话框（参考 Step3 导出模式）===
        self._progress_dialog = ProgressDialog(
            self,
            f"执行匹配任务: {group['name']}",
            "正在初始化...",
            cancelable=True
        )
        
        try:
            # 创建 Worker（Worker 内部会创建 Executor 并传递回调）
            self._match_worker = MatchWorker(
                executor=None,  # 不再传入，Worker 内部创建
                task_groups=[group],
                global_config=global_config,
                parent=self
            )
            
            # 连接信号到进度对话框
            self._match_worker.progress.connect(self._on_progress_update)
            self._match_worker.log.connect(self._log)
            self._match_worker.group_completed.connect(self._on_group_completed)
            self._match_worker.finished.connect(self._on_match_finished)
            self._match_worker.error.connect(self._on_match_error)
            
            # 取消按钮
            self._progress_dialog.on_cancel = self._match_worker.cancel
            
            # 启动 Worker
            self._match_worker.start()
            
            # 显示模态进度对话框（阻塞直到完成）
            self._progress_dialog.exec()
            
        except Exception as e:
            group["status"] = "失败"
            self._log(f"[Step4] 执行异常: {e}", "error")
            self._persist_tasks()
            self._refresh_task_list()
            self.lbl_match_status.setText(f"失败：{str(e)[:50]}")
            if hasattr(self, '_progress_dialog') and self._progress_dialog:
                self._progress_dialog.close()
    
    def _on_progress_update(self, current: int, total: int, message: str):
        """进度更新回调 - 同时更新对话框和面板
        
        现在 current/total 直接是百分比形式（0-100, 100）
        """
        # 计算百分比（处理两种格式：直接百分比或分数）
        if total == 100:
            percent = current  # 直接是百分比
        elif total > 0:
            percent = int(current / total * 100)
        else:
            percent = 0
        
        # 更新进度对话框
        if hasattr(self, '_progress_dialog') and self._progress_dialog:
            self._progress_dialog.set_progress(percent, message)
        
        # 更新面板进度条
        self.match_progress.setMaximum(100)
        self.match_progress.setValue(percent)
        self.lbl_match_status.setText(message)
        
        # 更新任务组进度
        if self._current_group_idx >= 0:
            group = self._task_groups[self._current_group_idx]
            group["progress"] = percent
    
    def _on_group_completed(self, group_name: str, result: dict):
        """单个任务组完成"""
        # 查找对应的任务组
        for group in self._task_groups:
            if group.get('name') == group_name:
                if result.get('success'):
                    group["status"] = "已完成"
                    group["progress"] = 100
                else:
                    group["status"] = "失败"
                break
        self._refresh_task_list()
    
    def _on_match_finished(self, summary: dict):
        """匹配任务完成 - 关闭进度对话框并显示结果"""
        self._match_worker = None
        self._persist_tasks()
        self._refresh_task_list()
        
        # === 关闭进度对话框 ===
        if hasattr(self, '_progress_dialog') and self._progress_dialog:
            self._progress_dialog.close()
            self._progress_dialog = None
        
        if summary.get('cancelled'):
            self._log("[Step4] 匹配任务已取消", "warning")
            self.lbl_match_status.setText("已取消")
            self.match_progress.setValue(0)
            return
        
        # 更新进度条和状态
        success_count = summary.get('success_count', 0)
        fail_count = summary.get('fail_count', 0)
        auto_match = summary.get('auto_match', 0)
        need_review = summary.get('total_need_review', 0)
        
        self.match_progress.setValue(100)
        if fail_count == 0:
            self.lbl_match_status.setText(f"✅ 完成：自动匹配 {auto_match} 条，需确认 {need_review} 条")
        else:
            self.lbl_match_status.setText(f"⚠️ 完成：成功{success_count}个，失败{fail_count}个")
        
        # 显示分层结果弹窗
        results = summary.get('results', [])
        if results and results[0].get('success'):
            self._show_match_result_dialog(results[0], summary)
    
    def _on_match_error(self, error_msg: str):
        """匹配任务出错 - 关闭进度对话框并显示错误"""
        from ..widgets.result_dialog import ResultDialog
        
        self._match_worker = None
        
        # === 关闭进度对话框 ===
        if hasattr(self, '_progress_dialog') and self._progress_dialog:
            self._progress_dialog.close()
            self._progress_dialog = None
        
        self.lbl_match_status.setText(f"❌ 出错：{error_msg[:50]}")
        self.match_progress.setValue(0)
        
        # 显示错误弹窗
        ResultDialog.show_error(self, "匹配出错", error_msg[:500])
        
        # 更新当前任务组状态
        if self._current_group_idx >= 0:
            self._task_groups[self._current_group_idx]["status"] = "失败"
        
        self._persist_tasks()
        self._refresh_task_list()
        self._log(f"[Step4] 匹配出错: {error_msg}", "error")
    
    def _show_match_result_dialog(self, result: Dict, summary: Dict = None):
        """显示分层匹配结果对话框"""
        from qgis.PyQt.QtWidgets import QMessageBox
        
        # 获取统计数据
        stats = result.get('statistics', {})
        total = stats.get('total', 0)
        exact = stats.get('exact', 0)
        high_conf = stats.get('high_confidence', 0)
        need_review = stats.get('need_review', 0)
        unmatched = stats.get('unmatched', 0)
        auto_match_rate = stats.get('auto_match_rate', 0)
        
        msg = f"""🎯 匹配任务完成！

📋 任务名称: {result.get('task_name', '')}
⏱️ 执行时间: {result.get('execution_time', '')}

📊 分层匹配结果 (共 {total} 条)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🟢 精确匹配: {exact} 条  ({stats.get('exact_rate', 0):.1f}%)
   - 核心字段完全相等 / POI结构化相等
   - 无需人工确认

🔵 高置信度: {high_conf} 条  ({stats.get('high_confidence_rate', 0):.1f}%)
   - 区县约束 + 模糊匹配 ≥95%
   - 无需人工确认

🟡 需人工确认: {need_review} 条  ({stats.get('need_review_rate', 0):.1f}%)
   - 模糊匹配 88-95%
   - 建议人工核实

⚪ 未匹配: {unmatched} 条  ({100 - stats.get('match_rate', 0):.1f}%)
   - 无匹配结果
━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✨ 自动匹配率: {auto_match_rate:.1f}%（无需人工确认）

💾 结果已保存到缓存目录的 match_results 文件夹：
   - {{源表}}_精确匹配_{{N}}条.csv
   - {{源表}}_高置信度_{{N}}条.csv
   - {{源表}}_需人工确认_{{N}}条.csv
   - {{源表}}_未匹配_{{N}}条.csv"""
        
        QMessageBox.information(self, "匹配完成", msg)
    
    def _export_current_group_results(self):
        """导出当前任务组的匹配结果
        
        缓存中只保留最新结果，文件命名格式：
        - 匹配结果: {源表}_vs_{目标表}_匹配{N}条.csv
        - 未匹配: {源表}_未匹配{M}条.csv
        """
        from qgis.PyQt.QtWidgets import QFileDialog, QMessageBox
        import shutil
        
        if self._current_group_idx < 0:
            return
        
        group = self._task_groups[self._current_group_idx]
        task_name = group.get("name", "未命名任务")
        source_file = group.get("source", "")
        
        # 检查是否有执行结果
        if group.get("status") != "已完成":
            QMessageBox.warning(self, "无法导出", "请先执行任务，完成后再导出结果")
            return
        
        if not source_file:
            QMessageBox.warning(self, "配置错误", "任务组未配置源表")
            return
        
        # 获取缓存目录中的结果文件
        global_config = self._get_global_config()
        if not global_config:
            QMessageBox.warning(self, "配置错误", "无法获取全局配置")
            return
        
        region_info = global_config.get_region_info()
        cache_folder = region_info.get('cache_folder', '')
        result_dir = os.path.join(cache_folder, "match_results")
        
        if not os.path.exists(result_dir):
            QMessageBox.warning(self, "无结果", "匹配结果目录不存在，请先执行任务")
            return
        
        # 源表名（去掉扩展名和"_标准化"后缀，与保存时一致）
        source_name = os.path.splitext(source_file)[0].replace("_标准化", "")
        source_name = source_name.replace(" ", "_").replace("/", "_").replace("\\", "_")
        
        # 收集该源表的结果文件
        result_files = []
        for f in os.listdir(result_dir):
            if f.startswith(source_name) and f.endswith('.csv'):
                result_files.append(os.path.join(result_dir, f))
        
        if not result_files:
            QMessageBox.warning(self, "无结果", f"未找到源表 '{source_file}' 的匹配结果文件")
            return
        
        # 选择导出目录
        export_dir = QFileDialog.getExistingDirectory(
            self,
            f"选择导出目录 - {task_name}",
            region_info.get('base_folder', '')
        )
        
        if not export_dir:
            return
        
        # 复制文件到导出目录
        exported_count = 0
        exported_files = []
        for src_file in result_files:
            filename = os.path.basename(src_file)
            dst_file = os.path.join(export_dir, filename)
            try:
                shutil.copy2(src_file, dst_file)
                exported_count += 1
                exported_files.append(filename)
                self._log(f"[Step4] 导出: {filename}", "info")
            except Exception as e:
                self._log(f"[Step4] 导出失败: {filename}, {e}", "error")
        
        # 显示导出的文件列表
        file_list = "\n".join(f"  • {f}" for f in exported_files)
        QMessageBox.information(
            self,
            "导出完成",
            f"已导出 {exported_count} 个文件到:\n{export_dir}\n\n文件列表:\n{file_list}"
        )
    
    def _delete_current_group(self):
        """删除当前任务组"""
        if self._current_group_idx < 0:
            return
        
        group = self._task_groups[self._current_group_idx]
        del self._task_groups[self._current_group_idx]
        self._current_group_idx = -1
        self._persist_tasks()  # 持久化
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
    
    def _export_all_results(self):
        """批量导出所有已完成任务组的匹配结果
        
        缓存中只保留最新结果，文件命名格式：
        - 匹配结果: {源表}_vs_{目标表}_匹配{N}条.csv
        - 未匹配: {源表}_未匹配{M}条.csv
        """
        from qgis.PyQt.QtWidgets import QFileDialog, QMessageBox
        import shutil
        
        # 获取已完成的任务组
        completed_groups = [g for g in self._task_groups if g.get("status") == "已完成"]
        if not completed_groups:
            QMessageBox.warning(self, "无可导出任务", "没有已完成的任务组，请先执行任务")
            return
        
        # 获取缓存目录
        global_config = self._get_global_config()
        if not global_config:
            QMessageBox.warning(self, "配置错误", "无法获取全局配置")
            return
        
        region_info = global_config.get_region_info()
        cache_folder = region_info.get('cache_folder', '')
        result_dir = os.path.join(cache_folder, "match_results")
        
        if not os.path.exists(result_dir):
            QMessageBox.warning(self, "无结果", "匹配结果目录不存在")
            return
        
        # 选择导出目录
        export_dir = QFileDialog.getExistingDirectory(
            self,
            f"选择导出目录 - 批量导出 ({len(completed_groups)} 个任务组)",
            region_info.get('base_folder', '')
        )
        
        if not export_dir:
            return
        
        total_exported = 0
        exported_files = []
        
        # 收集每个任务组的结果文件（按源表名查找）
        for group in completed_groups:
            source_file = group.get("source", "")
            if not source_file:
                continue
            
            # 源表名（去掉扩展名和"_标准化"后缀，与保存时一致）
            source_name = os.path.splitext(source_file)[0].replace("_标准化", "")
            source_name = source_name.replace(" ", "_").replace("/", "_").replace("\\", "_")
            
            # 收集该源表的结果文件
            for f in os.listdir(result_dir):
                if f.startswith(source_name) and f.endswith('.csv'):
                    src_file = os.path.join(result_dir, f)
                    dst_file = os.path.join(export_dir, f)
                    try:
                        shutil.copy2(src_file, dst_file)
                        total_exported += 1
                        exported_files.append(f)
                    except Exception as e:
                        self._log(f"[Step4] 导出失败: {f}, {e}", "error")
        
        self._log(f"[Step4] 批量导出完成: {total_exported} 个文件", "info")
        
        # 显示摘要
        file_list = "\n".join(f"  • {f}" for f in exported_files[:10])
        if len(exported_files) > 10:
            file_list += f"\n  ... 等共 {len(exported_files)} 个文件"
        
        QMessageBox.information(
            self,
            "批量导出完成",
            f"已导出 {total_exported} 个文件到:\n{export_dir}\n\n"
            f"包含 {len(completed_groups)} 个任务组的结果:\n{file_list}"
        )
    
    def showEvent(self, event):
        """显示时刷新文件列表和初始化持久化"""
        super().showEvent(event)
        # 确保持久化管理器已初始化（用户可能在其他步骤配置了全局配置）
        if not self._persist_manager:
            self._init_persist_manager()
            if self._persist_manager:
                self._load_persisted_tasks()
                self._refresh_task_list()
        self._load_available_files()
    
    def _preview_match(self):
        """预览匹配结果（前10条）"""
        if self._current_group_idx < 0:
            return
        
        group = self._task_groups[self._current_group_idx]
        
        # 验证配置
        if not group.get("source"):
            self._log("[Step4] 请先选择源表", "warning")
            return
        
        targets = group.get("targets", [])
        if not targets or not targets[0].get("table"):
            self._log("[Step4] 请先添加目标表", "warning")
            return
        
        self._log("[Step4] 开始预览匹配（前10条）...", "info")
        
        import pandas as pd
        from ...core.poi_matcher import POIMatcher
        
        global_config = self._get_global_config()
        if not global_config:
            self._log("[Step4] 无法获取全局配置", "error")
            return
        
        region_info = global_config.get_region_info()
        
        # 加载源表
        source_file = group.get("source")
        source_df = self._load_file_for_preview(source_file, region_info)
        if source_df is None or source_df.empty:
            self._log(f"[Step4] 源表加载失败: {source_file}", "error")
            return
        
        # 只取前10条
        source_df = source_df.head(10)
        
        # 加载第一个目标表
        target_file = targets[0].get("table")
        target_df = self._load_file_for_preview(target_file, region_info)
        if target_df is None or target_df.empty:
            self._log(f"[Step4] 目标表加载失败: {target_file}", "error")
            return
        
        # 检测POI列
        poi_col = self._detect_poi_column(source_df)
        target_poi_col = self._detect_poi_column(target_df)
        
        if not poi_col:
            hint = self._get_available_columns_hint(source_df)
            self._log(f"[Step4] 源表 '{source_file}' 未找到POI列（请选择 *_标准化.csv 文件）", "error")
            self._log(f"[Step4] 可用列: {hint}", "debug")
            return
        if not target_poi_col:
            hint = self._get_available_columns_hint(target_df)
            self._log(f"[Step4] 目标表 '{target_file}' 未找到POI列（请选择 *_标准化.csv 文件）", "error")
            self._log(f"[Step4] 可用列: {hint}", "debug")
            return
        
        # 执行预览匹配
        matcher = POIMatcher(log_callback=self._log)
        preview_df = matcher.match(
            left_df=source_df,
            right_df=target_df,
            left_file=source_file,
            right_file=target_file,
            left_poi_col=poi_col,
            right_poi_col=target_poi_col
        )
        
        # 显示预览结果
        self._show_preview_dialog(preview_df)
    
    def _load_file_for_preview(self, filename: str, region_info: Dict):
        """加载文件用于预览（只从标准化文件夹加载）"""
        import pandas as pd
        
        # 从缓存的路径映射中获取
        if hasattr(self, '_file_paths') and filename in self._file_paths:
            filepath = self._file_paths[filename]
            if os.path.exists(filepath):
                try:
                    return self._read_file(filepath)
                except Exception as e:
                    self._log(f"[Step4] 读取失败: {e}", "error")
                    return None
        
        self._log(f"[Step4] 文件未找到: {filename}（请刷新文件列表）", "error")
        return None
    
    def _read_file(self, filepath: str):
        """读取文件（支持多种编码）"""
        import pandas as pd
        
        if filepath.lower().endswith('.csv'):
            for enc in ['utf-8', 'gbk', 'gb2312', 'utf-8-sig']:
                try:
                    return pd.read_csv(filepath, encoding=enc)
                except UnicodeDecodeError:
                    continue
            raise ValueError(f"无法解析文件编码: {filepath}")
        elif filepath.lower().endswith(('.xlsx', '.xls')):
            return pd.read_excel(filepath)
        else:
            raise ValueError(f"不支持的文件格式: {filepath}")
    
    def _detect_poi_column(self, df) -> str:
        """
        检测POI列
        
        优先级：
        1. Step3 解析生成的列：'标准化POI抽取'
        2. 其他常见 POI 列名
        """
        # Step3 解析生成的标准列名
        poi_columns = [
            "标准化POI抽取",  # Step3 解析生成
            "predict_poi",    # 原始 API 字段名
            "POI",            # 通用名称
            "poi",            # 小写
            "POI_结构化",     # Step3 结构化 POI
        ]
        for col in poi_columns:
            if col in df.columns:
                return col
        return ""
    
    def _get_available_columns_hint(self, df) -> str:
        """获取可用列提示"""
        cols = list(df.columns)[:10]
        return ", ".join(cols) + ("..." if len(df.columns) > 10 else "")
    
    def _show_preview_dialog(self, preview_df):
        """显示预览结果对话框"""
        from qgis.PyQt.QtWidgets import QDialog, QVBoxLayout, QTableWidget, QTableWidgetItem, QPushButton, QHeaderView, QLabel
        
        dialog = QDialog(self)
        dialog.setWindowTitle("匹配预览（前10条）")
        dialog.resize(1000, 500)
        dialog.setMinimumSize(800, 400)
        
        layout = QVBoxLayout(dialog)
        
        lbl_hint = QLabel("以下是前10条记录的匹配预览结果：")
        layout.addWidget(lbl_hint)
        
        # 统计
        matched_count = len(preview_df[preview_df["是否匹配"] == "是"]) if not preview_df.empty else 0
        total = len(preview_df) if not preview_df.empty else 0
        lbl_stats = QLabel(f"预览结果: {matched_count}/{total} 条匹配成功")
        lbl_stats.setObjectName("preview_stats")
        layout.addWidget(lbl_stats)
        
        # 表格
        table = QTableWidget()
        table.setObjectName("preview_table")
        
        display_cols = ["源表行号", "源表POI", "目标表行号", "目标表POI", "匹配类型", "匹配分数", "是否匹配"]
        actual_cols = [c for c in display_cols if c in preview_df.columns]
        
        table.setColumnCount(len(actual_cols))
        table.setHorizontalHeaderLabels(actual_cols)
        table.setRowCount(len(preview_df))
        
        for row_idx, (_, row) in enumerate(preview_df.iterrows()):
            for col_idx, col in enumerate(actual_cols):
                value = str(row.get(col, ""))
                item = QTableWidgetItem(value)
                
                if row.get("是否匹配") == "是":
                    item.setBackground(QColor("#dcfce7"))
                else:
                    item.setBackground(QColor("#fee2e2"))
                
                table.setItem(row_idx, col_idx, item)
        
        header = table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        
        layout.addWidget(table, 1)
        
        btn_close = QPushButton("关闭")
        btn_close.clicked.connect(dialog.accept)
        layout.addWidget(btn_close)
        
        dialog.exec()
