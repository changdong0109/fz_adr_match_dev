"""
Step1: 文件导入Widget
包含：数据源列表、SHP转换辅助
（全局范围配置已移到主对话框）
"""
import os
from typing import Callable, Optional, Dict
from pathlib import Path
from qgis.PyQt.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel, QLineEdit,
    QPushButton, QComboBox, QTableWidget, QTableWidgetItem, QCheckBox,
    QProgressBar, QFileDialog, QAbstractItemView
)
from qgis.PyQt.QtGui import QColor, QWheelEvent
from qgis.PyQt.QtCore import Qt, QThread, pyqtSignal, QSettings
from ..utils import safe_select_rows, set_resize_mode
from ..widgets.base_step_widget import BaseStepWidget
# 导入core层（使用相对导入，向上三级到插件根目录）
from ...core.data_loader import DataLoader


class NoWheelComboBox(QComboBox):
    """禁用滚轮的下拉框"""
    def wheelEvent(self, event: QWheelEvent):
        """忽略滚轮事件，防止意外修改"""
        event.ignore()


class ShpConvertThread(QThread):
    """SHP转换后台线程"""
    progress_updated = pyqtSignal(int, int, str)  # current, total, filename
    file_converted = pyqtSignal(str, str, str)  # shp_file, output_file, status
    finished = pyqtSignal(int, int)  # success_count, fail_count
    
    def __init__(self, shp_files, shp_folder):
        super().__init__()
        self.shp_files = shp_files
        self.shp_folder = shp_folder
    
    def run(self):
        """执行转换任务"""
        total = len(self.shp_files)
        success_count = 0
        fail_count = 0
        
        for idx, shp_file in enumerate(self.shp_files):
            try:
                # 发送进度更新信号
                self.progress_updated.emit(idx + 1, total, os.path.basename(shp_file))
                
                # 转换文件
                file_stem = Path(shp_file).stem
                output_file_name = f"{file_stem}.csv"
                output_path = os.path.join(self.shp_folder, output_file_name)
                
                # 如果文件已存在，添加序号
                counter = 1
                while os.path.exists(output_path):
                    output_file_name = f"{file_stem}_{counter}.csv"
                    output_path = os.path.join(self.shp_folder, output_file_name)
                    counter += 1
                
                DataLoader.convert_to_csv(shp_file, output_path)
                success_count += 1
                
                # 发送文件转换完成信号
                self.file_converted.emit(shp_file, output_file_name, "success")
                
            except Exception as e:
                fail_count += 1
                # 发送文件转换失败信号
                self.file_converted.emit(shp_file, "", f"失败: {e}")
        
        # 发送完成信号
        self.finished.emit(success_count, fail_count)


class Step1Widget(BaseStepWidget):
    """Step1: 文件导入"""
    
    def __init__(self, parent=None, log_callback: Optional[Callable[[str, str], None]] = None, 
                 task_manager=None):
        super().__init__(parent, log_callback, task_manager)
        # 存储数据源信息：{file_name: {source_path, saved_path, source_type, cleaned}}
        self.data_sources: Dict[str, Dict] = {}
        # 临时存储选择的SHP文件列表
        self._selected_shp_files = []
        # 转换线程
        self._convert_thread = None
        self._build_ui()
        # 设置尺寸策略，让Step1Widget能够扩展填满可用空间
        self._set_expanding_size_policy()
        # 延迟设置区域监听器（确保全局配置已创建）
        from qgis.PyQt.QtCore import QTimer
        QTimer.singleShot(300, self._setup_region_listener)
        # 延迟刷新数据源列表（确保全局配置已初始化）
        QTimer.singleShot(500, self._on_refresh)
    
    def _build_ui(self):
        """构建UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 16, 0, 16)  # 移除左右边距，由父容器统一控制
        layout.setSpacing(16)  # GroupBox之间的间距
        
        # 全局配置已移到主对话框，这里不再显示
        layout.addWidget(self._card_data_sources())
        layout.addWidget(self._card_shp_helper())
        # 移除addStretch，让内容充分利用空间
    
    def _set_expanding_size_policy(self):
        """设置Step1Widget的尺寸策略为Expanding"""
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
    
    def _card_data_sources(self) -> QGroupBox:
        """数据源文件列表"""
        box = QGroupBox("数据源文件列表")
        # 设置尺寸策略，让GroupBox能够水平扩展
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
        
        v = QVBoxLayout(box)
        v.setContentsMargins(16, 20, 16, 16)
        v.setSpacing(12)
        
        # 按钮行
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        btn_add = QPushButton("添加文件")
        btn_add.setObjectName("step1_btn_add")
        btn_del = QPushButton("移除选中")
        btn_del.setObjectName("step1_btn_del")
        btn_ref = QPushButton("刷新")
        btn_ref.setObjectName("step1_btn_refresh")
        btn_row.addWidget(btn_add)
        btn_row.addWidget(btn_del)
        btn_row.addWidget(btn_ref)
        btn_row.addStretch()
        v.addLayout(btn_row)
        
        # 表格：选择、文件名、来源类型、清洗状态（移除参与任务和字段组合数）
        self.data_sources_table = QTableWidget(0, 4)
        self.data_sources_table.setHorizontalHeaderLabels(["选择", "文件名", "来源类型", "清洗状态"])
        self.data_sources_table.setMinimumHeight(200)
        safe_select_rows(self.data_sources_table)
        from ..utils import safe_no_edit
        safe_no_edit(self.data_sources_table)
        header = self.data_sources_table.horizontalHeader()
        # 选择列：固定宽度，左对齐
        set_resize_mode(header, 0, prefer_contents=True)
        header.resizeSection(0, 60)
        # 文件名列：自动扩展
        set_resize_mode(header, 1, prefer_contents=False)
        # 来源类型列：固定宽度，确保下拉框能显示
        set_resize_mode(header, 2, prefer_contents=False)
        header.resizeSection(2, 150)
        # 清洗状态列：固定宽度
        set_resize_mode(header, 3, prefer_contents=True)
        header.resizeSection(3, 100)
        
        # 表格样式通过 QSS 文件统一管理（使用 objectName）
        self.data_sources_table.setObjectName("step1_data_sources_table")
        v.addWidget(self.data_sources_table)
        
        btn_add.clicked.connect(self._on_add_files)
        btn_del.clicked.connect(self._on_remove_selected)
        btn_ref.clicked.connect(self._on_refresh)
        
        return box
    
    def add_data_source(self, file_name: str, source_type: str = "其他", cleaned: str = "未清洗"):
        """添加数据源到表格"""
        row = self.data_sources_table.rowCount()
        self.data_sources_table.insertRow(row)
        
        # 选择复选框（左对齐，默认不选中）
        chk = QCheckBox()
        chk.setChecked(False)
        self.data_sources_table.setCellWidget(row, 0, chk)
        
        # 文件名
        self.data_sources_table.setItem(row, 1, QTableWidgetItem(file_name))
        
        # 来源类型下拉框（确保能显示完整内容，禁用滚轮修改）
        type_combo = NoWheelComboBox()
        type_combo.addItems(["客户采集数据", "GIS 数据", "其他"])
        type_combo.setEditable(False)
        type_combo.setMinimumWidth(140)
        if source_type in ["客户采集数据", "GIS 数据", "其他"]:
            type_combo.setCurrentText(source_type)
        else:
            type_combo.setCurrentText("其他")
        self.data_sources_table.setCellWidget(row, 2, type_combo)
        
        # 清洗状态
        status_item = QTableWidgetItem(cleaned)
        if cleaned == "已清洗":
            status_item.setForeground(QColor("#15803d"))
        self.data_sources_table.setItem(row, 3, status_item)
    
    def _card_shp_helper(self) -> QGroupBox:
        """SHP转换辅助"""
        box = QGroupBox("辅助：shp → Excel 转换")
        # 设置尺寸策略，让GroupBox能够水平扩展
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
        
        v = QVBoxLayout(box)
        v.setContentsMargins(16, 20, 16, 16)
        v.setSpacing(12)
        
        # 文件选择行
        row = QHBoxLayout()
        row.setSpacing(8)
        row.addWidget(QLabel("选择 shp 文件或文件夹："))
        self.edit_shp_src = QLineEdit("")
        self.edit_shp_src.setMinimumWidth(300)
        row.addWidget(self.edit_shp_src)
        
        # 提供两个按钮：选择文件夹和选择文件
        btn_browse_folder = QPushButton("选择文件夹")
        btn_browse_folder.setObjectName("step1_btn_browse_folder")
        btn_browse_folder.clicked.connect(self._on_browse_shp_folder)
        row.addWidget(btn_browse_folder)
        
        btn_browse_file = QPushButton("选择文件")
        btn_browse_file.setObjectName("step1_btn_browse_file")
        btn_browse_file.clicked.connect(self._on_browse_shp_file)
        row.addWidget(btn_browse_file)
        
        row.addStretch()
        v.addLayout(row)
        
        # 加载保存的shp路径（延迟加载，确保全局配置已初始化）
        from qgis.PyQt.QtCore import QTimer
        QTimer.singleShot(100, self._load_shp_path)
        
        # 自动添加选项
        self.chk_auto_add = QCheckBox("转换完成后自动加入上方数据源列表")
        self.chk_auto_add.setChecked(True)
        v.addWidget(self.chk_auto_add)
        
        # 进度和控制按钮
        rowp = QHBoxLayout()
        rowp.setSpacing(8)
        self.bar_shp = QProgressBar()
        self.bar_shp.setValue(0)
        self.bar_shp.setMinimumHeight(24)
        rowp.addWidget(self.bar_shp)
        self.lbl_shp = QLabel("空闲")
        self.lbl_shp.setMinimumWidth(60)
        self.lbl_shp.setObjectName("step1_shp_status_label")
        rowp.addWidget(self.lbl_shp)
        btn_run = QPushButton("执行")
        btn_run.setObjectName("step1_btn_run")
        rowp.addWidget(btn_run)
        rowp.addStretch()
        v.addLayout(rowp)
        
        # 连接按钮到实际的转换方法
        btn_run.clicked.connect(self._on_convert_shp_batch)
        
        return box
    
    def _get_qsettings(self):
        """获取QSettings实例"""
        return QSettings("fz_adr_match_dev", "step1_config")
    
    def _save_shp_path(self):
        """保存SHP文件路径到QSettings"""
        shp_path = self.edit_shp_src.text().strip()
        if not shp_path:
            return
        
        try:
            global_config = self._get_global_config()
            if not global_config:
                return
            
            region_info = global_config.get_region_info()
            region_key = f"{region_info.get('province', '')}|{region_info.get('city', '')}|{region_info.get('county', '')}"
            
            settings = self._get_qsettings()
            settings.setValue(f"shp_paths/{region_key}", shp_path)
            settings.sync()
        except Exception as e:
            self._log(f"[Step1] 保存SHP路径失败：{e}", "error")
    
    def _load_shp_path(self):
        """从QSettings加载SHP文件路径"""
        try:
            global_config = self._get_global_config()
            if not global_config:
                return
            
            region_info = global_config.get_region_info()
            if not region_info.get('province') or not region_info.get('city'):
                return
            
            region_key = f"{region_info.get('province', '')}|{region_info.get('city', '')}|{region_info.get('county', '')}"
            
            settings = self._get_qsettings()
            saved_path = settings.value(f"shp_paths/{region_key}", "")
            
            if saved_path:
                # 检查路径是否存在，如果不存在但目录存在，也显示（可能是文件被删除了）
                if os.path.exists(saved_path) or (os.path.isdir(os.path.dirname(saved_path)) if os.path.dirname(saved_path) else False):
                    self.edit_shp_src.setText(saved_path)
                else:
                    # 路径不存在，清空
                    self.edit_shp_src.setText("")
        except Exception as e:
            # 静默失败，不影响主流程
            pass
    
    def _setup_region_listener(self):
        """设置区域变化监听器"""
        try:
            global_config = self._get_global_config()
            if global_config:
                # 监听区域变化信号
                global_config.region_changed.connect(self._on_region_changed)
        except Exception as e:
            # 静默失败
            pass
    
    def _on_region_changed(self):
        """区域变化时的回调，重新加载shp路径"""
        # 延迟加载，确保全局配置已更新
        from qgis.PyQt.QtCore import QTimer
        QTimer.singleShot(200, self._load_shp_path)
    
    def _get_global_config(self):
        """获取全局配置组件（通过parent查找MatchDialog）"""
        parent = self.parent()
        while parent:
            if hasattr(parent, 'global_config'):
                return parent.global_config
            parent = parent.parent()
        return None
    
    def _get_target_folder(self, file_path: str) -> Optional[str]:
        """
        根据文件类型获取目标文件夹
        
        Args:
            file_path: 源文件路径
            
        Returns:
            目标文件夹路径，如果全局配置未设置则返回None
        """
        global_config = self._get_global_config()
        if not global_config:
            return None
        
        region_info = global_config.get_region_info()
        if not region_info.get('base_folder'):
            return None
        
        ext = Path(file_path).suffix.lower()
        if ext in ['.xlsx', '.xls', '.csv']:
            # Excel/CSV 文件保存到客户数据目录
            return region_info.get('customer_folder', '')
        elif ext == '.shp':
            # SHP 文件保存到 shp 数据目录
            return region_info.get('shp_folder', '')
        else:
            # 其他文件保存到客户数据目录
            return region_info.get('customer_folder', '')
    
    def _on_add_files(self):
        """添加文件"""
        # 检查全局配置
        global_config = self._get_global_config()
        if not global_config:
            self._log("[Step1] 错误：无法获取全局配置", "error")
            return
        
        region_info = global_config.get_region_info()
        if not region_info.get('base_folder'):
            self._log("[Step1] 请先配置全局目录（省/市/根目录）", "warn")
            return
        
        # 打开文件选择对话框（支持多选）
        file_paths, _ = QFileDialog.getOpenFileNames(
            self,
            "选择要导入的文件（Excel/SHP/CSV）",
            "",
            "所有支持格式 (*.xlsx *.xls *.csv *.shp);;Excel文件 (*.xlsx *.xls);;CSV文件 (*.csv);;SHP文件 (*.shp)"
        )
        
        if not file_paths:
            return
        
        # 批量处理文件
        success_count = 0
        fail_count = 0
        
        for file_path in file_paths:
            try:
                self._import_file(file_path)
                success_count += 1
            except Exception as e:
                self._log(f"[Step1] 导入失败 {os.path.basename(file_path)}: {e}", "error")
                fail_count += 1
        
        if success_count > 0:
            self._log(f"[Step1] 成功导入 {success_count} 个文件", "success")
        if fail_count > 0:
            self._log(f"[Step1] 失败 {fail_count} 个文件", "warn")
    
    def _import_file(self, source_path: str):
        """
        导入单个文件：加载、转换、保存
        
        Args:
            source_path: 源文件路径
        """
        source_path = os.path.abspath(source_path)
        file_name = os.path.basename(source_path)
        file_stem = Path(file_name).stem
        
        # 获取目标文件夹
        target_folder = self._get_target_folder(source_path)
        if not target_folder:
            raise ValueError("无法获取目标文件夹，请检查全局配置")
        
        # 确保目标文件夹存在
        os.makedirs(target_folder, exist_ok=True)
        
        # 生成输出文件名（转换为CSV）
        output_file_name = f"{file_stem}.csv"
        output_path = os.path.join(target_folder, output_file_name)
        
        # 如果文件已存在，添加序号
        counter = 1
        while os.path.exists(output_path):
            output_file_name = f"{file_stem}_{counter}.csv"
            output_path = os.path.join(target_folder, output_file_name)
            counter += 1
        
        # 转换文件
        self._log(f"[Step1] 正在转换：{file_name} → {output_file_name}", "info")
        DataLoader.convert_to_csv(source_path, output_path)
        
        # 判断来源类型
        ext = Path(source_path).suffix.lower()
        if ext == '.shp':
            source_type = "GIS 数据"
        elif ext in ['.xlsx', '.xls']:
            source_type = "客户采集数据"
        else:
            source_type = "其他"
        
        # 保存数据源信息
        self.data_sources[output_file_name] = {
            'source_path': source_path,
            'saved_path': output_path,
            'source_type': source_type,
            'cleaned': '未清洗'
        }
        
        # 添加到表格
        self.add_data_source(output_file_name, source_type, '未清洗')
        
        self._log(f"[Step1] 已保存到：{output_path}", "success")
    
    def _on_remove_selected(self):
        """移除选中的文件（从文件夹中删除文件）"""
        selected_rows = []
        for i in range(self.data_sources_table.rowCount()):
            chk = self.data_sources_table.cellWidget(i, 0)
            if chk and chk.isChecked():
                selected_rows.append(i)
        
        if not selected_rows:
            self._log("[Step1] 请先选择要移除的文件", "warn")
            return
        
        # 确认删除
        from qgis.PyQt.QtWidgets import QMessageBox
        # 使用 StandardButton 枚举（兼容不同 PyQt 版本）
        try:
            # PyQt5/PyQt6 标准方式
            YesButton = QMessageBox.StandardButton.Yes
            NoButton = QMessageBox.StandardButton.No
        except AttributeError:
            # 兼容旧版本，使用常量值
            YesButton = 0x00004000  # QMessageBox.Yes
            NoButton = 0x00010000  # QMessageBox.No
        
        reply = QMessageBox.question(
            self,
            "确认删除",
            f"确定要删除选中的 {len(selected_rows)} 个文件吗？\n文件将从对应文件夹中永久删除。",
            YesButton | NoButton,
            NoButton
        )
        if reply != YesButton:
            return
        
        # 统计删除结果
        success_count = 0
        fail_count = 0
        
        # 从后往前删除，避免索引变化
        for row in sorted(selected_rows, reverse=True):
            file_name_item = self.data_sources_table.item(row, 1)
            if file_name_item:
                file_name = file_name_item.text()
                
                # 获取文件路径并删除文件
                if file_name in self.data_sources:
                    file_info = self.data_sources[file_name]
                    saved_path = file_info.get('saved_path', '')
                    
                    # 删除文件
                    if saved_path and os.path.exists(saved_path):
                        try:
                            os.remove(saved_path)
                            success_count += 1
                            self._log(f"[Step1] 已删除文件：{file_name}", "info")
                        except Exception as e:
                            fail_count += 1
                            self._log(f"[Step1] 删除文件失败 {file_name}：{e}", "error")
                    elif saved_path:
                        # 文件不存在，但路径存在，记录警告
                        fail_count += 1
                        self._log(f"[Step1] 文件不存在：{saved_path}", "warn")
                    else:
                        # 没有保存路径，只从列表中移除
                        success_count += 1
                        self._log(f"[Step1] 已移除（无文件路径）：{file_name}", "info")
                    
                    # 从数据源字典中移除
                    del self.data_sources[file_name]
                
                # 从表格中移除
                self.data_sources_table.removeRow(row)
        
        # 汇总日志
        if success_count > 0 and fail_count == 0:
            self._log(f"[Step1] 已成功移除 {success_count} 个文件", "success")
        elif success_count > 0 and fail_count > 0:
            self._log(f"[Step1] 移除完成：成功 {success_count} 个，失败 {fail_count} 个", "warn")
        else:
            self._log(f"[Step1] 移除失败：{fail_count} 个文件", "error")
    
    def _on_refresh(self):
        """刷新表格（重新加载已保存的文件）"""
        # 获取全局配置
        global_config = self._get_global_config()
        if not global_config:
            return
        
        region_info = global_config.get_region_info()
        customer_folder = region_info.get('customer_folder', '')
        shp_folder = region_info.get('shp_folder', '')
        
        # 清空表格和数据源
        self.data_sources_table.setRowCount(0)
        self.data_sources.clear()
        
        # 扫描文件夹，加载已保存的CSV文件
        folders_to_scan = []
        if customer_folder and os.path.isdir(customer_folder):
            folders_to_scan.append(('customer', customer_folder))
        if shp_folder and os.path.isdir(shp_folder):
            folders_to_scan.append(('shp', shp_folder))
        
        for folder_type, folder_path in folders_to_scan:
            try:
                for file_name in os.listdir(folder_path):
                    if file_name.lower().endswith('.csv'):
                        file_path = os.path.join(folder_path, file_name)
                        source_type = "GIS 数据" if folder_type == 'shp' else "客户采集数据"
                        
                        self.data_sources[file_name] = {
                            'source_path': '',  # 原始路径未知
                            'saved_path': file_path,
                            'source_type': source_type,
                            'cleaned': '未清洗'
                        }
                        self.add_data_source(file_name, source_type, '未清洗')
            except Exception as e:
                self._log(f"[Step1] 扫描文件夹失败 {folder_path}: {e}", "error")
        
        self._log(f"[Step1] 已刷新，找到 {len(self.data_sources)} 个文件", "info")
    
    def _get_initial_path(self):
        """获取初始路径（用于文件/文件夹选择对话框）"""
        initial_path = self.edit_shp_src.text().strip()
        if not initial_path or not os.path.exists(initial_path):
            return ""
        elif os.path.isfile(initial_path):
            return os.path.dirname(initial_path)
        elif os.path.isdir(initial_path):
            return initial_path
        return ""
    
    def _on_browse_shp_folder(self):
        """选择SHP文件所在文件夹"""
        initial_path = self._get_initial_path()
        
        folder_path = QFileDialog.getExistingDirectory(
            self,
            "选择 shp 文件所在文件夹",
            initial_path
        )
        
        if folder_path:
            self.edit_shp_src.setText(folder_path)
            self._log(f"[Step1] 选择SHP文件夹：{folder_path}", "info")
            self._save_shp_path()
            # 清空临时文件列表，使用文件夹路径
            self._selected_shp_files = []
    
    def _on_browse_shp_file(self):
        """选择SHP文件（支持多选）"""
        initial_path = self._get_initial_path()
        
        file_paths, _ = QFileDialog.getOpenFileNames(
            self,
            "选择 shp 文件（可多选）",
            initial_path,
            "SHP文件 (*.shp);;所有文件 (*.*)"
        )
        
        if file_paths:
            # 如果只选择了一个文件，直接显示该文件路径
            if len(file_paths) == 1:
                self.edit_shp_src.setText(file_paths[0])
                self._log(f"[Step1] 选择SHP文件：{os.path.basename(file_paths[0])}", "info")
            else:
                # 多个文件，显示第一个文件的目录路径
                first_dir = os.path.dirname(file_paths[0])
                self.edit_shp_src.setText(first_dir)
                self._log(f"[Step1] 选择 {len(file_paths)} 个SHP文件，目录：{first_dir}", "info")
            
            # 保存选择的路径
            self._save_shp_path()
            
            # 保存到临时文件列表，供转换使用（点击执行按钮时才使用）
            self._selected_shp_files = file_paths
    
    def _on_convert_shp_batch(self):
        """批量转换SHP文件"""
        # 检查全局配置
        global_config = self._get_global_config()
        if not global_config:
            self._log("[Step1] 错误：无法获取全局配置", "error")
            return
        
        region_info = global_config.get_region_info()
        if not region_info.get('base_folder'):
            self._log("[Step1] 请先配置全局目录（省/市/根目录）", "warn")
            return
        
        # 优先使用已选择的文件列表（从文件选择对话框）
        shp_files = []
        if hasattr(self, '_selected_shp_files') and self._selected_shp_files:
            shp_files = self._selected_shp_files
            # 清空临时列表
            self._selected_shp_files = []
        else:
            # 如果没有临时列表，从输入框获取路径
            shp_path = self.edit_shp_src.text().strip()
            if not shp_path or not os.path.exists(shp_path):
                self._log("[Step1] 请先选择有效的SHP文件", "warn")
                return
            
            # 如果是文件，直接使用
            if os.path.isfile(shp_path) and shp_path.lower().endswith('.shp'):
                shp_files.append(shp_path)
            elif os.path.isdir(shp_path):
                # 如果是目录，扫描所有.shp文件
                for root, dirs, files in os.walk(shp_path):
                    for file in files:
                        if file.lower().endswith('.shp'):
                            shp_files.append(os.path.join(root, file))
        
        if not shp_files:
            self._log("[Step1] 未找到SHP文件", "warn")
            return
        
        # 获取目标文件夹
        shp_folder = region_info.get('shp_folder', '')
        if not shp_folder:
            self._log("[Step1] 无法获取SHP数据目录", "error")
            return
        
        os.makedirs(shp_folder, exist_ok=True)
        
        # 检查是否已有转换任务在运行
        if self._convert_thread and self._convert_thread.isRunning():
            self._log("[Step1] 转换任务正在运行中，请等待完成", "warn")
            return
        
        # 创建后台线程执行转换
        self._convert_thread = ShpConvertThread(shp_files, shp_folder)
        
        # 连接信号
        self._convert_thread.progress_updated.connect(self._on_convert_progress)
        self._convert_thread.file_converted.connect(self._on_file_converted)
        self._convert_thread.finished.connect(self._on_convert_finished)
        
        # 初始化进度
        total = len(shp_files)
        self.bar_shp.setValue(0)
        self.lbl_shp.setText(f"批量 shp→CSV... 0/{total}")
        
        # 启动线程
        self._convert_thread.start()
        self._log(f"[Step1] 开始转换 {total} 个SHP文件", "info")
    
    def _on_convert_progress(self, current: int, total: int, filename: str):
        """转换进度更新回调"""
        progress = int((current / total) * 100)
        self.bar_shp.setValue(progress)
        self.lbl_shp.setText(f"批量 shp→CSV... {current}/{total}: {filename}")
    
    def _on_file_converted(self, shp_file: str, output_file: str, status: str):
        """单个文件转换完成回调"""
        if status == "success":
            self._log(f"[Step1] 已转换：{os.path.basename(shp_file)} → {output_file}", "info")
            
            # 如果设置了自动添加，添加到表格
            if self.chk_auto_add.isChecked():
                output_path = os.path.join(self._convert_thread.shp_folder, output_file)
                self.data_sources[output_file] = {
                    'source_path': shp_file,
                    'saved_path': output_path,
                    'source_type': 'GIS 数据',
                    'cleaned': '未清洗'
                }
                self.add_data_source(output_file, 'GIS 数据', '未清洗')
        else:
            self._log(f"[Step1] 转换失败 {os.path.basename(shp_file)}: {status}", "error")
    
    def _on_convert_finished(self, success_count: int, fail_count: int):
        """转换完成回调"""
        self.bar_shp.setValue(100)
        self.lbl_shp.setText(f"完成：成功 {success_count}，失败 {fail_count}")
        self._log(f"[Step1] 批量转换完成：成功 {success_count}，失败 {fail_count}", "success" if fail_count == 0 else "warn")
        
        # 清理线程引用
        if self._convert_thread:
            self._convert_thread.deleteLater()
            self._convert_thread = None
    
