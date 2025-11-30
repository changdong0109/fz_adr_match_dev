"""
任务管理器 - 统一管理进度条和定时器
"""
from typing import Dict, Optional
from qgis.PyQt.QtCore import QTimer, QObject
from qgis.PyQt.QtWidgets import QProgressBar, QLabel


class TaskManager(QObject):
    """任务管理器：统一管理所有任务的进度和定时器"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._timers: Dict[str, QTimer] = {}
        self._log_callback = None
    
    def set_log_callback(self, callback):
        """设置日志回调"""
        self._log_callback = callback
    
    def _log(self, msg: str, level: str = "info"):
        """内部日志"""
        if self._log_callback:
            self._log_callback(msg, level)
    
    def start_task(self, key: str, bar: QProgressBar, lbl: QLabel, text: str):
        """启动任务"""
        # 如果任务已存在，先停止旧任务
        if key in self._timers:
            old_timer = self._timers.pop(key)
            old_timer.stop()
            old_timer.deleteLater()
        # 重置进度条和标签
        if bar:
            bar.setValue(0)
        if lbl:
            lbl.setText(f"{text} 0%")
        timer = QTimer(self)
        timer.setInterval(350)

        def tick():
            if bar is None or lbl is None:
                timer.stop()
                self._timers.pop(key, None)
                return
            val = bar.value() + 7
            if val >= 100:
                val = 100
                timer.stop()
                self._timers.pop(key, None)
                lbl.setText(f"{text} 完成 (100%)")
                self._log(f"[任务] {text} 完成（示意）。", "success")
            else:
                lbl.setText(f"{text} {val}%")
            bar.setValue(val)

        timer.timeout.connect(tick)
        self._timers[key] = timer
        timer.start()
        self._log(f"[任务] {text}")
    
    def pause_task(self, key: str, lbl: Optional[QLabel] = None):
        """暂停任务"""
        t = self._timers.get(key)
        if t:
            t.stop()
            if lbl is not None:
                lbl.setText("暂停")
            self._log(f"[任务] {key} 暂停（示意）。", "warn")
        else:
            self._log(f"[任务] {key} 未运行，无法暂停。", "warn")
    
    def stop_task(self, key: str, bar: Optional[QProgressBar] = None, lbl: Optional[QLabel] = None):
        """停止任务"""
        t = self._timers.pop(key, None)
        if t:
            t.stop()
            t.deleteLater()
        if bar is not None:
            bar.setValue(0)
        if lbl is not None:
            lbl.setText("空闲")
        self._log(f"[任务] {key} 终止并重置（示意）。", "warn")
    
    def has_task(self, key: str) -> bool:
        """检查任务是否存在"""
        return key in self._timers

