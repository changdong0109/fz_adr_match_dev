# Step5 步骤2：配置验证参数 - 核心目标与数据来源梳理

## 一、核心目标

**步骤2的核心目标是：配置数据治理验证所需的参数，为步骤3的验证做准备**

具体包括：
1. 选择原始客户数据文件（从Step1导入的数据）
2. 选择匹配结果文件（从Step4输出的匹配结果）
3. 配置图层和字段匹配关系（原始SHP图层、数据库图层、匹配字段）
4. 设置验证参数（位置偏差阈值、坐标系转换等）

## 二、数据来源与位置

### 1. 原始客户数据文件

**来源位置**：
- 文件路径：`{customer_folder}/*.csv`
  - `customer_folder` 通过 `global_config.get_region_info()['customer_folder']` 获取
  - 例如：`C:\Users\chang\Desktop\qigsPlugsTest\河北省廊坊市客户数据\`
  
**数据标识**：
- 从 `{cache_folder}/file_status.json` 读取文件状态
- 只显示 `source_type == "客户采集数据"` 的文件
- `file_status.json` 结构：
  ```json
  {
    "文件名.csv": {
      "source_type": "客户采集数据",
      "cleaned": "已清洗/未清洗",
      "source_path": "原始文件路径"
    }
  }
  ```

**实现位置**：
- `ui/steps/step5_widget.py` → `_load_source_files()` 方法（第45-88行）
- 已实现：✅

### 2. 匹配结果文件

**来源位置**：
- 文件路径：`{cache_folder}/match_results/*.csv`
  - `cache_folder` 通过 `global_config.get_region_info()['cache_folder']` 获取
  - 例如：`C:\Users\chang\Desktop\qigsPlugsTest\河北省廊坊市cache数据\match_results\`
  
**文件命名规则**（由Step4生成）：
- `{源表名}_精确匹配_{N}条.csv`
- `{源表名}_高置信度_{N}条.csv`
- `{源表名}_需人工确认_{N}条.csv`
- `{源表名}_未匹配_{N}条.csv`
  
**过滤规则**：
- 只加载 `_精确匹配_` 和 `_高置信度_` 的文件（用于验证）

**实现位置**：
- `ui/steps/step5_widget.py` → `_load_match_files()` 方法（第90-122行）
- 已实现：✅

### 3. QGIS图层

**来源位置**：
- 从当前QGIS项目中获取已加载的图层
- 使用 `QgsProject.instance().mapLayers()` 获取

**图层类型**：
- **原始SHP图层**：从步骤0加载的SHP文件图层
  - 识别方式：`layer.dataProvider().name() == 'ogr'` 且 `layer.source().endswith('.shp')`
- **数据库图层**：PostgreSQL/PostGIS/Spatialite等数据库连接图层
  - 识别方式：`layer.dataProvider().name()` 在 `['postgres', 'spatialite']` 中

**实现位置**：
- `ui/steps/step5_widget.py` → `_refresh_layer_combos()` 方法
- 部分实现：⚠️（需要完善数据库图层识别逻辑）

## 三、当前实现状态

### ✅ 已实现

1. **UI结构**（`_card_validation_config()` 方法）：
   - 原始客户数据文件选择下拉框
   - 匹配结果文件选择下拉框
   - 图层选择下拉框（原始SHP图层、数据库图层）
   - 字段选择下拉框（GID字段、匹配字段）
   - 验证参数设置（偏差阈值、坐标系转换）

2. **文件列表加载**：
   - `_load_source_files()` - 从 `file_status.json` 读取客户采集数据文件 ✅
   - `_load_match_files()` - 从 `match_results/` 目录读取匹配结果文件 ✅

3. **图层列表刷新**：
   - `_refresh_layer_combos()` - 从QGIS项目获取图层列表 ✅

### ⚠️ 部分实现

1. **字段自动检测**：
   - `_on_source_file_changed()` - 占位符，未实现
   - `_on_match_file_changed()` - 占位符，未实现
   - 需要从匹配结果CSV文件中检测字段名

2. **图层字段加载**：
   - `_on_database_layer_changed()` - 部分实现，需要完善
   - `_on_shp_layer_changed()` - 部分实现，需要完善

### ❌ 未实现

1. **字段自动检测逻辑**：
   - 从匹配结果文件中检测目标表GID字段
   - 从匹配结果文件中检测源表匹配字段（`【匹配源:表名】字段名` 或 `[源:表名]字段名`）

2. **字段联动逻辑**：
   - 选择原始客户数据文件后，自动加载其字段列表
   - 选择匹配结果文件后，自动检测并显示可用字段
   - 选择图层后，自动加载图层字段列表

3. **验证逻辑**：
   - `_start_validation()` - 占位符，未实现

## 四、需要补充的内容

### 1. 字段自动检测功能

**位置**：`core/field_detector.py` 或 `ui/steps/step5_widget.py`

**需要实现**：
```python
def auto_detect_target_gid_field(match_result_file: str) -> Optional[str]:
    """从匹配结果文件中自动检测目标表GID字段"""
    # 读取CSV第一行（表头）
    # 查找包含"gid"的列名（不区分大小写）
    # 优先返回 exact_gid, target_gid 等常见命名
    pass

def auto_detect_source_match_fields(match_result_file: str) -> List[str]:
    """从匹配结果文件中自动检测源表匹配字段"""
    # 读取CSV第一行（表头）
    # 查找格式为 【匹配源:表名】字段名 或 [源:表名]字段名 的列
    # 排除gid字段，返回2-3个字段
    pass
```

### 2. 文件字段读取功能

**位置**：使用 `core/data_loader.py` 的 `auto_load()` 方法

**需要实现**：
```python
def _on_source_file_changed(self, file_name: str):
    """原始客户数据文件选择变化时，加载字段列表"""
    if not file_name or file_name == "请选择...":
        return
    
    # 获取文件完整路径
    file_path = os.path.join(customer_folder, file_name)
    
    # 读取文件表头
    data, _ = DataLoader.auto_load(file_path)
    if data:
        fields = list(data[0].keys())
        # 更新字段下拉框
        self.source_field1_combo.clear()
        self.source_field2_combo.clear()
        for field in fields:
            self.source_field1_combo.addItem(field)
            self.source_field2_combo.addItem(field)
```

### 3. 匹配结果文件字段检测

**位置**：`ui/steps/step5_widget.py` → `_on_match_file_changed()` 方法

**需要实现**：
```python
def _on_match_file_changed(self, file_name: str):
    """匹配结果文件选择变化时，自动检测字段"""
    if not file_name or file_name == "请选择...":
        return
    
    # 获取文件完整路径
    file_path = os.path.join(cache_folder, "match_results", file_name)
    
    # 读取文件表头
    data, _ = DataLoader.auto_load(file_path)
    if data:
        fields = list(data[0].keys())
        
        # 自动检测目标表GID字段
        gid_field = self._auto_detect_gid_field(fields)
        if gid_field:
            # 更新GID下拉框
            self.target_gid_combo.clear()
            self.target_gid_combo.addItem(gid_field)
        
        # 自动检测源表匹配字段
        match_fields = self._auto_detect_source_match_fields(fields)
        # 更新匹配字段下拉框
        self.source_match_field1_combo.clear()
        self.source_match_field2_combo.clear()
        for field in match_fields[:2]:
            self.source_match_field1_combo.addItem(field)
            if len(match_fields) > 1:
                self.source_match_field2_combo.addItem(field)
        
        # 显示检测到的字段信息
        self.match_fields_info.setText(f"检测到 {len(fields)} 个字段，GID: {gid_field or '未检测到'}")
```

### 4. 图层字段加载

**位置**：`ui/steps/step5_widget.py` → `_on_database_layer_changed()` 和 `_on_shp_layer_changed()` 方法

**需要完善**：
- 从 `QgsVectorLayer.fields()` 获取字段列表
- 更新对应的字段下拉框

## 五、数据流转关系

```
Step1 (文件导入)
    ↓
    保存到 customer_folder
    记录到 cache/file_status.json (source_type="客户采集数据")
    ↓
Step5 步骤2：从 file_status.json 读取客户采集数据文件列表
    ↓
    用户选择原始客户数据文件
    ↓
Step4 (匹配任务)
    ↓
    生成匹配结果 → cache/match_results/{源表}_精确匹配_{N}条.csv
    ↓
Step5 步骤2：从 match_results/ 目录读取匹配结果文件列表
    ↓
    用户选择匹配结果文件
    ↓
    自动检测字段（GID、匹配字段）
    ↓
Step0 (加载SHP到QGIS)
    ↓
    QGIS图层列表
    ↓
Step5 步骤2：从QGIS项目获取图层列表
    ↓
    用户选择图层
    ↓
    加载图层字段列表
    ↓
    配置完成，进入步骤3验证
```

## 六、关键代码位置

| 功能 | 文件位置 | 方法/代码行 |
|------|---------|------------|
| 加载客户数据文件列表 | `ui/steps/step5_widget.py` | `_load_source_files()` (45-88行) |
| 加载匹配结果文件列表 | `ui/steps/step5_widget.py` | `_load_match_files()` (90-122行) |
| 刷新图层列表 | `ui/steps/step5_widget.py` | `_refresh_layer_combos()` |
| 文件状态读取 | `utils/cache.py` | `load_cache('file_status')` |
| 全局配置获取 | `ui/widgets/global_config_widget.py` | `get_region_info()` |
| 数据加载 | `core/data_loader.py` | `auto_load()` |
| 字段检测（待实现） | `core/field_detector.py` 或 `ui/steps/step5_widget.py` | 待添加 |

## 七、下一步行动

1. ✅ **已清楚数据来源位置**
   - 客户数据：`customer_folder` + `file_status.json`
   - 匹配结果：`cache_folder/match_results/`
   - QGIS图层：`QgsProject.instance().mapLayers()`

2. ⚠️ **需要补充实现**
   - 字段自动检测逻辑
   - 文件字段读取和下拉框更新
   - 图层字段加载逻辑

3. 📝 **建议实现顺序**
   - 先实现字段自动检测辅助方法
   - 再实现文件选择变化的回调函数
   - 最后完善图层字段加载逻辑

