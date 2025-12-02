"""
字段关联配置对话框
融合设计：展示已发现的关联 + 手动配置
"""
import os
import pandas as pd
from typing import List, Dict, Optional, Callable
from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget, QTableWidgetItem,
    QPushButton, QHeaderView, QGroupBox, QListWidget, QListWidgetItem,
    QCheckBox, QWidget
)
from qgis.PyQt.QtCore import Qt
from ..widgets.no_wheel_combo_box import NoWheelComboBox


class MatchModal(QDialog):
    """字段关联配置 - 融合已发现关联 + 手动配置"""
    
    def __init__(self, parent=None, global_config=None):
        super().__init__(parent)
        self.setWindowTitle("关联字段配置")
        self.setObjectName("match_modal")
        self.setModal(True)
        self.resize(700, 550)
        
        self._global_config = global_config
        self._target_key = ""
        self._source_file = ""
        self._target_file = ""
        self._source_fields: List[str] = []
        self._target_fields: List[str] = []
        self._discovered_relations: List[Dict] = []  # 来自 Step3 的分析结果
        self._conditions: Dict[str, List[Dict]] = {}  # 保存的配置
        
        # 获取分析结果的回调
        self._get_relations_callback: Optional[Callable] = None
        
        self._build_ui()
    
    def set_global_config(self, config):
        self._global_config = config
    
    def set_relations_callback(self, callback: Callable):
        """设置获取关联分析结果的回调"""
        self._get_relations_callback = callback
    
    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)
        
        # 标题
        self.title_label = QLabel("关联字段配置")
        self.title_label.setObjectName("match_modal_title")
        layout.addWidget(self.title_label)
        
        # === 区域1：已发现的关联（来自分析） ===
        discovered_box = QGroupBox("已发现的关联（来自 Step3 分析，勾选使用）")
        discovered_box.setObjectName("match_modal_group")
        discovered_layout = QVBoxLayout(discovered_box)
        discovered_layout.setContentsMargins(8, 12, 8, 8)
        
        self.discovered_list = QListWidget()
        self.discovered_list.setObjectName("match_modal_discovered_list")
        self.discovered_list.setMaximumHeight(150)
        self.discovered_list.itemChanged.connect(self._on_discovered_changed)
        discovered_layout.addWidget(self.discovered_list)
        
        self.lbl_no_discovered = QLabel("暂无分析数据，请先在 Step3 执行关联分析")
        self.lbl_no_discovered.setObjectName("match_modal_hint")
        self.lbl_no_discovered.setVisible(False)
        discovered_layout.addWidget(self.lbl_no_discovered)
        
        layout.addWidget(discovered_box)
        
        # === 区域2：已选关联对 ===
        selected_box = QGroupBox("已选关联对（源表字段 = 目标表字段）")
        selected_box.setObjectName("match_modal_group")
        selected_layout = QVBoxLayout(selected_box)
        selected_layout.setContentsMargins(8, 12, 8, 8)
        
        self.pair_table = QTableWidget(0, 4)
        self.pair_table.setObjectName("match_modal_table")
        self.pair_table.setHorizontalHeaderLabels(["源表字段", "目标表字段", "来源", ""])
        self.pair_table.verticalHeader().setVisible(False)
        self.pair_table.verticalHeader().setDefaultSectionSize(32)
        self.pair_table.setAlternatingRowColors(True)
        
        header = self.pair_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(2, 80)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(3, 40)
        
        selected_layout.addWidget(self.pair_table)
        layout.addWidget(selected_box)
        
        # === 区域3：手动添加 ===
        manual_box = QGroupBox("手动添加")
        manual_box.setObjectName("match_modal_group")
        manual_layout = QHBoxLayout(manual_box)
        manual_layout.setContentsMargins(8, 12, 8, 8)
        
        manual_layout.addWidget(QLabel("源表:"))
        self.combo_src = NoWheelComboBox()
        self.combo_src.setEditable(False)
        self.combo_src.setMinimumWidth(120)
        manual_layout.addWidget(self.combo_src)
        
        manual_layout.addWidget(QLabel("="))
        
        manual_layout.addWidget(QLabel("目标表:"))
        self.combo_tgt = NoWheelComboBox()
        self.combo_tgt.setEditable(False)
        self.combo_tgt.setMinimumWidth(120)
        manual_layout.addWidget(self.combo_tgt)
        
        btn_add = QPushButton("添加")
        btn_add.setObjectName("match_modal_btn_add")
        btn_add.clicked.connect(self._add_manual_pair)
        manual_layout.addWidget(btn_add)
        
        manual_layout.addStretch()
        layout.addWidget(manual_box)
        
        # === 按钮行 ===
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
        
        self.title_label.setText(f"关联配置：{self._source_file} ↔ {self._target_file}")
        
        self._load_fields()
        self._load_discovered_relations()
        self._restore_saved_pairs()
    
    def _extract_file_name(self, key: str) -> str:
        """从 key 中提取文件名"""
        import re
        match = re.match(r'\[.*?\](.+)', key)
        return match.group(1) if match else key
    
    def _load_fields(self):
        """加载两表的字段"""
        self._source_fields = self._read_columns(self._source_file)
        self._target_fields = self._read_columns(self._target_file)
        
        self.combo_src.clear()
        self.combo_tgt.clear()
        self.combo_src.addItems(self._source_fields)
        self.combo_tgt.addItems(self._target_fields)
    
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
    
    def _load_discovered_relations(self):
        """加载已发现的关联（来自 Step3 分析）"""
        self.discovered_list.clear()
        self._discovered_relations = []
        
        # 通过回调获取分析结果
        if self._get_relations_callback:
            try:
                all_relations = self._get_relations_callback()
                # 筛选：涉及源表和目标表的关联
                for rel in all_relations:
                    file_a = rel.get("file_a", "")
                    file_b = rel.get("file_b", "")
                    
                    # 匹配源表和目标表
                    src_match = self._source_file in file_a or self._source_file in file_b
                    tgt_match = self._target_file in file_a or self._target_file in file_b
                    
                    if src_match and tgt_match and file_a != file_b:
                        # 确定哪个是源表字段，哪个是目标表字段
                        if self._source_file in file_a:
                            src_field = rel.get("field_a", "")
                            tgt_field = rel.get("field_b", "")
                        else:
                            src_field = rel.get("field_b", "")
                            tgt_field = rel.get("field_a", "")
                        
                        self._discovered_relations.append({
                            "src": src_field,
                            "tgt": tgt_field,
                            "overlap": rel.get("overlap_count", 0),
                            "jaccard": rel.get("jaccard", 0)
                        })
            except Exception as e:
                print(f"[MatchModal] 获取关联分析失败: {e}")
        
        # 显示已发现的关联
        if self._discovered_relations:
            self.lbl_no_discovered.setVisible(False)
            for rel in self._discovered_relations:
                text = f"{rel['src']} ↔ {rel['tgt']}  |  共同值: {rel['overlap']}  |  相似度: {rel['jaccard']:.0%}"
                item = QListWidgetItem(text)
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(Qt.CheckState.Unchecked)
                item.setData(Qt.ItemDataRole.UserRole, rel)
                self.discovered_list.addItem(item)
        else:
            self.lbl_no_discovered.setVisible(True)
    
    def _on_discovered_changed(self, item: QListWidgetItem):
        """勾选/取消已发现的关联"""
        rel = item.data(Qt.ItemDataRole.UserRole)
        if not rel:
            return
        
        if item.checkState() == Qt.CheckState.Checked:
            # 添加到已选列表（如果不存在）
            if not self._pair_exists(rel["src"], rel["tgt"]):
                self._add_pair_to_table(rel["src"], rel["tgt"], "分析发现")
        else:
            # 从已选列表移除
            self._remove_pair_from_table(rel["src"], rel["tgt"])
    
    def _pair_exists(self, src: str, tgt: str) -> bool:
        """检查字段对是否已存在"""
        for row in range(self.pair_table.rowCount()):
            src_item = self.pair_table.item(row, 0)
            tgt_item = self.pair_table.item(row, 1)
            if src_item and tgt_item:
                if src_item.text() == src and tgt_item.text() == tgt:
                    return True
        return False
    
    def _add_pair_to_table(self, src: str, tgt: str, source: str = "手动添加"):
        """添加字段对到表格"""
        row = self.pair_table.rowCount()
        self.pair_table.insertRow(row)
        
        src_item = QTableWidgetItem(src)
        src_item.setFlags(src_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.pair_table.setItem(row, 0, src_item)
        
        tgt_item = QTableWidgetItem(tgt)
        tgt_item.setFlags(tgt_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.pair_table.setItem(row, 1, tgt_item)
        
        source_item = QTableWidgetItem(source)
        source_item.setFlags(source_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        source_item.setForeground(Qt.GlobalColor.gray)
        self.pair_table.setItem(row, 2, source_item)
        
        btn_del = QPushButton("删")
        btn_del.setObjectName("match_modal_btn_del")
        btn_del.clicked.connect(self._delete_pair)
        self.pair_table.setCellWidget(row, 3, btn_del)
    
    def _remove_pair_from_table(self, src: str, tgt: str):
        """从表格移除字段对"""
        for row in range(self.pair_table.rowCount() - 1, -1, -1):
            src_item = self.pair_table.item(row, 0)
            tgt_item = self.pair_table.item(row, 1)
            if src_item and tgt_item:
                if src_item.text() == src and tgt_item.text() == tgt:
                    self.pair_table.removeRow(row)
                    break
    
    def _add_manual_pair(self):
        """手动添加字段对"""
        src = self.combo_src.currentText()
        tgt = self.combo_tgt.currentText()
        
        if not src or not tgt:
            return
        
        if self._pair_exists(src, tgt):
            return
        
        self._add_pair_to_table(src, tgt, "手动添加")
    
    def _delete_pair(self):
        """删除字段对"""
        sender = self.sender()
        for r in range(self.pair_table.rowCount()):
            if self.pair_table.cellWidget(r, 3) is sender:
                # 同步取消勾选
                src = self.pair_table.item(r, 0).text()
                tgt = self.pair_table.item(r, 1).text()
                self._uncheck_discovered(src, tgt)
                self.pair_table.removeRow(r)
                break
    
    def _uncheck_discovered(self, src: str, tgt: str):
        """取消勾选已发现的关联"""
        for i in range(self.discovered_list.count()):
            item = self.discovered_list.item(i)
            rel = item.data(Qt.ItemDataRole.UserRole)
            if rel and rel["src"] == src and rel["tgt"] == tgt:
                item.setCheckState(Qt.CheckState.Unchecked)
                break
    
    def _restore_saved_pairs(self):
        """恢复已保存的配置"""
        self.pair_table.setRowCount(0)
        saved = self._conditions.get(self._target_key, [])
        
        for p in saved:
            src, tgt = p.get("src", ""), p.get("tgt", "")
            source = p.get("source", "已保存")
            self._add_pair_to_table(src, tgt, source)
            
            # 同步勾选已发现的关联
            for i in range(self.discovered_list.count()):
                item = self.discovered_list.item(i)
                rel = item.data(Qt.ItemDataRole.UserRole)
                if rel and rel["src"] == src and rel["tgt"] == tgt:
                    item.setCheckState(Qt.CheckState.Checked)
                    break
    
    def get_pairs(self) -> List[Dict]:
        """获取已配置的字段对"""
        pairs = []
        for row in range(self.pair_table.rowCount()):
            src_item = self.pair_table.item(row, 0)
            tgt_item = self.pair_table.item(row, 1)
            source_item = self.pair_table.item(row, 2)
            if src_item and tgt_item:
                pairs.append({
                    "src": src_item.text(),
                    "tgt": tgt_item.text(),
                    "source": source_item.text() if source_item else ""
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
