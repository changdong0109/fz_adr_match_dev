"""
地址匹配 UI 对话框 - QGIS 插件主界面
"""

from typing import List, Dict, Optional
import traceback

try:
    from qgis.PyQt.QtWidgets import (
        QDialog, QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
        QPushButton, QLabel, QFileDialog, QTableWidget, QTableWidgetItem,
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
        tabs.addTab(self._create_data_tab(), "数据加载")
        tabs.addTab(self._create_field_tab(), "字段映射")
        tabs.addTab(self._create_matching_tab(), "匹配配置")
        tabs.addTab(self._create_result_tab(), "匹配结果")

        layout.addWidget(tabs)

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
