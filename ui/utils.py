"""
UI工具函数模块
提供表格、样式等通用辅助函数
"""
from qgis.PyQt.QtWidgets import QTableWidget, QHeaderView, QAbstractItemView, QTableWidgetItem
from qgis.PyQt.QtCore import Qt


def safe_get_item_flag_enabled():
    """安全获取 ItemIsEnabled 标志（兼容不同PyQt版本）"""
    # 方法1: 尝试使用 Qt.ItemFlag.ItemIsEnabled (PyQt6风格)
    try:
        if hasattr(Qt, 'ItemFlag'):
            ItemFlag = getattr(Qt, 'ItemFlag')
            if hasattr(ItemFlag, 'ItemIsEnabled'):
                return getattr(ItemFlag, 'ItemIsEnabled')
    except (AttributeError, TypeError):
        pass
    
    # 方法2: 尝试使用 Qt.ItemIsEnabled (PyQt5风格)
    try:
        if hasattr(Qt, 'ItemIsEnabled'):
            val = getattr(Qt, 'ItemIsEnabled')
            if not callable(val):
                return val
    except (AttributeError, TypeError):
        pass
    
    # 方法3: 使用数值常量 (ItemIsEnabled = 1)
    return 1


def safe_set_edit_triggers(table: QTableWidget, allow_edit: bool = True):
    """安全设置表格编辑触发器（兼容不同PyQt版本）"""
    if allow_edit:
        # 方法1: 尝试使用 QAbstractItemView.EditTrigger 枚举类
        try:
            # 在PyQt中，EditTrigger 是枚举类
            EditTrigger = getattr(QAbstractItemView, 'EditTrigger', None)
            if EditTrigger is not None:
                # 尝试组合所有编辑触发器
                flags = None
                for trigger_name in ['DoubleClicked', 'SelectedClicked', 'EditKeyPressed', 'AnyKeyPressed']:
                    if hasattr(EditTrigger, trigger_name):
                        trigger_val = getattr(EditTrigger, trigger_name)
                        if flags is None:
                            flags = trigger_val
                        else:
                            flags = flags | trigger_val
                if flags is not None:
                    table.setEditTriggers(flags)
                    return
        except (AttributeError, TypeError, ValueError):
            pass
        
        # 方法2: 尝试使用 QAbstractItemView.EditTriggers 枚举类（PyQt6）
        try:
            EditTriggers = getattr(QAbstractItemView, 'EditTriggers', None)
            if EditTriggers is not None and isinstance(EditTriggers, type):
                if hasattr(EditTriggers, 'AllEditTriggers'):
                    val = getattr(EditTriggers, 'AllEditTriggers')
                    if not callable(val):
                        table.setEditTriggers(val)
                        return
        except (AttributeError, TypeError, ValueError):
            pass
        
        # 方法3: 尝试使用直接属性
        try:
            if hasattr(QAbstractItemView, 'AllEditTriggers'):
                val = getattr(QAbstractItemView, 'AllEditTriggers')
                if not callable(val):
                    table.setEditTriggers(val)
                    return
        except (AttributeError, TypeError, ValueError):
            pass
        
        # 方法4: 尝试使用 QTableWidget 自己的枚举
        try:
            EditTrigger = getattr(table, 'EditTrigger', None)
            if EditTrigger is not None:
                flags = None
                for trigger_name in ['DoubleClicked', 'SelectedClicked', 'EditKeyPressed', 'AnyKeyPressed']:
                    if hasattr(EditTrigger, trigger_name):
                        trigger_val = getattr(EditTrigger, trigger_name)
                        if flags is None:
                            flags = trigger_val
                        else:
                            flags = flags | trigger_val
                if flags is not None:
                    table.setEditTriggers(flags)
                    return
        except (AttributeError, TypeError, ValueError):
            pass
        
        # 方法5: 尝试直接使用 QTableWidget 的属性
        try:
            flags = None
            for attr_name in ['DoubleClicked', 'SelectedClicked', 'EditKeyPressed', 'AnyKeyPressed']:
                if hasattr(table, attr_name):
                    val = getattr(table, attr_name)
                    if not callable(val):
                        if flags is None:
                            flags = val
                        else:
                            flags = flags | val
            if flags is not None:
                table.setEditTriggers(flags)
                return
        except (AttributeError, TypeError, ValueError):
            pass
        
        # 如果所有方法都失败，不设置（使用默认行为，通常是可编辑的）
        # 大多数QTableWidget默认就是可编辑的
        pass
    else:
        # 不可编辑模式
        try:
            EditTrigger = getattr(QAbstractItemView, 'EditTrigger', None)
            if EditTrigger is not None and hasattr(EditTrigger, 'NoEditTriggers'):
                val = getattr(EditTrigger, 'NoEditTriggers')
                if not callable(val):
                    table.setEditTriggers(val)
                    return
        except (AttributeError, TypeError, ValueError):
            pass
        
        try:
            EditTriggers = getattr(QAbstractItemView, 'EditTriggers', None)
            if EditTriggers is not None and isinstance(EditTriggers, type):
                if hasattr(EditTriggers, 'NoEditTriggers'):
                    val = getattr(EditTriggers, 'NoEditTriggers')
                    if not callable(val):
                        table.setEditTriggers(val)
                        return
        except (AttributeError, TypeError, ValueError):
            pass
        
        try:
            if hasattr(QAbstractItemView, 'NoEditTriggers'):
                val = getattr(QAbstractItemView, 'NoEditTriggers')
                if not callable(val):
                    table.setEditTriggers(val)
                    return
        except (AttributeError, TypeError, ValueError):
            pass
        
        try:
            if hasattr(table, 'NoEditTriggers'):
                val = getattr(table, 'NoEditTriggers')
                if not callable(val):
                    table.setEditTriggers(val)
                    return
        except (AttributeError, TypeError, ValueError):
            pass
        
        # 如果所有方法都失败，不设置（使用默认行为）
        pass


def safe_select_rows(table: QTableWidget):
    """安全设置表格为行选择模式"""
    try:
        table.setSelectionBehavior(QTableWidget.SelectRows)
        return
    except Exception:
        pass
    try:
        table.setSelectionBehavior(table.SelectRows)
    except Exception:
        pass


# 向后兼容别名
_safe_select_rows = safe_select_rows


def safe_no_edit(table: QTableWidget):
    """安全设置表格为不可编辑"""
    safe_set_edit_triggers(table, allow_edit=False)


# 向后兼容别名
_safe_no_edit = safe_no_edit


def set_resize_mode(header: QHeaderView, col: int, prefer_contents: bool = False):
    """安全设置表头列宽模式"""
    # 方法1: 尝试使用 QHeaderView.ResizeMode 枚举类
    try:
        ResizeMode = getattr(QHeaderView, 'ResizeMode', None)
        if ResizeMode is not None:
            if prefer_contents:
                if hasattr(ResizeMode, 'ResizeToContents'):
                    mode = getattr(ResizeMode, 'ResizeToContents')
                    header.setSectionResizeMode(col, mode)
                    return
            else:
                if hasattr(ResizeMode, 'Stretch'):
                    mode = getattr(ResizeMode, 'Stretch')
                    header.setSectionResizeMode(col, mode)
                    return
    except (AttributeError, TypeError, ValueError):
        pass
    
    # 方法2: 尝试使用直接属性
    try:
        if prefer_contents:
            if hasattr(QHeaderView, 'ResizeToContents'):
                mode = getattr(QHeaderView, 'ResizeToContents')
                if not callable(mode):
                    header.setSectionResizeMode(col, mode)
                    return
        else:
            if hasattr(QHeaderView, 'Stretch'):
                mode = getattr(QHeaderView, 'Stretch')
                if not callable(mode):
                    header.setSectionResizeMode(col, mode)
                    return
    except (AttributeError, TypeError, ValueError):
        pass
    
    # 方法3: 尝试使用 header 实例的属性
    try:
        if prefer_contents:
            if hasattr(header, 'ResizeToContents'):
                mode = getattr(header, 'ResizeToContents')
                if not callable(mode):
                    header.setSectionResizeMode(col, mode)
                    return
        else:
            if hasattr(header, 'Stretch'):
                mode = getattr(header, 'Stretch')
                if not callable(mode):
                    header.setSectionResizeMode(col, mode)
                    return
    except (AttributeError, TypeError, ValueError):
        pass
    
    # 方法4: 使用数值常量（最后的fallback）
    # ResizeMode 枚举值：
    # Interactive = 0
    # Stretch = 1
    # ResizeToContents = 2
    # Fixed = 3
    try:
        if prefer_contents:
            # ResizeToContents = 2
            header.setSectionResizeMode(col, 2)
        else:
            # Stretch = 1
            header.setSectionResizeMode(col, 1)
    except (AttributeError, TypeError, ValueError):
        # 如果所有方法都失败，不设置（使用默认行为）
        pass


def auto_resize_table_columns(table: QTableWidget, min_col_width: int = 80, max_col_width: int = 300):
    """自动调整表格列宽，确保内容可见"""
    if table.columnCount() == 0:
        return
    
    header = table.horizontalHeader()
    if not header:
        return
    
    # 先根据内容调整
    table.resizeColumnsToContents()
    
    # 确保最小和最大宽度
    for col in range(table.columnCount()):
        current_width = table.columnWidth(col)
        if current_width < min_col_width:
            table.setColumnWidth(col, min_col_width)
        elif current_width > max_col_width:
            table.setColumnWidth(col, max_col_width)
    
    # 让最后一列可以拉伸（如果表格宽度足够）
    if table.columnCount() > 0:
        set_resize_mode(header, table.columnCount() - 1, prefer_contents=False)


# 向后兼容别名
_set_resize_mode = set_resize_mode

