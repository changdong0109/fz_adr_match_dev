"""
Step3: 标准化解析与关联Widget
包含：Key配置、解析任务、关联关系识别
"""
from typing import Callable, List, Optional
from qgis.PyQt.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel, QLineEdit,
    QPushButton, QTableWidget, QTableWidgetItem, QCheckBox,
    QProgressBar, QTextEdit, QAbstractItemView
)
from qgis.PyQt.QtGui import QColor
from ..utils import safe_select_rows, safe_no_edit, set_resize_mode
from ..widgets.base_step_widget import BaseStepWidget


class Step3Widget(BaseStepWidget):
    """Step3: 标准化解析与关联"""
    
    def __init__(self, parent=None, log_callback: Optional[Callable[[str, str], None]] = None, 
                 task_manager=None):
        self.parse_bars: List[QProgressBar] = []
        super().__init__(parent, log_callback, task_manager)
        self._build_ui()
    
    def _build_ui(self):
        """构建UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        
        layout.addWidget(self._card_key())
        layout.addWidget(self._card_parse())
        layout.addWidget(self._card_relations())
        layout.addStretch()
    
    def _card_key(self) -> QGroupBox:
        """阿里云解析Key配置"""
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
        """选择已清洗文件，执行标准化解析"""
        box = QGroupBox("选择已清洗文件，执行标准化解析")
        v = QVBoxLayout(box)
        v.addWidget(QLabel("多文件可并行解析，命中缓存的不再调用外部接口。"))
        
        parse_table = QTableWidget(3, 4)
        parse_table.setHorizontalHeaderLabels(["选择", "文件名", "状态", "进度"])
        safe_select_rows(parse_table)
        from ..utils import safe_no_edit
        safe_no_edit(parse_table)
        header = parse_table.horizontalHeader()
        for i in range(4):
            set_resize_mode(header, i, prefer_contents=(i == 0))
        
        files = [
            {"selected": True, "name": "客户采集数据_2025Q1_clean.csv", "status": "未解析", "progress": 0},
            {"selected": True, "name": "小区地址库_clean.xlsx", "status": "部分缓存", "progress": 0},
            {"selected": False, "name": "补录地址库_clean.csv", "status": "已解析", "progress": 100},
        ]
        
        self.parse_bars = []
        for r, file_data in enumerate(files):
            chk = QCheckBox()
            chk.setChecked(file_data["selected"])
            parse_table.setCellWidget(r, 0, chk)
            
            parse_table.setItem(r, 1, QTableWidgetItem(file_data["name"]))
            
            status_item = QTableWidgetItem(file_data["status"])
            if file_data["status"] == "已解析":
                status_item.setForeground(QColor("#15803d"))
            parse_table.setItem(r, 2, status_item)
            
            bar = QProgressBar()
            bar.setValue(file_data["progress"])
            bar.setStyleSheet("""
                QProgressBar {
                    border: 1px solid #d1d5db;
                    border-radius: 3px;
                    text-align: center;
                    height: 7px;
                }
                QProgressBar::chunk {
                    background: linear-gradient(90deg, #2563eb, #1d4ed8);
                    border-radius: 3px;
                }
            """)
            self.parse_bars.append(bar)
            parse_table.setCellWidget(r, 3, bar)
        
        v.addWidget(parse_table)
        row = QHBoxLayout()
        btn_run = QPushButton("解析选中")
        btn_pause = QPushButton("全部暂停")
        btn_stop = QPushButton("全部终止")
        row.addWidget(btn_run)
        row.addWidget(btn_pause)
        row.addWidget(btn_stop)
        row.addStretch()
        v.addLayout(row)
        
        task_mgr = self.get_task_manager()
        btn_run.clicked.connect(self._run_parse_demo)
        btn_pause.clicked.connect(lambda: task_mgr.pause_task("parse", None))
        btn_stop.clicked.connect(lambda: task_mgr.stop_task("parse", None, None))
        
        return box
    
    def _card_relations(self) -> QGroupBox:
        """智能关联关系识别"""
        box = QGroupBox("智能关联关系识别（字段层级）")
        v = QVBoxLayout(box)
        v.addWidget(QLabel("不参与匹配逻辑，纯展示：根据字段值特征自动识别潜在关联，作为你手工选字段时的参考。"))
        
        btn_refresh = QPushButton("刷新关联关系")
        btn_refresh.setStyleSheet("""
            QPushButton {
                padding: 4px 8px;
                font-size: 12px;
                background-color: #2563eb;
                color: white;
                border: none;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #1d4ed8;
            }
        """)
        v.addWidget(btn_refresh)
        
        row_layout = QHBoxLayout()
        
        left_col = QWidget()
        left_layout = QVBoxLayout(left_col)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.addWidget(QLabel("字段列表（示例）"))
        
        field_table = QTableWidget(5, 2)
        field_table.setHorizontalHeaderLabels(["文件", "字段"])
        safe_select_rows(field_table)
        safe_no_edit(field_table)
        header = field_table.horizontalHeader()
        for i in range(2):
            set_resize_mode(header, i, prefer_contents=False)
        fields = [
            ("客户采集数据_2025Q1_std.csv", "std_full_addr"),
            ("客户采集数据_2025Q1_std.csv", "customer_name"),
            ("小区地址库_std.xlsx", "community_name"),
            ("GIS_小区点位_std.shp", "poi_name"),
            ("门牌库_市政_std.csv", "mp_full_addr"),
        ]
        for r, row in enumerate(fields):
            for c, val in enumerate(row):
                field_table.setItem(r, c, QTableWidgetItem(val))
        left_layout.addWidget(field_table)
        row_layout.addWidget(left_col, 1)
        
        right_col = QWidget()
        right_layout = QVBoxLayout(right_col)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.addWidget(QLabel("字段关联图（示意）"))
        
        self.graph_placeholder = QTextEdit("（示意）已刷新字段关联图 —— 实际实现时可用 Canvas/SVG 绘制力导图。")
        self.graph_placeholder.setReadOnly(True)
        self.graph_placeholder.setMinimumHeight(220)
        self.graph_placeholder.setStyleSheet("""
            QTextEdit {
                border: 1px dashed #d1d5db;
                border-radius: 4px;
                background: #f9fafb;
                font-size: 12px;
                color: #9ca3af;
            }
        """)
        right_layout.addWidget(self.graph_placeholder)
        row_layout.addWidget(right_col, 2)
        
        v.addLayout(row_layout)
        
        v.addWidget(QLabel("高关联字段对列表（样例）"))
        rel_table = QTableWidget(3, 3)
        rel_table.setHorizontalHeaderLabels(["字段 A", "字段 B", "关联度"])
        safe_select_rows(rel_table)
        safe_no_edit(rel_table)
        set_resize_mode(rel_table.horizontalHeader(), 0, prefer_contents=False)
        for i in range(1, 3):
            set_resize_mode(rel_table.horizontalHeader(), i, prefer_contents=False)
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
    
    def _run_parse_demo(self):
        """运行解析演示"""
        from qgis.PyQt.QtWidgets import QLabel
        task_mgr = self.get_task_manager()
        for idx, bar in enumerate(self.parse_bars):
            lbl = QLabel()
            task_mgr.start_task(f"parse{idx}", bar, lbl, f"解析文件{idx+1}...")
    
    def _refresh_relations(self):
        """刷新关联关系"""
        self.graph_placeholder.setPlainText("（示意）已刷新字段关联图 —— 实际实现时可用 Canvas/SVG 绘制力导图。")
        self._log("[关联] 刷新字段关联关系（示意）。")

