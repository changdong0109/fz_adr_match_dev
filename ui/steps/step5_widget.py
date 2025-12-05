"""
Step5: 工具面板Widget
包含：加载SHP文件、配置验证参数、查看验证结果
"""
import os
import json
from typing import Callable, Optional, List, Dict
from pathlib import Path
from qgis.PyQt.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QCheckBox, QProgressBar, QFileDialog,
    QTableWidget, QTableWidgetItem, QHeaderView, QGroupBox,
    QAbstractItemView
)
from qgis.PyQt.QtGui import QColor
from qgis.PyQt.QtCore import Qt, QTimer, QThread, pyqtSignal
from ..widgets.base_step_widget import BaseStepWidget
from ..collapsible_section import CollapsibleSection
from ..widgets.no_wheel_combo_box import NoWheelComboBox
from ...core.validation_engine import ValidationEngine


class ValidationThread(QThread):
    """验证线程"""
    progress_updated = pyqtSignal(int, int, str)  # current, total, message
    validation_completed = pyqtSignal(dict)  # result
    validation_error = pyqtSignal(str)  # error message
    log_message = pyqtSignal(str, str)  # message, level - 用于线程安全的日志
    
    def __init__(self, config: Dict, log_callback=None):
        super().__init__()
        self.config = config
        self._log_callback = log_callback  # 保存回调，但不直接使用
        self._engine = None
    
    def _log(self, msg: str, level: str = "info"):
        """线程安全的日志方法：通过信号发送日志"""
        self.log_message.emit(msg, level)
    
    def run(self):
        """执行验证"""
        try:
            # 获取预先构建的索引数据（在主线程中已构建）
            db_index = self.config.get('db_index')
            shp_index = self.config.get('shp_index')
            
            if not db_index:
                self.validation_error.emit("数据库索引不存在")
                return
            
            if not shp_index:
                self.validation_error.emit("SHP索引不存在")
                return
            
            # 创建验证引擎
            self._engine = ValidationEngine(
                log_callback=self._log,
                progress_callback=lambda c, t, m: self.progress_updated.emit(c, t, m)
            )
            
            # 执行验证（使用预先构建的索引，不操作QGIS图层）
            result = self._engine.validate(
                match_result_file=self.config.get('match_result_file'),
                original_customer_file=self.config.get('original_customer_file'),
                db_index=db_index,  # 纯数据索引
                shp_index=shp_index,  # 纯数据索引（已转换为数据库坐标系）
                original_shp_gid_field=self.config.get('original_shp_gid_field'),
                database_match_field=self.config.get('database_match_field', 'name'),  # 固定为'name'
                source_match_fields=self.config.get('source_match_fields', []),  # 多个字段的列表
                deviation_threshold=float(self.config.get('deviation_threshold', 10.0)),
                db_crs=self.config.get('db_crs')  # 数据库坐标系
            )
            
            if result.get('success'):
                self.validation_completed.emit(result)
            else:
                self.validation_error.emit(result.get('error', '验证失败'))
        
        except Exception as e:
            self.validation_error.emit(f"验证异常: {e}")
            import traceback
            self._log(f"[验证线程] 异常详情: {traceback.format_exc()}", "error")


class Step5Widget(BaseStepWidget):
    """Step5: 工具面板"""
    
    def __init__(self, parent=None, log_callback: Optional[Callable[[str, str], None]] = None, 
                 task_manager=None, log_panel=None, global_config=None):
        self.global_config = global_config
        # 存储加载的图层引用
        self._loaded_layers: Dict[str, 'QgsVectorLayer'] = {}  # {file_path: layer}
        # 存储原始SHP文件信息
        self._original_shp_files: Dict[str, Dict] = {}  # {shp_path: {file_name, size, status}}
        super().__init__(parent, log_callback, task_manager)
        self._build_ui()
        # 存储当前选中的任务组信息
        self._current_task_group: Optional[Dict] = None
        self._current_target: Optional[Dict] = None
        
        # 验证结果
        self._validation_result: Optional[Dict] = None
        self._validation_thread: Optional['ValidationThread'] = None
        # 保存所有匹配到的字段（用于验证）
        self._matched_field_names: List[str] = []
        
        # 延迟刷新文件列表（确保全局配置已初始化）
        from qgis.PyQt.QtCore import QTimer
        QTimer.singleShot(300, self._load_original_shp_path)  # 先加载SHP路径（会触发自动刷新）
        # 延迟加载文件列表
        QTimer.singleShot(600, self._load_source_files)
        QTimer.singleShot(600, self._load_task_groups)  # 改为加载任务组列表
        # 延迟刷新图层列表
        QTimer.singleShot(700, self._refresh_layer_combos)
    
    # ==================== 步骤2相关方法 ====================
    
    def _load_source_files(self):
        """加载原始客户数据文件列表（从file_status.json缓存读取source_type为"客户采集数据"的文件）"""
        self._log("[Step5] 开始加载原始客户数据文件列表（从缓存读取）...", "info")
        
        # 1. 获取全局配置
        global_config = self._get_global_config()
        if not global_config:
            self._log("[Step5] ❌ 无法获取全局配置对象", "error")
            return
        
        # 2. 获取区域信息
        region_info = global_config.get_region_info()
        if not region_info:
            self._log("[Step5] ❌ 无法获取区域信息", "error")
            return
        
        cache_folder = region_info.get('cache_folder', '')
        customer_folder = region_info.get('customer_folder', '')
        
        self._log(f"[Step5] 调试: cache_folder = '{cache_folder}'", "info")
        self._log(f"[Step5] 调试: customer_folder = '{customer_folder}'", "info")
        
        if not cache_folder:
            self._log("[Step5] ❌ 缓存目录未配置", "warning")
            return
        
        if not customer_folder:
            self._log("[Step5] ❌ 客户数据目录未配置", "warning")
            return
        
        # 3. 读取file_status.json缓存文件
        file_status_path = os.path.join(cache_folder, "file_status.json")
        self._log(f"[Step5] 调试: file_status.json路径 = '{file_status_path}'", "info")
        
        file_status = {}
        if os.path.exists(file_status_path):
            try:
                with open(file_status_path, 'r', encoding='utf-8') as f:
                    file_status = json.load(f)
                self._log(f"[Step5] 调试: ✅ 成功读取file_status.json，包含 {len(file_status)} 个文件记录", "info")
                # 显示前5个文件的状态信息
                for file_name, status in list(file_status.items())[:5]:
                    self._log(f"[Step5] 调试: 文件 '{file_name}' 的状态: {status}", "info")
            except Exception as e:
                self._log(f"[Step5] ❌ 读取file_status.json失败: {e}", "error")
                import traceback
                self._log(f"[Step5] 错误详情: {traceback.format_exc()}", "error")
                return
        else:
            self._log(f"[Step5] ⚠️ file_status.json文件不存在: {file_status_path}", "warning")
            return
        
        # 4. 获取客户数据文件列表（从customer_folder目录扫描）
        if not os.path.exists(customer_folder):
            self._log(f"[Step5] ❌ 客户数据目录不存在: {customer_folder}", "warning")
            return
        
        # 5. 筛选source_type为"客户采集数据"的文件
        customer_files = []
        all_csv_files = []
        
        try:
            for f in os.listdir(customer_folder):
                if f.lower().endswith('.csv'):
                    all_csv_files.append(f)
                    file_path = os.path.join(customer_folder, f)
                    if os.path.exists(file_path) and os.path.isfile(file_path):
                        # 检查文件状态，只显示"客户采集数据"类型的文件
                        status = file_status.get(f, {})
                        self._log(f"[Step5] 调试: 文件 '{f}' 的缓存状态: {status}", "info")
                        
                        # 兼容不同的状态格式
                        if isinstance(status, dict):
                            source_type = status.get('source_type', '')
                        elif isinstance(status, str):
                            # 旧格式：只有cleaned状态，没有source_type
                            source_type = ''
                        else:
                            source_type = ''
                        
                        # 如果缓存中没有source_type，尝试从Step1的数据源中获取
                        if not source_type:
                            step1_data_sources = self.get_step1_data_sources()
                            if step1_data_sources and f in step1_data_sources:
                                step1_info = step1_data_sources[f]
                                source_type = step1_info.get('source_type', '')
                                self._log(f"[Step5] 调试: 从Step1数据源获取到source_type = '{source_type}'", "info")
                                
                                # 如果从Step1获取到了，更新缓存
                                if source_type:
                                    try:
                                        file_status[f]['source_type'] = source_type
                                        # 保存更新后的缓存
                                        cache_file = os.path.join(cache_folder, "file_status.json")
                                        with open(cache_file, 'w', encoding='utf-8') as cache_f:
                                            json.dump(file_status, cache_f, ensure_ascii=False, indent=2)
                                        self._log(f"[Step5] 调试: ✅ 已更新缓存，补充source_type字段", "info")
                                    except Exception as e:
                                        self._log(f"[Step5] 调试: 更新缓存失败: {e}", "warning")
                        
                        # 如果还是没有，根据文件位置推断（CSV文件在customer_folder中，通常是客户数据）
                        if not source_type:
                            # CSV文件在customer_folder目录中，默认推断为"客户采集数据"
                            source_type = "客户采集数据"
                            self._log(f"[Step5] 调试: 根据文件位置推断source_type = '{source_type}'", "info")
                        
                        self._log(f"[Step5] 调试: 文件 '{f}' 的最终source_type = '{source_type}' (期望='客户采集数据')", "info")
                        
                        if source_type == "客户采集数据":
                            customer_files.append(f)
                            self._log(f"[Step5] 调试: ✅ 文件 '{f}' 匹配，已添加到列表", "info")
                        else:
                            self._log(f"[Step5] 调试: ❌ 文件 '{f}' 不匹配（source_type='{source_type}'）", "info")
        except Exception as e:
            self._log(f"[Step5] ❌ 读取客户数据目录失败: {e}", "error")
            import traceback
            self._log(f"[Step5] 错误详情: {traceback.format_exc()}", "error")
            return
        
        # 6. 调试信息汇总
        self._log(f"[Step5] 调试: 目录中共有 {len(all_csv_files)} 个CSV文件", "info")
        self._log(f"[Step5] 调试: file_status.json中有 {len(file_status)} 条记录", "info")
        self._log(f"[Step5] 调试: 匹配到 {len(customer_files)} 个'客户采集数据'类型的文件", "info")
        
        # 7. 更新下拉框（如果组件存在，UI已重构后可能不存在）
        if hasattr(self, 'source_file_combo'):
            self.source_file_combo.clear()
            self.source_file_combo.addItem("请选择...", None)
            for file_name in sorted(customer_files):
                self.source_file_combo.addItem(file_name, file_name)
        
        # 8. 最终结果日志
        if customer_files:
            self._log(f"[Step5] ✅ 加载原始客户数据文件: {len(customer_files)} 个（从缓存筛选）", "info")
            self._log(f"[Step5] 文件列表: {', '.join(sorted(customer_files))}", "info")
        else:
            self._log(f"[Step5] ⚠️ 未找到'客户采集数据'类型的文件", "warning")
            if all_csv_files:
                self._log(f"[Step5] 提示: 目录中有 {len(all_csv_files)} 个CSV文件，但file_status.json中未标记为'客户采集数据'", "warning")
                self._log(f"[Step5] 提示: CSV文件列表: {', '.join(all_csv_files[:5])}", "warning")
                self._log(f"[Step5] 提示: 请检查file_status.json中的source_type字段是否正确", "warning")
    
    def _load_task_groups(self):
        """加载任务组列表"""
        global_config = self._get_global_config()
        if not global_config:
            return
        
        region_info = global_config.get_region_info()
        cache_folder = region_info.get('cache_folder', '')
        
        if not cache_folder:
            return
        
        # 从match_tasks.json读取任务组
        match_tasks_file = os.path.join(cache_folder, "match_tasks.json")
        if not os.path.exists(match_tasks_file):
            self.task_group_combo.clear()
            self.task_group_combo.addItem("请选择...", None)
            self._log("[Step5] 未找到匹配任务配置文件", "warning")
            return
        
        try:
            with open(match_tasks_file, 'r', encoding='utf-8') as f:
                match_tasks_data = json.load(f)
            
            tasks = match_tasks_data.get('tasks', [])
            
            self.task_group_combo.clear()
            self.task_group_combo.addItem("请选择...", None)
            
            for task in tasks:
                task_name = task.get('name', '未命名任务组')
                source_name = task.get('source_original', task.get('source', ''))
                status = task.get('status', '')
                # 显示格式：任务组名 (源表) [状态]
                display_text = f"{task_name} ({os.path.splitext(source_name)[0]}) [{status}]"
                self.task_group_combo.addItem(display_text, task)
            
            if tasks:
                self._log(f"[Step5] 加载任务组: {len(tasks)} 个", "info")
        except Exception as e:
            self._log(f"[Step5] 读取任务组失败: {e}", "error")
            self.task_group_combo.clear()
            self.task_group_combo.addItem("请选择...", None)
    
    def _on_task_group_changed(self, display_text: str):
        """任务组选择变化 - 自动关联所有配置"""
        if not display_text or display_text == "请选择...":
            self._current_task_group = None
            self.task_group_info.setText("选择任务组后显示详细信息...")
            self.target_tables_label.setText("选择任务组后自动显示所有目标表...")
            self.match_file_combo.clear()
            self.auto_config_info.setText("选择任务组后自动关联所有配置...")
            return
        
        # 获取选中的任务组数据
        task_data = self.task_group_combo.currentData()
        if not task_data:
            return
        
        self._current_task_group = task_data
        
        # 显示任务组信息
        source_original = task_data.get('source_original', '')
        targets = task_data.get('targets', [])
        results = task_data.get('results', {})
        
        info_text = f"源表: {source_original}\n"
        info_text += f"目标表数量: {len(targets)}\n"
        if results:
            info_text += f"匹配结果: "
            result_types = []
            if results.get('exact'):
                result_types.append("精确匹配")
            if results.get('high_confidence'):
                result_types.append("高置信度")
            if results.get('need_review'):
                result_types.append("需人工确认")
            if results.get('unmatched'):
                result_types.append("未匹配")
            info_text += ", ".join(result_types)
        self.task_group_info.setText(info_text)
        
        # 显示所有目标表（不需要选择）
        target_tables_text = f"目标表列表（共{len(targets)}个）：\n"
        for i, target in enumerate(targets, 1):
            target_table = target.get('table', '')
            original_path = target.get('original_path', '')
            target_tables_text += f"{i}. {os.path.splitext(target_table)[0]}"
            if original_path:
                target_tables_text += f" (SHP: {os.path.basename(original_path)})"
            target_tables_text += "\n"
        self.target_tables_label.setText(target_tables_text)
        
        # 加载匹配结果文件列表（从任务组的results中获取）
        self.match_file_combo.clear()
        self.match_file_combo.addItem("请选择...", None)
        match_files = []
        if results:
            if results.get('exact'):
                self.match_file_combo.addItem(results['exact'], results['exact'])
                match_files.append(results['exact'])
            if results.get('high_confidence'):
                self.match_file_combo.addItem(results['high_confidence'], results['high_confidence'])
                if not match_files:  # 如果还没有文件，添加这个
                    match_files.append(results['high_confidence'])
            if results.get('need_review'):
                self.match_file_combo.addItem(results['need_review'], results['need_review'])
                if not match_files:
                    match_files.append(results['need_review'])
            if results.get('unmatched'):
                self.match_file_combo.addItem(results['unmatched'], results['unmatched'])
                if not match_files:
                    match_files.append(results['unmatched'])
        
        # 如果有匹配结果文件，自动选择第一个
        if match_files:
            first_file = match_files[0]
            for i in range(self.match_file_combo.count()):
                if self.match_file_combo.itemText(i) == first_file:
                    self.match_file_combo.setCurrentIndex(i)
                    self._log(f"[Step5] ✅ 已自动选择匹配结果文件: '{first_file}'", "info")
                    # 手动触发_on_match_file_changed，确保字段下拉框被填充
                    QTimer.singleShot(100, lambda: self._on_match_file_changed(first_file))
                    break
        
        # 自动关联所有配置（延迟执行，确保匹配文件字段已加载）
        QTimer.singleShot(1000, lambda: self._auto_link_from_task_group())
        
        # 自动检测数据库点图层
        QTimer.singleShot(200, self._detect_database_layer)
    
    def _detect_database_layer(self):
        """自动检测数据库点图层（必须有code和name字段）"""
        try:
            from qgis.core import QgsProject, QgsWkbTypes
            
            layers = QgsProject.instance().mapLayers().values()
            valid_layers = []  # 数据库连接的图层
            file_layers = []  # 文件图层（非原始SHP）
            
            for layer in layers:
                if layer.type() != 0:  # 不是矢量图层
                    continue
                
                # 检查是否是点图层
                geom_type = layer.wkbType()
                if QgsWkbTypes.geometryType(geom_type) != QgsWkbTypes.GeometryType.PointGeometry:
                    continue
                
                # 获取数据源信息
                is_db_connection = False
                is_original_shp = False
                try:
                    provider = layer.dataProvider()
                    if provider:
                        data_source = provider.dataSourceUri() if hasattr(provider, 'dataSourceUri') else ''
                        if data_source:
                            data_source_str = str(data_source).lower()
                            # 检查是否是数据库连接（包含数据库连接关键词）
                            is_db_connection = any(keyword in data_source_str for keyword in ['dbname=', 'host=', 'database=', 'server='])
                            # 检查是否是原始SHP文件
                            is_original_shp = ('原始shp' in data_source_str or '原始shp数据' in data_source_str)
                except:
                    pass
                
                # 排除原始SHP文件
                if is_original_shp:
                    continue
                
                # 检查是否有code和name字段
                fields = layer.fields()
                field_names = [f.name().lower() for f in fields]
                
                has_code = 'code' in field_names
                has_name = 'name' in field_names
                
                if has_code and has_name:
                    # 优先选择数据库连接的图层
                    if is_db_connection:
                        valid_layers.append(layer)
                    else:
                        file_layers.append(layer)
            
            # 如果数据库连接的图层为空，使用文件图层（排除原始SHP后的）
            if not valid_layers and file_layers:
                valid_layers = file_layers
            
            if len(valid_layers) == 0:
                self.db_layer_status_label.setText(
                    "❌ 未检测到数据库点图层\n"
                    "要求：点图层，且必须有'code'和'name'字段\n"
                    "请先加载数据库点图层到QGIS"
                )
                self._detected_db_layer = None
                self._log("[Step5] ⚠️ 未检测到数据库点图层（需要点图层，且有code和name字段）", "warning")
            elif len(valid_layers) == 1:
                layer = valid_layers[0]
                self.db_layer_status_label.setText(
                    f"✅ 已检测到数据库点图层：{layer.name()}\n"
                    f"字段检查：code ✓, name ✓"
                )
                self._detected_db_layer = layer
                self._log(f"[Step5] ✅ 已检测到数据库点图层: {layer.name()}", "info")
            else:
                # 多个符合条件的图层，显示列表让用户知道
                layer_names = [l.name() for l in valid_layers]
                self.db_layer_status_label.setText(
                    f"⚠️ 检测到 {len(valid_layers)} 个符合条件的图层：\n" +
                    "\n".join(f"- {name}" for name in layer_names) +
                    "\n\n将使用第一个图层进行验证"
                )
                self._detected_db_layer = valid_layers[0]
                self._log(f"[Step5] ⚠️ 检测到多个数据库点图层，使用第一个: {valid_layers[0].name()}", "warning")
        
        except Exception as e:
            self.db_layer_status_label.setText(f"❌ 检测失败: {e}")
            self._detected_db_layer = None
            self._log(f"[Step5] 检测数据库点图层失败: {e}", "error")
    
    def _build_ui(self):
        """构建UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 6, 0, 6)
        layout.setSpacing(12)
        
        # 四个步骤区块
        layout.addWidget(self._card_csv_to_shp())  # 步骤0：加载原始SHP文件
        layout.addWidget(self._card_select_data_source())  # 步骤1：选择验证数据源
        layout.addWidget(self._card_validation_config())  # 步骤2：配置验证参数
        layout.addWidget(self._card_validation_results())  # 步骤3：执行验证并查看结果
        layout.addStretch(1)
    
    def _card_csv_to_shp(self) -> QWidget:
        """加载原始SHP文件区块"""
        section = CollapsibleSection("步骤0：加载原始SHP文件", expanded=True)
        
        content = QWidget()
        v = QVBoxLayout(content)
        v.setContentsMargins(16, 12, 16, 12)
        v.setSpacing(12)
        
        # 说明文字
        tip = QLabel("选择SHP文件所在的文件夹，扫描并加载SHP文件到QGIS。")
        tip.setWordWrap(True)
        tip.setObjectName("step5_tip")
        v.addWidget(tip)
        
        # SHP文件夹选择
        folder_row = QHBoxLayout()
        folder_label = QLabel("SHP文件夹：")
        self.original_shp_folder_display = QLineEdit()
        self.original_shp_folder_display.setReadOnly(True)
        self.original_shp_folder_display.setPlaceholderText("点击浏览选择SHP文件夹")
        
        btn_browse_folder = QPushButton("浏览...")
        btn_browse_folder.setObjectName("step5_btn_browse_original_shp_folder")
        btn_browse_folder.clicked.connect(self._browse_original_shp_folder)
        
        btn_refresh = QPushButton("刷新文件列表")
        btn_refresh.setObjectName("step5_btn_refresh_original_shp")
        btn_refresh.clicked.connect(self._refresh_original_shp_files)
        
        folder_row.addWidget(folder_label)
        folder_row.addWidget(self.original_shp_folder_display)
        folder_row.addWidget(btn_browse_folder)
        folder_row.addWidget(btn_refresh)
        folder_row.addStretch()
        v.addLayout(folder_row)
        
        # 文件列表表格
        self.original_shp_files_table = QTableWidget()
        self.original_shp_files_table.setColumnCount(4)
        self.original_shp_files_table.setHorizontalHeaderLabels([
            "选择", "文件名", "大小", "状态"
        ])
        self.original_shp_files_table.setColumnWidth(0, 60)
        self.original_shp_files_table.setColumnWidth(1, 300)
        self.original_shp_files_table.setColumnWidth(2, 100)
        self.original_shp_files_table.setColumnWidth(3, 100)
        self.original_shp_files_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        v.addWidget(self.original_shp_files_table)
        
        # 操作按钮
        btn_row = QHBoxLayout()
        btn_select_all = QPushButton("全选")
        btn_select_all.setObjectName("step5_btn_select_all_original")
        btn_select_all.clicked.connect(self._select_all_original_shp_files)
        
        btn_select_none = QPushButton("取消全选")
        btn_select_none.setObjectName("step5_btn_select_none_original")
        btn_select_none.clicked.connect(self._select_none_original_shp_files)
        
        btn_load = QPushButton("加载到QGIS")
        btn_load.setObjectName("step5_btn_load_original_shp")
        btn_load.clicked.connect(self._load_original_shp_to_qgis)
        
        btn_row.addWidget(btn_select_all)
        btn_row.addWidget(btn_select_none)
        btn_row.addStretch()
        btn_row.addWidget(btn_load)
        v.addLayout(btn_row)
        
        # 加载进度条
        self.original_shp_load_progress = QProgressBar()
        self.original_shp_load_progress.setVisible(False)
        v.addWidget(self.original_shp_load_progress)
        
        section.add_widget(content)
        return section
    
    def _card_select_data_source(self) -> QWidget:
        """步骤1：选择验证数据源"""
        section = CollapsibleSection("步骤1：选择验证数据源", expanded=True)
        
        content = QWidget()
        v = QVBoxLayout(content)
        v.setContentsMargins(16, 12, 16, 12)
        v.setSpacing(16)
        
        # 1. 任务组选择
        task_group_group = QGroupBox("匹配任务组")
        task_group_layout = QVBoxLayout(task_group_group)
        
        task_group_row = QHBoxLayout()
        task_group_label = QLabel("选择任务组：")
        self.task_group_combo = NoWheelComboBox()
        self.task_group_combo.setMinimumWidth(300)
        self.task_group_combo.currentTextChanged.connect(self._on_task_group_changed)
        task_group_row.addWidget(task_group_label)
        task_group_row.addWidget(self.task_group_combo)
        
        # 添加刷新按钮
        btn_refresh_task = QPushButton("刷新列表")
        btn_refresh_task.setObjectName("step5_btn_refresh")
        btn_refresh_task.setMaximumWidth(80)
        btn_refresh_task.clicked.connect(self._load_task_groups)
        task_group_row.addWidget(btn_refresh_task)
        
        task_group_row.addStretch()
        task_group_layout.addLayout(task_group_row)
        
        # 任务组信息显示
        self.task_group_info = QLabel("选择任务组后显示详细信息...")
        self.task_group_info.setWordWrap(True)
        self.task_group_info.setObjectName("step5_tip")
        task_group_layout.addWidget(self.task_group_info)
        
        v.addWidget(task_group_group)
        
        # 2. 目标表列表（自动显示，不需要选择）
        target_tables_group = QGroupBox("目标表列表（自动关联）")
        target_tables_layout = QVBoxLayout(target_tables_group)
        
        self.target_tables_label = QLabel("选择任务组后自动显示所有目标表...")
        self.target_tables_label.setWordWrap(True)
        self.target_tables_label.setObjectName("step5_tip")
        target_tables_layout.addWidget(self.target_tables_label)
        
        v.addWidget(target_tables_group)
        
        # 3. 匹配结果文件选择
        match_file_group = QGroupBox("匹配结果文件")
        match_layout = QVBoxLayout(match_file_group)
        
        match_row = QHBoxLayout()
        match_label = QLabel("选择文件：")
        self.match_file_combo = NoWheelComboBox()
        self.match_file_combo.setMinimumWidth(300)
        self.match_file_combo.currentTextChanged.connect(self._on_match_file_changed)
        match_row.addWidget(match_label)
        match_row.addWidget(self.match_file_combo)
        match_row.addStretch()
        match_layout.addLayout(match_row)
        
        # 匹配结果文件字段自动检测显示
        match_fields_label = QLabel("检测到的字段：")
        match_layout.addWidget(match_fields_label)
        
        self.match_fields_info = QLabel("选择文件后自动检测...")
        self.match_fields_info.setWordWrap(True)
        match_layout.addWidget(self.match_fields_info)
        
        v.addWidget(match_file_group)
        
        # 4. 数据库点图层检测（自动检测）
        db_layer_group = QGroupBox("数据库点图层检测")
        db_layer_layout = QVBoxLayout(db_layer_group)
        
        self.db_layer_status_label = QLabel("正在检测数据库点图层...")
        self.db_layer_status_label.setWordWrap(True)
        self.db_layer_status_label.setObjectName("step5_tip")
        db_layer_layout.addWidget(self.db_layer_status_label)
        
        db_layer_actions = QHBoxLayout()
        btn_refresh_db = QPushButton("重新检测")
        btn_refresh_db.setObjectName("step5_btn_refresh")
        btn_refresh_db.clicked.connect(self._detect_database_layer)
        db_layer_actions.addWidget(btn_refresh_db)
        db_layer_actions.addStretch()
        db_layer_layout.addLayout(db_layer_actions)
        
        v.addWidget(db_layer_group)
        
        section.add_widget(content)
        return section
    
    def _card_validation_config(self) -> QWidget:
        """步骤2：验证配置（自动完成，仅显示）"""
        section = CollapsibleSection("步骤2：验证配置（自动完成）", expanded=True)
        
        content = QWidget()
        v = QVBoxLayout(content)
        v.setContentsMargins(16, 12, 16, 12)
        v.setSpacing(16)
        
        # 自动关联信息显示
        auto_config_group = QGroupBox("自动关联配置")
        auto_config_layout = QVBoxLayout(auto_config_group)
        
        self.auto_config_info = QLabel("选择任务组后自动关联所有配置...")
        self.auto_config_info.setWordWrap(True)
        self.auto_config_info.setObjectName("step5_tip")
        auto_config_layout.addWidget(self.auto_config_info)
        
        # 源表匹配字段（自动选择，不显示给用户，但需要存储）
        # 这些字段用于验证逻辑，会自动从Step2配置中获取
        self.source_match_field1_combo = NoWheelComboBox()
        self.source_match_field1_combo.setVisible(False)  # 隐藏，但保留用于验证
        self.source_match_field2_combo = NoWheelComboBox()
        self.source_match_field2_combo.setVisible(False)  # 隐藏，但保留用于验证
        auto_config_layout.addWidget(self.source_match_field1_combo)
        auto_config_layout.addWidget(self.source_match_field2_combo)
        
        v.addWidget(auto_config_group)
        
        # 验证参数（仅位置偏差阈值，其他都自动）
        param_group = QGroupBox("验证参数")
        param_layout = QVBoxLayout(param_group)
        
        threshold_row = QHBoxLayout()
        threshold_label = QLabel("位置偏差阈值（米，可选）：")
        self.distance_threshold_input = QLineEdit()
        self.distance_threshold_input.setText("10.0")
        self.distance_threshold_input.setMaximumWidth(100)
        threshold_row.addWidget(threshold_label)
        threshold_row.addWidget(self.distance_threshold_input)
        threshold_row.addStretch()
        param_layout.addLayout(threshold_row)
        
        param_tip = QLabel("提示：其他配置已自动完成，无需手动设置。")
        param_tip.setWordWrap(True)
        param_tip.setObjectName("step5_tip")
        param_layout.addWidget(param_tip)
        
        v.addWidget(param_group)
        
        # 6. 进度条和状态标签（参考Step2/Step3）
        progress_row = QHBoxLayout()
        progress_row.setSpacing(12)
        
        self.validation_progress = QProgressBar()
        self.validation_progress.setObjectName("step5_validation_progress")
        self.validation_progress.setValue(0)
        self.validation_progress.setMinimumHeight(20)
        self.validation_progress.setVisible(False)
        
        self.validation_status_label = QLabel("就绪")
        self.validation_status_label.setObjectName("step5_validation_status_label")
        
        progress_row.addWidget(self.validation_progress)
        progress_row.addWidget(self.validation_status_label)
        progress_row.addStretch()
        v.addLayout(progress_row)
        
        # 7. 开始验证按钮
        btn_validate = QPushButton("开始验证")
        btn_validate.setObjectName("step5_btn_validate")
        btn_validate.clicked.connect(self._start_validation)
        v.addWidget(btn_validate)
        
        section.add_widget(content)
        return section
    
    def _card_validation_results(self) -> QWidget:
        """查看验证结果区块"""
        section = CollapsibleSection("步骤3：查看验证结果", expanded=False)
        self.results_section = section  # 保存引用，用于后续展开
        
        content = QWidget()
        v = QVBoxLayout(content)
        v.setContentsMargins(16, 12, 16, 12)
        v.setSpacing(16)
        
        # 1. 统计卡片（6个）
        stats_row = QHBoxLayout()
        stats_row.setSpacing(12)
        
        self.stat_source_total = self._create_stat_card("原始数据总数", "0", "blue")
        self.stat_matched_total = self._create_stat_card("匹配总数", "0", "blue")
        self.stat_valid = self._create_stat_card("验证通过", "0", "green")
        self.stat_missing = self._create_stat_card("缺失数据", "0", "red")
        self.stat_deviation = self._create_stat_card("位置偏差", "0", "orange")
        self.stat_duplicate = self._create_stat_card("重复数据", "0", "yellow")
        
        stats_row.addWidget(self.stat_source_total)
        stats_row.addWidget(self.stat_matched_total)
        stats_row.addWidget(self.stat_valid)
        stats_row.addWidget(self.stat_missing)
        stats_row.addWidget(self.stat_deviation)
        stats_row.addWidget(self.stat_duplicate)
        
        v.addLayout(stats_row)
        
        # 2. 统计详情（可折叠）
        stats_detail_section = CollapsibleSection("统计详情", expanded=False)
        stats_detail_content = QWidget()
        stats_detail_layout = QVBoxLayout(stats_detail_content)
        
        self.stats_detail_label = QLabel("验证完成后显示详细统计...")
        self.stats_detail_label.setWordWrap(True)
        stats_detail_layout.addWidget(self.stats_detail_label)
        
        stats_detail_section.add_widget(stats_detail_content)
        v.addWidget(stats_detail_section)
        
        # 3. 问题数据表格
        table_group = QGroupBox("问题数据列表")
        table_layout = QVBoxLayout(table_group)
        
        # 筛选按钮
        filter_row = QHBoxLayout()
        self.filter_all_btn = QPushButton("全部")
        self.filter_all_btn.setObjectName("step5_btn_filter_all")
        self.filter_all_btn.setCheckable(True)
        self.filter_all_btn.setChecked(True)
        self.filter_all_btn.clicked.connect(lambda: self._filter_problems('all'))
        
        self.filter_missing_btn = QPushButton("缺失")
        self.filter_missing_btn.setObjectName("step5_btn_filter_missing")
        self.filter_missing_btn.setCheckable(True)
        self.filter_missing_btn.clicked.connect(lambda: self._filter_problems('missing'))
        
        self.filter_deviation_btn = QPushButton("偏差")
        self.filter_deviation_btn.setObjectName("step5_btn_filter_deviation")
        self.filter_deviation_btn.setCheckable(True)
        self.filter_deviation_btn.clicked.connect(lambda: self._filter_problems('deviation'))
        
        self.filter_duplicate_btn = QPushButton("重复")
        self.filter_duplicate_btn.setObjectName("step5_btn_filter_duplicate")
        self.filter_duplicate_btn.setCheckable(True)
        self.filter_duplicate_btn.clicked.connect(lambda: self._filter_problems('duplicate'))
        
        filter_row.addWidget(self.filter_all_btn)
        filter_row.addWidget(self.filter_missing_btn)
        filter_row.addWidget(self.filter_deviation_btn)
        filter_row.addWidget(self.filter_duplicate_btn)
        filter_row.addStretch()
        table_layout.addLayout(filter_row)
        
        # 存储所有问题数据（用于筛选）
        self._all_problems: List[Dict] = []
        
        # 问题数据表格
        self.problem_table = QTableWidget()
        self.problem_table.setColumnCount(7)
        self.problem_table.setHorizontalHeaderLabels([
            "目标表GID", "数据库code", "源表匹配值", "状态", "偏差距离", "原始坐标", "数据库坐标"
        ])
        table_layout.addWidget(self.problem_table)
        
        # 操作按钮
        action_row = QHBoxLayout()
        btn_zoom = QPushButton("定位")
        btn_zoom.setObjectName("step5_btn_zoom")
        btn_zoom.clicked.connect(self._zoom_to_selected)
        
        btn_export_problems = QPushButton("导出问题数据")
        btn_export_problems.setObjectName("step5_btn_export_problems")
        btn_export_problems.clicked.connect(self._export_problems)
        
        btn_export_duplicate_layer = QPushButton("导出重复数据图层")
        btn_export_duplicate_layer.setObjectName("step5_btn_export_duplicate_layer")
        btn_export_duplicate_layer.clicked.connect(self._export_duplicate_layer)
        
        btn_export_stats = QPushButton("导出统计报告")
        btn_export_stats.setObjectName("step5_btn_export_stats")
        btn_export_stats.clicked.connect(self._export_stats_report)
        
        btn_clear_highlight = QPushButton("清除高亮")
        btn_clear_highlight.setObjectName("step5_btn_clear_highlight")
        btn_clear_highlight.clicked.connect(self._clear_highlight)
        
        action_row.addWidget(btn_zoom)
        action_row.addWidget(btn_export_problems)
        action_row.addWidget(btn_export_duplicate_layer)
        action_row.addWidget(btn_export_stats)
        action_row.addStretch()
        action_row.addWidget(btn_clear_highlight)
        table_layout.addLayout(action_row)
        
        v.addWidget(table_group)
        
        section.add_widget(content)
        return section
    
    def _create_stat_card(self, title: str, value: str, color: str) -> QWidget:
        """创建统计卡片"""
        card = QWidget()
        card.setObjectName(f"step5_stat_card_{color}")
        
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(4)
        
        title_label = QLabel(title)
        title_label.setObjectName("step5_stat_title")
        
        value_label = QLabel(value)
        value_label.setObjectName("step5_stat_value")
        
        layout.addWidget(title_label)
        layout.addWidget(value_label)
        
        # 存储value_label引用以便更新
        card.value_label = value_label
        card.title_label = title_label  # 也存储title_label
        
        return card
    
    def _is_layer_loaded(self, layer_name: str) -> bool:
        """检查图层是否已加载到QGIS"""
        try:
            from qgis.core import QgsProject
            layers = QgsProject.instance().mapLayers().values()
            for layer in layers:
                if layer.name() == layer_name:
                    return True
            return False
        except:
            return False
    
    def _refresh_layer_combos(self):
        """刷新图层下拉框"""
        # 如果组件不存在（UI已重构），直接返回
        if not hasattr(self, 'original_shp_layer_combo'):
            return
        
        # 刷新原始SHP图层下拉框
        self.original_shp_layer_combo.clear()
        self.original_shp_layer_combo.addItem("请选择...", None)
        
        try:
            from qgis.core import QgsProject, QgsWkbTypes
            layers = QgsProject.instance().mapLayers().values()
            for layer in layers:
                if layer.type() == 0:  # QgsMapLayer.VectorLayer
                    # 只显示SHP文件图层
                    if layer.dataProvider().name() == 'ogr':
                        layer_path = layer.source()
                        if layer_path.lower().endswith('.shp'):
                            self.original_shp_layer_combo.addItem(layer.name(), layer)
        except Exception as e:
            self._log(f"[Step5] 刷新图层列表失败: {e}", "error")
        
        # 刷新数据库图层下拉框（只显示点图层）
        self._refresh_database_layers()
    
    def _refresh_database_layers(self):
        """刷新数据库图层下拉框（只显示点图层）"""
        # 如果组件不存在（UI已重构），直接返回
        if not hasattr(self, 'database_layer_combo'):
            return
        
        self.database_layer_combo.clear()
        self.database_layer_combo.addItem("请选择...", None)
        
        try:
            from qgis.core import QgsProject, QgsWkbTypes
            layers = QgsProject.instance().mapLayers().values()
            for layer in layers:
                if layer.type() == 0:  # QgsMapLayer.VectorLayer
                    # 只显示点图层（Point, MultiPoint）
                    geom_type = layer.wkbType()
                    if QgsWkbTypes.geometryType(geom_type) == QgsWkbTypes.GeometryType.PointGeometry:
                        self.database_layer_combo.addItem(layer.name(), layer)
        except Exception as e:
            self._log(f"[Step5] 刷新数据库图层列表失败: {e}", "error")
    
    def _on_shp_layer_changed(self, layer_name: str):
        """原始SHP图层选择变化"""
        if layer_name == "请选择...":
            self.original_shp_gid_combo.clear()
            return
        
        # 获取选中的图层
        layer = self.original_shp_layer_combo.currentData()
        if not layer:
            return
        
        # 加载图层字段
        self.original_shp_gid_combo.clear()
        self.original_shp_gid_combo.addItem("请选择...", None)
        
        try:
            fields = layer.fields()
            for field in fields:
                field_name = field.name()
                self.original_shp_gid_combo.addItem(field_name, field_name)
            
            # 自动选择gid字段（尝试多种常见的GID字段名）
            gid_keywords = ['gid', 'id', 'fid', 'objectid', 'oid']
            selected = False
            for i in range(self.original_shp_gid_combo.count()):
                field_text = self.original_shp_gid_combo.itemText(i).lower()
                if field_text in gid_keywords or field_text.endswith('_gid') or field_text.endswith('_id'):
                    self.original_shp_gid_combo.setCurrentIndex(i)
                    selected = True
                    break
            
            if not selected and self.original_shp_gid_combo.count() > 1:
                # 如果没有找到标准GID字段，尝试选择第一个字段（通常第一个字段是ID类）
                self.original_shp_gid_combo.setCurrentIndex(1)
            
            self._log(f"[Step5] 已加载SHP图层字段: {layer_name}", "info")
        except Exception as e:
            self._log(f"[Step5] 加载图层字段失败: {e}", "error")
    
    def _on_database_layer_changed(self, layer_name: str):
        """数据库图层选择变化"""
        if layer_name == "请选择...":
            self.database_field1_combo.clear()
            self.database_field2_combo.clear()
            return
        
        # 获取选中的图层
        layer = self.database_layer_combo.currentData()
        if not layer:
            return
        
        # 加载图层字段
        self.database_field1_combo.clear()
        self.database_field2_combo.clear()
        self.database_field1_combo.addItem("请选择...", None)
        self.database_field2_combo.addItem("请选择...", None)
        
        try:
            fields = layer.fields()
            field_names = []
            for field in fields:
                field_name = field.name()
                field_names.append(field_name)
                self.database_field1_combo.addItem(field_name, field_name)
                self.database_field2_combo.addItem(field_name, field_name)
            
            # 尝试自动选择常见字段（名称、地址）
            if field_names:
                # 自动选择字段1（名称类）
                name_keywords = ['名称', 'name', '客户名称', '单位名称', '姓名', '名称1']
                for i in range(self.database_field1_combo.count()):
                    field_text = self.database_field1_combo.itemText(i).lower()
                    if any(keyword.lower() in field_text for keyword in name_keywords):
                        self.database_field1_combo.setCurrentIndex(i)
                        break
                
                # 自动选择字段2（地址类）
                address_keywords = ['地址', 'address', '详细地址', '完整地址', 'addr', '地址1']
                for i in range(self.database_field2_combo.count()):
                    field_text = self.database_field2_combo.itemText(i).lower()
                    if any(keyword.lower() in field_text for keyword in address_keywords):
                        self.database_field2_combo.setCurrentIndex(i)
                        break
            
            self._log(f"[Step5] 已加载数据库图层字段: {layer_name} ({len(field_names)} 个字段)", "info")
        except Exception as e:
            self._log(f"[Step5] 加载数据库图层字段失败: {e}", "error")
    
    def _on_source_file_changed(self, file_name: str):
        """原始客户数据文件选择变化（仅用于统计，不需要选择字段）"""
        # 原始客户数据文件只用于统计原始数据总数，不需要选择字段
        # 这个方法保留为空，仅作为占位符
        pass
    
    def _on_match_file_changed(self, file_name: str):
        """匹配结果文件选择变化"""
        if not file_name or file_name == "请选择...":
            self.match_fields_info.setText("选择文件后自动检测...")
            self.source_match_field1_combo.clear()
            self.source_match_field2_combo.clear()
            return
        
        # 加载匹配结果文件并检测字段
        global_config = self._get_global_config()
        if not global_config:
            return
        
        region_info = global_config.get_region_info()
        cache_folder = region_info.get('cache_folder', '')
        if not cache_folder:
            return
        
        result_dir = os.path.join(cache_folder, "match_results")
        file_path = os.path.join(result_dir, file_name)
        if not os.path.exists(file_path):
            self.match_fields_info.setText(f"文件不存在: {file_path}")
            return
        
        # 读取CSV文件的列名
        try:
            import csv
            with open(file_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                field_names = reader.fieldnames or []
        except Exception as e:
            self.match_fields_info.setText(f"读取文件失败: {e}")
            self._log(f"[Step5] 读取匹配结果文件失败: {file_name}, {e}", "error")
            return
        
        # 检测字段类型
        source_fields = []  # [源:表名]字段名
        match_source_fields = []  # 【匹配源:表名】字段名
        target_fields = []  # [目标:表名]字段名
        target_gid_fields = []  # [目标:表名]gid
        
        for field in field_names:
            if field.startswith('[源:'):
                source_fields.append(field)
            elif field.startswith('【匹配源:'):
                match_source_fields.append(field)
            elif field.startswith('[目标:'):
                target_fields.append(field)
                # 检查是否是GID字段
                if 'gid' in field.lower():
                    target_gid_fields.append(field)
        
        # 更新字段信息显示
        info_text = f"检测到 {len(field_names)} 个字段：\n"
        info_text += f"- 源表字段: {len(source_fields)} 个\n"
        info_text += f"- 匹配源字段: {len(match_source_fields)} 个\n"
        info_text += f"- 目标表字段: {len(target_fields)} 个"
        if target_gid_fields:
            info_text += f"\n- 检测到GID字段: {len(target_gid_fields)} 个"
        self.match_fields_info.setText(info_text)
        
        # 目标表GID字段已自动检测（不需要用户选择，验证时会自动从匹配结果中查找）
        if target_gid_fields:
            self._log(f"[Step5] 检测到目标表GID字段: {', '.join(target_gid_fields)}", "info")
        
        # 更新源表匹配字段下拉框
        self.source_match_field1_combo.clear()
        self.source_match_field2_combo.clear()
        self.source_match_field1_combo.addItem("请选择...", None)
        self.source_match_field2_combo.addItem("请选择...", None)
        
        # 优先使用【匹配源:表名】字段
        available_match_fields = []
        if match_source_fields:
            for field in match_source_fields:
                available_match_fields.append(field)
                self.source_match_field1_combo.addItem(field, field)
                self.source_match_field2_combo.addItem(field, field)
        
        # 如果【匹配源字段不够，补充[源:表名]字段（排除gid）
        # 这样字段2也有更多选择
        for field in source_fields:
            if 'gid' not in field.lower() and field not in available_match_fields:
                available_match_fields.append(field)
                self.source_match_field1_combo.addItem(field, field)
                self.source_match_field2_combo.addItem(field, field)
        
        # 尝试自动选择常见字段（名称、地址）
        if available_match_fields:
            # 自动选择字段1（名称类）
            name_keywords = ['名称', 'name', '客户名称', '单位名称', '姓名', '匹配源']
            for i in range(self.source_match_field1_combo.count()):
                field_text = self.source_match_field1_combo.itemText(i).lower()
                if any(keyword.lower() in field_text for keyword in name_keywords):
                    self.source_match_field1_combo.setCurrentIndex(i)
                    break
            
            # 自动选择字段2（地址类）
            address_keywords = ['地址', 'address', '详细地址', '完整地址', 'addr', '匹配源']
            selected_field2 = False
            for i in range(self.source_match_field2_combo.count()):
                field_text = self.source_match_field2_combo.itemText(i).lower()
                if any(keyword.lower() in field_text for keyword in address_keywords):
                    self.source_match_field2_combo.setCurrentIndex(i)
                    selected_field2 = True
                    break
            
            # 如果字段2没有匹配到地址类关键词，但字段1已选择，自动选择第一个可用的字段（作为备选）
            if not selected_field2 and self.source_match_field1_combo.currentIndex() > 0:
                # 跳过"请选择..."，选择第一个实际字段
                if self.source_match_field2_combo.count() > 1:
                    # 找到字段1选择的字段，字段2选择不同的字段
                    field1_text = self.source_match_field1_combo.currentText()
                    for i in range(1, self.source_match_field2_combo.count()):  # 跳过"请选择..."
                        field2_text = self.source_match_field2_combo.itemText(i)
                        if field2_text != field1_text:  # 选择不同的字段
                            self.source_match_field2_combo.setCurrentIndex(i)
                            break
        
        self._log(f"[Step5] 已检测匹配结果文件字段: {file_name} (共{len(field_names)}个字段)", "info")
        
        # ========== 基于任务组自动关联所有配置 ==========
        # 匹配文件选择后，立即触发自动关联（此时match_file_name已确定）
        if self._current_task_group:
            self._log(f"[Step5] 匹配文件已选择，触发自动关联配置", "info")
            # 延迟执行，确保字段下拉框已填充
            QTimer.singleShot(300, lambda: self._auto_link_from_task_group())
    
    def _auto_link_from_task_group(self):
        """
        从任务组自动关联所有配置
        
        这是核心方法，基于任务组自动关联：
        1. 原始客户数据文件（从任务组的source_original沿file_chain追溯）
        2. 自动加载所有相关的原始SHP文件（从所有targets的original_path）
        3. Step2字段组合配置（自动选择源表匹配字段）
        4. 更新自动配置信息显示
        """
        if not self._current_task_group:
            return
        
        try:
            global_config = self._get_global_config()
            if not global_config:
                return
            
            region_info = global_config.get_region_info()
            cache_folder = region_info.get('cache_folder', '')
            customer_folder = region_info.get('customer_folder', '')
            
            # 1. 自动关联原始客户数据文件（从source_original沿file_chain追溯）
            source_original = self._current_task_group.get('source_original', '')
            source_standardized = self._current_task_group.get('source', '')
            
            original_file_path = None
            if source_original:
                # 直接使用source_original
                original_file_name = os.path.basename(source_original) if os.path.sep in source_original else source_original
                original_file_path = os.path.join(customer_folder, original_file_name)
                if not os.path.exists(original_file_path):
                    # 尝试从file_chain追溯
                    file_status_path = os.path.join(cache_folder, "file_status.json")
                    if os.path.exists(file_status_path):
                        with open(file_status_path, 'r', encoding='utf-8') as f:
                            file_status = json.load(f)
                            if original_file_name in file_status:
                                status = file_status[original_file_name]
                                if isinstance(status, dict):
                                    file_chain = status.get('file_chain', {})
                                    step1_original = file_chain.get('step1_original', '')
                                    if step1_original and os.path.exists(step1_original):
                                        original_file_path = step1_original
                                        original_file_name = os.path.basename(step1_original)
            
            # 更新自动配置信息
            config_info = "自动关联配置：\n"
            if original_file_path and os.path.exists(original_file_path):
                config_info += f"✅ 原始客户数据文件: {os.path.basename(original_file_path)}\n"
            else:
                config_info += f"⚠️ 原始客户数据文件: 未找到\n"
            
            # 2. 自动加载所有相关的原始SHP文件（从所有targets的original_path）
            targets = self._current_task_group.get('targets', [])
            loaded_shp_count = 0
            for target in targets:
                original_shp_path = target.get('original_path', '')
                if original_shp_path and os.path.exists(original_shp_path):
                    if not self._is_shp_file_loaded(original_shp_path):
                        self._auto_load_shp_file(original_shp_path)
                        loaded_shp_count += 1
                        self._log(f"[Step5] ✅ 已自动加载原始SHP文件: '{os.path.basename(original_shp_path)}'", "info")
            
            config_info += f"✅ 原始SHP图层: 已加载 {loaded_shp_count} 个\n"
            config_info += f"✅ 数据库点图层: 使用检测到的图层（code和name字段）\n"
            config_info += f"✅ 匹配字段: 从Step4配置自动获取\n"
            
            self.auto_config_info.setText(config_info)
            
            # 3. 读取Step2字段组合配置，自动选择源表匹配字段
            # 从任务组的results中获取实际的文件名（优先使用exact，否则使用第一个可用的）
            results = self._current_task_group.get('results', {})
            match_file_name = None
            if results:
                if results.get('exact'):
                    match_file_name = results['exact']
                elif results.get('high_confidence'):
                    match_file_name = results['high_confidence']
                elif results.get('need_review'):
                    match_file_name = results['need_review']
                elif results.get('unmatched'):
                    match_file_name = results['unmatched']
            
            self._log(f"[Step5] 调试: _auto_link_from_task_group - source_original='{source_original}', match_file_name='{match_file_name}'", "info")
            
            if source_original and match_file_name:
                original_file_name = os.path.basename(source_original) if os.path.sep in source_original else source_original
                self._log(f"[Step5] 调试: 准备调用_auto_load_step2_combo_config - original_file_name='{original_file_name}', match_file_name='{match_file_name}'", "info")
                QTimer.singleShot(200, lambda: self._auto_load_step2_combo_config(original_file_name, match_file_name))
            elif not match_file_name:
                self._log(f"[Step5] ⚠️ 任务组中未找到匹配结果文件，无法加载Step2配置", "warning")
            elif not source_original:
                self._log(f"[Step5] ⚠️ 任务组中未找到source_original，无法加载Step2配置", "warning")
        
        except Exception as e:
            self._log(f"[Step5] 从任务组自动关联失败: {e}", "error")
            import traceback
            self._log(f"[Step5] 错误详情: {traceback.format_exc()}", "error")
    
    def _auto_load_step4_match_fields_from_target(self):
        """从当前选中的目标表自动加载Step4的匹配字段配置"""
        if not self._current_target:
            return
        
        # 检查数据库图层是否已选择
        db_layer_name = self.database_layer_combo.currentText()
        if not db_layer_name or db_layer_name == "请选择...":
            return
        
        try:
            match_fields_json = self._current_target.get('match_fields', '')
            if not match_fields_json:
                return
            
            # 解析JSON配置
            config = json.loads(match_fields_json)
            pairs = config.get('pairs', [])
            
            if pairs:
                # 获取第一个字段对（用于字段1）
                first_pair = pairs[0]
                tgt_field = first_pair.get('tgt', '')
                
                # 自动选择数据库图层匹配字段1
                if tgt_field:
                    for i in range(self.database_field1_combo.count()):
                        if self.database_field1_combo.itemText(i) == tgt_field:
                            self.database_field1_combo.setCurrentIndex(i)
                            self._log(f"[Step5] ✅ 已自动选择数据库图层匹配字段1: '{tgt_field}'", "info")
                            break
                
                # 获取第二个字段对（用于字段2）
                if len(pairs) >= 2:
                    second_pair = pairs[1]
                    tgt_field2 = second_pair.get('tgt', '')
                    if tgt_field2:
                        for i in range(self.database_field2_combo.count()):
                            if self.database_field2_combo.itemText(i) == tgt_field2:
                                self.database_field2_combo.setCurrentIndex(i)
                                self._log(f"[Step5] ✅ 已自动选择数据库图层匹配字段2: '{tgt_field2}'", "info")
                                break
        
        except Exception as e:
            self._log(f"[Step5] 从目标表加载匹配字段配置失败: {e}", "warning")
    
    def _auto_link_source_file_from_match_result(self, match_file_name: str):
        """
        从匹配结果文件自动关联原始客户数据文件和原始SHP文件
        
        逻辑（使用文件流转链）：
        1. 从匹配结果文件名提取源表名（去掉_精确匹配_、_高置信度_等后缀）
        2. 从match_tasks.json查找source_original（直接获取原始文件名）
        3. 如果找不到，从file_status.json的file_chain.step1_original查找
        4. 自动选择原始客户数据文件下拉框
        5. 自动加载原始SHP文件（从file_chain.step1_original读取SHP路径）
        """
        try:
            global_config = self._get_global_config()
            if not global_config:
                return
        
            region_info = global_config.get_region_info()
            cache_folder = region_info.get('cache_folder', '')
            if not cache_folder:
                return
            
            # 1. 从匹配结果文件名提取源表名
            # 例如：廊坊工商户_精确匹配_100条.csv → 廊坊工商户
            source_name = match_file_name
            for suffix in ['_精确匹配_', '_高置信度_', '_需人工确认_', '_未匹配_']:
                if suffix in source_name:
                    source_name = source_name.split(suffix)[0]
                    break
            source_name = os.path.splitext(source_name)[0]
            
            self._log(f"[Step5] 从匹配结果文件名提取源表名: '{source_name}'", "info")
            
            # 2. 优先从match_tasks.json查找source_original（最直接的方式）
            original_source_file = None
            original_shp_path = None
            
            match_tasks_file = os.path.join(cache_folder, "match_tasks.json")
            if os.path.exists(match_tasks_file):
                try:
                    with open(match_tasks_file, 'r', encoding='utf-8') as f:
                        match_tasks_data = json.load(f)
                        tasks = match_tasks_data.get('tasks', [])
                        
                        # 查找匹配的任务（通过匹配结果文件名匹配）
                        for task in tasks:
                            results = task.get('results', {})
                            # 检查匹配结果文件名是否在results中
                            for level, result_file in results.items():
                                if result_file == match_file_name:
                                    # 找到匹配的任务，获取source_original
                                    original_source_file = task.get('source_original', '')
                                    if original_source_file:
                                        # 从targets中获取原始SHP文件路径（优先使用targets[].original_path）
                                        targets = task.get('targets', [])
                                        for target in targets:
                                            target_original_path = target.get('original_path', '')
                                            if target_original_path and target_original_path.lower().endswith('.shp'):
                                                original_shp_path = target_original_path
                                                self._log(f"[Step5] 从match_tasks.json找到原始SHP文件: '{os.path.basename(original_shp_path)}'", "info")
                                                break
                                        
                                        self._log(f"[Step5] 从match_tasks.json找到原始文件: '{original_source_file}'", "info")
                                        break
                            
                            if original_source_file:
                                break
                except Exception as e:
                    self._log(f"[Step5] 读取match_tasks.json失败: {e}", "warning")
            
            # 3. 如果还没找到，从file_status.json的file_chain查找
            if not original_source_file:
                file_status_path = os.path.join(cache_folder, "file_status.json")
                if os.path.exists(file_status_path):
                    try:
                        with open(file_status_path, 'r', encoding='utf-8') as f:
                            file_status = json.load(f)
                            
                            # 查找匹配的原始文件名（通过文件名匹配）
                            for file_name, status in file_status.items():
                                file_base = os.path.splitext(file_name)[0]
                                # 检查文件名是否匹配source_name
                                if file_base == source_name or file_base.startswith(source_name):
                                    if isinstance(status, dict):
                                        source_type = status.get('source_type', '')
                                        if source_type == "客户采集数据":
                                            original_source_file = file_name
                                            # 注意：这里不获取SHP路径，因为file_status.json的step1_original是客户数据文件路径
                                            # SHP路径应该从match_tasks.json的targets[].original_path获取
                                            self._log(f"[Step5] 从file_status.json找到原始文件: '{original_source_file}'", "info")
                                            break
                    except Exception as e:
                        self._log(f"[Step5] 读取file_status.json失败: {e}", "warning")
            
            # 4. 自动选择原始客户数据文件下拉框
            if original_source_file:
                # 只取文件名（去掉路径）
                original_file_name = os.path.basename(original_source_file) if os.path.sep in original_source_file else original_source_file
                
                # 原始客户数据文件已自动关联（UI已重构，不再需要下拉框选择）
                self._log(f"[Step5] ✅ 已自动关联原始客户数据文件: '{original_file_name}'", "info")
                # 延迟加载Step2字段组合配置
                QTimer.singleShot(500, lambda: self._auto_load_step2_combo_config(original_file_name, match_file_name))
            else:
                self._log(f"[Step5] ⚠️ 无法从匹配结果文件名 '{match_file_name}' 查找到原始客户数据文件", "warning")
            
            # 5. 自动加载原始SHP文件（如果找到了SHP路径）
            if original_shp_path and os.path.exists(original_shp_path):
                # 检查SHP文件是否已经在QGIS中加载
                shp_file_name = os.path.basename(original_shp_path)
                if not self._is_shp_file_loaded(original_shp_path):
                    # 自动加载SHP文件到QGIS
                    self._auto_load_shp_file(original_shp_path)
                    self._log(f"[Step5] ✅ 已自动加载原始SHP文件: '{shp_file_name}'", "info")
                else:
                    self._log(f"[Step5] 原始SHP文件已加载: '{shp_file_name}'", "info")
            
            # 6. 自动关联Step4的匹配字段配置（从任务配置中获取）
            if original_source_file:
                QTimer.singleShot(1000, lambda: self._auto_load_step4_match_fields(match_file_name))
        
        except Exception as e:
            self._log(f"[Step5] 自动关联失败: {e}", "error")
            import traceback
            self._log(f"[Step5] 错误详情: {traceback.format_exc()}", "error")
    
    def _auto_load_step2_combo_config(self, original_file_name: str, match_file_name: str):
        """
        自动加载Step2的字段组合配置，并自动选择源表匹配字段
        直接从配置文件读取，不等待下拉框填充
        """
        try:
            global_config = self._get_global_config()
            if not global_config:
                return
            
            region_info = global_config.get_region_info()
            cache_folder = region_info.get('cache_folder', '')
            if not cache_folder:
                return
            
            # 1. 读取Step2的字段组合配置
            file_stem = os.path.splitext(original_file_name)[0]
            combo_config_path = os.path.join(cache_folder, f"{file_stem}_combo_config.json")
            
            if not os.path.exists(combo_config_path):
                self._log(f"[Step5] ⚠️ Step2字段组合配置不存在: {combo_config_path}", "warning")
                return
            
            with open(combo_config_path, 'r', encoding='utf-8') as f:
                combo_config = json.load(f)
            
            fields = combo_config.get('fields', [])
            if not fields:
                self._log(f"[Step5] ⚠️ Step2字段组合配置为空", "warning")
                return
            
            # 获取字段名列表（按顺序）
            field_names = [f.get('field', '') for f in fields if f.get('field')]
            self._log(f"[Step5] 从Step2配置读取字段组合: {field_names}", "info")
            
            # 2. 直接读取匹配结果文件的CSV，获取所有列名
            result_dir = os.path.join(cache_folder, "match_results")
            match_file_path = os.path.join(result_dir, match_file_name)
            
            # 如果文件不存在，尝试查找相似的文件名（去掉条数部分）
            if not os.path.exists(match_file_path):
                self._log(f"[Step5] ⚠️ 匹配结果文件不存在: {match_file_path}，尝试查找相似文件", "warning")
                # 提取文件名前缀（去掉条数部分）
                import re
                # 匹配格式：文件名_类型_数字条.csv
                pattern = r'^(.+?)_(精确匹配|高置信度|需人工确认|未匹配)_\d+条\.csv$'
                match = re.match(pattern, match_file_name)
                if match:
                    file_prefix = match.group(1)
                    file_type = match.group(2)
                    # 在目录中查找匹配的文件
                    if os.path.exists(result_dir):
                        for f in os.listdir(result_dir):
                            if f.startswith(f"{file_prefix}_{file_type}_") and f.endswith('.csv'):
                                match_file_path = os.path.join(result_dir, f)
                                match_file_name = f  # 更新为实际文件名
                                self._log(f"[Step5] ✅ 找到实际文件: {f}", "info")
                                break
                
                # 如果还是找不到，尝试从下拉框获取当前选择的文件名
                if not os.path.exists(match_file_path) and hasattr(self, 'match_file_combo'):
                    current_selected = self.match_file_combo.currentText()
                    if current_selected and current_selected != "请选择...":
                        match_file_path = os.path.join(result_dir, current_selected)
                        match_file_name = current_selected
                        self._log(f"[Step5] 使用下拉框中选择的文件: {current_selected}", "info")
                
                if not os.path.exists(match_file_path):
                    self._log(f"[Step5] ⚠️ 无法找到匹配结果文件", "warning")
                    return
            
            import csv
            with open(match_file_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                match_file_columns = reader.fieldnames or []
            
            self._log(f"[Step5] 匹配结果文件列数: {len(match_file_columns)}", "info")
            
            # 3. 从匹配结果文件名提取源表名
            source_name = match_file_name
            for suffix in ['_精确匹配_', '_高置信度_', '_需人工确认_', '_未匹配_']:
                if suffix in source_name:
                    source_name = source_name.split(suffix)[0]
                    break
            source_name = os.path.splitext(source_name)[0]
            self._log(f"[Step5] 从匹配结果文件名提取源表名: '{source_name}'", "info")
            
            # 4. 在匹配结果文件的列名中查找对应的字段
            matched_field_names = []
            for field_name in field_names:
                # 策略1: 尝试匹配 `[源:表名]字段名` 格式
                source_field_pattern = f"[源:{source_name}]{field_name}"
                # 策略2: 尝试匹配 `【匹配源:表名】字段名` 格式
                match_source_field_pattern = f"【匹配源:{source_name}】{field_name}"
                
                found_field = None
                # 精确匹配
                if source_field_pattern in match_file_columns:
                    found_field = source_field_pattern
                elif match_source_field_pattern in match_file_columns:
                    found_field = match_source_field_pattern
                else:
                    # 模糊匹配：字段名包含在列名中
                    for col in match_file_columns:
                        if field_name.lower() in col.lower() and (f"[源:{source_name}]" in col or f"【匹配源:{source_name}】" in col):
                            found_field = col
                            break
                
                if found_field:
                    matched_field_names.append(found_field)
                    self._log(f"[Step5] ✅ 匹配到字段: '{found_field}' (Step2字段: '{field_name}')", "info")
                else:
                    self._log(f"[Step5] ⚠️ 未找到Step2字段 '{field_name}' 对应的匹配结果字段", "warning")
            
            # 5. 填充下拉框并自动选择
            if not hasattr(self, 'source_match_field1_combo') or not hasattr(self, 'source_match_field2_combo'):
                self._log(f"[Step5] ⚠️ 源表匹配字段下拉框不存在", "warning")
                return
        
            # 清空并填充下拉框
            self.source_match_field1_combo.clear()
            self.source_match_field2_combo.clear()
            self.source_match_field1_combo.addItem("请选择...", None)
            self.source_match_field2_combo.addItem("请选择...", None)
            
            # 添加所有匹配源字段到下拉框
            for col in match_file_columns:
                if col.startswith('[源:') or col.startswith('【匹配源:'):
                    self.source_match_field1_combo.addItem(col, col)
                    self.source_match_field2_combo.addItem(col, col)
            
            # 自动选择字段1和字段2（从所有匹配的字段中选择前2个）
            if len(matched_field_names) >= 1:
                found_field1 = False
                for i in range(self.source_match_field1_combo.count()):
                    if self.source_match_field1_combo.itemText(i) == matched_field_names[0]:
                        self.source_match_field1_combo.setCurrentIndex(i)
                        self._log(f"[Step5] ✅ 已自动选择源表匹配字段1: '{matched_field_names[0]}'", "info")
                        found_field1 = True
                        break
                if not found_field1:
                    self._log(f"[Step5] ⚠️ 在下拉框中未找到字段1: '{matched_field_names[0]}'", "warning")
            
            if len(matched_field_names) >= 2:
                # 选择第2个匹配的字段
                found_field2 = False
                for i in range(self.source_match_field2_combo.count()):
                    if self.source_match_field2_combo.itemText(i) == matched_field_names[1]:
                        self.source_match_field2_combo.setCurrentIndex(i)
                        self._log(f"[Step5] ✅ 已自动选择源表匹配字段2: '{matched_field_names[1]}'", "info")
                        found_field2 = True
                        break
                if not found_field2:
                    self._log(f"[Step5] ⚠️ 在下拉框中未找到字段2: '{matched_field_names[1]}'", "warning")
            elif len(matched_field_names) == 1:
                # 如果只有一个字段匹配，字段2选择第一个可用的不同字段
                field1_text = self.source_match_field1_combo.currentText()
                for i in range(1, self.source_match_field2_combo.count()):
                    field2_text = self.source_match_field2_combo.itemText(i)
                    if field2_text != field1_text:
                        self.source_match_field2_combo.setCurrentIndex(i)
                        self._log(f"[Step5] ✅ 已自动选择源表匹配字段2: '{field2_text}'", "info")
                        break
            
            # 保存所有匹配到的字段（用于验证）
            self._matched_field_names = matched_field_names
            
            # 记录所有匹配到的字段（用于验证时会使用所有字段）
            if len(matched_field_names) > 0:
                self._log(f"[Step5] ✅ Step2配置中有 {len(field_names)} 个字段，匹配到 {len(matched_field_names)} 个字段，将使用所有匹配的字段进行验证", "info")
                self._log(f"[Step5] 所有匹配的字段: {matched_field_names}", "info")
        
        except Exception as e:
            self._log(f"[Step5] 加载Step2字段组合配置失败: {e}", "error")
            import traceback
            self._log(f"[Step5] 错误详情: {traceback.format_exc()}", "error")
    
    def _auto_load_step4_match_fields(self, match_file_name: str):
        """
        自动加载Step4的匹配字段配置，并自动选择数据库图层匹配字段
        """
        try:
            # 检查数据库图层是否已选择
            db_layer_name = self.database_layer_combo.currentText()
            if not db_layer_name or db_layer_name == "请选择...":
                # 数据库图层未选择，无法自动选择匹配字段
                return
            
            global_config = self._get_global_config()
            if not global_config:
                return
            
            region_info = global_config.get_region_info()
            cache_folder = region_info.get('cache_folder', '')
            if not cache_folder:
                return
            
            # 从match_tasks.json查找匹配字段配置
            match_tasks_file = os.path.join(cache_folder, "match_tasks.json")
            if not os.path.exists(match_tasks_file):
                return
            
            with open(match_tasks_file, 'r', encoding='utf-8') as f:
                match_tasks_data = json.load(f)
            
            tasks = match_tasks_data.get('tasks', [])
            
            # 查找匹配的任务
            for task in tasks:
                results = task.get('results', {})
                # 检查匹配结果文件名是否在results中
                for level, result_file in results.items():
                    if result_file == match_file_name:
                        # 找到匹配的任务，获取targets中的匹配字段配置
                        targets = task.get('targets', [])
                        for target in targets:
                            match_fields_json = target.get('match_fields', '')
                            if match_fields_json:
                                try:
                                    # 解析JSON配置
                                    config = json.loads(match_fields_json)
                                    pairs = config.get('pairs', [])
                                    
                                    if pairs:
                                        # 获取第一个字段对（用于字段1）
                                        first_pair = pairs[0]
                                        src_field = first_pair.get('src', '')
                                        tgt_field = first_pair.get('tgt', '')
                                        
                                        # 自动选择数据库图层匹配字段1
                                        if tgt_field:
                                            for i in range(self.database_field1_combo.count()):
                                                if self.database_field1_combo.itemText(i) == tgt_field:
                                                    self.database_field1_combo.setCurrentIndex(i)
                                                    self._log(f"[Step5] ✅ 已自动选择数据库图层匹配字段1: '{tgt_field}'", "info")
                                                    break
                                        
                                        # 获取第二个字段对（用于字段2）
                                        if len(pairs) >= 2:
                                            second_pair = pairs[1]
                                            tgt_field2 = second_pair.get('tgt', '')
                                            if tgt_field2:
                                                for i in range(self.database_field2_combo.count()):
                                                    if self.database_field2_combo.itemText(i) == tgt_field2:
                                                        self.database_field2_combo.setCurrentIndex(i)
                                                        self._log(f"[Step5] ✅ 已自动选择数据库图层匹配字段2: '{tgt_field2}'", "info")
                                                        break
                                        
                                        return  # 找到配置后退出
                                except Exception as e:
                                    self._log(f"[Step5] 解析Step4匹配字段配置失败: {e}", "warning")
        
        except Exception as e:
            self._log(f"[Step5] 加载Step4匹配字段配置失败: {e}", "error")
    
    def _find_original_file_from_processed_name(self, processed_file_name: str, cache_folder: str) -> Optional[str]:
        """
        从处理后的文件名（如：廊坊工商户_清洗_标准化.csv）反向查找到原始文件名（如：廊坊工商户.csv）
        """
        try:
            # 去掉文件扩展名和后缀
            base_name = os.path.splitext(processed_file_name)[0]
            # 去掉处理后缀
            for suffix in ['_标准化', '_清洗', '_清洗_标准化']:
                if base_name.endswith(suffix):
                    base_name = base_name[:-len(suffix)]
                    break
            
            # 从file_status.json查找
            file_status_path = os.path.join(cache_folder, "file_status.json")
            if os.path.exists(file_status_path):
                with open(file_status_path, 'r', encoding='utf-8') as f:
                    file_status = json.load(f)
                    
                    # 查找匹配的原始文件名
                    for file_name, status in file_status.items():
                        file_base = os.path.splitext(file_name)[0]
                        if file_base == base_name:
                            # 检查是否是客户采集数据
                            if isinstance(status, dict):
                                source_type = status.get('source_type', '')
                                if source_type == "客户采集数据":
                                    return file_name
                            elif isinstance(status, str):
                                # 旧格式，尝试推断
                                pass
        except Exception as e:
            self._log(f"[Step5] 查找原始文件失败: {e}", "warning")
        
        return None
    
    def _find_original_file_by_name(self, source_name: str, cache_folder: str) -> Optional[str]:
        """
        根据源表名（如：廊坊工商户）查找原始文件名（如：廊坊工商户.csv）
        """
        try:
            file_status_path = os.path.join(cache_folder, "file_status.json")
            if os.path.exists(file_status_path):
                with open(file_status_path, 'r', encoding='utf-8') as f:
                    file_status = json.load(f)
                    
                    # 查找匹配的原始文件名
                    for file_name, status in file_status.items():
                        file_base = os.path.splitext(file_name)[0]
                        # 检查文件名是否以source_name开头
                        if file_base == source_name or file_base.startswith(source_name):
                            # 检查是否是客户采集数据
                            if isinstance(status, dict):
                                source_type = status.get('source_type', '')
                                if source_type == "客户采集数据":
                                    return file_name
        except Exception as e:
            self._log(f"[Step5] 根据名称查找原始文件失败: {e}", "warning")
        
        return None
    
    def _try_select_source_file(self, file_name: str):
        """尝试在下拉框中选择指定的原始客户数据文件（UI已重构，此方法不再需要）"""
        # UI已重构，原始客户数据文件自动关联，不再需要下拉框选择
        self._log(f"[Step5] ✅ 已自动关联原始客户数据文件: '{file_name}'", "info")
    
    def _is_shp_file_loaded(self, shp_path: str) -> bool:
        """检查SHP文件是否已经在QGIS中加载"""
        try:
            from qgis.core import QgsProject
            layers = QgsProject.instance().mapLayers().values()
            for layer in layers:
                if layer.type() == 0:  # QgsMapLayer.VectorLayer
                    if layer.dataProvider().name() == 'ogr':
                        layer_path = layer.source()
                        # 比较路径（标准化路径）
                        if os.path.normpath(layer_path) == os.path.normpath(shp_path):
                            return True
        except Exception as e:
            self._log(f"[Step5] 检查SHP文件加载状态失败: {e}", "warning")
        return False
    
    def _auto_load_shp_file(self, shp_path: str):
        """自动加载SHP文件到QGIS"""
        try:
            from qgis.core import QgsVectorLayer, QgsProject
            
            shp_file_name = os.path.basename(shp_path)
            layer_name = os.path.splitext(shp_file_name)[0]
            
            # 创建图层
            layer = QgsVectorLayer(shp_path, layer_name, "ogr")
            if not layer.isValid():
                self._log(f"[Step5] 无法加载SHP文件: {shp_path}", "error")
                return
            
            # 添加到QGIS项目
            QgsProject.instance().addMapLayer(layer)
            
            # 更新原始SHP文件列表的状态
            if shp_path in self._original_shp_files:
                self._original_shp_files[shp_path]['status'] = '已加载'
                self._original_shp_files[shp_path]['layer_name'] = layer_name
            
            # 刷新图层下拉框（如果组件存在）
            self._refresh_layer_combos()
            
            # 自动选择原始SHP图层下拉框（如果组件存在）
            if hasattr(self, 'original_shp_layer_combo'):
                for i in range(self.original_shp_layer_combo.count()):
                    if self.original_shp_layer_combo.itemText(i) == layer_name:
                        self.original_shp_layer_combo.setCurrentIndex(i)
                        # 触发字段加载
                        self._on_shp_layer_changed(layer_name)
                        break
            
            self._log(f"[Step5] 已自动加载SHP文件到QGIS: {layer_name}", "info")
        except Exception as e:
            self._log(f"[Step5] 自动加载SHP文件失败: {e}", "error")
            import traceback
            self._log(f"[Step5] 错误详情: {traceback.format_exc()}", "error")
    
    def _start_validation(self):
        """开始验证"""
        from qgis.PyQt.QtWidgets import QApplication
        from qgis.PyQt.QtCore import QThread
        
        # 先处理事件，确保UI响应
        QApplication.processEvents()
        
        # 如果已有验证线程在运行，先停止并清理
        if self._validation_thread and self._validation_thread.isRunning():
            self._log("[Step5] ⚠️ 检测到正在运行的验证，先停止...", "warning")
            self._validation_thread.terminate()
            waited = 0
            while self._validation_thread.isRunning() and waited < 2000:
                QApplication.processEvents()
                QThread.msleep(50)
                waited += 50
            if self._validation_thread.isRunning():
                self._validation_thread.wait(1000)
            try:
                self._validation_thread.progress_updated.disconnect()
                self._validation_thread.validation_completed.disconnect()
                self._validation_thread.validation_error.disconnect()
                self._validation_thread.log_message.disconnect()
            except:
                pass
            self._validation_thread.deleteLater()
            self._validation_thread = None
            QApplication.processEvents()
            QThread.msleep(200)  # 等待清理完成
        
        # 检查配置完整性
        error_messages = []
        
        # 1. 检查任务组（必填）
        if not self._current_task_group:
            error_messages.append("请选择任务组")
            if error_messages:
                from ..widgets.result_dialog import ResultDialog
                error_text = "配置不完整，请检查以下项：\n\n" + "\n".join(f"• {msg}" for msg in error_messages)
                ResultDialog.show_warning(self, "配置不完整", error_text)
                return
        
        # 2. 检查匹配结果文件（必填）- 从任务组的results中获取实际文件名
        results = self._current_task_group.get('results', {})
        match_file = None
        if results:
            if results.get('exact'):
                match_file = results['exact']
            elif results.get('high_confidence'):
                match_file = results['high_confidence']
            elif results.get('need_review'):
                match_file = results['need_review']
            elif results.get('unmatched'):
                match_file = results['unmatched']
        
        # 如果从results中没找到，尝试从下拉框获取
        if not match_file and hasattr(self, 'match_file_combo'):
            match_file = self.match_file_combo.currentText()
            if match_file == "请选择...":
                match_file = None
        
        if not match_file:
            error_messages.append("请选择匹配结果文件")
        
        # 3. 检查源表匹配字段（从Step2配置自动获取，支持多个字段）
        # 使用_auto_load_step2_combo_config中保存的所有匹配字段
        source_match_fields = getattr(self, '_matched_field_names', [])
        
        # 如果为空，尝试从下拉框获取（兜底方案）
        if not source_match_fields:
            field1_text = self.source_match_field1_combo.currentText()
            field2_text = self.source_match_field2_combo.currentText()
            
            if field1_text and field1_text != "请选择...":
                source_match_fields.append(field1_text)
            if field2_text and field2_text != "请选择..." and field2_text != field1_text:
                source_match_fields.append(field2_text)
        
        if not source_match_fields:
            error_messages.append("源表匹配字段未自动配置，请检查Step2配置")
        
        # 4. 检查数据库点图层（自动检测）
        if not hasattr(self, '_detected_db_layer') or not self._detected_db_layer:
            error_messages.append("未检测到数据库点图层（需要点图层，且有code和name字段）")
        
        # 5. 检查验证参数
        try:
            threshold_str = self.distance_threshold_input.text().strip()
            if not threshold_str:
                error_messages.append("请设置位置偏差阈值")
            else:
                threshold = float(threshold_str)
                if threshold <= 0:
                    error_messages.append("位置偏差阈值必须大于0")
        except ValueError:
            error_messages.append("位置偏差阈值必须是数字")
        
        # 如果有错误，显示提示
        if error_messages:
            from ..widgets.result_dialog import ResultDialog
            error_text = "配置不完整，请检查以下项：\n\n" + "\n".join(f"• {msg}" for msg in error_messages)
            ResultDialog.show_warning(self, "配置不完整", error_text)
            return
        
        # 配置完整，开始验证
        self._log("[Step5] 验证配置检查通过，开始验证", "info")
        
        # 准备验证配置
        global_config = self._get_global_config()
        if not global_config:
            from ..widgets.result_dialog import ResultDialog
            ResultDialog.show_error(self, "配置错误", "无法获取全局配置")
            return
        
        region_info = global_config.get_region_info()
        cache_folder = region_info.get('cache_folder', '')
        customer_folder = region_info.get('customer_folder', '')
        
        # 获取匹配结果文件路径（如果文件不存在，尝试查找相似的文件名）
        result_dir = os.path.join(cache_folder, "match_results")
        match_result_path = os.path.join(result_dir, match_file)
        
        if not os.path.exists(match_result_path):
            # 尝试查找相似的文件名（去掉条数部分）
            import re
            pattern = r'^(.+?)_(精确匹配|高置信度|需人工确认|未匹配)_\d+条\.csv$'
            match_obj = re.match(pattern, match_file)
            if match_obj:
                file_prefix = match_obj.group(1)
                file_type = match_obj.group(2)
                # 在目录中查找匹配的文件
                if os.path.exists(result_dir):
                    for f in os.listdir(result_dir):
                        if f.startswith(f"{file_prefix}_{file_type}_") and f.endswith('.csv'):
                            match_result_path = os.path.join(result_dir, f)
                            match_file = f  # 更新为实际文件名
                            self._log(f"[Step5] ✅ 找到实际文件: {f}", "info")
                            break
            
            # 如果还是找不到，报错
            if not os.path.exists(match_result_path):
                from ..widgets.result_dialog import ResultDialog
                ResultDialog.show_error(self, "文件不存在", f"匹配结果文件不存在: {match_result_path}")
                return
        
        # 获取原始客户数据文件路径（自动关联，从任务组的source_original沿file_chain追溯）
        source_file_path = None
        if self._current_task_group:
            source_original = self._current_task_group.get('source_original', '')
            if source_original:
                original_file_name = os.path.basename(source_original) if os.path.sep in source_original else source_original
                source_file_path = os.path.join(customer_folder, original_file_name)
                if not os.path.exists(source_file_path):
                    # 尝试从file_chain追溯
                    file_status_path = os.path.join(cache_folder, "file_status.json")
                    if os.path.exists(file_status_path):
                        with open(file_status_path, 'r', encoding='utf-8') as f:
                            file_status = json.load(f)
                            if original_file_name in file_status:
                                status = file_status[original_file_name]
                                if isinstance(status, dict):
                                    file_chain = status.get('file_chain', {})
                                    step1_original = file_chain.get('step1_original', '')
                                    if step1_original and os.path.exists(step1_original):
                                        source_file_path = step1_original
        
        if not source_file_path:
            source_file_path = match_result_path  # 如果没有原始文件，使用匹配结果文件
            self._log(f"[Step5] ⚠️ 原始客户数据文件未找到，使用匹配结果文件进行统计", "warning")
        
        # 获取所有原始SHP图层（从所有targets）
        targets = self._current_task_group.get('targets', [])
        original_shp_layers = []
        for target in targets:
            original_shp_path = target.get('original_path', '')
            if original_shp_path and os.path.exists(original_shp_path):
                from qgis.core import QgsProject
                # 查找已加载的图层
                layers = QgsProject.instance().mapLayers().values()
                for layer in layers:
                    if layer.type() == 0 and layer.dataProvider().name() == 'ogr':
                        layer_path = layer.source()
                        if os.path.normpath(layer_path) == os.path.normpath(original_shp_path):
                            original_shp_layers.append(layer)
                            break
        
        if not original_shp_layers:
            from ..widgets.result_dialog import ResultDialog
            ResultDialog.show_error(self, "配置错误", "未找到原始SHP图层，请确保已自动加载")
            return
        
        # 使用第一个SHP图层（如果有多个，后续可以扩展为分别验证）
        original_shp_layer = original_shp_layers[0]
        # 自动检测GID字段
        shp_gid_field = 'gid'
        fields = original_shp_layer.fields()
        field_names = [f.name().lower() for f in fields]
        if 'gid' in field_names:
            shp_gid_field = 'gid'
        elif 'id' in field_names:
            shp_gid_field = 'id'
        elif len(field_names) > 0:
            shp_gid_field = field_names[0]
        
        # 获取数据库点图层（自动检测的）
        database_layer = self._detected_db_layer
        if not database_layer:
            from ..widgets.result_dialog import ResultDialog
            ResultDialog.show_error(self, "配置错误", "未检测到数据库点图层")
            return
        
        # 检查坐标系并准备坐标转换
        self._log("[Step5] 检查坐标系...", "info")
        from qgis.core import QgsCoordinateReferenceSystem, QgsCoordinateTransform, QgsProject
        
        # 获取数据库图层的坐标系
        db_crs = database_layer.crs()
        if not db_crs.isValid():
            self._log("[Step5] ⚠️ 数据库图层坐标系无效，将使用默认坐标系", "warning")
            db_crs = QgsCoordinateReferenceSystem('EPSG:3857')  # 默认使用Web Mercator
        
        db_crs_authid = db_crs.authid() if db_crs.isValid() else 'Unknown'
        self._log(f"[Step5] 数据库图层坐标系: {db_crs_authid}", "info")
        
        # 获取SHP图层的坐标系
        shp_crs = original_shp_layer.crs()
        if not shp_crs.isValid():
            self._log("[Step5] ⚠️ SHP图层坐标系无效，将使用默认坐标系", "warning")
            shp_crs = QgsCoordinateReferenceSystem('EPSG:3857')  # 默认使用Web Mercator
        
        shp_crs_authid = shp_crs.authid() if shp_crs.isValid() else 'Unknown'
        self._log(f"[Step5] SHP图层坐标系: {shp_crs_authid}", "info")
        
        # 创建坐标转换器（如果需要）
        coord_transform = None
        if db_crs_authid != shp_crs_authid:
            self._log(f"[Step5] ⚠️ 坐标系不一致，将SHP坐标从 {shp_crs_authid} 转换为 {db_crs_authid}", "warning")
            coord_transform = QgsCoordinateTransform(shp_crs, db_crs, QgsProject.instance())
            if not coord_transform.isValid():
                self._log("[Step5] ⚠️ 坐标转换器创建失败，将使用原始坐标", "warning")
                coord_transform = None
            else:
                self._log(f"[Step5] ✅ 坐标转换器已创建，将在构建SHP索引时自动转换坐标", "info")
        else:
            self._log(f"[Step5] ✅ 坐标系一致 ({db_crs_authid})，无需转换，直接使用原始坐标", "info")
        
        # 在主线程中预先构建索引（QGIS图层操作必须在主线程中执行）
        self._log("[Step5] 在主线程中构建图层索引...", "info")
        from ...core.validation_engine import ValidationEngine
        
        # 创建临时验证引擎用于构建索引（不使用进度回调，避免干扰）
        temp_engine = ValidationEngine(log_callback=self._log)
        
        # 构建数据库图层索引（在主线程中）
        self._log("[Step5] 构建数据库图层索引...", "info")
        if hasattr(self, 'validation_progress'):
            self.validation_progress.setValue(15)
            self.validation_progress.setVisible(True)
        if hasattr(self, 'validation_status_label'):
            self.validation_status_label.setText("构建数据库图层索引...")
        
        # 处理事件，确保UI更新
        from qgis.PyQt.QtWidgets import QApplication
        QApplication.processEvents()
        
        db_index = temp_engine._build_database_index(database_layer)
        
        # 构建完成后再次处理事件
        QApplication.processEvents()
        
        # 构建SHP图层索引（在主线程中，使用坐标转换）
        self._log("[Step5] 构建原始SHP图层索引...", "info")
        if hasattr(self, 'validation_progress'):
            self.validation_progress.setValue(20)
        if hasattr(self, 'validation_status_label'):
            self.validation_status_label.setText("构建原始SHP图层索引...")
        
        # 处理事件，确保UI更新
        QApplication.processEvents()
        
        shp_index = temp_engine._build_shp_index(original_shp_layer, shp_gid_field, coord_transform)
        
        # 构建完成后再次处理事件
        QApplication.processEvents()
        
        # 将索引中的QgsFeature转换为纯数据（避免在后台线程中使用QGIS对象）
        # 数据库索引：将feature转换为(code, name, x, y)元组
        self._log("[Step5] 转换数据库索引为纯数据...", "info")
        if hasattr(self, 'validation_progress'):
            self.validation_progress.setValue(25)
        if hasattr(self, 'validation_status_label'):
            self.validation_status_label.setText("转换数据库索引为纯数据...")
        
        from qgis.PyQt.QtWidgets import QApplication
        
        db_index_data = {
            'code': {},
            'name': {}
        }
        total_code_features = sum(len(features) for features in db_index.get('code', {}).values())
        total_name_features = sum(len(features) for features in db_index.get('name', {}).values())
        processed_code = 0
        processed_name = 0
        
        for code_key, features in db_index.get('code', {}).items():
            db_index_data['code'][code_key] = []
            for feat in features:
                processed_code += 1
                # 每处理200个要素更新一次进度（更频繁，避免卡死）
                if processed_code % 200 == 0:
                    if hasattr(self, 'validation_progress'):
                        self.validation_progress.setValue(25 + int((processed_code / total_code_features) * 5))
                    if hasattr(self, 'validation_status_label'):
                        self.validation_status_label.setText(f"转换数据库索引... ({processed_code}/{total_code_features})")
                    QApplication.processEvents()
                    # 额外等待，确保UI有时间响应
                    from qgis.PyQt.QtCore import QThread
                    QThread.msleep(10)
                
                code_val = str(feat.attribute('code') or '').strip()
                name_val = str(feat.attribute('name') or '').strip()
                geom = feat.geometry()
                if geom and geom.type() == 0:  # Point
                    point = geom.asPoint()
                    db_index_data['code'][code_key].append({
                        'code': code_val,
                        'name': name_val,
                        'x': point.x(),
                        'y': point.y()
                    })
        
        for name_key, features in db_index.get('name', {}).items():
            db_index_data['name'][name_key] = []
            for feat in features:
                processed_name += 1
                # 每处理200个要素更新一次进度（更频繁，避免卡死）
                if processed_name % 200 == 0:
                    if hasattr(self, 'validation_progress'):
                        self.validation_progress.setValue(30 + int((processed_name / total_name_features) * 5))
                    if hasattr(self, 'validation_status_label'):
                        self.validation_status_label.setText(f"转换数据库索引... ({processed_name}/{total_name_features})")
                    QApplication.processEvents()
                    # 额外等待，确保UI有时间响应
                    from qgis.PyQt.QtCore import QThread
                    QThread.msleep(10)
                
                code_val = str(feat.attribute('code') or '').strip()
                name_val = str(feat.attribute('name') or '').strip()
                geom = feat.geometry()
                if geom and geom.type() == 0:  # Point
                    point = geom.asPoint()
                    db_index_data['name'][name_key].append({
                        'code': code_val,
                        'name': name_val,
                        'x': point.x(),
                        'y': point.y()
                    })
        
        self._log("[Step5] 索引转换完成，准备启动验证线程...", "info")
        
        # 构建验证配置（传递索引数据，而不是图层对象）
        validation_config = {
            'match_result_file': match_result_path,
            'original_customer_file': source_file_path,
            'db_index': db_index_data,  # 纯数据索引
            'shp_index': shp_index,  # SHP索引已经是纯数据（已转换为数据库坐标系）
            'original_shp_gid_field': shp_gid_field,
            'database_match_field': 'name',  # 固定使用name字段
            'source_match_fields': source_match_fields,  # 多个字段的列表
            'deviation_threshold': threshold,
            'db_crs': db_crs  # 数据库坐标系（用于距离计算）
        }
        
        # 执行验证（在后台线程中执行，避免UI冻结）
        self._execute_validation(validation_config)
    
    def _execute_validation(self, config: Dict):
        """在后台线程中执行验证"""
        from qgis.PyQt.QtWidgets import QApplication
        from qgis.PyQt.QtCore import QThread
        
        # 如果已有验证线程在运行，先停止并断开所有信号连接
        if self._validation_thread:
            if self._validation_thread.isRunning():
                self._log("[Step5] 停止旧的验证线程...", "info")
                self._validation_thread.terminate()
                # 等待线程结束，并处理事件
                waited = 0
                while self._validation_thread.isRunning() and waited < 3000:
                    QApplication.processEvents()
                    QThread.msleep(50)
                    waited += 50
                
                if self._validation_thread.isRunning():
                    self._log("[Step5] ⚠️ 旧线程未能在3秒内停止，强制终止", "warning")
                    self._validation_thread.terminate()
                    self._validation_thread.wait(1000)
            
            # 断开所有信号连接，避免重复连接
            try:
                self._validation_thread.progress_updated.disconnect()
                self._validation_thread.validation_completed.disconnect()
                self._validation_thread.validation_error.disconnect()
                self._validation_thread.log_message.disconnect()
            except:
                pass  # 如果信号未连接，忽略错误
            
            self._validation_thread.deleteLater()
            self._validation_thread = None
            
            # 再次处理事件，确保旧线程完全清理
            QApplication.processEvents()
            QThread.msleep(100)  # 额外等待，确保清理完成
        
        # 验证配置已经包含预先构建的索引数据（不需要再传递图层对象）
        validation_config = config
        
        self._validation_thread = ValidationThread(validation_config, log_callback=self._log)
        self._validation_thread.progress_updated.connect(self._on_validation_progress)
        self._validation_thread.validation_completed.connect(self._on_validation_completed)
        self._validation_thread.validation_error.connect(self._on_validation_error)
        self._validation_thread.log_message.connect(self._on_validation_log)  # 连接日志信号
        
        # 禁用验证按钮，显示进度条
        btn_validate = self.findChild(QPushButton, "step5_btn_validate")
        if btn_validate:
            btn_validate.setEnabled(False)
            btn_validate.setText("验证中...")
        
        # 显示进度条，重置状态（参考Step2/Step3）
        if hasattr(self, 'validation_progress'):
            self.validation_progress.setValue(0)
            self.validation_progress.setMaximum(100)
            self.validation_progress.setVisible(True)
        if hasattr(self, 'validation_status_label'):
            self.validation_status_label.setText("准备验证...")
        
        # 展开结果区域
        if hasattr(self, 'results_section'):
            self.results_section.set_expanded(True)
        
        # 启动线程
        self._validation_thread.start()
        self._log("[Step5] 验证线程已启动", "info")
    
    def _on_validation_log(self, msg: str, level: str):
        """验证日志消息（线程安全）"""
        # 在主线程中调用日志方法
        self._log(msg, level)
    
    def _on_validation_progress(self, current: int, total: int, message: str):
        """验证进度更新（参考Step2/Step3的实现）"""
        # 更新进度条
        if hasattr(self, 'validation_progress'):
            self.validation_progress.setMaximum(total)
            self.validation_progress.setValue(current)
            self.validation_progress.setVisible(True)
        
        # 更新状态标签
        if hasattr(self, 'validation_status_label'):
            percentage = int((current / total * 100)) if total > 0 else 0
            self.validation_status_label.setText(f"{message} ({percentage}%)")
        
        # 输出日志
        self._log(f"[Step5] {message} ({current}/{total})", "info")
    
    def _on_validation_completed(self, result: Dict):
        """验证完成"""
        from qgis.PyQt.QtWidgets import QApplication
        from qgis.PyQt.QtCore import QThread
        
        # 先处理事件，确保UI响应
        QApplication.processEvents()
        
        self._validation_result = result
        
        # 隐藏进度条，更新状态标签
        if hasattr(self, 'validation_progress'):
            self.validation_progress.setVisible(False)
        if hasattr(self, 'validation_status_label'):
            self.validation_status_label.setText("验证完成")
        
        # 处理事件，确保UI更新
        QApplication.processEvents()
        
        # 恢复验证按钮
        btn_validate = self.findChild(QPushButton, "step5_btn_validate")
        if btn_validate:
            btn_validate.setEnabled(True)
            btn_validate.setText("开始验证")
        
        # 处理事件，确保按钮状态更新
        QApplication.processEvents()
        
        # 更新统计卡片
        self._update_stat_cards(result)
        
        # 处理事件，确保统计卡片更新
        QApplication.processEvents()
        
        # 更新统计详情
        self._update_stats_detail(result)
        
        # 处理事件，确保统计详情更新
        QApplication.processEvents()
        
        # 更新问题数据表格（这可能是最耗时的操作）
        self._update_problem_table(result)
        
        # 最后处理事件，确保表格更新
        QApplication.processEvents()
        
        # 更新问题数据列表
        self._update_problem_table(result)
        
        self._log("[Step5] ✅ 验证完成", "success")
    
    def _on_validation_error(self, error_msg: str):
        """验证错误"""
        # 隐藏进度条，更新状态标签
        if hasattr(self, 'validation_progress'):
            self.validation_progress.setVisible(False)
        if hasattr(self, 'validation_status_label'):
            self.validation_status_label.setText("验证失败")
        
        # 恢复验证按钮
        btn_validate = self.findChild(QPushButton, "step5_btn_validate")
        if btn_validate:
            btn_validate.setEnabled(True)
            btn_validate.setText("开始验证")
        
        from ..widgets.result_dialog import ResultDialog
        ResultDialog.show_error(self, "验证失败", error_msg)
        self._log(f"[Step5] ❌ 验证失败: {error_msg}", "error")
    
    def _update_stat_cards(self, result: Dict):
        """更新统计卡片"""
        stats = result.get('statistics', {})
        
        # 原始数据总数
        original_total = stats.get('original_total', 0)
        self._update_stat_card(self.stat_source_total, "原始数据总数", str(original_total))
        
        # 匹配总数
        match_total = stats.get('match_total', 0)
        self._update_stat_card(self.stat_matched_total, "匹配总数", str(match_total))
        
        # 原始客户数据在数据库中的完整性
        original_completeness = stats.get('original_completeness', {})
        original_found = original_completeness.get('found', 0)
        original_missing = original_completeness.get('missing', 0)
        
        # 匹配结果在数据库中的完整性
        match_completeness = stats.get('match_completeness', {})
        match_found = match_completeness.get('found', 0)
        match_missing = match_completeness.get('missing', 0)
        
        # 位置偏差统计
        deviation_stats = stats.get('deviation', {})
        within_threshold = deviation_stats.get('within_threshold', 0)
        exceed_threshold = deviation_stats.get('exceed_threshold', 0)
        
        # 重复数据统计
        duplicate_stats = stats.get('duplicates', {})
        duplicate_values = duplicate_stats.get('duplicate_values', 0)
        
        # 验证通过（匹配结果在数据库中存在且位置偏差在阈值内）
        valid_count = match_found - exceed_threshold
        self._update_stat_card(self.stat_valid, "验证通过", str(valid_count))
        
        # 缺失数据（匹配结果在数据库中缺失）
        self._update_stat_card(self.stat_missing, "缺失数据", str(match_missing))
        
        # 位置偏差（超过阈值）
        self._update_stat_card(self.stat_deviation, "位置偏差", str(exceed_threshold))
        
        # 重复数据
        self._update_stat_card(self.stat_duplicate, "重复数据", str(duplicate_values))
    
    def _update_stat_card(self, card_widget: QWidget, title: str, value: str):
        """更新单个统计卡片"""
        # 直接通过存储的属性更新
        if hasattr(card_widget, 'title_label'):
            card_widget.title_label.setText(title)
        if hasattr(card_widget, 'value_label'):
            card_widget.value_label.setText(value)
    
    def _update_stats_detail(self, result: Dict):
        """更新统计详情"""
        stats = result.get('statistics', {})
        detail_text = "验证统计详情：\n\n"
        
        # 原始客户数据统计
        original_total = stats.get('original_total', 0)
        original_completeness = stats.get('original_completeness', {})
        if original_total > 0:
            detail_text += f"原始客户数据总数: {original_total}\n"
            detail_text += f"  在数据库中存在: {original_completeness.get('found', 0)} ({original_completeness.get('completeness_rate', 0):.2f}%)\n"
            detail_text += f"  在数据库中缺失: {original_completeness.get('missing', 0)}\n"
        
        # 匹配结果统计
        match_total = stats.get('match_total', 0)
        match_completeness = stats.get('match_completeness', {})
        detail_text += f"\n匹配结果总数: {match_total}\n"
        detail_text += f"  在数据库中存在: {match_completeness.get('found', 0)} ({match_completeness.get('completeness_rate', 0):.2f}%)\n"
        detail_text += f"  在数据库中缺失: {match_completeness.get('missing', 0)}\n"
        
        # 位置偏差统计
        deviation = stats.get('deviation', {})
        detail_text += f"\n位置偏差统计:\n"
        detail_text += f"  检查总数: {deviation.get('total_checked', 0)}\n"
        detail_text += f"  在阈值内: {deviation.get('within_threshold', 0)} ({deviation.get('within_rate', 0):.2f}%)\n"
        detail_text += f"  超过阈值: {deviation.get('exceed_threshold', 0)}\n"
        if deviation.get('no_shp_coord', 0) > 0:
            detail_text += f"  无原始坐标: {deviation.get('no_shp_coord', 0)}\n"
        if deviation.get('no_db_coord', 0) > 0:
            detail_text += f"  无数据库坐标: {deviation.get('no_db_coord', 0)}\n"
        
        # 重复数据统计
        duplicate = stats.get('duplicates', {})
        detail_text += f"\n重复数据统计:\n"
        detail_text += f"  重复匹配值数: {duplicate.get('duplicate_values', 0)}\n"
        detail_text += f"  重复记录数: {duplicate.get('duplicate_records', 0)}\n"
        
        self.stats_detail_label.setText(detail_text)
    
    def _update_problem_table(self, result: Dict):
        """更新问题数据表格"""
        import time
        from qgis.PyQt.QtWidgets import QApplication
        
        start_time = time.time()
        self._log(f"[Step5] ========== 开始更新问题数据表格 ==========", "info")
        
        problem_data = result.get('problem_data', {})
        
        # 添加日志输出
        missing_count = len(problem_data.get('missing', []))
        deviation_count = len(problem_data.get('deviation', []))
        duplicate_count = len(problem_data.get('duplicate', []))
        self._log(f"[Step5] 问题数据统计: 缺失={missing_count}, 偏差={deviation_count}, 重复={duplicate_count}", "info")
        
        # 合并所有问题数据
        self._all_problems = []
        
        # 缺失数据
        self._log(f"[Step5] [表格更新-阶段1] 开始处理缺失数据，共{missing_count}条...", "info")
        missing_start = time.time()
        missing_list = problem_data.get('missing', [])
        for idx, missing in enumerate(missing_list):
            # 每处理100条数据，让出控制权
            if idx > 0 and idx % 100 == 0:
                elapsed = time.time() - missing_start
                self._log(f"[Step5] [表格更新-阶段1] 进度: {idx}/{missing_count} ({idx*100//missing_count if missing_count>0 else 0}%), 已耗时={elapsed:.2f}秒", "info")
                QApplication.processEvents()
            row_data = missing.get('row', {})
            # 只提取gid字段的值（不提取code字段）
            target_gid = ''
            import math
            for col in row_data.keys():
                if '[目标:' in col and 'gid' in col.lower() and 'code' not in col.lower():
                    val = row_data.get(col)
                    # 处理pandas的nan值：如果值是nan或空，跳过
                    if val is not None and not (isinstance(val, float) and math.isnan(val)):
                        val_str = str(val).strip()
                        if val_str and val_str.lower() != 'nan':
                            target_gid = val_str
                            break
            
            self._all_problems.append({
                'type': 'missing',
                'target_gid': target_gid,
                'db_code': None,  # 缺失数据没有匹配到数据库，所以db_code为None
                'match_value': self._get_match_value_from_row(row_data),
                'status': '缺失',
                'deviation': None,
                'shp_coord': None,
                'db_coord': None,
                'row_data': row_data
            })
        
        missing_time = time.time() - missing_start
        self._log(f"[Step5] [表格更新-阶段1] 缺失数据处理完成，耗时={missing_time:.2f}秒", "info")
        
        # 位置偏差数据
        self._log(f"[Step5] [表格更新-阶段2] 开始处理位置偏差数据，共{deviation_count}条...", "info")
        deviation_start = time.time()
        deviation_list = problem_data.get('deviation', [])
        for idx, deviation_item in enumerate(deviation_list):
            # 每处理100条数据，让出控制权
            if idx > 0 and idx % 100 == 0:
                elapsed = time.time() - deviation_start
                self._log(f"[Step5] [表格更新-阶段2] 进度: {idx}/{deviation_count} ({idx*100//deviation_count if deviation_count>0 else 0}%), 已耗时={elapsed:.2f}秒", "info")
                QApplication.processEvents()
            row_data = deviation_item.get('row', {})
            # 只提取gid字段的值（不提取code字段）
            target_gid = ''
            import math
            for col in row_data.keys():
                if '[目标:' in col and 'gid' in col.lower() and 'code' not in col.lower():
                    val = row_data.get(col)
                    # 处理pandas的nan值
                    if val is not None and not (isinstance(val, float) and math.isnan(val)):
                        val_str = str(val).strip()
                        if val_str and val_str.lower() != 'nan':
                            target_gid = val_str
                            break
            
            # 提取匹配到的数据库code（从deviation_item中获取，如果有的话）
            db_code = deviation_item.get('db_code', '')
            
            self._all_problems.append({
                'type': 'deviation',
                'target_gid': target_gid,
                'db_code': db_code,  # 位置偏差数据应该匹配到了数据库
                'match_value': self._get_match_value_from_row(row_data),
                'status': '位置偏差',
                'deviation': deviation_item.get('deviation'),
                'shp_coord': deviation_item.get('shp_coord'),
                'db_coord': deviation_item.get('db_coord'),
                'row_data': row_data
            })
        
        deviation_time = time.time() - deviation_start
        self._log(f"[Step5] [表格更新-阶段2] 位置偏差数据处理完成，耗时={deviation_time:.2f}秒", "info")
        
        # 重复数据
        self._log(f"[Step5] [表格更新-阶段3] 开始处理重复数据，共{duplicate_count}条...", "info")
        duplicate_start = time.time()
        duplicate_list = problem_data.get('duplicate', [])
        for idx, duplicate in enumerate(duplicate_list):
            # 每处理50条数据，让出控制权（更频繁，避免卡死）
            if idx > 0 and idx % 50 == 0:
                elapsed = time.time() - duplicate_start
                self._log(f"[Step5] [表格更新-阶段3] 进度: {idx}/{duplicate_count} ({idx*100//duplicate_count if duplicate_count>0 else 0}%), 已耗时={elapsed:.2f}秒", "info")
                QApplication.processEvents()
            # 如果是最后一条，也处理事件
            if idx == len(duplicate_list) - 1:
                QApplication.processEvents()
            row_data = duplicate.get('row', {})
            # 只提取gid字段的值（不提取code字段）
            target_gid = ''
            import math
            for col in row_data.keys():
                if '[目标:' in col and 'gid' in col.lower() and 'code' not in col.lower():
                    val = row_data.get(col)
                    # 处理pandas的nan值
                    if val is not None and not (isinstance(val, float) and math.isnan(val)):
                        val_str = str(val).strip()
                        if val_str and val_str.lower() != 'nan':
                            target_gid = val_str
                            break
            
            # 提取匹配到的数据库code（从duplicate中直接获取）
            db_code = duplicate.get('db_code', '')
            
            # 处理match_value，去掉code:或name:前缀
            match_value = duplicate.get('match_value', '')
            if match_value.startswith('code:') or match_value.startswith('name:'):
                match_value = match_value.split(':', 1)[1] if ':' in match_value else match_value
            
            self._all_problems.append({
                'type': 'duplicate',
                'target_gid': target_gid,
                'db_code': db_code,
                'match_value': match_value,
                'status': f"重复({duplicate.get('duplicate_count', 0)}个)",
                'deviation': None,
                'shp_coord': None,
                'db_coord': None,
                'row_data': row_data
            })
        
        duplicate_time = time.time() - duplicate_start
        self._log(f"[Step5] [表格更新-阶段3] 重复数据处理完成，耗时={duplicate_time:.2f}秒", "info")
        
        # 显示所有问题数据
        self._log(f"[Step5] 收集到的问题数据总数: {len(self._all_problems)}", "info")
        if len(self._all_problems) > 0:
            # 优化统计：直接使用已知的计数，避免遍历
            self._log(f"[Step5] 问题数据统计: 缺失={missing_count}, 偏差={deviation_count}, 重复={duplicate_count}", "info")
            self._log(f"[Step5] 问题数据示例（前3条）:", "info")
            for i, prob in enumerate(self._all_problems[:3]):
                match_value = prob.get('match_value', '')
                if len(match_value) > 50:
                    match_value = match_value[:50] + "..."
                self._log(f"  问题{i+1}: type={prob.get('type')}, target_gid={prob.get('target_gid')}, status={prob.get('status')}, match_value={match_value}", "info")
        else:
            self._log(f"[Step5] ⚠️ 未收集到任何问题数据，请检查验证逻辑", "warning")
        
        self._log(f"[Step5] [表格更新-阶段4] 开始显示问题数据到表格，共{len(self._all_problems)}条...", "info")
        display_start = time.time()
        
        # 分批渲染：先显示前500条，然后异步加载剩余部分
        if len(self._all_problems) > 500:
            self._log(f"[Step5] [表格更新-阶段4] 数据量较大，使用分批渲染策略...", "info")
            # 先显示前500条
            first_batch = self._all_problems[:500]
            self._display_problems_batch(first_batch, 0, update_enabled=True)
            # 剩余数据异步加载
            remaining_problems = self._all_problems[500:]
            from qgis.PyQt.QtCore import QTimer
            QTimer.singleShot(100, lambda: self._display_problems_batch_async(remaining_problems, 500))
            display_time = time.time() - display_start
            self._log(f"[Step5] [表格更新-阶段4] 前500条数据已显示，耗时={display_time:.2f}秒，剩余{len(remaining_problems)}条异步加载中...", "info")
        else:
            # 数据量小，直接显示
            self._display_problems(self._all_problems)
            display_time = time.time() - display_start
            self._log(f"[Step5] [表格更新-阶段4] 表格显示完成，耗时={display_time:.2f}秒", "info")
        
        total_time = time.time() - start_time
        self._log(f"[Step5] ========== 问题数据表格更新完成 ==========", "info")
        self._log(f"[Step5] 总耗时={total_time:.2f}秒 (缺失={missing_time:.2f}秒, 偏差={deviation_time:.2f}秒, 重复={duplicate_time:.2f}秒)", "info")
    
    def _display_problems(self, problems: List[Dict]):
        """显示问题数据到表格（优化版本：禁用更新，批量设置）"""
        import time
        from qgis.PyQt.QtWidgets import QApplication
        
        display_start = time.time()
        self._log(f"[Step5] [表格更新-阶段4] 开始显示问题数据到表格，共{len(problems)}条...", "info")
        
        # 禁用表格自动更新，提高性能
        self.problem_table.setUpdatesEnabled(False)
        self.problem_table.setSortingEnabled(False)  # 禁用排序，设置数据时更快
        
        try:
            # 更新表格行数
            self.problem_table.setRowCount(len(problems))
            QApplication.processEvents()
            
            # 批量设置数据
            for row, problem in enumerate(problems):
                # 每处理100行数据，让出控制权并记录进度
                if row > 0 and row % 100 == 0:
                    elapsed = time.time() - display_start
                    self._log(f"[Step5] [表格更新-阶段4] 进度: {row}/{len(problems)} ({row*100//len(problems) if len(problems)>0 else 0}%), 已耗时={elapsed:.2f}秒", "info")
                    # 暂时启用更新，让UI响应
                    self.problem_table.setUpdatesEnabled(True)
                    QApplication.processEvents()
                    self.problem_table.setUpdatesEnabled(False)
                
                # 目标表GID（只显示gid字段的值）
                target_gid = problem.get('target_gid', '')
                self.problem_table.setItem(row, 0, QTableWidgetItem(target_gid))
                
                # 数据库code（如果匹配到了显示code，没匹配到显示"-"）
                db_code = problem.get('db_code', '')
                if not db_code:
                    db_code = '-'
                self.problem_table.setItem(row, 1, QTableWidgetItem(db_code))
                
                # 源表匹配值
                self.problem_table.setItem(row, 2, QTableWidgetItem(problem.get('match_value', '')))
                
                # 状态
                status = problem.get('status', '')
                status_item = QTableWidgetItem(status)
                if '缺失' in status:
                    status_item.setForeground(QColor(220, 53, 69))  # 红色
                elif '位置偏差' in status:
                    status_item.setForeground(QColor(255, 193, 7))  # 橙色
                elif '重复' in status:
                    status_item.setForeground(QColor(255, 152, 0))  # 黄色
                self.problem_table.setItem(row, 3, status_item)
                
                # 偏差距离
                deviation = problem.get('deviation')
                distance_text = f"{deviation:.2f}米" if deviation is not None else "-"
                self.problem_table.setItem(row, 4, QTableWidgetItem(distance_text))
                
                # 原始坐标
                shp_coord = problem.get('shp_coord')
                try:
                    coord_text = f"({shp_coord[0]:.6f}, {shp_coord[1]:.6f})" if shp_coord and len(shp_coord) >= 2 else "-"
                except (TypeError, IndexError):
                    coord_text = "-"
                self.problem_table.setItem(row, 5, QTableWidgetItem(coord_text))
                
                # 数据库坐标
                db_coord = problem.get('db_coord')
                try:
                    coord_text = f"({db_coord[0]:.6f}, {db_coord[1]:.6f})" if db_coord and len(db_coord) >= 2 else "-"
                except (TypeError, IndexError):
                    coord_text = "-"
                self.problem_table.setItem(row, 6, QTableWidgetItem(coord_text))
            
            # 数据设置完成，启用更新
            self.problem_table.setUpdatesEnabled(True)
            QApplication.processEvents()
            
            # 延迟调整列宽（使用QTimer异步执行，避免阻塞）
            display_time = time.time() - display_start
            self._log(f"[Step5] [表格更新-阶段4] 数据填充完成，耗时={display_time:.2f}秒，延迟调整列宽...", "info")
            
            # 使用QTimer延迟调整列宽，避免阻塞UI
            from qgis.PyQt.QtCore import QTimer
            QTimer.singleShot(100, self._adjust_table_columns)
        except Exception as e:
            # 确保即使出错也重新启用更新
            self.problem_table.setUpdatesEnabled(True)
            self._log(f"[Step5] [表格更新-阶段4] 表格显示出错: {e}", "error")
            raise
    
    def _filter_problems(self, filter_type: str):
        """筛选问题数据"""
        # 重置所有按钮状态
        self.filter_all_btn.setChecked(filter_type == 'all')
        self.filter_missing_btn.setChecked(filter_type == 'missing')
        self.filter_deviation_btn.setChecked(filter_type == 'deviation')
        self.filter_duplicate_btn.setChecked(filter_type == 'duplicate')
        
        if filter_type == 'all':
            filtered_problems = self._all_problems
        else:
            filtered_problems = [p for p in self._all_problems if p.get('type') == filter_type]
        
        self._display_problems(filtered_problems)
    
    def _get_match_value_from_row(self, row_data: Dict) -> str:
        """从行数据中获取匹配值（显示所有配置的匹配字段，用分号分隔）"""
        # 使用所有匹配的字段（从_matched_field_names获取）
        matched_fields = getattr(self, '_matched_field_names', [])
        
        # 如果没有保存的匹配字段，从下拉框获取
        if not matched_fields:
            field1 = self.source_match_field1_combo.currentText()
            field2 = self.source_match_field2_combo.currentText()
            if field1 and field1 != "请选择...":
                matched_fields.append(field1)
            if field2 and field2 != "请选择..." and field2 != field1:
                matched_fields.append(field2)
        
        # 获取所有字段的值（只显示值，不显示字段名，用分号分隔）
        values = []
        for field in matched_fields:
            val = str(row_data.get(field, '') or '').strip()
            if val:
                values.append(val)
        
        # 用分号分隔（更清晰，表格单元格支持）
        if values:
            return "; ".join(values)
        return ""
    
    def _zoom_to_selected(self):
        """定位到选中的问题数据"""
        selected_rows = self.problem_table.selectionModel().selectedRows()
        if not selected_rows:
            from ..widgets.result_dialog import ResultDialog
            ResultDialog.show_warning(self, "未选择", "请先选择要定位的问题数据")
            return
        
        try:
            from qgis.core import QgsProject, QgsRectangle
            from qgis.gui import QgsMapCanvas
            
            # 获取自动检测的数据库图层
            db_layer = getattr(self, '_detected_db_layer', None)
            if not db_layer:
                from ..widgets.result_dialog import ResultDialog
                ResultDialog.show_warning(self, "未检测到图层", "未检测到数据库点图层，无法定位")
                return
            
            # 获取选中的问题数据
            selected_problems = []
            for row_index in selected_rows:
                row = row_index.row()
                problem = self._all_problems[row]  # 获取完整的问题数据对象
                selected_problems.append(problem)
            
            # 在数据库图层中查找对应的要素并定位
            found_features = []
            for problem in selected_problems:
                target_gid = problem.get('target_gid', '').strip()
                row_data = problem.get('row_data', {})
                
                # 1. 优先用target_gid（对应数据库的code字段）查找
                if target_gid and target_gid.lower() != 'nan':
                    for feature in db_layer.getFeatures():
                        code_val = str(feature.attribute('code') or '').strip()
                        if code_val.lower() == target_gid.lower():
                            found_features.append(feature)
                            break
                
                # 2. 如果GID匹配不到，用匹配字段查找（匹配数据库的name字段）
                if not found_features or found_features[-1].id() == -1:
                    matched_fields = getattr(self, '_matched_field_names', [])
                    for field in matched_fields:
                        match_value = str(row_data.get(field, '') or '').strip()
                        if match_value:
                            for feature in db_layer.getFeatures():
                                name_val = str(feature.attribute('name') or '').strip()
                                if name_val.lower() == match_value.lower():
                                    found_features.append(feature)
                                    break
                            if found_features and found_features[-1].id() != -1:
                                break
            
            if not found_features:
                from ..widgets.result_dialog import ResultDialog
                ResultDialog.show_warning(self, "未找到", "未在数据库图层中找到对应的要素")
                return
            
            # 定位到第一个找到的要素
            first_feature = found_features[0]
            geom = first_feature.geometry()
            if geom and geom.type() == 0:  # Point
                point = geom.asPoint()
                # 获取QGIS主窗口的map canvas并定位
                from qgis.core import QgsApplication
                canvas = None
                for widget in QgsApplication.instance().allWidgets():
                    if hasattr(widget, 'mapCanvas'):
                        canvas = widget.mapCanvas()
                        break
                
                if canvas:
                    canvas.setCenter(point)
                    canvas.zoomScale(1000)  # 缩放到合适比例
                    canvas.refresh()
                    self._log(f"[Step5] ✅ 已定位到 {len(found_features)} 个要素", "info")
                else:
                    self._log(f"[Step5] ⚠️ 未找到地图画布，无法定位", "warning")
            
        except Exception as e:
            self._log(f"[Step5] 定位失败: {e}", "error")
            import traceback
            self._log(f"[Step5] 错误详情: {traceback.format_exc()}", "error")
    
    def _export_problems(self):
        """导出问题数据"""
        if not self._validation_result or not self._all_problems:
            from ..widgets.result_dialog import ResultDialog
            ResultDialog.show_warning(self, "无数据", "请先执行验证")
            return
        
        # 选择保存路径
        global_config = self._get_global_config()
        if not global_config:
            return
        
        region_info = global_config.get_region_info()
        base_folder = region_info.get('base_folder', '')
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, "导出问题数据", 
            os.path.join(base_folder, "问题数据.csv"),
            "CSV文件 (*.csv)"
        )
        
        if not file_path:
            return
        
        try:
            # 转换为DataFrame并导出
            import pandas as pd
            df = pd.DataFrame(self._all_problems)
            df.to_csv(file_path, index=False, encoding='utf-8-sig')
            self._log(f"[Step5] ✅ 问题数据已导出: {file_path}", "success")
            
            from ..widgets.result_dialog import ResultDialog
            ResultDialog.show_success(self, "导出成功", f"问题数据已导出到:\n{file_path}")
        except Exception as e:
            self._log(f"[Step5] 导出失败: {e}", "error")
            from ..widgets.result_dialog import ResultDialog
            ResultDialog.show_error(self, "导出失败", str(e))
    
    def _export_duplicate_layer(self):
        """导出重复数据图层"""
        if not self._validation_result:
            from ..widgets.result_dialog import ResultDialog
            ResultDialog.show_warning(self, "无数据", "请先执行验证")
            return
        
        # 筛选重复数据
        duplicate_problems = [p for p in self._all_problems if p.get('type') == 'duplicate']
        if not duplicate_problems:
            from ..widgets.result_dialog import ResultDialog
            ResultDialog.show_warning(self, "无数据", "没有重复数据可导出")
            return
        
        # 选择保存路径
        global_config = self._get_global_config()
        if not global_config:
            return
        
        region_info = global_config.get_region_info()
        base_folder = region_info.get('base_folder', '')
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, "导出重复数据图层", 
            os.path.join(base_folder, "重复数据.shp"),
            "SHP文件 (*.shp)"
        )
        
        if not file_path:
            return
        
        try:
            # 获取自动检测的数据库图层
            db_layer = getattr(self, '_detected_db_layer', None)
            if not db_layer:
                from ..widgets.result_dialog import ResultDialog
                ResultDialog.show_error(self, "配置错误", "未检测到数据库点图层，无法导出")
                return
            
            from qgis.core import QgsVectorFileWriter, QgsFields
            
            # 从问题数据中收集重复数据的匹配标识
            # 使用target_gid（对应数据库的code）和匹配字段值（对应数据库的name）
            duplicate_code_set = set()  # 存储重复的code值
            duplicate_name_set = set()  # 存储重复的name值
            
            for problem in duplicate_problems:
                target_gid = problem.get('target_gid', '').strip()
                match_value = problem.get('match_value', '').strip()
                
                # 如果有target_gid，添加到code集合（用于GID匹配）
                if target_gid and target_gid.lower() != 'nan':
                    duplicate_code_set.add(target_gid.lower())
                
                # 如果有匹配值，添加到name集合（用于字段匹配）
                # match_value是用分号分隔的多个字段值，需要分别添加到集合
                if match_value:
                    # 分割匹配值（用分号分隔）
                    values = [v.strip() for v in match_value.split(';') if v.strip()]
                    for val in values:
                        duplicate_name_set.add(val.lower())
            
            # 创建新图层（复制数据库图层的结构）
            fields = QgsFields(db_layer.fields())
            writer = QgsVectorFileWriter(
                file_path, "UTF-8", fields,
                db_layer.wkbType(), db_layer.crs(), "ESRI Shapefile"
            )
            
            if writer.hasError():
                raise Exception(f"创建图层失败: {writer.errorMessage()}")
            
            # 复制重复数据的要素
            count = 0
            for feature in db_layer.getFeatures():
                matched = False
                
                # 1. 优先用code字段匹配（GID匹配）
                code_val = str(feature.attribute('code') or '').strip()
                if code_val and code_val.lower() in duplicate_code_set:
                    matched = True
                
                # 2. 如果code匹配不到，用name字段匹配（字段匹配）
                if not matched:
                    name_val = str(feature.attribute('name') or '').strip()
                    if name_val and name_val.lower() in duplicate_name_set:
                        matched = True
                
                if matched:
                    writer.addFeature(feature)
                    count += 1
            
            del writer
            
            self._log(f"[Step5] ✅ 重复数据图层已导出: {file_path} ({count}条)", "success")
            
            from ..widgets.result_dialog import ResultDialog
            ResultDialog.show_success(self, "导出成功", f"重复数据图层已导出到:\n{file_path}\n共{count}条记录")
        except Exception as e:
            self._log(f"[Step5] 导出失败: {e}", "error")
            import traceback
            self._log(f"[Step5] 错误详情: {traceback.format_exc()}", "error")
            from ..widgets.result_dialog import ResultDialog
            ResultDialog.show_error(self, "导出失败", str(e))
    
    def _export_stats_report(self):
        """导出统计报告"""
        if not self._validation_result:
            from ..widgets.result_dialog import ResultDialog
            ResultDialog.show_warning(self, "无数据", "请先执行验证")
            return
        
        # 选择保存路径
        global_config = self._get_global_config()
        if not global_config:
            return
        
        region_info = global_config.get_region_info()
        base_folder = region_info.get('base_folder', '')
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, "导出统计报告", 
            os.path.join(base_folder, "验证统计报告.txt"),
            "文本文件 (*.txt);;所有文件 (*.*)"
        )
        
        if not file_path:
            return
        
        try:
            # 生成统计报告文本
            report_text = self._generate_stats_report(self._validation_result)
            
            # 保存文件
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(report_text)
            
            self._log(f"[Step5] ✅ 统计报告已导出: {file_path}", "success")
            
            from ..widgets.result_dialog import ResultDialog
            ResultDialog.show_success(self, "导出成功", f"统计报告已导出到:\n{file_path}")
        except Exception as e:
            self._log(f"[Step5] 导出失败: {e}", "error")
            from ..widgets.result_dialog import ResultDialog
            ResultDialog.show_error(self, "导出失败", str(e))
    
    def _generate_stats_report(self, result: Dict) -> str:
        """生成统计报告文本"""
        report = "=" * 60 + "\n"
        report += "数据治理验证统计报告\n"
        report += "=" * 60 + "\n\n"
        
        # 基本信息
        report += "【基本信息】\n"
        report += f"原始客户数据总数: {result.get('source_total', 0)}\n"
        report += f"匹配结果总数: {result.get('match_total', 0)}\n\n"
        
        # 数据完整性统计
        completeness = result.get('completeness', {})
        match_in_db = completeness.get('match_in_db', {})
        report += "【数据完整性统计】\n"
        report += f"匹配结果在数据库中存在: {match_in_db.get('found', 0)}\n"
        report += f"匹配结果在数据库中缺失: {match_in_db.get('missing', 0)}\n\n"
        
        # 位置偏差统计
        deviation = result.get('deviation', {})
        report += "【位置偏差统计】\n"
        report += f"检查总数: {deviation.get('total_checked', 0)}\n"
        report += f"在阈值内: {deviation.get('within_threshold', 0)}\n"
        report += f"超过阈值: {deviation.get('exceed_threshold', 0)}\n\n"
        
        # 重复数据统计
        duplicate = result.get('duplicate', {})
        report += "【重复数据统计】\n"
        report += f"重复匹配值数: {duplicate.get('duplicate_values', 0)}\n"
        report += f"重复记录数: {duplicate.get('duplicate_records', 0)}\n\n"
        
        # 问题数据列表
        problems = result.get('problems', [])
        if problems:
            report += "【问题数据详情】\n"
            for i, problem in enumerate(problems[:100], 1):  # 最多显示100条
                report += f"{i}. {problem.get('status', '')} - GID: {problem.get('target_gid', '')}\n"
                if problem.get('distance'):
                    report += f"   偏差距离: {problem.get('distance', 0):.2f}米\n"
            if len(problems) > 100:
                report += f"... 还有 {len(problems) - 100} 条问题数据未显示\n"
        
        return report
    
    def _clear_highlight(self):
        """清除高亮"""
        # TODO: 如果实现了高亮功能，在这里清除
        self._log("[Step5] 清除高亮", "info")
    
    # ==================== 步骤0相关方法 ====================
    
    def _load_original_shp_path(self):
        """从根目录下的原始SHP数据目录加载SHP文件夹路径"""
        try:
            global_config = self._get_global_config()
            if not global_config:
                return
            
            region_info = global_config.get_region_info()
            if not region_info.get('province') or not region_info.get('city'):
                return
            
            base_folder = region_info.get('base_folder', '')
            province = region_info.get('province', '')
            city = region_info.get('city', '')
            county = region_info.get('county', '')
            
            # 优先使用根目录下的原始SHP数据目录：{省}{市}原始SHP数据
            saved_shp_path = ""
            if base_folder and province and city:
                region_prefix = f"{province}{city}{county}".strip()
                original_shp_folder = os.path.join(base_folder, f"{region_prefix}原始SHP数据")
                if os.path.exists(original_shp_folder):
                    saved_shp_path = original_shp_folder
                    self._log(f"[Step5] 从根目录加载原始SHP数据目录: {saved_shp_path}", "info")
            
            # 如果根目录下没有，尝试从QSettings读取（兼容旧数据）
            if not saved_shp_path:
                try:
                    from qgis.PyQt.QtCore import QSettings
                    region_key = f"{province}|{city}|{county}"
                    settings = QSettings("fz_adr_match_dev", "step1_config")
                    saved_shp_path = settings.value(f"shp_paths/{region_key}", "")
                    
                    # 如果保存的是文件路径，取目录
                    if saved_shp_path and os.path.isfile(saved_shp_path):
                        saved_shp_path = os.path.dirname(saved_shp_path)
                except Exception as e:
                    self._log(f"[Step5] 从QSettings读取路径失败: {e}", "warning")
            
            # 如果还是没有，从全局配置的shp_folder获取（兼容旧数据）
            if not saved_shp_path:
                saved_shp_path = region_info.get('shp_folder', '')
                self._log(f"[Step5] 从全局配置获取shp_folder: {saved_shp_path}", "info")
            
            # 显示路径（即使路径不存在也显示，让用户知道）
            if saved_shp_path:
                self.original_shp_folder_display.setText(saved_shp_path)
                if os.path.exists(saved_shp_path):
                    self._log(f"[Step5] 已加载SHP文件夹路径: {saved_shp_path}", "info")
                    # 自动刷新文件列表
                    from qgis.PyQt.QtCore import QTimer
                    QTimer.singleShot(200, self._refresh_original_shp_files)
                else:
                    self._log(f"[Step5] SHP文件夹路径不存在，但仍显示: {saved_shp_path}", "warning")
            else:
                self._log(f"[Step5] 未找到SHP文件夹路径，请手动选择", "warning")
        except Exception as e:
            self._log(f"[Step5] 加载SHP路径失败: {e}", "error")
    
    def _browse_original_shp_folder(self):
        """浏览选择原始SHP文件夹"""
        current_folder = self.original_shp_folder_display.text().strip()
        if not current_folder:
            # 尝试从全局配置获取
            global_config = self._get_global_config()
            if global_config:
                region_info = global_config.get_region_info()
                current_folder = region_info.get('shp_folder', '')
        
        folder = QFileDialog.getExistingDirectory(self, "选择SHP文件夹", current_folder)
        if folder:
            self.original_shp_folder_display.setText(folder)
            self._log(f"[Step5] 选择SHP文件夹: {folder}", "info")
            # 自动刷新文件列表
            self._refresh_original_shp_files()
    
    def _refresh_original_shp_files(self):
        """刷新原始SHP文件列表"""
        self._log("[Step5] 刷新原始SHP文件列表", "info")
        
        # 获取选中的文件夹
        shp_folder = self.original_shp_folder_display.text().strip()
        
        if not shp_folder:
            # 尝试从全局配置获取
            global_config = self._get_global_config()
            if global_config:
                region_info = global_config.get_region_info()
                shp_folder = region_info.get('shp_folder', '')
                if shp_folder:
                    self.original_shp_folder_display.setText(shp_folder)
        
        if not shp_folder or not os.path.exists(shp_folder):
            self._log("[Step5] 请先选择有效的SHP文件夹", "warning")
            self._update_original_shp_files_table()
            return
        
        # 扫描SHP文件
        self._original_shp_files = {}
        
        try:
            for f in os.listdir(shp_folder):
                if f.lower().endswith('.shp'):
                    shp_path = os.path.join(shp_folder, f)
                    try:
                        file_size = os.path.getsize(shp_path)
                        size_mb = file_size / (1024 * 1024)
                        
                        # 检查是否已加载到QGIS
                        status = "未加载"
                        layer_name = os.path.splitext(f)[0]
                        if self._is_layer_loaded(layer_name):
                            status = "已加载"
                        
                        self._original_shp_files[shp_path] = {
                            'file_name': f,
                            'size': size_mb,
                            'status': status,
                            'layer_name': layer_name
                        }
                    except Exception as e:
                        self._log(f"[Step5] 读取文件信息失败: {f}, {e}", "error")
        except Exception as e:
            self._log(f"[Step5] 扫描文件夹失败: {e}", "error")
        
        self._update_original_shp_files_table()
        self._log(f"[Step5] 找到 {len(self._original_shp_files)} 个SHP文件", "info")
    
    def _update_original_shp_files_table(self):
        """更新原始SHP文件列表表格"""
        self.original_shp_files_table.setRowCount(len(self._original_shp_files))
        
        for row, (shp_path, info) in enumerate(self._original_shp_files.items()):
            # 复选框列
            chk = QCheckBox()
            chk.setChecked(False)
            self.original_shp_files_table.setCellWidget(row, 0, chk)
            
            # 文件名
            self.original_shp_files_table.setItem(row, 1, QTableWidgetItem(info['file_name']))
            
            # 大小
            size_text = f"{info['size']:.2f} MB" if info['size'] >= 1.0 else f"{info['size'] * 1024:.2f} KB"
            self.original_shp_files_table.setItem(row, 2, QTableWidgetItem(size_text))
            
            # 状态
            status_item = QTableWidgetItem(info['status'])
            if info['status'] == "已加载":
                status_item.setForeground(QColor(0, 128, 0))  # 绿色
            else:
                status_item.setForeground(QColor(128, 128, 128))  # 灰色
            self.original_shp_files_table.setItem(row, 3, status_item)
    
    def _select_all_original_shp_files(self):
        """全选原始SHP文件"""
        for row in range(self.original_shp_files_table.rowCount()):
            chk = self.original_shp_files_table.cellWidget(row, 0)
            if chk:
                chk.setChecked(True)
    
    def _select_none_original_shp_files(self):
        """取消全选原始SHP文件"""
        for row in range(self.original_shp_files_table.rowCount()):
            chk = self.original_shp_files_table.cellWidget(row, 0)
            if chk:
                chk.setChecked(False)
    
    def _load_original_shp_to_qgis(self):
        """加载选中的原始SHP文件到QGIS"""
        selected_files = []
        for row in range(self.original_shp_files_table.rowCount()):
            chk = self.original_shp_files_table.cellWidget(row, 0)
            if chk and chk.isChecked():
                file_name = self.original_shp_files_table.item(row, 1).text()
                # 找到对应的文件路径
                for shp_path, info in self._original_shp_files.items():
                    if info['file_name'] == file_name:
                        selected_files.append(shp_path)
                        break
        
        if not selected_files:
            self._log("[Step5] 请先选择要加载的SHP文件", "warn")
            return
        
        self._log(f"[Step5] 开始加载 {len(selected_files)} 个SHP文件到QGIS", "info")
        self.original_shp_load_progress.setVisible(True)
        self.original_shp_load_progress.setMaximum(len(selected_files))
        self.original_shp_load_progress.setValue(0)
        
        # 加载文件（使用QGIS API）
        try:
            from qgis.core import QgsVectorLayer, QgsProject
            
            success_count = 0
            fail_count = 0
            
            for idx, shp_path in enumerate(selected_files):
                try:
                    file_name = os.path.basename(shp_path)
                    layer_name = os.path.splitext(file_name)[0]
                    
                    # 创建图层
                    layer = QgsVectorLayer(shp_path, layer_name, "ogr")
                    if not layer.isValid():
                        self._log(f"[Step5] 加载失败: {file_name} - {layer.error().message()}", "error")
                        fail_count += 1
                        self._original_shp_files[shp_path]['status'] = "加载失败"
                        continue
                    
                    # 添加到项目
                    QgsProject.instance().addMapLayer(layer)
                    
                    # 保存图层引用
                    self._loaded_layers[shp_path] = layer
                    self._original_shp_files[shp_path]['status'] = "已加载"
                    
                    success_count += 1
                    self._log(f"[Step5] 加载成功: {file_name}", "success")
                except Exception as e:
                    fail_count += 1
                    self._original_shp_files[shp_path]['status'] = "加载失败"
                    self._log(f"[Step5] 加载失败: {os.path.basename(shp_path)} - {e}", "error")
                
                self.original_shp_load_progress.setValue(idx + 1)
            
            # 更新表格状态
            self._update_original_shp_files_table()
            
            # 刷新图层下拉框
            self._refresh_layer_combos()
            
            self._log(f"[Step5] 加载完成: 成功 {success_count}/{len(selected_files)}", "info" if success_count == len(selected_files) else "warning")
            
        except Exception as e:
            self._log(f"[Step5] 加载过程出错: {e}", "error")
        finally:
            self.original_shp_load_progress.setVisible(False)
    
    def _get_global_config(self):
        """获取全局配置组件"""
        if self.global_config:
            return self.global_config
        parent = self.parent()
        while parent:
            if hasattr(parent, 'global_config'):
                return parent.global_config
            parent = parent.parent()
        return None
    
    def _adjust_table_columns(self):
        """调整表格列宽"""
        try:
            from ..utils import auto_resize_table_columns
            auto_resize_table_columns(self.problem_table, min_col_width=80, max_col_width=400)
        except Exception as e:
            self._log(f"[Step5] 调整表格列宽失败: {e}", "warning")
    
    def _display_problems_batch(self, problems: List[Dict], start_row: int, update_enabled: bool = False):
        """分批显示问题数据到表格"""
        from qgis.PyQt.QtWidgets import QApplication
        
        if not update_enabled:
            self.problem_table.setUpdatesEnabled(False)
            self.problem_table.setSortingEnabled(False)
        
        try:
            # 确保表格有足够的行数
            current_rows = self.problem_table.rowCount()
            needed_rows = start_row + len(problems)
            if needed_rows > current_rows:
                self.problem_table.setRowCount(needed_rows)
            
            # 填充数据
            for idx, problem in enumerate(problems):
                row = start_row + idx
                
                # 目标表GID
                target_gid = problem.get('target_gid', '')
                self.problem_table.setItem(row, 0, QTableWidgetItem(target_gid))
                
                # 数据库code
                db_code = problem.get('db_code', '') or '-'
                self.problem_table.setItem(row, 1, QTableWidgetItem(db_code))
                
                # 源表匹配值
                self.problem_table.setItem(row, 2, QTableWidgetItem(problem.get('match_value', '')))
                
                # 状态
                status = problem.get('status', '')
                status_item = QTableWidgetItem(status)
                if '缺失' in status:
                    status_item.setForeground(QColor(220, 53, 69))
                elif '位置偏差' in status:
                    status_item.setForeground(QColor(255, 193, 7))
                elif '重复' in status:
                    status_item.setForeground(QColor(255, 152, 0))
                self.problem_table.setItem(row, 3, status_item)
                
                # 偏差距离
                deviation = problem.get('deviation')
                distance_text = f"{deviation:.2f}米" if deviation is not None else "-"
                self.problem_table.setItem(row, 4, QTableWidgetItem(distance_text))
                
                # 原始坐标
                shp_coord = problem.get('shp_coord')
                try:
                    coord_text = f"({shp_coord[0]:.6f}, {shp_coord[1]:.6f})" if shp_coord and len(shp_coord) >= 2 else "-"
                except (TypeError, IndexError):
                    coord_text = "-"
                self.problem_table.setItem(row, 5, QTableWidgetItem(coord_text))
                
                # 数据库坐标
                db_coord = problem.get('db_coord')
                try:
                    coord_text = f"({db_coord[0]:.6f}, {db_coord[1]:.6f})" if db_coord and len(db_coord) >= 2 else "-"
                except (TypeError, IndexError):
                    coord_text = "-"
                self.problem_table.setItem(row, 6, QTableWidgetItem(coord_text))
                
                # 每50行处理一次事件
                if idx > 0 and idx % 50 == 0:
                    QApplication.processEvents()
            
            if not update_enabled:
                self.problem_table.setUpdatesEnabled(True)
                self.problem_table.setSortingEnabled(True)
        except Exception as e:
            if not update_enabled:
                self.problem_table.setUpdatesEnabled(True)
            self._log(f"[Step5] 分批显示问题数据失败: {e}", "error")
            raise
    
    def _display_problems_batch_async(self, remaining_problems: List[Dict], start_row: int):
        """异步分批显示剩余的问题数据"""
        from qgis.PyQt.QtWidgets import QApplication
        from qgis.PyQt.QtCore import QTimer
        
        if not remaining_problems:
            return
        
        # 每次处理100条
        batch_size = 100
        batch = remaining_problems[:batch_size]
        remaining = remaining_problems[batch_size:]
        
        # 显示当前批次
        self._display_problems_batch(batch, start_row, update_enabled=True)
        QApplication.processEvents()
        
        # 如果还有剩余，继续异步加载
        if remaining:
            QTimer.singleShot(50, lambda: self._display_problems_batch_async(remaining, start_row + len(batch)))
        else:
            # 所有数据加载完成，调整列宽
            QTimer.singleShot(100, self._adjust_table_columns)
            self._log(f"[Step5] 所有问题数据已异步加载完成", "info")
