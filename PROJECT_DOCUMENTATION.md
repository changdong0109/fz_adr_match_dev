# QGIS 地址匹配插件 - 完整项目文档

> **本文档是项目的唯一权威文档，包含所有需求、架构设计、实现逻辑和开发指南。所有代码修改和架构变更都应在此文档中更新。**

---

## 📋 目录

1. [项目概述](#项目概述)
2. [需求与功能](#需求与功能)
3. [架构设计](#架构设计)
4. [代码组织指南](#代码组织指南)
5. [实现逻辑](#实现逻辑)
6. [开发规范](#开发规范)
7. [使用指南](#使用指南)
8. [开发状态](#开发状态)
9. [待办事项](#待办事项)
10. [AI开发指南](#ai开发指南)

---

## 项目概述

### 项目名称
**fz_adr_match_dev** - QGIS 地址标准化与管网匹配插件

### 项目定位
轻量化多源数据匹配工具，用于地址数据的标准化、清洗和匹配。

### 技术栈
- **平台**: QGIS 3.40+
- **语言**: Python 3.x
- **UI框架**: PyQt6 (QGIS内置)
- **数据格式**: CSV, Excel, SHP, GeoJSON

### 插件信息
- **版本**: 0.1.0
- **作者**: chang
- **类别**: Vector
- **Qt支持**: Qt6 only

---

## 需求与功能

### 核心需求

1. **多格式数据加载**
   - 支持 CSV、Excel、SHP、GeoJSON 格式
   - 自动识别文件格式和编码
   - 统一数据格式为 `List[Dict]`

2. **智能字段检测**
   - 自动识别地址字段（省、市、区、街道等）
   - 识别字段类型（address/id/numeric/date/text）
   - 跨数据源字段关系推断

3. **数据清洗**
   - 去空格、去重、去空行
   - 地址标准化（如：北京市→北京）
   - 结果缓存到 `cache/` 目录

4. **匹配功能**
   - **精准匹配**: 完全相等匹配
   - **模糊匹配**: 基于相似度的容错匹配（可配置阈值）
   - **多字段组合匹配**: 跨多个字段的联合匹配
   - **混合匹配**: 多种策略自动尝试

5. **结果导出**
   - 匹配结果导出为 CSV/Excel
   - 日志导出功能
   - 实时日志显示

### 功能特性

- ✅ 多格式数据加载（CSV/Excel/SHP/GeoJSON）
- ✅ 智能字段检测与关联推断
- ✅ 数据清洗与标准化
- ✅ 精准/模糊/组合匹配
- ✅ 结果导出与日志管理
- ✅ 实时进度显示
- ✅ 模块化架构设计

---

## 架构设计

### 整体架构原则

1. **分层架构**: UI层 → Core层 → Utils层
2. **单一职责**: 每个模块只负责一个明确的功能
3. **依赖注入**: 通过构造函数注入共享资源
4. **关注点分离**: UI与业务逻辑完全分离

### 依赖方向

```
ui/ → core/ → utils/
```

- **UI层** 可以调用 **Core层** 和 **Utils层**
- **Core层** 可以调用 **Utils层**，但不能调用 **UI层**
- **Utils层** 应该是独立的，不依赖其他层

### 目录结构

```
fz_adr_match_dev/
├── fz_adr_match.py          # QGIS插件入口（只负责插件生命周期）
├── __init__.py               # QGIS classFactory 入口
├── metadata.txt              # 插件元数据
├── resources.qrc             # Qt 资源配置文件
├── resources_rc.py           # 编译后的资源
│
├── core/                     # 核心业务逻辑层（纯业务逻辑，无UI依赖）
│   ├── __init__.py
│   ├── data_loader.py        # 数据加载（CSV/Excel/SHP等）
│   ├── field_detector.py     # 字段检测与关联推断
│   └── match_engine.py       # 匹配算法（精准/模糊/组合）
│
├── ui/                       # 用户界面层（所有UI相关代码）
│   ├── __init__.py
│   ├── match_dialog.py       # 主对话框（布局和协调，~298行）
│   ├── styles.py             # 样式管理器
│   ├── styles.qss            # 样式表（统一管理所有样式）
│   ├── utils.py              # UI工具函数（表格、布局等）
│   ├── collapsible_section.py # UI组件
│   │
│   ├── steps/                # Step Widgets（UI + 业务逻辑调用）
│   │   ├── __init__.py
│   │   ├── step1_widget.py   # Step1: 文件导入
│   │   ├── step2_widget.py   # Step2: 字段映射与清洗
│   │   ├── step3_widget.py   # Step3: 标准化解析 & 关联
│   │   ├── step4_widget.py   # Step4: 匹配任务管理
│   │   └── step5_widget.py   # Step5: 导出 & 日志
│   │
│   ├── modals/               # 模态对话框
│   │   ├── __init__.py
│   │   ├── filter_modal.py   # 过滤条件对话框
│   │   └── match_modal.py     # 字段匹配对对话框
│   │
│   └── widgets/              # 可复用UI组件
│       ├── __init__.py
│       ├── base_step_widget.py    # Step Widget基类
│       ├── task_manager.py        # UI任务管理（进度条、定时器）
│       └── global_config_widget.py
│
├── utils/                    # 通用工具层（跨模块的通用工具函数）
│   ├── __init__.py
│   ├── cache.py              # 缓存工具
│   └── generate_test_data.py # 测试数据生成
│
├── data/                     # 数据文件
│   └── regions/              # 区域数据（省市区等）
│       ├── provinces.json
│       ├── cities.json
│       ├── areas.json
│       ├── streets.json
│       └── villages.json
│
├── icons/                    # 图标资源
│   └── fz_adr_match.svg
│
└── cache/                    # 运行时缓存目录
    └── cleaned_left.json     # 清洗结果缓存示例
```

### 架构设计原则

#### 1. 单一职责原则

- **MatchDialog**: 只负责布局和协调
  - 侧边栏导航
  - 主内容区布局
  - 步骤切换逻辑
  - 样式加载（通过 StyleManager）
  - 日志统一入口
  - **代码行数**: ~298行

- **Step Widgets**: 各自负责自己的UI和业务逻辑
  - 所有 Step Widgets 继承自 `BaseStepWidget`
  - 每个 Widget 独立管理自己的 UI 和业务逻辑
  - 通过依赖注入接收共享资源（log_callback, task_manager）

- **TaskManager**: 统一管理所有任务的进度和定时器
  - 独立模块，职责单一
  - 通过依赖注入提供给 Step Widgets

- **StyleManager**: 统一管理所有样式（QSS加载）
  - 独立模块，职责单一
  - 所有样式定义在 `styles.qss` 中

#### 2. 依赖注入

**Step Widgets 构造函数**:
```python
# Step1-3, Step5
def __init__(self, parent=None, log_callback=None, task_manager=None):

# Step4 (需要模态对话框回调)
def __init__(self, parent=None, log_callback=None, task_manager=None,
             open_filter_modal=None, open_match_modal=None):
```

**共享资源注入**:
- `log_callback`: 通过构造函数注入
- `task_manager`: 通过构造函数注入
- `模态对话框回调`: Step4 通过构造函数注入

#### 3. 通信机制

- **日志通信**: 通过回调函数 `log_callback(msg, level)`
  - 所有 Step Widgets 通过 `self._log()` 方法（继承自 BaseStepWidget）记录日志
  - 日志统一由 MatchDialog 的 `_log()` 方法处理

- **任务管理**: 通过共享的 `TaskManager` 实例
  - 所有 Step Widgets 通过 `self.get_task_manager()` 获取 TaskManager
  - TaskManager 由 MatchDialog 创建并注入

- **模态对话框**: Step4 通过回调函数打开
  - Step4 通过 `open_filter_modal` 和 `open_match_modal` 回调打开模态对话框
  - 回调由 MatchDialog 提供

#### 4. 样式管理

- **样式定义**: `ui/styles.qss`（统一管理所有样式）
- **样式加载**: 通过 `StyleManager.load_qss()` 统一加载
- **样式应用**: 通过 `objectName` 和类选择器
  - 所有组件通过 `setObjectName()` 设置标识
  - QSS 通过选择器应用样式
- **无内联样式**: 所有样式都在 QSS 文件中，无 `setStyleSheet()` 调用

---

## 代码组织指南

### Core层职责

**应该放的内容**:
- ✅ 数据处理算法
- ✅ 业务规则和逻辑
- ✅ 数据转换和清洗
- ✅ 匹配算法
- ✅ 字段检测和推断

**不应该有**:
- ❌ UI组件
- ❌ Qt依赖
- ❌ 界面相关代码

**示例**:
```python
# ✅ 正确：纯业务逻辑
class MatchEngine:
    def exact_match(self, left_data, right_data, left_key, right_key):
        # 匹配算法实现
        pass

# ❌ 错误：不应该有UI依赖
class MatchEngine:
    def exact_match(self, left_data, right_data, left_key, right_key):
        from qgis.PyQt.QtWidgets import QMessageBox  # ❌ 不应该
        QMessageBox.information(...)  # ❌ 不应该
```

### UI层职责

**应该放的内容**:
- ✅ Qt Widget组件
- ✅ UI布局和样式
- ✅ 用户交互处理
- ✅ 调用core层的业务逻辑
- ✅ UI工具函数（表格操作、布局辅助等）

**不应该有**:
- ❌ 纯业务算法
- ❌ 数据处理逻辑（应调用core层）

**示例**:
```python
# ✅ 正确：UI层调用业务层
class Step2Widget(BaseStepWidget):
    def _on_clean_clicked(self):
        from core.data_loader import DataLoader  # ✅ 调用core层
        data = DataLoader.load_csv(self.file_path)
        # 处理UI更新
        self._update_progress(50)

# ❌ 错误：不应该在UI层实现业务逻辑
class Step2Widget(BaseStepWidget):
    def _on_clean_clicked(self):
        # ❌ 不应该在这里实现数据清洗算法
        import csv
        with open(self.file_path) as f:
            # 数据处理逻辑应该放在core层
            pass
```

### Utils层职责

**应该放的内容**:
- ✅ 通用工具函数（文件操作、字符串处理等）
- ✅ 缓存管理
- ✅ 测试辅助工具

**不应该有**:
- ❌ UI组件
- ❌ 业务逻辑
- ❌ Qt依赖

### 代码放置检查清单

#### ✅ 应该放在 core/ 的代码
- [x] 数据加载逻辑（CSV/Excel/SHP解析）
- [x] 数据清洗算法
- [x] 字段检测和推断算法
- [x] 匹配算法（精准/模糊/组合）
- [x] 地址标准化算法
- [x] 业务规则验证

#### ✅ 应该放在 ui/ 的代码
- [x] Qt Widget组件
- [x] UI布局代码
- [x] 事件处理（按钮点击、输入变化等）
- [x] 进度条更新
- [x] 表格操作（选择、编辑等UI操作）
- [x] 样式定义（QSS）
- [x] 模态对话框

#### ✅ 应该放在 ui/utils.py 的代码
- [x] 表格辅助函数（列宽调整、选择操作等）
- [x] Qt组件操作辅助函数
- [x] UI相关的工具函数

#### ✅ 应该放在 utils/ 的代码
- [x] 文件操作工具
- [x] 缓存管理
- [x] 通用字符串/数据处理
- [x] 测试数据生成

### 新增功能时的判断流程

```
1. 这个功能需要UI吗？
   ├─ 是 → 放在 ui/
   └─ 否 → 继续判断

2. 这个功能是业务逻辑吗？
   ├─ 是 → 放在 core/
   └─ 否 → 继续判断

3. 这个功能是通用工具吗？
   ├─ 是 → 放在 utils/
   └─ 否 → 重新考虑设计
```

---

## 实现逻辑

### 数据流与工作流

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

### 核心模块实现

#### 1. DataLoader（数据加载器）

**位置**: `core/data_loader.py`

**功能**:
- 自动识别文件格式（CSV/Excel/SHP/GeoJSON）
- 统一数据格式为 `List[Dict]`
- 处理编码问题（自动检测）

**API**:
```python
from core.data_loader import DataLoader

# 自动识别格式加载
data, geom_column = DataLoader.auto_load('file.csv')
# data → List[Dict]  字段统一格式
# geom_column → 若包含几何字段则返回列名，否则 None
```

#### 2. FieldDetector（字段检测器）

**位置**: `core/field_detector.py`

**功能**:
- 自动识别字段类型（address/id/numeric/date/text）
- 识别地址子字段（province/city/district/street/building）
- 计算跨数据源字段的相似度并推断关联

**API**:
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

#### 3. MatchEngine（匹配引擎）

**位置**: `core/match_engine.py`

**功能**:
- 精准匹配：字段值完全相等
- 模糊匹配：基于相似度（difflib.SequenceMatcher）
- 多字段组合匹配：跨多个字段的联合匹配
- 混合匹配：多种策略自动尝试

**API**:
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

#### 4. MatchDialog（主对话框）

**位置**: `ui/match_dialog.py`

**职责**:
- 只负责布局和协调
- 侧边栏导航
- 主内容区布局
- 步骤切换逻辑
- 样式加载（通过 StyleManager）
- 日志统一入口

**代码行数**: ~298行

#### 5. Step Widgets

**位置**: `ui/steps/stepX_widget.py`

**职责**:
- 各自负责自己的UI和业务逻辑
- 通过依赖注入接收共享资源
- 调用core层完成业务逻辑

**实现**:
- 所有 Step Widgets 继承自 `BaseStepWidget`
- 通过 `self._log()` 记录日志
- 通过 `self.get_task_manager()` 获取任务管理器

---

## 开发规范

### QGIS插件开发规范

#### 1. 必需文件
- [x] `metadata.txt` - 存在且格式正确
- [x] `__init__.py` - 存在且有 `classFactory(iface)` 函数
- [x] 主插件类文件 - `fz_adr_match.py` 存在

#### 2. 插件类接口
- [x] `__init__(self, iface)` - 构造函数
- [x] `initGui(self)` - 初始化GUI
- [x] `unload(self)` - 卸载插件
- [x] `run(self)` - 运行主功能

#### 3. Qt 导入规范
- [x] 所有 Qt 导入使用 `qgis.PyQt.*` 前缀
  - ✅ `from qgis.PyQt.QtWidgets import ...`
  - ✅ `from qgis.PyQt.QtCore import ...`
  - ✅ `from qgis.PyQt.QtGui import ...`

#### 4. 路径处理规范
- [x] 使用 `os.path.join()` 构建路径
- [x] 使用 `os.path.dirname(__file__)` 获取插件目录
- [x] 使用相对路径访问资源文件
- [x] 没有硬编码的绝对路径

#### 5. 模块导入规范
- [x] UI 模块使用相对导入（`from .steps import ...`）
- [x] 子模块使用相对导入（`from ..utils import ...`）
- [x] 没有循环导入

### 代码质量规范

#### 命名规范
- **类名**: PascalCase ✅
- **方法名**: snake_case ✅
- **私有方法**: `_method_name` ✅

#### 导入规范
- 使用相对导入 ✅
- 导入顺序：标准库 → 第三方库 → 本地模块 ✅

#### 文档字符串
- 所有类和方法都有文档字符串 ✅
- 类型提示完整 ✅

#### 错误处理
- 使用 try-except 捕获异常 ✅
- 提供用户友好的错误消息 ✅
- 记录错误日志 ✅

### 代码审查检查点
- [ ] core/ 中是否有 `from qgis.PyQt` 导入？
- [ ] ui/ 中是否有复杂的数据处理算法？
- [ ] utils/ 中是否有UI或业务逻辑依赖？
- [ ] 各层之间的依赖方向是否正确？

---

## 使用指南

### 快速开始

#### 1. 安装插件

1. 将本目录复制到 QGIS 插件目录：
   ```
   %APPDATA%\QGIS\QGIS3\profiles\default\python\plugins\fz_adr_match_dev
   ```

2. 重启 QGIS，在 **Plugins → Manage and Install Plugins** 中启用 `fz_adr_match_dev`

#### 2. 使用工作流

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

### 高级用法

#### 自定义字段识别规则

编辑 `core/field_detector.py` 中的 `ADDRESS_FIELD_PATTERNS`：
```python
ADDRESS_FIELD_PATTERNS = {
    'province': ['省', 'province', '...'],
    'city': ['市', 'city', '...'],
    # 添加更多规则...
}
```

#### 调整模糊匹配阈值

在匹配配置中修改 **模糊匹配相似度阈值**（0.0-1.0）：
- 0.5: 容错度高（可能误匹配）
- 0.7: 平衡（推荐）
- 0.9: 严格（容错度低）

#### 添加新的数据格式支持

在 `core/data_loader.py` 中添加 `load_xxx()` 方法：
```python
@staticmethod
def load_xxx(file_path: str) -> List[Dict]:
    # 实现新格式加载逻辑
    pass
```

### 常见问题

**Q1: 加载大文件时很慢**
- 考虑使用分块加载（批处理）
- 对超大表使用分片匹配
- 为频繁查询的字段建立索引

**Q2: 模糊匹配精度不高**
- 调高相似度阈值（0.8+）
- 检查字段名是否正确
- 尝试多字段组合匹配而非单字段

**Q3: 如何处理特殊字符（如繁体字）**
- 预处理数据：规范化字符集（简繁转换）
- 在 `MatchEngine._similarity_score()` 中实现预处理

**Q4: 能否保存/加载匹配配置？**
- 当前版本不支持配置保存
- 可扩展：在 `MatchDialog` 中添加 `save_config()` / `load_config()` 方法

---

## 开发状态

### ✅ 已完成的工作

#### 1. 基础架构 ✅
- [x] `ui/widgets/task_manager.py` - 任务管理器（75行）
- [x] `ui/widgets/base_step_widget.py` - Step Widget基类（37行）
- [x] `ui/utils.py` - 工具函数（66行，含向后兼容）
- [x] `ui/modals/filter_modal.py` - 过滤条件对话框（100行）
- [x] `ui/modals/match_modal.py` - 字段匹配对对话框（97行）

#### 2. Step Widget ✅
- [x] `ui/steps/step1_widget.py` - Step1完整实现（417行）
- [x] `ui/steps/step2_widget.py` - Step2字段映射与清洗（413行）
- [x] `ui/steps/step3_widget.py` - Step3标准化解析与关联（226行）
- [x] `ui/steps/step4_widget.py` - Step4匹配任务管理（401行）
- [x] `ui/steps/step5_widget.py` - Step5导出与日志（126行）

#### 3. 主对话框重构 ✅
- [x] `ui/match_dialog.py` - 已重构为精简版本（~298行）
- [x] 移除了所有Step相关代码，改为使用Widget
- [x] 移除了所有内联样式，改为通过 StyleManager 统一加载 QSS
- [x] 保留了：侧边栏、主内容区布局、步骤切换、样式加载、日志统一入口

#### 4. 模块化结构 ✅
- [x] 所有 `__init__.py` 文件已创建
- [x] 导入路径已更新
- [x] 临时文件已清理

#### 5. Core层实现 ✅
- [x] `core/data_loader.py` - 数据加载（CSV/Excel/SHP等）
- [x] `core/field_detector.py` - 字段检测与关联推断
- [x] `core/match_engine.py` - 匹配算法（精准/模糊/组合）

#### 6. 样式管理 ✅
- [x] `ui/styles.qss` - 统一管理所有样式
- [x] `ui/styles.py` - 样式管理器
- [x] 所有样式通过 StyleManager 统一加载
- [x] 无内联样式（`setStyleSheet()` 调用）

### 代码行数统计

#### 重构前
- `match_dialog.py` - **2217行**（单一文件，所有逻辑集中）

#### 重构后
- `match_dialog.py` - **~298行**（只负责布局和协调）
- `step1_widget.py` - **417行**
- `step2_widget.py` - **413行**
- `step3_widget.py` - **226行**
- `step4_widget.py` - **401行**
- `step5_widget.py` - **126行**
- `task_manager.py` - **75行**
- `base_step_widget.py` - **37行**
- `filter_modal.py` - **100行**
- `match_modal.py` - **97行**
- `utils.py` - **66行**

**总计**: 约2371行（比原来增加154行，但结构清晰、可维护性大幅提升）

### 架构遵循情况

✅ **架构遵循情况良好**
- 所有模块遵循单一职责原则
- 依赖注入正确实现
- 通信机制清晰
- 样式管理统一
- 文档与实际代码一致

代码结构清晰，易于维护和扩展。

---

## 待办事项

### 功能改进

- [ ] **后台线程化**: 将清洗/匹配操作迁移到后台 QThread，避免UI卡顿
- [ ] **配置保存/加载**: 添加匹配配置的保存和加载功能
- [ ] **地图可视化**: 在 QGIS 画布添加临时内存图层显示匹配结果
- [ ] **高级匹配算法**: 接入更复杂的相似度度量（当前为基础 difflib）
- [ ] **地址标准化规则配置化**: 将硬编码的标准化规则改为配置文件驱动

### 代码质量

- [ ] **单元测试**: 添加单元测试覆盖核心功能
- [ ] **错误处理**: 加强异常处理和错误提示
- [ ] **日志级别**: 更细化日志级别使用
- [ ] **性能优化**: 对大数据集进行性能优化

### 文档完善

- [ ] **API文档**: 生成完整的API文档
- [ ] **示例代码**: 添加更多使用示例
- [ ] **视频教程**: 制作使用视频教程

### 扩展功能

- [ ] **Processing Provider**: 添加 QGIS Processing Provider，使功能能通过模型/批处理调用
- [ ] **国际化**: 添加多语言支持（i18n）
- [ ] **插件配置**: 添加插件配置界面
- [ ] **批量处理**: 支持批量处理多个文件

---

## 更新日志

### 2024-XX-XX - 文档整合
- 将所有文档整合为单一文档 `PROJECT_DOCUMENTATION.md`
- 删除冗余文档文件
- 建立统一的文档维护机制

---

## 附录

### 文件结构总览

```
fz_adr_match_dev/
├── fz_adr_match.py              # 主插件类与 QGIS 集成入口
├── __init__.py                  # QGIS classFactory 入口
├── metadata.txt                 # 插件元数据（名称、版本等）
├── resources.qrc                # Qt 资源配置文件
├── resources_rc.py              # 编译后的资源（图标等）
├── PROJECT_DOCUMENTATION.md     # 本文档（唯一权威文档）
│
├── core/                        # 核心逻辑模块
│   ├── __init__.py
│   ├── field_detector.py        # 字段类型检测与跨源字段关系推断
│   ├── data_loader.py           # 多格式数据加载器（CSV/Excel/SHP/GeoJSON）
│   └── match_engine.py          # 匹配引擎（精准/模糊/多字段匹配）
│
├── ui/                          # 用户界面
│   ├── __init__.py
│   ├── match_dialog.py          # 主对话框 UI（精简版：仅主页）
│   ├── styles.py                # 样式管理器
│   ├── styles.qss               # 样式表（统一管理所有样式）
│   ├── utils.py                 # UI工具函数
│   ├── collapsible_section.py   # 可折叠组件
│   │
│   ├── steps/                   # Step组件模块
│   │   ├── __init__.py
│   │   ├── step1_widget.py      # Step1: 文件导入
│   │   ├── step2_widget.py      # Step2: 字段映射与清洗
│   │   ├── step3_widget.py      # Step3: 标准化解析 & 关联
│   │   ├── step4_widget.py      # Step4: 匹配任务管理
│   │   └── step5_widget.py      # Step5: 导出 & 日志
│   │
│   ├── modals/                  # 模态对话框模块
│   │   ├── __init__.py
│   │   ├── filter_modal.py      # 过滤条件对话框
│   │   └── match_modal.py        # 字段匹配对对话框
│   │
│   └── widgets/                 # 可复用组件模块
│       ├── __init__.py
│       ├── base_step_widget.py  # 基础Step Widget类
│       ├── task_manager.py      # 任务管理器
│       └── global_config_widget.py
│
├── utils/                       # 工具函数
│   ├── __init__.py
│   ├── cache.py                 # JSON 缓存读写助手
│   └── generate_test_data.py    # 测试数据生成脚本
│
├── data/                        # 数据文件
│   └── regions/                 # 区域数据（省市区等）
│       ├── provinces.json
│       ├── cities.json
│       ├── areas.json
│       ├── streets.json
│       └── villages.json
│
├── icons/                       # 图标资源
│   └── fz_adr_match.svg
│
└── cache/                       # 运行时缓存目录
    └── cleaned_left.json        # 清洗结果缓存示例
```

---

## AI开发指南

### 概述

本文档是项目的唯一权威文档。所有AI助手在开发代码时，必须：
1. **严格遵循本文档**中的架构设计、代码组织指南和开发规范
2. **在实现新需求时**，同步更新本文档的相关部分
3. **在修改代码前**，先查阅本文档了解代码应该放在哪里

### 📚 相关文档

- **[AI_QUICK_REFERENCE.md](AI_QUICK_REFERENCE.md)** - 最常用的提示词，一键复制使用
- **[AI_PROMPT_TEMPLATE.md](AI_PROMPT_TEMPLATE.md)** - 完整提示词模板库
- **[AI_PROMPT_EXAMPLES.md](AI_PROMPT_EXAMPLES.md)** - 实际使用示例和技巧

**快速开始**：直接使用 [AI_QUICK_REFERENCE.md](AI_QUICK_REFERENCE.md) 中的提示词模板！

### 标准提示词模板

> **💡 快速使用**：如果你需要快速复制提示词，请直接使用 [AI_QUICK_REFERENCE.md](AI_QUICK_REFERENCE.md) 中的模板！

当你需要AI助手开发代码时，使用以下提示词模板：

```
请按照 PROJECT_DOCUMENTATION.md 中的要求开发代码。

【任务描述】
[在这里描述你的具体需求]

【要求】
1. 严格遵循文档中的架构设计原则：
   - 分层架构：UI层 → Core层 → Utils层
   - 单一职责：每个模块只负责一个明确的功能
   - 依赖注入：通过构造函数注入共享资源
   - 关注点分离：UI与业务逻辑完全分离

2. 代码放置规则：
   - UI相关代码 → ui/ 目录
   - 业务逻辑代码 → core/ 目录
   - 通用工具代码 → utils/ 目录
   - 具体放置位置请参考文档中的"代码组织指南"部分

3. 开发规范：
   - 遵循QGIS插件开发规范（见文档"开发规范"部分）
   - 使用相对导入
   - 所有Qt导入使用 qgis.PyQt.* 前缀
   - 使用 os.path.join() 构建路径

4. 文档更新：
   - 如果这是新功能，请在文档的"需求与功能"部分添加
   - 如果修改了架构，请在"架构设计"部分更新
   - 如果新增了模块，请在"实现逻辑"部分添加API说明
   - 在"开发状态"中记录完成的工作
   - 在"更新日志"中记录本次变更

5. 代码审查：
   - 确保core/中没有UI依赖
   - 确保ui/中没有复杂的数据处理算法
   - 确保各层之间的依赖方向正确

请先阅读 PROJECT_DOCUMENTATION.md，然后开始开发。
```

### 简化版提示词（快速使用）

如果任务比较简单，可以使用简化版：

```
按照 PROJECT_DOCUMENTATION.md 的要求实现：[你的需求]

要求：
1. 遵循文档中的架构设计和代码组织规则
2. 代码放在正确的位置（参考"代码组织指南"）
3. 完成后更新文档相关部分
```

### 文档更新流程

当AI助手实现新功能或修改代码时，必须按以下流程更新文档：

#### 1. 新功能开发

**步骤**：
1. 在 `PROJECT_DOCUMENTATION.md` 的"需求与功能"部分添加新功能描述
2. 如果涉及架构变更，在"架构设计"部分更新
3. 在"实现逻辑"部分添加新模块的API说明
4. 开发代码
5. 在"开发状态"中记录完成的工作
6. 在"更新日志"中记录本次变更

**示例**：
```
【任务】添加数据验证功能

AI应该：
1. 在"需求与功能" → "核心需求"中添加：
   - 数据验证：验证数据格式、必填字段等

2. 在"实现逻辑" → "核心模块实现"中添加：
   - 6. DataValidator（数据验证器）
     位置: core/data_validator.py
     功能: 验证数据格式、必填字段等
     API: [代码示例]

3. 开发代码：core/data_validator.py

4. 在"开发状态" → "已完成的工作"中添加：
   - [x] core/data_validator.py - 数据验证器

5. 在"更新日志"中添加：
   - 2024-XX-XX - 添加数据验证功能
```

#### 2. 代码重构

**步骤**：
1. 在"架构设计"或"代码组织指南"中说明重构原因和目标
2. 执行重构
3. 在"开发状态"中记录重构完成
4. 在"更新日志"中记录

#### 3. Bug修复

**步骤**：
1. 修复代码
2. 在"更新日志"中记录修复内容

### 文档更新检查清单

AI助手在完成代码开发后，必须检查：

- [ ] 新功能是否在"需求与功能"部分描述？
- [ ] 新模块是否在"实现逻辑"部分有API说明？
- [ ] 架构变更是否在"架构设计"部分更新？
- [ ] 代码是否放在正确的位置（参考"代码组织指南"）？
- [ ] "开发状态"是否记录了完成的工作？
- [ ] "更新日志"是否记录了本次变更？
- [ ] 代码是否符合文档中的开发规范？

### 常见场景示例

#### 场景1：添加新的匹配算法

**提示词**：
```
按照 PROJECT_DOCUMENTATION.md 的要求，添加基于拼音的匹配算法。

要求：
1. 在 core/match_engine.py 中添加 phonetic_match() 方法
2. 遵循文档中的架构设计（core层不能有UI依赖）
3. 在文档的"实现逻辑" → "MatchEngine"部分添加API说明
4. 在"需求与功能"中添加新功能描述
5. 更新"开发状态"和"更新日志"
```

#### 场景2：添加新的UI组件

**提示词**：
```
按照 PROJECT_DOCUMENTATION.md 的要求，在Step2中添加数据预览表格。

要求：
1. 在 ui/steps/step2_widget.py 中添加表格组件
2. 遵循文档中的UI层职责（调用core层完成业务逻辑）
3. 使用文档中规定的样式管理方式（styles.qss）
4. 在文档的"实现逻辑" → "Step Widgets"部分说明
5. 更新"开发状态"
```

#### 场景3：重构代码

**提示词**：
```
按照 PROJECT_DOCUMENTATION.md 的要求，将Step3中的数据处理逻辑提取到core层。

要求：
1. 先阅读文档了解代码应该放在哪里
2. 将业务逻辑移到 core/ 目录
3. Step3只保留UI相关代码，调用core层
4. 在文档的"架构设计"部分说明重构原因
5. 更新"开发状态"和"更新日志"
```

### 文档阅读优先级

AI助手在开发前，应按以下优先级阅读文档：

1. **必须阅读**：
   - "架构设计" → 了解整体架构和依赖方向
   - "代码组织指南" → 了解代码应该放在哪里
   - "开发规范" → 了解编码规范

2. **根据任务阅读**：
   - 开发新功能 → "需求与功能"、"实现逻辑"
   - 修改UI → "架构设计" → "UI层职责"
   - 修改业务逻辑 → "架构设计" → "Core层职责"
   - 添加工具函数 → "架构设计" → "Utils层职责"

3. **参考阅读**：
   - "使用指南" → 了解功能如何使用
   - "开发状态" → 了解已完成的工作

### 注意事项

1. **文档是唯一权威**：所有架构决策、代码组织规则都在文档中，不要自行决定
2. **先读后写**：开发前必须先阅读相关文档部分
3. **同步更新**：代码变更必须同步更新文档
4. **保持一致性**：文档与实际代码必须保持一致

### 快速参考

**代码应该放在哪里？**
- UI组件 → `ui/`
- 业务逻辑 → `core/`
- 工具函数 → `utils/` 或 `ui/utils.py`（UI相关）

**如何判断？**
参考文档"代码组织指南" → "新增功能时的判断流程"

**如何更新文档？**
参考文档"文档更新流程"部分

---

**文档维护说明**: 
- 本文档是项目的唯一权威文档
- 所有代码修改和架构变更都应在此文档中更新
- 删除其他冗余文档，保持文档单一性
- 每次重要变更后更新"更新日志"部分

