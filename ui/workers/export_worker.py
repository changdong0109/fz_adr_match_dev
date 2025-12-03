# -*- coding: utf-8 -*-
"""
结果导出后台 Worker

使用 QThread 实现，确保：
1. UI 不卡死
2. 进度实时更新
3. 支持取消操作
"""
import os
from qgis.PyQt.QtCore import QThread, pyqtSignal
from typing import List, Dict, Any, Optional


class ExportWorker(QThread):
    """结果导出后台线程"""
    
    # 信号定义
    progress = pyqtSignal(int, int, str)  # current, total, message
    log = pyqtSignal(str, str)  # message, level
    file_completed = pyqtSignal(str, dict)  # file_name, result
    finished = pyqtSignal(dict)  # summary
    error = pyqtSignal(str)  # error message
    
    def __init__(self, exporter, export_config: Dict, parent=None):
        super().__init__(parent)
        self.exporter = exporter
        self.export_config = export_config
        self._cancelled = False
    
    def cancel(self):
        """取消任务"""
        self._cancelled = True
    
    def run(self):
        """执行导出任务"""
        export_dir = self.export_config.get('export_dir', '')
        export_types = self.export_config.get('export_types', [])
        output_format = self.export_config.get('output_format', 'xlsx')
        customer_folder = self.export_config.get('customer_folder', '')
        cache_folder = self.export_config.get('cache_folder', '')
        selected_fields = self.export_config.get('selected_fields', [])
        
        total_steps = len(export_types)
        current_step = 0
        total_success = 0
        total_fail = 0
        output_files = []
        
        self.log.emit(f"[导出任务] 开始导出: {', '.join(export_types)}", "info")
        
        try:
            os.makedirs(export_dir, exist_ok=True)
        except Exception as e:
            self.log.emit(f"[导出任务] 创建目录失败: {e}", "error")
            self.finished.emit({'success': False, 'error': str(e)})
            return
        
        # 1. 导出清洗结果
        if "清洗结果" in export_types:
            if self._cancelled:
                self.finished.emit({'cancelled': True})
                return
            
            current_step += 1
            percent = int((current_step / total_steps) * 100) if total_steps > 0 else 0
            self.progress.emit(percent, 100, "导出清洗结果...")
            self.log.emit("[导出任务] 导出清洗结果...", "info")
            
            if customer_folder and os.path.isdir(customer_folder):
                clean_files = [f for f in os.listdir(customer_folder) if f.endswith('_清洗.csv')]
                for f in clean_files:
                    input_path = os.path.join(customer_folder, f)
                    output_name = os.path.splitext(f)[0] + f".{output_format}"
                    output_path = os.path.join(export_dir, output_name)
                    if self.exporter.export_from_file(input_path, output_path, output_format):
                        total_success += 1
                        output_files.append(output_path)
                        self.file_completed.emit(f, {'success': True, 'output': output_path})
                    else:
                        total_fail += 1
                        self.file_completed.emit(f, {'success': False})
        
        # 2. 导出标准化结果
        if "标准化结果" in export_types:
            if self._cancelled:
                self.finished.emit({'cancelled': True})
                return
            
            current_step += 1
            percent = int((current_step / total_steps) * 100) if total_steps > 0 else 0
            self.progress.emit(percent, 100, "导出标准化结果...")
            self.log.emit("[导出任务] 导出标准化结果...", "info")
            
            if customer_folder and os.path.isdir(customer_folder):
                std_files = [f for f in os.listdir(customer_folder) if f.endswith('_标准化.csv')]
                for f in std_files:
                    input_path = os.path.join(customer_folder, f)
                    output_name = os.path.splitext(f)[0] + f".{output_format}"
                    output_path = os.path.join(export_dir, output_name)
                    if self.exporter.export_from_file(input_path, output_path, output_format):
                        total_success += 1
                        output_files.append(output_path)
                        self.file_completed.emit(f, {'success': True, 'output': output_path})
                    else:
                        total_fail += 1
                        self.file_completed.emit(f, {'success': False})
        
        # 3. 导出匹配结果
        if "匹配结果" in export_types:
            if self._cancelled:
                self.finished.emit({'cancelled': True})
                return
            
            current_step += 1
            percent = int((current_step / total_steps) * 100) if total_steps > 0 else 0
            self.progress.emit(percent, 100, "导出匹配结果...")
            self.log.emit("[导出任务] 导出匹配结果...", "info")
            
            if cache_folder and os.path.isdir(cache_folder):
                match_files = [f for f in os.listdir(cache_folder) if f.endswith('_匹配结果.csv')]
                for f in match_files:
                    input_path = os.path.join(cache_folder, f)
                    output_name = os.path.splitext(f)[0] + f".{output_format}"
                    output_path = os.path.join(export_dir, output_name)
                    if self.exporter.export_from_file(input_path, output_path, output_format):
                        total_success += 1
                        output_files.append(output_path)
                        self.file_completed.emit(f, {'success': True, 'output': output_path})
                    else:
                        total_fail += 1
                        self.file_completed.emit(f, {'success': False})
        
        # 4. 导出未匹配数据
        if "未匹配数据" in export_types:
            if self._cancelled:
                self.finished.emit({'cancelled': True})
                return
            
            current_step += 1
            percent = int((current_step / total_steps) * 100) if total_steps > 0 else 0
            self.progress.emit(percent, 100, "导出未匹配数据...")
            self.log.emit("[导出任务] 导出未匹配数据...", "info")
            
            if cache_folder and os.path.isdir(cache_folder):
                unmatch_files = [f for f in os.listdir(cache_folder) if f.endswith('_未匹配.csv')]
                for f in unmatch_files:
                    input_path = os.path.join(cache_folder, f)
                    output_name = os.path.splitext(f)[0] + f".{output_format}"
                    output_path = os.path.join(export_dir, output_name)
                    if self.exporter.export_from_file(input_path, output_path, output_format):
                        total_success += 1
                        output_files.append(output_path)
                        self.file_completed.emit(f, {'success': True, 'output': output_path})
                    else:
                        total_fail += 1
                        self.file_completed.emit(f, {'success': False})
        
        # 5. 导出关联分析结果
        if "关联分析结果" in export_types:
            if self._cancelled:
                self.finished.emit({'cancelled': True})
                return
            
            current_step += 1
            percent = int((current_step / total_steps) * 100) if total_steps > 0 else 0
            self.progress.emit(percent, 100, "导出关联分析结果...")
            self.log.emit("[导出任务] 导出关联分析结果...", "info")
            
            if cache_folder and os.path.isdir(cache_folder):
                relation_files = [f for f in os.listdir(cache_folder) if '关联' in f and f.endswith('.csv')]
                for f in relation_files:
                    input_path = os.path.join(cache_folder, f)
                    output_name = os.path.splitext(f)[0] + f".{output_format}"
                    output_path = os.path.join(export_dir, output_name)
                    if self.exporter.export_from_file(input_path, output_path, output_format):
                        total_success += 1
                        output_files.append(output_path)
                        self.file_completed.emit(f, {'success': True, 'output': output_path})
                    else:
                        total_fail += 1
                        self.file_completed.emit(f, {'success': False})
        
        self.progress.emit(100, 100, f"导出完成: 成功{total_success}个")
        self.log.emit(
            f"[导出任务] 全部完成: 成功{total_success}个，失败{total_fail}个",
            "info"
        )
        
        self.finished.emit({
            'success_count': total_success,
            'fail_count': total_fail,
            'output_files': output_files,
            'export_dir': export_dir
        })

