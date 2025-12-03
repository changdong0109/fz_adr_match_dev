"""
Step5: 导出 & 日志Widget
包含：结果导出、数据统计、日志查看
"""
from typing import Callable, Optional, List, Dict
from qgis.PyQt.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QCheckBox, QProgressBar, QFileDialog,
    QTableWidget, QTableWidgetItem, QHeaderView
)
from qgis.PyQt.QtGui import QColor
from qgis.PyQt.QtCore import Qt
from ..widgets.base_step_widget import BaseStepWidget
from ..collapsible_section import CollapsibleSection


class Step5Widget(BaseStepWidget):
    """Step5: 导出 & 日志"""
    
    def __init__(self, parent=None, log_callback: Optional[Callable[[str, str], None]] = None, 
                 task_manager=None, log_panel=None, global_config=None):
        self.global_config = global_config
        self._export_stats: Dict = {}  # 导出统计
        super().__init__(parent, log_callback, task_manager)
        self._build_ui()
        self._load_demo_stats()
    
    def _build_ui(self):
        """构建UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 6, 0, 6)
        layout.setSpacing(12)
        
        layout.addWidget(self._card_stats())
        layout.addWidget(self._card_export())
        layout.addWidget(self._card_export_history())
        layout.addStretch(1)
    
    def _card_stats(self) -> QWidget:
        """数据处理统计"""
        section = CollapsibleSection("数据处理统计", expanded=True)
        
        content = QWidget()
        v = QVBoxLayout(content)
        v.setContentsMargins(16, 12, 16, 12)
        v.setSpacing(12)
        
        # 统计卡片区
        cards_layout = QHBoxLayout()
        cards_layout.setSpacing(16)
        
        # 文件统计卡片
        self.card_files = self._create_stat_card("", "导入文件", "0", "个文件")
        cards_layout.addWidget(self.card_files)
        
        # 清洗统计卡片
        self.card_cleaned = self._create_stat_card("", "清洗完成", "0", "条记录")
        cards_layout.addWidget(self.card_cleaned)
        
        # 标准化统计卡片
        self.card_standardized = self._create_stat_card("", "标准化完成", "0", "条记录")
        cards_layout.addWidget(self.card_standardized)
        
        # 匹配统计卡片
        self.card_matched = self._create_stat_card("", "匹配成功", "0", "条记录")
        cards_layout.addWidget(self.card_matched)
        
        v.addLayout(cards_layout)
        
        # 刷新按钮
        btn_refresh = QPushButton("刷新统计")
        btn_refresh.setObjectName("step5_btn_refresh")
        btn_refresh.clicked.connect(self._refresh_stats)
        v.addWidget(btn_refresh)
        
        section.add_widget(content)
        return section
    
    def _create_stat_card(self, icon: str, title: str, value: str, unit: str) -> QWidget:
        """创建统计卡片"""
        card = QWidget()
        card.setObjectName("step5_stat_card")
        
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(4)
        
        # 图标和标题
        header = QHBoxLayout()
        icon_label = QLabel(icon)
        icon_label.setObjectName("step5_stat_icon")
        header.addWidget(icon_label)
        
        title_label = QLabel(title)
        title_label.setObjectName("step5_stat_title")
        header.addWidget(title_label)
        header.addStretch()
        layout.addLayout(header)
        
        # 数值
        value_layout = QHBoxLayout()
        value_label = QLabel(value)
        value_label.setObjectName("step5_stat_value")
        value_layout.addWidget(value_label)
        
        unit_label = QLabel(unit)
        unit_label.setObjectName("step5_stat_unit")
        value_layout.addWidget(unit_label)
        value_layout.addStretch()
        layout.addLayout(value_layout)
        
        # 存储标签引用以便更新
        card.value_label = value_label
        
        return card
    
    def _card_export(self) -> QWidget:
        """结果导出"""
        section = CollapsibleSection("结果导出", expanded=True)
        
        content = QWidget()
        v = QVBoxLayout(content)
        v.setContentsMargins(16, 12, 16, 12)
        v.setSpacing(12)
        
        # 导出选项
        tip = QLabel("选择要导出的数据类型，支持批量导出到指定目录。")
        tip.setObjectName("step5_tip")
        tip.setWordWrap(True)
        v.addWidget(tip)
        
        # 导出选项复选框
        options_layout = QVBoxLayout()
        options_layout.setSpacing(8)
        
        self.chk_export_clean = QCheckBox("清洗结果（*_清洗.csv）")
        self.chk_export_clean.setObjectName("step5_checkbox")
        self.chk_export_clean.setChecked(True)
        options_layout.addWidget(self.chk_export_clean)
        
        self.chk_export_std = QCheckBox("标准化结果（*_标准化.csv）")
        self.chk_export_std.setObjectName("step5_checkbox")
        self.chk_export_std.setChecked(True)
        options_layout.addWidget(self.chk_export_std)
        
        self.chk_export_match = QCheckBox("匹配结果（按任务组输出）")
        self.chk_export_match.setObjectName("step5_checkbox")
        self.chk_export_match.setChecked(True)
        options_layout.addWidget(self.chk_export_match)
        
        self.chk_export_unmatched = QCheckBox("未匹配数据（便于后续处理）")
        self.chk_export_unmatched.setObjectName("step5_checkbox")
        self.chk_export_unmatched.setChecked(False)
        options_layout.addWidget(self.chk_export_unmatched)
        
        self.chk_export_relations = QCheckBox("字段关联分析结果")
        self.chk_export_relations.setObjectName("step5_checkbox")
        self.chk_export_relations.setChecked(False)
        options_layout.addWidget(self.chk_export_relations)
        
        v.addLayout(options_layout)
        
        # 导出格式选择
        format_layout = QHBoxLayout()
        format_layout.addWidget(QLabel("导出格式:"))
        
        self.radio_excel = QCheckBox("Excel (.xlsx)")
        self.radio_excel.setObjectName("step5_checkbox")
        self.radio_excel.setChecked(True)
        format_layout.addWidget(self.radio_excel)
        
        self.radio_csv = QCheckBox("CSV (.csv)")
        self.radio_csv.setObjectName("step5_checkbox")
        self.radio_csv.setChecked(False)
        format_layout.addWidget(self.radio_csv)
        
        format_layout.addStretch()
        
        btn_config_fields = QPushButton("配置导出字段...")
        btn_config_fields.setObjectName("step5_btn_config_fields")
        btn_config_fields.setToolTip("选择要导出的字段")
        btn_config_fields.clicked.connect(self._open_field_config_dialog)
        format_layout.addWidget(btn_config_fields)
        
        v.addLayout(format_layout)
        
        # 输出目录
        dir_layout = QHBoxLayout()
        dir_layout.addWidget(QLabel("输出目录:"))
        
        self.edit_export_dir = QLineEdit()
        self.edit_export_dir.setObjectName("step5_path_input")
        self.edit_export_dir.setPlaceholderText("选择或输入导出目录...")
        dir_layout.addWidget(self.edit_export_dir)
        
        btn_browse = QPushButton("浏览...")
        btn_browse.setObjectName("step5_btn_browse")
        btn_browse.clicked.connect(self._browse_export_dir)
        dir_layout.addWidget(btn_browse)
        
        v.addLayout(dir_layout)
        
        # 进度条和操作按钮
        progress_layout = QHBoxLayout()
        
        self.export_progress = QProgressBar()
        self.export_progress.setObjectName("step5_progress")
        self.export_progress.setValue(0)
        progress_layout.addWidget(self.export_progress)
        
        self.lbl_export_status = QLabel("就绪")
        self.lbl_export_status.setObjectName("step5_status_label")
        self.lbl_export_status.setMinimumWidth(80)
        progress_layout.addWidget(self.lbl_export_status)
        
        v.addLayout(progress_layout)
        
        # 操作按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        btn_export = QPushButton("▶ 执行导出")
        btn_export.setObjectName("step5_btn_export")
        btn_export.clicked.connect(self._run_export)
        btn_layout.addWidget(btn_export)
        
        btn_open_dir = QPushButton("📂 打开输出目录")
        btn_open_dir.setObjectName("step5_btn_secondary")
        btn_open_dir.clicked.connect(self._open_export_dir)
        btn_layout.addWidget(btn_open_dir)
        
        v.addLayout(btn_layout)
        
        section.add_widget(content)
        return section
    
    def _card_export_history(self) -> QWidget:
        """导出历史"""
        section = CollapsibleSection("导出历史", expanded=False)
        
        content = QWidget()
        v = QVBoxLayout(content)
        v.setContentsMargins(16, 12, 16, 12)
        v.setSpacing(10)
        
        # 历史记录表格
        self.history_table = QTableWidget(0, 4)
        self.history_table.setObjectName("step5_history_table")
        self.history_table.setHorizontalHeaderLabels([
            "导出时间", "导出类型", "文件数量", "输出目录"
        ])
        self.history_table.setMinimumHeight(150)
        
        header = self.history_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(0, 150)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(1, 120)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(2, 80)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        
        v.addWidget(self.history_table)
        
        # 加载示例历史
        self._load_demo_history()
        
        section.add_widget(content)
        return section
    
    def _load_demo_stats(self):
        """加载示例统计数据"""
        self._export_stats = {
            "files": 20,
            "cleaned": 15680,
            "standardized": 12450,
            "matched": 8920
        }
        self._update_stat_cards()
    
    def _update_stat_cards(self):
        """更新统计卡片显示"""
        if hasattr(self, 'card_files') and hasattr(self.card_files, 'value_label'):
            self.card_files.value_label.setText(str(self._export_stats.get("files", 0)))
        if hasattr(self, 'card_cleaned') and hasattr(self.card_cleaned, 'value_label'):
            self.card_cleaned.value_label.setText(f"{self._export_stats.get('cleaned', 0):,}")
        if hasattr(self, 'card_standardized') and hasattr(self.card_standardized, 'value_label'):
            self.card_standardized.value_label.setText(f"{self._export_stats.get('standardized', 0):,}")
        if hasattr(self, 'card_matched') and hasattr(self.card_matched, 'value_label'):
            self.card_matched.value_label.setText(f"{self._export_stats.get('matched', 0):,}")
    
    def _load_demo_history(self):
        """加载示例导出历史"""
        demo_history = [
            ("2025-12-01 22:30:15", "清洗结果", "4", "C:/output/cleaned/"),
            ("2025-12-01 20:15:30", "标准化结果", "3", "C:/output/standardized/"),
            ("2025-11-30 18:45:00", "匹配结果", "2", "C:/output/matched/"),
        ]
        
        self.history_table.setRowCount(len(demo_history))
        for r, (time, type_, count, path) in enumerate(demo_history):
            self.history_table.setItem(r, 0, QTableWidgetItem(time))
            self.history_table.setItem(r, 1, QTableWidgetItem(type_))
            self.history_table.setItem(r, 2, QTableWidgetItem(count))
            self.history_table.setItem(r, 3, QTableWidgetItem(path))
    
    def _refresh_stats(self):
        """刷新统计数据"""
        self._log("[Step5] 刷新统计数据", "info")
        # TODO: 从实际数据加载统计
        self._update_stat_cards()
    
    def _browse_export_dir(self):
        """浏览导出目录"""
        current_dir = self.edit_export_dir.text() or ""
        path = QFileDialog.getExistingDirectory(self, "选择导出目录", current_dir)
        if path:
            self.edit_export_dir.setText(path)
            self._log(f"[Step5] 选择导出目录: {path}", "info")
    
    def _run_export(self):
        """执行导出 - 调用 ExportManager（后台线程）"""
        import os
        from ..widgets.result_dialog import ResultDialog
        from ..workers.export_worker import ExportWorker
        
        # 检查是否已有任务在运行
        if hasattr(self, '_export_worker') and self._export_worker is not None and self._export_worker.isRunning():
            ResultDialog.show_warning(self, "任务进行中", "请等待当前导出任务完成")
            return
        
        export_dir = self.edit_export_dir.text()
        if not export_dir:
            ResultDialog.show_warning(self, "请先选择导出目录")
            return
        
        # 收集选中的导出类型
        export_types = []
        if self.chk_export_clean.isChecked():
            export_types.append("清洗结果")
        if self.chk_export_std.isChecked():
            export_types.append("标准化结果")
        if self.chk_export_match.isChecked():
            export_types.append("匹配结果")
        if self.chk_export_unmatched.isChecked():
            export_types.append("未匹配数据")
        if self.chk_export_relations.isChecked():
            export_types.append("关联分析结果")
        
        if not export_types:
            ResultDialog.show_warning(self, "请至少选择一种导出类型")
            return
        
        # 获取全局配置
        global_config = self._get_global_config()
        if not global_config:
            self._log("[Step5] 无法获取全局配置", "error")
            self.lbl_export_status.setText("失败")
            return
        
        region_info = global_config.get_region_info()
        customer_folder = region_info.get('customer_folder', '')
        cache_folder = region_info.get('cache_folder', '')
        
        # 确定导出格式
        output_format = "xlsx" if self.radio_excel.isChecked() else "csv"
        
        # 获取字段配置
        field_config = self.get_export_field_config()
        selected_fields = field_config.get("selected", [])
        
        self._log(f"[Step5] 开始后台导出: {', '.join(export_types)}", "info")
        self.lbl_export_status.setText("导出中...")
        self.export_progress.setValue(0)
        self.export_progress.setMaximum(len(export_types))
        self.btn_export.setEnabled(False)
        self.btn_export.setText("导出中...")
        
        # 创建导出器（不传入 log_callback，避免后台线程直接操作 UI）
        from ...core.export_manager import ExportManager
        exporter = ExportManager(log_callback=None)  # 日志通过 Worker 信号发送
        
        # 构建导出配置
        export_config = {
            'export_dir': export_dir,
            'export_types': export_types,
            'output_format': output_format,
            'customer_folder': customer_folder,
            'cache_folder': cache_folder,
            'selected_fields': selected_fields
        }
        
        # 创建并启动 Worker
        self._export_worker = ExportWorker(
            exporter=exporter,
            export_config=export_config,
            parent=self
        )
        
        # 连接信号
        self._export_worker.progress.connect(self._on_export_progress)
        self._export_worker.log.connect(self._log)
        self._export_worker.file_completed.connect(self._on_file_exported)
        self._export_worker.finished.connect(self._on_export_finished)
        self._export_worker.error.connect(self._on_export_error)
        
        # 启动
        self._export_worker.start()
    
    def _on_export_progress(self, current: int, total: int, message: str):
        """导出进度更新"""
        self.export_progress.setMaximum(total)
        self.export_progress.setValue(current)
        self.lbl_export_status.setText(message)
    
    def _on_file_exported(self, file_name: str, result: dict):
        """单个文件导出完成"""
        if result.get('success'):
            self._log(f"[Step5] 导出成功: {file_name}", "info")
    
    def _on_export_finished(self, summary: dict):
        """导出任务完成"""
        from ..widgets.result_dialog import ResultDialog
        
        self.btn_export.setEnabled(True)
        self.btn_export.setText("开始导出")
        self._export_worker = None
        
        if summary.get('cancelled'):
            self.lbl_export_status.setText("已取消")
            self._log("[Step5] 导出任务已取消", "warning")
            return
        
        total_success = summary.get('success_count', 0)
        total_fail = summary.get('fail_count', 0)
        export_dir = summary.get('export_dir', '')
        
        self.export_progress.setValue(self.export_progress.maximum())
        self.lbl_export_status.setText("完成")
        
        if total_fail == 0 and total_success > 0:
            self._log(f"[Step5] 导出完成: 成功 {total_success} 个文件", "success")
            ResultDialog.show_success(
                self, "导出成功",
                f"成功导出 {total_success} 个文件到:\n{export_dir}"
            )
        elif total_success > 0:
            self._log(f"[Step5] 导出部分完成: 成功 {total_success}, 失败 {total_fail}", "warning")
            ResultDialog.show_warning(
                self, "部分完成",
                f"成功: {total_success} 个文件\n失败: {total_fail} 个文件"
            )
        else:
            self._log("[Step5] 没有找到可导出的文件", "warning")
            ResultDialog.show_warning(self, "无可导出数据", "没有找到符合条件的文件")
    
    def _on_export_error(self, error_msg: str):
        """导出任务出错"""
        from ..widgets.result_dialog import ResultDialog
        
        self.btn_export.setEnabled(True)
        self.btn_export.setText("开始导出")
        self.export_progress.setValue(0)
        self.lbl_export_status.setText("失败")
        self._export_worker = None
        
        self._log(f"[Step5] 导出失败: {error_msg}", "error")
        ResultDialog.show_error(self, "导出失败", error_msg[:500])
    
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
    
    def _open_export_dir(self):
        """打开导出目录"""
        import os
        export_dir = self.edit_export_dir.text()
        if export_dir and os.path.exists(export_dir):
            os.startfile(export_dir)
        else:
            from ..widgets.result_dialog import ResultDialog
            ResultDialog.show_warning(self, "导出目录不存在")
    
    def _open_field_config_dialog(self):
        """打开字段配置对话框"""
        from qgis.PyQt.QtWidgets import (
            QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
            QPushButton, QLabel, QAbstractItemView
        )
        
        dialog = QDialog(self)
        dialog.setWindowTitle("配置导出字段")
        dialog.resize(500, 400)
        
        layout = QVBoxLayout(dialog)
        
        lbl = QLabel("勾选要导出的字段：")
        layout.addWidget(lbl)
        
        # 获取可用字段
        available_fields = self._get_available_export_fields()
        
        if not hasattr(self, '_export_field_config'):
            self._export_field_config = {"selected": available_fields.copy()}
        
        # 字段列表
        self._field_list = QListWidget()
        
        for field in available_fields:
            item = QListWidgetItem(field)
            item.setCheckState(
                Qt.CheckState.Checked if field in self._export_field_config.get("selected", [])
                else Qt.CheckState.Unchecked
            )
            self._field_list.addItem(item)
        
        layout.addWidget(self._field_list, 1)
        
        # 快捷按钮
        quick_layout = QHBoxLayout()
        btn_all = QPushButton("全选")
        btn_all.clicked.connect(lambda: self._set_all_fields(True))
        quick_layout.addWidget(btn_all)
        
        btn_none = QPushButton("全不选")
        btn_none.clicked.connect(lambda: self._set_all_fields(False))
        quick_layout.addWidget(btn_none)
        quick_layout.addStretch()
        layout.addLayout(quick_layout)
        
        # 按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_ok = QPushButton("确定")
        btn_ok.clicked.connect(lambda: self._save_field_config(dialog))
        btn_layout.addWidget(btn_ok)
        btn_cancel = QPushButton("取消")
        btn_cancel.clicked.connect(dialog.reject)
        btn_layout.addWidget(btn_cancel)
        layout.addLayout(btn_layout)
        
        dialog.exec()
    
    def _get_available_export_fields(self):
        """获取可用的导出字段"""
        return [
            "源表文件", "源表行号", "源表名称", "源表标准化地址", "源表POI原始", "源表POI",
            "目标表文件", "目标表行号", "目标表名称", "目标表标准化地址", "目标表POI原始", "目标表POI",
            "匹配类型", "匹配类型代码", "匹配分数", "POI来源", "是否匹配"
        ]
    
    def _set_all_fields(self, checked: bool):
        """全选/全不选"""
        for i in range(self._field_list.count()):
            self._field_list.item(i).setCheckState(
                Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
            )
    
    def _save_field_config(self, dialog):
        """保存字段配置"""
        selected = []
        for i in range(self._field_list.count()):
            item = self._field_list.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                selected.append(item.text())
        
        self._export_field_config = {"selected": selected}
        self._log(f"[Step5] 导出字段配置已保存: {len(selected)} 个", "info")
        dialog.accept()
    
    def get_export_field_config(self):
        """获取导出字段配置"""
        if not hasattr(self, '_export_field_config'):
            return {"selected": self._get_available_export_fields()}
        return self._export_field_config
