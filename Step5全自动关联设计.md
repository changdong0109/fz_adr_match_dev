# Step5 全自动关联设计

## 数据流梳理

### Step1: 导入原始数据
- **客户数据**：Excel/CSV → 保存到 `{省}{市}原始客户数据/`
- **GIS数据**：SHP → 保存到 `{省}{市}原始SHP数据/`，并转换为CSV
- **缓存**：`file_status.json` 记录 `source_path`, `source_type`, `file_chain.step1_original`

### Step2: 字段映射与清洗
- **字段组合配置**：配置哪些字段用于提取关键匹配信息（有顺序）
- **保存位置**：`{文件名}_combo_config.json`
- **结构**：
  ```json
  {
    "title": "字段组合",
    "subtitle": "",
    "fields": [
      {"role": "", "field": "location"},
      {"role": "", "field": "address"},
      {"role": "", "field": "name"}
    ]
  }
  ```
- **作用**：解决"用哪些字段去提取关键匹配信息"，字段是一个或多个的并清洗

### Step3: 标准化解析
- **作用**：进一步清洗，提取关键地址信息组合，支持匹配
- **输出**：标准化后的CSV文件（`{文件名}_标准化.csv`）
- **缓存**：`file_status.json` 记录 `file_chain.step3_parsed`

### Step4: 匹配任务管理
- **任务配置**：源表和目标表的关联，1对多匹配
- **保存位置**：`match_tasks.json`
- **结构**：
  ```json
  {
    "name": "任务组名",
    "source": "源表文件名（标准化后的）",
    "source_original": "原始源表文件名",
    "targets": [
      {
        "table": "目标表文件名",
        "original_path": "原始SHP文件路径",
        "match_fields": "匹配字段配置（JSON字符串）",
        "match_desc": "匹配方式说明"
      }
    ],
    "results": {
      "exact": "精确匹配结果文件名",
      "high_confidence": "高置信度结果文件名",
      "need_review": "需人工确认结果文件名",
      "unmatched": "未匹配结果文件名"
    }
  }
  ```
- **作用**：解决"从哪些数据中去捞数据"，配置1对多匹配

### Step5: 全自动关联（目标）

**核心诉求**：根据前面步骤的配置，全自动关联所有内容，无需手动选择。

## 全自动关联逻辑

### 1. 从匹配结果文件自动关联到任务配置

**输入**：用户选择匹配结果文件（如：`廊坊工商户_精确匹配_2730条.csv`）

**自动关联流程**：
1. 从文件名提取源表名：`廊坊工商户_精确匹配_2730条.csv` → `廊坊工商户`
2. 从 `match_tasks.json` 查找对应的任务：
   - 遍历所有任务的 `results`，找到包含该结果文件名的任务
   - 获取任务的 `source_original`（原始源表文件名）
   - 获取任务的 `targets`（目标表列表）

### 2. 自动关联原始客户数据文件

**从任务配置获取**：
- `source_original`: `廊坊工商户.csv`
- 自动选择 `source_file_combo` 下拉框

### 3. 自动关联Step2的字段组合配置

**从Step2配置获取**：
- 读取 `{source_original}_combo_config.json`
- 获取字段组合：`["location", "address", "name"]`
- **这些字段用于**：
  - 在匹配结果文件中查找对应的字段（如：`[源:廊坊工商户]location`）
  - 自动选择源表匹配字段（字段1、字段2）

### 4. 自动关联原始SHP图层

**从任务配置获取**：
- 从 `targets[].original_path` 获取原始SHP文件路径
- 自动加载SHP文件到QGIS
- 自动选择 `original_shp_layer_combo` 下拉框
- 自动选择GID字段

### 5. 自动关联数据库图层

**问题**：数据库图层无法自动选择，因为：
- 数据库图层是用户手动加载到QGIS的
- 无法从配置中获取数据库图层的名称

**解决方案**：
- 如果只有一个点图层，自动选择
- 否则，提示用户选择（这是合理的，因为数据库图层可能来自外部）

### 6. 自动关联数据库图层匹配字段

**从Step4配置获取**：
- 从 `targets[].match_fields` 获取匹配字段配置
- 解析JSON字符串，获取源表字段和目标表字段的对应关系
- 自动选择 `database_field1_combo` 和 `database_field2_combo`

### 7. 自动关联目标表GID字段

**从匹配结果文件获取**：
- 检测 `[目标:表名]gid` 字段
- 自动选择 `target_gid_combo`

## 实现要点

### 1. Step4需要保存匹配字段配置

**当前问题**：`match_tasks.json` 中的 `match_fields` 是空字符串

**解决方案**：
- 在 `MatchModal` 中，当用户配置完字段对后，保存到 `match_tasks.json`
- 格式：JSON字符串，如：`[{"src": "name", "tgt": "名称", "match_type": "="}]`

### 2. Step5需要读取Step2的字段组合配置

**实现**：
- 从 `source_original` 文件名获取字段组合配置路径
- 读取 `{文件名}_combo_config.json`
- 根据字段组合配置，在匹配结果文件中查找对应的字段

### 3. Step5需要解析Step4的匹配字段配置

**实现**：
- 从 `targets[].match_fields` 解析JSON字符串
- 获取源表字段和目标表字段的对应关系
- 自动选择数据库图层的匹配字段

## 完整自动关联流程

```
用户选择匹配结果文件
    ↓
1. 从match_tasks.json查找任务配置
    ↓
2. 自动选择原始客户数据文件（source_original）
    ↓
3. 读取Step2字段组合配置（{source_original}_combo_config.json）
    ↓
4. 自动选择源表匹配字段（从字段组合配置中获取）
    ↓
5. 自动加载原始SHP文件（从targets[].original_path获取）
    ↓
6. 自动选择原始SHP图层和GID字段
    ↓
7. 自动选择目标表GID字段（从匹配结果文件检测）
    ↓
8. 解析Step4匹配字段配置（从targets[].match_fields获取）
    ↓
9. 自动选择数据库图层匹配字段（如果数据库图层已选择）
    ↓
10. 所有配置完成，用户只需点击"开始验证"
```

## 需要修复的问题

1. **Step4需要保存匹配字段配置到match_tasks.json**
2. **Step5需要读取Step2的字段组合配置**
3. **Step5需要解析Step4的匹配字段配置**
4. **Step5需要根据字段组合配置自动选择源表匹配字段**

