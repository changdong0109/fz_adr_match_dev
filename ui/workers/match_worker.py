# -*- coding: utf-8 -*-
"""
匹配执行后台 Worker

使用 QThread 实现，确保：
1. UI 不卡死
2. 进度实时更新
3. 支持取消操作
"""
from qgis.PyQt.QtCore import QThread, pyqtSignal
from typing import List, Dict, Any, Optional


class MatchWorker(QThread):
    """匹配执行后台线程"""
    
    # 信号定义
    progress = pyqtSignal(int, int, str)  # current, total, message
    log = pyqtSignal(str, str)  # message, level
    group_completed = pyqtSignal(str, dict)  # group_name, result
    finished = pyqtSignal(dict)  # summary
    error = pyqtSignal(str)  # error message
    
    def __init__(self, executor, task_groups: List[Dict], parent=None):
        super().__init__(parent)
        self.executor = executor
        self.task_groups = task_groups
        self._cancelled = False
    
    def cancel(self):
        """取消任务"""
        self._cancelled = True
    
    def run(self):
        """执行匹配任务"""
        total = len(self.task_groups)
        success_count = 0
        fail_count = 0
        total_matched = 0
        total_unmatched = 0
        results = []
        
        self.log.emit(f"[匹配任务] 开始处理 {total} 个任务组", "info")
        
        for idx, group in enumerate(self.task_groups):
            if self._cancelled:
                self.log.emit("[匹配任务] 任务已取消", "warning")
                self.finished.emit({'cancelled': True})
                return
            
            group_name = group.get('name', f'任务组{idx + 1}')
            percent = int((idx / total) * 100) if total > 0 else 0
            self.progress.emit(percent, 100, f"匹配 ({idx+1}/{total}): {group_name}")
            self.log.emit(f"[匹配任务] 处理任务组: {group_name}", "info")
            
            try:
                # 构建任务配置
                task_config = {
                    "name": group.get("name", "未命名任务"),
                    "source": group.get("source", ""),
                    "source_filter": group.get("source_filter", ""),
                    "targets": [
                        {
                            "file": t.get("table", ""),
                            "filter": t.get("filter", ""),
                            "match_fields": t.get("match_fields", [])
                        }
                        for t in group.get("targets", []) if t.get("table")
                    ]
                }
                
                # 执行匹配
                result = self.executor.execute_task_group(task_config)
                results.append(result)
                
                if result.get('success'):
                    success_count += 1
                    total_matched += result.get('total_matched', 0)
                    total_unmatched += result.get('total_unmatched', 0)
                    self.log.emit(
                        f"[匹配任务] {group_name} 完成: 匹配{result.get('total_matched', 0)}条",
                        "info"
                    )
                    self.group_completed.emit(group_name, result)
                else:
                    fail_count += 1
                    self.log.emit(
                        f"[匹配任务] {group_name} 失败: {result.get('error', '未知错误')}",
                        "error"
                    )
                    self.group_completed.emit(group_name, result)
                    
            except Exception as e:
                fail_count += 1
                self.log.emit(f"[匹配任务] {group_name} 异常: {e}", "error")
                self.group_completed.emit(group_name, {'success': False, 'error': str(e)})
        
        self.progress.emit(100, 100, f"匹配完成: 成功{success_count}个")
        self.log.emit(
            f"[匹配任务] 全部完成: 成功{success_count}个，失败{fail_count}个，"
            f"匹配{total_matched}条，未匹配{total_unmatched}条",
            "info"
        )
        
        self.finished.emit({
            'success_count': success_count,
            'fail_count': fail_count,
            'total_matched': total_matched,
            'total_unmatched': total_unmatched,
            'results': results
        })

