# Step5 工具面板 - UI原型设计

## 📋 整体布局结构

参考 Step1、Step2 的实现方式，使用 `CollapsibleSection` 或 `QGroupBox` 组织UI区块。

```
Step5Widget (BaseStepWidget)
└── QVBoxLayout
    ├── CollapsibleSection: "步骤1：加载原始SHP文件" (expanded=True)
    ├── CollapsibleSection: "步骤2：配置验证参数" (expanded=True)
    └── CollapsibleSection: "步骤3：查看验证结果" (expanded=False，验证完成后展开)
```

---

## 🎨 步骤1：加载原始SHP文件

### UI结构

```python
def _card_load_shp(self) -> QWidget:
    """加载原始SHP文件区块"""
    section = CollapsibleSection("步骤1：加载原始SHP文件", expanded=True)
    
    content = QWidget()
    v = QVBoxLayout(content)
    v.setContentsMargins(16, 12, 16, 12)
    v.setSpacing(12)
    
    # 1. SHP文件夹路径显示（使用全局配置）
    folder_row = QHBoxLayout()
    folder_label = QLabel("SHP文件夹：")
    self.shp_folder_display = QLineEdit()
    self.shp_folder_display.setReadOnly(True)  # 只读，使用全局配置
    self.shp_folder_display.setPlaceholderText("从全局配置自动获取")
    folder_row.addWidget(folder_label)
    folder_row.addWidget(self.shp_folder_display)
    v.addLayout(folder_row)
    
    # 2. 文件列表表格
    self.shp_files_table = QTableWidget()
    self.shp_files_table.setColumnCount(4)
    self.shp_files_table.setHorizontalHeaderLabels([
        "选择", "文件名", "大小", "状态"
    ])
    # 设置复选框列
    self.shp_files_table.setColumnWidth(0, 60)
    self.shp_files_table.setColumnWidth(1, 300)
    self.shp_files_table.setColumnWidth(2, 100)
    self.shp_files_table.setColumnWidth(3, 120)
    v.addWidget(self.shp_files_table)
    
    # 3. 操作按钮
    btn_row = QHBoxLayout()
    btn_refresh = QPushButton("刷新文件列表")
    btn_refresh.setObjectName("step5_btn_refresh_shp")
    btn_refresh.clicked.connect(self._refresh_shp_files)
    
    btn_select_all = QPushButton("全选")
    btn_select_all.setObjectName("step5_btn_select_all")
    btn_select_all.clicked.connect(self._select_all_shp_files)
    
    btn_select_none = QPushButton("取消全选")
    btn_select_none.setObjectName("step5_btn_select_none")
    btn_select_none.clicked.connect(self._select_none_shp_files)
    
    btn_load = QPushButton("加载到QGIS")
    btn_load.setObjectName("step5_btn_load_shp")
    btn_load.clicked.connect(self._load_shp_to_qgis)
    
    btn_row.addWidget(btn_refresh)
    btn_row.addWidget(btn_select_all)
    btn_row.addWidget(btn_select_none)
    btn_row.addStretch()
    btn_row.addWidget(btn_load)
    v.addLayout(btn_row)
    
    # 4. 加载进度条
    self.shp_load_progress = QProgressBar()
    self.shp_load_progress.setVisible(False)
    v.addWidget(self.shp_load_progress)
    
    section.add_widget(content)
    return section
```

### 表格设计

```
┌──────┬──────────────┬──────────┬──────────┐
│选择  │文件名        │大小      │状态      │
├──────┼──────────────┼──────────┼──────────┤
│☑    │管网点.shp    │2.3 MB   │已加载    │
│☑    │管网线.shp    │5.1 MB   │已加载    │
│☐    │阀门.shp      │1.2 MB   │未加载    │
└──────┴──────────────┴──────────┴──────────┘
```

---

## 🎨 步骤2：配置验证参数

### UI结构

```python
def _card_validation_config(self) -> QWidget:
    """配置验证参数区块"""
    section = CollapsibleSection("步骤2：配置验证参数", expanded=True)
    
    content = QWidget()
    v = QVBoxLayout(content)
    v.setContentsMargins(16, 12, 16, 12)
    v.setSpacing(16)
    
    # 1. 原始客户数据文件选择
    source_file_group = QGroupBox("原始客户数据文件")
    source_layout = QVBoxLayout(source_file_group)
    
    source_row = QHBoxLayout()
    source_label = QLabel("选择文件：")
    self.source_file_combo = NoWheelComboBox()
    self.source_file_combo.setMinimumWidth(300)
    self.source_file_combo.currentTextChanged.connect(self._on_source_file_changed)
    source_row.addWidget(source_label)
    source_row.addWidget(self.source_file_combo)
    source_row.addStretch()
    source_layout.addLayout(source_row)
    
    # 原始客户数据文件的匹配字段选择（2-3个字段）
    source_fields_label = QLabel("匹配字段（用于在数据库中查找）：")
    source_layout.addWidget(source_fields_label)
    
    source_fields_row = QHBoxLayout()
    source_field1_label = QLabel("字段1（名称）：")
    self.source_field1_combo = NoWheelComboBox()
    source_field2_label = QLabel("字段2（地址）：")
    self.source_field2_combo = NoWheelComboBox()
    source_fields_row.addWidget(source_field1_label)
    source_fields_row.addWidget(self.source_field1_combo)
    source_fields_row.addWidget(source_field2_label)
    source_fields_row.addWidget(self.source_field2_combo)
    source_fields_row.addStretch()
    source_layout.addLayout(source_fields_row)
    
    v.addWidget(source_file_group)
    
    # 2. 匹配结果文件选择
    match_file_group = QGroupBox("匹配结果文件")
    match_layout = QVBoxLayout(match_file_group)
    
    match_row = QHBoxLayout()
    match_label = QLabel("选择文件：")
    self.match_file_combo = NoWheelComboBox()
    self.match_file_combo.setMinimumWidth(300)
    self.match_file_combo.currentTextChanged.connect(self._on_match_file_changed)
    match_row.addWidget(match_label)
    match_row.addWidget(self.match_file_combo)
    match_row.addStretch()
    match_layout.addLayout(match_row)
    
    # 匹配结果文件字段自动检测显示
    match_fields_label = QLabel("检测到的字段：")
    match_layout.addWidget(match_fields_label)
    
    self.match_fields_info = QLabel("选择文件后自动检测...")
    self.match_fields_info.setWordWrap(True)
    match_layout.addWidget(self.match_fields_info)
    
    # 目标表GID字段选择
    target_gid_row = QHBoxLayout()
    target_gid_label = QLabel("目标表GID字段：")
    self.target_gid_combo = NoWheelComboBox()
    target_gid_row.addWidget(target_gid_label)
    target_gid_row.addWidget(self.target_gid_combo)
    target_gid_row.addStretch()
    match_layout.addLayout(target_gid_row)
    
    # 源表匹配字段选择（2-3个字段）
    source_match_row = QHBoxLayout()
    source_match_label = QLabel("源表匹配字段（用于匹配数据库）：")
    match_layout.addWidget(source_match_label)
    
    source_match_fields_row = QHBoxLayout()
    source_match_field1_label = QLabel("字段1：")
    self.source_match_field1_combo = NoWheelComboBox()
    source_match_field2_label = QLabel("字段2：")
    self.source_match_field2_combo = NoWheelComboBox()
    source_match_fields_row.addWidget(source_match_field1_label)
    source_match_fields_row.addWidget(self.source_match_field1_combo)
    source_match_fields_row.addWidget(source_match_field2_label)
    source_match_fields_row.addWidget(self.source_match_field2_combo)
    source_match_fields_row.addStretch()
    match_layout.addLayout(source_match_fields_row)
    
    v.addWidget(match_file_group)
    
    # 3. 图层选择
    layer_group = QGroupBox("图层配置")
    layer_layout = QVBoxLayout(layer_group)
    
    # 原始SHP图层
    shp_layer_row = QHBoxLayout()
    shp_layer_label = QLabel("原始SHP图层：")
    self.original_shp_layer_combo = NoWheelComboBox()
    self.original_shp_layer_combo.setMinimumWidth(250)
    shp_layer_gid_label = QLabel("GID字段：")
    self.original_shp_gid_combo = NoWheelComboBox()
    self.original_shp_gid_combo.setMinimumWidth(120)
    shp_layer_row.addWidget(shp_layer_label)
    shp_layer_row.addWidget(self.original_shp_layer_combo)
    shp_layer_row.addWidget(shp_layer_gid_label)
    shp_layer_row.addWidget(self.original_shp_gid_combo)
    shp_layer_row.addStretch()
    layer_layout.addLayout(shp_layer_row)
    
    # 数据库图层
    db_layer_row = QHBoxLayout()
    db_layer_label = QLabel("数据库图层：")
    self.database_layer_combo = NoWheelComboBox()
    self.database_layer_combo.setMinimumWidth(250)
    self.database_layer_combo.currentTextChanged.connect(self._on_database_layer_changed)
    db_layer_row.addWidget(db_layer_label)
    db_layer_row.addWidget(self.database_layer_combo)
    db_layer_row.addStretch()
    layer_layout.addLayout(db_layer_row)
    
    # 数据库图层匹配字段（2-3个字段，用户手动选择）
    db_match_row = QHBoxLayout()
    db_match_label = QLabel("数据库图层匹配字段：")
    layer_layout.addWidget(db_match_label)
    
    db_match_fields_row = QHBoxLayout()
    db_match_field1_label = QLabel("字段1（名称）：")
    self.database_field1_combo = NoWheelComboBox()
    db_match_field2_label = QLabel("字段2（地址）：")
    self.database_field2_combo = NoWheelComboBox()
    db_match_fields_row.addWidget(db_match_field1_label)
    db_match_fields_row.addWidget(self.database_field1_combo)
    db_match_fields_row.addWidget(db_match_field2_label)
    db_match_fields_row.addWidget(self.database_field2_combo)
    db_match_fields_row.addStretch()
    layer_layout.addLayout(db_match_fields_row)
    
    v.addWidget(layer_group)
    
    # 4. 验证参数
    param_group = QGroupBox("验证参数")
    param_layout = QVBoxLayout(param_group)
    
    threshold_row = QHBoxLayout()
    threshold_label = QLabel("位置偏差阈值（米）：")
    self.distance_threshold_input = QLineEdit()
    self.distance_threshold_input.setText("10.0")
    self.distance_threshold_input.setMaximumWidth(100)
    threshold_row.addWidget(threshold_label)
    threshold_row.addWidget(self.distance_threshold_input)
    threshold_row.addStretch()
    param_layout.addLayout(threshold_row)
    
    crs_check = QCheckBox("自动转换坐标系（如果坐标系不一致）")
    crs_check.setChecked(True)
    self.auto_transform_crs = crs_check
    param_layout.addWidget(crs_check)
    
    v.addWidget(param_group)
    
    # 5. 开始验证按钮
    btn_validate = QPushButton("开始验证")
    btn_validate.setObjectName("step5_btn_validate")
    btn_validate.clicked.connect(self._start_validation)
    v.addWidget(btn_validate)
    
    section.add_widget(content)
    return section
```

---

## 🎨 步骤3：查看验证结果

### UI结构

```python
def _card_validation_results(self) -> QWidget:
    """查看验证结果区块"""
    section = CollapsibleSection("步骤3：查看验证结果", expanded=False)
    
    content = QWidget()
    v = QVBoxLayout(content)
    v.setContentsMargins(16, 12, 16, 12)
    v.setSpacing(16)
    
    # 1. 统计卡片（6个）
    stats_row = QHBoxLayout()
    stats_row.setSpacing(12)
    
    self.stat_source_total = self._create_stat_card("原始数据总数", "0", "blue")
    self.stat_matched_total = self._create_stat_card("匹配总数", "0", "blue")
    self.stat_valid = self._create_stat_card("验证通过", "0", "green")
    self.stat_missing = self._create_stat_card("缺失数据", "0", "red")
    self.stat_deviation = self._create_stat_card("位置偏差", "0", "orange")
    self.stat_duplicate = self._create_stat_card("重复数据", "0", "yellow")
    
    stats_row.addWidget(self.stat_source_total)
    stats_row.addWidget(self.stat_matched_total)
    stats_row.addWidget(self.stat_valid)
    stats_row.addWidget(self.stat_missing)
    stats_row.addWidget(self.stat_deviation)
    stats_row.addWidget(self.stat_duplicate)
    
    v.addLayout(stats_row)
    
    # 2. 统计详情（可折叠）
    stats_detail_section = CollapsibleSection("统计详情", expanded=False)
    stats_detail_content = QWidget()
    stats_detail_layout = QVBoxLayout(stats_detail_content)
    
    self.stats_detail_label = QLabel("验证完成后显示详细统计...")
    self.stats_detail_label.setWordWrap(True)
    stats_detail_layout.addWidget(self.stats_detail_label)
    
    stats_detail_section.add_widget(stats_detail_content)
    v.addWidget(stats_detail_section)
    
    # 3. 问题数据表格
    table_group = QGroupBox("问题数据列表")
    table_layout = QVBoxLayout(table_group)
    
    # 筛选按钮
    filter_row = QHBoxLayout()
    filter_all = QPushButton("全部")
    filter_all.setObjectName("step5_btn_filter_all")
    filter_missing = QPushButton("缺失")
    filter_missing.setObjectName("step5_btn_filter_missing")
    filter_deviation = QPushButton("偏差")
    filter_deviation.setObjectName("step5_btn_filter_deviation")
    filter_duplicate = QPushButton("重复")
    filter_duplicate.setObjectName("step5_btn_filter_duplicate")
    
    filter_row.addWidget(filter_all)
    filter_row.addWidget(filter_missing)
    filter_row.addWidget(filter_deviation)
    filter_row.addWidget(filter_duplicate)
    filter_row.addStretch()
    table_layout.addLayout(filter_row)
    
    # 问题数据表格
    self.problem_table = QTableWidget()
    self.problem_table.setColumnCount(6)
    self.problem_table.setHorizontalHeaderLabels([
        "目标表GID", "源表匹配值", "状态", "偏差距离", "原始坐标", "数据库坐标"
    ])
    table_layout.addWidget(self.problem_table)
    
    # 操作按钮
    action_row = QHBoxLayout()
    btn_zoom = QPushButton("定位")
    btn_zoom.setObjectName("step5_btn_zoom")
    btn_zoom.clicked.connect(self._zoom_to_selected)
    
    btn_export_problems = QPushButton("导出问题数据")
    btn_export_problems.setObjectName("step5_btn_export_problems")
    btn_export_problems.clicked.connect(self._export_problems)
    
    btn_export_duplicate_layer = QPushButton("导出重复数据图层")
    btn_export_duplicate_layer.setObjectName("step5_btn_export_duplicate_layer")
    btn_export_duplicate_layer.clicked.connect(self._export_duplicate_layer)
    
    btn_export_stats = QPushButton("导出统计报告")
    btn_export_stats.setObjectName("step5_btn_export_stats")
    btn_export_stats.clicked.connect(self._export_stats_report)
    
    btn_clear_highlight = QPushButton("清除高亮")
    btn_clear_highlight.setObjectName("step5_btn_clear_highlight")
    btn_clear_highlight.clicked.connect(self._clear_highlight)
    
    action_row.addWidget(btn_zoom)
    action_row.addWidget(btn_export_problems)
    action_row.addWidget(btn_export_duplicate_layer)
    action_row.addWidget(btn_export_stats)
    action_row.addStretch()
    action_row.addWidget(btn_clear_highlight)
    table_layout.addLayout(action_row)
    
    v.addWidget(table_group)
    
    section.add_widget(content)
    return section
```

### 统计卡片设计

```python
def _create_stat_card(self, title: str, value: str, color: str) -> QWidget:
    """创建统计卡片"""
    card = QWidget()
    card.setObjectName(f"step5_stat_card_{color}")
    
    layout = QVBoxLayout(card)
    layout.setContentsMargins(16, 12, 16, 12)
    layout.setSpacing(4)
    
    title_label = QLabel(title)
    title_label.setObjectName("step5_stat_title")
    
    value_label = QLabel(value)
    value_label.setObjectName("step5_stat_value")
    
    layout.addWidget(title_label)
    layout.addWidget(value_label)
    
    return card
```

### 表格设计

```
┌──────────┬──────────────┬──────────┬──────┬──────────┬──────────┐
│目标表GID │源表匹配值    │状态      │偏差  │原始坐标  │数据库坐标│
├──────────┼──────────────┼──────────┼──────┼──────────┼──────────┤
│SHP_001   │客户A|北京市...│❌缺失    │--    │116.123   │--        │
│SHP_002   │客户B|北京市...│⚠️偏差    │15.3m │116.123   │116.124   │
│SHP_003   │客户C|北京市...│🔄重复    │--    │116.123   │(3个点)   │
└──────────┴──────────────┴──────────┴──────┴──────────┴──────────┘
```

---

## 📐 组件尺寸和布局规范

### 参考其他Step Widget的规范

1. **布局边距**：
   - 外层 `QVBoxLayout`：`setContentsMargins(0, 6, 0, 6)`
   - CollapsibleSection 内容：`setContentsMargins(16, 12, 16, 12)`
   - 间距：`setSpacing(12)` 或 `setSpacing(16)`

2. **下拉框宽度**：
   - 文件选择下拉框：`setMinimumWidth(300)`
   - 图层选择下拉框：`setMinimumWidth(250)`
   - 字段选择下拉框：`setMinimumWidth(150)`

3. **按钮样式**：
   - 使用 `objectName` 标识按钮，通过 QSS 文件统一管理样式
   - 命名规则：`step5_btn_{功能名}`

4. **表格设置**：
   - 使用 `QTableWidget`
   - 设置合适的列宽
   - 使用 `setHorizontalHeaderLabels` 设置表头

---

## 🎨 样式定义位置

所有样式定义在 `ui/styles.qss` 文件中，通过 `objectName` 应用：

```qss
/* Step5 统计卡片 */
QWidget#step5_stat_card_blue {
    background-color: #e0ecff;
    border: 1px solid #2563eb;
    border-radius: 4px;
}

QWidget#step5_stat_card_green {
    background-color: #dcfce7;
    border: 1px solid #15803d;
    border-radius: 4px;
}

QWidget#step5_stat_card_red {
    background-color: #fee2e2;
    border: 1px solid #b91c1c;
    border-radius: 4px;
}

QWidget#step5_stat_card_orange {
    background-color: #fed7aa;
    border: 1px solid #ea580c;
    border-radius: 4px;
}

QWidget#step5_stat_card_yellow {
    background-color: #fef3c7;
    border: 1px solid #d97706;
    border-radius: 4px;
}

QLabel#step5_stat_title {
    font-size: 12px;
    color: #6b7280;
}

QLabel#step5_stat_value {
    font-size: 18px;
    font-weight: 600;
    color: #111827;
}

/* Step5 按钮 */
QPushButton#step5_btn_validate {
    background-color: #2563eb;
    color: #ffffff;
    padding: 8px 16px;
    border-radius: 4px;
}

QPushButton#step5_btn_validate:hover {
    background-color: #1d4ed8;
}
```

---

## 📋 关键交互逻辑

1. **文件选择联动**：
   - 选择原始客户数据文件 → 自动加载字段列表
   - 选择匹配结果文件 → 自动检测并填充字段

2. **图层选择联动**：
   - 选择数据库图层 → 自动加载图层字段列表
   - 自动检测 GID 字段（原始SHP图层）

3. **验证完成后的交互**：
   - 自动展开"步骤3：查看验证结果"
   - 更新所有统计卡片
   - 填充问题数据表格
   - 在地图上高亮显示问题数据

4. **统计卡片点击**：
   - 点击统计卡片 → 筛选对应类型的问题数据
   - 在地图上高亮显示对应类型的数据

