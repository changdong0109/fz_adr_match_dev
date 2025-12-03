# -*- coding: utf-8 -*-
"""
匹配结果导出后台线程

功能：
- 后台执行导出任务
- 发送进度信号
- 支持取消

参考 Step3 的 RelationExportWorker 实现
"""
from qgis.PyQt.QtCore import QThread, pyqtSignal
import pandas as pd
from typing import List, Optional


class MatchExportWorker(QThread):
    """匹配结果导出 Worker"""
    
    # 信号定义
    progress = pyqtSignal(int, str)  # (percent, message)
    log = pyqtSignal(str, str)       # (message, level)
    finished = pyqtSignal(dict)      # result dict
    error = pyqtSignal(str)          # error message
    
    def __init__(
        self,
        result_files: List[str],
        output_path: str,
        levels: List[str] = None,
        export_format: str = 'excel',  # 'excel' or 'csv'
        source_file: str = "",
        parent=None
    ):
        super().__init__(parent)
        
        self.result_files = result_files
        self.output_path = output_path
        self.levels = levels  # 要导出的层级
        self.export_format = export_format
        self.source_file = source_file
        
        self._cancelled = False
    
    def cancel(self):
        """取消导出"""
        self._cancelled = True
    
    def run(self):
        """执行导出"""
        try:
            from ...core.match_result_exporter import MatchResultExporter
            
            self.progress.emit(5, "准备导出...")
            
            if self._cancelled:
                self.finished.emit({'cancelled': True})
                return
            
            # 创建导出器
            exporter = MatchResultExporter(
                log_callback=lambda m, l: self.log.emit(m, l)
            )
            
            self.progress.emit(10, "读取结果文件...")
            
            # 合并结果文件
            df = exporter.merge_results(self.result_files, self.levels)
            
            if df.empty:
                self.finished.emit({
                    'success': False,
                    'row_count': 0,
                    'message': '没有找到符合条件的数据'
                })
                return
            
            if self._cancelled:
                self.finished.emit({'cancelled': True})
                return
            
            self.progress.emit(20, f"准备导出 {len(df)} 条记录...")
            
            # 定义进度回调
            def on_progress(pct, msg):
                # 映射到 20-100 范围
                mapped_pct = 20 + int(pct * 0.8)
                self.progress.emit(mapped_pct, msg)
            
            # 执行导出
            if self.export_format == 'excel':
                result = exporter.export_to_excel(
                    df, self.output_path, self.source_file, on_progress
                )
            else:
                result = exporter.export_to_csv(
                    df, self.output_path, on_progress
                )
            
            if self._cancelled:
                self.finished.emit({'cancelled': True})
                return
            
            self.finished.emit(result)
            
        except Exception as e:
            self.error.emit(str(e))

