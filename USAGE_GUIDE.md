# 地址匹配插件使用指南

## 功能概览

该插件为 QGIS 提供完整的**地址数据匹配与标准化**工具，支持：

- ✅ **多格式数据加载**: CSV、Excel、SHP、GeoJSON
- ✅ **智能字段检测**: 自动识别地址字段（省、市、区、街道等）
- ✅ **字段关联推断**: 自动检测不同数据源之间的字段对应关系
- ✅ **精准匹配**: 完全相等匹配
- ✅ **模糊匹配**: 基于相似度的容错匹配
- ✅ **多字段组合匹配**: 跨多个字段的联合匹配
- ✅ **混合匹配**: 多种策略自动尝试
- ✅ **结果导出**: 匹配结果导出为 CSV/Excel

## 快速开始

### 1. 启动插件

在 QGIS 中：
- **Plugins** → **Manage and Install Plugins**
- 搜索 `fz_adr_match` 并启用
- 工具栏或菜单中点击 **地址标准化匹配** 按钮

### 2. 加载测试数据

已预生成示例数据在 `test_data/` 目录：

```
test_data/
├── test_left.csv      # 管网数据（主表，4 条记录）
└── test_right.geojson # 第三方数据（待匹配表，4 条记录）
```

**步骤**:
- 打开插件对话框 → **数据加载** 标签
- **左表数据**：选择 `test_left.csv`
- **右表数据**：选择 `test_right.geojson`
- 系统自动预览数据和字段关系

### 3. 配置字段映射

在 **字段映射** 标签：
- 系统已自动检测字段关系（相似度排序）
- 或在 **手动配置匹配字段** 中选择：
  - 匹配字段组 1: `province` → `address_province`
  - 匹配字段组 2: `city` → `address_city`
  - 匹配字段组 3: `district` → `address_district`

### 4. 执行匹配

在 **匹配配置** 标签：
- 选择匹配类型：
  - **精准匹配**: 完全相等
  - **模糊匹配**: 相似度 ≥ 70%（可调）
  - **多字段组合匹配**: 所有字段同时匹配
  - **混合匹配**: 依次尝试所有策略
- 调整 **模糊匹配相似度阈值**（默认 0.7）
- 点击 **开始匹配**

### 5. 查看结果

在 **匹配结果** 标签：
- 查看匹配统计（总数、匹配数、匹配率）
- 结果表显示前 100 条记录
- 每条记录显示：
  - 左表 ID / 右表 ID
  - 匹配类型（exact/fuzzy/multi_field_exact）
  - 匹配信度（0-100%）
  - 原始地址数据

### 6. 导出结果

点击 **导出结果** 按钮，选择输出格式（CSV/Excel）

---

## 架构说明

### 项目结构

```
fz_adr_match_dev/
├── fz_adr_match.py          # 主插件类
├── __init__.py              # QGIS 入口
├── metadata.txt             # 插件元数据
├── core/
│   ├── field_detector.py    # 字段检测与关联推断
│   ├── data_loader.py       # 多格式数据加载
│   └── match_engine.py      # 匹配引擎（精准/模糊/组合）
├── ui/
│   └── match_dialog.py      # 主对话框 UI
├── utils/
│   └── generate_test_data.py # 测试数据生成
└── test_data/
    ├── test_left.csv
    └── test_right.geojson
```

### 核心模块说明

#### `FieldDetector`（字段检测器）
- 自动识别字段类型（address/id/numeric/date/text）
- 识别地址子字段（province/city/district/street/building）
- 计算跨数据源字段的相似度并推断关联

#### `DataLoader`（数据加载器）
- 支持 CSV（自动编码检测）、Excel、SHP、GeoJSON
- 统一数据格式为 List[Dict]

#### `MatchEngine`（匹配引擎）
- `exact_match()`: 精准匹配
- `fuzzy_match()`: 基于相似度的模糊匹配
- `multi_field_match()`: 多字段组合匹配（索引加速）
- `batch_match()`: 多策略批量匹配

#### `MatchDialog`（主对话框）
- 4 个标签页：数据加载 → 字段映射 → 匹配配置 → 结果显示
- 支持进度条、实时预览、统计信息

---

## 高级用法

### 自定义字段识别规则

编辑 `core/field_detector.py` 中的 `ADDRESS_FIELD_PATTERNS`：

```python
ADDRESS_FIELD_PATTERNS = {
    'province': ['省', 'province', '...'],
    'city': ['市', 'city', '...'],
    # 添加更多规则...
}
```

### 调整模糊匹配阈值

在匹配配置中修改 **模糊匹配相似度阈值**（0.0-1.0）：
- 0.5: 容错度高（可能误匹配）
- 0.7: 平衡（推荐）
- 0.9: 严格（容错度低）

### 添加新的数据格式支持

在 `core/data_loader.py` 中添加 `load_xxx()` 方法：

```python
@staticmethod
def load_xxx(file_path: str) -> List[Dict]:
    # 实现新格式加载逻辑
    pass
```

---

## 常见问题

### Q1: 加载大文件时很慢
**A**: 
- 考虑使用分块加载（批处理）
- 对超大表使用分片匹配
- 为频繁查询的字段建立索引

### Q2: 模糊匹配精度不高
**A**:
- 调高相似度阈值（0.8+）
- 检查字段名是否正确
- 尝试多字段组合匹配而非单字段

### Q3: 如何处理特殊字符（如繁体字）
**A**:
- 预处理数据：规范化字符集（简繁转换）
- 在 `MatchEngine._similarity_score()` 中实现预处理

### Q4: 能否保存/加载匹配配置？
**A**:
- 当前版本不支持配置保存
- 可扩展：在 `MatchDialog` 中添加 `save_config()` / `load_config()` 方法

---

## 开发与扩展

### 添加新的匹配策略

在 `core/match_engine.py` 中添加新方法：

```python
def phonetic_match(self, left_data, right_data, left_key, right_key):
    """基于发音相似度的匹配"""
    # 实现逻辑...
```

### 集成地理空间匹配

结合 SHP/GeoJSON 的几何信息：

```python
def spatial_match(self, left_data, right_data, distance_threshold=100):
    """基于地理距离的匹配"""
    # 使用 shapely/fiona 计算距离...
```

### 批处理与 API

未来可扩展为 REST API 或 QGIS Processing Provider，支持脚本化调用。

---

## 测试

### 运行单元测试

```bash
python -m pytest tests/
```

### 生成新的测试数据

```bash
python utils/generate_test_data.py
```

---

## 许可证

GPL v3 (QGIS 标准)

---

## 联系与反馈

提交 Issue 或 Pull Request 到 GitHub 仓库。
