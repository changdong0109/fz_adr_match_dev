"""
Step3: 标准化解析与关联Widget
包含：Key配置、解析任务、关联关系识别
"""
import os
import json
from typing import Any, Callable, Dict, List, Optional
from qgis.PyQt.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel, QLineEdit,
    QPushButton, QTableWidget, QTableWidgetItem, QCheckBox,
    QProgressBar, QTextEdit, QMessageBox, QListWidget, QListWidgetItem,
    QGraphicsItem, QGraphicsEllipseItem, QGraphicsPathItem, QGraphicsView, QGraphicsScene
)
from qgis.PyQt.QtGui import QColor, QPen, QBrush, QPainterPath, QFont
from qgis.PyQt.QtCore import Qt, QSettings
from ..utils import safe_select_rows, safe_no_edit, set_resize_mode
from ..widgets.base_step_widget import BaseStepWidget
from ..widgets.no_wheel_combo_box import NoWheelComboBox
from ..collapsible_section import CollapsibleSection


class ClickableNodeItem(QGraphicsEllipseItem):
    """可点击的节点图形项"""
    
    def __init__(self, x, y, w, h, node_id: str, callback: Callable[[str], None], parent=None):
        super().__init__(x, y, w, h, parent)
        self.node_id = node_id
        self.callback = callback
        self.setAcceptHoverEvents(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self._original_pen = None
        self._original_brush = None
        # 设置 tooltip 显示完整的 文件名.字段名
        self.setToolTip(node_id)
    
    def hoverEnterEvent(self, event):
        """鼠标进入时高亮"""
        self._original_pen = self.pen()
        self._original_brush = self.brush()
        highlight_pen = QPen(QColor("#1d4ed8"), 3)
        self.setPen(highlight_pen)
        super().hoverEnterEvent(event)
    
    def hoverLeaveEvent(self, event):
        """鼠标离开时恢复"""
        if self._original_pen:
            self.setPen(self._original_pen)
        super().hoverLeaveEvent(event)
    
    def mousePressEvent(self, event):
        """点击节点时触发回调（延迟执行避免对象被删除）"""
        from qgis.PyQt.QtCore import QTimer
        if self.callback:
            node_id = self.node_id
            callback = self.callback
            # 延迟执行，避免在事件处理中删除自己
            QTimer.singleShot(0, lambda: callback(node_id))
        event.accept()


class ClickableEdgeItem(QGraphicsPathItem):
    """可点击的边图形项"""
    
    def __init__(self, path: QPainterPath, relation: Dict, callback: Callable[[Dict], None], parent=None):
        super().__init__(path, parent)
        self.relation = relation
        self.callback = callback
        self.setAcceptHoverEvents(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._original_pen = None
    
    def hoverEnterEvent(self, event):
        """鼠标进入时高亮"""
        self._original_pen = self.pen()
        highlight_pen = QPen(QColor("#1d4ed8"), self._original_pen.width() + 2)
        self.setPen(highlight_pen)
        super().hoverEnterEvent(event)
    
    def hoverLeaveEvent(self, event):
        """鼠标离开时恢复"""
        if self._original_pen:
            self.setPen(self._original_pen)
        super().hoverLeaveEvent(event)
    
    def mousePressEvent(self, event):
        """点击边时触发回调（延迟执行避免对象被删除）"""
        from qgis.PyQt.QtCore import QTimer
        if self.callback:
            relation = self.relation.copy()  # 复制数据
            callback = self.callback
            # 延迟执行，避免在事件处理中删除自己
            QTimer.singleShot(0, lambda: callback(relation))
        event.accept()


class Step3Widget(BaseStepWidget):
    """Step3: 标准化解析与关联"""
    
    # QSettings 键名
    SETTINGS_KEY_ACCESS_KEY_ID = "fz_adr_match/ali_access_key_id"
    SETTINGS_KEY_ACCESS_KEY_SECRET = "fz_adr_match/ali_access_key_secret"
    SETTINGS_KEY_APP_KEY = "fz_adr_match/ali_app_key"
    
    def __init__(self, parent=None, log_callback: Optional[Callable[[str, str], None]] = None, 
                 task_manager=None):
        self.parse_file_list: Optional[QListWidget] = None
        self.parse_selected_files: Dict[str, bool] = {}
        self._is_running = False  # 防止重复执行
        super().__init__(parent, log_callback, task_manager)
        self._build_ui()
        self._set_expanding_size_policy()
        
        # 延迟加载文件列表（等待 UI 完全初始化）
        from qgis.PyQt.QtCore import QTimer
        QTimer.singleShot(100, self._refresh_parse_file_list)
    
    def showEvent(self, event):
        """当 Widget 显示时刷新文件列表"""
        super().showEvent(event)
        self._refresh_parse_file_list()
    
    def _set_expanding_size_policy(self):
        """设置尺寸策略为Expanding"""
        from qgis.PyQt.QtWidgets import QSizePolicy
        try:
            if hasattr(QSizePolicy, 'Policy') and hasattr(QSizePolicy.Policy, 'Expanding'):
                expanding = QSizePolicy.Policy.Expanding
            elif hasattr(QSizePolicy, 'Expanding'):
                expanding = QSizePolicy.Expanding
            else:
                expanding = 7
            self.setSizePolicy(expanding, expanding)
        except (AttributeError, TypeError):
            self.setSizePolicy(7, 7)
    
    def _set_section_size_policy(self, section):
        """设置CollapsibleSection的尺寸策略"""
        from qgis.PyQt.QtWidgets import QSizePolicy
        try:
            if hasattr(QSizePolicy, 'Policy'):
                expanding = QSizePolicy.Policy.Expanding
                preferred = QSizePolicy.Policy.Preferred
            else:
                expanding = 7
                preferred = 1
            section.setSizePolicy(expanding, preferred)
        except (AttributeError, TypeError):
            section.setSizePolicy(7, 1)
    
    def _build_ui(self):
        """构建UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 6, 0, 6)
        layout.setSpacing(12)
        
        layout.addWidget(self._card_key())
        layout.addWidget(self._card_parse())
        layout.addWidget(self._card_relation())
        layout.addStretch(1)
    
    def _card_key(self) -> QWidget:
        """阿里云解析 Key 配置"""
        section = CollapsibleSection("阿里云解析 Key 配置", expanded=False)
        self._set_section_size_policy(section)
        
        content_widget = QWidget()
        v = QVBoxLayout(content_widget)
        v.setContentsMargins(16, 12, 16, 12)
        v.setSpacing(10)
        
        # AccessKey ID
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("AccessKey ID:"))
        self.edit_access_key_id = QLineEdit()
        self.edit_access_key_id.setObjectName("step3_key_input")
        self.edit_access_key_id.setPlaceholderText("请输入 AccessKey ID")
        self.edit_access_key_id.setMinimumWidth(280)
        row1.addWidget(self.edit_access_key_id)
        row1.addStretch()
        v.addLayout(row1)
        
        # AccessKey Secret
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("AccessKey Secret:"))
        self.edit_access_key_secret = QLineEdit()
        self.edit_access_key_secret.setObjectName("step3_key_input")
        self.edit_access_key_secret.setPlaceholderText("请输入 AccessKey Secret")
        self.edit_access_key_secret.setEchoMode(QLineEdit.EchoMode.Password)
        self.edit_access_key_secret.setMinimumWidth(280)
        row2.addWidget(self.edit_access_key_secret)
        row2.addStretch()
        v.addLayout(row2)
        
        # App Key
        row3 = QHBoxLayout()
        row3.addWidget(QLabel("App Key:"))
        self.edit_app_key = QLineEdit()
        self.edit_app_key.setObjectName("step3_key_input")
        self.edit_app_key.setPlaceholderText("请输入 App Key")
        self.edit_app_key.setMinimumWidth(280)
        row3.addWidget(self.edit_app_key)
        row3.addStretch()
        v.addLayout(row3)
        
        # 按钮行
        btn_row = QHBoxLayout()
        btn_test = QPushButton("测试连接")
        btn_test.setObjectName("step3_btn_test")
        btn_save = QPushButton("保存配置")
        btn_save.setObjectName("step3_btn_save")
        btn_row.addWidget(btn_test)
        btn_row.addWidget(btn_save)
        btn_row.addStretch()
        v.addLayout(btn_row)
        
        # 提示文字
        tip = QLabel("提示：配置会保存到本地，解析时自动使用。API 调用结果会缓存，避免重复计费。")
        tip.setObjectName("step3_tip_label")
        v.addWidget(tip)
        
        # 加载已保存的配置
        self._load_key_config()
        
        # 绑定事件
        btn_test.clicked.connect(self._on_test_connection)
        btn_save.clicked.connect(self._on_save_key_config)
        
        section.add_widget(content_widget)
        return section
    
    def _card_parse(self) -> QWidget:
        """选择已清洗文件，执行标准化解析"""
        section = CollapsibleSection("标准化解析任务", expanded=True)
        self._set_section_size_policy(section)
        
        content_widget = QWidget()
        v = QVBoxLayout(content_widget)
        v.setContentsMargins(16, 12, 16, 12)
        v.setSpacing(12)
        
        # 说明文字
        tip = QLabel("勾选要解析的文件，解析结果会缓存到项目目录，命中缓存的不再调用 API。")
        tip.setWordWrap(True)
        v.addWidget(tip)
        
        # 文件列表
        self.parse_file_list = QListWidget()
        self.parse_file_list.setObjectName("step3_parse_file_list")
        self.parse_file_list.setMinimumHeight(180)
        self.parse_file_list.itemChanged.connect(self._on_parse_file_item_changed)
        v.addWidget(self.parse_file_list)
        
        # 测试数量输入（临时入口，用于测试）
        test_row = QHBoxLayout()
        test_row.addWidget(QLabel("测试数量:"))
        self.edit_test_limit = QLineEdit()
        self.edit_test_limit.setText("5")  # 默认测试 5 条
        self.edit_test_limit.setPlaceholderText("留空表示全部，填数字限制条数")
        self.edit_test_limit.setMaximumWidth(200)
        test_row.addWidget(self.edit_test_limit)
        test_row.addWidget(QLabel("（用于测试，正式使用时留空）"))
        test_row.addStretch()
        v.addLayout(test_row)
        
        # 进度条
        progress_row = QHBoxLayout()
        progress_row.addWidget(QLabel("解析进度:"))
        self.parse_progress = QProgressBar()
        self.parse_progress.setObjectName("step3_parse_progress")
        self.parse_progress.setValue(0)
        self.parse_progress.setMinimumHeight(20)
        progress_row.addWidget(self.parse_progress)
        v.addLayout(progress_row)
        
        # 状态标签
        self.lbl_parse_status = QLabel("就绪")
        v.addWidget(self.lbl_parse_status)
        
        # 操作按钮行
        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)
        
        btn_refresh = QPushButton("刷新文件列表")
        btn_refresh.setObjectName("step3_btn_refresh")
        btn_refresh.clicked.connect(self._refresh_parse_file_list)
        btn_row.addWidget(btn_refresh)
        
        btn_select_all = QPushButton("全选")
        btn_select_all.clicked.connect(self._select_all_parse_files)
        btn_row.addWidget(btn_select_all)
        
        btn_deselect = QPushButton("取消选择")
        btn_deselect.clicked.connect(self._deselect_all_parse_files)
        btn_row.addWidget(btn_deselect)
        
        btn_row.addStretch()
        
        btn_clear = QPushButton("清除数据")
        btn_clear.setObjectName("step3_btn_clear")
        btn_clear.clicked.connect(self._show_clear_dialog)
        btn_row.addWidget(btn_clear)
        
        btn_run = QPushButton("开始解析")
        btn_run.setObjectName("step3_btn_run")
        btn_run.clicked.connect(self._run_parse_task)
        btn_row.addWidget(btn_run)
        
        v.addLayout(btn_row)
        
        section.add_widget(content_widget)
        return section
    
    def _card_relation(self) -> QWidget:
        """智能关联关系识别（字段层级）- 使用 pandas + NetworkX 分析"""
        from qgis.PyQt.QtWidgets import (
            QTableWidget, QTableWidgetItem, QHeaderView, QSplitter, 
            QGraphicsView, QGraphicsScene, QTextEdit
        )
        from qgis.PyQt.QtGui import QPen, QBrush, QColor, QFont
        
        section = CollapsibleSection("智能关联关系识别", expanded=False)
        self._set_section_size_policy(section)
        
        # 保存分析结果
        self._relation_result = None
        
        content_widget = QWidget()
        v = QVBoxLayout(content_widget)
        v.setContentsMargins(16, 12, 16, 12)
        v.setSpacing(12)
        
        # 说明文字
        tip = QLabel("基于字段值重叠自动发现跨文件的字段关联关系，使用 NetworkX 图分析发现数据洞察。")
        tip.setWordWrap(True)
        tip.setObjectName("step3_relation_tip")
        v.addWidget(tip)
        
        # 刷新按钮行
        btn_row = QHBoxLayout()
        btn_refresh_relation = QPushButton("分析关联关系")
        btn_refresh_relation.setObjectName("step3_btn_refresh_relation")
        btn_refresh_relation.clicked.connect(self._analyze_relations)
        btn_row.addWidget(btn_refresh_relation)
        
        # 状态标签
        self.lbl_relation_status = QLabel("点击按钮开始分析")
        self.lbl_relation_status.setObjectName("step3_relation_status")
        btn_row.addWidget(self.lbl_relation_status)
        
        # 进度条
        self.progress_relation = QProgressBar()
        self.progress_relation.setObjectName("step3_relation_progress")
        self.progress_relation.setMaximumWidth(150)
        self.progress_relation.setVisible(False)
        btn_row.addWidget(self.progress_relation)
        
        btn_row.addStretch()
        v.addLayout(btn_row)
        
        # 分割器：左侧字段列表，右侧关联图
        splitter = QSplitter()
        splitter.setObjectName("step3_relation_splitter")
        
        # 左侧：字段列表表格
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(4)
        
        left_label = QLabel("字段列表")
        left_label.setObjectName("step3_relation_label")
        left_layout.addWidget(left_label)
        
        self.tbl_field_list = QTableWidget()
        self.tbl_field_list.setObjectName("step3_field_list_table")
        self.tbl_field_list.setColumnCount(2)
        self.tbl_field_list.setHorizontalHeaderLabels(["文件", "字段"])
        self.tbl_field_list.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.tbl_field_list.setMinimumHeight(180)
        self.tbl_field_list.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        left_layout.addWidget(self.tbl_field_list)
        
        splitter.addWidget(left_widget)
        
        # 右侧：关联关系图（使用 QGraphicsView）
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(4)
        
        right_label = QLabel("字段关联图")
        right_label.setObjectName("step3_relation_label")
        right_layout.addWidget(right_label)
        
        # 创建图形视图和场景
        self.relation_scene = QGraphicsScene()
        self.relation_view = QGraphicsView(self.relation_scene)
        self.relation_view.setObjectName("step3_relation_graph")
        self.relation_view.setMinimumHeight(180)
        # 开启抗锯齿渲染
        from qgis.PyQt.QtGui import QPainter
        self.relation_view.setRenderHints(
            QPainter.RenderHint.Antialiasing | 
            QPainter.RenderHint.TextAntialiasing |
            QPainter.RenderHint.SmoothPixmapTransform
        )
        # 支持拖拽和缩放
        self.relation_view.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.relation_view.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.relation_view.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        # 绑定滚轮缩放
        self.relation_view.wheelEvent = self._on_graph_wheel_event
        right_layout.addWidget(self.relation_view)
        
        splitter.addWidget(right_widget)
        splitter.setSizes([250, 350])
        
        v.addWidget(splitter)
        
        # 高关联字段对列表 - 标题行（含筛选器）
        relation_header_row = QHBoxLayout()
        relation_label = QLabel("高关联字段对列表")
        relation_label.setObjectName("step3_relation_label")
        relation_header_row.addWidget(relation_label)
        
        relation_header_row.addWidget(QLabel("筛选文件:"))
        self.cmb_file_filter = NoWheelComboBox()
        self.cmb_file_filter.setObjectName("step3_file_pair_filter")
        self.cmb_file_filter.setMinimumWidth(200)
        self.cmb_file_filter.addItem("全部文件", "all")
        self.cmb_file_filter.currentIndexChanged.connect(self._on_file_filter_changed)
        relation_header_row.addWidget(self.cmb_file_filter)
        relation_header_row.addStretch()
        v.addLayout(relation_header_row)
        
        self.tbl_relation_pairs = QTableWidget()
        self.tbl_relation_pairs.setObjectName("step3_relation_pairs_table")
        self.tbl_relation_pairs.setColumnCount(4)
        self.tbl_relation_pairs.setHorizontalHeaderLabels(["字段 A", "字段 B", "重叠度", "共同值数"])
        self.tbl_relation_pairs.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tbl_relation_pairs.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.tbl_relation_pairs.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self.tbl_relation_pairs.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self.tbl_relation_pairs.horizontalHeader().resizeSection(2, 70)
        self.tbl_relation_pairs.horizontalHeader().resizeSection(3, 70)
        self.tbl_relation_pairs.setMinimumHeight(120)
        self.tbl_relation_pairs.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tbl_relation_pairs.cellDoubleClicked.connect(self._on_relation_double_click)
        v.addWidget(self.tbl_relation_pairs)
        
        # 分页控件
        self._all_relations = []  # 存储全部关联数据（原始）
        self._filtered_relations = []  # 存储筛选后的关联数据
        self._page_size = 20
        self._current_page = 0
        
        page_row = QHBoxLayout()
        self.btn_prev_page = QPushButton("上一页")
        self.btn_prev_page.setObjectName("step3_btn_page")
        self.btn_prev_page.clicked.connect(self._prev_page)
        self.btn_next_page = QPushButton("下一页")
        self.btn_next_page.setObjectName("step3_btn_page")
        self.btn_next_page.clicked.connect(self._next_page)
        self.lbl_page_info = QLabel("第 0/0 页，共 0 条")
        self.lbl_page_info.setObjectName("step3_page_info")
        
        page_row.addWidget(self.btn_prev_page)
        page_row.addWidget(self.lbl_page_info)
        page_row.addWidget(self.btn_next_page)
        page_row.addStretch()
        v.addLayout(page_row)
        
        # 洞察发现面板（可点击筛选）
        insight_label = QLabel("洞察发现 (点击可筛选)")
        insight_label.setObjectName("step3_relation_label")
        v.addWidget(insight_label)
        
        self.lst_insights = QListWidget()
        self.lst_insights.setObjectName("step3_insights_list")
        self.lst_insights.setMaximumHeight(140)
        self.lst_insights.setAlternatingRowColors(True)
        self.lst_insights.itemClicked.connect(self._on_insight_clicked)
        v.addWidget(self.lst_insights)
        
        # 保留 txt_insights 用于向后兼容（隐藏）
        self.txt_insights = QTextEdit()
        self.txt_insights.hide()
        
        # 初始显示提示
        self._show_relation_placeholder()
        
        section.add_widget(content_widget)
        return section
    
    def _show_relation_placeholder(self):
        """显示占位提示"""
        from qgis.PyQt.QtGui import QColor, QFont
        
        self.tbl_field_list.setRowCount(0)
        self.tbl_relation_pairs.setRowCount(0)
        self.lst_insights.clear()
        
        self.relation_scene.clear()
        text = self.relation_scene.addText("点击「分析关联关系」按钮\n读取清洗后数据并分析")
        text.setDefaultTextColor(QColor("#9ca3af"))
        font = QFont()
        font.setPointSize(10)
        text.setFont(font)
        text.setPos(80, 70)
        self.relation_scene.setSceneRect(0, 0, 350, 200)
    
    def _analyze_relations(self):
        """分析字段关联关系（调用 Core 层）"""
        from ..widgets.result_dialog import ResultDialog
        from ...core.field_relation import FieldRelationAnalyzer
        from qgis.PyQt.QtWidgets import QApplication
        import os
        
        self._log("[Step3] 开始分析字段关联关系", "info")
        self.lbl_relation_status.setText("正在扫描文件...")
        
        # 显示进度条
        self.progress_relation.setVisible(True)
        self.progress_relation.setValue(0)
        QApplication.processEvents()
        
        # 获取原始数据文件列表
        cleaned_files = self._get_source_files_for_relation()
        
        if not cleaned_files:
            self.progress_relation.setVisible(False)
            self.lbl_relation_status.setText("未找到原始数据文件")
            ResultDialog.show_warning(self, "无数据", "未找到原始数据文件，请先在 Step1 导入数据")
            return
        
        try:
            self.progress_relation.setValue(10)
            self.lbl_relation_status.setText(f"加载 {len(cleaned_files)} 个文件...")
            QApplication.processEvents()
            
            # 创建分析器，传入进度回调
            def progress_callback(percent, msg):
                self.progress_relation.setValue(int(10 + percent * 0.8))  # 10-90%
                self.lbl_relation_status.setText(msg)
                QApplication.processEvents()
            
            analyzer = FieldRelationAnalyzer(log_callback=self._log, progress_callback=progress_callback)
            
            # 执行分析
            result = analyzer.analyze(cleaned_files, min_overlap=1)
            
            self.progress_relation.setValue(95)
            self.lbl_relation_status.setText("更新界面...")
            QApplication.processEvents()
            
            if not result['success']:
                self.progress_relation.setVisible(False)
                self.lbl_relation_status.setText("分析失败")
                ResultDialog.show_error(self, "分析失败", result['message'])
                return
            
            # 保存结果
            self._relation_result = result
            
            # 更新 UI
            self._update_relation_ui(result)
            
            self.progress_relation.setValue(100)
            self.lbl_relation_status.setText(f"完成: {len(result['fields'])} 字段, {len(result['relations'])} 关联")
            self._log(f"[Step3] 关联分析完成: {result['message']}", "success")
            
        except Exception as e:
            self.lbl_relation_status.setText("分析出错")
            self._log(f"[Step3] 关联分析失败: {e}", "error")
            ResultDialog.show_error(self, "分析出错", str(e))
        finally:
            self.progress_relation.setVisible(False)
    
    def _get_source_files_for_relation(self) -> List[str]:
        """获取所有导入的原始数据文件路径"""
        import os
        
        files = []
        global_config = self._get_global_config()
        if not global_config:
            self._log("[关联分析] 未获取到全局配置", "warning")
            return files
        
        region_info = global_config.get_region_info()
        customer_folder = region_info.get("customer_folder", "")
        shp_folder = region_info.get("shp_folder", "")
        
        self._log(f"[关联分析] 客户数据目录: {customer_folder}", "debug")
        self._log(f"[关联分析] SHP数据目录: {shp_folder}", "debug")
        
        # 扫描原始数据目录（Step1 导入的数据）
        folders_to_scan = []
        if customer_folder and os.path.isdir(customer_folder):
            folders_to_scan.append(("客户数据", customer_folder))
        else:
            self._log(f"[关联分析] 客户数据目录不存在或为空: {customer_folder}", "warning")
            
        if shp_folder and os.path.isdir(shp_folder):
            folders_to_scan.append(("SHP数据", shp_folder))
        else:
            self._log(f"[关联分析] SHP数据目录不存在或为空: {shp_folder}", "warning")
        
        for folder_type, source_folder in folders_to_scan:
            folder_files = []
            for file_name in os.listdir(source_folder):
                file_lower = file_name.lower()
                # 支持 CSV 和 Excel 格式
                if file_lower.endswith('.csv') or file_lower.endswith('.xlsx') or file_lower.endswith('.xls'):
                    files.append(os.path.join(source_folder, file_name))
                    folder_files.append(file_name)
            self._log(f"[关联分析] {folder_type}目录找到 {len(folder_files)} 个文件", "debug")
        
        return files
    
    def _update_relation_ui(self, result: Dict[str, Any]):
        """更新关联分析 UI"""
        from qgis.PyQt.QtWidgets import QTableWidgetItem
        
        # 1. 更新字段列表
        fields = result.get('fields', [])
        self.tbl_field_list.setRowCount(len(fields))
        for i, field in enumerate(fields):
            self.tbl_field_list.setItem(i, 0, QTableWidgetItem(field['file']))
            self.tbl_field_list.setItem(i, 1, QTableWidgetItem(field['field']))
        
        # 2. 存储全部关联数据和字段列表
        self._all_relations = result.get('relations', [])
        self._all_fields = result.get('fields', [])
        
        # 3. 更新文件筛选器（从所有字段中提取文件名）
        self._update_file_filter()
        
        # 4. 筛选并分页显示
        self._filtered_relations = self._all_relations.copy()
        self._current_page = 0
        self._refresh_relation_table()
        
        # 5. 更新洞察面板
        insights = result.get('insights', [])
        self._update_insights_panel(insights)
        
        # 6. 绘制关系图
        self._draw_relation_graph(result)
    
    def _update_file_filter(self):
        """更新文件筛选下拉框（从所有字段中提取文件名）"""
        # 从所有字段中提取文件名（不仅是有关联的）
        files = set()
        if hasattr(self, '_all_fields'):
            for field in self._all_fields:
                files.add(field['file'])
        
        # 更新下拉框
        self.cmb_file_filter.blockSignals(True)
        self.cmb_file_filter.clear()
        self.cmb_file_filter.addItem(f"全部文件 ({len(files)})", "all")
        
        for f in sorted(files):
            # 统计该文件有多少关联（用 startswith 精确匹配）
            rel_count = sum(1 for rel in self._all_relations 
                           if rel['field_a'].startswith(f + ".") or rel['field_b'].startswith(f + "."))
            display = f"{f} ({rel_count}条)" if rel_count > 0 else f"{f} (无关联)"
            self.cmb_file_filter.addItem(display, f)
        
        self.cmb_file_filter.blockSignals(False)
    
    def _on_file_filter_changed(self, index: int):
        """文件筛选改变 - 同步更新字段列表、关联图、关联列表"""
        from qgis.PyQt.QtWidgets import QTableWidgetItem
        
        filter_value = self.cmb_file_filter.itemData(index)
        
        # 如果选择的不是临时筛选项（节点或洞察），移除它们
        if not (filter_value and (filter_value.startswith("node:") or filter_value.startswith("insight:"))):
            self._remove_temp_filter_items()
        
        if filter_value == "all":
            # 全部文件
            self._filtered_relations = self._all_relations.copy()
            filtered_fields = self._all_fields if hasattr(self, '_all_fields') else []
        elif filter_value and filter_value.startswith("node:"):
            # 节点筛选（由点击节点触发）
            node_id = filter_value[5:]  # 去掉 "node:" 前缀
            self._filtered_relations = [
                rel for rel in self._all_relations
                if rel['field_a'] == node_id or rel['field_b'] == node_id
            ]
            # 字段列表显示该节点所在文件的字段
            file_name = node_id.rsplit('.', 1)[0] if '.' in node_id else node_id
            filtered_fields = [f for f in self._all_fields if f['file'] == file_name] if hasattr(self, '_all_fields') else []
        else:
            # 筛选包含该文件的所有关联
            target_file = filter_value
            self._filtered_relations = []
            for rel in self._all_relations:
                if rel['field_a'].startswith(target_file + ".") or rel['field_b'].startswith(target_file + "."):
                    self._filtered_relations.append(rel)
            
            # 筛选字段列表 - 只显示该文件的字段
            filtered_fields = [f for f in self._all_fields if f['file'] == target_file] if hasattr(self, '_all_fields') else []
        
        # 按共同值数降序排序（保持排序一致性）
        self._filtered_relations.sort(key=lambda x: (-x.get('overlap_count', 0), -x.get('jaccard', 0)))
        
        # 节点/洞察筛选时，只更新列表，不更新图和字段列表
        is_temp_filter = filter_value and (filter_value.startswith("node:") or filter_value.startswith("insight:"))
        
        if not is_temp_filter:
            # 1. 更新字段列表（仅文件筛选时）
            self.tbl_field_list.setRowCount(len(filtered_fields))
            for i, field in enumerate(filtered_fields):
                self.tbl_field_list.setItem(i, 0, QTableWidgetItem(field['file']))
                self.tbl_field_list.setItem(i, 1, QTableWidgetItem(field['field']))
            
            # 2. 更新关联图（仅文件筛选时）
            self._draw_filtered_relation_graph(filter_value)
        
        # 3. 更新关联列表（始终更新）
        self._current_page = 0
        self._refresh_relation_table()
    
    def _draw_filtered_relation_graph(self, filter_value: str):
        """根据筛选条件重绘关联图"""
        if not hasattr(self, '_graph_layout') or not self._graph_layout:
            return
        
        # 获取需要显示的节点和边
        if filter_value == "all":
            # 全部文件 - 显示所有节点和边
            filtered_relations = self._all_relations
            filtered_nodes = set(self._graph_layout.keys())
        else:
            # 单个文件 - 只显示与该文件相关的节点和边
            target_file = filter_value
            filtered_relations = self._filtered_relations
            
            # 收集相关节点
            filtered_nodes = set()
            for rel in filtered_relations:
                filtered_nodes.add(rel['field_a'])
                filtered_nodes.add(rel['field_b'])
        
        # 重绘图
        self._draw_relation_graph_filtered(
            filtered_nodes, 
            filtered_relations, 
            self._graph_layout,
            getattr(self, '_node_community', {}),
            getattr(self, '_centrality', {})
        )
    
    def _draw_relation_graph_filtered(self, nodes: set, relations: list, layout: dict, 
                                       node_community: dict, centrality: dict):
        """绘制筛选后的关联图（可交互）"""
        from qgis.PyQt.QtGui import QColor, QFont, QBrush, QPen, QPainterPath, QLinearGradient
        from qgis.PyQt.QtCore import Qt
        
        self.relation_scene.clear()
        
        if not nodes or not layout:
            text = self.relation_scene.addText("无关联数据\n\n💡 点击节点筛选关联")
            text.setDefaultTextColor(QColor("#6b7280"))
            return
        
        # 场景尺寸
        width = 340
        height = 200
        margin = 40
        
        # 计算节点位置（只包含筛选后的节点）
        filtered_layout = {k: v for k, v in layout.items() if k in nodes}
        
        if not filtered_layout:
            text = self.relation_scene.addText("无关联数据\n\n💡 点击节点筛选关联")
            text.setDefaultTextColor(QColor("#6b7280"))
            return
        
        # 重新计算坐标范围
        xs = [pos[0] for pos in filtered_layout.values()]
        ys = [pos[1] for pos in filtered_layout.values()]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        
        range_x = max_x - min_x if max_x != min_x else 1
        range_y = max_y - min_y if max_y != min_y else 1
        
        def scale_pos(pos):
            x = margin + (pos[0] - min_x) / range_x * (width - 2 * margin)
            y = margin + (pos[1] - min_y) / range_y * (height - 2 * margin)
            return (x, y)
        
        node_positions = {node: scale_pos(pos) for node, pos in filtered_layout.items()}
        
        # 社区颜色
        community_colors = [
            "#3b82f6", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6",
            "#ec4899", "#06b6d4", "#84cc16", "#f97316", "#6366f1"
        ]
        
        # 绘制边（可点击）
        for rel in relations:
            field_a, field_b = rel['field_a'], rel['field_b']
            if field_a not in node_positions or field_b not in node_positions:
                continue
            
            pos_a = node_positions[field_a]
            pos_b = node_positions[field_b]
            jaccard = rel.get('jaccard', 0)
            
            # 边颜色
            if jaccard >= 0.8:
                edge_color = QColor("#22c55e")
            elif jaccard >= 0.6:
                edge_color = QColor("#84cc16")
            elif jaccard >= 0.4:
                edge_color = QColor("#eab308")
            elif jaccard >= 0.2:
                edge_color = QColor("#f97316")
            else:
                edge_color = QColor("#ef4444")
            
            # 曲线边
            path = QPainterPath()
            path.moveTo(pos_a[0], pos_a[1])
            mid_x = (pos_a[0] + pos_b[0]) / 2
            mid_y = (pos_a[1] + pos_b[1]) / 2 - 20
            path.quadTo(mid_x, mid_y, pos_b[0], pos_b[1])
            
            # 使用可点击边
            edge_item = ClickableEdgeItem(path, rel, self._on_edge_clicked)
            pen = QPen(edge_color)
            pen.setWidth(max(1, int(jaccard * 3)))
            edge_item.setPen(pen)
            self.relation_scene.addItem(edge_item)
        
        # 绘制节点（可点击）
        node_radius = 8
        for node, pos in node_positions.items():
            comm_id = node_community.get(node, 0)
            color = QColor(community_colors[comm_id % len(community_colors)])
            
            cent = centrality.get(node, 0)
            radius = node_radius + cent * 10
            
            # 使用可点击节点
            node_item = ClickableNodeItem(
                pos[0] - radius, pos[1] - radius,
                radius * 2, radius * 2,
                node, self._on_node_clicked
            )
            node_item.setPen(QPen(color.darker(120)))
            node_item.setBrush(QBrush(color))
            self.relation_scene.addItem(node_item)
            
            # 标签（只显示字段名，hover 显示完整名称）
            field_name = node.split('.')[-1] if '.' in node else node
            if len(field_name) > 8:
                field_name = field_name[:6] + ".."
            
            label = self.relation_scene.addText(field_name)
            label.setDefaultTextColor(QColor("#374151"))
            label.setFont(QFont("Microsoft YaHei", 7))
            label.setPos(pos[0] + radius + 2, pos[1] - 6)
        
        # 添加图例
        self._draw_filtered_graph_legend()
    
    def _draw_filtered_graph_legend(self):
        """绘制筛选图的图例"""
        from qgis.PyQt.QtGui import QPen, QBrush, QColor, QFont
        
        legend_x = 5
        legend_y = 170
        
        # 图例标题
        title = self.relation_scene.addText("图例 (悬停显示完整名称)")
        title.setDefaultTextColor(QColor("#374151"))
        title.setFont(QFont("Microsoft YaHei", 7, QFont.Weight.Bold))
        title.setPos(legend_x, legend_y)
        
        # 关联强度说明
        colors = [
            ("#22c55e", "≥80%"),
            ("#84cc16", "60-80%"),
            ("#eab308", "40-60%"),
            ("#f97316", "20-40%"),
            ("#ef4444", "<20%")
        ]
        
        y_offset = legend_y + 15
        for i, (color, label) in enumerate(colors):
            # 色块
            rect = self.relation_scene.addRect(
                legend_x, y_offset + i * 12, 20, 8,
                QPen(Qt.PenStyle.NoPen),
                QBrush(QColor(color))
            )
            # 标签
            txt = self.relation_scene.addText(label)
            txt.setDefaultTextColor(QColor("#6b7280"))
            txt.setFont(QFont("Microsoft YaHei", 6))
            txt.setPos(legend_x + 25, y_offset + i * 12 - 3)
    
    def _on_relation_double_click(self, row: int, col: int):
        """双击关联行，显示共同值详情并支持导出"""
        # 计算实际数据索引
        actual_idx = self._current_page * self._page_size + row
        if actual_idx >= len(self._filtered_relations):
            return
        
        rel = self._filtered_relations[actual_idx]
        common_values = rel.get('common_values', [])
        
        # 解析字段信息
        field_a = rel['field_a']
        field_b = rel['field_b']
        # 格式: "文件名.字段名" -> 分离
        file_a = field_a.rsplit('.', 1)[0] if '.' in field_a else field_a
        col_a = field_a.rsplit('.', 1)[1] if '.' in field_a else field_a
        file_b = field_b.rsplit('.', 1)[0] if '.' in field_b else field_b
        col_b = field_b.rsplit('.', 1)[1] if '.' in field_b else field_b
        
        # 简短文件名（去掉扩展名）
        file_a_short = file_a.replace('.csv', '').replace('.xlsx', '')
        file_b_short = file_b.replace('.csv', '').replace('.xlsx', '')
        
        # 构建详情对话框（使用全局样式）
        from qgis.PyQt.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit, QPushButton, QFrame
        from qgis.PyQt.QtCore import Qt
        
        dialog = QDialog(self)
        dialog.setWindowTitle("字段关联详情")
        dialog.setObjectName("relation_detail_dialog")
        dialog.setMinimumSize(550, 480)
        
        layout = QVBoxLayout(dialog)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # 标题
        title = QLabel("📊 字段关联详情")
        title.setObjectName("relation_detail_title")
        layout.addWidget(title)
        
        # 分隔线
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setObjectName("relation_detail_line")
        layout.addWidget(line)
        
        # 关联信息卡片
        info_card = QFrame()
        info_card.setObjectName("relation_detail_card")
        card_layout = QVBoxLayout(info_card)
        card_layout.setSpacing(8)
        
        # 真实的 SQL 关联条件
        sql_condition = f'"{file_a}"."{col_a}" = "{file_b}"."{col_b}"'
        
        info_items = [
            ("表 A", file_a),
            ("字段 A", col_a),
            ("表 B", file_b),
            ("字段 B", col_b),
            ("重叠度", f"{rel['jaccard']:.2%}"),
            ("共同值数", f"{rel['overlap_count']:,}"),
            ("关联条件 (SQL)", sql_condition),
        ]
        
        for label, value in info_items:
            row_layout = QHBoxLayout()
            lbl = QLabel(f"<b>{label}:</b>")
            lbl.setFixedWidth(100)
            val = QLabel(value)
            val.setWordWrap(True)
            val.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            row_layout.addWidget(lbl)
            row_layout.addWidget(val, 1)
            card_layout.addLayout(row_layout)
        
        layout.addWidget(info_card)
        
        # 共同值列表
        layout.addWidget(QLabel(f"<b>共同值示例（前 {len(common_values)} 个）:</b>"))
        
        values_text = QTextEdit()
        values_text.setObjectName("relation_detail_values")
        values_text.setReadOnly(True)
        if common_values:
            values_text.setPlainText('\n'.join(f"{i+1}. {v}" for i, v in enumerate(common_values)))
        else:
            values_text.setPlainText("（共同值数据未缓存，请重新分析）")
        layout.addWidget(values_text)
        
        # 按钮行1：导出关联数据
        btn_row1 = QHBoxLayout()
        
        btn_export = QPushButton("📥 导出关联数据 (INNER JOIN)")
        btn_export.setObjectName("relation_detail_btn_export")
        btn_export.setToolTip(f"导出 {file_a} 和 {file_b} 关联上的数据")
        btn_export.clicked.connect(lambda: self._export_joined_data(rel, dialog, 'inner'))
        btn_row1.addWidget(btn_export)
        btn_row1.addStretch()
        layout.addLayout(btn_row1)
        
        # 按钮行2：导出未关联数据
        btn_row2 = QHBoxLayout()
        
        btn_export_a_only = QPushButton(f"📤 导出 {file_a_short} 未关联数据")
        btn_export_a_only.setObjectName("relation_detail_btn_export_unmatched")
        btn_export_a_only.setToolTip(f"导出 {file_a} 中没有匹配到 {file_b} 的数据")
        btn_export_a_only.clicked.connect(lambda: self._export_joined_data(rel, dialog, 'left_only'))
        btn_row2.addWidget(btn_export_a_only)
        
        btn_export_b_only = QPushButton(f"📤 导出 {file_b_short} 未关联数据")
        btn_export_b_only.setObjectName("relation_detail_btn_export_unmatched")
        btn_export_b_only.setToolTip(f"导出 {file_b} 中没有匹配到 {file_a} 的数据")
        btn_export_b_only.clicked.connect(lambda: self._export_joined_data(rel, dialog, 'right_only'))
        btn_row2.addWidget(btn_export_b_only)
        
        btn_row2.addStretch()
        layout.addLayout(btn_row2)
        
        # 按钮行3：关闭
        btn_row3 = QHBoxLayout()
        btn_row3.addStretch()
        btn_close = QPushButton("关闭")
        btn_close.setObjectName("relation_detail_btn_close")
        btn_close.clicked.connect(dialog.accept)
        btn_row3.addWidget(btn_close)
        layout.addLayout(btn_row3)
        
        dialog.exec()
    
    def _export_joined_data(self, rel: Dict[str, Any], parent_dialog: Any, join_type: str = 'inner'):
        """
        导出两个表的关联/未关联数据（调用 Core 层 RelationExporter）
        
        Args:
            rel: 关联信息
            parent_dialog: 父对话框
            join_type: 'inner' - 关联数据, 'left_only' - A表未关联, 'right_only' - B表未关联
        """
        import os
        from ..widgets.result_dialog import ResultDialog
        from qgis.PyQt.QtWidgets import QFileDialog
        from ...core.field_relation import RelationExporter
        
        field_a = rel['field_a']
        field_b = rel['field_b']
        
        # 解析文件名和字段名
        file_a = field_a.rsplit('.', 1)[0] if '.' in field_a else field_a
        col_a = field_a.rsplit('.', 1)[1] if '.' in field_a else field_a
        file_b = field_b.rsplit('.', 1)[0] if '.' in field_b else field_b
        col_b = field_b.rsplit('.', 1)[1] if '.' in field_b else field_b
        
        # 获取文件路径
        global_config = self._get_global_config()
        if not global_config:
            ResultDialog.show_error(parent_dialog, "配置错误", "无法获取全局配置")
            return
        
        region_info = global_config.get_region_info()
        customer_folder = region_info.get("customer_folder", "")
        shp_folder = region_info.get("shp_folder", "")
        cache_folder = region_info.get("cache_folder", "")
        base_folder = region_info.get("base_folder", "")
        
        # 查找文件路径
        def find_file(file_name):
            for folder in [customer_folder, shp_folder]:
                if folder:
                    path = os.path.join(folder, file_name)
                    if os.path.exists(path):
                        return path
            return None
        
        path_a = find_file(file_a)
        path_b = find_file(file_b)
        
        if not path_a:
            ResultDialog.show_error(parent_dialog, "文件不存在", f"找不到文件: {file_a}")
            return
        if not path_b:
            ResultDialog.show_error(parent_dialog, "文件不存在", f"找不到文件: {file_b}")
            return
        
        # 生成默认文件名
        file_a_short = file_a.replace('.csv', '').replace('.xlsx', '')
        file_b_short = file_b.replace('.csv', '').replace('.xlsx', '')
        
        # 根据导出类型设置文件名和对话框标题
        if join_type == RelationExporter.JOIN_INNER:
            default_name = f"关联结果_{file_a_short}_{file_b_short}.xlsx"
            dialog_title = "导出关联数据"
        elif join_type == RelationExporter.JOIN_LEFT_ONLY:
            default_name = f"未关联数据_{file_a_short}.xlsx"
            dialog_title = f"导出 {file_a_short} 未关联数据"
        else:  # right_only
            default_name = f"未关联数据_{file_b_short}.xlsx"
            dialog_title = f"导出 {file_b_short} 未关联数据"
        
        default_dir = base_folder or customer_folder or shp_folder or ""
        
        # 弹出文件保存对话框（UI 层职责）
        output_path, _ = QFileDialog.getSaveFileName(
            parent_dialog,
            dialog_title,
            os.path.join(default_dir, default_name),
            "Excel 文件 (*.xlsx);;CSV 文件 (*.csv)"
        )
        
        if not output_path:
            return  # 用户取消
        
        # 调用 Core 层执行导出（业务逻辑在 Core 层）
        exporter = RelationExporter(log_callback=self._log)
        result = exporter.export(
            path_a=path_a,
            path_b=path_b,
            col_a=col_a,
            col_b=col_b,
            output_path=output_path,
            join_type=join_type
        )
        
        # 显示结果（UI 层职责）
        if result['success']:
            if result['row_count'] > 0:
                # 保存关联元数据到缓存
                self._save_join_metadata(rel, output_path, result['row_count'], cache_folder)
                ResultDialog.show_success(
                    parent_dialog, 
                    "导出成功", 
                    f"{result['message']}\n\n保存位置:\n{output_path}"
                )
            else:
                # 没有数据
                if join_type == RelationExporter.JOIN_INNER:
                    ResultDialog.show_warning(parent_dialog, "无匹配数据", result['message'])
                else:
                    ResultDialog.show_info(parent_dialog, "全部已关联", result['message'])
        else:
            ResultDialog.show_error(parent_dialog, "导出失败", result['message'])
    
    def _save_join_metadata(self, rel: Dict[str, Any], output_path: str, row_count: int, cache_folder: str):
        """保存关联导出的元数据到持久化缓存"""
        import os
        import json
        from datetime import datetime
        
        if not cache_folder:
            return
        
        metadata_file = os.path.join(cache_folder, "join_exports.json")
        
        # 读取现有元数据
        metadata = {}
        if os.path.exists(metadata_file):
            try:
                with open(metadata_file, 'r', encoding='utf-8') as f:
                    metadata = json.load(f)
            except:
                pass
        
        # 添加新记录
        key = f"{rel['field_a']}|{rel['field_b']}"
        metadata[key] = {
            'field_a': rel['field_a'],
            'field_b': rel['field_b'],
            'jaccard': rel['jaccard'],
            'overlap_count': rel['overlap_count'],
            'output_path': output_path,
            'row_count': row_count,
            'export_time': datetime.now().isoformat()
        }
        
        # 保存
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)
    
    def _refresh_relation_table(self):
        """刷新关联表格（当前页，使用筛选后的数据）"""
        from qgis.PyQt.QtWidgets import QTableWidgetItem
        
        # 使用筛选后的数据
        data_source = self._filtered_relations if hasattr(self, '_filtered_relations') else self._all_relations
        total = len(data_source)
        total_pages = (total + self._page_size - 1) // self._page_size if total > 0 else 1
        
        # 计算当前页数据范围
        start_idx = self._current_page * self._page_size
        end_idx = min(start_idx + self._page_size, total)
        page_data = data_source[start_idx:end_idx]
        
        # 更新表格
        self.tbl_relation_pairs.setRowCount(len(page_data))
        for i, rel in enumerate(page_data):
            item_a = QTableWidgetItem(rel['field_a'])
            item_b = QTableWidgetItem(rel['field_b'])
            score_item = QTableWidgetItem(f"{rel['jaccard']:.2f}")
            count_item = QTableWidgetItem(str(rel['overlap_count']))
            
            score_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            count_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            
            # 行高亮
            row_color = self._get_row_highlight_color(rel['jaccard'])
            if row_color:
                item_a.setBackground(row_color)
                item_b.setBackground(row_color)
                score_item.setBackground(row_color)
                count_item.setBackground(row_color)
            
            self.tbl_relation_pairs.setItem(i, 0, item_a)
            self.tbl_relation_pairs.setItem(i, 1, item_b)
            self.tbl_relation_pairs.setItem(i, 2, score_item)
            self.tbl_relation_pairs.setItem(i, 3, count_item)
        
        # 更新分页信息
        self.lbl_page_info.setText(f"第 {self._current_page + 1}/{total_pages} 页，共 {total} 条")
        self.btn_prev_page.setEnabled(self._current_page > 0)
        self.btn_next_page.setEnabled(self._current_page < total_pages - 1)
    
    def _prev_page(self):
        """上一页"""
        if self._current_page > 0:
            self._current_page -= 1
            self._refresh_relation_table()
    
    def _next_page(self):
        """下一页"""
        data_source = self._filtered_relations if hasattr(self, '_filtered_relations') else self._all_relations
        total = len(data_source)
        total_pages = (total + self._page_size - 1) // self._page_size if total > 0 else 1
        if self._current_page < total_pages - 1:
            self._current_page += 1
            self._refresh_relation_table()
    
    def _update_insights_panel(self, insights: List[Dict[str, Any]]):
        """更新洞察面板（可点击列表）"""
        self.lst_insights.clear()
        self._insight_data = {}  # 存储每个洞察项的筛选数据
        
        for insight in insights:
            insight_type = insight['type']
            title = insight['title']
            data = insight.get('data', [])
            
            # 添加图标（如果没有）
            if not any(c in title for c in ['🔗', '⭐', '📊', '🎯', '🔑', '🔥']):
                icon = {
                    'community': '🔗',
                    'central': '⭐',
                    'stats': '📊',
                    'high_relation': '🎯',
                    'foreign_key': '🔑'
                }.get(insight_type, '📊')
                title = f"{icon} {title}"
            
            # 构建显示文本和提示
            if insight_type == 'stats':
                # 统计类型可点击，清除筛选显示全部
                display = f"{title} - {insight['description']} 👆点击显示全部"
                item = QListWidgetItem(display)
                item.setToolTip("点击清除筛选，显示全部关联")
                item.setData(Qt.ItemDataRole.UserRole, {'type': 'stats'})
                item.setForeground(QColor("#059669"))
            elif insight_type == 'high_relation':
                # 高关联可点击筛选
                display = f"{title} 👆点击查看全部"
                item = QListWidgetItem(display)
                item.setToolTip(f"{insight['description']}\n\n点击在下方列表中显示全部 {len(data) if isinstance(data, list) else 0} 对关联")
                item.setData(Qt.ItemDataRole.UserRole, {'type': 'high_relation', 'min_jaccard': 0.6, 'diff_name': True})
                item.setForeground(QColor("#dc2626"))
            elif insight_type == 'foreign_key':
                # 外键可点击筛选
                display = f"{title} 👆点击查看全部"
                item = QListWidgetItem(display)
                item.setToolTip(f"{insight['description']}\n\n点击在下方列表中显示全部疑似外键")
                item.setData(Qt.ItemDataRole.UserRole, {'type': 'foreign_key', 'min_containment': 0.9, 'diff_name': True})
                item.setForeground(QColor("#7c3aed"))
            elif insight_type == 'central':
                # 核心字段可点击 - 预先计算关联数
                central_fields = [d[0] for d in data if isinstance(d, tuple)] if data else []
                # 计算这些核心字段涉及的关联数
                central_relation_count = sum(1 for rel in self._all_relations 
                    if rel['field_a'] in central_fields or rel['field_b'] in central_fields)
                display = f"{title} ({len(data)}个字段, {central_relation_count}对关联) 👆点击查看"
                item = QListWidgetItem(display)
                item.setToolTip(f"这{len(data)}个核心字段共涉及{central_relation_count}对关联关系")
                item.setData(Qt.ItemDataRole.UserRole, {'type': 'central', 'fields': central_fields})
                item.setForeground(QColor("#0891b2"))
            else:
                # 其他类型
                display = f"{title}"
                item = QListWidgetItem(display)
                item.setForeground(QColor("#374151"))
            
            self.lst_insights.addItem(item)
        
        if self.lst_insights.count() == 0:
            item = QListWidgetItem("未发现有价值的洞察")
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            item.setForeground(QColor("#9ca3af"))
            self.lst_insights.addItem(item)
    
    def _on_insight_clicked(self, item: QListWidgetItem):
        """点击洞察项，筛选关联列表"""
        data = item.data(Qt.ItemDataRole.UserRole)
        if not data:
            return
        
        insight_type = data.get('type')
        
        if insight_type == 'high_relation':
            # 筛选高关联字段（跨文件，不同名，Jaccard > 0.6）
            self._filtered_relations = []
            for rel in self._all_relations:
                # 获取文件名和字段名
                file_a = rel['field_a'].rsplit('.', 1)[0] if '.' in rel['field_a'] else ''
                file_b = rel['field_b'].rsplit('.', 1)[0] if '.' in rel['field_b'] else ''
                field_a = rel['field_a'].split('.')[-1] if '.' in rel['field_a'] else rel['field_a']
                field_b = rel['field_b'].split('.')[-1] if '.' in rel['field_b'] else rel['field_b']
                # 跨文件 + 不同名 + 高关联
                if file_a != file_b and field_a.lower() != field_b.lower() and rel['jaccard'] > 0.6:
                    self._filtered_relations.append(rel)
            self._log(f"[洞察] 筛选异名高关联字段: {len(self._filtered_relations)} 对", "info")
            
        elif insight_type == 'foreign_key':
            # 筛选疑似外键（跨文件，不同名，overlap >= 10，包含度 > 0.9）
            self._filtered_relations = []
            for rel in self._all_relations:
                file_a = rel['field_a'].rsplit('.', 1)[0] if '.' in rel['field_a'] else ''
                file_b = rel['field_b'].rsplit('.', 1)[0] if '.' in rel['field_b'] else ''
                field_a = rel['field_a'].split('.')[-1] if '.' in rel['field_a'] else rel['field_a']
                field_b = rel['field_b'].split('.')[-1] if '.' in rel['field_b'] else rel['field_b']
                overlap = rel.get('overlap_count', 0)
                containment_a = rel.get('containment_a', 0)
                containment_b = rel.get('containment_b', 0)
                # 跨文件 + 不同名 + overlap >= 10 + 包含度 > 0.9
                if (file_a != file_b and 
                    field_a.lower() != field_b.lower() and 
                    overlap >= 10 and 
                    (containment_a > 0.9 or containment_b > 0.9)):
                    self._filtered_relations.append(rel)
            self._log(f"[洞察] 筛选疑似外键: {len(self._filtered_relations)} 对", "info")
            
        elif insight_type == 'central':
            # 筛选核心字段的关联
            central_fields = data.get('fields', [])
            self._filtered_relations = []
            for rel in self._all_relations:
                if rel['field_a'] in central_fields or rel['field_b'] in central_fields:
                    self._filtered_relations.append(rel)
            self._log(f"[洞察] 筛选核心字段关联: {len(self._filtered_relations)} 对", "info")
        
        elif insight_type == 'stats':
            # 清除筛选，显示全部关联
            self._filtered_relations = self._all_relations.copy()
            self._log(f"[洞察] 显示全部关联: {len(self._filtered_relations)} 对", "info")
            # 重置筛选下拉框为"全部文件"
            self.cmb_file_filter.blockSignals(True)
            self.cmb_file_filter.setCurrentIndex(0)
            self.cmb_file_filter.blockSignals(False)
            # 直接刷新表格和图并返回
            self._filtered_relations.sort(key=lambda x: (-x.get('overlap_count', 0), -x.get('jaccard', 0)))
            self._current_page = 0
            self._refresh_relation_table()
            self._update_graph_for_filtered_relations()
            return
        
        # 排序
        self._filtered_relations.sort(key=lambda x: (-x.get('overlap_count', 0), -x.get('jaccard', 0)))
        self._current_page = 0
        
        # 先更新筛选下拉框显示（阻止信号避免重复触发）
        self.cmb_file_filter.blockSignals(True)
        # 移除旧的临时筛选项
        for i in range(self.cmb_file_filter.count() - 1, -1, -1):
            data = self.cmb_file_filter.itemData(i)
            if data and (str(data).startswith("node:") or str(data).startswith("insight:")):
                self.cmb_file_filter.removeItem(i)
        # 添加新的洞察筛选项
        insight_display = f"🔍 {item.text().split('👆')[0].strip()} ({len(self._filtered_relations)}条)"
        self.cmb_file_filter.addItem(insight_display, f"insight:{insight_type}")
        self.cmb_file_filter.setCurrentIndex(self.cmb_file_filter.count() - 1)
        self.cmb_file_filter.blockSignals(False)
        
        # 刷新表格和图
        self._refresh_relation_table()
        self._update_graph_for_filtered_relations()
    
    def _update_graph_for_filtered_relations(self):
        """根据筛选后的关联数据更新图"""
        if not hasattr(self, '_graph_layout') or not self._graph_layout:
            return
        
        # 收集筛选后涉及的节点
        filtered_nodes = set()
        for rel in self._filtered_relations:
            filtered_nodes.add(rel['field_a'])
            filtered_nodes.add(rel['field_b'])
        
        # 重绘图
        self._draw_relation_graph_filtered(
            filtered_nodes,
            self._filtered_relations,
            self._graph_layout,
            getattr(self, '_node_community', {}),
            getattr(self, '_centrality', {})
        )
    
    def _draw_relation_graph(self, result: Dict[str, Any]):
        """基于分析结果绘制关联关系图（可交互）"""
        from qgis.PyQt.QtGui import QPen, QBrush, QColor, QFont, QPainterPath, QLinearGradient
        
        self.relation_scene.clear()
        
        layout = result.get('layout', {})
        relations = result.get('relations', [])
        node_community = result.get('node_community', {})
        centrality = result.get('centrality', {})
        
        # 保存到实例变量，供筛选时使用
        self._graph_layout = layout
        self._node_community = node_community
        self._centrality = centrality
        
        if not layout:
            # 无节点时显示提示
            text = self.relation_scene.addText("未发现跨文件的字段关联\n\n💡 提示：点击节点筛选关联\n    点击边查看详情")
            text.setDefaultTextColor(QColor("#9ca3af"))
            text.setPos(60, 60)
            self.relation_scene.setSceneRect(0, 0, 350, 200)
            return
        
        # 社区颜色映射
        community_colors = ["#3b82f6", "#10b981", "#f59e0b", "#8b5cf6", "#ef4444", "#06b6d4", "#84cc16"]
        
        node_radius = 22
        
        # 先绘制边（可点击）
        for rel in relations:
            field_a = rel['field_a']
            field_b = rel['field_b']
            score = rel['jaccard']
            
            if field_a not in layout or field_b not in layout:
                continue
            
            x1, y1 = layout[field_a]
            x2, y2 = layout[field_b]
            
            # 颜色和线宽
            line_color = self._get_score_color(score)
            line_width = 1 + score * 2.5
            
            # 绘制曲线
            path = QPainterPath()
            path.moveTo(x1, y1)
            
            mid_x = (x1 + x2) / 2
            mid_y = (y1 + y2) / 2
            offset = 20 if abs(y1 - y2) < 50 else 0
            ctrl_y = mid_y + offset
            
            path.quadTo(mid_x, ctrl_y, x2, y2)
            
            # 使用可点击边
            edge_item = ClickableEdgeItem(path, rel, self._on_edge_clicked)
            pen = QPen(line_color, line_width)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            edge_item.setPen(pen)
            self.relation_scene.addItem(edge_item)
        
        # 绘制节点（可点击）
        for node, (x, y) in layout.items():
            # 获取社区颜色
            comm_idx = node_community.get(node, 0) % len(community_colors)
            color = community_colors[comm_idx]
            
            # 根据中心性调整大小
            cent = centrality.get(node, 0)
            radius = node_radius + cent * 15
            
            # 节点阴影
            self.relation_scene.addEllipse(
                x - radius + 2, y - radius + 2,
                radius * 2, radius * 2,
                QPen(Qt.PenStyle.NoPen),
                QBrush(QColor(0, 0, 0, 25))
            )
            
            # 节点（带渐变，可点击）
            gradient = QLinearGradient(x - radius, y - radius, x + radius, y + radius)
            base_color = QColor(color)
            gradient.setColorAt(0, base_color.lighter(130))
            gradient.setColorAt(1, base_color)
            
            node_item = ClickableNodeItem(
                x - radius, y - radius,
                radius * 2, radius * 2,
                node, self._on_node_clicked
            )
            node_item.setPen(QPen(base_color.darker(110), 2))
            node_item.setBrush(QBrush(gradient))
            self.relation_scene.addItem(node_item)
            
            # 节点标签（字段名）
            parts = node.split('.')
            field_name = parts[-1] if len(parts) > 1 else node
            short_name = field_name[:10]
            
            text = self.relation_scene.addText(short_name)
            text.setDefaultTextColor(QColor("white"))
            font = QFont()
            font.setPointSize(7)
            font.setBold(True)
            text.setFont(font)
            text.setPos(x - len(short_name) * 3.5, y - 6)
        
        # 添加图例
        self._draw_graph_legend()
        
        # 添加交互提示
        tip = self.relation_scene.addText("💡 点击节点筛选 | 点击边查看详情")
        tip.setDefaultTextColor(QColor("#6b7280"))
        tip.setFont(QFont("Microsoft YaHei", 7))
        tip.setPos(-25, 240)
        
        # 设置场景范围
        self.relation_scene.setSceneRect(-30, -20, 440, 280)
        self.relation_view.fitInView(self.relation_scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)
    
    def _remove_node_filter_item(self):
        """移除临时的节点筛选项"""
        self._remove_temp_filter_items()
    
    def _remove_temp_filter_items(self):
        """移除所有临时筛选项（节点筛选、洞察筛选）"""
        self.cmb_file_filter.blockSignals(True)
        for i in range(self.cmb_file_filter.count() - 1, -1, -1):
            data = self.cmb_file_filter.itemData(i)
            if data and (str(data).startswith("node:") or str(data).startswith("insight:")):
                self.cmb_file_filter.removeItem(i)
        self.cmb_file_filter.blockSignals(False)
    
    def _on_node_clicked(self, node_id: str):
        """节点点击回调 - 只筛选关联列表，不改变关联图"""
        self._log(f"[关联图] 点击节点: {node_id}", "debug")
        
        # 只筛选包含该节点的关联（只更新列表，不更新图）
        self._filtered_relations = [
            rel for rel in self._all_relations
            if rel['field_a'] == node_id or rel['field_b'] == node_id
        ]
        self._filtered_relations.sort(key=lambda x: (-x.get('overlap_count', 0), -x.get('jaccard', 0)))
        self._current_page = 0
        
        # 只刷新关联列表（不重绘图、不更新字段列表）
        self._refresh_relation_table()
        
        # 更新筛选下拉框显示（不触发信号，不重绘图）
        self.cmb_file_filter.blockSignals(True)
        
        # 先移除旧的节点筛选项
        for i in range(self.cmb_file_filter.count() - 1, -1, -1):
            data = self.cmb_file_filter.itemData(i)
            if data and str(data).startswith("node:"):
                self.cmb_file_filter.removeItem(i)
        
        # 添加新的节点筛选项
        node_display = f"🎯 {node_id} ({len(self._filtered_relations)}条)"
        self.cmb_file_filter.addItem(node_display, f"node:{node_id}")
        self.cmb_file_filter.setCurrentIndex(self.cmb_file_filter.count() - 1)
        
        self.cmb_file_filter.blockSignals(False)
    
    def _on_edge_clicked(self, relation: Dict):
        """边点击回调 - 显示关联详情"""
        self._log(f"[关联图] 点击边: {relation['field_a']} ↔ {relation['field_b']}", "debug")
        
        # 找到该关联在列表中的索引
        for i, rel in enumerate(self._filtered_relations):
            if rel['field_a'] == relation['field_a'] and rel['field_b'] == relation['field_b']:
                # 调用双击处理方法显示详情
                self._show_relation_detail(rel)
                return
        
        # 如果在筛选列表中找不到，直接显示详情
        self._show_relation_detail(relation)
    
    def _show_relation_detail(self, rel: Dict):
        """显示关联详情对话框（复用双击逻辑）"""
        # 构造一个临时的行索引来复用 _on_relation_double_click 的逻辑
        # 直接调用详情显示
        common_values = rel.get('common_values', [])
        
        # 解析字段信息
        field_a = rel['field_a']
        field_b = rel['field_b']
        file_a = field_a.rsplit('.', 1)[0] if '.' in field_a else field_a
        col_a = field_a.rsplit('.', 1)[1] if '.' in field_a else field_a
        file_b = field_b.rsplit('.', 1)[0] if '.' in field_b else field_b
        col_b = field_b.rsplit('.', 1)[1] if '.' in field_b else field_b
        
        file_a_short = file_a.replace('.csv', '').replace('.xlsx', '')
        file_b_short = file_b.replace('.csv', '').replace('.xlsx', '')
        
        # 构建详情对话框
        from qgis.PyQt.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit, QPushButton, QFrame
        from qgis.PyQt.QtCore import Qt
        from ...core.field_relation import RelationExporter
        
        dialog = QDialog(self)
        dialog.setWindowTitle("字段关联详情")
        dialog.setObjectName("relation_detail_dialog")
        dialog.setMinimumSize(550, 480)
        
        layout = QVBoxLayout(dialog)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # 标题
        title = QLabel("📊 字段关联详情")
        title.setObjectName("relation_detail_title")
        layout.addWidget(title)
        
        # 分隔线
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setObjectName("relation_detail_line")
        layout.addWidget(line)
        
        # 关联信息卡片
        info_card = QFrame()
        info_card.setObjectName("relation_detail_card")
        card_layout = QVBoxLayout(info_card)
        
        # 字段信息
        lbl_a = QLabel(f"🔵 字段 A: <b>{file_a_short}</b>.<b>{col_a}</b>")
        lbl_a.setObjectName("relation_detail_label")
        card_layout.addWidget(lbl_a)
        
        lbl_b = QLabel(f"🟢 字段 B: <b>{file_b_short}</b>.<b>{col_b}</b>")
        lbl_b.setObjectName("relation_detail_label")
        card_layout.addWidget(lbl_b)
        
        # Jaccard 和共同值数
        jaccard = rel.get('jaccard', 0)
        overlap = rel.get('overlap_count', 0)
        lbl_score = QLabel(f"📈 Jaccard 相似度: <b>{jaccard:.2%}</b>  |  共同值数: <b>{overlap:,}</b>")
        lbl_score.setObjectName("relation_detail_label")
        card_layout.addWidget(lbl_score)
        
        # SQL 条件
        sql_condition = f'"{file_a}".{col_a} = "{file_b}".{col_b}'
        lbl_sql = QLabel(f"🔗 关联条件: <code>{sql_condition}</code>")
        lbl_sql.setObjectName("relation_detail_label")
        lbl_sql.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        card_layout.addWidget(lbl_sql)
        
        layout.addWidget(info_card)
        
        # 共同值列表
        lbl_values = QLabel(f"📋 共同值示例 (前 {min(20, len(common_values))} 个):")
        lbl_values.setObjectName("relation_detail_label")
        layout.addWidget(lbl_values)
        
        txt_values = QTextEdit()
        txt_values.setObjectName("relation_detail_values")
        txt_values.setReadOnly(True)
        txt_values.setMaximumHeight(120)
        if common_values:
            txt_values.setPlainText('\n'.join(str(v) for v in common_values[:20]))
        else:
            txt_values.setPlainText("(无共同值数据)")
        layout.addWidget(txt_values)
        
        # 按钮行1：导出关联数据
        btn_row1 = QHBoxLayout()
        
        btn_export = QPushButton("📥 导出关联数据 (INNER JOIN)")
        btn_export.setObjectName("relation_detail_btn_export")
        btn_export.clicked.connect(lambda: self._export_joined_data(rel, dialog, RelationExporter.JOIN_INNER))
        btn_row1.addWidget(btn_export)
        btn_row1.addStretch()
        layout.addLayout(btn_row1)
        
        # 按钮行2：导出未关联数据
        btn_row2 = QHBoxLayout()
        
        btn_export_a_only = QPushButton(f"📤 导出 {file_a_short} 未关联数据")
        btn_export_a_only.setObjectName("relation_detail_btn_export_unmatched")
        btn_export_a_only.clicked.connect(lambda: self._export_joined_data(rel, dialog, RelationExporter.JOIN_LEFT_ONLY))
        btn_row2.addWidget(btn_export_a_only)
        
        btn_export_b_only = QPushButton(f"📤 导出 {file_b_short} 未关联数据")
        btn_export_b_only.setObjectName("relation_detail_btn_export_unmatched")
        btn_export_b_only.clicked.connect(lambda: self._export_joined_data(rel, dialog, RelationExporter.JOIN_RIGHT_ONLY))
        btn_row2.addWidget(btn_export_b_only)
        
        btn_row2.addStretch()
        layout.addLayout(btn_row2)
        
        # 按钮行3：关闭
        btn_row3 = QHBoxLayout()
        btn_row3.addStretch()
        btn_close = QPushButton("关闭")
        btn_close.setObjectName("relation_detail_btn_close")
        btn_close.clicked.connect(dialog.accept)
        btn_row3.addWidget(btn_close)
        layout.addLayout(btn_row3)
        
        dialog.exec()
    
    def _get_row_highlight_color(self, score: float):
        """根据关联度返回表格行背景色"""
        from qgis.PyQt.QtGui import QColor, QBrush
        
        if score >= 0.9:
            # 高关联：淡绿色背景
            return QBrush(QColor("#dcfce7"))
        elif score >= 0.8:
            # 中高关联：淡黄绿色背景
            return QBrush(QColor("#ecfccb"))
        elif score >= 0.7:
            # 中等关联：淡黄色背景
            return QBrush(QColor("#fef9c3"))
        else:
            # 低关联：无特殊背景
            return None
    
    def _get_score_color(self, score: float) -> QColor:
        """根据关联度返回渐变色（红→黄→绿）"""
        from qgis.PyQt.QtGui import QColor
        
        if score >= 0.9:
            # 高关联：绿色
            return QColor("#10b981")
        elif score >= 0.8:
            # 中高关联：黄绿色
            return QColor("#84cc16")
        elif score >= 0.7:
            # 中等关联：黄色
            return QColor("#eab308")
        elif score >= 0.6:
            # 中低关联：橙色
            return QColor("#f97316")
        else:
            # 低关联：红色
            return QColor("#ef4444")
    
    def _draw_graph_legend(self):
        """绘制图例"""
        from qgis.PyQt.QtGui import QPen, QBrush, QColor, QFont
        
        legend_x = -70
        legend_y = 180
        
        # 图例标题
        title = self.relation_scene.addText("图例")
        title.setDefaultTextColor(QColor("#374151"))
        font = QFont()
        font.setPointSize(8)
        font.setBold(True)
        title.setFont(font)
        title.setPos(legend_x, legend_y)
        
        # 关联度颜色说明
        legend_items = [
            ("≥0.9 高", "#10b981"),
            ("≥0.8 中高", "#84cc16"),
            ("≥0.7 中", "#eab308"),
            ("<0.7 低", "#f97316"),
        ]
        
        for i, (label, color) in enumerate(legend_items):
            y_offset = legend_y + 18 + i * 14
            
            # 颜色方块
            rect = self.relation_scene.addRect(
                legend_x, y_offset, 10, 10,
                QPen(QColor(color).darker(110), 1),
                QBrush(QColor(color))
            )
            
            # 文字
            text = self.relation_scene.addText(label)
            text.setDefaultTextColor(QColor("#6b7280"))
            font = QFont()
            font.setPointSize(7)
            text.setFont(font)
            text.setPos(legend_x + 14, y_offset - 3)
    
    def _on_graph_wheel_event(self, event):
        """图形视图滚轮缩放"""
        # 缩放因子
        zoom_in_factor = 1.15
        zoom_out_factor = 1 / zoom_in_factor
        
        # 根据滚轮方向缩放
        if event.angleDelta().y() > 0:
            zoom_factor = zoom_in_factor
        else:
            zoom_factor = zoom_out_factor
        
        # 限制缩放范围
        current_scale = self.relation_view.transform().m11()
        if current_scale * zoom_factor < 0.3 or current_scale * zoom_factor > 3.0:
            return
        
        self.relation_view.scale(zoom_factor, zoom_factor)
    
    # ==================== Key 配置相关 ====================
    
    def _load_key_config(self):
        """从 QSettings 加载 Key 配置"""
        settings = QSettings()
        access_key_id = settings.value(self.SETTINGS_KEY_ACCESS_KEY_ID, "")
        access_key_secret = settings.value(self.SETTINGS_KEY_ACCESS_KEY_SECRET, "")
        app_key = settings.value(self.SETTINGS_KEY_APP_KEY, "")
        
        self.edit_access_key_id.setText(access_key_id or "")
        self.edit_access_key_secret.setText(access_key_secret or "")
        self.edit_app_key.setText(app_key or "")
    
    def _on_save_key_config(self):
        """保存 Key 配置到 QSettings"""
        from ..widgets.result_dialog import ResultDialog
        
        access_key_id = self.edit_access_key_id.text().strip()
        access_key_secret = self.edit_access_key_secret.text().strip()
        app_key = self.edit_app_key.text().strip()
        
        if not access_key_id or not access_key_secret or not app_key:
            ResultDialog.show_warning(self, "配置不完整", "请填写完整的配置信息")
            return
        
        settings = QSettings()
        settings.setValue(self.SETTINGS_KEY_ACCESS_KEY_ID, access_key_id)
        settings.setValue(self.SETTINGS_KEY_ACCESS_KEY_SECRET, access_key_secret)
        settings.setValue(self.SETTINGS_KEY_APP_KEY, app_key)
        
        self._log("[Step3] 阿里云 Key 配置已保存", "success")
        ResultDialog.show_success(self, "保存成功", "阿里云 Key 配置已保存到本地")
    
    def _on_test_connection(self):
        """测试 API 连接"""
        from ..widgets.result_dialog import ResultDialog
        
        access_key_id = self.edit_access_key_id.text().strip()
        access_key_secret = self.edit_access_key_secret.text().strip()
        app_key = self.edit_app_key.text().strip()
        
        if not access_key_id or not access_key_secret or not app_key:
            ResultDialog.show_warning(
                self, "配置不完整", 
                "请先填写完整的 AccessKey ID、AccessKey Secret 和 App Key",
                window_title="API 连接测试"
            )
            return
        
        # 获取区域信息
        global_config = self._get_global_config()
        province = ""
        city = ""
        if global_config:
            region_info = global_config.get_region_info()
            province = region_info.get('province', '')
            city = region_info.get('city', '')
        
        try:
            from ...core.ali_address_parser import AliAddressParser
            
            parser = AliAddressParser(
                access_key_id=access_key_id,
                access_key_secret=access_key_secret,
                app_key=app_key,
                default_province=province,
                default_city=city,
                log_callback=self._log
            )
            
            result = parser.test_connection()
            
            if result["success"]:
                self._log("[Step3] API 连接测试成功", "success")
                ResultDialog.show_success(
                    self, "连接成功",
                    "阿里云地址解析 API 配置正确，可以正常使用",
                    detail="💡 提示：解析结果会自动缓存，相同地址不会重复调用 API，节省费用。",
                    window_title="API 连接测试"
                )
            else:
                self._log(f"[Step3] API 连接测试失败: {result['message']}", "error")
                ResultDialog.show_error(
                    self, "连接失败", result["message"],
                    window_title="API 连接测试"
                )
        except ImportError as e:
            self._log(f"[Step3] 模块导入失败: {e}", "error")
            ResultDialog.show_error(self, "模块错误", f"模块导入失败: {e}")
        except Exception as e:
            self._log(f"[Step3] 测试连接异常: {e}", "error")
            ResultDialog.show_error(self, "测试异常", str(e))
    
    # ==================== 解析任务相关 ====================
    
    def _refresh_parse_file_list(self):
        """刷新解析文件列表（从 Step2 清洗输出目录读取）"""
        self.parse_file_list.blockSignals(True)
        self.parse_file_list.clear()
        
        # 获取清洗输出目录
        clean_files = self._get_cleaned_files()
        
        if not clean_files:
            self.parse_file_list.blockSignals(False)
            self._log("[Step3] 未找到已清洗的文件", "warning")
            return
        
        # 加载解析状态
        parse_status = self._load_parse_status()
        
        for file_info in clean_files:
            file_name = file_info["name"]
            file_path = file_info["path"]
            
            # 获取解析状态
            status = parse_status.get(file_name, {})
            parsed = status.get("parsed", False)
            status_text = "已解析" if parsed else "未解析"
            
            # 创建列表项
            item_text = f"{file_name}  [{status_text}]"
            item = QListWidgetItem(item_text)
            item.setData(Qt.ItemDataRole.UserRole, file_path)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            
            # 默认勾选未解析的
            if file_name in self.parse_selected_files:
                is_checked = self.parse_selected_files[file_name]
            else:
                is_checked = not parsed
                self.parse_selected_files[file_name] = is_checked
            
            item.setCheckState(Qt.CheckState.Checked if is_checked else Qt.CheckState.Unchecked)
            
            # 设置颜色
            if parsed:
                item.setForeground(QColor("#15803d"))
            
            self.parse_file_list.addItem(item)
        
        self.parse_file_list.blockSignals(False)
        self._log(f"[Step3] 已刷新文件列表，找到 {len(clean_files)} 个清洗后文件", "info")
    
    def _get_cleaned_files(self) -> List[Dict]:
        """获取已清洗的文件列表"""
        files = []
        
        global_config = self._get_global_config()
        if not global_config:
            return files
        
        region_info = global_config.get_region_info()
        base_folder = region_info.get('base_folder', '')
        province = region_info.get('province', '')
        city = region_info.get('city', '')
        county = region_info.get('county', '')
        
        if not base_folder or not province or not city:
            return files
        
        region_prefix = f"{province}{city}{county}".strip()
        
        # 扫描清洗输出目录
        clean_folders = [
            os.path.join(base_folder, f"{region_prefix}_客户数据清洗", "清洗后数据"),
            os.path.join(base_folder, f"{region_prefix}_GIS数据清洗", "清洗后数据"),
        ]
        
        for folder in clean_folders:
            if os.path.isdir(folder):
                try:
                    for file_name in os.listdir(folder):
                        # 只扫描 _清洗.csv 文件，排除 _标准化.csv
                        if file_name.endswith('_清洗.csv'):
                            files.append({
                                "name": file_name,
                                "path": os.path.join(folder, file_name)
                            })
                except Exception as e:
                    self._log(f"[Step3] 扫描文件夹失败: {e}", "error")
        
        return files
    
    def _on_parse_file_item_changed(self, item: QListWidgetItem):
        """文件选择状态变化"""
        file_path = item.data(Qt.ItemDataRole.UserRole)
        file_name = os.path.basename(file_path) if file_path else ""
        is_checked = item.checkState() == Qt.CheckState.Checked
        
        if file_name:
            self.parse_selected_files[file_name] = is_checked
    
    def _select_all_parse_files(self):
        """全选"""
        self.parse_file_list.blockSignals(True)
        for i in range(self.parse_file_list.count()):
            item = self.parse_file_list.item(i)
            item.setCheckState(Qt.CheckState.Checked)
            file_path = item.data(Qt.ItemDataRole.UserRole)
            file_name = os.path.basename(file_path) if file_path else ""
            if file_name:
                self.parse_selected_files[file_name] = True
        self.parse_file_list.blockSignals(False)
    
    def _deselect_all_parse_files(self):
        """取消全选"""
        self.parse_file_list.blockSignals(True)
        for i in range(self.parse_file_list.count()):
            item = self.parse_file_list.item(i)
            item.setCheckState(Qt.CheckState.Unchecked)
            file_path = item.data(Qt.ItemDataRole.UserRole)
            file_name = os.path.basename(file_path) if file_path else ""
            if file_name:
                self.parse_selected_files[file_name] = False
        self.parse_file_list.blockSignals(False)
    
    def _run_parse_task(self):
        """执行解析任务"""
        from ..widgets.result_dialog import ResultDialog
        import pandas as pd
        
        # 防止重复执行
        if self._is_running:
            self._log("[Step3] 任务正在执行中，请等待完成", "warning")
            return
        
        self._is_running = True
        
        try:
            self._do_parse_task(ResultDialog, pd)
        finally:
            self._is_running = False
    
    def _do_parse_task(self, ResultDialog, pd):
        """实际执行解析任务"""
        # 获取选中的文件
        selected_files = []
        for i in range(self.parse_file_list.count()):
            item = self.parse_file_list.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                file_path = item.data(Qt.ItemDataRole.UserRole)
                if file_path:
                    selected_files.append(file_path)
        
        if not selected_files:
            ResultDialog.show_warning(self, "未选择文件", "请先选择要解析的文件")
            return
        
        # 检查 Key 配置
        access_key_id = self.edit_access_key_id.text().strip()
        access_key_secret = self.edit_access_key_secret.text().strip()
        app_key = self.edit_app_key.text().strip()
        
        if not access_key_id or not access_key_secret or not app_key:
            ResultDialog.show_warning(self, "配置缺失", "请先配置阿里云 Key")
            return
        
        # 获取测试数量限制
        test_limit_text = self.edit_test_limit.text().strip()
        test_limit = None
        if test_limit_text:
            try:
                test_limit = int(test_limit_text)
                if test_limit <= 0:
                    test_limit = None
            except ValueError:
                ResultDialog.show_warning(self, "参数错误", "测试数量必须是正整数")
                return
        
        # 获取区域信息
        global_config = self._get_global_config()
        province = ""
        city = ""
        cache_folder = ""
        if global_config:
            region_info = global_config.get_region_info()
            province = region_info.get('province', '')
            city = region_info.get('city', '')
            cache_folder = region_info.get('cache_folder', '')
        
        self._log(f"[Step3] 开始解析 {len(selected_files)} 个文件", "info")
        if test_limit:
            self._log(f"[Step3] 测试模式：每个文件最多处理 {test_limit} 条", "info")
        
        # 创建解析器
        try:
            from ...core.ali_address_parser import AliAddressParser
            
            parser = AliAddressParser(
                access_key_id=access_key_id,
                access_key_secret=access_key_secret,
                app_key=app_key,
                default_province=province,
                default_city=city,
                cache_folder=cache_folder,
                log_callback=self._log
            )
        except Exception as e:
            self._log(f"[Step3] 创建解析器失败: {e}", "error")
            ResultDialog.show_error(self, "初始化失败", str(e))
            return
        
        # 执行解析
        total_success = 0
        total_fail = 0
        total_cached = 0
        
        for file_idx, file_path in enumerate(selected_files):
            file_name = os.path.basename(file_path)
            self.lbl_parse_status.setText(f"正在解析: {file_name} ({file_idx + 1}/{len(selected_files)})")
            self._log(f"[Step3] 开始解析文件: {file_name}", "info")
            
            try:
                # 读取 CSV
                df = pd.read_csv(file_path, encoding='utf-8-sig')
                
                # 查找清洗后的地址列（以 _adr_clean 结尾）
                adr_clean_cols = [col for col in df.columns if col.endswith('_adr_clean')]
                if not adr_clean_cols:
                    self._log(f"[Step3] 文件 {file_name} 未找到清洗后的地址列（*_adr_clean）", "warning")
                    total_fail += 1
                    continue
                
                adr_col = adr_clean_cols[0]
                self._log(f"[Step3] 使用地址列: {adr_col}", "info")
                
                # 限制处理数量
                if test_limit and len(df) > test_limit:
                    df = df.head(test_limit)
                    self._log(f"[Step3] 测试模式：只处理前 {test_limit} 条", "info")
                
                total_rows = len(df)
                self.parse_progress.setValue(0)
                self.parse_progress.setMaximum(total_rows)
                
                # 只新增两个关键字段
                df['标准化地址'] = ""
                df['标准化POI抽取'] = ""
                
                file_cached = 0
                
                # 逐行解析
                for idx, row in df.iterrows():
                    address = str(row.get(adr_col, "")).strip()
                    
                    if not address:
                        continue
                    
                    # 调用解析（内部会缓存所有结构化字段）
                    result = parser.parse(address)
                    
                    # 只填充两个关键字段
                    df.at[idx, '标准化地址'] = result.get('std_address', '')
                    df.at[idx, '标准化POI抽取'] = result.get('predict_poi', '')
                    
                    if result.get("cached"):
                        file_cached += 1
                    
                    # 更新进度
                    self.parse_progress.setValue(idx + 1)
                    
                    # 处理事件，保持 UI 响应
                    from qgis.PyQt.QtWidgets import QApplication
                    QApplication.processEvents()
                
                # 保存结果
                output_dir = os.path.dirname(file_path)
                output_name = os.path.splitext(file_name)[0] + "_标准化.csv"
                output_path = os.path.join(output_dir, output_name)
                
                df.to_csv(output_path, index=False, encoding='utf-8-sig')
                
                self._log(f"[Step3] 文件 {file_name} 解析完成，缓存命中 {file_cached} 条", "success")
                self._log(f"[Step3] 结果已保存: {output_path}", "info")
                
                # 更新解析状态
                self._save_parse_status(file_name, {
                    "parsed": True,
                    "parse_time": pd.Timestamp.now().isoformat(),
                    "total_rows": total_rows,
                    "cached_rows": file_cached
                })
                
                total_success += 1
                total_cached += file_cached
                
            except Exception as e:
                self._log(f"[Step3] 解析文件 {file_name} 失败: {e}", "error")
                total_fail += 1
        
        # 保存缓存到磁盘
        parser.flush_cache()
        
        # 刷新文件列表
        self._refresh_parse_file_list()
        
        # 显示结果
        self.lbl_parse_status.setText("解析完成")
        self.parse_progress.setValue(self.parse_progress.maximum())
        
        if total_fail == 0:
            ResultDialog.show_success(
                self, "解析完成",
                f"成功解析 {total_success} 个文件",
                detail=f"💡 缓存命中 {total_cached} 条，节省了 API 调用费用"
            )
        else:
            ResultDialog.show_warning(
                self, "部分完成",
                f"成功: {total_success} 个，失败: {total_fail} 个",
                detail="请查看日志了解失败原因"
            )
    
    # ==================== 缓存相关 ====================
    
    def _get_parse_status_file(self) -> str:
        """获取解析状态文件路径"""
        global_config = self._get_global_config()
        if not global_config:
            return ""
        
        region_info = global_config.get_region_info()
        cache_folder = region_info.get('cache_folder', '')
        if not cache_folder:
            return ""
        
        return os.path.join(cache_folder, "parse_status.json")
    
    def _load_parse_status(self) -> Dict:
        """加载解析状态"""
        status_file = self._get_parse_status_file()
        if not status_file or not os.path.exists(status_file):
            return {}
        
        try:
            with open(status_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    
    def _save_parse_status(self, file_name: str, status: Dict):
        """保存解析状态"""
        status_file = self._get_parse_status_file()
        if not status_file:
            return
        
        all_status = self._load_parse_status()
        all_status[file_name] = status
        
        try:
            os.makedirs(os.path.dirname(status_file), exist_ok=True)
            with open(status_file, 'w', encoding='utf-8') as f:
                json.dump(all_status, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self._log(f"[Step3] 保存解析状态失败: {e}", "error")
    
    # ==================== 通用方法 ====================
    
    def _get_global_config(self):
        """获取全局配置组件"""
        parent = self.parent()
        while parent:
            if hasattr(parent, 'global_config'):
                return parent.global_config
            parent = parent.parent()
        return None
    
    # ==================== 清除数据功能 ====================
    
    def _show_clear_dialog(self):
        """显示清除数据对话框"""
        from qgis.PyQt.QtWidgets import (
            QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
            QCheckBox, QPushButton, QFrame, QSpacerItem, QSizePolicy
        )
        from ..widgets.result_dialog import ResultDialog
        
        dialog = QDialog(self)
        dialog.setWindowTitle("清除数据")
        dialog.setMinimumWidth(400)
        dialog.setObjectName("step3_clear_dialog")
        
        # 移除帮助按钮
        try:
            dialog.setWindowFlags(dialog.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)
        except:
            pass
        
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)
        
        # 标题图标
        title_row = QHBoxLayout()
        icon_label = QLabel("🗑️")
        icon_label.setObjectName("clear_dialog_icon")
        title_row.addWidget(icon_label)
        
        title_text = QLabel("选择要清除的数据")
        title_text.setObjectName("clear_dialog_title")
        title_row.addWidget(title_text)
        title_row.addStretch()
        layout.addLayout(title_row)
        
        # 分隔线
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setObjectName("clear_dialog_separator")
        layout.addWidget(line)
        
        # 选项区域
        options_widget = QWidget()
        options_layout = QVBoxLayout(options_widget)
        options_layout.setContentsMargins(0, 0, 0, 0)
        options_layout.setSpacing(12)
        
        # API 缓存选项
        self.chk_clear_api_cache = QCheckBox("清除 API 调用缓存")
        self.chk_clear_api_cache.setObjectName("clear_dialog_checkbox")
        tip1 = QLabel("包括内存缓存和磁盘缓存（api_cache.json），清除后重新解析需要调用 API")
        tip1.setObjectName("clear_dialog_tip")
        tip1.setWordWrap(True)
        options_layout.addWidget(self.chk_clear_api_cache)
        options_layout.addWidget(tip1)
        
        # 标准化文件选项
        self.chk_clear_parsed_files = QCheckBox("清除已标准化的文件")
        self.chk_clear_parsed_files.setObjectName("clear_dialog_checkbox")
        tip2 = QLabel("删除所有 *_标准化.csv 文件，保留原始清洗后的文件")
        tip2.setObjectName("clear_dialog_tip")
        tip2.setWordWrap(True)
        options_layout.addWidget(self.chk_clear_parsed_files)
        options_layout.addWidget(tip2)
        
        # 解析状态选项
        self.chk_clear_parse_status = QCheckBox("清除解析状态记录")
        self.chk_clear_parse_status.setObjectName("clear_dialog_checkbox")
        tip3 = QLabel("清除 parse_status.json，文件列表中的解析状态将重置")
        tip3.setObjectName("clear_dialog_tip")
        tip3.setWordWrap(True)
        options_layout.addWidget(self.chk_clear_parse_status)
        options_layout.addWidget(tip3)
        
        layout.addWidget(options_widget)
        
        # 警告提示
        warning = QLabel("⚠️ 此操作不可撤销，请谨慎选择")
        warning.setObjectName("clear_dialog_warning")
        layout.addWidget(warning)
        
        layout.addSpacerItem(QSpacerItem(20, 10, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding))
        
        # 按钮行
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        
        btn_cancel = QPushButton("取消")
        btn_cancel.setMinimumWidth(80)
        btn_cancel.clicked.connect(dialog.reject)
        btn_row.addWidget(btn_cancel)
        
        btn_confirm = QPushButton("确认清除")
        btn_confirm.setObjectName("clear_dialog_btn_confirm")
        btn_confirm.setMinimumWidth(100)
        btn_confirm.clicked.connect(lambda: self._execute_clear(dialog))
        btn_row.addWidget(btn_confirm)
        
        layout.addLayout(btn_row)
        
        dialog.exec()
    
    def _execute_clear(self, dialog):
        """执行清除操作"""
        from ..widgets.result_dialog import ResultDialog
        
        clear_api = self.chk_clear_api_cache.isChecked()
        clear_files = self.chk_clear_parsed_files.isChecked()
        clear_status = self.chk_clear_parse_status.isChecked()
        
        if not clear_api and not clear_files and not clear_status:
            ResultDialog.show_warning(self, "未选择项目", "请至少选择一项要清除的数据")
            return
        
        dialog.accept()
        
        results = []
        errors = []
        
        # 清除 API 缓存
        if clear_api:
            try:
                cleared = self._clear_api_cache()
                results.append(f"API 缓存：{cleared}")
            except Exception as e:
                errors.append(f"API 缓存清除失败: {e}")
        
        # 清除标准化文件
        if clear_files:
            try:
                count = self._clear_parsed_files()
                results.append(f"标准化文件：删除 {count} 个")
            except Exception as e:
                errors.append(f"标准化文件清除失败: {e}")
        
        # 清除解析状态
        if clear_status:
            try:
                self._clear_parse_status()
                results.append("解析状态：已清除")
            except Exception as e:
                errors.append(f"解析状态清除失败: {e}")
        
        # 刷新文件列表
        self._refresh_parse_file_list()
        
        # 显示结果
        if errors:
            ResultDialog.show_warning(
                self, "清除完成（部分失败）",
                "\n".join(results),
                detail="\n".join(errors)
            )
        else:
            ResultDialog.show_success(
                self, "清除完成",
                "\n".join(results)
            )
    
    def _clear_api_cache(self) -> str:
        """清除 API 缓存"""
        # 获取缓存目录
        global_config = self._get_global_config()
        if not global_config:
            return "未配置"
        
        region_info = global_config.get_region_info()
        cache_folder = region_info.get('cache_folder', '')
        
        cleared_count = 0
        
        # 清除磁盘缓存文件
        if cache_folder:
            cache_file = os.path.join(cache_folder, "api_cache.json")
            if os.path.exists(cache_file):
                try:
                    with open(cache_file, 'r', encoding='utf-8') as f:
                        cache_data = json.load(f)
                        cleared_count = len(cache_data)
                except:
                    pass
                os.remove(cache_file)
                self._log(f"[Step3] 已删除 API 缓存文件: {cache_file}", "info")
        
        return f"已清除 {cleared_count} 条缓存记录"
    
    def _clear_parsed_files(self) -> int:
        """清除已标准化的文件"""
        global_config = self._get_global_config()
        if not global_config:
            return 0
        
        region_info = global_config.get_region_info()
        base_folder = region_info.get('base_folder', '')
        province = region_info.get('province', '')
        city = region_info.get('city', '')
        county = region_info.get('county', '')
        
        if not base_folder:
            return 0
        
        deleted_count = 0
        
        # 遍历清洗目录（包括子目录 清洗后数据）
        for source_type in ['客户数据清洗', 'GIS数据清洗']:
            region_prefix = f"{province}{city}{county}".strip()
            clean_folder = os.path.join(base_folder, f"{region_prefix}_{source_type}")
            
            # 扫描清洗目录及其子目录
            folders_to_scan = [clean_folder]
            data_folder = os.path.join(clean_folder, "清洗后数据")
            if os.path.exists(data_folder):
                folders_to_scan.append(data_folder)
            
            for folder in folders_to_scan:
                if not os.path.exists(folder):
                    continue
                
                # 查找并删除所有包含 _标准化 的 .csv 文件
                try:
                    for file_name in os.listdir(folder):
                        if "_标准化" in file_name and file_name.endswith(".csv"):
                            file_path = os.path.join(folder, file_name)
                            try:
                                os.remove(file_path)
                                deleted_count += 1
                                self._log(f"[Step3] 已删除: {file_path}", "info")
                            except Exception as e:
                                self._log(f"[Step3] 删除失败: {file_path}, {e}", "error")
                except Exception as e:
                    self._log(f"[Step3] 扫描目录失败: {folder}, {e}", "error")
        
        return deleted_count
    
    def _clear_parse_status(self):
        """清除解析状态"""
        status_file = self._get_parse_status_file()
        if status_file and os.path.exists(status_file):
            os.remove(status_file)
            self._log(f"[Step3] 已删除解析状态文件: {status_file}", "info")
