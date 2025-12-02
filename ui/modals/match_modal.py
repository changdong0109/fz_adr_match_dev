"""
字段关联配置对话框
直接配置：源表字段 = 目标表字段
"""
import os
import pandas as pd
from typing import List, Dict, Optional, Callable
from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget, QTableWidgetItem,
    QPushButton, QHeaderView, QGroupBox, QListWidget, QListWidgetItem
)
from qgis.PyQt.QtCore import Qt
from ..widgets.no_wheel_combo_box import NoWheelComboBox


class MatchModal(QDialog):
    """字段关联配置 - 直接配置字段对"""
    
    def __init__(self, parent=None, global_config=None):
        super().__init__(parent)
        self.setWindowTitle("关联字段配置")
        self.setObjectName("match_modal")
        self.setModal(True)
        self.resize(650, 450)
        
        self._global_config = global_config
        self._target_key = ""
        self._source_file = ""
        self._target_file = ""
        self._source_fields: List[str] = []
        self._target_fields: List[str] = []
        self._conditions: Dict[str, List[Dict]] = {}  # 保存的配置
        
        self._build_ui()
    
    def set_global_config(self, config):
        self._global_config = config
    
    def set_relations_callback(self, callback: Callable):
        """兼容接口（不使用）"""
        pass
    
    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)
        
        # 标题
        self.title_label = QLabel("配置关联字段")
        self.title_label.setObjectName("match_modal_title")
        layout.addWidget(self.title_label)
        
        subtitle = QLabel("选择源表和目标表中用于匹配的字段（值相等的记录会被关联）")
        subtitle.setObjectName("match_modal_subtitle")
        layout.addWidget(subtitle)
        
        # 三栏布局
        main_layout = QHBoxLayout()
        
        # 左：源表字段
        left_box = QGroupBox("源表字段")
        left_box.setObjectName("match_modal_group")
        left_layout = QVBoxLayout(left_box)
        left_layout.setContentsMargins(6, 10, 6, 6)
        self.source_list = QListWidget()
        self.source_list.setObjectName("match_modal_field_list")
        left_layout.addWidget(self.source_list)
        main_layout.addWidget(left_box)
        
        # 中：已选关联对
        center_box = QGroupBox("已选关联（值相等则匹配）")
        center_box.setObjectName("match_modal_group")
        center_layout = QVBoxLayout(center_box)
        center_layout.setContentsMargins(6, 10, 6, 6)
        center_layout.setSpacing(8)
        
        self.pair_table = QTableWidget(0, 4)
        self.pair_table.setObjectName("match_modal_table")
        self.pair_table.setHorizontalHeaderLabels(["源表字段", "匹配方式", "目标表字段", ""])
        self.pair_table.verticalHeader().setVisible(False)
        self.pair_table.verticalHeader().setDefaultSectionSize(36)
        self.pair_table.setAlternatingRowColors(True)
        
        header = self.pair_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(1, 90)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(3, 40)
        
        center_layout.addWidget(self.pair_table)
        
        btn_add = QPushButton("← 添加 →")
        btn_add.setObjectName("match_modal_btn_add")
        btn_add.setToolTip("选中左右两边的字段后点击添加")
        btn_add.clicked.connect(self._add_pair)
        center_layout.addWidget(btn_add)
        
        main_layout.addWidget(center_box)
        
        # 右：目标表字段
        right_box = QGroupBox("目标表字段")
        right_box.setObjectName("match_modal_group")
        right_layout = QVBoxLayout(right_box)
        right_layout.setContentsMargins(6, 10, 6, 6)
        self.target_list = QListWidget()
        self.target_list.setObjectName("match_modal_field_list")
        right_layout.addWidget(self.target_list)
        main_layout.addWidget(right_box)
        
        layout.addLayout(main_layout, 1)
        
        # 按钮
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        
        btn_ok = QPushButton("确定")
        btn_ok.setObjectName("match_modal_btn_ok")
        btn_ok.clicked.connect(self._on_ok)
        btn_row.addWidget(btn_ok)
        
        btn_cancel = QPushButton("取消")
        btn_cancel.setObjectName("match_modal_btn_cancel")
        btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(btn_cancel)
        
        layout.addLayout(btn_row)
    
    def set_source_and_target(self, source_file: str, target_key: str):
        """设置源表和目标表"""
        self._source_file = self._extract_file_name(source_file)
        self._target_key = target_key
        self._target_file = self._extract_file_name(target_key)
        
        self.title_label.setText(f"{self._source_file} ↔ {self._target_file}")
        
        self._load_fields()
        self._restore_saved_pairs()
    
    def set_target_name(self, name: str):
        """兼容旧接口"""
        self._target_key = name
        self._target_file = self._extract_file_name(name)
        self.title_label.setText(f"关联配置 - {self._target_file}")
        self._load_target_fields()
        self._restore_saved_pairs()
    
    def _extract_file_name(self, key: str) -> str:
        """从 key 中提取文件名"""
        import re
        match = re.match(r'\[.*?\](.+)', key)
        return match.group(1) if match else key
    
    def _load_fields(self):
        """加载两表的字段"""
        self._load_source_fields()
        self._load_target_fields()
    
    def _load_source_fields(self):
        """加载源表字段"""
        self.source_list.clear()
        self._source_fields = self._read_columns(self._source_file)
        
        for f in self._source_fields:
            self.source_list.addItem(QListWidgetItem(f))
        
        if not self._source_fields:
            item = QListWidgetItem("(无法加载)")
            item.setForeground(Qt.GlobalColor.gray)
            self.source_list.addItem(item)
    
    def _load_target_fields(self):
        """加载目标表字段"""
        self.target_list.clear()
        self._target_fields = self._read_columns(self._target_file)
        
        for f in self._target_fields:
            self.target_list.addItem(QListWidgetItem(f))
        
        if not self._target_fields:
            item = QListWidgetItem("(无法加载)")
            item.setForeground(Qt.GlobalColor.gray)
            self.target_list.addItem(item)
    
    def _read_columns(self, file_name: str) -> List[str]:
        """读取文件列名"""
        path = self._find_file_path(file_name)
        if not path:
            return []
        
        try:
            if path.lower().endswith('.csv'):
                for enc in ['utf-8', 'gbk', 'gb2312', 'utf-8-sig']:
                    try:
                        df = pd.read_csv(path, nrows=0, encoding=enc)
                        return list(df.columns)
                    except UnicodeDecodeError:
                        continue
            elif path.lower().endswith(('.xlsx', '.xls')):
                df = pd.read_excel(path, nrows=0)
                return list(df.columns)
        except Exception as e:
            print(f"[MatchModal] 读取失败: {e}")
        return []
    
    def _find_file_path(self, file_name: str) -> Optional[str]:
        """查找文件"""
        if not self._global_config:
            p = self.parent()
            while p:
                if hasattr(p, 'global_config'):
                    self._global_config = p.global_config
                    break
                p = p.parent()
        
        if not self._global_config:
            return None
        
        info = self._global_config.get_region_info()
        for folder in [info.get('customer_folder', ''), info.get('shp_folder', '')]:
            if folder and os.path.isdir(folder):
                path = os.path.join(folder, file_name)
                if os.path.exists(path):
                    return path
        return None
    
    def _add_pair(self):
        """添加选中的字段对"""
        src_item = self.source_list.currentItem()
        tgt_item = self.target_list.currentItem()
        
        if not src_item or not tgt_item:
            return
        if src_item.text().startswith("(") or tgt_item.text().startswith("("):
            return
        
        src = src_item.text()
        tgt = tgt_item.text()
        
        # 检查是否已存在
        if self._pair_exists(src, tgt):
            return
        
        self._add_pair_to_table(src, tgt)
    
    def _pair_exists(self, src: str, tgt: str) -> bool:
        """检查字段对是否已存在"""
        for row in range(self.pair_table.rowCount()):
            src_item = self.pair_table.item(row, 0)
            tgt_item = self.pair_table.item(row, 2)
            if src_item and tgt_item:
                if src_item.text() == src and tgt_item.text() == tgt:
                    return True
        return False
    
    def _add_pair_to_table(self, src: str, tgt: str, match_type: str = "="):
        """添加字段对到表格"""
        row = self.pair_table.rowCount()
        self.pair_table.insertRow(row)
        
        # 源表字段
        src_item = QTableWidgetItem(src)
        src_item.setFlags(src_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.pair_table.setItem(row, 0, src_item)
        
        # 匹配方式下拉框
        combo_match = NoWheelComboBox()
        combo_match.setEditable(False)
        combo_match.addItems(["=", "LIKE", "包含", "被包含", "前缀", "后缀"])
        combo_match.setCurrentText(match_type)
        combo_match.setToolTip("= 精确匹配\nLIKE 模糊匹配\n包含 源包含目标\n被包含 目标包含源\n前缀 源以目标开头\n后缀 源以目标结尾")
        self.pair_table.setCellWidget(row, 1, combo_match)
        
        # 目标表字段
        tgt_item = QTableWidgetItem(tgt)
        tgt_item.setFlags(tgt_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.pair_table.setItem(row, 2, tgt_item)
        
        # 删除按钮
        btn_del = QPushButton("删")
        btn_del.setObjectName("match_modal_btn_del")
        btn_del.clicked.connect(self._delete_pair)
        self.pair_table.setCellWidget(row, 3, btn_del)
    
    def _delete_pair(self):
        """删除字段对"""
        sender = self.sender()
        for r in range(self.pair_table.rowCount()):
            if self.pair_table.cellWidget(r, 3) is sender:
                self.pair_table.removeRow(r)
                break
    
    def _restore_saved_pairs(self):
        """恢复已保存的配置"""
        self.pair_table.setRowCount(0)
        saved = self._conditions.get(self._target_key, [])
        for p in saved:
            self._add_pair_to_table(p.get("src", ""), p.get("tgt", ""), p.get("match_type", "="))
    
    def get_pairs(self) -> List[Dict]:
        """获取已配置的字段对"""
        pairs = []
        for row in range(self.pair_table.rowCount()):
            src_item = self.pair_table.item(row, 0)
            tgt_item = self.pair_table.item(row, 2)
            combo_match = self.pair_table.cellWidget(row, 1)
            if src_item and tgt_item:
                pairs.append({
                    "src": src_item.text(),
                    "match_type": combo_match.currentText() if combo_match else "=",
                    "tgt": tgt_item.text()
                })
        return pairs
    
    def get_summary(self) -> str:
        """获取摘要"""
        pairs = self.get_pairs()
        return f"{len(pairs)}对" if pairs else ""
    
    def _on_ok(self):
        """确定"""
        if self._target_key:
            self._conditions[self._target_key] = self.get_pairs()
        self.accept()
