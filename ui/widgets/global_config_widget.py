"""
全局配置组件
在所有步骤中都可见
"""
import json
import os
from typing import Dict, Callable, Optional
from qgis.PyQt.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QComboBox
)
from qgis.PyQt.QtCore import Qt, pyqtSignal, QSettings


class GlobalConfigWidget(QWidget):
    """全局配置组件"""
    
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
        self._config_loaded = False  # 标记是否已经加载过配置（防止重复推断）
        
        # 初始化区域数据
        self._region_tree = self._load_region_tree()
        self._build_ui()
        # 尝试加载上次的配置（在UI构建完成后）
        # 使用 QTimer 延迟执行，确保UI完全初始化，避免信号冲突
        from qgis.PyQt.QtCore import QTimer
        QTimer.singleShot(200, self._load_last_config)
    
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
        btn_choose.setObjectName("global_config_btn_choose")
        row1.addWidget(btn_choose)
        row1.addStretch()
        layout.addLayout(row1)
        
        # 自动生成的目录
        layout.addWidget(QLabel("客户数据目录（自动生成）："))
        self.label_customer = QLineEdit()
        self.label_customer.setObjectName("global_config_path_display")
        self.label_customer.setReadOnly(True)
        layout.addWidget(self.label_customer)
        
        layout.addWidget(QLabel("SHP 数据目录（自动生成）："))
        self.label_shp = QLineEdit()
        self.label_shp.setObjectName("global_config_path_display")
        self.label_shp.setReadOnly(True)
        layout.addWidget(self.label_shp)
        
        layout.addWidget(QLabel("数据缓存目录（自动生成）："))
        self.label_cache = QLineEdit()
        self.label_cache.setObjectName("global_config_path_display")
        self.label_cache.setReadOnly(True)
        layout.addWidget(self.label_cache)
        
        # 确认按钮
        row2 = QHBoxLayout()
        self.btn_confirm_dirs = QPushButton("确认并生成目录")
        self.btn_confirm_dirs.setObjectName("global_config_btn_confirm")
        row2.addWidget(self.btn_confirm_dirs)
        row2.addStretch()
        layout.addLayout(row2)
        
        layout.addWidget(QLabel("提示：省/市/根目录必选；县/区可为空。确认后会在根目录下生成三个目录：xx省xx市xx县客户数据、xx省xx市xx县shp数据、xx省xx市xx县cache数据。"))
        
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
            # 加载省份数据，建立 code -> name 映射
            with open(prov_path, "r", encoding="utf-8") as f:
                provs = json.load(f)
            prov_code_to_name = {p.get("code", ""): p.get("name", "") for p in provs}
            for pname in prov_code_to_name.values():
                tree[pname] = {}
            
            # 加载城市数据，建立 code -> name 映射，并通过 provinceCode 关联到省份
            with open(city_path, "r", encoding="utf-8") as f:
                cities = json.load(f)
            city_code_to_name = {c.get("code", ""): c.get("name", "") for c in cities}
            for c in cities:
                province_code = c.get("provinceCode", "")
                province_name = prov_code_to_name.get(province_code, "")
                city_name = c.get("name", "")
                if province_name and city_name:
                    tree.setdefault(province_name, {})[city_name] = []
            
            # 加载区县数据，通过 cityCode 和 provinceCode 关联到城市和省份
            with open(area_path, "r", encoding="utf-8") as f:
                areas = json.load(f)
            for a in areas:
                province_code = a.get("provinceCode", "")
                city_code = a.get("cityCode", "")
                area_name = a.get("name", "")
                province_name = prov_code_to_name.get(province_code, "")
                city_name = city_code_to_name.get(city_code, "")
                if province_name and city_name and area_name:
                    tree.setdefault(province_name, {}).setdefault(city_name, []).append(area_name)
        except Exception as e:
            # 如果加载失败，使用默认数据
            import traceback
            print(f"[GlobalConfig] 加载区域数据失败: {e}")
            traceback.print_exc()
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
        # 先阻止信号，避免递归调用
        self.combo_city.blockSignals(True)
        self.combo_county.blockSignals(True)
        
        self.region_province = text.strip()
        self.region_city = ""
        self.region_county = ""
        self.combo_city.clear()
        self.combo_city.addItem("")
        # 填充城市下拉框
        if self.region_province:
            cities = sorted(self._region_tree.get(self.region_province, {}).keys())
            for c in cities:
                self.combo_city.addItem(c)
        self.combo_county.clear()
        self.combo_county.addItem("")
        
        # 恢复信号
        self.combo_city.blockSignals(False)
        self.combo_county.blockSignals(False)
        
        # 清空根目录，等待用户选择城市后自动加载历史配置
        self.base_folder = ""
        self.edit_base.blockSignals(True)
        self.edit_base.setText("")
        self.edit_base.blockSignals(False)
        self._dirty_region = True
        self._refresh_paths()
        self._refresh_confirm_state()
        self.region_changed.emit()
    
    def _on_city_changed(self, text: str):
        """城市改变"""
        # 先阻止信号，避免递归调用
        self.combo_county.blockSignals(True)
        
        self.region_city = text.strip()
        self.region_county = ""
        self.combo_county.clear()
        self.combo_county.addItem("")
        
        # 填充县下拉框
        if self.region_province and self.region_city:
            counties = sorted(self._region_tree.get(self.region_province, {}).get(self.region_city, []))
            for a in counties:
                self.combo_county.addItem(a)
            # 尝试从QSettings加载该地区的历史配置（不包含区县）
            self._load_region_config(self.region_province, self.region_city, "")
        
        self.combo_county.blockSignals(False)
        self._dirty_region = True
        self._refresh_paths()
        self._refresh_confirm_state()
        self.region_changed.emit()
    
    def _on_county_changed(self, text: str):
        """区县改变"""
        self.region_county = text.strip()
        # 尝试从QSettings加载该地区的历史配置（包含区县）
        if self.region_province and self.region_city:
            self._load_region_config(self.region_province, self.region_city, self.region_county)
        self._dirty_region = True
        self._refresh_paths()
        self._refresh_confirm_state()
        self.region_changed.emit()
    
    def _load_region_config(self, province: str, city: str, county: str = ""):
        """从QSettings加载指定地区的历史配置"""
        if not (province and city):
            return
        
        try:
            settings = self._get_qsettings()
            # 先尝试加载包含区县的配置
            region_key = self._get_region_key(province, city, county)
            base_folder = settings.value(f"regions/{region_key}/base_folder", "")
            
            # 如果没有区县的配置，尝试加载不包含区县的配置
            if not base_folder and county:
                region_key_no_county = self._get_region_key(province, city, "")
                base_folder = settings.value(f"regions/{region_key_no_county}/base_folder", "")
            
            # 如果找到历史配置且目录存在，自动填充
            if base_folder and os.path.isdir(base_folder):
                self.base_folder = base_folder
                self.edit_base.blockSignals(True)
                self.edit_base.setText(base_folder)
                self.edit_base.blockSignals(False)
                self.log_callback(f"[配置] 已加载历史配置：{province} - {city}" + (f" - {county}" if county else "") + f"，根目录：{base_folder}", "info")
            else:
                # 如果没有找到历史配置，清空根目录和三个目录的显示
                # 让用户知道需要重新选择根目录
                self.base_folder = ""
                self.edit_base.blockSignals(True)
                self.edit_base.setText("")
                self.edit_base.blockSignals(False)
                # 清空三个目录的显示（通过_refresh_paths会自动处理）
        except Exception as e:
            # 加载失败时，也清空显示
            self.base_folder = ""
            self.edit_base.blockSignals(True)
            self.edit_base.setText("")
            self.edit_base.blockSignals(False)
        
            # 注意：不在这里调用_refresh_paths()，由调用者负责刷新
    
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
            # 统一使用：xx省xx市xx县客户数据、xx省xx市xx县shp数据、xx省xx市xx县cache数据
            suffix = f"{self.region_province}{self.region_city}{self.region_county}".strip()
            self.customer_folder = os.path.join(base, f"{suffix}客户数据")
            self.shp_folder = os.path.join(base, f"{suffix}shp数据")
            self.cache_folder = os.path.join(base, f"{suffix}cache数据")
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
        """缓存文件路径（保存在cache目录中）"""
        if not self.cache_folder:
            return ""
        return os.path.join(self.cache_folder, "region_cache.json")
    
    def _get_qsettings(self) -> QSettings:
        """获取QGIS QSettings实例（用于保存插件配置）"""
        return QSettings("fz_adr_match_dev", "global_config")
    
    def _get_region_key(self, province: str, city: str, county: str = "") -> str:
        """生成区域配置的key"""
        return f"{province}|{city}|{county}"
    
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
        
        # 同时保存到全局配置文件（用于下次打开时自动加载）
        self._save_global_config()
    
    def _save_global_config(self):
        """保存全局配置到QGIS QSettings（用于历史配置管理）"""
        if not (self.region_province and self.region_city and self.base_folder):
            return
        try:
            settings = self._get_qsettings()
            # 使用省市区作为key保存配置
            region_key = self._get_region_key(self.region_province, self.region_city, self.region_county)
            settings.setValue(f"regions/{region_key}/base_folder", self.base_folder)
            settings.setValue(f"regions/{region_key}/province", self.region_province)
            settings.setValue(f"regions/{region_key}/city", self.region_city)
            settings.setValue(f"regions/{region_key}/county", self.region_county)
            
            # 保存最后一次使用的配置（用于初始化时加载）
            settings.setValue("last_used/region_key", region_key)
            settings.sync()
        except Exception as e:
            self.log_callback(f"[配置] 保存QGIS配置失败: {e}", "error")
    
    def _load_last_config(self):
        """加载上次的配置（从QGIS QSettings）"""
        # 如果已经加载过配置，不再执行
        if self._config_loaded:
            return
        
        try:
            settings = self._get_qsettings()
            # 获取最后一次使用的配置
            last_region_key = settings.value("last_used/region_key", "")
            if not last_region_key:
                self._config_loaded = True
                return
            
            # 从QSettings加载最后一次使用的配置
            province = settings.value(f"regions/{last_region_key}/province", "")
            city = settings.value(f"regions/{last_region_key}/city", "")
            county = settings.value(f"regions/{last_region_key}/county", "")
            base_folder = settings.value(f"regions/{last_region_key}/base_folder", "")
            
            if not (province and city):
                self._config_loaded = True
                return
            
            # 如果根目录不存在，不加载（让用户重新选择）
            if not base_folder or not os.path.isdir(base_folder):
                self._config_loaded = True
                return
            
            # 设置省份（先阻止信号，避免触发多次更新）
            self.combo_prov.blockSignals(True)
            index = self.combo_prov.findText(province)
            if index >= 0:
                self.combo_prov.setCurrentIndex(index)
            self.combo_prov.blockSignals(False)
            
            # 触发省份改变事件，加载城市列表
            if index >= 0:
                self._on_province_changed(province)
                
                # 设置城市
                self.combo_city.blockSignals(True)
                index = self.combo_city.findText(city)
                if index >= 0:
                    self.combo_city.setCurrentIndex(index)
                self.combo_city.blockSignals(False)
                
                if index >= 0:
                    # 手动加载城市列表（不触发信号，避免递归）
                    self.region_city = city
                    self.combo_county.clear()
                    self.combo_county.addItem("")
                    for a in sorted(self._region_tree.get(self.region_province, {}).get(self.region_city, [])):
                        self.combo_county.addItem(a)
                    
                    # 设置区县（如果存在，不触发信号）
                    if county:
                        self.combo_county.blockSignals(True)
                        index = self.combo_county.findText(county)
                        if index >= 0:
                            self.combo_county.setCurrentIndex(index)
                            self.region_county = county
                        self.combo_county.blockSignals(False)
                
                # 设置根目录（直接设置，不触发信号）
                if base_folder and os.path.isdir(base_folder):
                    self.edit_base.blockSignals(True)
                    self.edit_base.setText(base_folder)
                    self.edit_base.blockSignals(False)
                    # 手动更新内部状态
                    self.base_folder = base_folder.strip()
                    # 刷新路径和状态
                    self._refresh_paths()
                    self._refresh_confirm_state()
                    self._dirty_region = False  # 已加载配置，不需要再次确认
                    
                    self.log_callback(f"[配置] 已加载上次配置：{province} - {city}" + (f" - {county}" if county else "") + f"，根目录：{base_folder}", "info")
                self._config_loaded = True
        except Exception as e:
            # 加载失败不影响正常使用，标记为已加载，不再尝试推断
            import traceback
            print(f"[GlobalConfig] 加载配置失败: {e}")
            traceback.print_exc()
            self._config_loaded = True
    
    
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

