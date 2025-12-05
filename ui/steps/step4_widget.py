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
        self.combo_src.currentTextChanged.connect(self._on_source_changed)
        src_row.addWidget(self.combo_src, 1)
        src_layout.addLayout(src_row)
        
        # 源表数据统计行
        stats_row = QHBoxLayout()
        lbl_stats = QLabel("数据统计:")
        lbl_stats.setMinimumWidth(70)
        stats_row.addWidget(lbl_stats)
        self.lbl_src_stats = QLabel("--")
        self.lbl_src_stats.setObjectName("step4_src_stats")
        self.lbl_src_stats.setMinimumHeight(28)
        stats_row.addWidget(self.lbl_src_stats, 1)
        btn_refresh_stats = QPushButton("刷新")
        btn_refresh_stats.setObjectName("step4_btn_refresh_stats")
        btn_refresh_stats.setMinimumHeight(28)
        btn_refresh_stats.setMaximumWidth(60)
        btn_refresh_stats.clicked.connect(self._refresh_source_stats)
        stats_row.addWidget(btn_refresh_stats)
        src_layout.addLayout(stats_row)
        
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
        
        # 目标表表格 - 6列（移除数据质量列）
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
        
        # ===== 匹配统计区域（默认隐藏，执行后显示） =====
        self.stats_group = QGroupBox("匹配统计")
        self.stats_group.setObjectName("step4_stats_group")
        self.stats_group.setVisible(False)  # 默认隐藏
        stats_layout = QVBoxLayout(self.stats_group)
        stats_layout.setSpacing(6)
        
        # ===== 数据质量分析区域 =====
        quality_group = QGroupBox("数据质量分析")
        quality_group.setObjectName("step4_quality_group")
        quality_layout = QVBoxLayout(quality_group)
        quality_layout.setSpacing(8)
        quality_layout.setContentsMargins(8, 8, 8, 8)
        
        # 源表数据质量（动态更新标签）
        src_quality_row = QHBoxLayout()
        src_quality_row.setSpacing(8)
        self.lbl_src_quality_name = QLabel("源表:")
        src_quality_row.addWidget(self.lbl_src_quality_name)
        self.lbl_src_quality = QLabel("--")
        self.lbl_src_quality.setObjectName("step4_quality_label")
        src_quality_row.addWidget(self.lbl_src_quality, 1)
        src_quality_row.addStretch()
        quality_layout.addLayout(src_quality_row)
        
        # 目标表数据质量（动态添加）
        self.target_quality_container = QWidget()
        self.target_quality_layout = QVBoxLayout(self.target_quality_container)
        self.target_quality_layout.setContentsMargins(0, 0, 0, 0)
        self.target_quality_layout.setSpacing(4)
        quality_layout.addWidget(self.target_quality_container)
        
        stats_layout.addWidget(quality_group)
        
        # 分隔线
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        stats_layout.addWidget(line)
        
        # 分层统计标签
        self.lbl_stats_summary = QLabel("等待执行...")
        self.lbl_stats_summary.setObjectName("step4_stats_summary")
        self.lbl_stats_summary.setWordWrap(True)
        stats_layout.addWidget(self.lbl_stats_summary)
        
        # 分层统计使用网格布局（2x2）
        from qgis.PyQt.QtWidgets import QGridLayout
        layer_container = QWidget()
        layer_grid = QGridLayout(layer_container)
        layer_grid.setContentsMargins(0, 4, 0, 4)
        layer_grid.setSpacing(8)
        
        # 精确匹配（绿色）- 左上
        exact_widget = QWidget()
        exact_widget.setObjectName("step4_layer_box_green")
        exact_box = QVBoxLayout(exact_widget)
        exact_box.setContentsMargins(8, 6, 8, 6)
        exact_box.setSpacing(2)
        self.lbl_exact = QLabel("🟢 精确匹配")
        self.lbl_exact.setObjectName("step4_layer_label")
        self.lbl_exact_count = QLabel("--")
        self.lbl_exact_count.setObjectName("step4_layer_count_green")
        self.lbl_exact_count.setAlignment(Qt.AlignmentFlag.AlignCenter)
        exact_box.addWidget(self.lbl_exact)
        exact_box.addWidget(self.lbl_exact_count)
        layer_grid.addWidget(exact_widget, 0, 0)
        
        # 高置信度（蓝色）- 右上
        high_widget = QWidget()
        high_widget.setObjectName("step4_layer_box_blue")
        high_box = QVBoxLayout(high_widget)
        high_box.setContentsMargins(8, 6, 8, 6)
        high_box.setSpacing(2)
        self.lbl_high = QLabel("🔵 高置信度")
        self.lbl_high.setObjectName("step4_layer_label")
        self.lbl_high_count = QLabel("--")
        self.lbl_high_count.setObjectName("step4_layer_count_blue")
        self.lbl_high_count.setAlignment(Qt.AlignmentFlag.AlignCenter)
        high_box.addWidget(self.lbl_high)
        high_box.addWidget(self.lbl_high_count)
        layer_grid.addWidget(high_widget, 0, 1)
        
        # 需确认（黄色）- 左下
        review_widget = QWidget()
        review_widget.setObjectName("step4_layer_box_yellow")
        review_box = QVBoxLayout(review_widget)
        review_box.setContentsMargins(8, 6, 8, 6)
        review_box.setSpacing(2)
        self.lbl_review = QLabel("🟡 需人工确认")
        self.lbl_review.setObjectName("step4_layer_label")
        self.lbl_review_count = QLabel("--")
        self.lbl_review_count.setObjectName("step4_layer_count_yellow")
        self.lbl_review_count.setAlignment(Qt.AlignmentFlag.AlignCenter)
        review_box.addWidget(self.lbl_review)
        review_box.addWidget(self.lbl_review_count)
        layer_grid.addWidget(review_widget, 1, 0)
        
        # 未匹配（灰色）- 右下
        unmatched_widget = QWidget()
        unmatched_widget.setObjectName("step4_layer_box_gray")
        unmatched_box = QVBoxLayout(unmatched_widget)
        unmatched_box.setContentsMargins(8, 6, 8, 6)
        unmatched_box.setSpacing(2)
        self.lbl_unmatched = QLabel("⚪ 未匹配")
        self.lbl_unmatched.setObjectName("step4_layer_label")
        self.lbl_unmatched_count = QLabel("--")
        self.lbl_unmatched_count.setObjectName("step4_layer_count_gray")
        self.lbl_unmatched_count.setAlignment(Qt.AlignmentFlag.AlignCenter)
        unmatched_box.addWidget(self.lbl_unmatched)
        unmatched_box.addWidget(self.lbl_unmatched_count)
        layer_grid.addWidget(unmatched_widget, 1, 1)
        
        stats_layout.addWidget(layer_container)
        
        # 进度条
        self.match_progress = QProgressBar()
        self.match_progress.setObjectName("step4_match_progress")
        self.match_progress.setMinimumHeight(20)
        self.match_progress.setValue(0)
        self.match_progress.setTextVisible(True)
        self.match_progress.setFormat("%p%")
        stats_layout.addWidget(self.match_progress)
        
        # 状态标签
        self.lbl_match_status = QLabel("就绪")
        self.lbl_match_status.setObjectName("step4_match_status")
        stats_layout.addWidget(self.lbl_match_status)
        
        config_layout.addWidget(self.stats_group)
        
        # ===== 备注区域（在操作按钮之前） =====
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
        
        # 加载匹配统计（如果有历史数据）
        self._load_group_stats(group)
        
        self._log(f"[Step4] 加载任务组配置: {group['name']}", "info")
    
    def _refresh_target_table(self, targets: List[Dict]):
        """刷新目标表表格"""
        self.tgt_table.setRowCount(len(targets))
        
        for r, target in enumerate(targets):
            self._add_target_table_row(r, target)
    
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
        """新增目标表 - 只添加一行，不刷新整个表格"""
        if self._current_group_idx < 0:
            return
        
        # 先保存当前表格中的选择到 targets
        self._sync_targets_from_table()
        
        group = self._task_groups[self._current_group_idx]
        new_target = {
            "table": "",
            "filter": "",
            "match_fields": "",
            "match_desc": ""
        }
        group["targets"].append(new_target)
        
        # 只添加新行
        r = self.tgt_table.rowCount()
        self.tgt_table.setRowCount(r + 1)
        self._add_target_table_row(r, new_target)
        
        self._log("[Step4] 新增目标表", "info")
    
    def _sync_targets_from_table(self):
        """从表格同步目标表选择到数据"""
        if self._current_group_idx < 0:
            return
        
        group = self._task_groups[self._current_group_idx]
        targets = group.get("targets", [])
        
        for r in range(min(self.tgt_table.rowCount(), len(targets))):
            combo = self.tgt_table.cellWidget(r, 1)
            if combo:
                targets[r]["table"] = combo.currentText()
    
    def _add_target_table_row(self, r: int, target: Dict):
        """添加单行目标表到表格"""
        # 序号
        seq_item = QTableWidgetItem(str(r + 1))
        seq_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        seq_item.setFlags(seq_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.tgt_table.setItem(r, 0, seq_item)
        
        # 目标表（下拉框）
        combo = NoWheelComboBox()
        combo.setEditable(False)
        combo.addItem("")  # 添加空选项
        combo.addItems(self._available_files)
        tgt_table_name = target.get("table", "")
        if tgt_table_name:
            combo.setCurrentText(tgt_table_name)
        else:
            combo.setCurrentIndex(0)  # 选择空选项
        # 下拉框变化时更新数据质量
        combo.currentTextChanged.connect(lambda text, row=r: self._update_target_quality_display())
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
    
    def _move_target(self, row: int, direction: int):
        """移动目标表"""
        if self._current_group_idx < 0:
            return
        
        # 查找实际行号（操作列索引为5）
        sender = self.sender()
        if sender:
            for r in range(self.tgt_table.rowCount()):
                widget = self.tgt_table.cellWidget(r, 5)
                if widget and sender in widget.findChildren(QPushButton):
                    row = r
                    break
        
        # 先同步表格中的选择到数据
        self._sync_targets_from_table()
        
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
        
        # 查找实际行号（操作列索引为5）
        sender = self.sender()
        if sender:
            for r in range(self.tgt_table.rowCount()):
                widget = self.tgt_table.cellWidget(r, 5)
                if widget and sender in widget.findChildren(QPushButton):
                    row = r
                    break
        
        # 先同步表格中的选择到数据
        self._sync_targets_from_table()
        
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
                # 更新按钮文字（过滤条件列索引为2）
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
        
        # 调用并获取返回值（现在是JSON字符串，包含pairs和summary）
        config_json = self.open_match_modal(src_key, tgt_key)
        
        # 解析配置
        import json
        summary = ""
        if config_json:
            try:
                config = json.loads(config_json)
                summary = config.get("summary", "")
            except:
                # 兼容旧格式（直接是摘要字符串）
                summary = config_json
        
        # 更新按钮状态（匹配字段列索引为3）
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
        
        # 保存到任务组（保存完整的JSON配置，而不仅仅是摘要）
        group = self._task_groups[self._current_group_idx]
        targets = group.get("targets", [])
        if row < len(targets):
            targets[row]["match_fields"] = config_json if config_json else ""
    
    def _save_current_config(self):
        """保存当前任务组配置"""
        if self._current_group_idx < 0:
            return
        
        group = self._task_groups[self._current_group_idx]
        group["source"] = self.combo_src.currentText()
        group["remark"] = self.txt_remark.text()
        
        # 更新目标表，保留已有的 filter 和 match_fields
        old_targets = group.get("targets", [])
        new_targets = []
        for r in range(self.tgt_table.rowCount()):
            combo = self.tgt_table.cellWidget(r, 1)
            desc_item = self.tgt_table.item(r, 5)
            if combo:
                # 尝试从旧数据中获取 filter 和 match_fields
                old_filter = ""
                old_match_fields = ""
                if r < len(old_targets):
                    old_filter = old_targets[r].get("filter", "")
                    old_match_fields = old_targets[r].get("match_fields", "")
                
                target_table = combo.currentText()
                # 查找目标表对应的原始 SHP 文件路径
                original_path = self._find_original_shp_path_from_target(target_table)
                
                new_targets.append({
                    "table": target_table,
                    "filter": old_filter,
                    "match_fields": old_match_fields,
                    "match_desc": desc_item.text() if desc_item else "",
                    "original_path": original_path  # 新增：原始 SHP 文件路径
                })
        group["targets"] = new_targets
        group["status"] = "待执行"
        
        self._persist_tasks()  # 持久化
        self._refresh_task_list()
        self._log(f"[Step4] 保存任务组配置: {group['name']}", "info")
    
    def _find_original_shp_path_from_target(self, target_table: str) -> str:
        """
        从目标表文件名查找对应的原始 SHP 文件路径
        
        Args:
            target_table: 目标表文件名（如：节点.csv 或 节点_清洗_标准化.csv）
            
        Returns:
            原始 SHP 文件路径，如果找不到则返回空字符串
        """
        if not self.global_config:
            return ""
        
        try:
            import json
            region_info = self.global_config.get_region_info()
            cache_folder = region_info.get('cache_folder', '')
            if not cache_folder:
                return ""
            
            file_status_path = os.path.join(cache_folder, "file_status.json")
            if not os.path.exists(file_status_path):
                return ""
            
            with open(file_status_path, 'r', encoding='utf-8') as f:
                file_status = json.load(f)
            
            # 查找目标表对应的文件记录
            for file_name, status in file_status.items():
                if isinstance(status, dict):
                    file_chain = status.get('file_chain', {})
                    
                    # 检查 step1, step2_cleaned, step3_parsed 是否匹配
                    if (file_chain.get('step1') == target_table or
                        file_chain.get('step2_cleaned') == target_table or
                        file_chain.get('step3_parsed') == target_table or
                        file_name == target_table):
                        
                        # 获取原始 SHP 文件路径
                        original_path = file_chain.get('step1_original', '')
                        if original_path and original_path.lower().endswith('.shp'):
                            return original_path
                        
                        # 如果没有 step1_original，尝试从 source_path 获取
                        source_path = status.get('source_path', '')
                        if source_path and source_path.lower().endswith('.shp'):
                            return source_path
            
            return ""
        except Exception as e:
            self._log(f"[Step4] 查找原始 SHP 文件路径失败: {e}", "warning")
            return ""
    
    # ===== 数据统计方法 =====
    
    def _on_source_changed(self, filename: str):
        """源表选择变化时更新统计并同步到任务组"""
        # 同步到当前任务组配置
        if self._current_group_idx >= 0:
            self._task_groups[self._current_group_idx]["source"] = filename
        
        if not filename:
            self.lbl_src_stats.setText("--")
            self._update_source_quality_display()
            return
        self._refresh_source_stats()
        self._update_source_quality_display()
    
    def _refresh_source_stats(self):
        """刷新源表数据统计"""
        filename = self.combo_src.currentText()
        if not filename:
            self.lbl_src_stats.setText("--")
            return
        
        stats = self._get_file_stats(filename)
        if stats:
            total = stats.get('total', 0)
            poi_rate = stats.get('poi_rate', 0)
            district_rate = stats.get('district_rate', 0)
            self.lbl_src_stats.setText(
                f"📊 {total}条 | POI: {poi_rate:.0%} | 区县: {district_rate:.0%}"
            )
        else:
            self.lbl_src_stats.setText("--")
    
    def _get_file_stats(self, filename: str) -> Optional[Dict]:
        """获取文件统计信息"""
        import pandas as pd
        
        if not filename:
            return None
        
        filepath = self._file_paths.get(filename, '')
        if not filepath or not os.path.exists(filepath):
            return None
        
        try:
            df = pd.read_csv(filepath, encoding='utf-8-sig', nrows=10000)  # 限制读取行数
            total = len(df)
            
            # POI_结构化非空率
            poi_col = 'POI_结构化'
            if poi_col in df.columns:
                poi_count = df[poi_col].notna().sum()
                poi_non_empty = df[poi_col].apply(lambda x: bool(str(x).strip()) if pd.notna(x) else False).sum()
                poi_rate = poi_non_empty / total if total > 0 else 0
            else:
                poi_rate = 0
            
            # 区县覆盖率
            district_col = '区县'
            if district_col in df.columns:
                district_non_empty = df[district_col].apply(lambda x: bool(str(x).strip()) if pd.notna(x) else False).sum()
                district_rate = district_non_empty / total if total > 0 else 0
            else:
                district_rate = 0
            
            return {
                'total': total,
                'poi_rate': poi_rate,
                'district_rate': district_rate
            }
        except Exception as e:
            self._log(f"[Step4] 读取文件统计失败: {e}", "warning")
            return None
    
    def _get_file_quality_text(self, filename: str) -> str:
        """获取文件质量简短文本（用于目标表列表）"""
        stats = self._get_file_stats(filename)
        if stats:
            total = stats.get('total', 0)
            poi_rate = stats.get('poi_rate', 0)
            return f"{total}条 {poi_rate:.0%}"
        return "--"
    
    def _update_target_quality_display(self):
        """更新所有目标表的匹配结果显示（在匹配统计区域）- 从匹配结果读取"""
        if not self.stats_group.isVisible():
            return
        
        # 清空现有目标表质量显示（包括布局项）
        while self.target_quality_layout.count():
            item = self.target_quality_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                # 清理布局中的控件
                layout = item.layout()
                while layout.count():
                    layout_item = layout.takeAt(0)
                    if layout_item.widget():
                        layout_item.widget().deleteLater()
                layout.deleteLater()
        
        # 从缓存数据读取目标表和匹配结果
        if self._current_group_idx < 0:
            return
        
        group = self._task_groups[self._current_group_idx]
        targets = group.get("targets", [])
        target_details = group.get("target_details", [])
        
        if not targets:
            return
        
        # 创建目标表名称到匹配详情的映射（用于快速查找）
        details_map = {}
        for detail in target_details:
            table_name = detail.get("table", "")
            if table_name:
                # 标准化为文件名（去掉路径，转为小写用于匹配）
                normalized = os.path.basename(table_name) if os.path.sep in table_name else table_name
                details_map[normalized.lower()] = detail
        
        # 按照targets的顺序显示（保持用户配置的优先级顺序）
        for target in targets:
            tgt_name = target.get("table", "")
            if not tgt_name:
                continue
            
            # 标准化文件名用于查找
            tgt_normalized = os.path.basename(tgt_name) if os.path.sep in tgt_name else tgt_name
            
            # 从target_details中查找匹配结果
            detail = details_map.get(tgt_normalized.lower(), None)
            
            # 显示文件名：优先使用target_details中的（准确），否则使用targets中的
            if detail and detail.get("table"):
                tgt_display_name = os.path.basename(detail.get("table")) if os.path.sep in detail.get("table") else detail.get("table")
            else:
                tgt_display_name = tgt_normalized
            
            # 读取匹配结果
            if detail:
                # 有匹配结果，显示匹配数量
                matched = detail.get("matched", 0)
                exact = detail.get("exact", 0)
                high_conf = detail.get("high_confidence", 0)
                need_review = detail.get("need_review", 0)
                
                # 格式化显示：匹配了X条（精确Y条，高置信Z条，需确认W条）
                match_text = f"匹配了{matched}条"
                if exact > 0 or high_conf > 0 or need_review > 0:
                    parts = []
                    if exact > 0:
                        parts.append(f"精确{exact}条")
                    if high_conf > 0:
                        parts.append(f"高置信{high_conf}条")
                    if need_review > 0:
                        parts.append(f"需确认{need_review}条")
                    if parts:
                        match_text += f"（{', '.join(parts)}）"
            else:
                # 没有匹配结果（未执行或执行失败）
                match_text = "未执行"
            
            quality_row = QHBoxLayout()
            quality_row.setSpacing(8)
            
            # 文件名标签（设置最小宽度，防止被压缩）
            name_label = QLabel(f"{tgt_display_name}:")
            name_label.setMinimumWidth(120)  # 确保文件名有足够显示空间
            name_label.setWordWrap(False)  # 不换行，完整显示
            quality_row.addWidget(name_label)
            
            # 匹配结果标签（可拉伸）
            quality_label = QLabel(match_text)
            quality_label.setObjectName("step4_quality_label")
            quality_label.setWordWrap(True)  # 允许换行，避免过长
            quality_row.addWidget(quality_label, 1)
            quality_row.addStretch()
            self.target_quality_layout.addLayout(quality_row)
    
    def _update_source_quality_display(self):
        """更新源表质量显示"""
        if not self.stats_group.isVisible():
            return
        
        source_file = self.combo_src.currentText()
        if source_file:
            # 显示完整文件名（包括后缀），只去掉路径
            source_display_name = os.path.basename(source_file) if os.path.sep in source_file else source_file
            self.lbl_src_quality_name.setText(f"{source_display_name}:")
            
            stats = self._get_file_stats(source_file)
            if stats:
                total = stats.get('total', 0)
                poi_rate = stats.get('poi_rate', 0)
                district_rate = stats.get('district_rate', 0)
                self.lbl_src_quality.setText(
                    f"📊 {total}条 | POI: {poi_rate:.0%} | 区县: {district_rate:.0%}"
                )
            else:
                self.lbl_src_quality.setText("--")
        else:
            self.lbl_src_quality_name.setText("源表:")
            self.lbl_src_quality.setText("--")
    
    def _load_group_stats(self, group: Dict):
        """加载任务组的匹配统计"""
        stats = group.get('match_stats', None)
        target_details = group.get('target_details', None)
        status = group.get('status', '')
        
        if stats and status == '已完成':
            # 有历史统计数据，显示匹配统计区域
            self.stats_group.setVisible(True)
            self._update_match_stats_display(stats, target_details)
            self._update_source_quality_display()
            self._update_target_quality_display()
            self.match_progress.setValue(100)
            self.lbl_match_status.setText(f"✅ 已完成")
        else:
            # 没有统计数据或未执行，隐藏匹配统计区域
            self.stats_group.setVisible(False)
            self._reset_match_stats_display()
            self.match_progress.setValue(0)
            if status == '执行中':
                self.stats_group.setVisible(True)  # 执行中也显示
                self._update_source_quality_display()
                self._update_target_quality_display()
                self.lbl_match_status.setText("⏳ 执行中...")
            elif status == '失败':
                self.stats_group.setVisible(True)  # 失败也显示
                self._update_source_quality_display()
                self._update_target_quality_display()
                self.lbl_match_status.setText("❌ 执行失败")
            else:
                self.lbl_match_status.setText("就绪")
    
    def _update_match_stats_display(self, stats: Dict, target_details: List[Dict] = None):
        """更新匹配统计显示"""
        total = stats.get('total', 0)
        exact = stats.get('exact', 0)
        high_conf = stats.get('high_confidence', 0)
        need_review = stats.get('need_review', 0)
        unmatched = stats.get('unmatched', 0)
        auto_rate = stats.get('auto_match_rate', 0)
        
        # 更新汇总（添加目标表信息）
        target_info = ""
        if target_details:
            target_count = len(target_details)
            total_matched = sum(d.get('matched', 0) for d in target_details)
            target_info = f" | {target_count}个目标表命中{total_matched}条"
        
        self.lbl_stats_summary.setText(
            f"共 {total} 条 | 自动匹配率: {auto_rate:.1f}%{target_info}"
        )
        
        # 更新分层数量
        self.lbl_exact_count.setText(f"{exact}")
        self.lbl_high_count.setText(f"{high_conf}")
        self.lbl_review_count.setText(f"{need_review}")
        self.lbl_unmatched_count.setText(f"{unmatched}")
    
    def _reset_match_stats_display(self):
        """重置匹配统计显示"""
        self.lbl_stats_summary.setText("等待执行...")
        self.lbl_exact_count.setText("--")
        self.lbl_high_count.setText("--")
        self.lbl_review_count.setText("--")
        self.lbl_unmatched_count.setText("--")
    
    def _run_current_group(self):
        """执行当前任务组 - 后台线程执行，进度显示在匹配统计区域"""
        from ..workers.match_worker import MatchWorker
        from ..widgets.result_dialog import ResultDialog
        
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
        
        # 显示匹配统计区域并更新面板进度条
        self.stats_group.setVisible(True)
        self.match_progress.setValue(0)
        self.match_progress.setMaximum(100)
        self.lbl_match_status.setText("执行中...")
        
        self._log(f"[Step4] 开始后台执行任务组: {group['name']}", "info")
        
        try:
            # 创建 Worker（Worker 内部会创建 Executor 并传递回调）
            self._match_worker = MatchWorker(
                executor=None,  # 不再传入，Worker 内部创建
                task_groups=[group],
                global_config=global_config,
                parent=self
            )
            
            # 连接信号（只更新匹配统计区域的进度条，不显示弹出对话框）
            self._match_worker.progress.connect(self._on_progress_update)
            self._match_worker.log.connect(self._log)
            self._match_worker.group_completed.connect(self._on_group_completed)
            self._match_worker.finished.connect(self._on_match_finished)
            self._match_worker.error.connect(self._on_match_error)
            
            # 启动 Worker（非阻塞，后台执行）
            self._match_worker.start()
            
        except Exception as e:
            group["status"] = "失败"
            self._log(f"[Step4] 执行异常: {e}", "error")
            self._persist_tasks()
            self._refresh_task_list()
            self.lbl_match_status.setText(f"失败：{str(e)[:50]}")
    
    def _on_progress_update(self, current: int, total: int, message: str):
        """进度更新回调 - 只更新匹配统计区域的进度条
        
        现在 current/total 直接是百分比形式（0-100, 100）
        """
        # 计算百分比（处理两种格式：直接百分比或分数）
        if total == 100:
            percent = current  # 直接是百分比
        elif total > 0:
            percent = int(current / total * 100)
        else:
            percent = 0
        
        # 更新匹配统计区域的进度条和状态
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
                    # 保存统计数据和目标详情
                    stats = result.get('statistics', {})
                    target_details = result.get('target_details', [])
                    if stats:
                        group['match_stats'] = stats
                    if target_details:
                        group['target_details'] = target_details
                else:
                    group["status"] = "失败"
                break
        self._refresh_task_list()
    
    def _on_match_finished(self, summary: dict):
        """匹配任务完成 - 显示结果"""
        self._match_worker = None
        self._persist_tasks()
        self._refresh_task_list()
        
        if summary.get('cancelled'):
            self._log("[Step4] 匹配任务已取消", "warning")
            self.lbl_match_status.setText("已取消")
            self.match_progress.setValue(0)
            self._reset_match_stats_display()
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
        
        # 更新分层统计显示并保存到任务组
        results = summary.get('results', [])
        if results and results[0].get('success'):
            # 保存统计数据到当前任务组（先保存，确保数据是最新的）
            if self._current_group_idx >= 0:
                stats = results[0].get('statistics', {})
                target_details = results[0].get('target_details', [])
                self._task_groups[self._current_group_idx]['match_stats'] = stats
                self._task_groups[self._current_group_idx]['target_details'] = target_details
                self._task_groups[self._current_group_idx]['status'] = '已完成'
                self._persist_tasks()  # 持久化
                
                # 重新加载当前任务组的统计数据（确保UI显示最新数据）
                current_group = self._task_groups[self._current_group_idx]
                self._load_group_stats(current_group)
            
            # 显示分层结果弹窗
            self._show_match_result_dialog(results[0], summary)
    
    def _on_match_error(self, error_msg: str):
        """匹配任务出错 - 显示错误"""
        from ..widgets.result_dialog import ResultDialog
        
        self._match_worker = None
        
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
        """显示分层匹配结果对话框 - 使用可滚动的自定义对话框"""
        from qgis.PyQt.QtWidgets import (
            QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
            QScrollArea, QWidget, QPushButton, QFrame
        )
        from qgis.PyQt.QtCore import Qt
        
        # 获取统计数据
        stats = result.get('statistics', {})
        total = stats.get('total', 0)
        exact = stats.get('exact', 0)
        high_conf = stats.get('high_confidence', 0)
        need_review = stats.get('need_review', 0)
        unmatched = stats.get('unmatched', 0)
        auto_match_rate = stats.get('auto_match_rate', 0)
        
        # 获取目标表详情
        source_file = result.get('source_file', '未知')
        target_details = result.get('target_details', [])
        
        # 创建对话框
        dialog = QDialog(self)
        dialog.setWindowTitle("匹配完成")
        dialog.setMinimumSize(520, 500)
        dialog.resize(560, 620)
        
        layout = QVBoxLayout(dialog)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)
        
        # ===== 标题 =====
        title = QLabel("🎯 匹配任务完成！")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #2563eb;")
        layout.addWidget(title)
        
        # ===== 任务信息 =====
        info_text = f"""📋 任务: {result.get('task_name', '')}
⏱️ 耗时: {result.get('execution_time', '')}
📁 源表: {source_file} ({total} 条)"""
        info_label = QLabel(info_text)
        info_label.setStyleSheet("color: #374151; line-height: 1.6;")
        layout.addWidget(info_label)
        
        # ===== 滚动区域 =====
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; }")
        
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        scroll_layout.setSpacing(12)
        scroll_layout.setContentsMargins(0, 0, 8, 0)
        
        # ===== 分层匹配结果 =====
        layer_title = QLabel("📊 分层匹配结果")
        layer_title.setStyleSheet("font-size: 14px; font-weight: bold; color: #1f2937; margin-top: 8px;")
        scroll_layout.addWidget(layer_title)
        
        # 精确匹配
        exact_box = self._create_layer_info_box(
            "🟢 精确匹配", exact, stats.get('exact_rate', 0),
            "核心字段完全相等 / POI结构化相等", "#10b981", "#ecfdf5"
        )
        scroll_layout.addWidget(exact_box)
        
        # 高置信度
        high_box = self._create_layer_info_box(
            "🔵 高置信度", high_conf, stats.get('high_confidence_rate', 0),
            "区县约束 + 模糊匹配 ≥95%", "#3b82f6", "#eff6ff"
        )
        scroll_layout.addWidget(high_box)
        
        # 需人工确认
        review_box = self._create_layer_info_box(
            "🟡 需人工确认", need_review, stats.get('need_review_rate', 0),
            "模糊匹配 88-95%，建议人工核实", "#f59e0b", "#fffbeb"
        )
        scroll_layout.addWidget(review_box)
        
        # 未匹配
        unmatched_box = self._create_layer_info_box(
            "⚪ 未匹配", unmatched, 100 - stats.get('match_rate', 0),
            "无匹配结果", "#6b7280", "#f9fafb"
        )
        scroll_layout.addWidget(unmatched_box)
        
        # ===== 目标表匹配详情 =====
        if target_details:
            target_title = QLabel("📋 各目标表匹配详情")
            target_title.setStyleSheet("font-size: 14px; font-weight: bold; color: #1f2937; margin-top: 12px;")
            scroll_layout.addWidget(target_title)
            
            for i, detail in enumerate(target_details, 1):
                table_name = detail.get('table', '未知')
                # 截断长名称
                display_name = table_name[:25] + '...' if len(table_name) > 28 else table_name
                target_total = detail.get('total', 0)
                matched = detail.get('matched', 0)
                t_exact = detail.get('exact', 0)
                t_high = detail.get('high_confidence', 0)
                t_review = detail.get('need_review', 0)
                status = detail.get('status', '')
                
                detail_text = f"""<b>目标表{i}:</b> {display_name}
<span style="color: #6b7280;">目标表记录: {target_total}条 | 匹配到: {matched}条</span>
<span style="color: #10b981;">精确: {t_exact}</span> | <span style="color: #3b82f6;">高置信: {t_high}</span> | <span style="color: #f59e0b;">需确认: {t_review}</span>"""
                
                detail_label = QLabel(detail_text)
                detail_label.setWordWrap(True)
                detail_label.setStyleSheet("""
                    background: #f8fafc; 
                    border: 1px solid #e2e8f0; 
                    border-radius: 6px; 
                    padding: 8px 12px;
                    line-height: 1.5;
                """)
                scroll_layout.addWidget(detail_label)
        
        # ===== 自动匹配率 =====
        rate_label = QLabel(f"✨ 自动匹配率: <b>{auto_match_rate:.1f}%</b>（无需人工确认）")
        rate_label.setStyleSheet("font-size: 14px; color: #059669; margin-top: 8px;")
        scroll_layout.addWidget(rate_label)
        
        # ===== 保存提示 =====
        save_label = QLabel(f"""💾 结果已保存到缓存目录的 <b>match_results</b> 文件夹""")
        save_label.setStyleSheet("color: #6b7280; margin-top: 4px;")
        scroll_layout.addWidget(save_label)
        
        scroll_layout.addStretch()
        scroll.setWidget(scroll_widget)
        layout.addWidget(scroll, 1)
        
        # ===== 确定按钮 =====
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_ok = QPushButton("确定")
        btn_ok.setMinimumWidth(100)
        btn_ok.setStyleSheet("""
            QPushButton {
                background: #2563eb;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 24px;
                font-weight: bold;
            }
            QPushButton:hover { background: #1d4ed8; }
        """)
        btn_ok.clicked.connect(dialog.accept)
        btn_layout.addWidget(btn_ok)
        layout.addLayout(btn_layout)
        
        dialog.exec()
    
    def _create_layer_info_box(self, title: str, count: int, rate: float, 
                                desc: str, color: str, bg_color: str) -> QLabel:
        """创建分层信息框"""
        text = f"""<b style="color: {color};">{title}: {count} 条 ({rate:.1f}%)</b>
<span style="color: #6b7280; font-size: 12px;">{desc}</span>"""
        
        label = QLabel(text)
        label.setWordWrap(True)
        label.setStyleSheet(f"""
            background: {bg_color};
            border-left: 4px solid {color};
            border-radius: 4px;
            padding: 8px 12px;
            line-height: 1.5;
        """)
        return label
    
    def _export_current_group_results(self):
        """导出当前任务组的匹配结果 - 弹出选择对话框"""
        from qgis.PyQt.QtWidgets import (
            QDialog, QVBoxLayout, QHBoxLayout, QLabel, QCheckBox,
            QRadioButton, QButtonGroup, QPushButton, QFileDialog, QMessageBox,
            QGroupBox
        )
        
        if self._current_group_idx < 0:
            return
        
        group = self._task_groups[self._current_group_idx]
        task_name = group.get("name", "未命名任务")
        source_file = group.get("source", "")
        stats = group.get("match_stats", {})
        
        # 检查是否有执行结果
        if group.get("status") != "已完成":
            QMessageBox.warning(self, "无法导出", "请先执行任务，完成后再导出结果")
            return
        
        if not source_file:
            QMessageBox.warning(self, "配置错误", "任务组未配置源表")
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
            QMessageBox.warning(self, "无结果", "匹配结果目录不存在，请先执行任务")
            return
        
        # 源表名
        source_name = os.path.splitext(source_file)[0].replace("_标准化", "")
        source_name = source_name.replace(" ", "_").replace("/", "_").replace("\\", "_")
        
        # 收集结果文件及其层级
        level_info = {
            '精确匹配': {'file': None, 'count': stats.get('exact', 0)},
            '高置信度': {'file': None, 'count': stats.get('high_confidence', 0)},
            '需人工确认': {'file': None, 'count': stats.get('need_review', 0)},
            '未匹配': {'file': None, 'count': stats.get('unmatched', 0)}
        }
        
        for f in os.listdir(result_dir):
            if f.startswith(source_name) and f.endswith('.csv'):
                for level in level_info:
                    if level in f:
                        level_info[level]['file'] = os.path.join(result_dir, f)
                        break
        
        # 检查是否有结果文件
        has_files = any(v['file'] for v in level_info.values())
        if not has_files:
            QMessageBox.warning(self, "无结果", f"未找到源表 '{source_file}' 的匹配结果文件")
            return
        
        # ===== 创建导出选择对话框 =====
        dialog = QDialog(self)
        dialog.setWindowTitle("导出匹配结果")
        dialog.setMinimumWidth(420)
        
        layout = QVBoxLayout(dialog)
        layout.setSpacing(12)
        
        # 标题
        title = QLabel(f"📤 导出匹配结果 - {task_name}")
        title.setStyleSheet("font-size: 14px; font-weight: bold; color: #1f2937;")
        layout.addWidget(title)
        
        # 源表信息
        info = QLabel(f"源表: {source_file}")
        info.setStyleSheet("color: #6b7280;")
        layout.addWidget(info)
        
        # ===== 层级选择 =====
        level_group = QGroupBox("选择要导出的层级")
        level_layout = QVBoxLayout(level_group)
        
        self._export_checkboxes = {}
        for level, data in level_info.items():
            count = data['count']
            has_file = data['file'] is not None
            
            cb = QCheckBox(f"{level} ({count} 条)")
            cb.setEnabled(has_file and count > 0)
            cb.setChecked(has_file and count > 0 and level != '未匹配')  # 默认选中有数据的（除未匹配）
            
            if not has_file:
                cb.setToolTip("无结果文件")
            elif count == 0:
                cb.setToolTip("无数据")
            
            self._export_checkboxes[level] = cb
            level_layout.addWidget(cb)
        
        layout.addWidget(level_group)
        
        # ===== 格式选择 =====
        format_group = QGroupBox("导出格式")
        format_layout = QHBoxLayout(format_group)
        
        self._format_group = QButtonGroup()
        rb_excel = QRadioButton("Excel (带颜色区分)")
        rb_excel.setChecked(True)
        rb_csv = QRadioButton("CSV")
        
        self._format_group.addButton(rb_excel, 0)
        self._format_group.addButton(rb_csv, 1)
        
        format_layout.addWidget(rb_excel)
        format_layout.addWidget(rb_csv)
        format_layout.addStretch()
        
        layout.addWidget(format_group)
        
        # ===== 合并选择 =====
        merge_group = QGroupBox("合并方式")
        merge_layout = QHBoxLayout(merge_group)
        
        self._merge_group = QButtonGroup()
        rb_merge = QRadioButton("合并为一个文件")
        rb_merge.setChecked(True)
        rb_separate = QRadioButton("每层级单独文件")
        
        self._merge_group.addButton(rb_merge, 0)
        self._merge_group.addButton(rb_separate, 1)
        
        merge_layout.addWidget(rb_merge)
        merge_layout.addWidget(rb_separate)
        merge_layout.addStretch()
        
        layout.addWidget(merge_group)
        
        # ===== 按钮 =====
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        btn_cancel = QPushButton("取消")
        btn_cancel.clicked.connect(dialog.reject)
        btn_layout.addWidget(btn_cancel)
        
        btn_export = QPushButton("选择位置并导出")
        btn_export.setStyleSheet("""
            QPushButton {
                background: #2563eb;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover { background: #1d4ed8; }
        """)
        btn_export.clicked.connect(lambda: self._do_export(
            dialog, level_info, source_file, source_name, region_info
        ))
        btn_layout.addWidget(btn_export)
        
        layout.addLayout(btn_layout)
        
        dialog.exec()
    
    def _do_export(self, dialog, level_info, source_file, source_name, region_info):
        """执行导出"""
        from qgis.PyQt.QtWidgets import QFileDialog
        from ..widgets.progress_dialog import ProgressDialog
        from ..workers.match_export_worker import MatchExportWorker
        
        # 获取选中的层级
        selected_levels = []
        result_files = []
        for level, cb in self._export_checkboxes.items():
            if cb.isChecked():
                selected_levels.append(level)
                if level_info[level]['file']:
                    result_files.append(level_info[level]['file'])
        
        if not selected_levels:
            from qgis.PyQt.QtWidgets import QMessageBox
            QMessageBox.warning(dialog, "请选择", "请至少选择一个层级")
            return
        
        # 获取格式
        is_excel = self._format_group.checkedId() == 0
        is_merge = self._merge_group.checkedId() == 0
        
        base_folder = region_info.get('base_folder', '')
        
        if is_merge:
            # 合并导出 - 选择单个文件
            ext = ".xlsx" if is_excel else ".csv"
            filter_str = "Excel 文件 (*.xlsx)" if is_excel else "CSV 文件 (*.csv)"
            default_name = f"{source_name}_匹配结果{ext}"
            
            output_path, _ = QFileDialog.getSaveFileName(
                dialog, "导出匹配结果", 
                os.path.join(base_folder, default_name),
                filter_str
            )
            
            if not output_path:
                return
            
            dialog.accept()
            
            # 后台导出
            self._start_export_worker(
                result_files, output_path, selected_levels, 
                'excel' if is_excel else 'csv', source_file
            )
        else:
            # 分开导出 - 选择目录
            export_dir = QFileDialog.getExistingDirectory(
                dialog, "选择导出目录", base_folder
            )
            
            if not export_dir:
                return
            
            dialog.accept()
            
            # 分别导出每个文件
            self._export_separate_files(
                result_files, export_dir, is_excel, source_file
            )
    
    def _start_export_worker(self, result_files, output_path, levels, export_format, source_file):
        """启动后台导出线程"""
        from ..widgets.progress_dialog import ProgressDialog
        from ..widgets.result_dialog import ResultDialog
        from ..workers.match_export_worker import MatchExportWorker
        
        # 创建进度对话框
        progress_dialog = ProgressDialog(
            self, "导出匹配结果", "正在准备...", cancelable=True
        )
        
        # 创建 Worker
        self._export_worker = MatchExportWorker(
            result_files=result_files,
            output_path=output_path,
            levels=levels,
            export_format=export_format,
            source_file=source_file,
            parent=self
        )
        
        # 连接信号
        self._export_worker.progress.connect(
            lambda pct, msg: progress_dialog.set_progress(pct, msg)
        )
        self._export_worker.log.connect(self._log)
        self._export_worker.finished.connect(
            lambda result: self._on_export_finished(result, progress_dialog)
        )
        self._export_worker.error.connect(
            lambda err: self._on_export_error(err, progress_dialog)
        )
        
        # 取消按钮
        progress_dialog.on_cancel = self._export_worker.cancel
        
        # 启动
        self._export_worker.start()
        progress_dialog.exec()
    
    def _on_export_finished(self, result, progress_dialog):
        """导出完成"""
        from ..widgets.result_dialog import ResultDialog
        
        progress_dialog.close()
        self._export_worker = None
        
        if result.get('cancelled'):
            self._log("[Step4] 导出已取消", "warning")
            return
        
        if result.get('success'):
            ResultDialog.show_success(
                self, "导出成功",
                f"{result['message']}\n\n保存位置:\n{result.get('output_path', '')}"
            )
            self._log(f"[Step4] 导出成功: {result['message']}", "info")
        else:
            ResultDialog.show_warning(self, "导出失败", result.get('message', '未知错误'))
    
    def _on_export_error(self, error_msg, progress_dialog):
        """导出出错"""
        from ..widgets.result_dialog import ResultDialog
        
        progress_dialog.close()
        self._export_worker = None
        
        ResultDialog.show_error(self, "导出失败", error_msg)
        self._log(f"[Step4] 导出出错: {error_msg}", "error")
    
    def _export_separate_files(self, result_files, export_dir, is_excel, source_file):
        """分别导出多个文件"""
        from ..widgets.result_dialog import ResultDialog
        import shutil
        
        if is_excel:
            # Excel 格式需要转换
            from ...core.match_result_exporter import MatchResultExporter
            import pandas as pd
            
            exporter = MatchResultExporter(log_callback=self._log)
            exported = []
            
            for f in result_files:
                try:
                    df = pd.read_csv(f, encoding='utf-8-sig')
                    basename = os.path.splitext(os.path.basename(f))[0]
                    output_path = os.path.join(export_dir, f"{basename}.xlsx")
                    result = exporter.export_to_excel(df, output_path, source_file)
                    if result['success']:
                        exported.append(os.path.basename(output_path))
                except Exception as e:
                    self._log(f"[Step4] 导出失败: {f}, {e}", "error")
            
            if exported:
                ResultDialog.show_success(
                    self, "导出成功",
                    f"已导出 {len(exported)} 个文件到:\n{export_dir}"
                )
        else:
            # CSV 直接复制
            exported = []
            for f in result_files:
                try:
                    dst = os.path.join(export_dir, os.path.basename(f))
                    shutil.copy2(f, dst)
                    exported.append(os.path.basename(dst))
                except Exception as e:
                    self._log(f"[Step4] 导出失败: {f}, {e}", "error")
            
            if exported:
                ResultDialog.show_success(
                    self, "导出成功",
                    f"已导出 {len(exported)} 个文件到:\n{export_dir}"
                )
    
    def _delete_current_group(self):
        """删除当前任务组及其匹配结果"""
        from qgis.PyQt.QtWidgets import QMessageBox
        import os
        import glob
        
        if self._current_group_idx < 0:
            return
        
        group = self._task_groups[self._current_group_idx]
        group_name = group.get('name', '未命名')
        source_file = group.get('source', '')
        
        # 确认删除
        reply = QMessageBox.question(
            self, "确认删除",
            f"确定要删除任务组 [{group_name}] 吗？\n\n"
            f"这将同时删除该任务组的：\n"
            f"  - 匹配结果文件\n"
            f"  - 缓存数据",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply != QMessageBox.StandardButton.Yes:
            return
        
        # 删除匹配结果文件
        deleted_files = []
        if source_file:
            try:
                global_config = self._get_global_config()
                if global_config:
                    region_info = global_config.get_region_info()
                    cache_folder = region_info.get('cache_folder', '')
                    
                    if cache_folder:
                        results_folder = os.path.join(cache_folder, 'match_results')
                        if os.path.exists(results_folder):
                            # 获取源表名称（不含扩展名）
                            source_base = os.path.splitext(source_file)[0]
                            
                            # 删除以源表名开头的所有结果文件
                            pattern = os.path.join(results_folder, f"{source_base}*.csv")
                            for f in glob.glob(pattern):
                                try:
                                    os.remove(f)
                                    deleted_files.append(os.path.basename(f))
                                except Exception as e:
                                    self._log(f"[Step4] 删除文件失败: {f}, {e}", "warning")
            except Exception as e:
                self._log(f"[Step4] 清理匹配结果时出错: {e}", "warning")
        
        # 删除任务组
        del self._task_groups[self._current_group_idx]
        self._current_group_idx = -1
        self._persist_tasks()  # 持久化
        self._refresh_task_list()
        
        # 隐藏配置面板和统计区域
        self.config_container.setVisible(False)
        self.stats_group.setVisible(False)
        self.empty_hint.setVisible(True)
        self.config_title.setText("请选择一个任务组")
        
        # 记录删除的文件
        if deleted_files:
            self._log(f"[Step4] 删除任务组: {group_name}，清理了 {len(deleted_files)} 个结果文件", "info")
        else:
            self._log(f"[Step4] 删除任务组: {group_name}", "info")
    
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
