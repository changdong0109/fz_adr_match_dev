# -*- coding: utf-8 -*-
"""
数据清洗后台 Worker

使用 QThread 实现，确保：
1. UI 不卡死
2. 进度实时更新
3. 支持取消操作
"""
from qgis.PyQt.QtCore import QThread, pyqtSignal
from typing import List, Dict, Any, Optional


class CleanWorker(QThread):
    """数据清洗后台线程"""
    
    # 信号定义
    progress = pyqtSignal(int, int, str)  # current, total, message
    log = pyqtSignal(str, str)  # message, level
    file_completed = pyqtSignal(str, dict)  # file_name, result
    finished = pyqtSignal(dict)  # summary
    error = pyqtSignal(str)  # error message
    
    def __init__(self, files: List[Dict], cleaner, output_dir: str,
                 province: str, city: str, county: str, parent=None):
        super().__init__(parent)
        self.files = files
        self.cleaner = cleaner
        self.output_dir = output_dir
        self.province = province
        self.city = city
        self.county = county
        self._cancelled = False
    
    def cancel(self):
        """取消任务"""
        self._cancelled = True
    
    def run(self):
        """执行清洗任务"""
        total = len(self.files)
        success_count = 0
        fail_count = 0
        total_valid = 0
        total_invalid = 0
        has_permission_error = False
        
        self.log.emit(f"[清洗任务] 开始处理 {total} 个文件", "info")
        
        for idx, file_info in enumerate(self.files):
            if self._cancelled:
                self.log.emit("[清洗任务] 任务已取消", "warning")
                self.finished.emit({'cancelled': True})
                return
            
            file_name = file_info['file_name']
            percent = int((idx / total) * 100)
            self.progress.emit(percent, 100, f"清洗 ({idx+1}/{total}): {file_name}")
            self.log.emit(f"[清洗任务] 处理文件: {file_name}", "info")
            
            try:
                result = self.cleaner.clean_file(
                    file_path=file_info['file_path'],
                    field_config=file_info['field_config'],
                    output_dir=self.output_dir,
                    province=self.province,
                    city=self.city,
                    county=self.county,
                    source_type=file_info.get('source_type', '其他')
                )
                
                if result.get('success'):
                    success_count += 1
                    total_valid += result.get('valid_count', 0)
                    total_invalid += result.get('invalid_count', 0)
                    self.log.emit(
                        f"[清洗任务] {file_name} 完成: 有效{result.get('valid_count', 0)}条, "
                        f"剔除{result.get('invalid_count', 0)}条",
                        "info"
                    )
                    self.file_completed.emit(file_name, result)
                else:
                    fail_count += 1
                    error_msg = result.get('error', '未知错误')
                    if 'Permission' in error_msg or '权限' in error_msg:
                        has_permission_error = True
                    self.log.emit(f"[清洗任务] {file_name} 失败: {error_msg}", "error")
                    self.file_completed.emit(file_name, result)
                    
            except Exception as e:
                fail_count += 1
                error_str = str(e)
                if 'Permission' in error_str or '权限' in error_str:
                    has_permission_error = True
                self.log.emit(f"[清洗任务] {file_name} 异常: {e}", "error")
                self.file_completed.emit(file_name, {'success': False, 'error': str(e)})
        
        self.progress.emit(100, 100, f"清洗完成: 成功{success_count}个")
        self.log.emit(
            f"[清洗任务] 全部完成: 成功{success_count}个，失败{fail_count}个，"
            f"有效记录{total_valid}条，剔除{total_invalid}条",
            "info"
        )
        
        self.finished.emit({
            'success_count': success_count,
            'fail_count': fail_count,
            'total_valid': total_valid,
            'total_invalid': total_invalid,
            'has_permission_error': has_permission_error
        })
