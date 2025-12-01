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
        """执行导出"""
        export_dir = self.edit_export_dir.text()
        if not export_dir:
            from ..widgets.result_dialog import ResultDialog
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
            from ..widgets.result_dialog import ResultDialog
            ResultDialog.show_warning(self, "请至少选择一种导出类型")
            return
        
        self._log(f"[Step5] 开始导出: {', '.join(export_types)}", "info")
        self.lbl_export_status.setText("导出中...")
        self.export_progress.setValue(50)
        
        # TODO: 实现实际导出逻辑
        
        # 模拟完成
        self.export_progress.setValue(100)
        self.lbl_export_status.setText("完成")
        self._log(f"[Step5] 导出完成，输出目录: {export_dir}", "success")
    
    def _open_export_dir(self):
        """打开导出目录"""
        import os
        export_dir = self.edit_export_dir.text()
        if export_dir and os.path.exists(export_dir):
            os.startfile(export_dir)
        else:
            from ..widgets.result_dialog import ResultDialog
            ResultDialog.show_warning(self, "导出目录不存在")
