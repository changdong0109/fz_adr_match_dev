# Step5 数据流关联缺失问题与解决方案

## 一、问题根源分析

### 数据流转过程中的文件名变化

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

1. **文件流转链缺失**
   - `file_status.json` 只记录原始文件名
   - 没有记录：原始文件名 → 清洗后文件名 → 标准化文件名

2. **匹配结果文件名简化**
   - 匹配结果文件名：`廊坊工商户_精确匹配_100条.csv`
   - 源表文件名：`廊坊工商户_清洗_标准化.csv`
   - **无法直接关联！**

3. **match_tasks.json 缺少原始文件信息**
   - 只记录：`source: "廊坊工商户_清洗_标准化.csv"`
   - 缺少：原始文件名 `廊坊工商户.csv` 和原始SHP路径

---

## 二、Step5需要的完整关联链

### 验证逻辑需要的关联：

```
匹配结果文件: 廊坊工商户_精确匹配_100条.csv
  ├─ 源表名: "廊坊工商户" (从文件名提取)
  ├─ 需要找到: 原始客户数据文件 "廊坊工商户.csv"
  ├─ 需要找到: 原始SHP文件路径 (从file_status.json的source_path)
  └─ 需要找到: 数据库图层 (从QGIS项目)
```

### 当前缺失的环节：

1. ❌ 从匹配结果文件名 `廊坊工商户_精确匹配_100条.csv` → 原始文件名 `廊坊工商户.csv`
2. ❌ 从匹配结果中的目标表GID → 原始SHP文件路径
3. ❌ 从匹配结果中的源表匹配字段 → 原始客户数据文件的字段

---

## 三、解决方案

### 方案A: 智能反向查找（立即实现）

在Step5中实现智能反向查找逻辑：

1. **从匹配结果文件名提取源表名**
   - `廊坊工商户_精确匹配_100条.csv` → `廊坊工商户`

2. **反向查找原始文件名**
   - 尝试1: 直接匹配 `廊坊工商户.csv`
   - 尝试2: 从 `match_tasks.json` 查找源表文件的原始文件名
   - 尝试3: 从 `file_status.json` 查找所有可能的原始文件

3. **从match_tasks.json获取目标表信息**
   - 查找任务配置中的目标表
   - 从目标表文件名反向查找原始SHP文件

### 方案B: 增强缓存记录（中期优化）

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

### 方案C: 在匹配结果文件中保存元数据（长期优化）

在匹配结果CSV中添加元数据列，直接记录原始文件信息。

---

## 四、立即实施方案A：智能反向查找

### 实现步骤：

1. **从匹配结果文件名提取源表名**
   ```python
   # 廊坊工商户_精确匹配_100条.csv → 廊坊工商户
   source_name = match_file.replace("_精确匹配_", "_").replace("_高置信度_", "_")
   source_name = source_name.split("_")[0]  # 取第一部分
   ```

2. **反向查找原始文件名**
   ```python
   # 从file_status.json查找
   for file_name, status in file_status.items():
       if file_name.startswith(source_name) and status.get('source_type') == '客户采集数据':
           return file_name
   ```

3. **从match_tasks.json查找目标表原始文件**
   ```python
   # 读取match_tasks.json
   # 查找源表匹配的任务
   # 获取目标表列表
   # 从file_status.json查找目标表的原始SHP路径
   ```

---

## 五、实施优先级

1. **立即**: 实现方案A（智能反向查找）
2. **中期**: 实施方案B（增强缓存记录）
3. **长期**: 考虑方案C（元数据列）

