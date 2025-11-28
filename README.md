# fz_adr_match

QGIS 地址标准化与管网匹配插件 — 完整的多源数据匹配与关联工具。

## ✨ 核心功能

- **多格式数据加载**: CSV、Excel、SHP、GeoJSON 一站式支持
- **智能字段检测**: 自动识别地址字段（省、市、区、街道等）及其类型
- **字段关联推断**: 跨数据源自动识别对应字段关系
- **精准匹配**: 完全相等的字段值匹配
- **模糊匹配**: 基于相似度的容错匹配（可配置阈值）
- **多字段组合匹配**: 同时使用多个字段进行联合匹配
- **混合匹配**: 多种策略自动尝试，按优先级去重
- **结果导出**: 匹配结果导出为 CSV/Excel 格式

## 🚀 快速开始

### 安装

1. 将本目录复制到 QGIS 插件目录：
   ```
   %APPDATA%\QGIS\QGIS3\profiles\default\python\plugins\fz_adr_match_dev
   ```

2. 重启 QGIS，在 **Plugins → Manage and Install Plugins** 中启用 `fz_adr_match_dev`

### 使用

1. 在 QGIS 工具栏或菜单中点击 **地址标准化匹配** 按钮
2. **数据加载**: 选择左表（主表）和右表（待匹配表）
3. **字段映射**: 系统自动检测字段关系，也可手动配置
4. **匹配配置**: 选择匹配类型和参数
5. **执行匹配**: 点击 **开始匹配**
6. **查看结果**: 在结果标签页查看匹配统计和详情
7. **导出结果**: 保存匹配结果

详细说明见 [USAGE_GUIDE.md](USAGE_GUIDE.md)

## 📁 项目结构

```
fz_adr_match_dev/
├── fz_adr_match.py              # 主插件类与 QGIS 集成
├── __init__.py                  # QGIS classFactory 入口
├── metadata.txt                 # 插件元数据
├── resources.qrc                # Qt 资源配置
├── resources_rc.py              # 编译后的资源
├── icons/
│   └── fz_adr_match.svg         # 插件图标
├── core/                        # 核心逻辑
│   ├── field_detector.py        # 字段检测与关联推断
│   ├── data_loader.py           # 多格式数据加载器
│   └── match_engine.py          # 匹配引擎（精准/模糊/组合）
├── ui/                          # 用户界面
│   └── match_dialog.py          # 主对话框 UI（4 个标签页）
├── utils/                       # 工具函数
│   └── generate_test_data.py   # 测试数据生成脚本
├── test_data/                   # 预生成的测试数据
│   ├── test_left.csv            # 左表示例（管网数据）
│   └── test_right.geojson       # 右表示例（第三方数据）
├── README.md                    # 项目说明
├── USAGE_GUIDE.md               # 使用指南（详细）
└── .github/
    └── copilot-instructions.md  # AI 代理开发指导
```

## 🔧 核心模块说明

### `FieldDetector`（字段检测与推断）
```python
# 自动识别字段类型和地址子字段
detector = FieldDetector()
fields = detector.detect_dataset_fields(data)
# → [{'name': 'province', 'inferred_type': 'address', 'category': 'province', ...}]

# 跨数据源字段关系推断
relationships = detector.infer_field_relationships({
    'source1': data1,
    'source2': data2
})
# → [('source1', 'field1', 'source2', 'field2', similarity_score), ...]
```

### `DataLoader`（数据加载器）
```python
# 自动检测格式加载
from core.data_loader import DataLoader
data, geom_col = DataLoader.auto_load('file.csv')  # 或 .xlsx, .shp, .geojson
```

### `MatchEngine`（匹配引擎）
```python
from core.match_engine import MatchEngine

engine = MatchEngine(fuzzy_threshold=0.7)

# 精准匹配
exact_results = engine.exact_match(left_data, right_data, 'province', 'province')

# 模糊匹配
fuzzy_results = engine.fuzzy_match(left_data, right_data, 'address', 'address')

# 多字段组合匹配
multi_results = engine.multi_field_match(
    left_data, right_data,
    [('province', 'province'), ('city', 'city'), ('district', 'district')]
)

# 混合匹配（多策略）
batch_results = engine.batch_match(
    left_data, right_data,
    [
        {'type': 'exact', 'left_key': 'address', 'right_key': 'address'},
        {'type': 'fuzzy', 'left_key': 'address', 'right_key': 'address'},
    ]
)
```

### `MatchDialog`（主 UI）
四个标签页：
1. **数据加载** — 选择和预览数据文件
2. **字段映射** — 自动检测和手动配置字段对应关系
3. **匹配配置** — 选择匹配策略和参数
4. **匹配结果** — 显示统计和详细结果

## 📊 数据流

```
CSV/Excel/SHP/GeoJSON 文件
         ↓
    DataLoader.auto_load()
         ↓
    List[Dict] 统一格式
         ↓
    FieldDetector（字段类型识别 + 字段关系推断）
         ↓
    用户在 MatchDialog 中选择匹配策略
         ↓
    MatchEngine（执行匹配：精准/模糊/组合）
         ↓
    匹配结果 List[Dict]（包含 confidence 等元数据）
         ↓
    导出为 CSV/Excel 或可视化在 QGIS
```

## 🧪 测试数据

## 下一步

- 在 `fz_adr_match.py` 中实现具体的 UI（工具栏按钮 / 面板）和业务逻辑。
- 将 `addr_std_1.py`、`addr_std_gis_1.py` 等核心功能拆成模块，封装为插件中的服务。
- 添加 Processing Provider，使标准化和匹配功能能通过 QGIS 模型/批处理调用。


