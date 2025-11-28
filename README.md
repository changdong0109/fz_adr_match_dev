# fz_adr_match_dev

QGIS 地址标准化与管网匹配插件 — 轻量化多源数据匹配工具。

## ✨ 核心功能

- **多格式数据加载**: CSV、Excel、SHP、GeoJSON 自动识别与加载
- **智能字段检测**: 自动识别地址字段（省、市、区、街道等）及其类型
- **字段关联推断**: 跨数据源自动识别对应字段关系
- **精准/模糊匹配**: 完全相等匹配 + 基于相似度的容错匹配（可配置阈值）
- **数据清洗**: 去空格、去重、去空行
- **结果导出**: 匹配结果导出为 CSV 格式
- **实时日志**: 控制台日志记录与导出

## 🚀 快速开始

### 安装

1. 将本目录复制到 QGIS 插件目录：
   ```
   %APPDATA%\QGIS\QGIS3\profiles\default\python\plugins\fz_adr_match_dev
   ```

2. 重启 QGIS，在 **Plugins → Manage and Install Plugins** 中启用 `fz_adr_match_dev`

### 使用工作流

1. **打开插件**: 在 QGIS 工具栏或 Plugins 菜单中点击 **地址标准化与管网匹配**
2. **加载数据**: 
   - 点击"选择文件(加载到左表)" → 选择左表（主表，如管网点位）
   - 系统自动加载并在左表预览区显示前 5 行
3. **数据清洗**（可选）:
   - 展开"数据上传与清洗"分组 → 点击"执行清洗"
   - 清洗结果（去空格、去空行）自动缓存到 `cache/cleaned_left.json`
4. **地址标准化**（可选）:
   - 展开"地址标准化"分组 → 选择字段 → 点击"执行标准化"
   - 示例标准化规则：北京市→北京、上海市→上海；可扩展
5. **字段推断**（可选）:
   - 展开"智能字段匹配关系"分组 → 点击"检测字段关系"
   - 系统列出左表与右表检测到的潜在关系及相似度
6. **匹配与导出**（核心步骤）:
   - 展开"匹配与导出"分组
   - 选择匹配类型：**精准匹配** 或 **模糊匹配**
   - 若为模糊匹配，可调整"模糊阈值"（默认 0.7，范围 0.0~1.0）
   - 点击"开始匹配" → 结果显示在下方表格（前 200 行）
   - 点击"导出匹配结果" → 保存为 CSV 文件
7. **查看日志**: 
   - 上方"控制台日志"区显示所有操作日志
   - 点击"导出日志"保存为 CSV；点击"清空日志"清空显示

## 📁 项目结构（精简版）

```
fz_adr_match_dev/
├── fz_adr_match.py              # 主插件类与 QGIS 集成入口
├── __init__.py                  # QGIS classFactory 入口
├── metadata.txt                 # 插件元数据（名称、版本等）
├── resources.qrc                # Qt 资源配置文件
├── resources_rc.py              # 编译后的资源（图标等）
├── icons/
│   └── fz_adr_match.svg         # 插件图标
├── core/                        # 核心逻辑模块
│   ├── field_detector.py        # 字段类型检测与跨源字段关系推断
│   ├── data_loader.py           # 多格式数据加载器（CSV/Excel/SHP/GeoJSON）
│   ├── match_engine.py          # 匹配引擎（精准/模糊/多字段匹配）
│   └── __init__.py
├── ui/                          # 用户界面
│   ├── match_dialog.py          # 主对话框 UI（精简版：仅主页）
│   └── __init__.py
├── utils/                       # 工具函数
│   ├── cache.py                 # JSON 缓存读写助手
│   ├── generate_test_data.py   # 测试数据生成脚本
│   └── __init__.py
├── test_data/                   # 预生成的测试数据
│   ├── test_left.csv            # 左表示例（管网点位数据）
│   └── test_right.geojson       # 右表示例（第三方 POI 数据）
├── cache/                       # 运行时缓存目录
│   └── cleaned_left.json        # 清洗结果缓存示例
├── README.md                    # 本文件
└── .github/
    └── copilot-instructions.md  # AI 开发指导文档
```

## 🔧 核心模块 API

### `DataLoader`（多格式数据加载）
```python
from core.data_loader import DataLoader

# 自动识别格式加载
data, geom_column = DataLoader.auto_load('file.csv')  # 或 .xlsx, .shp, .geojson
# data → List[Dict]  字段统一格式
# geom_column → 若包含几何字段则返回列名，否则 None
```

### `FieldDetector`（字段类型识别与关系推断）
```python
from core.field_detector import FieldDetector

detector = FieldDetector()

# 检测字段类型（地址字段、ID 字段等）
fields = detector.detect_dataset_fields(data)
# → [{'name': 'province', 'inferred_type': 'address', 'category': 'province'}, ...]

# 跨数据源推断字段对应关系
relationships = detector.infer_field_relationships({'left': data1, 'right': data2})
# → [('left', 'province', 'right', 'prov', similarity_score), ...]
```

### `MatchEngine`（匹配引擎）
```python
from core.match_engine import MatchEngine

engine = MatchEngine(fuzzy_threshold=0.7)

# 精准匹配：字段值完全相等
exact_results = engine.exact_match(left_data, right_data, 'province', 'province')

# 模糊匹配：基于相似度（difflib.SequenceMatcher）
fuzzy_results = engine.fuzzy_match(left_data, right_data, 'address', 'address')

# 返回格式
# [{'left': {...}, 'right': {...}, 'match_type': 'exact', 'confidence': 1.0}, ...]
```

## 📊 数据流与工作流

```
加载数据（支持多格式）
    ↓
[数据清洗] → 去空格/去重/去空行（可选）
    ↓
[地址标准化] → 标准化规则映射（可选）
    ↓
[字段推断] → 检测地址字段、跨源字段关系（参考用）
    ↓
[匹配执行] → 精准匹配 或 模糊匹配（主要操作）
    ↓
[结果导出] → CSV 文件 + 日志导出
    ↓
完成
```

## 🎯 设计思路

**精简原则**：
- UI 只保留**一个主页标签**，集中所有操作流程到一个界面
- 每个操作（清洗、标准化、推断、匹配）都对应一个**可折叠的分组**，用户可按需展开
- 所有操作结果实时显示在**控制台日志**（上方）和**结果表格**（下方）
- 缓存结果存到 `cache/` 目录以便中间步骤回顾

**核心模块**：
- `core/data_loader.py` — 统一多格式输入为 `List[Dict]`
- `core/field_detector.py` — 字段自动识别与跨源关系推断
- `core/match_engine.py` — 精准/模糊匹配核心算法
- `ui/match_dialog.py` — 简洁主对话框（仅一页）

**可扩展点**：
- 地址标准化规则可通过 JSON 配置扩展
- 匹配算法可添加更多相似度度量（当前用 difflib）
- 后续可添加地图可视化、后台线程化等高级功能

## 🐛 已知问题与改进方向

- 当前清洗/匹配在主线程执行，大数据集会导致 UI 卡顿 → 可迁移到后台 QThread
- 地址标准化规则目前为硬编码 → 建议改为配置文件驱动
- 地图可视化尚未实现 → 可在 QGIS 画布添加临时内存图层显示匹配结果
- 模糊匹配算法仍为基础的 `difflib.SequenceMatcher` → 可接入更复杂的相似度度量

## 📝 开发与测试

### 快速测试
```python
# 在 Python 控制台或独立脚本中测试
from core.data_loader import DataLoader
from core.field_detector import FieldDetector
from core.match_engine import MatchEngine

data = DataLoader.auto_load('test_data/test_left.csv')[0]
print(data[:2])  # 预览数据

detector = FieldDetector()
fields = detector.detect_dataset_fields(data)
print(fields)  # 检测字段类型
```

### 在 QGIS 中调试
- 打开 QGIS Python 控制台 (Plugins → Python Console)
- 导入插件模块并测试
- 查看 QGIS 日志 (Help → Log Messages) 跟踪插件加载和运行状态

## 📄 许可证与贡献

本项目为 QGIS 社区插件。欢迎提交 Issue 和 PR。
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


