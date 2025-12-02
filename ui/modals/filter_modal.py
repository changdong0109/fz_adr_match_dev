"""
过滤条件模态对话框 - 支持字段选择
遵循文档规范：样式通过 objectName + QSS 管理
"""
import os
import pandas as pd
from typing import List, Dict, Optional
from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QGroupBox, QSplitter,
    QListWidget, QListWidgetItem, QAbstractItemView, QLineEdit
)
from qgis.PyQt.QtCore import Qt
from ..widgets.no_wheel_combo_box import NoWheelComboBox


class FilterModal(QDialog):
    """目标表过滤条件对话框 - 支持字段选择"""
    
    def __init__(self, parent=None, global_config=None):
        super().__init__(parent)
        self.setWindowTitle("目标表过滤条件")
        self.setObjectName("filter_modal")
        self.setModal(True)
        self.resize(700, 500)
        self._target_name = ""
        self._conditions = {}  # 存储每个目标表的条件
        self._global_config = global_config
        self._fields: List[str] = []  # 当前表的字段列表
        self._build_ui()
    
    def set_global_config(self, config):
        """设置全局配置"""
        self._global_config = config
    
    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)
        
        # 标题
        self.title_label = QLabel("目标表过滤条件 -")
        self.title_label.setObjectName("filter_modal_title")
        layout.addWidget(self.title_label)
        
        # 使用 QSplitter 分左右两栏
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setObjectName("filter_modal_splitter")
        
        # ===== 左侧：字段列表 =====
        left_panel = QGroupBox("可用字段")
        left_panel.setObjectName("filter_modal_group")
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(8, 12, 8, 8)
        
        self.field_list = QListWidget()
        self.field_list.setObjectName("filter_modal_field_list")
        self.field_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.field_list.itemDoubleClicked.connect(self._on_field_double_clicked)
        left_layout.addWidget(self.field_list)
        
        hint = QLabel("双击字段添加到条件")
        hint.setObjectName("filter_modal_hint")
        left_layout.addWidget(hint)
        
        left_panel.setMinimumWidth(180)
        left_panel.setMaximumWidth(220)
        splitter.addWidget(left_panel)
        
        # ===== 右侧：条件构建 =====
        right_panel = QGroupBox("过滤条件")
        right_panel.setObjectName("filter_modal_group")
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(8, 12, 8, 8)
        right_layout.setSpacing(10)
        
        # 条件构建表格
        self.cond_table = QTableWidget(0, 5)
        self.cond_table.setObjectName("filter_modal_cond_table")
        self.cond_table.setHorizontalHeaderLabels(["字段", "运算符", "值", "逻辑", "操作"])
        self.cond_table.verticalHeader().setVisible(False)
        self.cond_table.verticalHeader().setDefaultSectionSize(36)
        self.cond_table.setMinimumHeight(150)
        self.cond_table.setAlternatingRowColors(True)
        
        header = self.cond_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(1, 80)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(3, 60)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(4, 50)
        
        right_layout.addWidget(self.cond_table)
        
        # 添加条件按钮
        btn_add_row = QPushButton("+ 添加条件")
        btn_add_row.setObjectName("filter_modal_btn_add")
        btn_add_row.clicked.connect(lambda: self._add_condition_row())
        right_layout.addWidget(btn_add_row)
        
        # 生成的SQL预览
        lbl_preview = QLabel("生成的条件预览:")
        lbl_preview.setObjectName("filter_modal_label")
        right_layout.addWidget(lbl_preview)
        
        self.txt_preview = QTextEdit()
        self.txt_preview.setObjectName("filter_modal_preview")
        self.txt_preview.setReadOnly(True)
        self.txt_preview.setMaximumHeight(60)
        right_layout.addWidget(self.txt_preview)
        
        splitter.addWidget(right_panel)
        splitter.setSizes([200, 480])
        
        layout.addWidget(splitter, 1)
        
        # 按钮行
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        
        btn_ok = QPushButton("确定")
        btn_ok.setObjectName("filter_modal_btn_ok")
        btn_ok.clicked.connect(self._on_ok)
        btn_row.addWidget(btn_ok)
        
        btn_cancel = QPushButton("取消")
        btn_cancel.setObjectName("filter_modal_btn_cancel")
        btn_cancel.clicked.connect(self.close)
        btn_row.addWidget(btn_cancel)
        
        layout.addLayout(btn_row)
    
    def set_target_name(self, name: str):
        """设置目标表名称并加载字段"""
        self._target_name = name
        self.title_label.setText(f"目标表过滤条件 - {name}")
        
        print(f"[FilterModal] set_target_name: {name}")
        print(f"[FilterModal] _global_config 存在: {self._global_config is not None}")
        
        # 加载字段列表
        self._load_fields(name)
        
        # 恢复之前保存的条件
        saved_conditions = self._conditions.get(name, [])
        self._load_conditions_to_table(saved_conditions)
        
        # 更新预览
        self._update_preview()
    
    def _load_fields(self, file_name: str):
        """加载文件的字段列表"""
        self._fields = []
        self.field_list.clear()
        
        # 尝试从全局配置获取文件路径
        file_path = self._find_file_path(file_name)
        print(f"[FilterModal] 查找文件: {file_name} -> {file_path}")
        
        if file_path and os.path.exists(file_path):
            try:
                # 读取文件头获取字段
                if file_path.lower().endswith('.csv'):
                    # 尝试多种编码
                    for encoding in ['utf-8', 'gbk', 'gb2312', 'utf-8-sig']:
                        try:
                            df = pd.read_csv(file_path, nrows=0, encoding=encoding)
                            break
                        except UnicodeDecodeError:
                            continue
                    else:
                        df = pd.read_csv(file_path, nrows=0, encoding='utf-8', errors='ignore')
                elif file_path.lower().endswith(('.xlsx', '.xls')):
                    df = pd.read_excel(file_path, nrows=0)
                else:
                    df = None
                
                if df is not None:
                    self._fields = list(df.columns)
                    print(f"[FilterModal] 加载到 {len(self._fields)} 个字段")
            except Exception as e:
                print(f"[FilterModal] 加载字段失败: {e}")
        else:
            print(f"[FilterModal] 文件不存在或路径为空")
        
        # 填充字段列表
        for field in self._fields:
            item = QListWidgetItem(field)
            self.field_list.addItem(item)
        
        # 如果没有字段，显示提示
        if not self._fields:
            item = QListWidgetItem("(无法加载字段)")
            item.setForeground(Qt.GlobalColor.gray)
            self.field_list.addItem(item)
    
    def _find_file_path(self, file_name: str) -> Optional[str]:
        """查找文件的完整路径"""
        if not self._global_config:
            # 尝试从父窗口获取
            parent = self.parent()
            while parent:
                if hasattr(parent, 'global_config'):
                    self._global_config = parent.global_config
                    break
                parent = parent.parent()
        
        if not self._global_config:
            print(f"[FilterModal] 无法获取全局配置")
            return None
        
        region_info = self._global_config.get_region_info()
        customer_folder = region_info.get('customer_folder', '')
        shp_folder = region_info.get('shp_folder', '')
        
        print(f"[FilterModal] 查找文件: '{file_name}'")
        print(f"[FilterModal] customer_folder: '{customer_folder}'")
        print(f"[FilterModal] shp_folder: '{shp_folder}'")
        
        # 在客户数据文件夹查找
        if customer_folder and os.path.isdir(customer_folder):
            files_in_dir = os.listdir(customer_folder)
            print(f"[FilterModal] customer_folder 文件列表: {files_in_dir[:5]}...")  # 显示前5个
            
            path = os.path.join(customer_folder, file_name)
            if os.path.exists(path):
                print(f"[FilterModal] 精确匹配: {path}")
                return path
            
            # 尝试模糊匹配（文件名可能有空格或特殊字符）
            for f in files_in_dir:
                if f.lower() == file_name.lower():
                    print(f"[FilterModal] 大小写匹配: {f}")
                    return os.path.join(customer_folder, f)
                # 匹配不带扩展名的情况
                if os.path.splitext(f)[0].lower() == os.path.splitext(file_name)[0].lower():
                    print(f"[FilterModal] 不带扩展名匹配: {f}")
                    return os.path.join(customer_folder, f)
                # 包含匹配（处理空格等问题）
                if file_name.replace(" ", "") in f.replace(" ", "") or f.replace(" ", "") in file_name.replace(" ", ""):
                    print(f"[FilterModal] 包含匹配: {f}")
                    return os.path.join(customer_folder, f)
        
        # 在SHP数据文件夹查找
        if shp_folder and os.path.isdir(shp_folder):
            files_in_dir = os.listdir(shp_folder)
            print(f"[FilterModal] shp_folder 文件列表: {files_in_dir[:5]}...")  # 显示前5个
            
            path = os.path.join(shp_folder, file_name)
            if os.path.exists(path):
                print(f"[FilterModal] 精确匹配: {path}")
                return path
            
            # 尝试模糊匹配
            for f in files_in_dir:
                if f.lower() == file_name.lower():
                    return os.path.join(shp_folder, f)
                if os.path.splitext(f)[0].lower() == os.path.splitext(file_name)[0].lower():
                    return os.path.join(shp_folder, f)
                if file_name.replace(" ", "") in f.replace(" ", "") or f.replace(" ", "") in file_name.replace(" ", ""):
                    return os.path.join(shp_folder, f)
        
        print(f"[FilterModal] 未找到文件: '{file_name}'")
        return None
    
    def _on_field_double_clicked(self, item: QListWidgetItem):
        """双击字段添加到条件"""
        field = item.text()
        if field and not field.startswith("("):
            self._add_condition_row(field)
    
    def _add_condition_row(self, field: str = ""):
        """添加条件行"""
        row = self.cond_table.rowCount()
        self.cond_table.insertRow(row)
        
        # 字段下拉框 - 只能从已有字段中选择，不可编辑
        combo_field = NoWheelComboBox()
        combo_field.setEditable(False)
        combo_field.addItems(self._fields)
        if field and field in self._fields:
            combo_field.setCurrentText(field)
        elif self._fields:
            combo_field.setCurrentIndex(0)  # 默认选第一个
        combo_field.currentTextChanged.connect(self._update_preview)
        self.cond_table.setCellWidget(row, 0, combo_field)
        
        # 运算符下拉框
        combo_op = NoWheelComboBox()
        combo_op.addItems(["=", "!=", ">", "<", ">=", "<=", "LIKE", "IN", "IS NULL", "IS NOT NULL"])
        combo_op.currentTextChanged.connect(self._update_preview)
        self.cond_table.setCellWidget(row, 1, combo_op)
        
        # 值输入
        txt_value = QLineEdit()
        txt_value.setPlaceholderText("输入值...")
        txt_value.textChanged.connect(self._update_preview)
        self.cond_table.setCellWidget(row, 2, txt_value)
        
        # 逻辑运算符
        combo_logic = NoWheelComboBox()
        combo_logic.addItems(["AND", "OR"])
        combo_logic.currentTextChanged.connect(self._update_preview)
        self.cond_table.setCellWidget(row, 3, combo_logic)
        
        # 删除按钮
        btn_del = QPushButton("删")
        btn_del.setObjectName("filter_modal_btn_del")
        btn_del.clicked.connect(lambda checked, r=row: self._delete_row(r))
        self.cond_table.setCellWidget(row, 4, btn_del)
        
        self._update_logic_visibility()
        self._update_preview()
    
    def _delete_row(self, row: int):
        """删除条件行"""
        # 查找实际行号
        sender = self.sender()
        if sender:
            for r in range(self.cond_table.rowCount()):
                widget = self.cond_table.cellWidget(r, 4)
                if widget is sender:
                    row = r
                    break
        
        self.cond_table.removeRow(row)
        self._update_logic_visibility()
        self._update_preview()
    
    def _update_logic_visibility(self):
        """更新逻辑列的可见性：最后一行隐藏逻辑下拉框"""
        row_count = self.cond_table.rowCount()
        for row in range(row_count):
            is_last_row = (row == row_count - 1)
            logic_widget = self.cond_table.cellWidget(row, 3)
            
            if is_last_row:
                # 最后一行：隐藏逻辑下拉框（但保留控件）
                if logic_widget and isinstance(logic_widget, NoWheelComboBox):
                    logic_widget.setEnabled(False)
                    logic_widget.setVisible(False)
            else:
                # 非最后一行：显示逻辑下拉框
                if logic_widget and isinstance(logic_widget, NoWheelComboBox):
                    logic_widget.setEnabled(True)
                    logic_widget.setVisible(True)
                elif logic_widget is None:
                    # 如果没有逻辑下拉框，创建一个
                    combo_logic = NoWheelComboBox()
                    combo_logic.addItems(["AND", "OR"])
                    combo_logic.currentTextChanged.connect(self._update_preview)
                    self.cond_table.setCellWidget(row, 3, combo_logic)
    
    def _update_preview(self):
        """更新条件预览"""
        conditions = []
        for row in range(self.cond_table.rowCount()):
            field_combo = self.cond_table.cellWidget(row, 0)
            op_combo = self.cond_table.cellWidget(row, 1)
            value_edit = self.cond_table.cellWidget(row, 2)
            logic_combo = self.cond_table.cellWidget(row, 3)
            
            if field_combo and op_combo:
                field = field_combo.currentText()
                op = op_combo.currentText()
                value = value_edit.text() if value_edit else ""
                logic = logic_combo.currentText() if logic_combo else "AND"
                
                if field:
                    if op in ("IS NULL", "IS NOT NULL"):
                        cond = f"{field} {op}"
                    elif op == "LIKE":
                        cond = f"{field} LIKE '%{value}%'"
                    elif op == "IN":
                        cond = f"{field} IN ({value})"
                    else:
                        # 判断是否需要加引号
                        if value.isdigit():
                            cond = f"{field} {op} {value}"
                        else:
                            cond = f"{field} {op} '{value}'"
                    
                    conditions.append((cond, logic))
        
        # 组装SQL
        if conditions:
            sql_parts = []
            for i, (cond, logic) in enumerate(conditions):
                if i == 0:
                    sql_parts.append(cond)
                else:
                    sql_parts.append(f"{logic} {cond}")
            sql = " ".join(sql_parts)
        else:
            sql = ""
        
        self.txt_preview.setPlainText(sql)
    
    def _load_conditions_to_table(self, conditions: List[Dict]):
        """加载保存的条件到表格"""
        self.cond_table.setRowCount(0)
        for cond in conditions:
            self._add_condition_row(cond.get("field", ""))
            row = self.cond_table.rowCount() - 1
            
            op_combo = self.cond_table.cellWidget(row, 1)
            if op_combo:
                op_combo.setCurrentText(cond.get("op", "="))
            
            value_edit = self.cond_table.cellWidget(row, 2)
            if value_edit:
                value_edit.setText(cond.get("value", ""))
            
            logic_combo = self.cond_table.cellWidget(row, 3)
            if logic_combo:
                logic_combo.setCurrentText(cond.get("logic", "AND"))
    
    def get_condition(self) -> str:
        """获取当前条件SQL"""
        return self.txt_preview.toPlainText().strip()
    
    def get_condition_for(self, target_name: str) -> str:
        """获取指定目标表的条件"""
        conditions = self._conditions.get(target_name, [])
        if not conditions:
            return ""
        return self.txt_preview.toPlainText().strip()
    
    def _on_ok(self):
        """确定按钮"""
        # 保存条件（结构化数据）
        if self._target_name:
            conditions = []
            for row in range(self.cond_table.rowCount()):
                field_combo = self.cond_table.cellWidget(row, 0)
                op_combo = self.cond_table.cellWidget(row, 1)
                value_edit = self.cond_table.cellWidget(row, 2)
                logic_combo = self.cond_table.cellWidget(row, 3)
                
                if field_combo:
                    conditions.append({
                        "field": field_combo.currentText(),
                        "op": op_combo.currentText() if op_combo else "=",
                        "value": value_edit.text() if value_edit else "",
                        "logic": logic_combo.currentText() if logic_combo else "AND"
                    })
            
            self._conditions[self._target_name] = conditions
        
        self.accept()
