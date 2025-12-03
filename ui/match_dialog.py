"""
重构后的主对话框 - 只负责布局和协调
"""
from datetime import datetime
from typing import Dict, Callable, Optional
from qgis.PyQt.QtWidgets import (
    QDialog, QHBoxLayout, QVBoxLayout, QWidget, QLabel, QListWidget,
    QListWidgetItem, QTextEdit, QScrollArea, QGroupBox
)
from qgis.PyQt.QtCore import QEvent, Qt
from qgis.PyQt.QtGui import QFont, QCloseEvent

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
        
        # 设置模态对话框的全局配置
        if self.global_config:
            self.filter_modal.set_global_config(self.global_config)

        # 初始化状态：默认显示Step1
        self._current_step = 1
        self._initialized = False  # 标记初始化状态
        self._switch_step(1)
        self._initialized = True  # 标记初始化完成

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
        """构建左侧边栏导航 - 符合QGIS原生开发标准"""
        # QGIS原生标准：使用系统调色板，简洁设计
        sidebar = QWidget()
        sidebar.setFixedWidth(180)  # QGIS标准侧边栏宽度（通常180-200px）
        sidebar.setObjectName("sidebar")
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_layout.setSpacing(0)
        
        # 标题区域（QGIS原生风格：简洁标题栏）
        header = QLabel("地址清洗与多源匹配")
        header.setObjectName("sidebar_header")
        sidebar_layout.addWidget(header)
        
        # 步骤列表（QGIS原生风格：使用QListWidget，符合QGIS面板标准）
        self.step_list = QListWidget()
        self.step_list.setObjectName("step_list")
        # QGIS原生设置：边框通过QSS样式移除，使用系统样式
        self.step_list.setSpacing(1)  # QGIS标准间距
        # QListWidget 默认就是单选模式，无需设置
        
        # 步骤定义（QGIS原生风格，简洁文本）
        steps = [
            "Step1 文件导入",
            "Step2 字段映射与清洗",
            "Step3 标准化解析 & 关联",
            "Step4 匹配任务管理",
            "Step5 导出 & 日志",
        ]
        for text in steps:
            item = QListWidgetItem(text)
            self.step_list.addItem(item)
        
        self.step_list.itemClicked.connect(self._on_step_clicked)
        sidebar_layout.addWidget(self.step_list, 1)  # 占据剩余空间
        
        # 底部提示（QGIS原生风格：小字体，次要信息）
        footer = QLabel("工作台模式：任意步骤可单独执行")
        footer.setObjectName("sidebar_footer")
        footer.setWordWrap(True)
        sidebar_layout.addWidget(footer)
        
        main_layout.addWidget(sidebar)
    
    def _build_main_content(self, main_layout: QHBoxLayout):
        """构建右侧主内容区"""
        # 使用垂直布局：上方是主内容，下方固定日志面板
        main_widget = QWidget()
        main_widget.setObjectName("main_content")
        # 设置尺寸策略，让主内容区能够水平扩展
        from qgis.PyQt.QtWidgets import QSizePolicy
        try:
            if hasattr(QSizePolicy, 'Policy') and hasattr(QSizePolicy.Policy, 'Expanding'):
                expanding = QSizePolicy.Policy.Expanding
            elif hasattr(QSizePolicy, 'Expanding'):
                expanding = QSizePolicy.Expanding
            else:
                expanding = 7  # Expanding = 7
            main_widget.setSizePolicy(expanding, expanding)
        except (AttributeError, TypeError):
            main_widget.setSizePolicy(7, 7)  # Expanding, Expanding
        
        main_content_layout = QVBoxLayout(main_widget)
        main_content_layout.setContentsMargins(0, 0, 0, 0)
        main_content_layout.setSpacing(0)
        
        # 标题栏（左右边距与内容区对齐）
        header_widget = QWidget()
        header_widget.setObjectName("header_widget")
        header_layout = QVBoxLayout(header_widget)
        header_layout.setContentsMargins(16, 10, 16, 10)  # 左右16px与内容区对齐
        
        self.header_title = QLabel("Step2 字段映射与清洗")
        self.header_title.setObjectName("header_title")
        header_layout.addWidget(self.header_title)
        
        self.header_subtitle = QLabel("为每个文件配置多个字段组合，一次性批量清洗。")
        self.header_subtitle.setObjectName("header_subtitle")
        header_layout.addWidget(self.header_subtitle)
        
        main_content_layout.addWidget(header_widget)
        
        # 全局配置组件（在所有步骤中都可见，可折叠，默认收起）
        # 左右边距与内容区对齐（16px）
        self.global_config_section = CollapsibleSection("全局配置", expanded=False)
        self.global_config = GlobalConfigWidget(self, self._log)
        self.global_config.region_changed.connect(self._on_region_changed)
        # 移除 GlobalConfigWidget 的 QGroupBox，直接使用内容
        self.global_config_section.add_widget(self.global_config)
        # 添加边距，使其与滚动区内容对齐（统一16px）
        global_config_container = QWidget()
        global_config_layout = QVBoxLayout(global_config_container)
        global_config_layout.setContentsMargins(16, 0, 16, 0)  # 左右16px与内容区对齐
        global_config_layout.addWidget(self.global_config_section)
        main_content_layout.addWidget(global_config_container)
        
        # 内容滚动区
        scroll = QScrollArea()
        scroll.setObjectName("content_scroll")
        scroll.setWidgetResizable(True)
        # 滚动条策略：QScrollArea 默认就是 ScrollBarAsNeeded，不需要显式设置
        
        self.content_widget = QWidget()
        # 设置尺寸策略，让内容区域能够扩展填满可用空间
        from qgis.PyQt.QtWidgets import QSizePolicy
        try:
            if hasattr(QSizePolicy, 'Policy') and hasattr(QSizePolicy.Policy, 'Expanding'):
                expanding = QSizePolicy.Policy.Expanding
            elif hasattr(QSizePolicy, 'Expanding'):
                expanding = QSizePolicy.Expanding
            else:
                expanding = 7  # Expanding = 7
            self.content_widget.setSizePolicy(expanding, expanding)
        except (AttributeError, TypeError):
            self.content_widget.setSizePolicy(7, 7)  # Expanding, Expanding
        
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(16, 12, 16, 12)  # 左右16px统一对齐
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
            open_match_modal=self._open_match_modal,
            global_config=self.global_config
        )
        
        # Step5
        self.step_widgets[5] = Step5Widget(
            self, self._log, self.task_manager, 
            log_panel=None,
            global_config=self.global_config
        )
        
        for i, widget in self.step_widgets.items():
            self.content_layout.addWidget(widget)
            widget.setVisible(False)
        
        scroll.setWidget(self.content_widget)
        # 关键修复：当QScrollArea的widgetResizable为True时，需要确保内容widget能够扩展
        # 通过监听QScrollArea的viewport resize事件，动态设置content_widget的最小宽度
        def update_content_width():
            """动态更新content_widget的宽度，确保填满QScrollArea"""
            try:
                viewport = scroll.viewport()
                if viewport and viewport.width() > 0:
                    self.content_widget.setMinimumWidth(viewport.width())
            except Exception:
                pass
        
        # 监听QScrollArea的viewport resize事件
        scroll.viewport().installEventFilter(self)
        # 存储更新函数和scroll引用
        self._update_content_width = update_content_width
        self._content_scroll = scroll
        # 初始设置一次
        from qgis.PyQt.QtCore import QTimer
        QTimer.singleShot(100, update_content_width)
        
        main_content_layout.addWidget(scroll, 1)  # 设置拉伸因子，让滚动区占据剩余空间
        
        # 下方日志面板（固定高度，不可拖动）
        log_box = QGroupBox("执行日志")
        log_box.setObjectName("log_panel_group")
        log_layout = QVBoxLayout(log_box)
        log_layout.setContentsMargins(16, 8, 16, 8)  # 左右16px与内容区对齐
        
        self.log_panel = QTextEdit()
        self.log_panel.setObjectName("log_panel")
        self.log_panel.setReadOnly(True)
        self.log_panel.setFixedHeight(200)  # 固定高度，不可拖动
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
        
        # 将日志面板添加到主布局底部（不拉伸）
        main_content_layout.addWidget(log_box)
        
        main_layout.addWidget(main_widget, 1)
    
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
    
    def eventFilter(self, obj, event):
        """事件过滤器：监听QScrollArea的viewport resize事件，动态更新content_widget宽度"""
        try:
            # 检查是否是content_scroll的viewport的resize事件
            if hasattr(self, '_content_scroll') and hasattr(self, '_update_content_width'):
                if obj == self._content_scroll.viewport():
                    if event.type() == QEvent.Resize:
                        self._update_content_width()
        except Exception:
            pass
        return super().eventFilter(obj, event)
    
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
        
        # Step1显示时自动刷新数据源列表
        # 注意：初始化时的刷新由Step1Widget.__init__中的延迟刷新处理（500ms）
        # 这里只在切换步骤时刷新，避免初始化时重复刷新
        # 使用标志位判断是否为初始化阶段
        if step_num == 1 and hasattr(self.step_widgets[1], '_on_refresh'):
            # 延迟刷新，确保不与初始化刷新冲突
            from qgis.PyQt.QtCore import QTimer
            # 如果是在初始化阶段（_current_step还未设置或刚设置为1），跳过
            # 否则延迟刷新（切换步骤时）
            if hasattr(self, '_initialized') and self._initialized:
                QTimer.singleShot(100, lambda: self.step_widgets[1]._on_refresh() if hasattr(self.step_widgets[1], '_on_refresh') else None)
    
    def _on_step_clicked(self, item: QListWidgetItem):
        """步骤点击事件"""
        index = self.step_list.row(item)
        self._switch_step(index + 1)
    
    def _log(self, msg: str, level: str = "info"):
        """添加日志 - 统一日志入口，限制最近500条"""
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
            
            # 限制日志条数为500条
            max_lines = 500
            doc = self.log_panel.document()
            if doc.blockCount() > max_lines:
                cursor = self.log_panel.textCursor()
                cursor.movePosition(cursor.MoveOperation.Start)
                cursor.movePosition(cursor.MoveOperation.Down, cursor.MoveMode.KeepAnchor, doc.blockCount() - max_lines)
                cursor.removeSelectedText()
            
            scrollbar = self.log_panel.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())
    
    def _open_filter_modal(self, target_name: str) -> str:
        """打开过滤条件模态对话框，返回设置的条件"""
        if self.filter_modal is not None:
            try:
                self.filter_modal.set_target_name(target_name)
                result = self.filter_modal.exec()
                # 如果用户点击确定，返回条件
                if result == QDialog.DialogCode.Accepted:
                    condition = self.filter_modal.get_condition()
                    return condition
            except Exception as e:
                self._log(f"[错误] 打开过滤条件对话框失败：{e}", "error")
        return ""
    
    def _open_match_modal(self, source_name: str, target_name: str) -> str:
        """打开字段关联配置对话框"""
        if self.match_modal is not None:
            try:
                # 设置获取分析结果的回调
                step3 = self.step_widgets.get(3)
                if step3 and hasattr(step3, 'get_all_relations'):
                    self.match_modal.set_relations_callback(step3.get_all_relations)
                
                # 设置全局配置
                if self.global_config:
                    self.match_modal.set_global_config(self.global_config)
                
                # 设置源表和目标表
                self.match_modal.set_source_and_target(source_name, target_name)
                
                if self.match_modal.exec() == QDialog.DialogCode.Accepted:
                    return self.match_modal.get_summary()
            except Exception as e:
                self._log(f"[错误] 打开字段关联对话框失败：{e}", "error")
        return ""
    
    def closeEvent(self, event: QCloseEvent):
        """
        重写关闭事件：点击关闭按钮时隐藏窗口而不是关闭
        再次点击插件按钮可以恢复窗口
        """
        event.ignore()  # 忽略关闭事件
        self.hide()     # 隐藏窗口
