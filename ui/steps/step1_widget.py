"""
Step1: 文件导入Widget
包含：数据源列表、SHP转换辅助
（全局范围配置已移到主对话框）
"""
from typing import Callable, Optional
from qgis.PyQt.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel, QLineEdit,
    QPushButton, QComboBox, QTableWidget, QTableWidgetItem, QCheckBox,
    QProgressBar, QFileDialog, QAbstractItemView
)
from qgis.PyQt.QtGui import QColor
from qgis.PyQt.QtCore import Qt
from ..utils import safe_select_rows, set_resize_mode
from ..widgets.base_step_widget import BaseStepWidget


class Step1Widget(BaseStepWidget):
    """Step1: 文件导入"""
    
    def __init__(self, parent=None, log_callback: Optional[Callable[[str, str], None]] = None, 
                 task_manager=None):
        super().__init__(parent, log_callback, task_manager)
        self._build_ui()
    
    def _build_ui(self):
        """构建UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        
        # 全局配置已移到主对话框，这里不再显示
        layout.addWidget(self._card_data_sources())
        layout.addWidget(self._card_shp_helper())
        layout.addStretch()
    
    def _card_data_sources(self) -> QGroupBox:
        """数据源文件列表"""
        box = QGroupBox("数据源文件列表")
        v = QVBoxLayout(box)
        v.addWidget(QLabel("示例：多源异构文件（客户采集、补录、GIS 等），标记参与任务与当前状态。"))
        
        btn_row = QHBoxLayout()
        btn_add = QPushButton("添加文件")
        btn_add.setStyleSheet("font-size: 12px; padding: 4px 8px;")
        btn_del = QPushButton("移除选中")
        btn_del.setStyleSheet("font-size: 12px; padding: 4px 8px;")
        btn_ref = QPushButton("刷新")
        btn_ref.setStyleSheet("font-size: 12px; padding: 4px 8px;")
        btn_row.addWidget(btn_add)
        btn_row.addWidget(btn_del)
        btn_row.addWidget(btn_ref)
        btn_row.addStretch()
        v.addLayout(btn_row)
        
        self.data_sources_table = QTableWidget(4, 6)
        self.data_sources_table.setHorizontalHeaderLabels(["选择", "文件名", "来源类型", "参与任务", "字段组合数", "清洗状态"])
        safe_select_rows(self.data_sources_table)
        from ..utils import safe_no_edit
        safe_no_edit(self.data_sources_table)
        header = self.data_sources_table.horizontalHeader()
        for i in range(6):
            set_resize_mode(header, i, prefer_contents=(i in (0, 3)))
        
        # 数据源数据
        data_sources = [
            {"name": "客户采集数据_2025Q1.csv", "type": "客户采集数据", "participate": True, "combos": "2 个组合", "cleaned": "已清洗"},
            {"name": "小区地址库.xlsx", "type": "其他", "participate": True, "combos": "1 个组合", "cleaned": "未清洗"},
            {"name": "补录地址库_现场.csv", "type": "客户采集数据", "participate": True, "combos": "1 个组合", "cleaned": "未清洗"},
            {"name": "管网GIS_小区点位.shp", "type": "GIS 数据", "participate": True, "combos": "1 个组合", "cleaned": "已清洗"},
        ]
        
        for r, data in enumerate(data_sources):
            chk = QCheckBox()
            chk.setChecked(True)
            self.data_sources_table.setCellWidget(r, 0, chk)
            self.data_sources_table.setItem(r, 1, QTableWidgetItem(data["name"]))
            
            type_combo = QComboBox()
            type_combo.addItems(["客户采集数据", "GIS 数据", "其他"])
            type_combo.setCurrentText(data["type"])
            self.data_sources_table.setCellWidget(r, 2, type_combo)
            
            chk_participate = QCheckBox("参与")
            chk_participate.setChecked(data["participate"])
            self.data_sources_table.setCellWidget(r, 3, chk_participate)
            
            self.data_sources_table.setItem(r, 4, QTableWidgetItem(data["combos"]))
            
            status_item = QTableWidgetItem(data["cleaned"])
            if data["cleaned"] == "已清洗":
                status_item.setForeground(QColor("#15803d"))
            self.data_sources_table.setItem(r, 5, status_item)
        
        v.addWidget(self.data_sources_table)
        v.addWidget(QLabel("这里只是\"任务参与的文件池\"，真正字段拼接和清洗逻辑在 Step2 按文件配置。"))
        
        btn_add.clicked.connect(lambda: self._log("[Step1] 添加文件（示意）"))
        btn_del.clicked.connect(lambda: self._log("[Step1] 移除选中（示意）"))
        btn_ref.clicked.connect(lambda: self._log("[Step1] 刷新（示意）"))
        
        return box
    
    def _card_shp_helper(self) -> QGroupBox:
        """SHP转换辅助"""
        box = QGroupBox("辅助：shp → Excel 转换")
        v = QVBoxLayout(box)
        v.addWidget(QLabel("将 GIS 图层转表，方便后续统一以\"表\"的视角做字段操作。"))
        row = QHBoxLayout()
        row.addWidget(QLabel("选择 shp 文件或文件夹"))
        self.edit_shp_src = QLineEdit("D:/qgis/layers/")
        row.addWidget(self.edit_shp_src)
        btn_browse = QPushButton("浏览...")
        btn_browse.setStyleSheet("font-size: 12px; padding: 4px 8px;")
        btn_browse.clicked.connect(self._on_browse_shp)
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
        
        task_mgr = self.get_task_manager()
        btn_run.clicked.connect(lambda: task_mgr.start_task("shp", self.bar_shp, self.lbl_shp, "批量 shp→Excel..."))
        btn_pause.clicked.connect(lambda: task_mgr.pause_task("shp", self.lbl_shp))
        btn_stop.clicked.connect(lambda: task_mgr.stop_task("shp", self.bar_shp, self.lbl_shp))
        
        return box
    
    def _on_browse_shp(self):
        """浏览SHP文件或文件夹"""
        path = QFileDialog.getExistingDirectory(self, "选择 shp 文件或文件夹", self.edit_shp_src.text())
        if path:
            self.edit_shp_src.setText(path)
            self._log(f"[Step1] 选择SHP路径：{path}")
    
