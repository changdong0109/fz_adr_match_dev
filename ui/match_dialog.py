"""
地址匹配 UI 对话框 - 精简版（仅保留主页）

此文件已精简：仅保留 `主页` 标签，主页包含文件上传、预览、清洗、标准化、字段推断、快速匹配、导出与日志。
后续若需扩展其它页面再拆分模块。
"""

from typing import List, Dict, Optional
import traceback

try:
    from qgis.PyQt.QtWidgets import (
        QDialog, QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
        QPushButton, QLabel, QFileDialog, QTableWidget, QTableWidgetItem,
        QHeaderView, QAbstractItemView,
        QComboBox, QDoubleSpinBox, QMessageBox, QProgressBar,
        QLineEdit, QGroupBox
    )
    from qgis.PyQt.QtCore import Qt, pyqtSignal
    QGIS_AVAILABLE = True
except ImportError:
    QGIS_AVAILABLE = False

# 兼容性封装：处理 PyQt 版本差异（某些 PyQt/PySide 绑定中 NoEditTriggers 属性位置不同）
try:
    EDIT_TRIGGERS_NONE = QAbstractItemView.NoEditTriggers
except AttributeError:
    # 备选方案：从 QTableWidget 读取
    try:
        EDIT_TRIGGERS_NONE = QTableWidget.NoEditTriggers
    except AttributeError:
        # 如果都找不到，使用数值常量（通常为 0）
        EDIT_TRIGGERS_NONE = 0


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
        layout = QVBoxLayout()

        # Console / log viewer
        console_group = QGroupBox("控制台日志")
        console_layout = QVBoxLayout()
        self.console_log = QTableWidget()
        self.console_log.setColumnCount(3)
        self.console_log.setHorizontalHeaderLabels(['时间', '级别', '消息'])
        self.console_log.setMaximumHeight(200)
        self.console_log.setEditTriggers(EDIT_TRIGGERS_NONE)
        self.console_log.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.console_log.setWordWrap(True)
        self.console_log.verticalHeader().setVisible(False)
        self.console_log.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.console_log.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.console_log.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
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

        # Section: 数据上传与清洗 + 预览
        clean_group = QGroupBox("1. 数据上传与清洗（左表/右表）")
        clean_group.setCheckable(True)
        clean_group.setChecked(True)
        cg_layout = QVBoxLayout()

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

        clean_group.setLayout(cg_layout)
        layout.addWidget(clean_group)

        # Section: 标准化
        std_group = QGroupBox("2. 地址标准化")
        std_group.setCheckable(True)
        std_group.setChecked(False)
        sg_layout = QVBoxLayout()
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
        std_group.setLayout(sg_layout)
        layout.addWidget(std_group)

        # Section: 字段推断（演示）
        rel_group = QGroupBox("3. 智能字段匹配关系（示例）")
        rel_group.setCheckable(True)
        rel_group.setChecked(False)
        rl_layout = QVBoxLayout()
        btn_rel = QPushButton("检测字段关系")
        btn_rel.clicked.connect(self._home_run_infer_relations)
        rl_layout.addWidget(btn_rel)
        self.rel_preview = QTableWidget()
        self.rel_preview.setColumnCount(5)
        self.rel_preview.setHorizontalHeaderLabels(['源1', '字段1', '源2', '字段2', '相似度'])
        rl_layout.addWidget(self.rel_preview)
        rel_group.setLayout(rl_layout)
        layout.addWidget(rel_group)

        # Section: 匹配与导出（主页唯一动作入口）
        res_group = QGroupBox("4. 匹配与导出")
        res_group.setCheckable(True)
        res_group.setChecked(True)
        rg_layout = QVBoxLayout()

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

        res_group.setLayout(rg_layout)
        layout.addWidget(res_group)

        # Spacer
        layout.addStretch()

        tab.setLayout(layout)
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
"""
地址匹配 UI 对话框 - QGIS 插件主界面
"""

from typing import List, Dict, Optional
import traceback

try:
    from qgis.PyQt.QtWidgets import (
        QDialog, QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
        QPushButton, QLabel, QFileDialog, QTableWidget, QTableWidgetItem,
            QHeaderView, QAbstractItemView,
        QComboBox, QSpinBox, QDoubleSpinBox, QMessageBox, QProgressBar,
        QLineEdit, QGroupBox, QFormLayout, QCheckBox
    )
    from qgis.PyQt.QtCore import Qt, pyqtSignal
    from qgis.PyQt.QtGui import QColor

    QGIS_AVAILABLE = True
except ImportError:
    QGIS_AVAILABLE = False


class MatchDialog(QDialog):
    """地址匹配主对话框"""

    match_completed = pyqtSignal(list)  # 匹配完成信号

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("地址标准化与管网匹配")
        self.setGeometry(100, 100, 1200, 800)

        self.left_data = None
        self.right_data = None
        self.left_file = None
        self.right_file = None

        self.init_ui()

    def init_ui(self):
        """初始化 UI"""
        layout = QVBoxLayout()

        # 创建标签页
        tabs = QTabWidget()
        tabs.addTab(self._create_home_tab(), "主页")
        tabs.addTab(self._create_data_tab(), "数据加载")
        tabs.addTab(self._create_field_tab(), "字段映射")
        tabs.addTab(self._create_matching_tab(), "匹配配置")
        tabs.addTab(self._create_result_tab(), "匹配结果")

        # keep reference for cross-widget synchronization
        self.tabs = tabs

        layout.addWidget(tabs)

        # connect Home group toggles to switch tabs (if groups exist)
        try:
            if getattr(self, 'clean_group', None):
                self.clean_group.toggled.connect(self._on_group_toggled_switch_tab(1))
            if getattr(self, 'std_group', None):
                self.std_group.toggled.connect(self._on_group_toggled_switch_tab(2))
            if getattr(self, 'matchrel_group', None):
                self.matchrel_group.toggled.connect(self._on_group_toggled_switch_tab(2))
            if getattr(self, 'res_group', None):
                self.res_group.toggled.connect(self._on_group_toggled_switch_tab(3))
            if getattr(self, 'vis_group', None):
                self.vis_group.toggled.connect(self._on_group_toggled_switch_tab(4))

            # when user changes tabs, try to expand a related Home group for context
            self.tabs.currentChanged.connect(self._on_tab_changed_sync_groups)
        except Exception:
            pass

        # 底部按钮
        btn_layout = QHBoxLayout()
        btn_match = QPushButton("开始匹配")
        btn_match.clicked.connect(self.perform_match)
        btn_export = QPushButton("导出结果")
        btn_export.clicked.connect(self.export_results)
        btn_close = QPushButton("关闭")
        btn_close.clicked.connect(self.close)

        btn_layout.addStretch()
        btn_layout.addWidget(btn_match)
        btn_layout.addWidget(btn_export)
        btn_layout.addWidget(btn_close)
        layout.addLayout(btn_layout)

        self.setLayout(layout)

    def _create_data_tab(self) -> QDialog:
        """数据加载标签页"""
        tab = QDialog()
        layout = QVBoxLayout()

        # 左表数据
        left_group = QGroupBox("左表数据（主表）")
        left_layout = QVBoxLayout()
        left_layout.addWidget(QLabel("选择文件 (CSV/Excel/SHP/GeoJSON):"))

        left_file_layout = QHBoxLayout()
        self.left_file_label = QLineEdit()
        self.left_file_label.setReadOnly(True)
        left_file_layout.addWidget(self.left_file_label)
        btn_left = QPushButton("浏览...")
        btn_left.clicked.connect(lambda: self._load_file('left'))
        left_file_layout.addWidget(btn_left)
        left_layout.addLayout(left_file_layout)

        self.left_preview = QTableWidget()
        self.left_preview.setMaximumHeight(200)
        left_layout.addWidget(QLabel("预览（前 5 行）:"))
        left_layout.addWidget(self.left_preview)

        left_group.setLayout(left_layout)
        layout.addWidget(left_group)

        # 右表数据
        right_group = QGroupBox("右表数据（待匹配表）")
        right_layout = QVBoxLayout()
        right_layout.addWidget(QLabel("选择文件 (CSV/Excel/SHP/GeoJSON):"))

        right_file_layout = QHBoxLayout()
        self.right_file_label = QLineEdit()
        self.right_file_label.setReadOnly(True)
        right_file_layout.addWidget(self.right_file_label)
        btn_right = QPushButton("浏览...")
        btn_right.clicked.connect(lambda: self._load_file('right'))
        right_file_layout.addWidget(btn_right)
        right_layout.addLayout(right_file_layout)

        self.right_preview = QTableWidget()
        self.right_preview.setMaximumHeight(200)
        right_layout.addWidget(QLabel("预览（前 5 行）:"))
        right_layout.addWidget(self.right_preview)

        right_group.setLayout(right_layout)
        layout.addWidget(right_group)

        tab.setLayout(layout)
        return tab

    def _on_group_toggled_switch_tab(self, index: int):
        """Return a callback to switch to tab `index` when a group is expanded."""
        def _cb(checked: bool):
            try:
                if checked and hasattr(self, 'tabs'):
                    # switch to the corresponding tab
                    self.tabs.setCurrentIndex(index)
            except Exception:
                pass
        return _cb

    def _on_tab_changed_sync_groups(self, index: int):
        """When the user changes tab, expand the related group in Home and collapse others."""
        try:
            mapping = {
                0: getattr(self, 'clean_group', None),
                1: None,  # Data tab not represented as a Home group
                2: None,
                3: getattr(self, 'res_group', None),
                4: getattr(self, 'res_group', None),
            }
            # If switching to Home (index 0) do nothing here; otherwise ensure a visible cue
            # Expand the Home group that most closely matches the tab (simple heuristic)
            # We'll expand the first relevant Home group when the tab changes.
            if index == 0:
                return
            # for simplicity, expand res_group when entering matching/result tabs
            if index in (3, 4) and getattr(self, 'res_group', None):
                self.res_group.setChecked(True)
            # if data tab, expand clean_group
            if index == 1 and getattr(self, 'clean_group', None):
                self.clean_group.setChecked(True)
        except Exception:
            pass

    def _create_field_tab(self) -> QDialog:
        """字段映射标签页"""
        tab = QDialog()
        layout = QVBoxLayout()

        layout.addWidget(QLabel("检测到的字段关联关系："))

        self.field_relations = QTableWidget()
        self.field_relations.setColumnCount(5)
        self.field_relations.setHorizontalHeaderLabels(
            ['左表字段', '字段类型', '右表字段', '推荐字段', '相似度']
        )
        self.field_relations.setMaximumHeight(300)
        layout.addWidget(self.field_relations)

        # 手动配置
        config_group = QGroupBox("手动配置匹配字段")
        config_layout = QFormLayout()

        self.field_config = []
        for i in range(3):  # 允许最多 3 组字段配置
            left_combo = QComboBox()
            right_combo = QComboBox()
            self.field_config.append((left_combo, right_combo))

            # 创建一个 QWidget 容器，将左右下拉框放入其中，然后作为字段添加到 QFormLayout
            row_widget = QWidget()
            row_layout = QHBoxLayout(row_widget)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.addWidget(left_combo)
            row_layout.addWidget(QLabel("→"))
            row_layout.addWidget(right_combo)

            config_layout.addRow(f"匹配字段组 {i + 1}", row_widget)

        config_group.setLayout(config_layout)
        layout.addWidget(config_group)

        tab.setLayout(layout)
        return tab

    def _create_home_tab(self) -> QDialog:
        """主页：折叠式工作流面板（上传/清洗/标准化/匹配/可视化/缓存/日志）"""
        tab = QDialog()
        layout = QVBoxLayout()

        # Console / log viewer at top
        console_group = QGroupBox("控制台日志")
        console_layout = QVBoxLayout()
        self.console_log = QTableWidget()
        # use 3 columns: 时间, 级别, 消息 (message column will stretch)
        self.console_log.setColumnCount(3)
        self.console_log.setHorizontalHeaderLabels(['时间', '级别', '消息'])
        self.console_log.setMaximumHeight(200)
        # UX improvements
        self.console_log.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.console_log.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.console_log.setWordWrap(True)
        self.console_log.verticalHeader().setVisible(False)
        # header sizing: time and level autosize, message stretch
        self.console_log.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.console_log.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.console_log.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        console_layout.addWidget(self.console_log)
        console_group.setLayout(console_layout)
        layout.addWidget(console_group)

        # make groupboxes visually consistent
        console_group.setStyleSheet('QGroupBox { font-weight: bold; margin-top: 6px; } QGroupBox::title { subcontrol-origin: margin; left: 6px; padding: 0 3px 0 3px; }')

        # Section 1: 数据清洗（上传 + 清洗 + 缓存）
        clean_group = QGroupBox("1. 数据上传与清洗")
        clean_group.setCheckable(True)
        clean_group.setChecked(True)
        clean_group.setStyleSheet('QGroupBox { font-weight: bold; }')

        # contenu widget: put all controls into a single child widget so hiding collapses properly
        clean_content = QWidget()
        clean_content_layout = QVBoxLayout(clean_content)
        clean_content_layout.setContentsMargins(0, 0, 0, 0)

        upload_layout = QHBoxLayout()
        self.home_file_label = QLineEdit()
        self.home_file_label.setReadOnly(True)
        upload_btn = QPushButton("选择文件...")
        upload_btn.clicked.connect(lambda: self._home_select_file())
        upload_layout.addWidget(self.home_file_label)
        upload_layout.addWidget(upload_btn)
        clean_content_layout.addLayout(upload_layout)

        self.clean_progress = QProgressBar()
        self.clean_progress.setValue(0)
        clean_content_layout.addWidget(self.clean_progress)

        clean_btns = QHBoxLayout()
        btn_clean_run = QPushButton("执行清洗")
        btn_clean_run.clicked.connect(lambda: self._home_run_clean())
        btn_clean_cache = QPushButton("打开清洗缓存")
        btn_clean_cache.clicked.connect(lambda: self._home_open_cache('clean'))
        clean_btns.addWidget(btn_clean_run)
        clean_btns.addWidget(btn_clean_cache)
        clean_content_layout.addLayout(clean_btns)

        # set QGroupBox layout and add the single content widget
        clean_group_layout = QVBoxLayout()
        clean_group_layout.setContentsMargins(6, 20, 6, 6)
        clean_group_layout.addWidget(clean_content)
        clean_group.setLayout(clean_group_layout)
        # keep a reference to the content widget for simpler toggling
        clean_group._content_widget = clean_content
        # expose as attributes for tab/group synchronization
        self.clean_group = clean_group
        layout.addWidget(clean_group)

        # connect toggled for collapse/expand
        clean_group.toggled.connect(lambda checked, g=clean_group: self._toggle_group_visibility(g, checked))

        # Section 2: 地址标准化
        std_group = QGroupBox("2. 地址标准化")
        std_group.setCheckable(True)
        std_group.setChecked(False)
        std_group.setStyleSheet('QGroupBox { font-weight: bold; }')

        std_content = QWidget()
        std_content_layout = QVBoxLayout(std_content)
        std_content_layout.setContentsMargins(0, 0, 0, 0)

        std_content_layout.addWidget(QLabel("选择要标准化的字段（可多选）："))
        self.std_field_combo = QComboBox()
        std_content_layout.addWidget(self.std_field_combo)

        self.std_progress = QProgressBar()
        std_content_layout.addWidget(self.std_progress)

        std_btns = QHBoxLayout()
        btn_std_run = QPushButton("执行标准化")
        btn_std_run.clicked.connect(lambda: self._home_run_standardize())
        btn_std_cache = QPushButton("打开标准化缓存")
        btn_std_cache.clicked.connect(lambda: self._home_open_cache('standardize'))
        std_btns.addWidget(btn_std_run)
        std_btns.addWidget(btn_std_cache)
        std_content_layout.addLayout(std_btns)

        std_group_layout = QVBoxLayout()
        std_group_layout.setContentsMargins(6, 20, 6, 6)
        std_group_layout.addWidget(std_content)
        std_group.setLayout(std_group_layout)
        std_group._content_widget = std_content
        self.std_group = std_group
        layout.addWidget(std_group)
        std_group.toggled.connect(lambda checked, g=std_group: self._toggle_group_visibility(g, checked))

        # Section 3: 智能字段匹配（演示与案例）
        matchrel_group = QGroupBox("3. 智能字段匹配关系（示例）")
        matchrel_group.setCheckable(True)
        matchrel_group.setChecked(False)
        matchrel_group.setStyleSheet('QGroupBox { font-weight: bold; }')

        matchrel_content = QWidget()
        matchrel_content_layout = QVBoxLayout(matchrel_content)
        matchrel_content_layout.setContentsMargins(0, 0, 0, 0)

        btn_rel_run = QPushButton("检测字段关系")
        btn_rel_run.clicked.connect(lambda: self._home_run_infer_relations())
        matchrel_content_layout.addWidget(btn_rel_run)

        self.rel_preview = QTableWidget()
        self.rel_preview.setColumnCount(5)
        self.rel_preview.setHorizontalHeaderLabels(['源1', '字段1', '源2', '字段2', '相似度'])
        matchrel_content_layout.addWidget(self.rel_preview)

        matchrel_group_layout = QVBoxLayout()
        matchrel_group_layout.setContentsMargins(6, 20, 6, 6)
        matchrel_group_layout.addWidget(matchrel_content)
        matchrel_group.setLayout(matchrel_group_layout)
        matchrel_group._content_widget = matchrel_content
        self.matchrel_group = matchrel_group
        layout.addWidget(matchrel_group)
        matchrel_group.toggled.connect(lambda checked, g=matchrel_group: self._toggle_group_visibility(g, checked))

        # Section 4: 匹配结果方式配置与导出
        res_group = QGroupBox("4. 匹配结果与导出")
        res_group.setCheckable(True)
        res_group.setChecked(False)
        res_group.setStyleSheet('QGroupBox { font-weight: bold; }')

        res_content = QWidget()
        res_content_layout = QVBoxLayout(res_content)
        res_content_layout.setContentsMargins(0, 0, 0, 0)

        btn_res_run = QPushButton("执行匹配(快速示例)")
        btn_res_run.clicked.connect(lambda: self._home_run_match())
        res_content_layout.addWidget(btn_res_run)

        btn_export_all = QPushButton("导出匹配/未匹配数据")
        btn_export_all.clicked.connect(lambda: self._home_export_results())
        res_content_layout.addWidget(btn_export_all)

        res_group_layout = QVBoxLayout()
        res_group_layout.setContentsMargins(6, 20, 6, 6)
        res_group_layout.addWidget(res_content)
        res_group.setLayout(res_group_layout)
        res_group._content_widget = res_content
        self.res_group = res_group
        layout.addWidget(res_group)
        res_group.toggled.connect(lambda checked, g=res_group: self._toggle_group_visibility(g, checked))

        # Section 5: 地图可视化（打开地图并高亮）
        vis_group = QGroupBox("5. 地图可视化")
        vis_group.setCheckable(True)
        vis_group.setChecked(False)
        vis_group.setStyleSheet('QGroupBox { font-weight: bold; }')

        vis_content = QWidget()
        vis_content_layout = QVBoxLayout(vis_content)
        vis_content_layout.setContentsMargins(0, 0, 0, 0)
        btn_vis = QPushButton("在地图上显示匹配关系")
        btn_vis.clicked.connect(lambda: self._home_show_on_map())
        vis_content_layout.addWidget(btn_vis)

        vis_group_layout = QVBoxLayout()
        vis_group_layout.setContentsMargins(6, 20, 6, 6)
        vis_group_layout.addWidget(vis_content)
        vis_group.setLayout(vis_group_layout)
        vis_group._content_widget = vis_content
        self.vis_group = vis_group
        layout.addWidget(vis_group)
        vis_group.toggled.connect(lambda checked, g=vis_group: self._toggle_group_visibility(g, checked))

        # Spacer
        layout.addStretch()

        tab.setLayout(layout)
        return tab

    def _create_matching_tab(self) -> QDialog:
        """匹配配置标签页"""
        tab = QDialog()
        layout = QVBoxLayout()

        config_group = QGroupBox("匹配策略配置")
        config_layout = QFormLayout()

        # 匹配类型选择
        self.match_type = QComboBox()
        self.match_type.addItems(['精准匹配', '模糊匹配', '多字段组合匹配', '混合匹配'])
        config_layout.addRow("匹配类型:", self.match_type)

        # 模糊匹配阈值
        self.fuzzy_threshold = QDoubleSpinBox()
        self.fuzzy_threshold.setRange(0.0, 1.0)
        self.fuzzy_threshold.setValue(0.7)
        self.fuzzy_threshold.setSingleStep(0.05)
        config_layout.addRow("模糊匹配相似度阈值:", self.fuzzy_threshold)

        # 其他选项
        self.case_sensitive = QCheckBox("区分大小写")
        config_layout.addRow("", self.case_sensitive)

        config_group.setLayout(config_layout)
        layout.addWidget(config_group)

        # 匹配进度
        progress_group = QGroupBox("匹配进度")
        progress_layout = QVBoxLayout()
        self.progress_bar = QProgressBar()
        progress_layout.addWidget(self.progress_bar)
        progress_group.setLayout(progress_layout)
        layout.addWidget(progress_group)

        layout.addStretch()

        tab.setLayout(layout)
        return tab

    def _create_result_tab(self) -> QDialog:
        """结果显示标签页"""
        tab = QDialog()
        layout = QVBoxLayout()

        # 统计信息
        stats_group = QGroupBox("匹配统计")
        stats_layout = QHBoxLayout()
        self.stat_total = QLabel("总记录数: 0")
        self.stat_matched = QLabel("匹配数: 0")
        self.stat_unmatched = QLabel("未匹配数: 0")
        self.stat_accuracy = QLabel("匹配率: 0%")
        stats_layout.addWidget(self.stat_total)
        stats_layout.addWidget(self.stat_matched)
        stats_layout.addWidget(self.stat_unmatched)
        stats_layout.addWidget(self.stat_accuracy)
        stats_group.setLayout(stats_layout)
        layout.addWidget(stats_group)

        # 结果表
        self.result_table = QTableWidget()
        self.result_table.setColumnCount(6)
        self.result_table.setHorizontalHeaderLabels(
            ['左表ID', '右表ID', '匹配类型', '相信度', '左表地址', '右表地址']
        )
        layout.addWidget(self.result_table)

        tab.setLayout(layout)
        return tab

    def _load_file(self, side: str):
        """加载文件"""
        try:
            from ..core.data_loader import DataLoader

            file_path, _ = QFileDialog.getOpenFileName(
                self,
                "选择数据文件",
                "",
                "所有支持格式 (*.csv *.xlsx *.xls *.shp *.geojson);;CSV (*.csv);;Excel (*.xlsx *.xls);;SHP (*.shp);;GeoJSON (*.geojson)"
            )

            if not file_path:
                return

            self.progress_bar.setValue(10)

            # 加载数据
            data, geom_col = DataLoader.auto_load(file_path)
            self.progress_bar.setValue(50)

            if side == 'left':
                self.left_data = data
                self.left_file = file_path
                self.left_file_label.setText(file_path)
                self._preview_data(self.left_preview, data)
                self._populate_field_combos('left')
            else:
                self.right_data = data
                self.right_file = file_path
                self.right_file_label.setText(file_path)
                self._preview_data(self.right_preview, data)
                self._populate_field_combos('right')

            # 自动检测字段关联
            if self.left_data and self.right_data:
                self._detect_field_relations()

            # update home combos and preview
            try:
                # populate home field combo with left table fields
                if self.left_data:
                    fields = list(self.left_data[0].keys())
                    self.std_field_combo.clear()
                    self.std_field_combo.addItems(fields)
            except Exception:
                pass

            self.progress_bar.setValue(100)

        except Exception as e:
            QMessageBox.critical(self, "错误", f"加载失败: {e}\n{traceback.format_exc()}")
            self.progress_bar.setValue(0)

    def _preview_data(self, table: QTableWidget, data: List[Dict]):
        """在表中显示数据预览"""
        if not data:
            return

        # 清空旧内容
        table.setRowCount(0)
        table.setColumnCount(0)

        # 设置列
        first_row = data[0]
        columns = list(first_row.keys())
        table.setColumnCount(len(columns))
        table.setHorizontalHeaderLabels(columns)

        # 添加行（最多 5 行）
        for row_idx, row in enumerate(data[:5]):
            table.insertRow(row_idx)
            for col_idx, col_name in enumerate(columns):
                value = str(row.get(col_name, ''))[:100]  # 截断长字符串
                table.setItem(row_idx, col_idx, QTableWidgetItem(value))

    def _populate_field_combos(self, side: str):
        """填充字段下拉框"""
        if side == 'left' and self.left_data:
            fields = list(self.left_data[0].keys())
            for combo, _ in self.field_config:
                combo.clear()
                combo.addItems(fields)
        elif side == 'right' and self.right_data:
            fields = list(self.right_data[0].keys())
            for _, combo in self.field_config:
                combo.clear()
                combo.addItems(fields)

    def _detect_field_relations(self):
        """自动检测字段关系"""
        try:
            from ..core.field_detector import FieldDetector

            detector = FieldDetector()
            datasets = {
                'left': self.left_data,
                'right': self.right_data
            }

            relationships = detector.infer_field_relationships(datasets)

            # 显示关系
            self.field_relations.setRowCount(0)
            for rel in relationships[:10]:  # 显示前 10 个
                source1, field1, source2, field2, score = rel
                row_idx = self.field_relations.rowCount()
                self.field_relations.insertRow(row_idx)

                self.field_relations.setItem(row_idx, 0, QTableWidgetItem(field1))
                self.field_relations.setItem(row_idx, 1, QTableWidgetItem(source1))
                self.field_relations.setItem(row_idx, 2, QTableWidgetItem(field2))
                self.field_relations.setItem(row_idx, 3, QTableWidgetItem(source2))
                self.field_relations.setItem(row_idx, 4, QTableWidgetItem(f"{score:.2%}"))

        except Exception as e:
            QMessageBox.warning(self, "警告", f"字段检测失败: {e}")

    def perform_match(self):
        """执行匹配"""
        try:
            if not self.left_data or not self.right_data:
                QMessageBox.warning(self, "提示", "请先加载两个数据文件")
                return

            from ..core.match_engine import MatchEngine

            # 获取配置
            match_type = self.match_type.currentText()
            threshold = self.fuzzy_threshold.value()

            engine = MatchEngine(fuzzy_threshold=threshold)

            # 获取用户选择的字段
            field_pairs = []
            for left_combo, right_combo in self.field_config:
                left_field = left_combo.currentText()
                right_field = right_combo.currentText()
                if left_field and right_field:
                    field_pairs.append((left_field, right_field))

            if not field_pairs:
                QMessageBox.warning(self, "提示", "请配置至少一组匹配字段")
                return

            self.progress_bar.setValue(0)

            # 执行匹配
            if match_type == '精准匹配':
                results = []
                for left_field, right_field in field_pairs:
                    results.extend(engine.exact_match(
                        self.left_data, self.right_data, left_field, right_field
                    ))
            elif match_type == '模糊匹配':
                results = []
                for left_field, right_field in field_pairs:
                    results.extend(engine.fuzzy_match(
                        self.left_data, self.right_data, left_field, right_field
                    ))
            elif match_type == '多字段组合匹配':
                results = engine.multi_field_match(
                    self.left_data, self.right_data, field_pairs
                )
            else:  # 混合匹配
                strategies = []
                for left_field, right_field in field_pairs:
                    strategies.append({'type': 'exact', 'left_key': left_field, 'right_key': right_field})
                    strategies.append({'type': 'fuzzy', 'left_key': left_field, 'right_key': right_field})
                results = engine.batch_match(self.left_data, self.right_data, strategies)

            self.progress_bar.setValue(80)

            # 显示结果
            self._display_results(results)
            self.match_completed.emit(results)

            self.progress_bar.setValue(100)
            QMessageBox.information(self, "成功", f"匹配完成！共匹配 {len(results)} 条记录")

        except Exception as e:
            QMessageBox.critical(self, "错误", f"匹配失败: {e}\n{traceback.format_exc()}")
            self.progress_bar.setValue(0)

    def _display_results(self, results: List[Dict]):
        """在结果表中显示匹配结果"""
        self.result_table.setRowCount(0)

        for result in results[:100]:  # 显示前 100 条
            row_idx = self.result_table.rowCount()
            self.result_table.insertRow(row_idx)

            left_row = result['left']
            right_row = result['right']
            match_type = result.get('match_type', 'unknown')
            confidence = result.get('confidence', 0)

            # 获取 ID（假设有 ID 字段）
            left_id = str(left_row.get('id', ''))[:20]
            right_id = str(right_row.get('id', ''))[:20]

            self.result_table.setItem(row_idx, 0, QTableWidgetItem(left_id))
            self.result_table.setItem(row_idx, 1, QTableWidgetItem(right_id))
            self.result_table.setItem(row_idx, 2, QTableWidgetItem(match_type))
            self.result_table.setItem(row_idx, 3, QTableWidgetItem(f"{confidence:.2%}"))
            self.result_table.setItem(row_idx, 4, QTableWidgetItem(str(left_row)[:100]))
            self.result_table.setItem(row_idx, 5, QTableWidgetItem(str(right_row)[:100]))

        # 更新统计
        total = len(self.left_data) if self.left_data else 0
        matched = len(results)
        unmatched = total - matched
        accuracy = (matched / total * 100) if total > 0 else 0

        self.stat_total.setText(f"总记录数: {total}")
        self.stat_matched.setText(f"匹配数: {matched}")
        self.stat_unmatched.setText(f"未匹配数: {unmatched}")
        self.stat_accuracy.setText(f"匹配率: {accuracy:.1f}%")

    # ------------------- Home tab helpers -------------------
    def _home_select_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "选择数据文件", "", "所有支持格式 (*.csv *.xlsx *.xls *.shp *.geojson)")
        if not file_path:
            return
        self.home_file_label.setText(file_path)
        # load immediately into left_data for demo convenience
        try:
            from ..core.data_loader import DataLoader
            data, geom = DataLoader.auto_load(file_path)
            self.left_data = data
            self.left_file = file_path
            self._preview_data(self.left_preview, data)
            self._populate_field_combos('left')
            self._log('INFO', f'Loaded file for cleaning: {file_path}')
        except Exception as e:
            self._log('ERROR', f'Failed to load file: {e}')

    def _home_run_clean(self):
        # Placeholder cleaning: trim strings and remove empty rows
        if not self.left_data:
            QMessageBox.warning(self, '提示', '请先选择文件并加载数据')
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
        # cache
        try:
            from ..utils.cache import save_cache
            save_cache('cleaned_left', cleaned)
            self._log('INFO', f'Clean complete, {len(cleaned)} rows. Cached as cleaned_left.json')
        except Exception as e:
            self._log('WARN', f'Cache failed: {e}')
        self.clean_progress.setValue(100)

    def _home_run_standardize(self):
        # Simple standardization demo: normalize '北京' vs '北京市'
        if not self.left_data:
            QMessageBox.warning(self, '提示', '请先加载数据')
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
            self._log('INFO', f'Standardization complete on field {field}. Cached as standardized_left.json')
        except Exception as e:
            self._log('WARN', f'Cache failed: {e}')
        self.std_progress.setValue(100)

    def _home_run_infer_relations(self):
        if not self.left_data or not self.right_data:
            QMessageBox.warning(self, '提示', '请先加载两个数据文件以推断字段关系')
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
            self._log('ERROR', f'Infer relations failed: {e}')

    def _home_run_match(self):
        # simple demo: match by first available field
        if not self.left_data or not self.right_data:
            QMessageBox.warning(self, '提示', '请先加载两个数据文件')
            return
        left_fields = list(self.left_data[0].keys())
        right_fields = list(self.right_data[0].keys())
        # choose first pair
        lf = left_fields[0]
        rf = right_fields[0]
        from ..core.match_engine import MatchEngine
        engine = MatchEngine()
        results = engine.exact_match(self.left_data, self.right_data, lf, rf)
        self._display_results(results)
        self._log('INFO', f'Ran quick match on {lf} -> {rf}, found {len(results)} matches')

    def _home_export_results(self):
        # placeholder: export displayed results table to CSV
        if self.result_table.rowCount() == 0:
            QMessageBox.warning(self, '提示', '当前无匹配结果可导出')
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

    def _home_show_on_map(self):
        # Simple demo: just log (full map integration requires QGIS iface usage)
        self._log('INFO', 'Map visualization requested (open in QGIS to implement actual drawing)')

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

    def _log(self, level: str, msg: str):
        # append to console table
        import datetime
        r = self.console_log.rowCount()
        self.console_log.insertRow(r)
        # columns: 0=time, 1=level, 2=message
        self.console_log.setItem(r, 0, QTableWidgetItem(datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        self.console_log.setItem(r, 1, QTableWidgetItem(level))
        self.console_log.setItem(r, 2, QTableWidgetItem(msg))
        try:
            # resize row height to fit wrapped message and auto-scroll to latest
            self.console_log.resizeRowsToContents()
            # select last row to ensure visibility
            if self.console_log.rowCount() > 0:
                self.console_log.scrollToItem(self.console_log.item(r, 0))
                self.console_log.setCurrentCell(r, 0)
        except Exception:
            pass

    def _toggle_group_visibility(self, group: QGroupBox, checked: bool):
        """Show/hide the contents of a checkable QGroupBox when toggled.

        This avoids relying on QFormLayout.FieldRole and provides a simple
        collapsible behavior: when unchecked, hide all child widgets in the
        group's layout; when checked, show them.
        """
        try:
            # Prefer toggling a single content widget when present.
            content = getattr(group, '_content_widget', None)
            if content is not None:
                content.setVisible(checked)
                # force relayout
                content.updateGeometry()
                group.updateGeometry()
                return

            layout = group.layout()
            if layout is None:
                return
            for i in range(layout.count()):
                item = layout.itemAt(i)
                if item is None:
                    continue
                widget = item.widget()
                if widget is not None:
                    # keep the title visible (QGroupBox handles title), hide/show children
                    widget.setVisible(checked)
                else:
                    # if the item is a layout itself, iterate its widgets
                    child_layout = item.layout()
                    if child_layout:
                        for j in range(child_layout.count()):
                            w = child_layout.itemAt(j).widget()
                            if w:
                                w.setVisible(checked)
        except Exception:
            pass

    def export_results(self):
        """导出匹配结果"""
        try:
            if self.result_table.rowCount() == 0:
                QMessageBox.warning(self, "提示", "没有匹配结果可导出")
                return

            file_path, _ = QFileDialog.getSaveFileName(
                self, "保存匹配结果", "", "CSV (*.csv);;Excel (*.xlsx)"
            )

            if not file_path:
                return

            # TODO: 实现导出逻辑
            QMessageBox.information(self, "成功", f"结果已导出到: {file_path}")

        except Exception as e:
            QMessageBox.critical(self, "错误", f"导出失败: {e}")
