"""
全局配置组件：数据范围与目录
在所有步骤中都可见
"""
import json
import os
from typing import Dict, Callable, Optional
from qgis.PyQt.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QComboBox
)
from qgis.PyQt.QtCore import Qt, pyqtSignal


class GlobalConfigWidget(QWidget):
    """全局配置组件：数据范围与目录"""
    
    # 信号：当区域或目录改变时发出
    region_changed = pyqtSignal()
    
    def __init__(self, parent=None, log_callback: Optional[Callable[[str, str], None]] = None):
        super().__init__(parent)
        self.log_callback = log_callback or (lambda msg, level="info": None)
        
        # 区域数据
        self._region_tree: Dict[str, Dict[str, list]] = {}
        self.region_province = ""
        self.region_city = ""
        self.region_county = ""
        self.base_folder = ""
        self.customer_folder = ""
        self.shp_folder = ""
        self.cache_folder = ""
        self._dirty_region = False
        
        # 初始化区域数据
        self._region_tree = self._load_region_tree()
        self._build_ui()
    
    def _build_ui(self):
        """构建UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)
        
        # 第一行：省市区和根目录
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("省："))
        self.combo_prov = QComboBox()
        self.combo_prov.setMinimumWidth(100)
        row1.addWidget(self.combo_prov)
        
        row1.addWidget(QLabel("市："))
        self.combo_city = QComboBox()
        self.combo_city.setMinimumWidth(100)
        row1.addWidget(self.combo_city)
        
        row1.addWidget(QLabel("县/区："))
        self.combo_county = QComboBox()
        self.combo_county.setMinimumWidth(100)
        row1.addWidget(self.combo_county)
        
        row1.addWidget(QLabel("根目录："))
        self.edit_base = QLineEdit()
        self.edit_base.setMinimumWidth(200)
        row1.addWidget(self.edit_base)
        
        btn_choose = QPushButton("选择根目录")
        btn_choose.setStyleSheet("font-size: 12px; padding: 4px 8px;")
        row1.addWidget(btn_choose)
        row1.addStretch()
        layout.addLayout(row1)
        
        # 自动生成的目录
        layout.addWidget(QLabel("客户数据目录（自动生成）："))
        self.label_customer = QLineEdit()
        self.label_customer.setReadOnly(True)
        self.label_customer.setStyleSheet("background-color: #f0f0f0; border: 1px solid #d0d0d0; color: #000000;")
        layout.addWidget(self.label_customer)
        
        layout.addWidget(QLabel("SHP 数据目录（自动生成）："))
        self.label_shp = QLineEdit()
        self.label_shp.setReadOnly(True)
        self.label_shp.setStyleSheet("background-color: #f0f0f0; border: 1px solid #d0d0d0; color: #000000;")
        layout.addWidget(self.label_shp)
        
        layout.addWidget(QLabel("数据缓存目录（自动生成）："))
        self.label_cache = QLineEdit()
        self.label_cache.setReadOnly(True)
        self.label_cache.setStyleSheet("background-color: #f0f0f0; border: 1px solid #d0d0d0; color: #000000;")
        layout.addWidget(self.label_cache)
        
        # 确认按钮
        row2 = QHBoxLayout()
        self.btn_confirm_dirs = QPushButton("确认并生成目录")
        self.btn_confirm_dirs.setStyleSheet("""
            QPushButton {
                font-size: 13px;
                padding: 6px 12px;
                background-color: #0078d4;
                color: white;
                border: none;
                border-radius: 4px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #005a9e;
            }
            QPushButton:disabled {
                background-color: #c0c0c0;
            }
        """)
        row2.addWidget(self.btn_confirm_dirs)
        row2.addStretch()
        layout.addLayout(row2)
        
        layout.addWidget(QLabel("提示：省/市/根目录必选；县/区可为空。确认后会在根目录下生成客户、SHP、缓存目录（缓存目录名：省市cache）。"))
        
        # 信号连接
        self.combo_prov.currentTextChanged.connect(self._on_province_changed)
        self.combo_city.currentTextChanged.connect(self._on_city_changed)
        self.combo_county.currentTextChanged.connect(self._on_county_changed)
        self.edit_base.textChanged.connect(self._on_base_changed)
        btn_choose.clicked.connect(self._on_choose_base)
        self.btn_confirm_dirs.clicked.connect(self._confirm_dirs)
        
        # 初始化
        self._init_regions()
        self._refresh_paths()
        self._refresh_confirm_state()
    
    def _load_region_tree(self) -> Dict[str, Dict[str, list]]:
        """加载区域树"""
        base = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "regions")
        prov_path = os.path.join(base, "provinces.json")
        city_path = os.path.join(base, "cities.json")
        area_path = os.path.join(base, "areas.json")
        tree: Dict[str, Dict[str, list]] = {}
        try:
            with open(prov_path, "r", encoding="utf-8") as f:
                provs = json.load(f)
            with open(city_path, "r", encoding="utf-8") as f:
                cities = json.load(f)
            with open(area_path, "r", encoding="utf-8") as f:
                areas = json.load(f)
            for prov in provs:
                pname = prov.get("name", "")
                tree[pname] = {}
            for c in cities:
                pname = c.get("province", "")
                cname = c.get("name", "")
                tree.setdefault(pname, {})[cname] = []
            for a in areas:
                pname = a.get("province", "")
                cname = a.get("city", "")
                aname = a.get("name", "")
                tree.setdefault(pname, {}).setdefault(cname, []).append(aname)
        except Exception:
            tree = {"江苏省": {"南京市": ["鼓楼区", "玄武区"], "苏州市": ["姑苏区"]}}
        return tree
    
    def _init_regions(self):
        """初始化区域下拉框"""
        self.combo_prov.clear()
        self.combo_city.clear()
        self.combo_county.clear()
        self.combo_prov.addItem("")
        for p in sorted(self._region_tree.keys()):
            self.combo_prov.addItem(p)
    
    def _on_province_changed(self, text: str):
        """省份改变"""
        self.region_province = text.strip()
        self.region_city = ""
        self.region_county = ""
        self.combo_city.clear()
        self.combo_city.addItem("")
        for c in sorted(self._region_tree.get(self.region_province, {}).keys()):
            self.combo_city.addItem(c)
        self.combo_county.clear()
        self.combo_county.addItem("")
        self._dirty_region = True
        self._refresh_paths()
        self._refresh_confirm_state()
        self.region_changed.emit()
    
    def _on_city_changed(self, text: str):
        """城市改变"""
        self.region_city = text.strip()
        self.region_county = ""
        self.combo_county.clear()
        self.combo_county.addItem("")
        for a in sorted(self._region_tree.get(self.region_province, {}).get(self.region_city, [])):
            self.combo_county.addItem(a)
        self._dirty_region = True
        self._refresh_paths()
        self._refresh_confirm_state()
        self.region_changed.emit()
    
    def _on_county_changed(self, text: str):
        """区县改变"""
        self.region_county = text.strip()
        self._dirty_region = True
        self._refresh_paths()
        self._refresh_confirm_state()
        self.region_changed.emit()
    
    def _on_base_changed(self, text: str):
        """根目录改变"""
        self.base_folder = text.strip()
        self._dirty_region = True
        self._refresh_paths()
        self._refresh_confirm_state()
    
    def _on_choose_base(self):
        """选择根目录"""
        from qgis.PyQt.QtWidgets import QFileDialog
        path = QFileDialog.getExistingDirectory(self, "选择根目录", "")
        if path:
            self.edit_base.setText(path)
    
    def _refresh_paths(self):
        """刷新路径"""
        if not (self.region_province and self.region_city and self.base_folder):
            self.customer_folder = ""
            self.shp_folder = ""
            self.cache_folder = ""
        else:
            base = self.base_folder.rstrip("\\/")
            suffix = f"{self.region_province}{self.region_city}{self.region_county}".strip()
            self.customer_folder = os.path.join(base, f"{suffix}客户数据")
            self.shp_folder = os.path.join(base, f"{suffix}SHP数据")
            cache_suffix = f"{self.region_province}{self.region_city}".strip()
            self.cache_folder = os.path.join(base, f"{cache_suffix}cache")
        self.label_customer.setText(self.customer_folder)
        self.label_shp.setText(self.shp_folder)
        self.label_cache.setText(self.cache_folder)
    
    def _confirm_dirs(self):
        """确认并生成目录"""
        if not (self.region_province and self.region_city):
            self.log_callback("[目录] 请先选择省与市。", "warn")
            return
        if not self.base_folder:
            self.log_callback("[目录] 请先选择根目录。", "warn")
            return
        if not self.customer_folder:
            self._refresh_paths()
        try:
            for p in [self.customer_folder, self.shp_folder, self.cache_folder]:
                os.makedirs(p, exist_ok=True)
            self.log_callback("[目录] 已生成/复用目录：\n" + "\n".join([self.customer_folder, self.shp_folder, self.cache_folder]), "success")
            self._save_cache()
            self._dirty_region = False
            self._refresh_confirm_state()
        except Exception as e:
            self.log_callback(f"[目录] 创建失败: {e}", "error")
    
    def _refresh_confirm_state(self):
        """刷新确认按钮状态"""
        allow = bool(self.region_province and self.region_city and self.base_folder and self._dirty_region)
        self.btn_confirm_dirs.setEnabled(allow)
    
    def _region_key(self) -> str:
        """区域键"""
        if not (self.region_province and self.region_city):
            return ""
        return f"{self.region_province}-{self.region_city}-{self.region_county}"
    
    def _cache_file_path(self) -> str:
        """缓存文件路径"""
        if not self.cache_folder:
            return ""
        return os.path.join(self.cache_folder, "region_cache.json")
    
    def _save_cache(self):
        """保存缓存"""
        key = self._region_key()
        if not key:
            return
        path = self._cache_file_path()
        if not path:
            return
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            data = {}
            if os.path.isfile(path):
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            data[key] = {"base": self.base_folder}
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self.log_callback(f"[缓存] 写入失败: {e}", "error")
    
    def get_region_info(self) -> Dict[str, str]:
        """获取区域信息（供其他组件使用）"""
        return {
            "province": self.region_province,
            "city": self.region_city,
            "county": self.region_county,
            "base_folder": self.base_folder,
            "customer_folder": self.customer_folder,
            "shp_folder": self.shp_folder,
            "cache_folder": self.cache_folder,
        }

