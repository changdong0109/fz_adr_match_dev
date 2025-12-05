# Step5字段动态读取说明

## 概述

Step5验证功能中的所有字段都是**完全动态**从缓存配置文件中读取的，用户无需手动配置。

## 动态读取流程

### 1. 选择任务组后自动触发

当用户在Step5中选择任务组后，系统会自动执行以下步骤：

1. **从 `match_tasks.json` 读取任务组配置**
   - 获取 `source_original`（原始客户数据文件名）
   - 获取 `results`（匹配结果文件列表）
   - 获取 `targets`（目标表配置，包含原始SHP路径）

### 2. 自动关联原始客户数据文件

从任务组的 `source_original` 沿 `file_chain` 追溯：
- 读取 `file_status.json`
- 通过 `file_chain` 找到原始客户数据文件路径

### 3. 自动加载Step2字段配置

**关键步骤：动态读取Step2配置**

```python
# 1. 从缓存读取Step2字段组合配置
file_stem = os.path.splitext(original_file_name)[0]
combo_config_path = os.path.join(cache_folder, f"{file_stem}_combo_config.json")

# 2. 读取配置文件
with open(combo_config_path, 'r', encoding='utf-8') as f:
    combo_config = json.load(f)

# 3. 提取字段名列表
field_names = [f.get('field', '') for f in fields if f.get('field')]
# 例如: ['location', 'address', 'name']
```

**配置文件位置**：
- `{缓存目录}/{文件名}_combo_config.json`
- 例如：`河北省廊坊市cache数据/廊坊工商户_combo_config.json`

### 4. 动态匹配匹配结果文件中的字段

**从匹配结果文件CSV的列名中动态查找**：

```python
# 1. 读取匹配结果文件的列名
with open(match_file_path, 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    match_file_columns = reader.fieldnames or []

# 2. 从文件名提取源表名
source_name = "廊坊工商户"  # 从文件名中提取

# 3. 动态匹配字段（三种策略）
for field_name in field_names:  # ['location', 'address', 'name']
    # 策略1: 精确匹配 `[源:表名]字段名`
    source_field_pattern = f"[源:{source_name}]{field_name}"
    # 例如: "[源:廊坊工商户]location"
    
    # 策略2: 精确匹配 `【匹配源:表名】字段名`
    match_source_field_pattern = f"【匹配源:{source_name}】{field_name}"
    
    # 策略3: 模糊匹配（字段名包含在列名中）
    # 在 match_file_columns 中查找包含 field_name 的列
```

**匹配结果**：
- 原始字段名：`['location', 'address', 'name']` → 保存在 `self._original_field_names`
- 匹配结果字段名：`['[源:廊坊工商户]location', '[源:廊坊工商户]address', '[源:廊坊工商户]name']` → 保存在 `self._matched_field_names`

### 5. 验证时使用不同的字段名

- **原始客户数据验证**：使用 `original_field_names`（如 `location`）
- **匹配结果验证**：使用 `matched_field_names`（如 `[源:廊坊工商户]location`）

## 完全动态特性

### ✅ 无需手动配置

所有字段都从缓存配置文件中动态读取：
- Step2字段配置 → `{文件名}_combo_config.json`
- 匹配结果文件列名 → CSV文件头
- 任务组配置 → `match_tasks.json`
- 文件状态 → `file_status.json`

### ✅ 自动匹配和查找

- 自动从匹配结果文件名提取源表名
- 自动在匹配结果文件列名中查找对应字段
- 支持多种字段名格式（`[源:表名]字段名` 或 `【匹配源:表名】字段名`）
- 支持模糊匹配

### ✅ 实时更新

每次选择任务组或匹配结果文件时，都会：
1. 重新读取缓存配置文件
2. 重新匹配字段名
3. 更新验证配置

## 字段映射关系

```
Step2配置文件 (combo_config.json)
├─ 字段名: location
├─ 字段名: address
└─ 字段名: name
         ↓ (动态匹配)
匹配结果文件 (CSV列名)
├─ [源:廊坊工商户]location  ← 匹配到
├─ [源:廊坊工商户]address   ← 匹配到
└─ [源:廊坊工商户]name      ← 匹配到

验证使用：
├─ 原始客户数据验证 → 使用原始字段名 (location, address, name)
└─ 匹配结果验证 → 使用匹配结果字段名 ([源:廊坊工商户]location, ...)
```

## 总结

**是的，所有字段都是完全动态从缓存配置文件中读取的！**

- ✅ 无需用户手动配置
- ✅ 自动读取Step2配置
- ✅ 自动匹配匹配结果文件中的字段
- ✅ 支持多种字段名格式
- ✅ 每次选择任务时重新读取和匹配

