# QGIS 地址匹配插件 - 完整项目文档

> **本文档是项目的唯一权威文档，包含所有需求、架构设计、实现逻辑和开发指南。所有代码修改和架构变更都应在此文档中更新。**

---

## ⚠️ AI开发前必读（强制）

**所有AI助手在开发代码前，必须先阅读本节！**

### 快速提醒

**⚠️ 核心原则：全局思维，系统性设计，不要堆砌功能！**

1. **必须先进行全局思维分析**：理解整体架构、识别根本问题、设计系统性解决方案
2. **必须先阅读文档**：查看"AI开发指南" → "强制工作流程" → "第零步：全局思维分析"
3. **必须完成检查清单**：查看 [AI_DEVELOPMENT_CHECKLIST.md](AI_DEVELOPMENT_CHECKLIST.md)
4. **必须更新文档**：代码变更后同步更新文档
5. **必须代码审查**：使用检查清单验证代码

**详细流程和检查清单请查看"AI开发指南"部分，或直接查看 [AI_DEVELOPMENT_CHECKLIST.md](AI_DEVELOPMENT_CHECKLIST.md)**

---

## 📋 目录

1. [项目概述](#项目概述)
2. [需求与功能](#需求与功能)
3. [架构设计](#架构设计)
4. [缓存与状态管理](#缓存与状态管理)
5. [代码组织指南](#代码组织指南)
6. [实现逻辑](#实现逻辑)
7. [公共组件设计](#公共组件设计)
8. [开发规范](#开发规范)
9. [使用指南](#使用指南)
10. [开发状态](#开发状态)
11. [待办事项](#待办事项)
12. [AI开发指南](#ai开发指南)

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

6. **全局配置管理**
   - **区域配置**: 省/市/县（县为可选）全局配置，所有5个步骤同步使用
   - **根目录选择**: 用户自由选择数据根目录
   - **自动目录生成**: 根据省市县自动创建三个子文件夹：
     - `xx省xx市xx县客户数据` - 客户数据目录
     - `xx省xx市xx县shp数据` - SHP数据目录
     - `xx省xx市xx县cache数据` - 缓存数据目录
   - **数据保存规则**: 相应数据自动保存到对应的文件夹下
   - **全局同步**: 全局配置修改后，所有步骤都能获取最新的区域和目录信息

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

### 整体架构概述

本项目采用**分层架构**设计，遵循**单一职责**、**依赖注入**、**关注点分离**等核心原则。

**架构层次**:
```
┌─────────────────────────────────────────┐
│          UI层 (ui/)                     │
│  - 用户界面组件                          │
│  - 用户交互处理                         │
│  - 调用Core层业务逻辑                    │
└──────────────┬──────────────────────────┘
               │ 依赖
               ▼
┌─────────────────────────────────────────┐
│        Core层 (core/)                    │
│  - 业务逻辑算法                          │
│  - 数据处理                              │
│  - 无UI依赖                              │
└──────────────┬──────────────────────────┘
               │ 依赖
               ▼
┌─────────────────────────────────────────┐
│       Utils层 (utils/)                   │
│  - 通用工具函数                          │
│  - 独立模块                              │
└─────────────────────────────────────────┘
```

**依赖规则**:
- ✅ **UI层** → **Core层** → **Utils层**（单向依赖）
- ❌ **Core层** 不能依赖 **UI层**
- ❌ **Utils层** 不能依赖其他层

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
│       ├── global_config_widget.py # 全局配置组件
│       └── result_dialog.py       # 通用结果弹窗组件
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
└── cache/                    # 项目数据缓存目录（运行时数据）
    └── cleaned_left.json     # 清洗结果缓存示例
    # 注意：历史配置保存在 QGIS QSettings 中，不在此目录
```

### 核心设计原则

#### 1. 单一职责原则

每个模块只负责一个明确的功能，职责清晰，边界明确。

**模块职责划分**:
- **MatchDialog** (`ui/match_dialog.py`): 只负责布局和协调
  - 侧边栏导航、主内容区布局、步骤切换逻辑
  - 样式加载（通过 StyleManager）、日志统一入口
  - **不负责**: 具体业务逻辑、数据处理
  
- **Step Widgets** (`ui/steps/step*_widget.py`): 各自负责自己的UI和业务逻辑调用
  - 所有 Step Widgets 继承自 `BaseStepWidget`
  - 每个 Widget 独立管理自己的 UI 和业务逻辑调用
  - 通过依赖注入接收共享资源（log_callback, task_manager）
  - **不负责**: 具体业务算法实现（应调用Core层）
  
- **Core层模块** (`core/*.py`): 纯业务逻辑，无UI依赖
  - `DataLoader`: 数据加载和转换
  - `FieldDetector`: 字段检测和推断
  - `MatchEngine`: 匹配算法
  - **不负责**: UI组件、用户交互
  
- **TaskManager** (`ui/widgets/task_manager.py`): 统一管理所有任务的进度和定时器
  - 独立模块，职责单一
  - 通过依赖注入提供给 Step Widgets

- **ResultDialog** (`ui/widgets/result_dialog.py`): 通用结果弹窗组件
  - 统一的弹窗样式，支持成功/失败/警告/信息四种类型
  - 避免各处重复定义弹窗样式
  - 样式通过 QSS 统一管理
  
- **StyleManager** (`ui/styles.py`): 统一管理所有样式（QSS加载）
  - 独立模块，职责单一
  - 所有样式定义在 `styles.qss` 中

#### 2. 依赖注入

通过构造函数注入共享资源，避免全局变量和紧耦合。

**实现方式**:
```python
# Step Widgets 构造函数签名
# Step1-3, Step5
def __init__(self, parent=None, log_callback=None, task_manager=None):

# Step4 (需要模态对话框回调)
def __init__(self, parent=None, log_callback=None, task_manager=None,
             open_filter_modal=None, open_match_modal=None):
```

**注入的资源**:
- `log_callback`: 日志回调函数，统一由 MatchDialog 提供
- `task_manager`: 任务管理器实例，统一由 MatchDialog 创建
- `模态对话框回调`: Step4 专用，由 MatchDialog 提供

**优势**:
- 解耦：Step Widgets 不直接依赖 MatchDialog
- 可测试：可以轻松注入 mock 对象进行测试
- 可扩展：新增共享资源只需修改构造函数签名

#### 3. 通信机制

模块间通过明确的接口进行通信，避免隐式依赖。

**日志通信**:
- 接口：`log_callback(msg: str, level: str)`
- 实现：所有 Step Widgets 通过 `self._log()` 方法（继承自 BaseStepWidget）记录日志
- 处理：日志统一由 MatchDialog 的 `_log()` 方法处理并显示

**任务管理**:
- 接口：`TaskManager` 类提供 `start_task()`, `pause_task()`, `stop_task()` 等方法
- 实现：所有 Step Widgets 通过 `self.get_task_manager()` 获取 TaskManager
- 管理：TaskManager 由 MatchDialog 创建并注入

**数据共享**:
- Step Widgets 之间通过父对话框（MatchDialog）共享数据
- 例如：Step2 通过 `get_step1_data_sources()` 获取 Step1 的数据源

#### 4. 样式管理

所有样式统一在 QSS 文件中管理，通过 `objectName` 应用，禁止内联样式。

**设计原则**:
- **统一管理**: 所有样式定义在 `ui/styles.qss` 中
- **自动加载**: 通过 `StyleManager.load_qss()` 统一加载
- **标识应用**: 通过 `objectName` 和类选择器应用样式
- **禁止内联**: 所有样式都在 QSS 文件中，禁止使用 `setStyleSheet()`

**实现方式**:

1. **代码中设置 objectName**:
```python
btn = QPushButton("新增组合")
btn.setObjectName("step2_btn_add_combo")  # ✅ 设置 objectName
```

2. **QSS 文件中定义样式**:
```css
/* styles.qss */
QPushButton#step2_btn_add_combo {
    padding: 4px 8px;
    font-size: 12px;
    background-color: #2563eb;
    color: white;
    border: none;
    border-radius: 3px;
}
QPushButton#step2_btn_add_combo:hover {
    background-color: #1d4ed8;
}
```

3. **样式自动加载和应用**:
- `MatchDialog.__init__()` 中调用 `self._apply_styles()`
- `_apply_styles()` 调用 `StyleManager.load_qss()` 加载 QSS 文件
- 通过 `self.setStyleSheet(qss)` 应用到整个对话框
- 所有设置了 `objectName` 的组件自动应用对应样式

**样式命名规范**:
- 使用 `step{数字}_` 前缀标识步骤（如 `step2_`）
- 使用组件类型前缀：`btn_`（按钮）、`label_`（标签）、`table_`（表格）
- 使用下划线分隔单词，全小写（如 `step2_btn_add_combo`）

**❌ 禁止的做法**:
```python
# ❌ 错误：使用内联样式
btn.setStyleSheet("padding: 4px 8px; background-color: #2563eb;")
```

### 各层职责与实现规范

基于分层架构原则，各层有明确的职责边界和实现规范。

#### Core层职责 (`core/`)

**职责**: 纯业务逻辑，无UI依赖

**应该实现**:
- ✅ 数据处理算法（数据加载、转换、清洗）
- ✅ 业务规则和逻辑（匹配算法、字段检测）
- ✅ 数据转换和清洗
- ✅ 匹配算法（精准/模糊/组合）
- ✅ 字段检测和推断

**禁止实现**:
- ❌ UI组件
- ❌ Qt依赖
- ❌ 界面相关代码

**实现示例**:
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

#### UI层职责 (`ui/`)

**职责**: 用户界面和交互，调用Core层业务逻辑

**应该实现**:
- ✅ Qt Widget组件
- ✅ UI布局和样式（通过 objectName + QSS）
- ✅ 用户交互处理
- ✅ 调用Core层业务逻辑
- ✅ UI工具函数（表格操作、布局辅助等）

**禁止实现**:
- ❌ 纯业务算法
- ❌ 数据处理逻辑（应调用Core层）
- ❌ 内联样式（`setStyleSheet()` 调用）

**实现示例**:
```python
# ✅ 正确：UI层调用Core层
class Step2Widget(BaseStepWidget):
    def _on_clean_clicked(self):
        from core.data_loader import DataLoader  # ✅ 调用Core层
        data = DataLoader.load_csv(self.file_path)
        # 处理UI更新
        self._update_progress(50)
    
    def _build_ui(self):
        # ✅ 正确：设置 objectName，样式在 QSS 中定义
        btn = QPushButton("执行清洗")
        btn.setObjectName("step2_btn_clean")
        btn.clicked.connect(self._on_clean_clicked)

# ❌ 错误：不应该在UI层实现业务逻辑，不应该使用内联样式
class Step2Widget(BaseStepWidget):
    def _on_clean_clicked(self):
        # ❌ 不应该在这里实现数据清洗算法
        import csv
        with open(self.file_path) as f:
            # 数据处理逻辑应该放在Core层
            pass
    
    def _build_ui(self):
        # ❌ 错误：不应该使用内联样式
        btn = QPushButton("执行清洗")
        btn.setStyleSheet("padding: 6px 12px;")  # ❌ 应该使用 objectName + QSS
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

## 缓存与状态管理

> ⚠️ **重要**：本章节定义了项目的缓存架构设计，是Step1-5开发的唯一参考标准。
> 所有缓存相关的开发必须遵循本设计。

### Step 1-5 数据流转全景

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              全局配置 (GlobalConfig)                         │
│  省/市/县 + 基目录 → 自动生成文件夹 → 所有Step共享                            │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
     ┌────────────────────────────────┼────────────────────────────────┐
     ▼                                ▼                                ▼
┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐
│  Step1   │  │  Step2   │  │  Step3   │  │  Step4   │  │  Step5   │
│ 文件导入 │─▶│ 字段清洗 │─▶│ 标准化   │─▶│ 匹配任务 │─▶│ 导出日志 │
├──────────┤  ├──────────┤  ├──────────┤  ├──────────┤  ├──────────┤
│ 输入:    │  │ 输入:    │  │ 输入:    │  │ 输入:    │  │ 输入:    │
│ CSV/SHP  │  │ Step1数据│  │ 清洗后CSV│  │ 标准化数据│  │ 匹配结果 │
├──────────┤  ├──────────┤  ├──────────┤  ├──────────┤  ├──────────┤
│ 输出:    │  │ 输出:    │  │ 输出:    │  │ 输出:    │  │ 输出:    │
│ 统一CSV  │  │ 清洗CSV  │  │ 解析结果 │  │ 匹配结果 │  │ 导出文件 │
├──────────┤  ├──────────┤  ├──────────┤  ├──────────┤  ├──────────┤
│ 状态:    │  │ 状态:    │  │ 状态:    │  │ 状态:    │  │ 状态:    │
│ 已导入   │  │ 已配置   │  │ 已解析   │  │ 已匹配   │  │ 已导出   │
│          │  │ 已清洗   │  │          │  │          │  │          │
└──────────┘  └──────────┘  └──────────┘  └──────────┘  └──────────┘
     │              │              │              │              │
     └──────────────┴──────────────┴──────────────┴──────────────┘
                                   │
                                   ▼
                    ┌─────────────────────────────┐
                    │   项目缓存 (cache数据/)      │
                    │   统一持久化所有Step状态     │
                    └─────────────────────────────┘
```

### 缓存层次

| 层次 | 存储位置 | 内容 | 生命周期 |
|------|----------|------|----------|
| **QSettings** | QGIS注册表 | 上次使用的省市县、基目录 | 跨会话持久 |
| **项目缓存** | `{省}{市}cache数据/` | 各Step状态和配置 | 项目级持久 |
| **内存** | Step Widgets | 运行时UI状态 | 会话级 |

### 项目文件夹结构（完整版）

```
用户选择的基目录/
│
├── {省}{市}{县}客户数据/              # Step1: 导入的客户CSV
│   └── *.csv
│
├── {省}{市}{县}shp数据/               # Step1: SHP转换后的CSV
│   └── *.csv
│
├── {省}{市}{县}_客户数据清洗/         # Step2: 清洗输出（客户类型）
│   ├── 清洗后数据/*.csv
│   └── 异常数据/*.csv
│
├── {省}{市}{县}_GIS数据清洗/          # Step2: 清洗输出（GIS类型）
│   ├── 清洗后数据/*.csv
│   └── 异常数据/*.csv
│
├── {省}{市}{县}_标准化结果/           # Step3: 标准化解析输出
│   └── *.csv
│
├── {省}{市}{县}_匹配结果/             # Step4: 匹配输出
│   └── *.csv
│
├── {省}{市}{县}_导出/                 # Step5: 最终导出
│   ├── 匹配报告/*.xlsx
│   └── 日志/*.log
│
└── {省}{市}{县}cache数据/             # 项目级缓存（核心）
    │
    ├── region_cache.json             # 区域配置
    │
    ├── file_status.json              # Step1/2: 文件状态（cleaned + source_type）
    ├── {文件名}_combo_config.json    # Step2: 字段组合配置
    │
    ├── parse_status.json             # Step3: 解析状态
    ├── api_cache/                    # Step3: API调用缓存
    │   └── {hash}.json
    │
    ├── match_tasks.json              # Step4: 匹配任务配置
    ├── match_results/                # Step4: 匹配结果缓存
    │   └── {任务名}.json
    │
    └── export_history.json           # Step5: 导出历史
```

### 各Step缓存文件格式

#### Step1/Step2 - 文件状态
**file_status.json** - 统一存储文件的清洗状态和来源类型
```json
{
  "廊坊工商户.csv": {
    "cleaned": "已清洗",
    "source_type": "客户采集数据"
  },
  "民用户.csv": {
    "cleaned": "已清洗",
    "source_type": "客户采集数据"
  },
  "阀门.csv": {
    "cleaned": "未清洗",
    "source_type": "GIS 数据"
  }
}
```

#### Step2 - 字段组合配置
**{文件名}_combo_config.json**
```json
{
  "fields": [
    {"role": "地址", "field": "address"},
    {"role": "区域", "field": "location"},
    {"role": "名称", "field": "name"}
  ]
}
```

#### Step3 - 解析状态
**parse_status.json**
```json
{
  "廊坊工商户_清洗.csv": {
    "parsed": true,
    "parse_time": "2024-12-01T17:00:00",
    "total_rows": 8069,
    "success_rows": 8000,
    "fail_rows": 69
  }
}
```

**api_cache/{hash}.json** - API调用缓存
```json
{
  "address": "河北省廊坊市新开路街道未来城1栋",
  "result": {
    "province": "河北省",
    "city": "廊坊市",
    "district": "广阳区",
    "street": "新开路街道",
    "detail": "未来城1栋",
    "lng": 116.7,
    "lat": 39.5
  },
  "cached_at": "2024-12-01T17:00:00"
}
```

#### Step4 - 匹配任务
**match_tasks.json**
```json
{
  "tasks": [
    {
      "id": "task_001",
      "name": "客户数据匹配GIS",
      "left_file": "廊坊工商户_清洗.csv",
      "right_file": "管网数据.csv",
      "match_fields": [
        {"left": "address", "right": "gis_address", "weight": 0.6},
        {"left": "name", "right": "gis_name", "weight": 0.4}
      ],
      "threshold": 0.8,
      "status": "completed"
    }
  ]
}
```

#### Step5 - 导出历史
**export_history.json**
```json
{
  "exports": [
    {
      "id": "export_001",
      "type": "match_result",
      "source_task": "task_001",
      "output_file": "匹配结果_20241201.xlsx",
      "export_time": "2024-12-01T19:00:00"
    }
  ]
}
```

### Step间数据流转

```
Step1 导入文件
    │
    ├─▶ data_sources (内存)
    │
    ▼
Step2 配置字段组合
    │
    ├─▶ 保存到 {文件名}_combo_config.json
    │
    ▼
Step2 执行清洗
    │
    ├─▶ 输出到 {省}{市}_客户数据清洗/清洗后数据/*.csv
    ├─▶ 保存状态到 file_cleaned_status.json
    ├─▶ 同步更新 Step1 内存
    │
    ▼
Step3 标准化解析（调用阿里云API）
    │
    ├─▶ 读取清洗后的CSV
    ├─▶ API结果缓存到 api_cache/
    ├─▶ 输出到 {省}{市}_标准化结果/*.csv
    ├─▶ 保存状态到 parse_status.json
    │
    ▼
Step4 匹配任务
    │
    ├─▶ 读取标准化后的数据
    ├─▶ 配置保存到 match_tasks.json
    ├─▶ 结果缓存到 match_results/
    ├─▶ 输出到 {省}{市}_匹配结果/*.csv
    │
    ▼
Step5 导出 & 日志
    │
    ├─▶ 读取匹配结果
    ├─▶ 导出到 {省}{市}_导出/
    └─▶ 记录到 export_history.json
```

### 实施路线图

#### 短期 - Step1/Step2（当前已完成）
- ✅ 清洗状态保存到项目缓存目录
- ✅ 字段组合配置保存到项目缓存目录
- ✅ Step1/Step2 共享同一缓存
- [ ] Step1 表格自动刷新（当Step2清洗完成时）

#### 中期 - Step3（标准化解析）
- [ ] 实现阿里云地址解析API调用
- [ ] API结果缓存（避免重复请求，节省费用）
- [ ] 解析状态保存到 parse_status.json
- [ ] 解析进度显示

#### 中期 - Step4（匹配任务）
- [ ] 匹配任务配置界面
- [ ] 精准/模糊/组合匹配算法
- [ ] 匹配结果缓存
- [ ] 匹配进度和结果预览

#### 中期 - Step5（导出日志）
- [ ] 匹配结果导出（Excel/CSV）
- [ ] 日志导出
- [ ] 导出历史记录

#### 长期 - 架构升级（规模扩大后）
- [ ] 合并缓存文件为 project_state.json
- [ ] 创建 ProjectStateManager（Core层）
- [ ] 添加事件机制（跨Step自动刷新）
- [ ] 添加缓存版本号和迁移机制

### 已知缺陷（接受）

| 缺陷 | 说明 | 影响范围 | 接受原因 |
|------|------|----------|----------|
| 文件名冲突 | 同名文件会共用状态 | 低 | 简化实现 |
| 缓存失效 | 手动删除文件后缓存不清理 | 低 | 后续可加清理 |
| 无版本控制 | 缓存格式升级需手动处理 | 低 | 格式稳定 |
| 无并发控制 | 多实例可能冲突 | 低 | 单实例为主 |

### 相关代码位置

| 功能 | 文件 | 方法 |
|------|------|------|
| 加载文件状态 | `ui/steps/step1_widget.py` | `_load_file_status_from_project_cache()` |
| 保存文件状态 | `ui/steps/step1_widget.py` | `_save_file_status_to_project_cache()` |
| 来源类型变更 | `ui/steps/step1_widget.py` | `_on_source_type_changed()` |
| 加载清洗状态 | `ui/steps/step2_widget.py` | `_load_cleaned_status_from_project_cache()` |
| 保存清洗状态 | `ui/steps/step2_widget.py` | `_save_cleaned_status_to_project_cache()` |
| 加载字段配置 | `ui/steps/step2_widget.py` | `_load_file_combo_config()` |
| 保存字段配置 | `ui/steps/step2_widget.py` | `_save_file_combo_config()` |
| 全局配置 | `ui/widgets/global_config_widget.py` | `get_region_info()` |

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

#### 4. FieldRelationAnalyzer（字段关联分析器）

**位置**: `core/field_relation.py`

**功能**:
- 读取多个 CSV/Excel 文件
- 计算跨文件字段间的值重叠（Jaccard 相似度、包含度）
- 构建 NetworkX 关系图
- 社区发现（Louvain 算法）
- 中心性分析
- 生成洞察报告

**API**:
```python
from core.field_relation import FieldRelationAnalyzer

analyzer = FieldRelationAnalyzer(log_callback=my_log, progress_callback=my_progress)
result = analyzer.analyze(file_paths=['a.csv', 'b.csv'], min_overlap=1)

# 返回格式
# {
#   'success': True,
#   'fields': [...],      # 所有字段列表
#   'relations': [...],   # 字段关联关系
#   'insights': [...],    # 洞察发现
#   'layout': {...},      # 图布局坐标
#   'communities': [...], # 社区/簇
#   'centrality': {...}   # 中心性指标
# }
```

#### 5. RelationExporter（关联数据导出器）

**位置**: `core/field_relation.py`

**功能**:
- 执行两表关联操作（INNER JOIN / LEFT ANTI JOIN / RIGHT ANTI JOIN）
- 导出带颜色区分的 Excel 文件
- 导出 CSV 文件

**导出类型**:
| 类型 | 常量 | 说明 |
|------|------|------|
| 关联数据 | `JOIN_INNER` | 两表都有的数据 |
| A表未关联 | `JOIN_LEFT_ONLY` | A表有但B表没有 |
| B表未关联 | `JOIN_RIGHT_ONLY` | B表有但A表没有 |

**API**:
```python
from core.field_relation import RelationExporter

exporter = RelationExporter(log_callback=my_log)
result = exporter.export(
    path_a='customers.csv',
    path_b='addresses.csv',
    col_a='customer_id',
    col_b='addr_customer_id',
    output_path='joined.xlsx',
    join_type=RelationExporter.JOIN_INNER  # 或 JOIN_LEFT_ONLY / JOIN_RIGHT_ONLY
)

# 返回格式
# {
#   'success': True,
#   'message': '已导出 1000 条关联数据',
#   'row_count': 1000,
#   'output_path': 'joined.xlsx'
# }
```

#### 6. MatchDialog（主对话框）

**位置**: `ui/match_dialog.py`

**职责**:
- 只负责布局和协调
- 侧边栏导航
- 主内容区布局
- 步骤切换逻辑
- 样式加载（通过 StyleManager）
- 日志统一入口

**代码行数**: ~298行

#### 5. GlobalConfigWidget（全局配置组件）

**位置**: `ui/widgets/global_config_widget.py`

**功能**:
- **区域配置**: 省/市/县（县为可选）下拉选择
- **根目录选择**: 用户选择数据根目录
- **自动目录生成**: 根据省市县自动创建三个子文件夹
- **全局同步**: 通过信号机制通知所有步骤区域变更

**目录命名规则**:
- 客户数据目录: `{根目录}/{省}{市}{县}客户数据`
- SHP数据目录: `{根目录}/{省}{市}{县}shp数据`
- 缓存数据目录: `{根目录}/{省}{市}{县}cache数据`

**示例**:
- 如果选择：省=上海市，市=浦东新区，县=陆家嘴，根目录=D:\Data
- 生成的目录：
  - `D:\Data\上海市浦东新区陆家嘴客户数据`
  - `D:\Data\上海市浦东新区陆家嘴shp数据`
  - `D:\Data\上海市浦东新区陆家嘴cache数据`

**API**:
```python
# 获取区域信息（供其他组件使用）
region_info = global_config.get_region_info()
# 返回: {
#   "province": "上海市",
#   "city": "浦东新区",
#   "county": "陆家嘴",
#   "base_folder": "D:\\Data",
#   "customer_folder": "D:\\Data\\上海市浦东新区陆家嘴客户数据",
#   "shp_folder": "D:\\Data\\上海市浦东新区陆家嘴shp数据",
#   "cache_folder": "D:\\Data\\上海市浦东新区陆家嘴cache数据"
# }

# 信号：区域改变时发出
global_config.region_changed.connect(callback)
```

**使用方式**:
- 在所有5个步骤中都可见（通过CollapsibleSection可折叠）
- 步骤组件通过 `MatchDialog` 获取 `global_config` 实例
- 通过 `get_region_info()` 获取当前区域和目录信息
- 监听 `region_changed` 信号以响应区域变更

**配置持久化**:
- **历史配置管理**: 使用 QGIS 的 `QSettings` 保存历史配置（符合 QGIS 插件标准）
  - 按省市区作为 key 保存：`regions/{省}|{市}|{县}/base_folder`
  - 支持保存多个地区的历史配置
  - 当用户选择某个地区时，自动从 QSettings 查找该地区的历史配置
  - 如果找到历史配置且目录存在，自动填充根目录
- **项目数据缓存**: `cache/` 目录用于缓存项目数据（清洗结果、中间数据等）
- **初始化加载**: 下次打开插件时，自动加载最后一次使用的配置（省、市、县、根目录）

#### 6. Step Widgets

**位置**: `ui/steps/stepX_widget.py`

**职责**:
- 各自负责自己的UI和业务逻辑
- 通过依赖注入接收共享资源
- 调用core层完成业务逻辑
- 使用全局配置获取区域和目录信息

**实现**:
- 所有 Step Widgets 继承自 `BaseStepWidget`
- 通过 `self._log()` 记录日志
- 通过 `self.get_task_manager()` 获取任务管理器
- 通过 `MatchDialog` 的 `global_config` 获取全局配置信息

**数据保存规则**:
- Step1（文件导入）: 导入的文件保存到 `customer_folder`
- Step2（字段映射与清洗）: 清洗后的数据保存到 `customer_folder`
- Step3（标准化解析）: 标准化后的数据保存到 `customer_folder`
- Step4（匹配任务）: 匹配结果保存到 `customer_folder`
- Step5（导出）: 导出文件保存到 `customer_folder`
- SHP数据: 保存到 `shp_folder`
- 缓存数据: 保存到 `cache_folder`

---

## 公共组件设计

> 遵循 DRY 原则，将通用功能抽取为公共组件，避免代码重复。

### 公共组件列表

| 组件 | 位置 | 用途 |
|------|------|------|
| ResultDialog | `ui/widgets/result_dialog.py` | 统一风格的结果弹窗 |
| CollapsibleSection | `ui/collapsible_section.py` | 可折叠的分组容器 |
| BaseStepWidget | `ui/widgets/base_step_widget.py` | Step Widget 基类 |
| TaskManager | `ui/widgets/task_manager.py` | 任务进度管理 |
| GlobalConfigWidget | `ui/widgets/global_config_widget.py` | 全局配置组件 |

### ResultDialog - 通用结果弹窗

**设计原则**：
- 统一弹窗样式，避免各处使用原生 QMessageBox
- 样式通过 QSS 管理，保持风格一致
- 支持四种类型：成功(✅)、失败(❌)、警告(⚠️)、信息(ℹ️)

**使用方式**：
```python
from ..widgets.result_dialog import ResultDialog

# 成功弹窗
ResultDialog.show_success(self, "操作成功", "数据已保存")

# 错误弹窗
ResultDialog.show_error(self, "操作失败", "文件不存在")

# 警告弹窗
ResultDialog.show_warning(self, "注意", "部分数据未处理")

# 信息弹窗
ResultDialog.show_info(self, "提示", "请先配置参数")

# 带详细信息
ResultDialog.show_success(
    self, "连接成功", "API 配置正确",
    detail="💡 提示：结果会自动缓存",
    window_title="测试结果"
)
```

**禁止做法**：
```python
# ❌ 错误：直接使用 QMessageBox
QMessageBox.information(self, "提示", "操作完成")

# ✅ 正确：使用公共组件
ResultDialog.show_success(self, "操作完成", "数据已保存")
```

### 公共组件开发规范

1. **位置**：公共组件统一放在 `ui/widgets/` 目录
2. **样式**：通过 QSS 管理，不使用内联样式
3. **命名**：使用 `setObjectName()` 设置对象名，便于 QSS 匹配
4. **文档**：组件需要有清晰的文档说明用法

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
  - ✅ `from qgis.PyQt.QtCore import ...`（包括 QSettings）
  - ✅ `from qgis.PyQt.QtGui import ...`

#### 4. 配置管理规范
- [x] **历史配置**: 使用 `QSettings` 保存插件配置（符合 QGIS 标准）
  - ✅ 使用 `QSettings("fz_adr_match_dev", "global_config")` 创建配置实例
  - ✅ 配置保存在 QGIS 的配置系统中（Windows 通常在注册表）
  - ✅ 支持多地区历史配置管理（按省市区作为 key）
  - ✅ 当用户选择某个地区时，自动从 QSettings 查找该地区的历史配置
- [x] **项目数据缓存**: 使用 `cache/` 目录缓存项目数据
  - ✅ 清洗结果、中间数据等保存在 `cache/` 目录
  - ✅ 使用 `utils/cache.py` 中的工具函数管理缓存
  - ✅ **配置存储分离**：
    - `cache/` 目录：用于缓存项目数据（清洗结果、中间数据等）
    - QSettings：用于保存历史配置（符合 QGIS 插件标准）

#### 5. 路径处理规范
- [x] 使用 `os.path.join()` 构建路径
- [x] 使用 `os.path.dirname(__file__)` 获取插件目录
- [x] 使用相对路径访问资源文件
- [x] 没有硬编码的绝对路径

#### 6. 模块导入规范
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
- [x] `ui/steps/step1_widget.py` - Step1文件导入（已实现完整功能：文件导入、格式转换、保存到全局配置目录）
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
- [x] `core/data_loader.py` - 数据加载（CSV/Excel/SHP等）和格式转换
- [x] `core/field_detector.py` - 字段检测与关联推断
- [x] `core/data_cleaner.py` - 数据清洗
- [x] `core/ali_address_parser.py` - 阿里云地址解析（StructureAddress + PredictPOI）
- [x] `core/poi_utils.py` - POI公共工具函数
- [x] `core/poi_matcher.py` - V11 POI匹配引擎（RapidFuzz + SentenceTransformer）
- [x] `core/match_executor.py` - 匹配任务执行器 + 任务持久化管理
- [x] `core/export_manager.py` - 导出管理器
- [x] `core/field_relation.py` - 字段关联分析
- [x] `core/match_engine.py` - 旧匹配引擎（已弃用，保留向后兼容）
- [x] `core/address_matcher.py` - 旧地址匹配器（已弃用，保留向后兼容）

#### 6. 样式管理 ✅
- [x] `ui/styles.qss` - 统一管理所有样式
- [x] `ui/styles.py` - 样式管理器
- [x] 所有样式通过 StyleManager 统一加载
- [x] 无内联样式（`setStyleSheet()` 调用）
- [x] Step1 专用样式已添加到 QSS 文件（表格、复选框、状态标签）

#### 7. 全局配置组件 ✅
- [x] `ui/widgets/global_config_widget.py` - 全局配置组件（308行）
- [x] 区域选择（省/市/县）
- [x] 根目录选择
- [x] 自动目录生成
- [x] 区域变更信号机制
- [x] 在所有步骤中可见

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

- [x] **全局配置目录命名修正**: ✅ 已完成
  - 修正文件夹命名规则，统一为：`xx省xx市xx县客户数据`、`xx省xx市xx县shp数据`、`xx省xx市xx县cache数据`
  - 确保县为可选时，目录名正确处理（无县时：`xx省xx市客户数据`）
  - 更新提示文本以反映新的目录命名规则
- [x] **配置保存/加载**: ✅ 已完成 - 任务组配置自动持久化到 cache/match_tasks.json
- [x] **高级匹配算法**: ✅ 已完成 - V11 POI匹配引擎（RapidFuzz + SentenceTransformer）
- [x] **Step4 执行功能**: ✅ 已完成 - 调用 MatchExecutor 执行匹配任务
- [x] **Step5 导出功能**: ✅ 已完成 - 调用 ExportManager 导出各类结果
- [ ] **后台线程化**: 将匹配操作迁移到后台 QThread，避免UI卡顿（大数据时推荐）
- [ ] **地图可视化**: 在 QGIS 画布添加临时内存图层显示匹配结果
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

### 2024-12-01 - Step2清洗功能实现与结果对话框优化
- **核心功能实现**：
  - **数据清洗模块** (`core/data_cleaner.py`)：
    - 按用户配置的字段顺序拼接地址
    - 删除全空行（配置字段全为空）
    - 删除纯行政区行（只有省市区街道村等，无具体地址）
    - 去除噪声关键字（高压、中压、nan等）
    - 去除冗余占位词（无单元、无号、无楼、暂无等）
    - 清理连续的"无"字（如"无1059" → "1059"）
    - 去除拼接后重复的内容（如"32090部队...32090部队" → "32090部队..."）
    - 忽略全数字且无差异的字段
    - 不含中文的字段不纳入拼接
    - 新增 `{文件名}_adr_clean` 列
  - **输出目录结构**：
    - `{省}{市}_客户数据清洗/清洗后数据/{文件名}_清洗.csv`
    - `{省}{市}_客户数据清洗/异常数据/{文件名}_剔除.csv`（含剔除原因列）
- **纯行政区判断逻辑优化**：
  - 包含数字（门牌号等）→ 不是纯行政区
  - 包含具体地址关键词（超市、公司、小区、号、栋等）→ 不是纯行政区
  - 文本较长（>15个中文字符）→ 不是纯行政区
  - 只有完全是"河北省廊坊市"这种纯行政区划才剔除
- **清洗结果对话框优化**（符合架构规范）：
  - 使用 `objectName` 标识组件，样式在 `styles.qss` 中统一管理
  - 根据结果状态显示不同图标和颜色（成功/警告/失败）
  - 文件被占用时显示友好提示，建议关闭相关文件后重试
  - 新增 QSS 样式：
    - `step2_clean_result_dialog` - 对话框
    - `step2_result_title_success/warning/error` - 结果标题
    - `step2_result_stats` - 统计信息
    - `step2_result_tip_frame/title/text` - 提示框
    - `step2_result_ok_btn` - 确定按钮

### 2024-12-XX - Step2页面架构规范修复（第三版）
- **符合架构要求**：
  - **移除所有内联样式**：移除了所有 `setStyleSheet()` 调用，符合文档要求"无内联样式：所有样式都在 QSS 文件中"
  - **使用 objectName 标识**：为所有需要样式的组件设置了 `objectName`，通过 QSS 选择器应用样式
  - **样式统一管理**：在 `styles.qss` 中添加了 Step2 的所有样式定义，包括：
    - 文件列表表格样式
    - 字段组合滚动区域样式
    - 标签样式（提示标签、当前文件标签、组合标题标签）
    - 字段组合框架样式
    - 字段表格样式
    - 按钮样式（刷新、新增组合、删除组合、新增字段、字段操作按钮等）

### 2024-12-XX - Step2页面UI优化（第二版）
- **UI布局优化**：
  - **文件列表表格高度优化**：设置表格最小高度为200px（参考Step1），让表格能显示多行数据，不再挤在一起
  - **文件列表列宽优化**：
    - 当前列：固定宽度60px（单选按钮）
    - 文件名列：自动扩展
    - 字段组合数列：固定宽度100px
    - 已配置列：固定宽度80px
    - 清洗状态列：固定宽度100px
  - **字段组合区域高度优化**：将滚动区域最小高度从400px增加到500px，让内容更清晰可见
  - **字段组合表格优化**：
    - 设置表格最小高度120px，确保内容可见
    - 设置行高32px，让内容更清晰
    - 优化列宽设置：
      - 顺序列：固定宽度60px
      - 角色名称列：固定宽度150px，确保能显示完整内容
      - 字段列：固定宽度200px，确保下拉框能完整显示
      - 操作列：固定宽度120px
  - **字段组合块间距优化**：增加内边距（从6px到8px）和间距（从4px到8px），让内容更清晰

### 2024-12-XX - Step2页面修复（第一版）
- **核心功能修复**：
  - **建立数据共享机制**：在 `BaseStepWidget` 中添加 `get_step1_data_sources()` 方法，让 Step2 能访问 Step1 的数据源
  - **动态加载文件列表**：移除硬编码的示例数据，改为从 Step1 的 `data_sources` 动态生成文件列表
  - **读取文件列名**：在 `DataLoader` 中添加 `get_file_columns()` 方法，支持读取 CSV/Excel 文件的列名
  - **字段映射下拉框优化**：字段映射下拉框现在使用实际文件的列名，而不是硬编码的选项
  - **自动刷新机制**：进入 Step2 时自动刷新文件列表（延迟500ms，确保 Step1 已初始化）
  - **刷新按钮**：添加"刷新文件列表"按钮，支持手动刷新
  
- **代码改进**：
  - 修改 `Step2Widget.__init__()`：移除硬编码数据，改为动态数据结构
  - 添加 `_refresh_file_list()` 方法：从 Step1 获取数据源并更新文件列表
  - 添加 `_update_cfg_progress_table()` 方法：动态更新文件配置进度表格
  - 添加 `_get_file_columns()` 方法：获取文件列名（带缓存机制）
  - 修改 `_create_combo_block()`：字段映射下拉框使用实际文件的列名
  - 修改 `_add_field_row()`：新增字段行时使用实际文件的列名
  - 修改 `_refresh_file_config_display()`：处理没有选中文件的情况
  
- **待完善功能**：
  - 配置持久化：字段组合配置暂未保存到配置文件（将在后续版本实现）
  - 文件状态同步：清洗状态需要与实际清洗结果同步（将在后续版本实现）

### 2024-12-XX - Step2页面问题分析总结
- **问题分析**：对 Step2 页面进行了全面分析，发现以下问题：
  
  **1. 数据源不同步（核心问题）**：
  - Step2 使用硬编码的示例数据，未从 Step1 获取实际文件列表
  - Step2 显示固定的 3 个示例文件，而 Step1 实际有 20 个文件
  - 无法对 Step1 导入的真实文件进行配置
  
  **2. 字段映射选项硬编码**：
  - 字段下拉框选项是固定的（"std_city", "province", "community_name" 等）
  - 应该从实际文件的列名动态获取
  - 无法映射到真实文件的列
  
  **3. 缺少数据获取机制**：
  - Step2 无法访问 Step1 的 `data_sources`
  - 应该通过父对话框或共享数据管理器获取 Step1 的数据
  - 无法获取文件路径、列名等信息
  
  **4. 配置未持久化**：
  - 字段组合配置只存在内存中
  - 应该保存到配置文件或数据库
  - 切换步骤或重启后配置丢失
  
  **5. 文件状态未同步**：
  - "已配置"、"清洗状态" 等状态是硬编码
  - 应该从实际配置和清洗结果中获取
  - 状态显示不准确
  
  **6. 缺少文件列名读取**：
  - 未读取实际文件的列名
  - 应该读取 CSV/Excel 文件的列名，用于字段映射
  - 无法进行正确的字段映射
  
  **7. UI布局和样式问题**：
  - 表格列宽可能未优化
  - 字段映射输入框显示可能不够清晰
  - 组合块的视觉层次可能需要优化
  - 按钮样式和间距可能需要统一
  - 滚动区域样式可能需要调整
  
- **待修复**：这些问题将在后续版本中逐步修复，确保 Step1 功能不受影响

### 2024-12-XX - 修复Step1移除选中功能
- **功能修复**：
  - 修复了"移除选中"功能，现在会从对应文件夹中实际删除文件
  - 添加了删除确认对话框，防止误删
  - 删除文件后从表格和数据源字典中移除
  - 记录详细的删除日志（成功/失败）
- **用户体验**：
  - 删除前会弹出确认对话框
  - 删除后显示成功/失败统计
  - 如果文件不存在，会记录警告但继续移除列表项
  - 用户如需重新使用，可以重新导入文件

### 2024-12-XX - 移除Step1描述文本（已还原）
- **UI优化**：
  - 移除了Step1页面的副标题描述："导入多源文件，管理参与任务的表。"（已还原）
  - 移除了全局配置中"确认并生成目录"按钮下方的提示文本（已还原）
  - 简化界面，减少冗余信息（已还原）
- **符合用户需求**：界面更简洁，去除不必要的描述性文字（已还原）

### 2024-12-XX - 修复导航栏SingleSelection错误
- **错误修复**：
  - 移除了错误的 `setSelectionMode(QAbstractItemView.SingleSelection)` 调用
  - `QListWidget` 默认就是单选模式，无需显式设置
  - 简化代码，移除不必要的设置
- **符合PyQt标准**：`QListWidget` 默认行为就是单选，符合需求

### 2024-12-XX - 修复导航栏SingleSelection错误（第一次尝试）
- **错误修复**：
  - 修复了 `QListWidget.SingleSelection` 错误
  - `SingleSelection` 是 `QAbstractItemView` 的常量，不是 `QListWidget` 的
  - 添加 `QAbstractItemView` 导入，使用 `QAbstractItemView.SingleSelection`
- **符合PyQt标准**：使用正确的枚举类设置选择模式

### 2024-12-XX - 修复导航栏NoFrame错误
- **错误修复**：
  - 移除了错误的 `setFrameShape(QListWidget.NoFrame)` 调用
  - `QListWidget` 没有 `NoFrame` 属性（该属性属于 `QFrame`）
  - 边框已通过 QSS 样式移除（`border: none;`），无需代码设置
- **符合QGIS标准**：使用 QSS 样式控制外观，而非代码设置

### 2024-12-XX - 重构左侧导航栏（符合QGIS原生开发标准）
- **QGIS原生标准重构**：
  - 参考QGIS官方UI设计指南，使用系统调色板（palette）
  - 宽度调整为180px（QGIS标准侧边栏宽度）
  - 使用QListWidget.SingleSelection单选模式
  - 间距优化：列表项间距1px，符合QGIS标准
- **样式系统化改进**：
  - 使用Qt系统调色板（palette）而非硬编码颜色
    - `palette(window)` - 窗口背景色
    - `palette(windowText)` - 窗口文字色
    - `palette(button)` - 按钮背景色
    - `palette(highlight)` - 选中高亮色
    - `palette(highlightedText)` - 选中文字色
    - `palette(mid)` - 边框色
    - `palette(disabled, windowText)` - 禁用文字色
  - 优势：自动适配系统主题（浅色/深色），符合QGIS原生体验
  - 字体大小优化：标题12px，列表项11px，底部提示9px
  - 内边距优化：符合QGIS标准间距规范
- **符合QGIS开发规范**：
  - 遵循QGIS插件UI设计指南
  - 使用系统调色板确保与QGIS主界面一致
  - 简洁设计，无多余装饰

### 2024-12-XX - 重构左侧导航栏（QGIS原生风格）
- **QGIS原生标准重构**：
  - 简化导航栏设计，符合QGIS原生插件风格
  - 移除圆圈数字符号（①-⑤），使用简洁的文本导航
  - 优化宽度：从230px调整为200px（QGIS标准宽度）
  - 简化标题：从"地址清洗 & 多源匹配插件"改为"地址清洗与多源匹配"
  - 简化底部提示文字
- **样式优化**：
  - 使用QGIS原生配色方案（#f5f5f5背景，更柔和的边框）
  - 优化导航项样式：更小的内边距，更标准的选中效果
  - 移除左侧边框指示器，使用背景色区分选中状态
  - 优化字体大小和间距，符合QGIS原生风格

### 2024-12-XX - 修复内容区域扩展问题（QScrollArea动态宽度调整）
- **根本原因分析**：
  - `QScrollArea` 的 `setWidgetResizable(True)` 会根据内容widget的 `sizeHint()` 调整大小
  - 即使设置了 `Expanding` 尺寸策略，在 `QScrollArea` 中也可能不会生效
  - 内容widget默认只占用最小必需空间，不会自动扩展填满viewport宽度
- **动态宽度调整方案**：
  - 添加 `eventFilter` 监听 `QScrollArea` 的 `viewport` resize事件
  - 当viewport宽度变化时，动态设置 `content_widget` 的最小宽度等于viewport宽度
  - 确保内容widget始终填满QScrollArea的可用宽度
  - 使用 `QTimer.singleShot` 在初始化时也设置一次宽度
- **配合尺寸策略**：
  - 所有 Step Widget 和 QGroupBox 已设置 `Expanding` 尺寸策略
  - 动态宽度调整确保在QScrollArea环境下也能正确扩展

### 2024-12-XX - 修复内容区域扩展问题（尺寸策略优化）
- **根本原因分析**：
  - `Step1Widget` 和所有 `QGroupBox` 使用默认的 `QSizePolicy.Preferred` 尺寸策略
  - `Preferred` 策略只占用最小必需空间，不会扩展填满可用空间
  - 即使父容器设置了 `Expanding`，子组件不扩展时仍会留下空白
- **系统性修复**：
  - 为所有 Step Widget（step1-5）设置 `Expanding` 尺寸策略（水平和垂直）
  - 为所有 `QGroupBox` 设置水平 `Expanding`、垂直 `Preferred` 尺寸策略
  - 创建统一的 `_set_expanding_size_policy()` 和 `_set_groupbox_expanding()` 辅助方法
  - 确保所有内容组件能够正确扩展填满可用空间
- **影响范围**：
  - 修复了右侧垂直空白（水平空间未充分利用）
  - 修复了底部垂直空白（垂直空间未充分利用）
  - 所有 Step 页面（1-5）现在都能正确扩展

### 2024-12-XX - 优化内容区域扩展策略
- **水平扩展优化**：
  - 为`main_widget`和`content_widget`设置`QSizePolicy.Expanding`尺寸策略
  - 确保主内容区能够水平扩展填满可用宽度
  - 确保内容滚动区内的内容能够正确扩展
- **垂直扩展优化**：
  - 移除所有Step Widget中的`addStretch()`调用
  - 让内容充分利用垂直空间，消除底部空白

### 2024-12-XX - 移除底部空白区域
- **充分利用空间**：
  - 移除所有Step Widget（step1-5）中`_build_ui`方法里的`layout.addStretch()`调用
  - 消除内容区域底部的空白空间，让内容充分利用可用空间
  - 保留按钮行等内部布局中的`addStretch()`（用于对齐按钮）

### 2024-12-XX - 全局布局对齐优化
- **统一内容区域对齐**：
  - 所有内容区域的左右边距统一为16px
  - 标题栏、全局配置容器、内容滚动区、日志面板都使用16px左右边距
  - 移除所有Step Widget内部的左右边距，由父容器统一控制
  - 确保所有Step页面（1-5）的内容都与左侧导航栏对齐
  - 右侧边距也统一对齐，保持视觉一致性

### 2024-12-XX - Step1初始化优化
- **自动加载已导入数据源**：
  - 在`Step1Widget.__init__`中添加延迟刷新逻辑
  - 使用`QTimer.singleShot(500, self._on_refresh)`延迟500ms后自动刷新
  - 确保全局配置已初始化后再加载数据源列表
  - 用户进入插件后无需手动点击"刷新"按钮即可看到已导入的文件

### 2024-12-XX - Step1表格交互优化
- **禁用下拉框滚轮修改**：
  - 创建`NoWheelComboBox`类，继承自`QComboBox`
  - 重写`wheelEvent`方法，忽略滚轮事件
  - 防止用户在滚动表格时意外修改"来源类型"下拉框的值
  - 用户只能通过点击下拉框选择，不能通过滚轮修改

### 2024-12-XX - Step1转换功能优化（后台线程与执行控制）
- **移除自动执行**：
  - 选择文件后不再自动执行转换
  - 用户必须点击"执行"按钮才会开始转换
  - 选择文件后只保存路径，等待用户点击执行
- **后台线程实现**：
  - 创建`ShpConvertThread`类，继承自`QThread`
  - 转换操作在后台线程执行，避免UI卡顿
  - 使用信号和槽机制更新进度条和状态
  - 进度更新信号：`progress_updated(current, total, filename)`
  - 文件转换完成信号：`file_converted(shp_file, output_file, status)`
  - 转换完成信号：`finished(success_count, fail_count)`
- **进度展示优化**：
  - 实时显示当前转换的文件名
  - 显示转换进度（当前/总数）
  - 转换完成后显示成功和失败数量
- **线程管理**：
  - 检查是否有任务正在运行，防止重复执行
  - 转换完成后自动清理线程引用

### 2024-12-XX - Step1页面优化与功能完善
- **布局优化**：
  - 调整全局配置块的边距，使其与Step内容更协调
  - 在全局配置容器中添加适当的边距（12px），与滚动区内容对齐
- **SHP路径持久化**：
  - 使用QSettings保存用户选择的SHP文件路径
  - 按省市区作为key保存，支持多地区配置
  - 区域切换时自动加载对应地区的SHP路径
  - 监听全局配置的`region_changed`信号，自动更新路径
- **自动刷新功能**：
  - Step1显示时自动刷新数据源文件列表
  - 在`_switch_step`中检测Step1，自动调用`_on_refresh()`
- **UI简化**：
  - 移除SHP转换的"暂停"和"终止"按钮
  - 简化控制按钮布局，只保留"执行"按钮
- **文件选择优化**：
  - 提供两个独立的按钮，分别支持两种选择方式：
    1. **"选择文件夹"按钮**：使用`QFileDialog.getExistingDirectory()`选择文件夹，扫描文件夹中所有.shp文件
    2. **"选择文件"按钮**：使用`QFileDialog.getOpenFileNames()`选择.shp文件（支持多选）
  - 用户可以直接点击对应按钮选择文件夹或文件，无需先选文件夹再取消
  - 选择文件或文件夹后，需要点击"执行"按钮才会开始转换
  - 单个文件选择后显示文件路径，多个文件或文件夹选择后显示路径

### 2024-12-XX - UI初始化优化
- **默认步骤修复**：
  - 将默认显示的步骤从Step2改为Step1
  - 修改 `_current_step` 初始值为1
  - 修改 `_switch_step()` 初始调用为 `_switch_step(1)`
- **全局配置默认状态**：
  - 将全局配置的默认状态从展开改为收起
  - 修改 `CollapsibleSection` 的 `expanded` 参数为 `False`
  - 用户可以根据需要手动展开

### 2024-12-XX - Step1 SHP文件转换功能修复与优化
- **改用QGIS原生API**：
  - 将 `load_shp()` 方法从使用 `fiona`/`shapely` 改为使用 QGIS 原生 API（`QgsVectorLayer`）
  - 优势：无需外部依赖，利用 QGIS 已有功能，更符合 QGIS 插件最佳实践
  - 自动处理编码问题（QGIS 自动处理 .dbf 文件的编码）
- **SHP文件结构理解与实现**：
  - 理解SHP文件组成：.shp（几何数据）、.shx（索引）、.dbf（属性数据）、.prj（投影）、.cpg（编码）
  - 改进 `load_shp()` 方法：
    - 检查必需的辅助文件（.shx、.dbf）是否存在
    - 使用 `QgsVectorLayer` 加载 SHP 文件（自动处理所有辅助文件）
    - 使用 `feature.attribute()` 读取 .dbf 文件中的属性数据
    - 使用 `feature.geometry().asWkt()` 将几何数据转换为WKT格式
    - 使用 `layer.crs()` 获取坐标系信息（如果有.prj文件）
    - 正确处理 `QVariant` 类型（QGIS 属性值的标准类型）
  - 改进错误处理：提供详细的错误信息，帮助用户定位问题
- **Core层优化**：
  - `save_to_csv()` 方法改进：正确处理WKT格式的几何数据
  - 确保输出目录存在（处理空目录情况）

### 2024-12-XX - Step1 文件导入功能实现
- **实现Step1完整功能**：
  - 文件选择对话框（支持多选Excel/SHP/CSV文件）
  - 自动格式转换：Excel/SHP → CSV
  - 根据文件类型自动保存到对应目录：
    - Excel/CSV文件 → `customer_folder`（客户数据目录）
    - SHP文件 → `shp_folder`（SHP数据目录）
  - 文件重名处理：自动添加序号避免覆盖
  - 批量SHP转换：支持选择文件夹，递归扫描所有SHP文件
  - 表格自动更新：导入后自动添加到数据源列表
  - 刷新功能：扫描全局配置目录，加载已保存的CSV文件
- **Core层扩展**：
  - 在 `DataLoader` 中添加 `save_to_csv()` 方法：将数据保存为CSV
  - 在 `DataLoader` 中添加 `convert_to_csv()` 方法：自动检测格式并转换为CSV
  - 支持处理复杂数据类型（dict/list转为JSON字符串）
  - 使用 utf-8-sig 编码，确保Excel能正确打开
- **架构设计**：
  - UI层通过parent查找MatchDialog获取global_config引用
  - UI层调用Core层完成数据加载和转换
  - 符合分层架构原则（UI → Core）

### 2024-12-XX - Step1 UI优化与规范修正
- **Step1 页面UI优化**：
  - 移除示例数据和说明文字，改为空表格（通过 `add_data_source()` 方法添加数据）
  - 移除"参与任务"和"字段组合数"列，表格简化为：选择、文件名、来源类型、清洗状态
  - 优化表格列宽设置，确保来源类型下拉框能完整显示
  - 优化复选框样式和位置（左对齐，使用 QSS 样式）
  - 移除 SHP 转换辅助功能的描述文字
  - 增加布局间距，提升页面美观度
- **日志面板优化**：
  - 标题改为"执行日志"（移除"（所有步骤）"说明）
  - 固定日志面板高度（200px），移除 QSplitter，使用固定布局
  - 日志面板固定在底部，不可拖动
- **代码规范修正**：
  - 移除内联样式（`setStyleSheet()` 调用），改为使用 `setObjectName()` 和 QSS 文件
  - 符合文档要求："无内联样式：所有样式都在 QSS 文件中"
  - 在 `styles.qss` 中添加 Step1 专用样式（表格、复选框、状态标签）

### 2024-XX-XX - 强化AI开发工作流程
- **添加强制工作流程**：
  - 在"AI开发指南"中添加"强制工作流程"部分
  - 明确四个步骤：阅读文档 → 开发代码 → 更新文档 → 代码审查
  - 添加强制检查清单，确保每次开发都完成所有检查项
  - 更新所有提示词模板，强调必须遵循强制工作流程
- **更新提示词模板**：
  - 更新 `AI_PROMPT_TEMPLATE.md`，包含强制工作流程
  - 更新 `AI_QUICK_REFERENCE.md`，强调必须遵循流程
  - 确保所有提示词都要求AI先阅读文档

### 2024-XX-XX - 全局配置需求明确与修正
- 明确全局配置逻辑需求：
  - 省/市/县（县可选）全局配置，所有5个步骤同步使用
  - 用户选择根目录，自动生成三个子文件夹
  - 目录命名规则：`xx省xx市xx县客户数据`、`xx省xx市xx县shp数据`、`xx省xx市xx县cache数据`
  - 所有步骤的数据保存都遵循全局配置的目录规则
- 在文档中添加全局配置的详细说明和API文档
- 修复 `match_dialog.py` 中的语法错误（try语句缩进问题）
- **修正代码中的目录命名规则**：
  - 修正 `global_config_widget.py` 中的 `_refresh_paths()` 方法
  - SHP目录：`SHP数据` → `shp数据`（小写）
  - 缓存目录：`{省}{市}cache` → `{省}{市}{县}cache数据`（包含县，并加上"数据"后缀）
  - 更新提示文本以反映新的目录命名规则
- **修复区域数据加载问题**：
  - 修正 `_load_region_tree()` 方法，通过代码（code）正确建立省份、城市、区县的关联关系
  - 数据文件使用 `provinceCode` 和 `cityCode` 进行关联，而不是直接使用名称
  - 现在可以正确加载和显示市和县的下拉选项
- **添加配置自动加载功能**：
  - 使用 QGIS 的 `QSettings` 保存历史配置（符合 QGIS 插件标准）
  - 添加 `_save_global_config()` 和 `_load_last_config()` 方法
  - 支持多地区历史配置管理（按省市区作为 key）
  - 当用户选择某个地区时，自动从 QSettings 查找该地区的历史配置
  - 下次打开插件时，自动加载最后一次使用的配置（省、市、县、根目录）
  - 自动填充下拉框和输入框，并刷新路径
  - **配置存储分离**：
    - `cache/` 目录：用于缓存项目数据（清洗结果、中间数据等）
    - QSettings：用于保存历史配置（符合 QGIS 插件标准）

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

### ⚠️ 重要：强制工作流程

**所有AI助手在开发代码前，必须严格按照以下流程执行：**

#### 第零步：全局思维分析（必须，防止堆砌式开发）

**⚠️ 这是最重要的步骤！在开始任何开发前，必须先完成全局思维分析。**

1. **理解整体架构和目标**：
   - 这个项目是什么？解决什么问题？
   - 整体架构是什么？各层职责是什么？
   - 核心设计原则是什么？（分层架构、单一职责、依赖注入、关注点分离）
   - 这个需求/问题在整个系统中的位置是什么？

2. **识别根本问题，而非表面症状**：
   - 不要看到问题就立即写代码修复
   - 先问：这个问题的根本原因是什么？
   - 先问：这个问题是否反映了架构设计的问题？
   - 先问：是否有更好的系统性解决方案？

3. **设计系统性解决方案**：
   - 不要零散地添加功能或修复
   - 思考：这个改动对整体架构的影响是什么？
   - 思考：是否有更符合架构原则的实现方式？
   - 思考：这个改动是否会破坏现有的设计模式？

4. **评估影响范围**：
   - 这个改动会影响哪些模块？
   - 是否需要重构现有代码？
   - 是否符合现有的代码组织规则？
   - 是否会引入新的依赖或耦合？

5. **检查架构设计文档**：
   - 阅读"架构设计"部分，理解整体架构
   - 阅读"代码组织指南"，了解各层职责
   - 阅读"样式管理"部分，了解如何正确使用 QSS 和 objectName
   - 查看现有代码示例，理解代码实现规范

**样式管理代码实现检查清单**（修改UI时必须检查）:
- [ ] 是否移除了所有 `setStyleSheet()` 调用？
- [ ] 是否为所有需要样式的组件设置了 `objectName`？
- [ ] 是否在 `styles.qss` 中添加了对应的样式定义？
- [ ] 样式命名是否符合规范（`step{数字}_` 前缀）？
- [ ] 是否参考了文档中的代码示例？

**❌ 错误示例（堆砌式开发）**：
```
用户：配置没有自动加载
AI：立即添加一个加载函数，在某个地方调用
问题：没有考虑配置管理的整体设计，可能与其他模块冲突
```

**✅ 正确示例（全局思维）**：
```
用户：配置没有自动加载
AI：
1. 先理解：配置管理应该在哪里？QSettings vs 文件缓存？
2. 先分析：现有代码中配置是如何管理的？是否有统一的设计？
3. 先设计：这个功能应该放在哪个模块？是否符合架构原则？
4. 再实现：按照整体设计实现，而不是零散添加
```

#### 第一步：阅读文档（必须）
1. **先阅读本文档的相关章节**：
   - 开发新功能 → 阅读"需求与功能"、"架构设计"、"代码组织指南"
   - 修改现有功能 → 阅读"实现逻辑"中对应的模块说明
   - 修改UI → 阅读"架构设计" → "UI层职责"
   - 修改业务逻辑 → 阅读"架构设计" → "Core层职责"

2. **明确代码应该放在哪里**：
   - 参考"代码组织指南" → "新增功能时的判断流程"
   - 参考"代码组织指南" → "代码放置检查清单"

3. **明确开发规范**：
   - 阅读"开发规范" → "QGIS插件开发规范"
   - 阅读"开发规范" → "代码质量规范"

#### 第二步：开发代码
1. **严格按照全局思维分析的结果开发**：
   - 遵循架构设计原则（不是堆砌功能）
   - 代码放在正确的位置（符合整体架构）
   - 遵循开发规范
   - **确保改动是系统性的，而非零散的**

2. **开发过程中的全局思维检查**：
   - 这个改动是否破坏了分层架构？
   - 这个改动是否引入了不必要的耦合？
   - 这个改动是否符合单一职责原则？
   - 这个改动是否与现有设计模式一致？

3. **如果文档中没有明确说明**：
   - 先进行全局思维分析
   - 先询问用户或查阅相关章节
   - 不要自行决定或堆砌功能

#### 第三步：更新文档（必须）
1. **同步更新文档**：
   - 新功能 → 更新"需求与功能"
   - 架构变更 → 更新"架构设计"
   - 新增模块 → 更新"实现逻辑"
   - 完成工作 → 更新"开发状态"
   - 记录变更 → 更新"更新日志"

2. **确保文档与实际代码一致**

#### 第四步：代码审查（必须）
使用 [AI_DEVELOPMENT_CHECKLIST.md](AI_DEVELOPMENT_CHECKLIST.md) 中的检查清单验证代码，确保所有检查项都通过。

### 📚 相关文档

- **[AI_DEVELOPMENT_CHECKLIST.md](AI_DEVELOPMENT_CHECKLIST.md)** - ⚠️ **强制检查清单**（每次开发前必须完成，包含完整的工作流程和检查项）
- **[AI_QUICK_REFERENCE.md](AI_QUICK_REFERENCE.md)** - 最常用的提示词，一键复制使用
- **[AI_PROMPT_TEMPLATE.md](AI_PROMPT_TEMPLATE.md)** - 完整提示词模板库
- **[AI_PROMPT_EXAMPLES.md](AI_PROMPT_EXAMPLES.md)** - 实际使用示例和技巧

**快速开始**：
1. **先查看** [AI_DEVELOPMENT_CHECKLIST.md](AI_DEVELOPMENT_CHECKLIST.md) 了解强制检查清单和工作流程
2. **使用** [AI_QUICK_REFERENCE.md](AI_QUICK_REFERENCE.md) 中的提示词模板

> **💡 提示**：详细的提示词模板和示例请查看独立的文档文件，本文档只保留核心工作流程说明。

### 文档更新要求

当AI助手实现新功能或修改代码时，必须同步更新文档：

1. **新功能** → 更新"需求与功能"、"实现逻辑"、"开发状态"、"更新日志"
2. **架构变更** → 更新"架构设计"、"开发状态"、"更新日志"
3. **Bug修复** → 更新"更新日志"

**详细流程和示例请查看** [AI_PROMPT_EXAMPLES.md](AI_PROMPT_EXAMPLES.md)

### 快速参考

**代码应该放在哪里？**
- UI组件 → `ui/`
- 业务逻辑 → `core/`
- 工具函数 → `utils/` 或 `ui/utils.py`（UI相关）

**如何判断？**
参考"代码组织指南" → "新增功能时的判断流程"

**完整检查清单？**
查看 [AI_DEVELOPMENT_CHECKLIST.md](AI_DEVELOPMENT_CHECKLIST.md)

---

**文档维护说明**: 
- 本文档是项目的唯一权威文档
- 所有代码修改和架构变更都应在此文档中更新
- 删除其他冗余文档，保持文档单一性
- 每次重要变更后更新"更新日志"部分

