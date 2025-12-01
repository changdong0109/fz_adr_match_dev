"""
Step2: 字段映射与清洗Widget
包含：文件配置进度、字段组合配置、批量清洗
"""
import os
from typing import Callable, Dict, List, Optional
from qgis.PyQt.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel, QLineEdit,
    QPushButton, QComboBox, QTableWidget, QTableWidgetItem, QCheckBox,
    QProgressBar, QRadioButton, QScrollArea, QFrame, QMessageBox,
    QAbstractItemView
)
from qgis.PyQt.QtGui import QColor, QWheelEvent
from qgis.PyQt.QtCore import Qt, QSettings
from ..utils import safe_select_rows, safe_no_edit, set_resize_mode, safe_get_item_flag_enabled
from ..widgets.base_step_widget import BaseStepWidget
from ..collapsible_section import CollapsibleSection
# 导入core层
from ...core.data_loader import DataLoader


class NoWheelComboBox(QComboBox):
    """禁用滚轮的下拉框"""
    def wheelEvent(self, event: QWheelEvent):
        """忽略滚轮事件，防止意外修改"""
        event.ignore()


class Step2Widget(BaseStepWidget):
    """Step2: 字段映射与清洗"""
    
    def __init__(self, parent=None, log_callback: Optional[Callable[[str, str], None]] = None, 
                 task_manager=None):
        super().__init__(parent, log_callback, task_manager)
        
        # 文件配置数据：{file_name: {name, saved_path, source_type, field_count, configured, cleaned, columns}}
        self.file_configs: Dict[str, Dict] = {}
        
        # 当前选中的文件ID（文件名）
        self.current_file_id: Optional[str] = None
        
        # 字段组合配置：{file_name: combo}（一个文件只能有一个组合）
        # combo结构：{title, subtitle, fields: [{role, field}]}
        self.file_combo_configs: Dict[str, Dict] = {}
        
        # 文件列名缓存：{file_name: [column1, column2, ...]}
        self.file_columns_cache: Dict[str, List[str]] = {}
        
        # 当前显示的字段表格（用于保存时读取数据）
        self.current_field_table: Optional[QTableWidget] = None
        
        self._build_ui()
        # 设置尺寸策略，让Step2Widget能够扩展填满可用空间
        self._set_expanding_size_policy()
        
        # 延迟刷新文件列表（确保Step1已初始化）
        from qgis.PyQt.QtCore import QTimer
        QTimer.singleShot(500, self._refresh_file_list)
    
    def _set_expanding_size_policy(self):
        """设置Step2Widget的尺寸策略为Expanding"""
        from qgis.PyQt.QtWidgets import QSizePolicy
        try:
            if hasattr(QSizePolicy, 'Policy') and hasattr(QSizePolicy.Policy, 'Expanding'):
                expanding = QSizePolicy.Policy.Expanding
            elif hasattr(QSizePolicy, 'Expanding'):
                expanding = QSizePolicy.Expanding
            else:
                expanding = 7  # Expanding = 7
            self.setSizePolicy(expanding, expanding)
        except (AttributeError, TypeError):
            self.setSizePolicy(7, 7)  # Expanding, Expanding
    
    def _set_groupbox_expanding(self, box: QGroupBox):
        """为QGroupBox设置水平扩展尺寸策略"""
        from qgis.PyQt.QtWidgets import QSizePolicy
        try:
            if hasattr(QSizePolicy, 'Policy'):
                if hasattr(QSizePolicy.Policy, 'Expanding'):
                    expanding = QSizePolicy.Policy.Expanding
                    preferred = QSizePolicy.Policy.Preferred
                else:
                    expanding = 7
                    preferred = 1
            elif hasattr(QSizePolicy, 'Expanding'):
                expanding = QSizePolicy.Expanding
                preferred = QSizePolicy.Preferred
            else:
                expanding = 7
                preferred = 1
            box.setSizePolicy(expanding, preferred)  # 水平扩展，垂直Preferred
        except (AttributeError, TypeError):
            box.setSizePolicy(7, 1)  # Expanding, Preferred
    
    def _build_ui(self):
        """构建UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 6, 0, 6)  # 移除左右边距，由父容器统一控制
        
        layout.addWidget(self._card_cfg_progress())
        layout.addWidget(self._card_field_combos())
        layout.addWidget(self._card_clean())
        # 移除addStretch，让内容充分利用空间
    
    def _card_cfg_progress(self):
        """文件配置列表（可折叠）"""
        # 使用 CollapsibleSection 实现可折叠功能
        section = CollapsibleSection("文件配置列表", expanded=True)
        
        # 设置尺寸策略，让 CollapsibleSection 能够扩展填满可用空间
        from qgis.PyQt.QtWidgets import QSizePolicy
        try:
            if hasattr(QSizePolicy, 'Policy'):
                if hasattr(QSizePolicy.Policy, 'Expanding'):
                    expanding = QSizePolicy.Policy.Expanding
                    preferred = QSizePolicy.Policy.Preferred
                else:
                    expanding = 7
                    preferred = 1
            elif hasattr(QSizePolicy, 'Expanding'):
                expanding = QSizePolicy.Expanding
                preferred = QSizePolicy.Preferred
            else:
                expanding = 7
                preferred = 1
            section.setSizePolicy(expanding, preferred)  # 水平扩展，垂直Preferred
        except (AttributeError, TypeError):
            section.setSizePolicy(7, 1)  # Expanding, Preferred
        
        # 创建内容容器
        content_widget = QWidget()
        v = QVBoxLayout(content_widget)
        v.addWidget(QLabel("每个文件可以配置多个\"字段组合\"；配置好后统一批量清洗。"))
        
        self.cfg_progress_table = QTableWidget(0, 5)
        self.cfg_progress_table.setObjectName("step2_cfg_progress_table")
        self.cfg_progress_table.setHorizontalHeaderLabels(["当前", "文件名", "字段组合数", "配置状态", "清洗状态"])
        # 设置表格最小高度，让表格能显示多行数据（参考Step1的设置）
        self.cfg_progress_table.setMinimumHeight(200)
        safe_select_rows(self.cfg_progress_table)
        safe_no_edit(self.cfg_progress_table)
        header = self.cfg_progress_table.horizontalHeader()
        # 优化列宽设置
        # 当前列：固定宽度（单选按钮）
        set_resize_mode(header, 0, prefer_contents=True)
        header.resizeSection(0, 60)
        # 文件名列：自动扩展
        set_resize_mode(header, 1, prefer_contents=False)
        # 字段组合数列：固定宽度
        set_resize_mode(header, 2, prefer_contents=True)
        header.resizeSection(2, 100)
        # 已配置列：固定宽度
        set_resize_mode(header, 3, prefer_contents=True)
        header.resizeSection(3, 80)
        # 清洗状态列：固定宽度
        set_resize_mode(header, 4, prefer_contents=True)
        header.resizeSection(4, 100)
        
        # 添加刷新按钮
        btn_row = QHBoxLayout()
        btn_refresh = QPushButton("刷新文件列表")
        btn_refresh.setObjectName("step2_btn_refresh")
        btn_refresh.clicked.connect(self._refresh_file_list)
        btn_row.addWidget(btn_refresh)
        btn_row.addStretch()
        v.addLayout(btn_row)
        
        v.addWidget(self.cfg_progress_table)
        
        # 将内容添加到可折叠区域
        section.add_widget(content_widget)
        
        return section
    
    def _refresh_file_list(self):
        """刷新文件列表（从Step1获取数据源）"""
        # 获取Step1的数据源
        step1_data_sources = self.get_step1_data_sources()
        if not step1_data_sources:
            self._log("[Step2] 未找到Step1的数据源，请先在Step1导入文件", "warn")
            # 清空表格
            self.cfg_progress_table.setRowCount(0)
            self.file_configs.clear()
            return
        
        # 清空当前配置
        self.file_configs.clear()
        
        # 从Step1的数据源构建文件配置
        for file_name, file_info in step1_data_sources.items():
            saved_path = file_info.get('saved_path', '')
            source_type = file_info.get('source_type', '其他')
            cleaned = file_info.get('cleaned', '未清洗')
            
            # 检查文件是否存在
            if not saved_path or not os.path.exists(saved_path):
                continue
            
            # 尝试从cache目录加载已保存的配置（如果内存中没有）
            if file_name not in self.file_combo_configs:
                self._load_file_combo_config(file_name)
            
            # 获取字段组合配置（一个文件只有一个组合）
            combo = self.file_combo_configs.get(file_name)
            
            # 计算字段数量（配置里配置了几个字段）
            field_count = 0
            if combo and combo.get('fields'):
                field_count = len(combo['fields'])
            
            # 判断配置状态
            if not combo or not combo.get('fields') or len(combo['fields']) == 0:
                configured = "未配置"
            else:
                configured = "已配置"
            
            # 保存文件配置
            self.file_configs[file_name] = {
                "name": file_name,
                "saved_path": saved_path,
                "source_type": source_type,
                "field_count": field_count,  # 字段数量（配置里配置了几个字段）
                "configured": configured,
                "cleaned": cleaned
            }
        
        # 更新表格显示
        self._update_cfg_progress_table()
        
        # 不再自动选中第一个文件，用户需要手动选择
        # 如果当前选中的文件不在新列表中，清除选择
        if self.current_file_id and self.current_file_id not in self.file_configs:
            self.current_file_id = None
            self._refresh_file_config_display()
        
        self._log(f"[Step2] 已刷新文件列表，找到 {len(self.file_configs)} 个文件", "info")
    
    def _update_cfg_progress_table(self):
        """更新文件配置进度表格"""
        self.cfg_progress_table.setRowCount(len(self.file_configs))
        
        for r, (file_name, data) in enumerate(self.file_configs.items()):
            # 当前单选按钮
            radio = QRadioButton()
            radio.setObjectName(file_name)
            if file_name == self.current_file_id:
                radio.setChecked(True)
            radio.toggled.connect(lambda checked, f=file_name: self._on_file_selected(f) if checked else None)
            self.cfg_progress_table.setCellWidget(r, 0, radio)
            
            # 文件名
            self.cfg_progress_table.setItem(r, 1, QTableWidgetItem(data["name"]))
            
            # 字段组合数（配置里配置了几个字段）
            self.cfg_progress_table.setItem(r, 2, QTableWidgetItem(str(data.get("field_count", 0))))
            
            # 配置状态
            config_item = QTableWidgetItem(data["configured"])
            if data["configured"] == "已配置":
                config_item.setForeground(QColor("#15803d"))
            elif data["configured"] == "部分":
                config_item.setForeground(QColor("#92400e"))
            self.cfg_progress_table.setItem(r, 3, config_item)
            
            # 清洗状态
            clean_item = QTableWidgetItem(data["cleaned"])
            if data["cleaned"] == "已清洗":
                clean_item.setForeground(QColor("#15803d"))
            self.cfg_progress_table.setItem(r, 4, clean_item)
        
    def _card_field_combos(self):
        """字段组合（可折叠）"""
        # 使用 CollapsibleSection 实现可折叠功能
        section = CollapsibleSection("字段组合", expanded=True)
        
        # 设置尺寸策略，让 CollapsibleSection 能够扩展填满可用空间
        from qgis.PyQt.QtWidgets import QSizePolicy
        try:
            if hasattr(QSizePolicy, 'Policy'):
                if hasattr(QSizePolicy.Policy, 'Expanding'):
                    expanding = QSizePolicy.Policy.Expanding
                    preferred = QSizePolicy.Policy.Preferred
                else:
                    expanding = 7
                    preferred = 1
            elif hasattr(QSizePolicy, 'Expanding'):
                expanding = QSizePolicy.Expanding
                preferred = QSizePolicy.Preferred
            else:
                expanding = 7
                preferred = 1
            section.setSizePolicy(expanding, preferred)  # 水平扩展，垂直Preferred
        except (AttributeError, TypeError):
            section.setSizePolicy(7, 1)  # Expanding, Preferred
        
        # 创建内容容器
        content_widget = QWidget()
        v = QVBoxLayout(content_widget)
        # 优化边距和间距，减少留白，为表格腾出更多空间
        v.setContentsMargins(16, 12, 16, 12)  # 减小上下边距
        v.setSpacing(8)  # 减小间距
        
        scroll = QScrollArea()
        scroll.setObjectName("step2_field_combos_scroll")
        scroll.setWidgetResizable(True)
        # 增加滚动区域的最小高度，给表格更多显示空间
        scroll.setMinimumHeight(400)  # 增加高度，让表格有更多显示空间
        
        self.file_config_container = QWidget()
        self.file_config_layout = QVBoxLayout(self.file_config_container)
        # 减小内边距，减少留白
        self.file_config_layout.setContentsMargins(4, 4, 4, 4)  # 减小内边距
        self.file_config_layout.setSpacing(8)  # 减小间距
        
        scroll.setWidget(self.file_config_container)
        v.addWidget(scroll)
        
        # 将内容添加到可折叠区域
        section.add_widget(content_widget)
        
        self._refresh_file_config_display()
        return section
    
    def _card_clean(self) -> QGroupBox:
        """批量执行清洗"""
        box = QGroupBox("批量执行清洗")
        self._set_groupbox_expanding(box)
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
        # 切换文件时自动加载已保存的配置
        self._load_file_combo_config(file_id)
        self._refresh_file_config_display()
    
    def _refresh_file_config_display(self):
        """刷新当前文件的配置显示"""
        while self.file_config_layout.count():
            child = self.file_config_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        
        if not self.current_file_id or self.current_file_id not in self.file_configs:
            # 如果没有选中的文件，显示提示
            tip_label = QLabel("请先选择一个文件")
            tip_label.setObjectName("step2_tip_label")
            self.file_config_layout.addWidget(tip_label)
            return
        
        # 尝试从cache目录加载已保存的配置
        self._load_file_combo_config(self.current_file_id)
        
        # 获取当前文件的组合配置（一个文件只有一个组合）
        combo = self.file_combo_configs.get(self.current_file_id)
        
        # 判断是否有有效的字段配置（combo存在且fields不为空）
        has_valid_config = combo and combo.get('fields') and len(combo['fields']) > 0
        
        # 按钮行布局（放在最顶部，方便操作）
        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)  # 增加按钮间距，避免重合
        btn_row.setContentsMargins(0, 0, 0, 0)  # 移除按钮行的边距
        
        # 创建/编辑字段组合按钮（一个文件只能有一个组合）
        if has_valid_config:
            btn_text = "编辑字段组合"
        else:
            btn_text = "+ 创建字段组合"
        btn_add_combo = QPushButton(btn_text)
        btn_add_combo.setObjectName("step2_btn_add_combo")
        btn_add_combo.clicked.connect(lambda: self._create_or_edit_combo(self.current_file_id) if self.current_file_id else None)
        btn_row.addWidget(btn_add_combo)
        
        # 保存配置按钮（只在有有效配置时显示）
        if has_valid_config:
            btn_save = QPushButton("保存配置")
            btn_save.setObjectName("step2_btn_save_combo")
            btn_save.clicked.connect(lambda: self._save_file_combo_config(self.current_file_id) if self.current_file_id else None)
            btn_row.addWidget(btn_save)
        
        btn_row.addStretch()
        self.file_config_layout.addLayout(btn_row)
        
        # 说明文字（放在按钮下方，根据是否有配置动态显示，紧凑布局）
        if has_valid_config:
            tip_text = "每个组合下的字段顺序定义拼接顺序，系统不做智能推荐，只按你选的字段 & 顺序执行清洗。"
        else:
            tip_text = "当前文件尚未配置字段组合，请点击上方按钮创建。"
        tip_label = QLabel(tip_text)
        tip_label.setObjectName("step2_tip_label")
        tip_label.setWordWrap(True)  # 允许换行，减少垂直空间
        self.file_config_layout.addWidget(tip_label)
        
        # 当前文件标签（放在说明文字下方，紧凑布局）
        current_file_name = self.file_configs.get(self.current_file_id, {}).get("name", "")
        file_label = QLabel(f"当前文件：{current_file_name}")
        file_label.setObjectName("step2_current_file_label")
        self.file_config_layout.addWidget(file_label)
        
        # 如果有有效配置，显示组合；如果没有，不显示任何内容（按钮已经在上面了）
        if has_valid_config:
            combo_widget = self._create_combo_block(combo, 0)
            self.file_config_layout.addWidget(combo_widget)
    
    def _create_combo_block(self, combo: Dict, combo_idx: int) -> QWidget:
        """创建一个组合块"""
        combo_frame = QFrame()
        combo_frame.setObjectName("step2_combo_frame")
        combo_layout = QVBoxLayout(combo_frame)
        # 减小内边距和间距，减少留白，为表格腾出更多空间
        combo_layout.setContentsMargins(6, 6, 6, 6)  # 减小内边距
        combo_layout.setSpacing(6)  # 减小间距
        
        header_layout = QHBoxLayout()
        title_label = QLabel(f"{combo.get('title', '字段组合')}{combo.get('subtitle', '')}")
        title_label.setObjectName("step2_combo_title_label")
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        combo_layout.addLayout(header_layout)
        
        field_table = QTableWidget(len(combo['fields']), 4)
        field_table.setObjectName("step2_field_table")
        field_table.setHorizontalHeaderLabels(["顺序", "角色名称（备注）", "字段（当前文件列）", "操作"])
        # 参考 Step1 的表格设计，设置表格最小高度为 200px，让操作更方便
        field_table.setMinimumHeight(200)
        # 增加行高，确保操作列按钮完整显示（从 32px 增加到 48px）
        field_table.verticalHeader().setDefaultSectionSize(48)
        safe_select_rows(field_table)
        from ..utils import safe_set_edit_triggers
        safe_set_edit_triggers(field_table, allow_edit=True)
        
        header = field_table.horizontalHeader()
        # 优化列宽设置，让内容更清晰可见
        # 顺序列：固定宽度
        set_resize_mode(header, 0, prefer_contents=True)
        header.resizeSection(0, 60)
        # 角色名称列：固定宽度，确保能显示完整内容
        set_resize_mode(header, 1, prefer_contents=False)
        header.resizeSection(1, 150)
        # 字段列：自动扩展，确保下拉框能完整显示
        set_resize_mode(header, 2, prefer_contents=False)
        header.resizeSection(2, 200)
        # 操作列：增加宽度，确保按钮文字显示完整
        set_resize_mode(header, 3, prefer_contents=True)
        header.resizeSection(3, 180)  # 从 120 增加到 180，确保按钮文字完整显示
        
        for r, field_data in enumerate(combo['fields']):
            field_table.setItem(r, 0, QTableWidgetItem(str(r + 1)))
            field_table.item(r, 0).setFlags(safe_get_item_flag_enabled())
            
            role_item = QTableWidgetItem(field_data['role'])
            field_table.setItem(r, 1, role_item)
            
            # 使用 NoWheelComboBox，防止滚轮意外修改
            field_combo = NoWheelComboBox()
            # 设置为不可编辑，只能下拉选择（用户要求字段列不能下拉选择的问题）
            field_combo.setEditable(False)
            # 获取当前文件的列名
            file_columns = self._get_file_columns(self.current_file_id)
            if file_columns:
                field_combo.addItems(file_columns)
            else:
                # 如果无法获取列名，使用默认选项
                field_combo.addItems(["std_city", "province", "community_name", "estate_name", 
                                   "addr_detail", "door_info", "door_no", "street_name"])
            # 设置当前值
            if field_data.get('field'):
                if field_data.get('field') in file_columns:
                    field_combo.setCurrentText(field_data['field'])
                else:
                    # 如果字段不在列表中，先添加到列表
                    field_combo.addItem(field_data['field'])
            field_combo.setCurrentText(field_data['field'])
            field_table.setCellWidget(r, 2, field_combo)
            # 设置行高，确保按钮完整显示
            field_table.setRowHeight(r, 48)
            
            btn_widget = QWidget()
            btn_layout = QHBoxLayout(btn_widget)
            btn_layout.setContentsMargins(4, 2, 4, 2)  # 增加左右边距
            btn_layout.setSpacing(4)  # 增加按钮间距
            
            # 使用统一的方法创建操作按钮
            self._create_operation_buttons(field_table, r)
        
        combo_layout.addWidget(field_table)
        
        # 保存当前表格引用，用于保存时读取数据
        self.current_field_table = field_table
        
        # 新增字段按钮（与当前组合关联）
        btn_add_field = QPushButton("+ 新增字段")
        btn_add_field.setObjectName("step2_btn_add_field")
        btn_add_field.clicked.connect(lambda: self._add_field_row(field_table))
        combo_layout.addWidget(btn_add_field)
        
        return combo_frame
    
    def _move_field_row(self, table: QTableWidget, row: int, direction: int):
        """移动字段行"""
        new_row = row + direction
        if new_row < 0 or new_row >= table.rowCount():
            return
        
        # 保存两行的数据（不包括操作列，操作列需要重新创建）
        row_data = {}
        new_row_data = {}
        
        for col in range(table.columnCount() - 1):  # 不包括操作列（最后一列）
            # 保存原行的数据
            item = table.item(row, col)
            widget = table.cellWidget(row, col)
            if item:
                row_data[col] = ('item', item.text(), item.flags())
            elif widget and isinstance(widget, QComboBox):
                row_data[col] = ('combo', widget.currentText())
            else:
                row_data[col] = None
            
            # 保存新行的数据
            item = table.item(new_row, col)
            widget = table.cellWidget(new_row, col)
            if item:
                new_row_data[col] = ('item', item.text(), item.flags())
            elif widget and isinstance(widget, QComboBox):
                new_row_data[col] = ('combo', widget.currentText())
            else:
                new_row_data[col] = None
        
        # 交换数据（不包括操作列）
        for col in range(table.columnCount() - 1):
            # 清除旧数据
            table.setItem(row, col, None)
            table.setCellWidget(row, col, None)
            table.setItem(new_row, col, None)
            table.setCellWidget(new_row, col, None)
            
            # 设置原行数据到新行
            if row_data[col]:
                if row_data[col][0] == 'item':
                    item = QTableWidgetItem(row_data[col][1])
                    item.setFlags(row_data[col][2])
                    table.setItem(new_row, col, item)
                elif row_data[col][0] == 'combo':
                    combo = NoWheelComboBox()
                    combo.setEditable(False)
                    file_columns = self._get_file_columns(self.current_file_id)
                    if file_columns:
                        combo.addItems(file_columns)
                    if row_data[col][1] not in [combo.itemText(i) for i in range(combo.count())]:
                        combo.addItem(row_data[col][1])
                    combo.setCurrentText(row_data[col][1])
                    table.setCellWidget(new_row, col, combo)
            
            # 设置新行数据到原行
            if new_row_data[col]:
                if new_row_data[col][0] == 'item':
                    item = QTableWidgetItem(new_row_data[col][1])
                    item.setFlags(new_row_data[col][2])
                    table.setItem(row, col, item)
                elif new_row_data[col][0] == 'combo':
                    combo = NoWheelComboBox()
                    combo.setEditable(False)
                    file_columns = self._get_file_columns(self.current_file_id)
                    if file_columns:
                        combo.addItems(file_columns)
                    if new_row_data[col][1] not in [combo.itemText(i) for i in range(combo.count())]:
                        combo.addItem(new_row_data[col][1])
                    combo.setCurrentText(new_row_data[col][1])
                    table.setCellWidget(row, col, combo)
        
        # 更新顺序列
        table.item(row, 0).setText(str(row + 1))
        table.item(new_row, 0).setText(str(new_row + 1))
        
        # 重新创建操作列的按钮（因为行号变了，需要重新绑定事件）
        self._create_operation_buttons(table, row)
        self._create_operation_buttons(table, new_row)
        
        # 确保行高足够，让按钮完整显示
        table.setRowHeight(row, 48)
        table.setRowHeight(new_row, 48)
        
        self._log(f"[Step2] 移动字段行 {row} -> {new_row}")
    
    def _create_operation_buttons(self, table: QTableWidget, row: int):
        """创建操作列的按钮"""
        # 清除旧按钮
        old_widget = table.cellWidget(row, 3)
        if old_widget:
            old_widget.deleteLater()
        
        # 创建新按钮
        btn_widget = QWidget()
        btn_layout = QHBoxLayout(btn_widget)
        btn_layout.setContentsMargins(4, 2, 4, 2)
        btn_layout.setSpacing(4)
        
        btn_up = QPushButton("上移")
        btn_up.setObjectName("step2_btn_field_up")
        btn_up.clicked.connect(lambda checked, r=row: self._move_field_row(table, r, -1))
        
        btn_down = QPushButton("下移")
        btn_down.setObjectName("step2_btn_field_down")
        btn_down.clicked.connect(lambda checked, r=row: self._move_field_row(table, r, 1))
        
        btn_del = QPushButton("删")
        btn_del.setObjectName("step2_btn_field_delete")
        btn_del.clicked.connect(lambda checked, r=row: self._delete_field_row(table, r))
        
        btn_layout.addWidget(btn_up)
        btn_layout.addWidget(btn_down)
        btn_layout.addWidget(btn_del)
        table.setCellWidget(row, 3, btn_widget)
    
    def _delete_field_row(self, table: QTableWidget, row: int):
        """删除字段行"""
        if table.rowCount() <= 1:
            QMessageBox.warning(self, "提示", "至少保留一行。")
            return
        
        # 确认删除
        reply = QMessageBox.question(
            self, "确认删除", 
            f"确定要删除第 {row + 1} 行吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        
        table.removeRow(row)
        # 更新所有行的顺序号和按钮事件
        for r in range(table.rowCount()):
            if table.item(r, 0):
                table.item(r, 0).setText(str(r + 1))
            # 重新创建操作按钮（因为行号变了）
            self._create_operation_buttons(table, r)
        
        self._log(f"[Step2] 删除字段行 {row}")
    
    def _add_field_row(self, table: QTableWidget):
        """添加字段行"""
        row = table.rowCount()
        table.insertRow(row)
        
        # 设置行高，确保内容不挤在一起（与创建组合块时的行高一致）
        table.setRowHeight(row, 32)
        
        table.setItem(row, 0, QTableWidgetItem(str(row + 1)))
        table.item(row, 0).setFlags(safe_get_item_flag_enabled())
        table.setItem(row, 1, QTableWidgetItem(""))
        
        # 使用 NoWheelComboBox，防止滚轮意外修改
        field_combo = NoWheelComboBox()
        # 设置为不可编辑，只能下拉选择
        field_combo.setEditable(False)
        # 获取当前文件的列名
        file_columns = self._get_file_columns(self.current_file_id)
        if file_columns:
            field_combo.addItems(file_columns)
        else:
            # 如果无法获取列名，使用默认选项
            field_combo.addItems(["std_city", "province", "community_name", "estate_name", 
                                 "addr_detail", "door_info", "door_no", "street_name"])
        table.setCellWidget(row, 2, field_combo)
        
        # 使用统一的方法创建操作按钮
        self._create_operation_buttons(table, row)
        
        # 设置行高，确保按钮完整显示（从 32px 增加到 48px）
        table.setRowHeight(row, 48)
        
        self._log(f"[Step2] 新增字段行")
    
    def _create_or_edit_combo(self, file_id: str):
        """创建或编辑字段组合（一个文件只能有一个组合）"""
        # 验证文件ID是否有效
        if not file_id or file_id not in self.file_configs:
            QMessageBox.warning(self, "提示", "请先选择一个文件")
            return
        
        # 获取文件的第一个列名作为默认字段
        file_columns = self._get_file_columns(file_id)
        default_field = file_columns[0] if file_columns else ""
        
        # 如果已有组合，使用现有配置；否则创建新组合
        if file_id in self.file_combo_configs and self.file_combo_configs[file_id]:
            # 已有组合，使用现有配置
            combo = self.file_combo_configs[file_id]
        else:
            # 创建新组合
            combo = {
                "title": "字段组合",
            "subtitle": "",
                "fields": [{"role": "", "field": default_field}]
        }
            self.file_combo_configs[file_id] = combo
        
        # 更新文件配置中的字段数量和配置状态
        field_count = len(combo.get('fields', [])) if combo else 0
        self.file_configs[file_id]["field_count"] = field_count
        self.file_configs[file_id]["configured"] = "已配置" if field_count > 0 else "未配置"
        self._update_cfg_progress_table()
        
        # 刷新显示
        self._refresh_file_config_display()
        
        self._log(f"[Step2] 为文件 {self.file_configs[file_id]['name']} 创建/编辑字段组合")
    
    def _get_global_config(self):
        """获取全局配置（通过父对话框）"""
        parent = self.parent()
        while parent:
            if hasattr(parent, 'global_config'):
                return parent.global_config
            parent = parent.parent()
        return None
    
    def _get_combo_config_file_path(self, file_name: str) -> Optional[str]:
        """获取字段组合配置文件的保存路径"""
        global_config = self._get_global_config()
        if not global_config:
            return None
        
        region_info = global_config.get_region_info()
        cache_folder = region_info.get('cache_folder', '')
        if not cache_folder:
            return None
        
        # 使用文件名（不含扩展名）作为配置文件名
        file_stem = os.path.splitext(file_name)[0]
        config_file_name = f"{file_stem}_combo_config.json"
        return os.path.join(cache_folder, config_file_name)
    
    def _load_file_combo_config(self, file_name: str):
        """从cache目录加载文件的字段组合配置"""
        if not file_name:
            return
        
        config_path = self._get_combo_config_file_path(file_name)
        if not config_path or not os.path.exists(config_path):
            # 配置文件不存在，使用空配置
            return
        
        try:
            import json
            with open(config_path, 'r', encoding='utf-8') as f:
                combo = json.load(f)
            self.file_combo_configs[file_name] = combo
            self._log(f"[Step2] 已加载文件 {file_name} 的字段组合配置", "info")
        except Exception as e:
            self._log(f"[Step2] 加载配置失败 {file_name}：{e}", "error")
    
    def _save_file_combo_config(self, file_name: str):
        """保存文件的字段组合配置到cache目录"""
        if not file_name or file_name not in self.file_combo_configs:
            QMessageBox.warning(self, "提示", "当前文件没有字段组合配置")
            return
        
        # 从表格中读取当前配置
        if not self.current_field_table:
            QMessageBox.warning(self, "提示", "无法读取字段配置，请先创建字段组合")
            return
        
        # 读取表格中的所有字段数据
        fields = []
        for r in range(self.current_field_table.rowCount()):
            role_item = self.current_field_table.item(r, 1)
            field_widget = self.current_field_table.cellWidget(r, 2)
            role = role_item.text() if role_item else ""
            field = field_widget.currentText() if isinstance(field_widget, QComboBox) else ""
            if field:  # 只保存有字段名的行
                fields.append({"role": role, "field": field})
        
        if not fields:
            QMessageBox.warning(self, "提示", "请至少配置一个字段")
            return
        
        # 更新配置数据
        combo = self.file_combo_configs[file_name]
        combo['fields'] = fields
        
        # 保存到文件
        config_path = self._get_combo_config_file_path(file_name)
        if not config_path:
            QMessageBox.warning(self, "提示", "无法获取缓存目录，请检查全局配置")
            return
        
        try:
            import json
            # 确保目录存在
            os.makedirs(os.path.dirname(config_path), exist_ok=True)
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(combo, f, ensure_ascii=False, indent=2)
            
            # 更新文件配置状态：field_count（字段数量）和 configured（配置状态）
            field_count = len(fields)
            self.file_configs[file_name]["field_count"] = field_count
            self.file_configs[file_name]["configured"] = "已配置" if field_count > 0 else "未配置"
            
            # 刷新文件配置列表表格
            self._update_cfg_progress_table()
            
            self._log(f"[Step2] 已保存文件 {file_name} 的字段组合配置到：{config_path}", "success")
            QMessageBox.information(self, "提示", f"配置已保存成功，共 {field_count} 个字段")
        except Exception as e:
            self._log(f"[Step2] 保存配置失败 {file_name}：{e}", "error")
            QMessageBox.warning(self, "错误", f"保存配置失败：{e}")
    
    def _get_file_columns(self, file_name: str) -> List[str]:
        """
        获取文件的列名（带缓存）
        
        Args:
            file_name: 文件名
            
        Returns:
            列名列表
        """
        # 检查缓存
        if file_name in self.file_columns_cache:
            return self.file_columns_cache[file_name]
        
        # 获取文件路径
        if file_name not in self.file_configs:
            return []
        
        saved_path = self.file_configs[file_name].get('saved_path', '')
        if not saved_path or not os.path.exists(saved_path):
            return []
        
        try:
            # 使用 DataLoader 读取列名
            columns = DataLoader.get_file_columns(saved_path)
            # 缓存列名
            self.file_columns_cache[file_name] = columns
            return columns
        except Exception as e:
            self._log(f"[Step2] 读取文件列名失败 {file_name}：{e}", "error")
            return []

