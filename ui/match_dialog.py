"""
重构后的主对话框 - 只负责布局和协调
"""
from datetime import datetime
from typing import Dict, Callable, Optional
from qgis.PyQt.QtWidgets import (
    QDialog, QHBoxLayout, QVBoxLayout, QWidget, QLabel, QListWidget,
    QListWidgetItem, QTextEdit, QScrollArea, QSplitter, QGroupBox
)
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QFont

from .steps import Step1Widget, Step2Widget, Step3Widget, Step4Widget, Step5Widget
from .modals import FilterModal, MatchModal
from .widgets import TaskManager, GlobalConfigWidget
from .styles import StyleManager
from .collapsible_section import CollapsibleSection


class MatchDialog(QDialog):
    """主对话框 - 只负责布局和协调"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("地址清洗与多源匹配")
        self.resize(1200, 800)
        
        # 设置高DPI支持，提高清晰度
        try:
            from qgis.PyQt.QtCore import Qt
            self.setAttribute(Qt.WA_UseHighDpiPixmaps, True)
        except:
            pass

        # 共享的任务管理器
        self.task_manager = TaskManager(self)
        
        # 全局配置组件
        self.global_config = None
        
        # 日志面板（公共组件）
        self.log_panel = None
        
        # 模态对话框
        self.filter_modal = FilterModal(self)
        self.match_modal = MatchModal(self)

        self._build_ui()
        self._apply_styles()

        # 初始化状态
        self._current_step = 2
        self._switch_step(2)

    def _build_ui(self):
        """构建主UI：侧边栏导航 + 主内容区"""
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # 左侧边栏
        self._build_sidebar(main_layout)
        
        # 右侧主内容区
        self._build_main_content(main_layout)
    
    def _build_sidebar(self, main_layout: QHBoxLayout):
        """构建左侧边栏导航 - 样式由 styles.qss 管理"""
        sidebar = QWidget()
        sidebar.setFixedWidth(230)
        sidebar.setObjectName("sidebar")
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_layout.setSpacing(0)
        
        # 标题
        header = QLabel("地址清洗 & 多源匹配插件")
        header.setObjectName("sidebar_header")
        sidebar_layout.addWidget(header)
        
        # 步骤列表
        self.step_list = QListWidget()
        self.step_list.setObjectName("step_list")
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
        footer.setObjectName("sidebar_footer")
        footer.setWordWrap(True)
        sidebar_layout.addWidget(footer)
        
        main_layout.addWidget(sidebar)
    
    def _build_main_content(self, main_layout: QHBoxLayout):
        """构建右侧主内容区"""
        # 使用垂直分割器：上方是主内容，下方是日志面板
        # 安全获取 Vertical 方向
        try:
            if hasattr(Qt, 'Orientation') and hasattr(Qt.Orientation, 'Vertical'):
                orientation = Qt.Orientation.Vertical
            elif hasattr(Qt, 'Vertical'):
                orientation = Qt.Vertical
            else:
                # 使用数值常量：Vertical = 1
                orientation = 1
        except (AttributeError, TypeError):
            orientation = 1
        
        main_splitter = QSplitter(orientation)
        main_splitter.setObjectName("main_splitter")
        
        # 上方主内容区
        main_widget = QWidget()
        main_widget.setObjectName("main_content")
        main_content_layout = QVBoxLayout(main_widget)
        main_content_layout.setContentsMargins(0, 0, 0, 0)
        main_content_layout.setSpacing(0)
        
        # 标题栏
        header_widget = QWidget()
        header_widget.setObjectName("header_widget")
        header_layout = QVBoxLayout(header_widget)
        header_layout.setContentsMargins(10, 10, 10, 10)
        
        self.header_title = QLabel("Step2 字段映射与清洗")
        self.header_title.setObjectName("header_title")
        header_layout.addWidget(self.header_title)
        
        self.header_subtitle = QLabel("为每个文件配置多个字段组合，一次性批量清洗。")
        self.header_subtitle.setObjectName("header_subtitle")
        header_layout.addWidget(self.header_subtitle)
        
        main_content_layout.addWidget(header_widget)
        
        # 全局配置组件（在所有步骤中都可见，可折叠）
        self.global_config_section = CollapsibleSection("数据范围与目录（全局配置）", expanded=True)
        self.global_config = GlobalConfigWidget(self, self._log)
        self.global_config.region_changed.connect(self._on_region_changed)
        # 移除 GlobalConfigWidget 的 QGroupBox，直接使用内容
        self.global_config_section.add_widget(self.global_config)
        main_content_layout.addWidget(self.global_config_section)
        
        # 内容滚动区
        scroll = QScrollArea()
        scroll.setObjectName("content_scroll")
        scroll.setWidgetResizable(True)
        
        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(12, 12, 12, 12)
        self.content_layout.setSpacing(12)
        
        # 创建所有步骤的内容（初始隐藏）
        self.step_widgets: Dict[int, QWidget] = {}
        
        # 创建Step Widgets（传入日志回调和任务管理器）
        self.step_widgets[1] = Step1Widget(self, self._log, self.task_manager)
        self.step_widgets[2] = Step2Widget(self, self._log, self.task_manager)
        self.step_widgets[3] = Step3Widget(self, self._log, self.task_manager)
        self.step_widgets[4] = Step4Widget(
            self, self._log, self.task_manager,
            open_filter_modal=self._open_filter_modal,
            open_match_modal=self._open_match_modal
        )
        
        # Step5不需要日志面板（因为日志面板已经在主对话框中）
        step5 = Step5Widget(self, self._log, self.task_manager, log_panel=None)
        self.step_widgets[5] = step5
        
        for i, widget in self.step_widgets.items():
            self.content_layout.addWidget(widget)
            widget.setVisible(False)
        
        scroll.setWidget(self.content_widget)
        main_content_layout.addWidget(scroll)
        
        main_splitter.addWidget(main_widget)
        
        # 下方日志面板（公共组件，所有步骤可见）
        log_box = QGroupBox("执行日志（所有步骤）")
        log_box.setObjectName("log_panel_group")
        log_layout = QVBoxLayout(log_box)
        log_layout.setContentsMargins(8, 8, 8, 8)
        
        self.log_panel = QTextEdit()
        self.log_panel.setObjectName("log_panel")
        self.log_panel.setReadOnly(True)
        self.log_panel.setMinimumHeight(150)
        # 设置字体以提高清晰度
        font = QFont("Consolas", 11)
        # 安全获取 Monospace StyleHint（兼容不同PyQt版本）
        try:
            if hasattr(QFont, 'StyleHint') and hasattr(QFont.StyleHint, 'Monospace'):
                font.setStyleHint(QFont.StyleHint.Monospace)
            else:
                font.setStyleHint(7)
        except (AttributeError, TypeError):
            font.setStyleHint(7)
        self.log_panel.setFont(font)
        log_layout.addWidget(self.log_panel)
        
        # 直接将 log_box 添加到 splitter（QGroupBox 本身就是 QWidget）
        main_splitter.addWidget(log_box)
        
        # 设置分割器比例（主内容区占70%，日志占30%）
        main_splitter.setSizes([560, 240])
        
        main_layout.addWidget(main_splitter, 1)
    
    def _apply_styles(self):
        """应用样式 - 通过 StyleManager 统一加载 QSS"""
        try:
            qss = StyleManager.load_qss()
            if qss:
                self.setStyleSheet(qss)
        except Exception:
            pass
        
        # 应用表格自动调整列宽（这是逻辑，不是样式）
        from qgis.PyQt.QtWidgets import QTableWidget
        from .utils import auto_resize_table_columns
        for widget in self.findChildren(QTableWidget):
            widget.setAlternatingRowColors(True)
            auto_resize_table_columns(widget, min_col_width=80, max_col_width=400)
    
    def _on_region_changed(self):
        """区域改变时的回调"""
        if self.global_config is not None:
            try:
            region_info = self.global_config.get_region_info()
            self._log(f"[全局配置] 区域已切换：{region_info.get('province', '')} - {region_info.get('city', '')}", "info")
            except Exception as e:
                self._log(f"[全局配置] 获取区域信息失败：{e}", "error")
    
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
    
    def _log(self, msg: str, level: str = "info"):
        """添加日志 - 统一日志入口"""
        if self.log_panel:
            timestamp = datetime.now().strftime("%H:%M:%S")
            level_upper = level.upper()
            
            # QGIS风格的日志颜色：深色文字，不同级别用不同颜色
            color_map = {
                "info": "#000000",
                "success": "#006400",
                "error": "#cc0000",
                "warn": "#ff8c00",
            }
            color = color_map.get(level, "#9ca3af")
            
            log_text = f'<span style="color: {color};">[{level_upper} {timestamp}] {msg}</span>'
            self.log_panel.append(log_text)
            
            scrollbar = self.log_panel.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())
    
    def _open_filter_modal(self, target_name: str):
        """打开过滤条件模态对话框"""
        if self.filter_modal is not None:
            try:
        self.filter_modal.set_target_name(target_name)
        self.filter_modal.exec_()
            except Exception as e:
                self._log(f"[错误] 打开过滤条件对话框失败：{e}", "error")
    
    def _open_match_modal(self, target_name: str):
        """打开字段匹配对模态对话框"""
        if self.match_modal is not None:
            try:
        self.match_modal.set_target_name(target_name)
        self.match_modal.exec_()
            except Exception as e:
                self._log(f"[错误] 打开字段匹配对话框失败：{e}", "error")
