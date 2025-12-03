# -*- coding: utf-8 -*-
"""
通用后台任务 Worker 基类
提供统一的信号、取消机制和错误处理
"""
from qgis.PyQt.QtCore import QThread, pyqtSignal
from typing import Optional, Callable
import traceback


class BaseWorker(QThread):
    """
    后台任务 Worker 基类
    
    所有耗时任务都应继承此类，统一：
    - 进度信号
    - 日志信号
    - 取消机制
    - 错误处理
    
    使用方式：
        class MyWorker(BaseWorker):
            def do_work(self):
                for i in range(100):
                    if self.is_cancelled:
                        return {'cancelled': True}
                    self.emit_progress(i, 100, f"处理中 {i}%")
                    # ... 实际工作
                return {'success': True}
    """
    
    # 通用信号
    progress = pyqtSignal(int, int, str)  # current, total, message
    log = pyqtSignal(str, str)  # message, level
    finished = pyqtSignal(dict)  # result summary
    error = pyqtSignal(str)  # error message
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._is_cancelled = False
    
    @property
    def is_cancelled(self) -> bool:
        """检查是否已取消"""
        return self._is_cancelled
    
    def cancel(self):
        """取消任务"""
        self._is_cancelled = True
    
    def emit_progress(self, current: int, total: int, message: str):
        """发送进度信号"""
        self.progress.emit(current, total, message)
    
    def emit_log(self, message: str, level: str = "info"):
        """发送日志信号"""
        self.log.emit(message, level)
    
    def run(self):
        """执行任务（在后台线程）"""
        try:
            result = self.do_work()
            self.finished.emit(result or {})
        except Exception as e:
            error_msg = f"{str(e)}\n{traceback.format_exc()}"
            self.error.emit(error_msg)
    
    def do_work(self) -> dict:
        """
        实际工作方法，子类必须实现
        
        Returns:
            结果字典，通过 finished 信号发送
        """
        raise NotImplementedError("子类必须实现 do_work 方法")

