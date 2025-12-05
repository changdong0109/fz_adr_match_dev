# Step5 CSV保存和分页功能使用说明

## 功能概述

为了解决大量问题数据渲染导致的UI卡死问题，实现了以下功能：

1. **CSV保存功能**：验证完成后，自动将问题数据保存为CSV文件到cache文件夹
2. **分页显示功能**：表格分页显示，每页100条数据，避免一次性渲染大量数据
3. **分页控件**：提供上一页、下一页、跳转等分页操作

## 文件说明

### 1. `ui/steps/step5_validation_helper.py`
包含CSV保存和分页辅助功能：
- `save_problems_to_csv()`: 保存问题数据为CSV文件
- `PaginationHelper`: 分页辅助类

### 2. `ui/widgets/pagination_widget.py`
分页控件组件，提供完整的分页UI。

## 使用方法

### 1. 在验证完成后保存CSV

```python
from ui.steps.step5_validation_helper import save_problems_to_csv

# 验证完成后
def _on_validation_completed(self, result: Dict):
    problems = result.get('problems', [])
    
    # 获取cache_folder
    global_config = self._get_global_config()
    if global_config:
        region_info = global_config.get_region_info()
        cache_folder = region_info.get('cache_folder', '')
        
        if cache_folder and problems:
            # 保存CSV文件
            csv_path = save_problems_to_csv(
                problems=problems,
                cache_folder=cache_folder,
                identifier="验证结果"  # 可选，用于生成文件名
            )
            
            if csv_path:
                self._log(f"[Step5] 问题数据已保存到: {csv_path}", "info")
```

### 2. 使用分页显示

```python
from ui.steps.step5_validation_helper import PaginationHelper
from ui.widgets.pagination_widget import PaginationWidget

class Step5Widget(BaseStepWidget):
    def __init__(self, ...):
        # ... 其他初始化代码 ...
        
        # 初始化分页辅助类
        self._pagination = PaginationHelper(page_size=100)
        self._all_problems = []  # 存储所有问题数据
        
        # 创建分页控件
        self.pagination_widget = PaginationWidget(self)
        self.pagination_widget.page_changed.connect(self._on_page_changed)
    
    def _on_validation_completed(self, result: Dict):
        """验证完成回调"""
        problems = result.get('problems', [])
        self._all_problems = problems
        
        # 设置分页信息
        self._pagination.set_total_items(len(problems))
        
        # 更新分页控件
        self.pagination_widget.set_pagination(
            current_page=1,
            total_pages=self._pagination.total_pages,
            total_items=len(problems),
            page_size=100
        )
        
        # 显示第一页数据
        self._display_current_page()
        
        # 保存CSV文件
        self._save_problems_to_csv(problems)
    
    def _on_page_changed(self, page: int):
        """页码改变回调"""
        self._pagination.go_to_page(page)
        self._display_current_page()
    
    def _display_current_page(self):
        """显示当前页数据"""
        # 获取当前页数据
        page_data = self._pagination.get_page_data(self._all_problems)
        
        # 更新表格（只显示当前页数据）
        self._update_problem_table(page_data)
    
    def _save_problems_to_csv(self, problems: List[Dict]):
        """保存问题数据为CSV"""
        from ui.steps.step5_validation_helper import save_problems_to_csv
        
        global_config = self._get_global_config()
        if not global_config:
            return
        
        region_info = global_config.get_region_info()
        cache_folder = region_info.get('cache_folder', '')
        
        if cache_folder and problems:
            # 生成标识符（可以使用任务组名称或其他标识）
            identifier = getattr(self, '_current_task_group_name', 'validation')
            
            csv_path = save_problems_to_csv(
                problems=problems,
                cache_folder=cache_folder,
                identifier=identifier
            )
            
            if csv_path:
                self._log(f"[Step5] ✅ 问题数据已保存到CSV: {csv_path}", "success")
                self._log(f"[Step5] 共保存 {len(problems)} 条问题数据", "info")
```

### 3. 在UI中添加分页控件

在构建问题数据表格时，添加分页控件：

```python
def _build_problem_table_section(self):
    """构建问题数据表格区域"""
    section = CollapsibleSection("问题数据列表", expanded=True)
    
    content = QWidget()
    layout = QVBoxLayout(content)
    
    # 表格
    self.problem_table = QTableWidget()
    # ... 设置表格 ...
    layout.addWidget(self.problem_table)
    
    # 分页控件
    self.pagination_widget = PaginationWidget()
    self.pagination_widget.page_changed.connect(self._on_page_changed)
    layout.addWidget(self.pagination_widget)
    
    section.add_widget(content)
    return section
```

## CSV文件格式

保存的CSV文件包含以下列：
- 目标表GID
- 数据库code
- 源表匹配值
- 状态
- 偏差距离
- 原始坐标
- 数据库坐标
- 问题类型

文件命名格式：`验证问题数据_{identifier}_{timestamp}.csv`

例如：`验证问题数据_验证结果_20241201_143025.csv`

## 注意事项

1. **CSV文件编码**：使用UTF-8 with BOM编码，确保Excel可以正确打开中文内容
2. **分页大小**：默认每页100条，可以在`PaginationHelper`初始化时修改
3. **性能优化**：分页显示可以显著提升大量数据时的UI响应速度
4. **CSV文件位置**：保存在`cache_folder`目录下，方便用户查找和打开

## 示例代码

完整的使用示例请参考上述代码片段。主要步骤：

1. 导入必要的模块
2. 初始化分页辅助类和控件
3. 在验证完成时保存CSV并设置分页
4. 实现页码改变回调，更新表格显示
5. 在UI中添加分页控件

