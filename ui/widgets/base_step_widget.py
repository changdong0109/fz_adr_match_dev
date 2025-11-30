"""
基础Step Widget类 - 提供通用功能
"""
from typing import Callable, Optional
from qgis.PyQt.QtWidgets import QWidget
from .task_manager import TaskManager


class BaseStepWidget(QWidget):
    """所有Step Widget的基类"""
    
    def __init__(self, parent=None, log_callback: Optional[Callable[[str, str], None]] = None, 
                 task_manager: Optional[TaskManager] = None):
        super().__init__(parent)
        self.log_callback = log_callback or (lambda msg, level="info": None)
        self.task_manager = task_manager
        if self.task_manager and hasattr(self.task_manager, 'set_log_callback'):
            self.task_manager.set_log_callback(self.log_callback)
    
    def _build_ui(self):
        """子类实现"""
        raise NotImplementedError("子类必须实现_build_ui方法")
    
    def _log(self, msg: str, level: str = "info"):
        """日志输出"""
        self.log_callback(msg, level)
    
    def get_task_manager(self) -> TaskManager:
        """获取任务管理器"""
        if self.task_manager is None:
            from .task_manager import TaskManager
            self.task_manager = TaskManager(self)
            if hasattr(self.task_manager, 'set_log_callback'):
                self.task_manager.set_log_callback(self.log_callback)
        return self.task_manager

