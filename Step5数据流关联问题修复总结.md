# Step5 数据流关联问题修复总结

## 一、问题分析结果

### 数据流转过程中的文件名变化链

```
Step1: 廊坊工商户.csv (原始文件)
  ↓
Step2: 廊坊工商户_清洗.csv (清洗后)
  ↓
Step3: 廊坊工商户_清洗_标准化.csv (标准化后)
  ↓
Step4: 廊坊工商户_精确匹配_100条.csv (匹配结果，文件名简化)
```

### 缺失的关联信息

1. **文件流转链缺失**：缓存中没有记录文件名变化链
2. **匹配结果文件名简化**：无法直接追溯到原始文件名
3. **match_tasks.json缺少原始文件信息**：只记录处理后的文件名

---

## 二、已实现的解决方案

### 方案：智能反向查找（立即实现）

在 `_on_match_file_changed` 方法中实现了智能反向查找逻辑：

#### 1. 从匹配结果文件名提取源表名
```python
# 廊坊工商户_精确匹配_100条.csv → 廊坊工商户
source_name = match_file_name
for suffix in ['_精确匹配_', '_高置信度_', '_需人工确认_', '_未匹配_']:
    if suffix in source_name:
        source_name = source_name.split(suffix)[0]
        break
```

#### 2. 从match_tasks.json查找原始文件名
- 查找任务配置中的源表文件（如：`廊坊工商户_清洗_标准化.csv`）
- 反向查找原始文件名（如：`廊坊工商户.csv`）

#### 3. 从file_status.json查找原始文件名
- 根据源表名（如：`廊坊工商户`）查找原始文件名
- 检查 `source_type == "客户采集数据"`

#### 4. 自动选择原始客户数据文件下拉框
- 如果找到了原始文件，自动在下拉框中选择
- 如果下拉框中没有，先刷新列表再选择

---

## 三、实现的方法

### 新增方法：

1. **`_auto_link_source_file_from_match_result(match_file_name: str)`**
   - 主方法：从匹配结果文件名智能反向查找到原始客户数据文件
   - 调用时机：在 `_on_match_file_changed` 中，检测完字段后自动调用

2. **`_find_original_file_from_processed_name(processed_file_name: str, cache_folder: str)`**
   - 从处理后的文件名（如：`廊坊工商户_清洗_标准化.csv`）反向查找到原始文件名
   - 去掉处理后缀（`_标准化`、`_清洗`、`_清洗_标准化`）
   - 从 `file_status.json` 查找匹配的原始文件名

3. **`_find_original_file_by_name(source_name: str, cache_folder: str)`**
   - 根据源表名（如：`廊坊工商户`）查找原始文件名
   - 从 `file_status.json` 查找文件名以源表名开头的文件

4. **`_try_select_source_file(file_name: str)`**
   - 尝试在下拉框中选择指定的原始客户数据文件
   - 用于刷新列表后的延迟选择

---

## 四、使用效果

### 用户操作流程：

1. **用户选择匹配结果文件**：`廊坊工商户_精确匹配_100条.csv`
2. **系统自动执行**：
   - 检测匹配结果文件的字段
   - 提取源表名：`廊坊工商户`
   - 从 `match_tasks.json` 或 `file_status.json` 查找原始文件
   - 自动选择原始客户数据文件下拉框：`廊坊工商户.csv`
3. **用户看到**：原始客户数据文件已自动关联

---

## 五、后续优化建议

### 优先级1: 增强缓存记录（中期优化）

在Step2/Step3/Step4中增强缓存，记录文件流转链：

1. **增强 file_status.json**
   ```json
   {
     "廊坊工商户.csv": {
       "source_type": "客户采集数据",
       "cleaned": "已清洗",
       "source_path": "...",
       "file_chain": {
         "step2_cleaned": "廊坊工商户_清洗.csv",
         "step3_parsed": "廊坊工商户_清洗_标准化.csv"
       }
     }
   }
   ```

2. **增强 match_tasks.json**
   ```json
   {
     "tasks": [{
       "source": "廊坊工商户_清洗_标准化.csv",
       "source_original": "廊坊工商户.csv",
       "targets": [{
         "table": "节点_清洗_标准化.csv",
         "original": "节点.shp",
         "original_path": "..."
       }]
     }]
   }
   ```

### 优先级2: 在匹配结果文件中保存元数据（长期优化）

在匹配结果CSV中添加元数据列，直接记录原始文件信息。

---

## 六、测试建议

1. **测试场景1**：选择匹配结果文件，检查是否自动关联到原始客户数据文件
2. **测试场景2**：测试不同的匹配结果文件名格式（精确匹配、高置信度等）
3. **测试场景3**：测试文件不存在或无法关联的情况（应该给出提示）

---

## 七、代码位置

- **文件**: `ui/steps/step5_widget.py`
- **方法**: 
  - `_on_match_file_changed` (第754行)
  - `_auto_link_source_file_from_match_result` (新增)
  - `_find_original_file_from_processed_name` (新增)
  - `_find_original_file_by_name` (新增)
  - `_try_select_source_file` (新增)

