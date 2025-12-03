# -*- coding: utf-8 -*-
"""
匹配任务执行器
根据 Step4 的任务配置执行匹配，支持多目标表按优先级匹配
"""
import os
import json
import pandas as pd
from typing import List, Dict, Optional, Callable
from datetime import datetime


class MatchExecutor:
    """匹配任务执行器"""
    
    def __init__(self,
                 global_config,
                 log_callback: Optional[Callable[[str, str], None]] = None,
                 progress_callback: Optional[Callable[[int, int, str], None]] = None):
        self.global_config = global_config
        self._log = log_callback or (lambda msg, level: None)
        self._progress = progress_callback or (lambda c, t, m: None)
        self._poi_matcher = None  # 延迟初始化
    
    @property
    def poi_matcher(self):
        """延迟加载 POIMatcher"""
        if self._poi_matcher is None:
            from .poi_matcher import POIMatcher
            self._poi_matcher = POIMatcher(log_callback=self._log)
        return self._poi_matcher
    
    def execute_task_group(self, task_group: Dict) -> Dict:
        """执行一个任务组"""
        start_time = datetime.now()
        task_name = task_group.get("name", "未命名任务")
        
        self._log(f"[执行器] 开始执行任务组: {task_name}", "info")
        
        # 1. 加载源表
        source_file = task_group.get("source", "")
        source_df, source_path = self._load_file(source_file)
        if source_df is None or source_df.empty:
            return self._error_result(task_name, f"源表加载失败: {source_file}")
        
        total_source = len(source_df)
        self._log(f"[执行器] 源表 {source_file}: {total_source} 条", "info")
        
        # 检测POI列
        poi_col = self._detect_poi_column(source_df)
        if not poi_col:
            return self._error_result(task_name, "源表未找到POI列")
        
        # 2. 执行匹配
        targets = task_group.get("targets", [])
        results = []
        matched_source_indices = set()
        total_matched = 0
        
        for i, target_config in enumerate(targets):
            target_file = target_config.get("file", "") or target_config.get("table", "")
            if not target_file:
                continue
            
            self._progress(i + 1, len(targets), f"匹配目标表: {target_file}")
            
            target_df, target_path = self._load_file(target_file)
            if target_df is None or target_df.empty:
                continue
            
            target_poi_col = self._detect_poi_column(target_df)
            if not target_poi_col:
                continue
            
            # 过滤未匹配的源表记录
            remaining_indices = [idx for idx in range(len(source_df)) if idx not in matched_source_indices]
            remaining_source = source_df.iloc[remaining_indices].copy()
            
            if remaining_source.empty:
                break
            
            # 执行匹配
            matched_df = self.poi_matcher.match(
                left_df=remaining_source,
                right_df=target_df,
                left_file=source_file,
                right_file=target_file,
                left_poi_col=poi_col,
                right_poi_col=target_poi_col
            )
            
            stats = self.poi_matcher.get_match_statistics(matched_df)
            matched_count = stats.get("matched", 0)
            
            # 更新已匹配索引
            if matched_count > 0:
                matched_rows = matched_df[matched_df["是否匹配"] == "是"]
                for _, row in matched_rows.iterrows():
                    orig_row_num = row.get("源表行号", 0)
                    if orig_row_num > 0:
                        matched_source_indices.add(orig_row_num - 1)
            
            total_matched += matched_count
            results.append({
                "target": target_file,
                "matched_df": matched_df,
                "matched_count": matched_count,
                "stats": stats
            })
        
        # 3. 获取未匹配记录
        unmatched_indices = [idx for idx in range(len(source_df)) if idx not in matched_source_indices]
        unmatched_source_df = source_df.iloc[unmatched_indices].copy()
        
        # 4. 保存结果
        execution_time = str(datetime.now() - start_time)
        self._save_result_cache(task_name, results, unmatched_source_df)
        
        self._log(f"[执行器] 完成: 匹配 {total_matched}/{total_source} 条, 耗时 {execution_time}", "info")
        
        return {
            "success": True,
            "task_name": task_name,
            "results": results,
            "unmatched_source_df": unmatched_source_df,
            "total_source": total_source,
            "total_matched": total_matched,
            "total_unmatched": len(unmatched_source_df),
            "execution_time": execution_time
        }
    
    def _detect_poi_column(self, df: pd.DataFrame) -> str:
        """检测POI列"""
        for col in ["标准化POI抽取", "predict_poi", "POI", "poi"]:
            if col in df.columns:
                return col
        return ""
    
    def _load_file(self, filename: str) -> tuple:
        """加载文件"""
        if not filename or not self.global_config:
            return None, ""
        
        region_info = self.global_config.get_region_info()
        for folder in [region_info.get('customer_folder', ''), 
                      region_info.get('shp_folder', ''),
                      region_info.get('cache_folder', '')]:
            if folder and os.path.isdir(folder):
                filepath = os.path.join(folder, filename)
                if os.path.exists(filepath):
                    df = self._read_file(filepath)
                    if df is not None:
                        return df, filepath
        return None, ""
    
    def _read_file(self, filepath: str) -> Optional[pd.DataFrame]:
        """读取文件"""
        try:
            if filepath.lower().endswith('.csv'):
                for enc in ['utf-8', 'gbk', 'gb2312', 'utf-8-sig']:
                    try:
                        return pd.read_csv(filepath, encoding=enc)
                    except UnicodeDecodeError:
                        continue
            elif filepath.lower().endswith(('.xlsx', '.xls')):
                return pd.read_excel(filepath)
        except Exception as e:
            self._log(f"[执行器] 读取失败: {filepath}, {e}", "error")
        return None
    
    def _save_result_cache(self, task_name: str, results: List[Dict], unmatched: pd.DataFrame):
        """保存结果"""
        if not self.global_config:
            return
        
        region_info = self.global_config.get_region_info()
        cache_folder = region_info.get('cache_folder', '')
        if not cache_folder:
            return
        
        result_dir = os.path.join(cache_folder, "match_results")
        os.makedirs(result_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = task_name.replace(" ", "_").replace("/", "_")
        
        for result in results:
            matched_df = result.get("matched_df", pd.DataFrame())
            if matched_df is not None and not matched_df.empty:
                target_name = os.path.splitext(result["target"])[0]
                output_path = os.path.join(result_dir, f"{safe_name}_{target_name}_{timestamp}.csv")
                matched_df.to_csv(output_path, index=False, encoding='utf-8-sig')
        
        if unmatched is not None and not unmatched.empty:
            output_path = os.path.join(result_dir, f"{safe_name}_未匹配_{timestamp}.csv")
            unmatched.to_csv(output_path, index=False, encoding='utf-8-sig')
    
    def _error_result(self, task_name: str, message: str) -> Dict:
        """错误结果"""
        self._log(f"[执行器] 失败: {message}", "error")
        return {
            "success": False,
            "task_name": task_name,
            "error": message,
            "results": [],
            "total_matched": 0,
            "total_unmatched": 0
        }


class MatchTaskManager:
    """任务配置管理器"""
    
    def __init__(self, global_config):
        self.global_config = global_config
        self._tasks_file = None
    
    def _get_tasks_file(self) -> str:
        if self._tasks_file:
            return self._tasks_file
        
        if not self.global_config:
            return ""
        
        region_info = self.global_config.get_region_info()
        cache_folder = region_info.get('cache_folder', '')
        
        if cache_folder:
            os.makedirs(cache_folder, exist_ok=True)
            self._tasks_file = os.path.join(cache_folder, "match_tasks.json")
        
        return self._tasks_file or ""
    
    def load_tasks(self) -> List[Dict]:
        tasks_file = self._get_tasks_file()
        if not tasks_file or not os.path.exists(tasks_file):
            return []
        try:
            with open(tasks_file, 'r', encoding='utf-8') as f:
                return json.load(f).get("tasks", [])
        except Exception:
            return []
    
    def save_tasks(self, tasks: List[Dict]):
        tasks_file = self._get_tasks_file()
        if not tasks_file:
            return
        try:
            with open(tasks_file, 'w', encoding='utf-8') as f:
                json.dump({"tasks": tasks}, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

