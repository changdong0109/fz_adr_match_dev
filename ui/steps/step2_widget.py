"""
Step2: 字段映射与清洗Widget
包含：字段组合配置、清洗任务配置
"""
import os
from typing import Callable, Dict, List, Optional
from qgis.PyQt.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel, QLineEdit,
    QPushButton, QComboBox, QTableWidget, QTableWidgetItem, QCheckBox,
    QProgressBar, QRadioButton, QScrollArea, QFrame, QMessageBox,
    QAbstractItemView, QListWidget, QListWidgetItem
)
from qgis.PyQt.QtGui import QColor
from qgis.PyQt.QtCore import Qt, QSettings
from ..utils import safe_select_rows, safe_no_edit, set_resize_mode, safe_get_item_flag_enabled
from ..widgets.base_step_widget import BaseStepWidget
from ..widgets.result_dialog import ResultDialog
from ..widgets.no_wheel_combo_box import NoWheelComboBox
from ..collapsible_section import CollapsibleSection
# 导入core层
from ...core.data_loader import DataLoader
from ...core.data_cleaner import DataCleaner
# 导入后台 Worker
from ..workers.clean_worker import CleanWorker


class Step2Widget(BaseStepWidget):
    """Step2: 字段映射与清洗"""
    
    def __init__(self, parent=None, log_callback: Optional[Callable[[str, str], None]] = None, 
                 task_manager=None):
        super().__init__(parent, log_callback, task_manager)
        
        # 文件配置数据：{file_name: {name, saved_path, source_type, field_count, configured, cleaned, columns}}
        self.file_configs: Dict[str, Dict] = {}
        
        # 当前选中的文件ID（文件名）- 用于字段组合配置
        self.current_file_id: Optional[str] = None
        
        # 字段组合配置：{file_name: combo}（一个文件只能有一个组合）
        # combo结构：{title, subtitle, fields: [{role, field}]}
        self.file_combo_configs: Dict[str, Dict] = {}
        
        # 文件列名缓存：{file_name: [column1, column2, ...]}
        self.file_columns_cache: Dict[str, List[str]] = {}
        
        # 当前显示的字段表格（用于保存时读取数据）
        self.current_field_table: Optional[QTableWidget] = None
        
        # 清洗任务选中的文件列表
        self.clean_selected_files: Dict[str, bool] = {}
        
        # 后台清洗 Worker
        self._clean_worker: Optional[CleanWorker] = None
        
        self._build_ui()
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
    
    def _build_ui(self):
        """构建UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 6, 0, 6)
        layout.setSpacing(12)
        
        # 区块1：字段组合配置
        layout.addWidget(self._card_field_config())
        # 区块2：清洗任务配置
        layout.addWidget(self._card_clean_task())
    
    # ==================== 区块1：字段组合配置 ====================
    
    def _card_field_config(self):
        """字段组合配置区块"""
        section = CollapsibleSection("字段组合配置", expanded=True)
        self._set_section_size_policy(section)
        
        content_widget = QWidget()
        v = QVBoxLayout(content_widget)
        v.setContentsMargins(16, 12, 16, 12)
        v.setSpacing(12)
        
        # 文件选择行
        file_select_row = QHBoxLayout()
        file_select_row.setSpacing(12)
        
        file_label = QLabel("选择文件：")
        file_label.setObjectName("step2_file_select_label")
        file_select_row.addWidget(file_label)
        
        self.file_select_combo = NoWheelComboBox()
        self.file_select_combo.setObjectName("step2_file_select_combo")
        self.file_select_combo.setMinimumWidth(300)
        self.file_select_combo.currentTextChanged.connect(self._on_file_combo_changed)
        file_select_row.addWidget(self.file_select_combo)
        
        btn_refresh = QPushButton("刷新")
        btn_refresh.setObjectName("step2_btn_refresh")
        btn_refresh.clicked.connect(self._refresh_file_list)
        file_select_row.addWidget(btn_refresh)
        
        file_select_row.addStretch()
        v.addLayout(file_select_row)
        
        # 字段组合配置区域（使用滚动区域）
        scroll = QScrollArea()
        scroll.setObjectName("step2_field_config_scroll")
        scroll.setWidgetResizable(True)
        scroll.setMinimumHeight(350)
        
        self.field_config_container = QWidget()
        self.field_config_layout = QVBoxLayout(self.field_config_container)
        self.field_config_layout.setContentsMargins(4, 4, 4, 4)
        self.field_config_layout.setSpacing(8)
        
        scroll.setWidget(self.field_config_container)
        v.addWidget(scroll)
        
        section.add_widget(content_widget)
        return section
    
    def _on_file_combo_changed(self, display_text: str):
        """文件下拉框选择变化"""
        if not display_text or display_text == "请选择文件...":
            self.current_file_id = None
            self._refresh_field_config_display()
            return
        
        # 从itemData获取真实的文件名
        current_index = self.file_select_combo.currentIndex()
        file_name = self.file_select_combo.itemData(current_index)
        
        if not file_name or file_name not in self.file_configs:
            self.current_file_id = None
            self._refresh_field_config_display()
            return
        
        self.current_file_id = file_name
        # 加载已保存的配置
        self._load_file_combo_config(file_name)
        self._refresh_field_config_display()
    
    def _refresh_field_config_display(self):
        """刷新字段组合配置显示"""
        # 清空现有内容
        while self.field_config_layout.count():
            child = self.field_config_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        
        if not self.current_file_id or self.current_file_id not in self.file_configs:
            tip_label = QLabel("请先选择一个文件进行配置")
            tip_label.setObjectName("step2_tip_label")
            self.field_config_layout.addWidget(tip_label)
            return
        
        # 获取当前文件的组合配置
        combo = self.file_combo_configs.get(self.current_file_id)
        has_valid_config = combo and combo.get('fields') and len(combo['fields']) > 0
        
        # 按钮行
        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)
        btn_row.setContentsMargins(0, 0, 0, 0)
        
        btn_text = "编辑字段组合" if has_valid_config else "+ 创建字段组合"
        btn_add_combo = QPushButton(btn_text)
        btn_add_combo.setObjectName("step2_btn_add_combo")
        btn_add_combo.clicked.connect(lambda: self._create_or_edit_combo(self.current_file_id))
        btn_row.addWidget(btn_add_combo)
        
        if has_valid_config:
            btn_save = QPushButton("保存配置")
            btn_save.setObjectName("step2_btn_save_combo")
            btn_save.clicked.connect(lambda: self._save_file_combo_config(self.current_file_id))
            btn_row.addWidget(btn_save)
        
        btn_row.addStretch()
        self.field_config_layout.addLayout(btn_row)
        
        # 提示文字
        if has_valid_config:
            tip_text = f"当前文件：{self.current_file_id}，已配置 {len(combo['fields'])} 个字段"
        else:
            tip_text = f"当前文件：{self.current_file_id}，尚未配置字段组合"
        tip_label = QLabel(tip_text)
        tip_label.setObjectName("step2_current_file_label")
        self.field_config_layout.addWidget(tip_label)
        
        # 显示字段组合表格
        if has_valid_config:
            combo_widget = self._create_combo_block(combo, 0)
            self.field_config_layout.addWidget(combo_widget)
    
    def _create_combo_block(self, combo: Dict, combo_idx: int) -> QWidget:
        """创建字段组合配置块"""
        combo_frame = QFrame()
        combo_frame.setObjectName("step2_combo_frame")
        combo_layout = QVBoxLayout(combo_frame)
        combo_layout.setContentsMargins(6, 6, 6, 6)
        combo_layout.setSpacing(6)
        
        # 字段表格
        field_table = QTableWidget(len(combo['fields']), 4)
        field_table.setObjectName("step2_field_table")
        field_table.setHorizontalHeaderLabels(["顺序", "角色名称（备注）", "字段（当前文件列）", "操作"])
        field_table.setMinimumHeight(200)
        field_table.verticalHeader().setDefaultSectionSize(48)
        safe_select_rows(field_table)
        from ..utils import safe_set_edit_triggers
        safe_set_edit_triggers(field_table, allow_edit=True)
        
        header = field_table.horizontalHeader()
        set_resize_mode(header, 0, prefer_contents=True)
        header.resizeSection(0, 60)
        set_resize_mode(header, 1, prefer_contents=False)
        header.resizeSection(1, 150)
        set_resize_mode(header, 2, prefer_contents=False)
        header.resizeSection(2, 200)
        set_resize_mode(header, 3, prefer_contents=True)
        header.resizeSection(3, 180)
        
        for r, field_data in enumerate(combo['fields']):
            field_table.setItem(r, 0, QTableWidgetItem(str(r + 1)))
            field_table.item(r, 0).setFlags(safe_get_item_flag_enabled())
            
            role_item = QTableWidgetItem(field_data['role'])
            field_table.setItem(r, 1, role_item)
            
            field_combo = NoWheelComboBox()
            field_combo.setEditable(False)
            file_columns = self._get_file_columns(self.current_file_id)
            if file_columns:
                field_combo.addItems(file_columns)
            # 如果已有配置的字段不在列表中，也添加进去
            if field_data.get('field'):
                if field_data['field'] not in [field_combo.itemText(i) for i in range(field_combo.count())]:
                    field_combo.addItem(field_data['field'])
            field_combo.setCurrentText(field_data['field'])
            field_table.setCellWidget(r, 2, field_combo)
            field_table.setRowHeight(r, 48)
            
            self._create_operation_buttons(field_table, r)
        
        combo_layout.addWidget(field_table)
        self.current_field_table = field_table
        
        # 新增字段按钮
        btn_add_field = QPushButton("+ 新增字段")
        btn_add_field.setObjectName("step2_btn_add_field")
        btn_add_field.clicked.connect(lambda: self._add_field_row(field_table))
        combo_layout.addWidget(btn_add_field)
        
        return combo_frame
    
    def _create_operation_buttons(self, table: QTableWidget, row: int):
        """创建操作列按钮"""
        old_widget = table.cellWidget(row, 3)
        if old_widget:
            old_widget.deleteLater()
        
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
    
    def _move_field_row(self, table: QTableWidget, row: int, direction: int):
        """移动字段行"""
        new_row = row + direction
        if new_row < 0 or new_row >= table.rowCount():
            return
        
        # 保存两行数据
        row_data = {}
        new_row_data = {}
        
        for col in range(table.columnCount() - 1):
            item = table.item(row, col)
            widget = table.cellWidget(row, col)
            if item:
                row_data[col] = ('item', item.text(), item.flags())
            elif widget and isinstance(widget, QComboBox):
                row_data[col] = ('combo', widget.currentText())
            else:
                row_data[col] = None
            
            item = table.item(new_row, col)
            widget = table.cellWidget(new_row, col)
            if item:
                new_row_data[col] = ('item', item.text(), item.flags())
            elif widget and isinstance(widget, QComboBox):
                new_row_data[col] = ('combo', widget.currentText())
            else:
                new_row_data[col] = None
        
        # 交换数据
        for col in range(table.columnCount() - 1):
            table.setItem(row, col, None)
            table.setCellWidget(row, col, None)
            table.setItem(new_row, col, None)
            table.setCellWidget(new_row, col, None)
            
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
        
        # 更新顺序
        table.item(row, 0).setText(str(row + 1))
        table.item(new_row, 0).setText(str(new_row + 1))
        
        # 重新创建操作按钮
        self._create_operation_buttons(table, row)
        self._create_operation_buttons(table, new_row)
        table.setRowHeight(row, 48)
        table.setRowHeight(new_row, 48)
        
        self._log(f"[Step2] 移动字段行 {row} -> {new_row}")
    
    def _delete_field_row(self, table: QTableWidget, row: int):
        """删除字段行"""
        if table.rowCount() <= 1:
            ResultDialog.show_warning(self, "无法删除", "至少保留一行")
            return
        
        reply = QMessageBox.question(
            self, "确认删除", 
            f"确定要删除第 {row + 1} 行吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        
        table.removeRow(row)
        for r in range(table.rowCount()):
            item = table.item(r, 0)
            if item:
                item.setText(str(r + 1))
            self._create_operation_buttons(table, r)
        
        self._log(f"[Step2] 删除字段行 {row}")
    
    def _add_field_row(self, table: QTableWidget):
        """添加字段行"""
        row = table.rowCount()
        table.insertRow(row)
        table.setRowHeight(row, 48)
        
        table.setItem(row, 0, QTableWidgetItem(str(row + 1)))
        table.item(row, 0).setFlags(safe_get_item_flag_enabled())
        table.setItem(row, 1, QTableWidgetItem(""))
        
        field_combo = NoWheelComboBox()
        field_combo.setEditable(False)
        file_columns = self._get_file_columns(self.current_file_id)
        if file_columns:
            field_combo.addItems(file_columns)
        else:
            # 无法读取文件列名时，添加提示项
            field_combo.addItem("（无法读取列名，请检查文件）")
        table.setCellWidget(row, 2, field_combo)
        
        self._create_operation_buttons(table, row)
        self._log(f"[Step2] 新增字段行")
    
    def _create_or_edit_combo(self, file_id: str):
        """创建或编辑字段组合"""
        if not file_id or file_id not in self.file_configs:
            ResultDialog.show_warning(self, "未选择文件", "请先选择一个文件")
            return
        
        file_columns = self._get_file_columns(file_id)
        default_field = file_columns[0] if file_columns else ""
        
        if file_id in self.file_combo_configs and self.file_combo_configs[file_id]:
            combo = self.file_combo_configs[file_id]
        else:
            combo = {
                "title": "字段组合",
                "subtitle": "",
                "fields": [{"role": "", "field": default_field}]
            }
            self.file_combo_configs[file_id] = combo
        
        # 更新配置状态
        field_count = len(combo.get('fields', [])) if combo else 0
        self.file_configs[file_id]["field_count"] = field_count
        self.file_configs[file_id]["configured"] = "已配置" if field_count > 0 else "未配置"
        
        self._refresh_field_config_display()
        self._refresh_clean_task_list()
        
        self._log(f"[Step2] 为文件 {file_id} 创建/编辑字段组合")
    
    # ==================== 区块2：清洗任务配置 ====================
    
    def _card_clean_task(self):
        """清洗任务配置区块"""
        section = CollapsibleSection("清洗任务配置", expanded=True)
        self._set_section_size_policy(section)
        
        content_widget = QWidget()
        v = QVBoxLayout(content_widget)
        v.setContentsMargins(16, 12, 16, 12)
        v.setSpacing(12)
        
        # 说明文字
        tip_label = QLabel("勾选要参与清洗的文件，只有「已配置」的文件才能参与清洗。")
        tip_label.setObjectName("step2_clean_tip_label")
        v.addWidget(tip_label)
        
        # 文件列表（使用QListWidget，带复选框）
        self.clean_file_list = QListWidget()
        self.clean_file_list.setObjectName("step2_clean_file_list")
        self.clean_file_list.setMinimumHeight(150)
        self.clean_file_list.itemChanged.connect(self._on_clean_file_item_changed)
        v.addWidget(self.clean_file_list)
        
        # 操作按钮行
        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)
        
        btn_select_all = QPushButton("全选")
        btn_select_all.setObjectName("step2_btn_select_all")
        btn_select_all.clicked.connect(self._select_all_configured)
        btn_row.addWidget(btn_select_all)
        
        btn_deselect_all = QPushButton("取消选择")
        btn_deselect_all.setObjectName("step2_btn_deselect_all")
        btn_deselect_all.clicked.connect(self._deselect_all)
        btn_row.addWidget(btn_deselect_all)
        
        btn_refresh_list = QPushButton("刷新列表")
        btn_refresh_list.setObjectName("step2_btn_refresh_list")
        btn_refresh_list.clicked.connect(self._refresh_file_list)
        btn_row.addWidget(btn_refresh_list)
        
        btn_row.addStretch()
        v.addLayout(btn_row)
        
        # 进度条
        progress_row = QHBoxLayout()
        self.bar_clean = QProgressBar()
        self.bar_clean.setObjectName("step2_clean_progress")
        self.lbl_clean = QLabel("空闲")
        self.lbl_clean.setObjectName("step2_clean_status_label")
        progress_row.addWidget(self.bar_clean)
        progress_row.addWidget(self.lbl_clean)
        v.addLayout(progress_row)
        
        # 执行按钮行
        exec_row = QHBoxLayout()
        exec_row.setSpacing(12)
        
        self.btn_clean = QPushButton("执行清洗")
        self.btn_clean.setObjectName("step2_btn_run_clean")
        self.btn_clean.clicked.connect(self._run_clean_task)
        exec_row.addWidget(self.btn_clean)
        
        btn_pause = QPushButton("暂停")
        btn_pause.setObjectName("step2_btn_pause_clean")
        task_mgr = self.get_task_manager()
        btn_pause.clicked.connect(lambda: task_mgr.pause_task("clean", self.lbl_clean))
        exec_row.addWidget(btn_pause)
        
        btn_stop = QPushButton("终止")
        btn_stop.setObjectName("step2_btn_stop_clean")
        btn_stop.clicked.connect(lambda: task_mgr.stop_task("clean", self.bar_clean, self.lbl_clean))
        exec_row.addWidget(btn_stop)
        
        exec_row.addStretch()
        v.addLayout(exec_row)
        
        section.add_widget(content_widget)
        return section
    
    def _refresh_clean_task_list(self):
        """刷新清洗任务文件列表"""
        self.clean_file_list.blockSignals(True)
        self.clean_file_list.clear()
        
        for file_name, file_info in self.file_configs.items():
            configured = file_info.get("configured", "未配置")
            field_count = file_info.get("field_count", 0)
            cleaned = file_info.get("cleaned", "未清洗")
            
            # 创建列表项
            item_text = f"{file_name}  [{field_count}个字段]  [{configured}]  [{cleaned}]"
            item = QListWidgetItem(item_text)
            item.setData(Qt.ItemDataRole.UserRole, file_name)
            
            # 只有已配置的文件才能选中
            if configured == "已配置":
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                # 如果之前有选中状态则保持，否则默认勾选「已配置且未清洗」的文件
                if file_name in self.clean_selected_files:
                    is_checked = self.clean_selected_files[file_name]
                else:
                    # 默认勾选已配置且未清洗的文件
                    is_checked = (cleaned == "未清洗")
                    self.clean_selected_files[file_name] = is_checked
                item.setCheckState(Qt.CheckState.Checked if is_checked else Qt.CheckState.Unchecked)
            else:
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(Qt.CheckState.Unchecked)
                # 设置灰色表示不可选
                item.setForeground(QColor("#999999"))
                # 未配置的文件不参与清洗
                self.clean_selected_files[file_name] = False
            
            self.clean_file_list.addItem(item)
        
        self.clean_file_list.blockSignals(False)
    
    def _on_clean_file_item_changed(self, item: QListWidgetItem):
        """清洗文件列表项选中状态变化"""
        file_name = item.data(Qt.ItemDataRole.UserRole)
        is_checked = item.checkState() == Qt.CheckState.Checked
        self.clean_selected_files[file_name] = is_checked
    
    def _select_all_configured(self):
        """全选已配置的文件"""
        for i in range(self.clean_file_list.count()):
            item = self.clean_file_list.item(i)
            file_name = item.data(Qt.ItemDataRole.UserRole)
            if self.file_configs.get(file_name, {}).get("configured") == "已配置":
                item.setCheckState(Qt.CheckState.Checked)
                self.clean_selected_files[file_name] = True
    
    def _deselect_all(self):
        """全不选"""
        for i in range(self.clean_file_list.count()):
            item = self.clean_file_list.item(i)
            file_name = item.data(Qt.ItemDataRole.UserRole)
            item.setCheckState(Qt.CheckState.Unchecked)
            self.clean_selected_files[file_name] = False
    
    def _run_clean_task(self):
        """执行清洗任务（后台线程）"""
        # 检查是否已有任务在运行
        if self._clean_worker is not None and self._clean_worker.isRunning():
            ResultDialog.show_warning(self, "任务进行中", "请等待当前清洗任务完成")
            return
        
        # 获取选中的文件
        selected_files = [f for f, selected in self.clean_selected_files.items() if selected]
        
        if not selected_files:
            ResultDialog.show_warning(self, "未选择文件", "请先选择要清洗的文件")
            return
        
        # 检查所有选中的文件是否都已配置
        unconfigured = []
        for file_name in selected_files:
            if self.file_configs.get(file_name, {}).get("configured") != "已配置":
                unconfigured.append(file_name)
        
        if unconfigured:
            ResultDialog.show_warning(self, "配置不完整", f"以下文件尚未配置，无法清洗：\n{', '.join(unconfigured)}")
            return
        
        # === 智能字段配置预检查 ===
        config_warnings = self._precheck_field_configs(selected_files)
        if config_warnings:
            warning_text = "\n".join(config_warnings[:10])
            if len(config_warnings) > 10:
                warning_text += f"\n...还有 {len(config_warnings) - 10} 条警告"
            
            from qgis.PyQt.QtWidgets import QMessageBox
            reply = QMessageBox.warning(
                self,
                "字段配置可能有问题",
                f"检测到以下配置问题：\n\n{warning_text}\n\n是否仍要继续清洗？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                self._log("[Step2] 用户取消清洗（配置检查未通过）", "info")
                return
        
        # 获取全局配置
        global_config = self._get_global_config()
        if not global_config:
            ResultDialog.show_error(self, "配置错误", "无法获取全局配置")
            return
        
        region_info = global_config.get_region_info()
        province = region_info.get('province', '')
        city = region_info.get('city', '')
        county = region_info.get('county', '')
        base_folder = region_info.get('base_folder', '')
        
        if not province or not city or not base_folder:
            ResultDialog.show_warning(self, "配置缺失", "请先在全局配置中设置省市信息")
            return
        
        # 准备文件列表
        files_to_clean = []
        for file_name in selected_files:
            file_info = self.file_configs.get(file_name, {})
            file_path = file_info.get('saved_path', '')
            source_type = file_info.get('source_type', '其他')
            
            if not file_path or not os.path.exists(file_path):
                self._log(f"[Step2] 文件不存在：{file_name}", "error")
                continue
            
            combo = self.file_combo_configs.get(file_name)
            if not combo or not combo.get('fields'):
                self._log(f"[Step2] 未找到字段配置：{file_name}", "error")
                continue
            
            files_to_clean.append({
                'file_name': file_name,
                'file_path': file_path,
                'source_type': source_type,
                'field_config': combo['fields']
            })
        
        if not files_to_clean:
            ResultDialog.show_warning(self, "无有效文件", "所选文件均无法处理")
            return
        
        self._log(f"[Step2] 开始后台清洗任务，共 {len(files_to_clean)} 个文件", "info")
        
        # 禁用按钮
        self.btn_clean.setEnabled(False)
        self.btn_clean.setText("清洗中...")
        self.bar_clean.setMaximum(len(files_to_clean))
        self.bar_clean.setValue(0)
        self.lbl_clean.setText("正在初始化...")
        
        # 创建清洗器
        cleaner = DataCleaner()
        
        # 创建并启动 Worker
        self._clean_worker = CleanWorker(
            files=files_to_clean,
            cleaner=cleaner,
            output_dir=base_folder,
            province=province,
            city=city,
            county=county,
            parent=self
        )
        
        # 连接信号
        self._clean_worker.progress.connect(self._on_clean_progress)
        self._clean_worker.log.connect(self._log)
        self._clean_worker.file_completed.connect(self._on_file_cleaned)
        self._clean_worker.finished.connect(self._on_clean_finished)
        self._clean_worker.error.connect(self._on_clean_error)
        
        # 启动
        self._clean_worker.start()
    
    def _on_clean_progress(self, current: int, total: int, message: str):
        """清洗进度更新"""
        self.bar_clean.setMaximum(total)
        self.bar_clean.setValue(current)
        self.lbl_clean.setText(message)
    
    def _on_file_cleaned(self, file_name: str, result: dict):
        """单个文件清洗完成"""
        if result.get('success'):
            # 更新文件清洗状态
            if file_name in self.file_configs:
                self.file_configs[file_name]['cleaned'] = '已清洗'
                self._update_step1_cleaned_status(file_name, '已清洗')
    
    def _on_clean_finished(self, summary: dict):
        """清洗任务完成"""
        # 恢复按钮
        self.btn_clean.setEnabled(True)
        self.btn_clean.setText("执行清洗")
        
        if summary.get('cancelled'):
            self.lbl_clean.setText("已取消")
            self._log("[Step2] 清洗任务已取消", "warning")
            self._clean_worker = None
            return
        
        # 更新进度
        success_count = summary.get('success_count', 0)
        fail_count = summary.get('fail_count', 0)
        total_valid = summary.get('total_valid', 0)
        total_invalid = summary.get('total_invalid', 0)
        has_permission_error = summary.get('has_permission_error', False)
        
        self.bar_clean.setValue(self.bar_clean.maximum())
        self.lbl_clean.setText(f"完成：成功{success_count}个，失败{fail_count}个")
        
        # 刷新清洗任务列表
        self._refresh_clean_task_list()
        
        # 显示结果对话框
        self._show_clean_result_dialog(success_count, fail_count, total_valid, total_invalid, has_permission_error)
        
        # 清理 Worker
        self._clean_worker = None
    
    def _on_clean_error(self, error_msg: str):
        """清洗任务出错"""
        self.btn_clean.setEnabled(True)
        self.btn_clean.setText("执行清洗")
        self.lbl_clean.setText("出错")
        self._log(f"[Step2] {error_msg}", "error")
        ResultDialog.show_error(self, "清洗出错", error_msg[:500])
        self._clean_worker = None
    
    def _show_clean_result_dialog(self, success_count: int, fail_count: int, total_valid: int, total_invalid: int, has_permission_error: bool):
        """显示清洗结果对话框"""
        from qgis.PyQt.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame
        from qgis.PyQt.QtCore import Qt
        
        dialog = QDialog(self)
        dialog.setObjectName("step2_clean_result_dialog")
        dialog.setWindowTitle("清洗完成")
        dialog.setMinimumWidth(380)
        
        # PyQt6 语法
        dialog.setWindowFlags(dialog.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)
        
        layout = QVBoxLayout(dialog)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 20)
        
        # 标题区域
        if fail_count == 0:
            icon_text = "✅"
            title_text = "清洗完成"
            title_class = "success"
        elif success_count == 0:
            icon_text = "❌"
            title_text = "清洗失败"
            title_class = "error"
        else:
            icon_text = "⚠️"
            title_text = "部分完成"
            title_class = "warning"
        
        header_layout = QHBoxLayout()
        header_layout.setSpacing(12)
        
        icon_label = QLabel(icon_text)
        icon_label.setObjectName("step2_result_icon")
        header_layout.addWidget(icon_label)
        
        title_label = QLabel(title_text)
        title_label.setObjectName(f"step2_result_title_{title_class}")
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        
        layout.addLayout(header_layout)
        
        # 分隔线
        line = QFrame()
        line.setObjectName("step2_result_divider")
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFixedHeight(1)
        layout.addWidget(line)
        
        # 统计信息
        stats_layout = QVBoxLayout()
        stats_layout.setSpacing(8)
        
        # 文件处理统计
        file_stats = QLabel(f"📁 文件处理：成功 {success_count} 个，失败 {fail_count} 个")
        file_stats.setObjectName("step2_result_stats")
        stats_layout.addWidget(file_stats)
        
        # 数据统计
        data_stats = QLabel(f"📊 数据统计：有效 {total_valid} 条，剔除 {total_invalid} 条")
        data_stats.setObjectName("step2_result_stats")
        stats_layout.addWidget(data_stats)
        
        layout.addLayout(stats_layout)
        
        # 如果有文件占用错误，显示提示
        if has_permission_error:
            tip_frame = QFrame()
            tip_frame.setObjectName("step2_result_tip_frame")
            tip_layout = QVBoxLayout(tip_frame)
            tip_layout.setContentsMargins(12, 10, 12, 10)
            tip_layout.setSpacing(4)
            
            tip_title = QLabel("💡 提示")
            tip_title.setObjectName("step2_result_tip_title")
            tip_layout.addWidget(tip_title)
            
            tip_text = QLabel("部分文件保存失败，可能是因为 CSV 文件正被其他程序（如 Excel）打开。\n请关闭相关文件后重新执行清洗。")
            tip_text.setObjectName("step2_result_tip_text")
            tip_text.setWordWrap(True)
            tip_layout.addWidget(tip_text)
            
            layout.addWidget(tip_frame)
        
        # 按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        ok_btn = QPushButton("确定")
        ok_btn.setObjectName("step2_result_ok_btn")
        ok_btn.clicked.connect(dialog.accept)
        btn_layout.addWidget(ok_btn)
        
        layout.addLayout(btn_layout)
        
        dialog.exec()
    
    def _update_step1_cleaned_status(self, file_name: str, status: str):
        """
        更新 Step1 中对应文件的清洗状态，并保存到项目缓存
        
        Args:
            file_name: 文件名
            status: 清洗状态（'已清洗' / '未清洗'）
        """
        # 更新 Step1 内存中的状态
        step1_data_sources = self.get_step1_data_sources()
        if step1_data_sources and file_name in step1_data_sources:
            step1_data_sources[file_name]['cleaned'] = status
        
        # 保存到项目缓存目录（持久化）
        self._save_cleaned_status_to_project_cache(file_name, status)
    
    def _get_project_cleaned_status_file(self) -> str:
        """获取项目级清洗状态缓存文件路径"""
        global_config = self._get_global_config()
        if not global_config:
            return ""
        region_info = global_config.get_region_info()
        cache_folder = region_info.get('cache_folder', '')
        if not cache_folder:
            return ""
        return os.path.join(cache_folder, "file_status.json")
    
    def _save_cleaned_status_to_project_cache(self, file_name: str, status: str):
        """保存清洗状态到项目缓存（使用新的 file_status.json 格式）"""
        cache_file = self._get_project_cleaned_status_file()
        if not cache_file:
            return
        
        # 读取现有缓存
        file_status = {}
        if os.path.exists(cache_file):
            try:
                import json
                with open(cache_file, 'r', encoding='utf-8') as f:
                    file_status = json.load(f)
            except:
                pass
        
        # 更新并保存（新格式：{file_name: {cleaned: status, source_type: type}}）
        if file_name not in file_status:
            file_status[file_name] = {}
        # 兼容旧格式：如果是字符串，转换为字典
        if isinstance(file_status[file_name], str):
            file_status[file_name] = {"cleaned": file_status[file_name]}
        file_status[file_name]["cleaned"] = status
        
        try:
            import json
            os.makedirs(os.path.dirname(cache_file), exist_ok=True)
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(file_status, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self._log(f"[Step2] 保存清洗状态失败：{e}", "error")
    
    def _load_cleaned_status_from_project_cache(self) -> dict:
        """
        从项目缓存加载清洗状态
        
        返回格式：{file_name: "已清洗"} （提取 cleaned 字段）
        兼容新旧格式
        """
        cache_file = self._get_project_cleaned_status_file()
        if not cache_file or not os.path.exists(cache_file):
            # 兼容旧文件名
            old_cache_file = cache_file.replace("file_status.json", "file_cleaned_status.json") if cache_file else None
            if old_cache_file and os.path.exists(old_cache_file):
                cache_file = old_cache_file
            else:
                return {}
        
        try:
            import json
            with open(cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            # 提取 cleaned 字段，兼容新旧格式
            result = {}
            for file_name, value in data.items():
                if isinstance(value, str):
                    result[file_name] = value  # 旧格式
                elif isinstance(value, dict):
                    result[file_name] = value.get('cleaned', '未清洗')  # 新格式
            return result
        except:
            return {}
    
    # ==================== 通用方法 ====================
    
    def _set_section_size_policy(self, section):
        """设置CollapsibleSection的尺寸策略"""
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
            section.setSizePolicy(expanding, preferred)
        except (AttributeError, TypeError):
            section.setSizePolicy(7, 1)
    
    def _refresh_file_list(self):
        """刷新文件列表（从Step1获取数据源）"""
        step1_data_sources = self.get_step1_data_sources()
        if not step1_data_sources:
            self._log("[Step2] 未找到Step1的数据源，请先在Step1导入文件", "warn")
            self.file_configs.clear()
            self.file_select_combo.clear()
            self.file_select_combo.addItem("请选择文件...")
            self._refresh_clean_task_list()
            self._refresh_field_config_display()
            return
        
        # 保存当前选择
        current_selection = self.current_file_id
        
        # 从项目缓存加载清洗状态（与Step1保持一致）
        cached_cleaned_status = self._load_cleaned_status_from_project_cache()
        
        # 同时保留内存中的状态（优先级：内存 > 缓存 > 默认）
        existing_cleaned_status = {
            name: info.get('cleaned', '未清洗') 
            for name, info in self.file_configs.items()
        }
        
        # 清空当前配置
        self.file_configs.clear()
        
        # 从Step1的数据源构建文件配置
        for file_name, file_info in step1_data_sources.items():
            saved_path = file_info.get('saved_path', '')
            source_type = file_info.get('source_type', '其他')
            
            # 优先级：内存状态 > 缓存状态 > 默认值
            cleaned = existing_cleaned_status.get(file_name) or cached_cleaned_status.get(file_name, '未清洗')
            
            if not saved_path or not os.path.exists(saved_path):
                continue
            
            # 尝试从cache加载配置
            if file_name not in self.file_combo_configs:
                self._load_file_combo_config(file_name)
            
            combo = self.file_combo_configs.get(file_name)
            field_count = len(combo['fields']) if combo and combo.get('fields') else 0
            configured = "已配置" if field_count > 0 else "未配置"
            
            self.file_configs[file_name] = {
                "name": file_name,
                "saved_path": saved_path,
                "source_type": source_type,
                "field_count": field_count,
                "configured": configured,
                "cleaned": cleaned
            }
        
        # 更新文件选择下拉框（显示配置状态）
        self._update_file_select_combo(current_selection)
        
        # 刷新清洗任务列表
        self._refresh_clean_task_list()
        
        # 刷新字段配置显示
        self._refresh_field_config_display()
        
        self._log(f"[Step2] 已刷新文件列表，找到 {len(self.file_configs)} 个文件", "info")
    
    def _update_file_select_combo(self, preserve_selection: str = None):
        """更新文件选择下拉框（显示配置状态）"""
        self.file_select_combo.blockSignals(True)
        self.file_select_combo.clear()
        
        if not self.file_configs:
            self.file_select_combo.addItem("请选择文件...")
            self.file_select_combo.blockSignals(False)
            return
        
        # 添加文件项，显示配置状态
        first_file = None
        for file_name, file_info in self.file_configs.items():
            if first_file is None:
                first_file = file_name
            
            field_count = file_info.get("field_count", 0)
            configured = file_info.get("configured", "未配置")
            
            # 格式：文件名 [已配置 3字段] 或 文件名 [未配置]
            if configured == "已配置":
                display_text = f"{file_name}  [已配置 {field_count}字段]"
        else:
                display_text = f"{file_name}  [未配置]"
            
            self.file_select_combo.addItem(display_text, file_name)
        
        # 恢复选择或默认选择第一个
        if preserve_selection and preserve_selection in self.file_configs:
            # 恢复之前的选择
            for i in range(self.file_select_combo.count()):
                if self.file_select_combo.itemData(i) == preserve_selection:
                    self.file_select_combo.setCurrentIndex(i)
                    self.current_file_id = preserve_selection
                    break
        elif first_file and not self.current_file_id:
            # 默认选择第一个文件
            self.file_select_combo.setCurrentIndex(0)
            self.current_file_id = first_file
            # 加载第一个文件的配置
            self._load_file_combo_config(first_file)
        
        self.file_select_combo.blockSignals(False)
    
    def _precheck_field_configs(self, selected_files: List[str]) -> List[str]:
        """
        预检查字段配置是否合理
        
        返回警告信息列表
        """
        import re
        warnings = []
        
        # 常见的非地址字段名
        NON_ADDRESS_FIELDS = {
            'crs', 'epsg', 'geometry', 'gid', 'guid', 'id', 'code', 'dno',
            'angle', 'xcoordinat', 'ycoordinat', 'x', 'y', 'lat', 'lng', 'lon',
            'crttime', 'modtime', 'crtuser', 'moduser', 'data_type',
            'groundelev', 'pipetopele', 'burieddept'
        }
        
        for file_name in selected_files:
            combo_config = self.file_combo_configs.get(file_name, {})
            fields_config = combo_config.get('fields', [])
            
            if not fields_config:
                warnings.append(f"⚠️ {file_name}: 未配置任何字段")
                continue
            
            field_names = [f.get('field', '') for f in fields_config if f.get('field')]
            
            # 检查是否配置了非地址字段
            bad_fields = [f for f in field_names if f.lower() in NON_ADDRESS_FIELDS]
            if bad_fields:
                warnings.append(f"❌ {file_name}: 配置了非地址字段 [{', '.join(bad_fields)}]")
            
            # 检查字段内容是否包含中文
            columns = self.file_columns_cache.get(file_name, [])
            if columns and field_names:
                # 尝试读取文件样本检查
                file_config = self.file_configs.get(file_name, {})
                file_path = file_config.get('saved_path', '')
                
                if file_path and os.path.exists(file_path):
                    try:
                        import pandas as pd
                        df_sample = pd.read_csv(file_path, encoding='utf-8', nrows=10)
                        
                        no_chinese_fields = []
                        for field in field_names:
                            if field in df_sample.columns:
                                sample_values = df_sample[field].dropna().astype(str)
                                has_chinese = any(
                                    bool(re.search(r'[\u4e00-\u9fa5]', str(v)))
                                    for v in sample_values
                                )
                                if not has_chinese and len(sample_values) > 0:
                                    sample = str(sample_values.iloc[0])[:20]
                                    no_chinese_fields.append(f"{field}={sample}")
                        
                        if no_chinese_fields:
                            warnings.append(f"⚠️ {file_name}: 字段不含中文 [{', '.join(no_chinese_fields)}]")
                    except Exception:
                        pass
        
        return warnings
    
    def _get_global_config(self):
        """获取全局配置"""
        parent = self.parent()
        while parent:
            if hasattr(parent, 'global_config'):
                return parent.global_config
            parent = parent.parent()
        return None
    
    def _get_combo_config_file_path(self, file_name: str) -> Optional[str]:
        """获取字段组合配置文件路径"""
        global_config = self._get_global_config()
        if not global_config:
            return None
        
        region_info = global_config.get_region_info()
        cache_folder = region_info.get('cache_folder', '')
        if not cache_folder:
            return None
        
        file_stem = os.path.splitext(file_name)[0]
        config_file_name = f"{file_stem}_combo_config.json"
        return os.path.join(cache_folder, config_file_name)
    
    def _load_file_combo_config(self, file_name: str):
        """从cache目录加载配置"""
        if not file_name:
            return
        
        config_path = self._get_combo_config_file_path(file_name)
        if not config_path or not os.path.exists(config_path):
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
        """保存配置到cache目录"""
        if not file_name or file_name not in self.file_combo_configs:
            ResultDialog.show_warning(self, "无配置", "当前文件没有字段组合配置")
            return
        
        if not self.current_field_table:
            ResultDialog.show_error(self, "读取失败", "无法读取字段配置")
            return
        
        # 读取表格数据
        fields = []
        for r in range(self.current_field_table.rowCount()):
            role_item = self.current_field_table.item(r, 1)
            field_widget = self.current_field_table.cellWidget(r, 2)
            role = role_item.text() if role_item else ""
            field = field_widget.currentText() if isinstance(field_widget, QComboBox) else ""
            if field:
                fields.append({"role": role, "field": field})
        
        if not fields:
            ResultDialog.show_warning(self, "字段为空", "请至少配置一个字段")
            return
        
        # 更新配置
        combo = self.file_combo_configs[file_name]
        combo['fields'] = fields
        
        config_path = self._get_combo_config_file_path(file_name)
        if not config_path:
            ResultDialog.show_error(self, "缓存错误", "无法获取缓存目录，请检查全局配置")
            return
        
        try:
            import json
            os.makedirs(os.path.dirname(config_path), exist_ok=True)
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(combo, f, ensure_ascii=False, indent=2)
            
            # 更新状态
            field_count = len(fields)
            self.file_configs[file_name]["field_count"] = field_count
            self.file_configs[file_name]["configured"] = "已配置" if field_count > 0 else "未配置"
            
            # 刷新文件选择下拉框（更新配置状态显示）
            self._update_file_select_combo(file_name)
            
            # 刷新清洗任务列表
            self._refresh_clean_task_list()
            
            self._log(f"[Step2] 已保存文件 {file_name} 的配置", "success")
            ResultDialog.show_success(self, "保存成功", f"配置已保存，共 {field_count} 个字段")
        except Exception as e:
            self._log(f"[Step2] 保存配置失败：{e}", "error")
            ResultDialog.show_error(self, "保存失败", str(e))
    
    def _get_file_columns(self, file_name: str) -> List[str]:
        """获取文件列名"""
        if file_name in self.file_columns_cache:
            return self.file_columns_cache[file_name]
        
        if file_name not in self.file_configs:
            return []
        
        saved_path = self.file_configs[file_name].get('saved_path', '')
        if not saved_path or not os.path.exists(saved_path):
            return []
        
        try:
            columns = DataLoader.get_file_columns(saved_path)
            self.file_columns_cache[file_name] = columns
            return columns
        except Exception as e:
            self._log(f"[Step2] 读取文件列名失败 {file_name}：{e}", "error")
            return []
