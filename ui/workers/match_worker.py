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
    
    def __init__(self, executor, task_groups: List[Dict], global_config=None, parent=None):
        super().__init__(parent)
        self.executor = executor
        self.task_groups = task_groups
        self.global_config = global_config
        self._cancelled = False
    
    def cancel(self):
        """取消任务"""
        self._cancelled = True
        # 同时取消执行器
        if hasattr(self.executor, 'cancel'):
            self.executor.cancel()
    
    def _emit_progress(self, current: int, total: int, message: str):
        """线程安全的进度发射"""
        self.progress.emit(current, total, message)
    
    def _emit_log(self, message: str, level: str):
        """线程安全的日志发射"""
        self.log.emit(message, level)
    
    def run(self):
        """执行匹配任务"""
        from ...core.match_executor import MatchExecutor
        
        total_groups = len(self.task_groups)
        success_count = 0
        fail_count = 0
        total_matched = 0
        total_unmatched = 0
        total_exact = 0
        total_high_conf = 0
        total_need_review = 0
        results = []
        
        self._emit_log(f"[匹配任务] 开始处理 {total_groups} 个任务组", "info")
        
        for idx, group in enumerate(self.task_groups):
            if self._cancelled:
                self._emit_log("[匹配任务] 任务已取消", "warning")
                self.finished.emit({'cancelled': True})
                return
            
            group_name = group.get('name', f'任务组{idx + 1}')
            
            # 发射初始进度
            self._emit_progress(0, 100, f"准备任务组: {group_name}")
            self._emit_log(f"[匹配任务] 处理任务组: {group_name}", "info")
            
            try:
                # 创建执行器，传入进度和日志回调
                executor = MatchExecutor(
                    global_config=self.global_config,
                    log_callback=self._emit_log,
                    progress_callback=self._emit_progress
                )
                
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
                result = executor.execute_task_group(task_config)
                results.append(result)
                
                if result.get('success'):
                    success_count += 1
                    # 获取分层统计
                    stats = result.get('statistics', {})
                    total_matched += stats.get('matched', 0)
                    total_unmatched += stats.get('unmatched', 0)
                    total_exact += stats.get('exact', 0)
                    total_high_conf += stats.get('high_confidence', 0)
                    total_need_review += stats.get('need_review', 0)
                    
                    self._emit_log(
                        f"[匹配任务] {group_name} 完成: "
                        f"精确{stats.get('exact', 0)}, "
                        f"高置信{stats.get('high_confidence', 0)}, "
                        f"需确认{stats.get('need_review', 0)}, "
                        f"未匹配{stats.get('unmatched', 0)}",
                        "info"
                    )
                    self.group_completed.emit(group_name, result)
                else:
                    fail_count += 1
                    self._emit_log(
                        f"[匹配任务] {group_name} 失败: {result.get('error', '未知错误')}",
                        "error"
                    )
                    self.group_completed.emit(group_name, result)
                    
            except Exception as e:
                fail_count += 1
                self._emit_log(f"[匹配任务] {group_name} 异常: {e}", "error")
                self.group_completed.emit(group_name, {'success': False, 'error': str(e)})
        
        self._emit_progress(100, 100, f"匹配完成: 成功{success_count}个")
        auto_match = total_exact + total_high_conf
        self._emit_log(
            f"[匹配任务] 全部完成: 成功{success_count}个，失败{fail_count}个，"
            f"自动匹配{auto_match}条（精确{total_exact}+高置信{total_high_conf}），"
            f"需确认{total_need_review}条，未匹配{total_unmatched}条",
            "info"
        )
        
        self.finished.emit({
            'success_count': success_count,
            'fail_count': fail_count,
            'total_matched': total_matched,
            'total_unmatched': total_unmatched,
            'total_exact': total_exact,
            'total_high_confidence': total_high_conf,
            'total_need_review': total_need_review,
            'auto_match': auto_match,
            'results': results
        })

