"""
Step5: 导出Widget
包含：结果导出
（日志面板已在主对话框中）
"""
from typing import Callable, Optional
from qgis.PyQt.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel, QLineEdit,
    QPushButton, QCheckBox, QProgressBar, QFileDialog
)
from ..widgets.base_step_widget import BaseStepWidget


class Step5Widget(BaseStepWidget):
    """Step5: 导出"""
    
    def __init__(self, parent=None, log_callback: Optional[Callable[[str, str], None]] = None, 
                 task_manager=None, log_panel=None):
        # log_panel 参数保留以兼容，但不再使用（日志面板在主对话框中）
        super().__init__(parent, log_callback, task_manager)
        self._build_ui()
        # 设置尺寸策略，让Step5Widget能够扩展填满可用空间
        self._set_expanding_size_policy()
    
    def _set_expanding_size_policy(self):
        """设置Step5Widget的尺寸策略为Expanding"""
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
    
    def _set_groupbox_expanding(self, box: QGroupBox):
        """为QGroupBox设置水平扩展尺寸策略"""
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
            box.setSizePolicy(expanding, preferred)  # 水平扩展，垂直Preferred
        except (AttributeError, TypeError):
            box.setSizePolicy(7, 1)  # Expanding, Preferred
    
    def _build_ui(self):
        """构建UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 6, 0, 6)  # 移除左右边距，由父容器统一控制
        
        # 日志面板已在主对话框中，这里只显示导出功能
        layout.addWidget(self._card_export())
        # 移除addStretch，让内容充分利用空间
    
    def _card_export(self) -> QGroupBox:
        """结果导出"""
        box = QGroupBox("结果导出")
        self._set_groupbox_expanding(box)
        v = QVBoxLayout(box)
        v.addWidget(QLabel("按类型导出：清洗结果、标准化结果、匹配结果、未匹配数据、关联关系表等。"))
        
        export_options = QVBoxLayout()
        self.chk_export_clean = QCheckBox("清洗结果（*_clean.*）")
        self.chk_export_clean.setChecked(True)
        export_options.addWidget(self.chk_export_clean)
        
        self.chk_export_std = QCheckBox("标准化结果（*_std.*）")
        self.chk_export_std.setChecked(True)
        export_options.addWidget(self.chk_export_std)
        
        self.chk_export_match = QCheckBox("匹配结果（按任务组 & 源→目标输出）")
        self.chk_export_match.setChecked(True)
        export_options.addWidget(self.chk_export_match)
        
        self.chk_export_unmatched = QCheckBox("未匹配数据（按源表输出）")
        self.chk_export_unmatched.setChecked(True)
        export_options.addWidget(self.chk_export_unmatched)
        
        self.chk_export_relations = QCheckBox("字段关联关系（智能关联结果表）")
        self.chk_export_relations.setChecked(True)
        export_options.addWidget(self.chk_export_relations)
        
        v.addLayout(export_options)
        
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("输出根目录"))
        self.edit_export = QLineEdit("D:/qgis_addr_output/run_demo/")
        row2.addWidget(self.edit_export)
        btn_browse_export = QPushButton("浏览...")
        btn_browse_export.setStyleSheet("font-size: 12px; padding: 4px 8px;")
        btn_browse_export.clicked.connect(self._on_browse_export_dir)
        row2.addWidget(btn_browse_export)
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
        
        task_mgr = self.get_task_manager()
        btn_run.clicked.connect(lambda: task_mgr.start_task("export", self.bar_export, self.lbl_export, "导出结果文件..."))
        btn_pause.clicked.connect(lambda: task_mgr.pause_task("export", self.lbl_export))
        btn_stop.clicked.connect(lambda: task_mgr.stop_task("export", self.bar_export, self.lbl_export))
        
        return box
    
    def _on_browse_export_dir(self):
        """浏览导出目录"""
        path = QFileDialog.getExistingDirectory(self, "选择输出根目录", self.edit_export.text())
        if path:
            self.edit_export.setText(path)
            self._log(f"[Step5] 选择导出目录：{path}")

