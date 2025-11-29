import json
import os
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from qgis.PyQt.QtCore import Qt, QTimer, QSize
from qgis.PyQt.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QWidget,
    QGroupBox,
    QLabel,
    QLineEdit,
    QPushButton,
    QComboBox,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QCheckBox,
    QProgressBar,
    QTextEdit,
    QFileDialog,
    QScrollArea,
    QListWidget,
    QListWidgetItem,
    QRadioButton,
    QTextBrowser,
    QFrame,
    QMessageBox,
    QAbstractItemView,
)
from qgis.PyQt.QtGui import QFont, QColor, QPalette


def _safe_select_rows(table: QTableWidget):
    try:
        table.setSelectionBehavior(QTableWidget.SelectRows)
        return
    except Exception:
        pass
    try:
        table.setSelectionBehavior(table.SelectRows)
    except Exception:
        pass


def _safe_no_edit(table: QTableWidget):
    try:
        table.setEditTriggers(table.NoEditTriggers)
        return
    except Exception:
        pass
    try:
        from qgis.PyQt.QtWidgets import QAbstractItemView

        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
    except Exception:
        pass


def _safe_stretch(header: QHeaderView, col: int):
    try:
        mode = QHeaderView.Stretch
    except Exception:
        mode = header.Stretch if hasattr(header, "Stretch") else header.Interactive
    try:
        header.setSectionResizeMode(col, mode)
    except Exception:
        try:
            header.setSectionResizeMode(col, header.Interactive)
        except Exception:
            pass


def _set_resize_mode(header: QHeaderView, col: int, prefer_contents: bool = False):
    try:
        if prefer_contents:
            mode = QHeaderView.ResizeToContents
        else:
            mode = QHeaderView.Stretch
    except Exception:
        # Fallback
        mode = header.ResizeToContents if prefer_contents and hasattr(header, "ResizeToContents") else (
            header.Stretch if hasattr(header, "Stretch") else header.Interactive
        )
    try:
        header.setSectionResizeMode(col, mode)
    except Exception:
        try:
            header.setSectionResizeMode(col, header.Interactive)
        except Exception:
            pass


class MatchDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("地址清洗与多源匹配")
        self.resize(1080, 720)

        # 区域与目录状态
        self.region_province = ""
        self.region_city = ""
        self.region_county = ""
        self.base_folder = ""
        self.customer_folder = ""
        self.shp_folder = ""
        self.cache_folder = ""
        self._dirty_region = False
        self._region_tree: Dict[str, Dict[str, List[str]]] = self._load_region_tree()

        self._timers: Dict[str, QTimer] = {}

        self._build_ui()

    # ---------------- UI 构建 ----------------
    def _build_ui(self):
        """构建主UI：侧边栏导航 + 主内容区"""
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 左侧边栏
        self._build_sidebar(main_layout)
        
        # 右侧主内容区
        self._build_main_content(main_layout)
        
        # 模态对话框
        self._build_modals()
        
        # 应用样式
        self._apply_styles()
        
        # 初始化状态
        self._current_step = 2  # 默认显示Step2
        self._switch_step(2)

    def _build_sidebar(self, main_layout: QHBoxLayout):
        """构建左侧边栏导航"""
        sidebar = QWidget()
        sidebar.setFixedWidth(230)
        sidebar.setStyleSheet("""
            QWidget {
                background-color: #111827;
                color: #e5e7eb;
            }
        """)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_layout.setSpacing(0)

        # 标题
        header = QLabel("地址清洗 & 多源匹配插件")
        header.setStyleSheet("""
            QLabel {
                padding: 14px;
                border-bottom: 1px solid #1f2937;
                font-size: 14px;
                font-weight: 600;
            }
        """)
        sidebar_layout.addWidget(header)

        # 步骤列表
        self.step_list = QListWidget()
        self.step_list.setStyleSheet("""
            QListWidget {
                border: none;
                background-color: transparent;
                color: #e5e7eb;
                font-size: 13px;
            }
            QListWidget::item {
                padding: 8px 14px;
                border-left: 3px solid transparent;
            }
            QListWidget::item:hover {
                background-color: #111827;
            }
            QListWidget::item:selected {
                background-color: #1f2937;
                border-left-color: #2563eb;
                color: #f9fafb;
            }
        """)
        steps = [
            ("①", "Step1 文件导入"),
            ("②", "Step2 字段映射与清洗"),
            ("③", "Step3 标准化解析 & 关联"),
            ("④", "Step4 匹配任务管理"),
            ("⑤", "Step5 导出 & 日志"),
        ]
        for icon, text in steps:
            item = QListWidgetItem(f"{icon} {text}")
            self.step_list.addItem(item)
        self.step_list.itemClicked.connect(self._on_step_clicked)
        sidebar_layout.addWidget(self.step_list)

        # 底部提示
        footer = QLabel("工作台模式：任意步骤可单独执行，支持增量数据多次处理。")
        footer.setStyleSheet("""
            QLabel {
                padding: 10px 14px;
                border-top: 1px solid #1f2937;
                font-size: 11px;
                color: #9ca3af;
            }
        """)
        footer.setWordWrap(True)
        sidebar_layout.addWidget(footer)

        main_layout.addWidget(sidebar)

    def _build_main_content(self, main_layout: QHBoxLayout):
        """构建右侧主内容区"""
        main_widget = QWidget()
        main_widget.setStyleSheet("background-color: #f3f4f6;")
        main_content_layout = QVBoxLayout(main_widget)
        main_content_layout.setContentsMargins(0, 0, 0, 0)
        main_content_layout.setSpacing(0)

        # 标题栏
        header_widget = QWidget()
        header_widget.setStyleSheet("""
            QWidget {
                background-color: #f9fafb;
                border-bottom: 1px solid #d1d5db;
                padding: 10px 16px;
            }
        """)
        header_layout = QVBoxLayout(header_widget)
        header_layout.setContentsMargins(10, 10, 10, 10)

        self.header_title = QLabel("Step2 字段映射与清洗")
        self.header_title.setStyleSheet("font-size: 14px; font-weight: 600;")
        header_layout.addWidget(self.header_title)

        self.header_subtitle = QLabel("为每个文件配置多个字段组合，一次性批量清洗。")
        self.header_subtitle.setStyleSheet("font-size: 12px; color: #6b7280;")
        header_layout.addWidget(self.header_subtitle)

        header_bottom = QHBoxLayout()
        header_bottom.addStretch()
        badge1 = QLabel("当前项目：Demo")
        badge1.setStyleSheet("""
            QLabel {
                background-color: #e5e7eb;
                border-radius: 3px;
                padding: 1px 4px;
                font-size: 11px;
            }
        """)
        badge2 = QLabel("模式：QGIS 插件原型")
        badge2.setStyleSheet("""
            QLabel {
                background-color: #e5e7eb;
                border-radius: 3px;
                padding: 1px 4px;
                font-size: 11px;
            }
        """)
        header_bottom.addWidget(badge1)
        header_bottom.addWidget(badge2)
        header_layout.addLayout(header_bottom)

        main_content_layout.addWidget(header_widget)

        # 内容滚动区
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("border: none; background-color: #f3f4f6;")
        
        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(12, 12, 12, 12)
        self.content_layout.setSpacing(12)

        # 创建所有步骤的内容（初始隐藏）
        self.step_widgets = {}
        for i in range(1, 6):
            widget = self._build_step(i)
            self.step_widgets[i] = widget
            self.content_layout.addWidget(widget)
            widget.setVisible(False)

        scroll.setWidget(self.content_widget)
        main_content_layout.addWidget(scroll)

        main_layout.addWidget(main_widget, 1)

    def _build_modals(self):
        """构建模态对话框"""
        # 过滤条件对话框
        self.filter_modal = QDialog(self)
        self.filter_modal.setWindowTitle("目标表过滤条件")
        self.filter_modal.setModal(True)
        self.filter_modal.resize(520, 400)
        filter_layout = QVBoxLayout(self.filter_modal)
        filter_layout.addWidget(QLabel("（过滤条件配置对话框）"))
        filter_layout.addStretch()
        btn_close = QPushButton("关闭")
        btn_close.clicked.connect(self.filter_modal.close)
        filter_layout.addWidget(btn_close)

        # 字段匹配对对话框
        self.match_modal = QDialog(self)
        self.match_modal.setWindowTitle("字段匹配对配置")
        self.match_modal.setModal(True)
        self.match_modal.resize(520, 400)
        match_layout = QVBoxLayout(self.match_modal)
        match_layout.addWidget(QLabel("（字段匹配对配置对话框）"))
        match_layout.addStretch()
        btn_close2 = QPushButton("关闭")
        btn_close2.clicked.connect(self.match_modal.close)
        match_layout.addWidget(btn_close2)

    def _apply_styles(self):
        """应用样式"""
        # 样式已在各个组件中通过setStyleSheet设置
        pass

    def _switch_step(self, step_num: int):
        """切换步骤"""
        self._current_step = step_num
        # 隐藏所有步骤
        for i, widget in self.step_widgets.items():
            widget.setVisible(i == step_num)
        
        # 更新标题
        step_meta = {
            1: ("Step1 文件导入", "导入多源文件，管理参与任务的表。"),
            2: ("Step2 字段映射与清洗", "为每个文件配置多个字段组合，一次性批量清洗。"),
            3: ("Step3 标准化解析 & 关联", "调用阿里云解析，并展示智能字段关联关系。"),
            4: ("Step4 匹配任务管理", "多源表任务组：一个源表 → 多目标表，带目标优先级。"),
            5: ("Step5 导出 & 日志", "按类型导出所有结果，并集中查看日志。"),
        }
        if step_num in step_meta:
            title, subtitle = step_meta[step_num]
            self.header_title.setText(title)
            self.header_subtitle.setText(subtitle)
        
        # 更新侧边栏选中状态
        for i in range(self.step_list.count()):
            item = self.step_list.item(i)
            if i + 1 == step_num:
                item.setSelected(True)
            else:
                item.setSelected(False)

    def _on_step_clicked(self, item: QListWidgetItem):
        """步骤点击事件"""
        index = self.step_list.row(item)
        self._switch_step(index + 1)

    def _build_step(self, step_num: int) -> QWidget:
        """构建指定步骤的内容"""
        if step_num == 1:
            return self._build_step1()
        elif step_num == 2:
            return self._build_step2()
        elif step_num == 3:
            return self._build_step3()
        elif step_num == 4:
            return self._build_step4()
        elif step_num == 5:
            return self._build_step5()
        return QWidget()

    # -------- Step1 --------
    def _build_step1(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(6, 6, 6, 6)
        v.addWidget(self._card_global_scope())
        v.addWidget(self._card_data_sources())
        v.addWidget(self._card_shp_helper())
        v.addStretch()
        return w

    def _card_global_scope(self) -> QGroupBox:
        box = QGroupBox("数据范围与目录（全局）")

        # 折叠按钮
        btn_toggle = QPushButton("折叠")
        btn_toggle.setCheckable(True)
        btn_toggle.setChecked(True)

        # 内容布局
        content_layout = QVBoxLayout()
        row = QHBoxLayout()
        row.addWidget(QLabel("省"))
        self.combo_prov = QComboBox()
        row.addWidget(self.combo_prov)
        row.addWidget(QLabel("市"))
        self.combo_city = QComboBox()
        row.addWidget(self.combo_city)
        row.addWidget(QLabel("县/区"))
        self.combo_county = QComboBox()
        row.addWidget(self.combo_county)
        row.addWidget(QLabel("根目录"))
        self.edit_base = QLineEdit()
        row.addWidget(self.edit_base)
        btn_choose = QPushButton("选择根目录")
        row.addWidget(btn_choose)
        content_layout.addLayout(row)

        content_layout.addWidget(QLabel("客户数据目录（自动生成）："))
        self.label_customer = QLineEdit()
        self.label_customer.setReadOnly(True)
        content_layout.addWidget(self.label_customer)
        content_layout.addWidget(QLabel("SHP 数据目录（自动生成）："))
        self.label_shp = QLineEdit()
        self.label_shp.setReadOnly(True)
        content_layout.addWidget(self.label_shp)
        content_layout.addWidget(QLabel("数据缓存目录（自动生成）："))
        self.label_cache = QLineEdit()
        self.label_cache.setReadOnly(True)
        content_layout.addWidget(self.label_cache)

        row2 = QHBoxLayout()
        self.btn_confirm_dirs = QPushButton("确认并生成目录")
        row2.addWidget(self.btn_confirm_dirs)
        row2.addStretch()
        content_layout.addLayout(row2)
        content_layout.addWidget(QLabel("提示：省/市/根目录必选；县/区可为空。确认后会在根目录下生成客户、SHP、缓存目录（缓存目录名：省市cache）。"))

        self._global_content = QWidget()
        self._global_content.setLayout(content_layout)

        outer = QVBoxLayout(box)
        header = QHBoxLayout()
        header.addWidget(QLabel("全局数据范围与目录"))
        header.addStretch()
        header.addWidget(btn_toggle)
        outer.addLayout(header)
        outer.addWidget(self._global_content)

        # 信号
        btn_toggle.toggled.connect(self._on_global_toggle)
        self.combo_prov.currentTextChanged.connect(self._on_province_changed)
        self.combo_city.currentTextChanged.connect(self._on_city_changed)
        self.combo_county.currentTextChanged.connect(self._on_county_changed)
        self.edit_base.textChanged.connect(self._on_base_changed)
        btn_choose.clicked.connect(self._on_choose_base)
        self.btn_confirm_dirs.clicked.connect(self._confirm_dirs)

        self._init_regions()
        self._refresh_paths()
        self._refresh_confirm_state()
        return box

    def _card_data_sources(self) -> QGroupBox:
        box = QGroupBox("数据源文件列表")
        v = QVBoxLayout(box)
        btn_row = QHBoxLayout()
        btn_add = QPushButton("添加文件")
        btn_del = QPushButton("移除选中")
        btn_ref = QPushButton("刷新")
        btn_row.addWidget(btn_add)
        btn_row.addWidget(btn_del)
        btn_row.addWidget(btn_ref)
        btn_row.addStretch()
        v.addLayout(btn_row)

        table = QTableWidget(4, 6)
        table.setHorizontalHeaderLabels(["选择", "文件名", "来源类型", "参与任务", "字段组合数", "清洗状态"])
        _safe_select_rows(table)
        _safe_no_edit(table)
        header = table.horizontalHeader()
        for i in range(6):
            _set_resize_mode(header, i, prefer_contents=(i in (0, 3)))
        rows = [
            ["√", "客户采集数据_2025Q1.csv", "客户采集数据", "√", "2 个组合", "已清洗"],
            ["√", "小区地址库.xlsx", "其他", "√", "1 个组合", "未清洗"],
            ["√", "补录地址库_现场.csv", "客户采集数据", "√", "1 个组合", "未清洗"],
            ["√", "管网GIS_小区点位.shp", "GIS 数据", "√", "1 个组合", "已清洗"],
        ]
        for r, row in enumerate(rows):
            for c, val in enumerate(row):
                item = QTableWidgetItem(val)
                table.setItem(r, c, item)
        v.addWidget(table)
        v.addWidget(QLabel("这里只是“任务参与的文件池”，真正字段拼接和清洗逻辑在 Step2 按文件配置。"))
        return box

    def _card_shp_helper(self) -> QGroupBox:
        box = QGroupBox("辅助：shp → Excel 转换")
        v = QVBoxLayout(box)
        v.addWidget(QLabel("将 GIS 图层转表，方便后续统一以“表”的视角做字段操作。"))
        row = QHBoxLayout()
        row.addWidget(QLabel("选择 shp 文件或文件夹"))
        self.edit_shp_src = QLineEdit("D:/qgis/layers/")
        row.addWidget(self.edit_shp_src)
        btn_browse = QPushButton("浏览...")
        row.addWidget(btn_browse)
        v.addLayout(row)
        self.chk_auto_add = QCheckBox("转换完成后自动加入上方数据源列表")
        self.chk_auto_add.setChecked(True)
        v.addWidget(self.chk_auto_add)

        # 进度
        rowp = QHBoxLayout()
        self.bar_shp = QProgressBar()
        self.bar_shp.setValue(0)
        rowp.addWidget(self.bar_shp)
        self.lbl_shp = QLabel("空闲")
        rowp.addWidget(self.lbl_shp)
        btn_run = QPushButton("执行")
        btn_pause = QPushButton("暂停")
        btn_stop = QPushButton("终止")
        rowp.addWidget(btn_run)
        rowp.addWidget(btn_pause)
        rowp.addWidget(btn_stop)
        rowp.addStretch()
        v.addLayout(rowp)

        btn_run.clicked.connect(lambda: self._start_task("shp", self.bar_shp, self.lbl_shp, "批量 shp→Excel..."))
        btn_pause.clicked.connect(lambda: self._pause_task("shp", self.lbl_shp))
        btn_stop.clicked.connect(lambda: self._stop_task("shp", self.bar_shp, self.lbl_shp))
        return box

    # -------- Step2 --------
    def _build_step2(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(6, 6, 6, 6)
        v.addWidget(self._card_cfg_progress())
        v.addWidget(self._card_field_combos())
        v.addWidget(self._card_clean())
        v.addStretch()
        return w

    def _card_cfg_progress(self) -> QGroupBox:
        box = QGroupBox("参与任务文件配置进度")
        v = QVBoxLayout(box)
        table = QTableWidget(3, 5)
        table.setHorizontalHeaderLabels(["当前", "文件名", "字段组合数", "已配置", "清洗状态"])
        _safe_select_rows(table)
        _safe_no_edit(table)
        header = table.horizontalHeader()
        for i in range(5):
            _set_resize_mode(header, i, prefer_contents=(i == 0))
        rows = [
            ["○", "客户采集数据_2025Q1.csv", "2", "是", "已清洗"],
            ["○", "小区地址库.xlsx", "1", "是", "未清洗"],
            ["○", "补录地址库_现场.csv", "1", "部分", "未清洗"],
        ]
        for r, row in enumerate(rows):
            for c, val in enumerate(row):
                table.setItem(r, c, QTableWidgetItem(val))
        v.addWidget(table)
        return box

    def _card_field_combos(self) -> QGroupBox:
        box = QGroupBox("字段组合与字段顺序（当前文件）")
        v = QVBoxLayout(box)
        v.addWidget(QLabel("一个文件可以有多个组合；每个组合下的字段顺序定义拼接顺序。"))

        self.table_fields = QTableWidget(3, 4)
        self.table_fields.setHorizontalHeaderLabels(["顺序", "角色名称（备注）", "字段（当前文件列）", "操作"])
        _safe_select_rows(self.table_fields)
        _safe_no_edit(self.table_fields)
        header = self.table_fields.horizontalHeader()
        for i in range(4):
            _set_resize_mode(header, i, prefer_contents=(i in (0, 3)))
        rows = [
            ["1", "城市", "std_city / province", "上移/下移/删"],
            ["2", "小区名", "community_name / estate_name", "上移/下移/删"],
            ["3", "详细地址", "addr_detail / door_info", "上移/下移/删"],
        ]
        for r, row in enumerate(rows):
            for c, val in enumerate(row):
                self.table_fields.setItem(r, c, QTableWidgetItem(val))
        btn_add_field = QPushButton("+ 新增字段")
        v.addWidget(self.table_fields)
        v.addWidget(btn_add_field)
        btn_add_combo = QPushButton("+ 新增字段组合")
        v.addWidget(btn_add_combo)
        v.addWidget(QLabel("拼接顺序 = 行顺序；后端只拿字段名与顺序，角色名称只是备注。"))
        return box

    def _card_clean(self) -> QGroupBox:
        box = QGroupBox("批量执行清洗")
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
        btn_run.clicked.connect(lambda: self._start_task("clean", self.bar_clean, self.lbl_clean, "批量清洗..."))
        btn_pause.clicked.connect(lambda: self._pause_task("clean", self.lbl_clean))
        btn_stop.clicked.connect(lambda: self._stop_task("clean", self.bar_clean, self.lbl_clean))
        return box

    # -------- Step3 --------
    def _build_step3(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(6, 6, 6, 6)
        v.addWidget(self._card_key())
        v.addWidget(self._card_parse())
        v.addWidget(self._card_relations())
        v.addStretch()
        return w

    def _card_key(self) -> QGroupBox:
        box = QGroupBox("阿里云解析 Key 配置")
        v = QVBoxLayout(box)
        row = QHBoxLayout()
        row.addWidget(QLabel("AccessKey / Token"))
        self.edit_key = QLineEdit("****************")
        row.addWidget(self.edit_key)
        btn_test = QPushButton("测试连接")
        btn_save = QPushButton("保存")
        row.addWidget(btn_test)
        row.addWidget(btn_save)
        row.addStretch()
        v.addLayout(row)
        v.addWidget(QLabel("这里只保存凭证，解析策略你在后端写死即可。"))
        btn_test.clicked.connect(lambda: self._log("[Key] 测试连接（示意）"))
        btn_save.clicked.connect(lambda: self._log("[Key] 保存凭证（示意）"))
        return box

    def _card_parse(self) -> QGroupBox:
        box = QGroupBox("选择已清洗文件，执行标准化解析")
        v = QVBoxLayout(box)
        table = QTableWidget(3, 4)
        table.setHorizontalHeaderLabels(["选择", "文件名", "状态", "进度"])
        _safe_select_rows(table)
        _safe_no_edit(table)
        header = table.horizontalHeader()
        for i in range(4):
            _set_resize_mode(header, i, prefer_contents=(i == 0))
        files = [
            ("√", "客户采集数据_2025Q1_clean.csv", "未解析"),
            ("√", "小区地址库_clean.xlsx", "部分缓存"),
            ("", "补录地址库_clean.csv", "已解析"),
        ]
        self.parse_bars: List[QProgressBar] = []
        for r, row in enumerate(files):
            for c, val in enumerate(row):
                table.setItem(r, c, QTableWidgetItem(val))
            bar = QProgressBar()
            bar.setValue(0 if r < 2 else 100)
            self.parse_bars.append(bar)
            table.setCellWidget(r, 3, bar)
        v.addWidget(table)
        row = QHBoxLayout()
        btn_run = QPushButton("解析选中")
        btn_pause = QPushButton("全部暂停")
        btn_stop = QPushButton("全部终止")
        row.addWidget(btn_run)
        row.addWidget(btn_pause)
        row.addWidget(btn_stop)
        row.addStretch()
        v.addLayout(row)
        btn_run.clicked.connect(self._run_parse_demo)
        btn_pause.clicked.connect(lambda: self._pause_task("parse", None))
        btn_stop.clicked.connect(lambda: self._stop_task("parse", None, None))
        return box

    def _card_relations(self) -> QGroupBox:
        box = QGroupBox("智能关联关系识别（字段层级）")
        v = QVBoxLayout(box)
        btn_refresh = QPushButton("刷新关联关系")
        v.addWidget(btn_refresh)

        table = QTableWidget(5, 2)
        table.setHorizontalHeaderLabels(["文件", "字段"])
        _safe_select_rows(table)
        _safe_no_edit(table)
        header = table.horizontalHeader()
        for i in range(2):
            _set_resize_mode(header, i, prefer_contents=False)
        fields = [
            ("客户采集数据_2025Q1_std.csv", "std_full_addr"),
            ("客户采集数据_2025Q1_std.csv", "customer_name"),
            ("小区地址库_std.xlsx", "community_name"),
            ("GIS_小区点位_std.shp", "poi_name"),
            ("门牌库_市政_std.csv", "mp_full_addr"),
        ]
        for r, row in enumerate(fields):
            for c, val in enumerate(row):
                table.setItem(r, c, QTableWidgetItem(val))
        v.addWidget(table)

        self.graph_placeholder = QTextEdit("（示意）已刷新字段关联图 —— 实际实现时可用 Canvas/SVG 绘制力导图。")
        self.graph_placeholder.setReadOnly(True)
        self.graph_placeholder.setMinimumHeight(180)
        v.addWidget(self.graph_placeholder)

        # 关联度表
        rel_table = QTableWidget(3, 3)
        rel_table.setHorizontalHeaderLabels(["字段 A", "字段 B", "关联度"])
        _safe_select_rows(rel_table)
        _safe_no_edit(rel_table)
        _set_resize_mode(rel_table.horizontalHeader(), 0, prefer_contents=False)
        for i in range(1, 3):
            _set_resize_mode(rel_table.horizontalHeader(), i, prefer_contents=False)
        rels = [
            ("客户采集数据.std_full_addr", "门牌库_市政.mp_full_addr", "0.97"),
            ("客户采集数据.std_full_addr", "小区地址库.full_addr", "0.89"),
            ("补录地址库.community_name", "GIS_小区点位.poi_name", "0.82"),
        ]
        for r, row in enumerate(rels):
            for c, val in enumerate(row):
                rel_table.setItem(r, c, QTableWidgetItem(val))
        v.addWidget(rel_table)

        btn_refresh.clicked.connect(self._refresh_relations)
        return box

    # -------- Step4 --------
    def _build_step4(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(6, 6, 6, 6)
        v.addWidget(self._card_task_groups())
        v.addWidget(self._card_group_config())
        v.addStretch()
        return w

    def _card_task_groups(self) -> QGroupBox:
        box = QGroupBox("匹配任务组列表（多源表）")
        v = QVBoxLayout(box)
        table = QTableWidget(2, 7)
        table.setHorizontalHeaderLabels(["启用", "任务组名称", "源表", "目标表数量", "状态", "进度", "操作"])
        _safe_select_rows(table)
        _safe_no_edit(table)
        header = table.horizontalHeader()
        for i in range(7):
            _set_resize_mode(header, i, prefer_contents=(i in (0, 6)))

        self.group_bars: Dict[str, QProgressBar] = {}
        rows = [
            ("g1", "任务组1：客户地址 ↔ 门牌库 & 小区库", "客户采集数据_2025Q1_std.csv", "2", "未执行", 0),
            ("g2", "任务组2：补录地址 ↔ 小区库 & GIS 点位", "补录地址库_std.csv", "2", "未执行", 0),
        ]
        for r, row in enumerate(rows):
            gid, name, src, tgt_count, status, prog = row
            table.setItem(r, 0, QTableWidgetItem("√"))
            table.setItem(r, 1, QTableWidgetItem(name))
            table.setItem(r, 2, QTableWidgetItem(src))
            table.setItem(r, 3, QTableWidgetItem(tgt_count))
            table.setItem(r, 4, QTableWidgetItem(status))
            bar = QProgressBar()
            bar.setValue(prog)
            self.group_bars[gid] = bar
            table.setCellWidget(r, 5, bar)
            table.setItem(r, 6, QTableWidgetItem("执行/暂停/终止"))
        v.addWidget(table)
        btn_add = QPushButton("+ 新增任务组")
        v.addWidget(btn_add)
        return box

    def _card_group_config(self) -> QGroupBox:
        box = QGroupBox("当前任务组配置：任务组1（示例）")
        v = QVBoxLayout(box)
        # 源表过滤
        row = QHBoxLayout()
        row.addWidget(QLabel("源表（From，仅一个）"))
        self.combo_src_table = QComboBox()
        self.combo_src_table.addItems(
            ["客户采集数据_2025Q1_std.csv", "补录地址库_std.csv", "小区地址库_std.xlsx"]
        )
        row.addWidget(self.combo_src_table)
        row.addStretch()
        v.addLayout(row)

        v.addWidget(QLabel("源表过滤条件（示例）"))
        src_table = QTableWidget(1, 5)
        src_table.setHorizontalHeaderLabels(["字段", "运算符", "值", "逻辑", "操作"])
        _safe_select_rows(src_table)
        _safe_no_edit(src_table)
        src_header = src_table.horizontalHeader()
        for i in range(5):
            _set_resize_mode(src_header, i, prefer_contents=False)
        sample = ["cust_district", "=", "鼓楼区", "AND", "删"]
        for c, val in enumerate(sample):
            src_table.setItem(0, c, QTableWidgetItem(val))
        v.addWidget(src_table)
        v.addWidget(QPushButton("+ 新增条件"))

        # 目标表列表
        v.addWidget(QLabel("目标表列表（优先级从上到下）"))
        tgt_table = QTableWidget(2, 6)
        tgt_table.setHorizontalHeaderLabels(["序", "目标表", "过滤条件", "字段匹配对", "匹配方式说明", "操作"])
        _safe_select_rows(tgt_table)
        _safe_no_edit(tgt_table)
        tgt_header = tgt_table.horizontalHeader()
        for i in range(6):
            _set_resize_mode(tgt_header, i, prefer_contents=False)
        tgt_rows = [
            ["1", "门牌库_市政_std.csv", "配置过滤条件", "配置字段匹配对", "std_full_addr ↔ mp_full_addr", "上/下/删"],
            ["2", "小区地址库_std.xlsx", "配置过滤条件", "配置字段匹配对", "community_name ↔ community_name", "上/下/删"],
        ]
        for r, row in enumerate(tgt_rows):
            for c, val in enumerate(row):
                tgt_table.setItem(r, c, QTableWidgetItem(val))
        v.addWidget(tgt_table)
        v.addWidget(QPushButton("+ 新增目标表"))
        return box

    # -------- Step5 --------
    def _build_step5(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(6, 6, 6, 6)
        v.addWidget(self._card_export())
        v.addWidget(self._card_log())
        v.addStretch()
        return w

    def _card_export(self) -> QGroupBox:
        box = QGroupBox("结果导出")
        v = QVBoxLayout(box)
        row = QHBoxLayout()
        row.addWidget(QCheckBox("清洗结果（*_clean.*）"))
        row.addWidget(QCheckBox("标准化结果（*_std.*）"))
        row.addWidget(QCheckBox("匹配结果"))
        row.addWidget(QCheckBox("未匹配数据"))
        row.addWidget(QCheckBox("字段关联关系"))
        v.addLayout(row)
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("输出根目录"))
        self.edit_export = QLineEdit("D:/qgis_addr_output/run_demo/")
        row2.addWidget(self.edit_export)
        row2.addWidget(QPushButton("浏览..."))
        v.addLayout(row2)

        row3 = QHBoxLayout()
        self.bar_export = QProgressBar()
        self.lbl_export = QLabel("空闲")
        row3.addWidget(self.bar_export)
        row3.addWidget(self.lbl_export)
        btn_run = QPushButton("执行导出")
        btn_pause = QPushButton("暂停")
        btn_stop = QPushButton("终止")
        row3.addWidget(btn_run)
        row3.addWidget(btn_pause)
        row3.addWidget(btn_stop)
        row3.addStretch()
        v.addLayout(row3)
        btn_run.clicked.connect(lambda: self._start_task("export", self.bar_export, self.lbl_export, "导出结果文件..."))
        btn_pause.clicked.connect(lambda: self._pause_task("export", self.lbl_export))
        btn_stop.clicked.connect(lambda: self._stop_task("export", self.bar_export, self.lbl_export))
        return box

    def _card_log(self) -> QGroupBox:
        box = QGroupBox("日志工作台")
        v = QVBoxLayout(box)
        self.log_panel = QTextEdit()
        self.log_panel.setReadOnly(True)
        self.log_panel.setMinimumHeight(160)
        v.addWidget(self.log_panel)
        self._log("[INIT] 界面加载完成，待用户配置。")
        return box

    # ---------------- 逻辑 ----------------
    def _load_region_tree(self) -> Dict[str, Dict[str, List[str]]]:
        base = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "regions")
        prov_path = os.path.join(base, "provinces.json")
        city_path = os.path.join(base, "cities.json")
        area_path = os.path.join(base, "areas.json")
        tree: Dict[str, Dict[str, List[str]]] = {}
        try:
            with open(prov_path, "r", encoding="utf-8") as f:
                provs = json.load(f)
            with open(city_path, "r", encoding="utf-8") as f:
                cities = json.load(f)
            with open(area_path, "r", encoding="utf-8") as f:
                areas = json.load(f)
            for prov in provs:
                pname = prov.get("name", "")
                tree[pname] = {}
            for c in cities:
                pname = c.get("province", "")
                cname = c.get("name", "")
                tree.setdefault(pname, {})[cname] = []
            for a in areas:
                pname = a.get("province", "")
                cname = a.get("city", "")
                aname = a.get("name", "")
                tree.setdefault(pname, {}).setdefault(cname, []).append(aname)
        except Exception:
            tree = {"江苏省": {"南京市": ["鼓楼区", "玄武区"], "苏州市": ["姑苏区"]}}
        return tree

    def _init_regions(self):
        self.combo_prov.clear()
        self.combo_city.clear()
        self.combo_county.clear()
        self.combo_prov.addItem("")
        for p in sorted(self._region_tree.keys()):
            self.combo_prov.addItem(p)

    def _on_global_toggle(self, checked: bool):
        self._global_content.setVisible(checked)

    def _on_province_changed(self, text: str):
        self.region_province = text.strip()
        self.region_city = ""
        self.region_county = ""
        self.combo_city.clear()
        self.combo_city.addItem("")
        for c in sorted(self._region_tree.get(self.region_province, {}).keys()):
            self.combo_city.addItem(c)
        self.combo_county.clear()
        self.combo_county.addItem("")
        self._dirty_region = True
        self._refresh_paths()
        self._refresh_confirm_state()

    def _on_city_changed(self, text: str):
        self.region_city = text.strip()
        self.region_county = ""
        self.combo_county.clear()
        self.combo_county.addItem("")
        for a in sorted(self._region_tree.get(self.region_province, {}).get(self.region_city, [])):
            self.combo_county.addItem(a)
        self._dirty_region = True
        self._refresh_paths()
        self._refresh_confirm_state()

    def _on_county_changed(self, text: str):
        self.region_county = text.strip()
        self._dirty_region = True
        self._refresh_paths()
        self._refresh_confirm_state()

    def _on_base_changed(self, text: str):
        self.base_folder = text.strip()
        self._dirty_region = True
        self._refresh_paths()
        self._refresh_confirm_state()

    def _on_choose_base(self):
        path = QFileDialog.getExistingDirectory(self, "选择根目录", "")
        if path:
            self.edit_base.setText(path)

    def _refresh_paths(self):
        if not (self.region_province and self.region_city and self.base_folder):
            self.customer_folder = ""
            self.shp_folder = ""
            self.cache_folder = ""
        else:
            base = self.base_folder.rstrip("\\/")
            suffix = f"{self.region_province}{self.region_city}{self.region_county}".strip()
            self.customer_folder = os.path.join(base, f"{suffix}客户数据")
            self.shp_folder = os.path.join(base, f"{suffix}SHP数据")
            cache_suffix = f"{self.region_province}{self.region_city}".strip()
            self.cache_folder = os.path.join(base, f"{cache_suffix}cache")
        self.label_customer.setText(self.customer_folder)
        self.label_shp.setText(self.shp_folder)
        self.label_cache.setText(self.cache_folder)

    def _region_key(self) -> str:
        if not (self.region_province and self.region_city):
            return ""
        return f"{self.region_province}-{self.region_city}-{self.region_county}"

    def _cache_file_path(self) -> str:
        if not self.cache_folder:
            return ""
        return os.path.join(self.cache_folder, "region_cache.json")

    def _save_cache(self):
        key = self._region_key()
        if not key:
            return
        path = self._cache_file_path()
        if not path:
            return
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            data = {}
            if os.path.isfile(path):
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            data[key] = {"base": self.base_folder}
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self._log(f"[缓存] 写入失败: {e}")

    def _confirm_dirs(self):
        if not (self.region_province and self.region_city):
            self._log("[目录] 请先选择省与市。")
            return
        if not self.base_folder:
            self._log("[目录] 请先选择根目录。")
            return
        if not self.customer_folder:
            self._refresh_paths()
        try:
            for p in [self.customer_folder, self.shp_folder, self.cache_folder]:
                os.makedirs(p, exist_ok=True)
            self._log("[目录] 已生成/复用目录：\n" + "\n".join([self.customer_folder, self.shp_folder, self.cache_folder]))
            self._save_cache()
            self._dirty_region = False
            self._refresh_confirm_state()
        except Exception as e:
            self._log(f"[目录] 创建失败: {e}")

    def _refresh_confirm_state(self):
        allow = bool(self.region_province and self.region_city and self.base_folder and self._dirty_region)
        self.btn_confirm_dirs.setEnabled(allow)

    # ---------------- 任务进度模拟 ----------------
    def _start_task(self, key: str, bar: QProgressBar, lbl: QLabel, text: str):
        if key in self._timers:
            return
        lbl.setText(f"{text} 0%")
        timer = QTimer(self)
        timer.setInterval(350)

        def tick():
            val = bar.value() + 7
            if val >= 100:
                val = 100
                timer.stop()
                self._timers.pop(key, None)
                lbl.setText(f"{text} 完成 (100%)")
                self._log(f"[任务] {text} 完成（示意）。")
            else:
                lbl.setText(f"{text} {val}%")
            bar.setValue(val)

        timer.timeout.connect(tick)
        self._timers[key] = timer
        timer.start()
        self._log(f"[任务] {text}")

    def _pause_task(self, key: str, lbl: QLabel | None):
        t = self._timers.get(key)
        if t:
            t.stop()
            if lbl:
                lbl.setText("暂停")
            self._log(f"[任务] {key} 暂停（示意）。")

    def _stop_task(self, key: str, bar: QProgressBar | None, lbl: QLabel | None):
        t = self._timers.pop(key, None)
        if t:
            t.stop()
        if bar:
            bar.setValue(0)
        if lbl:
            lbl.setText("空闲")
        self._log(f"[任务] {key} 终止并重置（示意）。")

    def _run_parse_demo(self):
        for idx, bar in enumerate(self.parse_bars):
            self._start_task(f"parse{idx}", bar, QLabel(), f"解析文件{idx+1}...")

    def _refresh_relations(self):
        self.graph_placeholder.setPlainText("（示意）已刷新字段关联图 —— 实际实现时可用 Canvas/SVG 绘制力导图。")
        self._log("[关联] 刷新字段关联关系（示意）。")

    # ---------------- 日志 ----------------
    def _log(self, msg: str):
        if hasattr(self, "log_panel"):
            self.log_panel.append(msg)


if __name__ == "__main__":
    # 仅便于独立调试
    from qgis.PyQt.QtWidgets import QApplication
    import sys

    app = QApplication(sys.argv)
    dlg = MatchDialog()
    dlg.show()
    sys.exit(app.exec_())
