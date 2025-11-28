"""
地址匹配 UI 对话框 - QGIS 插件主界面（精简版）

此文件已精简：仅保留 `主页` 标签，主页包含文件上传、预览、清洗、标准化、字段推断、快速匹配、导出与日志。
后续若需扩展其它页面再拆分模块。

样式管理已分离到 styles.py 和 styles.qss，保持代码与视觉的解耦。
"""

from typing import List, Dict, Optional
import traceback

try:
    from qgis.PyQt.QtWidgets import (
        QDialog, QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
        QPushButton, QLabel, QFileDialog, QTableWidget, QTableWidgetItem,
        QHeaderView, QAbstractItemView,
        QComboBox, QDoubleSpinBox, QMessageBox, QProgressBar,
        QLineEdit, QGroupBox, QScrollArea
    )
    from qgis.PyQt.QtCore import Qt, pyqtSignal
    QGIS_AVAILABLE = True
except ImportError:
    QGIS_AVAILABLE = False

# 导入样式管理模块和可折叠组件
from .styles import get_collapsible_groupbox_style
from .collapsible_section import CollapsibleSection

# Compatibility: obtain enum-like values accepted by QGIS PyQt bindings.
# Some bindings require the enum attribute (e.g. QAbstractItemView.NoEditTriggers),
# others require a specific enum type (e.g. QAbstractItemView.EditTriggers(0)).
try:
    EDIT_TRIGGERS_NONE = QAbstractItemView.NoEditTriggers
except Exception:
    try:
        EDIT_TRIGGERS_NONE = QTableWidget.NoEditTriggers
    except Exception:
        try:
            EDIT_TRIGGERS_NONE = QAbstractItemView.EditTriggers(0)
        except Exception:
            EDIT_TRIGGERS_NONE = 0

try:
    SELECT_ROWS = QAbstractItemView.SelectRows
except Exception:
    try:
        SELECT_ROWS = QTableWidget.SelectRows
    except Exception:
        try:
            SELECT_ROWS = QAbstractItemView.SelectionBehavior(1)
        except Exception:
            SELECT_ROWS = 1

# Header resize mode compatibility
try:
    HEADER_RESIZE_TO_CONTENTS = QHeaderView.ResizeToContents
    HEADER_RESIZE_STRETCH = QHeaderView.Stretch
except Exception:
    try:
        HEADER_RESIZE_TO_CONTENTS = QHeaderView.ResizeMode.ResizeToContents
        HEADER_RESIZE_STRETCH = QHeaderView.ResizeMode.Stretch
    except Exception:
        try:
            HEADER_RESIZE_TO_CONTENTS = QHeaderView.ResizeMode(1)
            HEADER_RESIZE_STRETCH = QHeaderView.ResizeMode(2)
        except Exception:
            HEADER_RESIZE_TO_CONTENTS = 1
            HEADER_RESIZE_STRETCH = 2

class MatchDialog(QDialog):
    """精简的地址匹配对话框，仅保留主页功能"""

    match_completed = pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("地址标准化与管网匹配")
        self.setGeometry(100, 100, 1000, 700)

        # 数据存放
        self.left_data = None
        self.right_data = None
        self.left_file = None
        self.right_file = None

        # 初始化 UI
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()

        tabs = QTabWidget()
        tabs.addTab(self._create_home_tab(), "主页")
        layout.addWidget(tabs)

        # 只保留主页；底部按钮由主页内部控制（避免重复）
        self.setLayout(layout)

    def _create_home_tab(self) -> QWidget:
        tab = QWidget()
        main_layout = QVBoxLayout()

        # 使用 ScrollArea 包装主内容，支持滚动
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_content = QWidget()
        layout = QVBoxLayout(scroll_content)
        layout.setSpacing(8)

        # Console / log viewer (始终显示在上方)
        console_group = QGroupBox("控制台日志")
        console_layout = QVBoxLayout()
        self.console_log = QTableWidget()
        self.console_log.setColumnCount(3)
        self.console_log.setHorizontalHeaderLabels(['时间', '级别', '消息'])
        self.console_log.setMaximumHeight(200)
        # Use compatibility values for edit triggers and selection behavior
        self.console_log.setEditTriggers(EDIT_TRIGGERS_NONE)
        self.console_log.setSelectionBehavior(SELECT_ROWS)
        self.console_log.setWordWrap(True)
        self.console_log.verticalHeader().setVisible(False)
        self.console_log.horizontalHeader().setSectionResizeMode(0, HEADER_RESIZE_TO_CONTENTS)
        self.console_log.horizontalHeader().setSectionResizeMode(1, HEADER_RESIZE_TO_CONTENTS)
        self.console_log.horizontalHeader().setSectionResizeMode(2, HEADER_RESIZE_STRETCH)
        console_layout.addWidget(self.console_log)

        # console control buttons
        cbtn_layout = QHBoxLayout()
        btn_clear_log = QPushButton("清空日志")
        btn_clear_log.clicked.connect(lambda: self.console_log.setRowCount(0))
        btn_export_log = QPushButton("导出日志")
        btn_export_log.clicked.connect(self._export_log)
        cbtn_layout.addStretch()
        cbtn_layout.addWidget(btn_clear_log)
        cbtn_layout.addWidget(btn_export_log)
        console_layout.addLayout(cbtn_layout)

        console_group.setLayout(console_layout)
        layout.addWidget(console_group)

        # Section 1: 数据上传与清洗 + 预览 (使用 CollapsibleSection)
        clean_content = QWidget()
        cg_layout = QVBoxLayout(clean_content)
        cg_layout.setContentsMargins(0, 0, 0, 0)

        # file selectors
        file_layout = QHBoxLayout()
        self.home_file_label = QLineEdit()
        self.home_file_label.setReadOnly(True)
        btn_select = QPushButton("选择文件(加载到左表)")
        btn_select.clicked.connect(self._home_select_file)
        file_layout.addWidget(self.home_file_label)
        file_layout.addWidget(btn_select)
        cg_layout.addLayout(file_layout)

        # previews
        preview_layout = QHBoxLayout()
        self.left_preview = QTableWidget()
        self.left_preview.setMaximumHeight(160)
        self.right_preview = QTableWidget()
        self.right_preview.setMaximumHeight(160)
        preview_layout.addWidget(self.left_preview)
        preview_layout.addWidget(self.right_preview)
        cg_layout.addLayout(preview_layout)

        # cleaning controls
        self.clean_progress = QProgressBar()
        self.clean_progress.setValue(0)
        cg_layout.addWidget(self.clean_progress)

        btns = QHBoxLayout()
        btn_clean = QPushButton("执行清洗")
        btn_clean.clicked.connect(self._home_run_clean)
        btn_open_cache = QPushButton("打开清洗缓存")
        btn_open_cache.clicked.connect(lambda: self._home_open_cache('cleaned_left'))
        btns.addWidget(btn_clean)
        btns.addWidget(btn_open_cache)
        btns.addStretch()
        cg_layout.addLayout(btns)

        clean_section = CollapsibleSection("1. 数据上传与清洗（左表/右表）", expanded=True)
        clean_section.add_content_widget(clean_content)
        layout.addWidget(clean_section)

        # Section 2: 标准化 (使用 CollapsibleSection)
        std_content = QWidget()
        sg_layout = QVBoxLayout(std_content)
        sg_layout.setContentsMargins(0, 0, 0, 0)
        sg_layout.addWidget(QLabel("选择要标准化的字段（Home 支持单字段演示）"))
        self.std_field_combo = QComboBox()
        sg_layout.addWidget(self.std_field_combo)
        self.std_progress = QProgressBar()
        sg_layout.addWidget(self.std_progress)
        sbtn_layout = QHBoxLayout()
        btn_std = QPushButton("执行标准化")
        btn_std.clicked.connect(self._home_run_standardize)
        btn_std_cache = QPushButton("打开标准化缓存")
        btn_std_cache.clicked.connect(lambda: self._home_open_cache('standardized_left'))
        sbtn_layout.addWidget(btn_std)
        sbtn_layout.addWidget(btn_std_cache)
        sbtn_layout.addStretch()
        sg_layout.addLayout(sbtn_layout)

        std_section = CollapsibleSection("2. 地址标准化", expanded=False)
        std_section.add_content_widget(std_content)
        layout.addWidget(std_section)

        # Section 3: 字段推断（演示）(使用 CollapsibleSection)
        rel_content = QWidget()
        rl_layout = QVBoxLayout(rel_content)
        rl_layout.setContentsMargins(0, 0, 0, 0)
        btn_rel = QPushButton("检测字段关系")
        btn_rel.clicked.connect(self._home_run_infer_relations)
        rl_layout.addWidget(btn_rel)
        self.rel_preview = QTableWidget()
        self.rel_preview.setColumnCount(5)
        self.rel_preview.setHorizontalHeaderLabels(['源1', '字段1', '源2', '字段2', '相似度'])
        rl_layout.addWidget(self.rel_preview)

        rel_section = CollapsibleSection("3. 智能字段匹配关系（示例）", expanded=False)
        rel_section.add_content_widget(rel_content)
        layout.addWidget(rel_section)

        # Section 4: 匹配与导出（主页唯一动作入口）(使用 CollapsibleSection)
        res_content = QWidget()
        rg_layout = QVBoxLayout(res_content)
        rg_layout.setContentsMargins(0, 0, 0, 0)

        # matching options
        opt_layout = QHBoxLayout()
        self.match_type = QComboBox()
        self.match_type.addItems(['精准匹配', '模糊匹配'])
        self.fuzzy_threshold = QDoubleSpinBox()
        self.fuzzy_threshold.setRange(0.0, 1.0)
        self.fuzzy_threshold.setValue(0.7)
        opt_layout.addWidget(QLabel('匹配类型:'))
        opt_layout.addWidget(self.match_type)
        opt_layout.addWidget(QLabel('模糊阈值:'))
        opt_layout.addWidget(self.fuzzy_threshold)
        opt_layout.addStretch()
        rg_layout.addLayout(opt_layout)

        match_btn_layout = QHBoxLayout()
        btn_run_match = QPushButton("开始匹配")
        btn_run_match.clicked.connect(self._home_run_match)
        btn_export_results = QPushButton("导出匹配结果")
        btn_export_results.clicked.connect(self._home_export_results)
        match_btn_layout.addStretch()
        match_btn_layout.addWidget(btn_run_match)
        match_btn_layout.addWidget(btn_export_results)
        rg_layout.addLayout(match_btn_layout)

        # result preview table (home shows a small summary)
        self.result_table = QTableWidget()
        self.result_table.setColumnCount(6)
        self.result_table.setHorizontalHeaderLabels(['左表ID', '右表ID', '匹配类型', '置信度', '左表地址', '右表地址'])
        rg_layout.addWidget(self.result_table)

        res_section = CollapsibleSection("4. 匹配与导出", expanded=True)
        res_section.add_content_widget(res_content)
        layout.addWidget(res_section)

        # Spacer
        layout.addStretch()

        scroll.setWidget(scroll_content)
        main_layout.addWidget(scroll)

        tab.setLayout(main_layout)
        return tab

    # ---------------- Home helpers ----------------
    def _home_select_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "选择数据文件（加载到左表）", "", "所有支持格式 (*.csv *.xlsx *.xls *.shp *.geojson)")
        if not file_path:
            return
        self.home_file_label.setText(file_path)
        try:
            from ..core.data_loader import DataLoader
            data, geom = DataLoader.auto_load(file_path)
            self.left_data = data
            self.left_file = file_path
            self._preview_data(self.left_preview, data)
            # populate std combo
            try:
                fields = list(self.left_data[0].keys())
                self.std_field_combo.clear()
                self.std_field_combo.addItems(fields)
            except Exception:
                pass
            self._log('INFO', f'Loaded file into left: {file_path}')
        except Exception as e:
            self._log('ERROR', f'Load failed: {e}')

    def _home_run_clean(self):
        if not self.left_data:
            QMessageBox.warning(self, '提示', '请先选择并加载左表文件')
            return
        self.clean_progress.setValue(10)
        cleaned = []
        for row in self.left_data:
            newrow = {k: (v.strip() if isinstance(v, str) else v) for k, v in row.items()}
            if any(v not in (None, '') for v in newrow.values()):
                cleaned.append(newrow)
        self.left_data = cleaned
        self._preview_data(self.left_preview, cleaned)
        self.clean_progress.setValue(80)
        try:
            from ..utils.cache import save_cache
            save_cache('cleaned_left', cleaned)
            self._log('INFO', f'Clean complete, {len(cleaned)} rows cached')
        except Exception as e:
            self._log('WARN', f'Cache failed: {e}')
        self.clean_progress.setValue(100)

    def _home_run_standardize(self):
        if not self.left_data:
            QMessageBox.warning(self, '提示', '请先加载左表')
            return
        field = self.std_field_combo.currentText()
        if not field:
            QMessageBox.warning(self, '提示', '请选择要标准化的字段')
            return
        self.std_progress.setValue(10)
        mapping = {'北京市': '北京', '上海市': '上海'}
        for row in self.left_data:
            val = row.get(field)
            if isinstance(val, str) and val in mapping:
                row[field] = mapping[val]
        self._preview_data(self.left_preview, self.left_data)
        self.std_progress.setValue(80)
        try:
            from ..utils.cache import save_cache
            save_cache('standardized_left', self.left_data)
            self._log('INFO', f'Standardized field {field} and cached')
        except Exception as e:
            self._log('WARN', f'Cache failed: {e}')
        self.std_progress.setValue(100)

    def _home_run_infer_relations(self):
        if not self.left_data or not self.right_data:
            QMessageBox.warning(self, '提示', '请加载左/右表以推断字段关系')
            return
        try:
            from ..core.field_detector import FieldDetector
            detector = FieldDetector()
            rels = detector.infer_field_relationships({'left': self.left_data, 'right': self.right_data})
            self.rel_preview.setRowCount(0)
            for rel in rels[:50]:
                s1, f1, s2, f2, score = rel
                r = self.rel_preview.rowCount()
                self.rel_preview.insertRow(r)
                self.rel_preview.setItem(r, 0, QTableWidgetItem(s1))
                self.rel_preview.setItem(r, 1, QTableWidgetItem(f1))
                self.rel_preview.setItem(r, 2, QTableWidgetItem(s2))
                self.rel_preview.setItem(r, 3, QTableWidgetItem(f2))
                self.rel_preview.setItem(r, 4, QTableWidgetItem(f"{score:.2%}"))
            self._log('INFO', f'Inferred {len(rels)} relationships')
        except Exception as e:
            self._log('ERROR', f'Infer failed: {e}')

    def _home_run_match(self):
        if not self.left_data or not self.right_data:
            QMessageBox.warning(self, '提示', '请先加载左/右表')
            return
        from ..core.match_engine import MatchEngine
        engine = MatchEngine(fuzzy_threshold=self.fuzzy_threshold.value())

        match_type = self.match_type.currentText()
        if match_type == '精准匹配':
            # quick demo: match by first field
            lf = list(self.left_data[0].keys())[0]
            rf = list(self.right_data[0].keys())[0]
            results = engine.exact_match(self.left_data, self.right_data, lf, rf)
        else:
            lf = list(self.left_data[0].keys())[0]
            rf = list(self.right_data[0].keys())[0]
            results = engine.fuzzy_match(self.left_data, self.right_data, lf, rf)

        # display limited results in home result_table
        self.result_table.setRowCount(0)
        for res in results[:200]:
            r = self.result_table.rowCount()
            self.result_table.insertRow(r)
            left_id = str(res['left'].get('id', ''))
            right_id = str(res['right'].get('id', res['right'].get('record_id', '')))
            self.result_table.setItem(r, 0, QTableWidgetItem(left_id))
            self.result_table.setItem(r, 1, QTableWidgetItem(right_id))
            self.result_table.setItem(r, 2, QTableWidgetItem(res.get('match_type', '')))
            self.result_table.setItem(r, 3, QTableWidgetItem(f"{res.get('confidence', 0):.2%}"))
            self.result_table.setItem(r, 4, QTableWidgetItem(str(res['left'])[:150]))
            self.result_table.setItem(r, 5, QTableWidgetItem(str(res['right'])[:150]))

        self._log('INFO', f'Match finished, found {len(results)} results')

    def _home_export_results(self):
        if self.result_table.rowCount() == 0:
            QMessageBox.warning(self, '提示', '无匹配结果可导出')
            return
        file_path, _ = QFileDialog.getSaveFileName(self, '保存匹配结果', '', 'CSV (*.csv)')
        if not file_path:
            return
        import csv
        with open(file_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            headers = [self.result_table.horizontalHeaderItem(i).text() for i in range(self.result_table.columnCount())]
            writer.writerow(headers)
            for r in range(self.result_table.rowCount()):
                row = [self.result_table.item(r, c).text() if self.result_table.item(r, c) else '' for c in range(self.result_table.columnCount())]
                writer.writerow(row)
        self._log('INFO', f'Exported results to {file_path}')

    def _preview_data(self, table: QTableWidget, data: List[Dict]):
        if not data:
            return
        table.setRowCount(0)
        table.setColumnCount(0)
        first = data[0]
        cols = list(first.keys())
        table.setColumnCount(len(cols))
        table.setHorizontalHeaderLabels(cols)
        for i, row in enumerate(data[:5]):
            table.insertRow(i)
            for j, col in enumerate(cols):
                table.setItem(i, j, QTableWidgetItem(str(row.get(col, ''))[:120]))

    def _log(self, level: str, msg: str):
        import datetime
        r = self.console_log.rowCount()
        self.console_log.insertRow(r)
        self.console_log.setItem(r, 0, QTableWidgetItem(datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        self.console_log.setItem(r, 1, QTableWidgetItem(level))
        self.console_log.setItem(r, 2, QTableWidgetItem(msg))
        try:
            self.console_log.resizeRowsToContents()
            if self.console_log.rowCount() > 0:
                self.console_log.scrollToItem(self.console_log.item(r, 0))
                self.console_log.setCurrentCell(r, 0)
        except Exception:
            pass

    def _export_log(self):
        if self.console_log.rowCount() == 0:
            QMessageBox.information(self, '提示', '日志为空')
            return
        file_path, _ = QFileDialog.getSaveFileName(self, '导出日志', '', 'CSV (*.csv)')
        if not file_path:
            return
        import csv
        with open(file_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['时间', '级别', '消息'])
            for r in range(self.console_log.rowCount()):
                t = self.console_log.item(r, 0).text() if self.console_log.item(r, 0) else ''
                lv = self.console_log.item(r, 1).text() if self.console_log.item(r, 1) else ''
                msg = self.console_log.item(r, 2).text() if self.console_log.item(r, 2) else ''
                writer.writerow([t, lv, msg])
        self._log('INFO', f'Exported log to {file_path}')

    def _home_open_cache(self, name: str):
        try:
            from ..utils.cache import load_cache
            data = load_cache(name if name else 'cleaned_left')
            if not data:
                QMessageBox.information(self, '提示', '未找到缓存')
                return
            # show a quick preview
            self._preview_data(self.left_preview, data)
            self._log('INFO', f'Loaded cache {name}')
        except Exception as e:
            self._log('ERROR', f'Open cache failed: {e}')
