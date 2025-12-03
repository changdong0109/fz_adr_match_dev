# -*- coding: utf-8 -*-
"""
匹配任务执行器

使用 SmartMatcher 实现多层级地址匹配：
1. 精确匹配 - 核心字段/POI精确相等
2. 高置信度 - 带约束的模糊匹配 >= 95%
3. 需确认 - 模糊匹配 88-95%
4. 未匹配 - 无匹配结果

分层输出:
- {源表}_精确匹配_{N}条.csv
- {源表}_高置信度_{N}条.csv
- {源表}_需人工确认_{N}条.csv
- {源表}_未匹配_{N}条.csv
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
        self._smart_matcher = None
        self._cancelled = False
    
    def cancel(self):
        """取消执行"""
        self._cancelled = True
    
    @property
    def smart_matcher(self):
        """延迟加载 SmartMatcher"""
        if self._smart_matcher is None:
            from .smart_matcher import SmartMatcher
            self._smart_matcher = SmartMatcher(
                self.global_config,
                log_callback=self._log,
                progress_callback=self._progress
            )
        return self._smart_matcher
    
    def execute_task_group(self, task_group: Dict) -> Dict:
        """执行一个任务组（多层级匹配）"""
        start_time = datetime.now()
        task_name = task_group.get("name", "未命名任务")
        
        self._log(f"[执行器] 开始执行任务组: {task_name}", "info")
        self._progress(2, 100, f"加载源表...")
        
        # 1. 加载源表
        source_file = task_group.get("source", "")
        source_df, source_path = self._load_file(source_file)
        if source_df is None or source_df.empty:
            return self._error_result(task_name, f"源表加载失败: {source_file}")
        
        total_source = len(source_df)
        self._log(f"[执行器] 源表 {source_file}: {total_source} 条", "info")
        self._progress(5, 100, f"源表加载完成: {total_source} 条")
        
        # 2. 获取目标表列表
        targets = task_group.get("targets", [])
        valid_targets = [t for t in targets if t.get("file") or t.get("table")]
        total_targets = len(valid_targets)
        
        if total_targets == 0:
            return self._error_result(task_name, "未配置目标表")
        
        # 3. 初始化全局结果（所有目标表合并）
        all_results = {
            'exact': [],
            'high_confidence': [],
            'need_review': [],
            'unmatched': []
        }
        matched_source_indices = set()
        
        # 记录每个目标表的匹配详情
        target_details = []
        
        # 4. 逐个目标表匹配
        for i, target_config in enumerate(valid_targets):
            if self._cancelled:
                self._log("[执行器] 任务已取消", "warning")
                break
            
            target_file = target_config.get("file", "") or target_config.get("table", "")
            if not target_file:
                continue
            
            # 计算进度
            base_progress = 5 + int((i / max(total_targets, 1)) * 85)
            self._progress(base_progress, 100, f"匹配目标表 ({i+1}/{total_targets}): {target_file}")
            self._log(f"[执行器] 开始匹配目标表: {target_file}", "info")
            
            target_df, target_path = self._load_file(target_file)
            if target_df is None or target_df.empty:
                self._log(f"[执行器] 目标表加载失败: {target_file}", "warning")
                target_details.append({
                    'table': target_file,
                    'total': 0,
                    'exact': 0,
                    'high_confidence': 0,
                    'need_review': 0,
                    'status': '加载失败'
                })
                continue
            
            target_total = len(target_df)
            self._log(f"[执行器] 目标表 {target_file}: {target_total} 条", "info")
            
            # 过滤已匹配的源表记录
            remaining_indices = [idx for idx in source_df.index if idx not in matched_source_indices]
            if not remaining_indices:
                self._log("[执行器] 所有源表记录已匹配完成", "info")
                target_details.append({
                    'table': target_file,
                    'total': target_total,
                    'exact': 0,
                    'high_confidence': 0,
                    'need_review': 0,
                    'status': '无剩余记录'
                })
                break
            
            remaining_df = source_df.loc[remaining_indices].copy()
            self._log(f"[执行器] 剩余未匹配: {len(remaining_df)} 条", "info")
            
            # 执行多层级匹配
            results = self.smart_matcher.match(
                remaining_df, target_df, source_file, target_file
            )
            
            # 记录本目标表的匹配数量
            target_exact = len(results.get('exact', []))
            target_high = len(results.get('high_confidence', []))
            target_review = len(results.get('need_review', []))
            target_matched = target_exact + target_high + target_review
            
            target_details.append({
                'table': target_file,
                'total': target_total,
                'exact': target_exact,
                'high_confidence': target_high,
                'need_review': target_review,
                'matched': target_matched,
                'status': '完成'
            })
            
            # 合并结果
            for level in ['exact', 'high_confidence', 'need_review']:
                for match in results.get(level, []):
                    all_results[level].append(match)
                    matched_source_indices.add(match['source_idx'])
            
            self._log(f"[执行器] 目标表 {target_file} 匹配完成: "
                      f"精确{target_exact}, "
                      f"高置信{target_high}, "
                      f"需确认{target_review}", "info")
        
        # 5. 最终未匹配记录
        final_unmatched_indices = [idx for idx in source_df.index if idx not in matched_source_indices]
        for idx in final_unmatched_indices:
            row = source_df.loc[idx]
            all_results['unmatched'].append({
                'source_idx': idx,
                'source_row': idx + 1,
                'source_file': source_file,
                'source_poi': row.get('POI_结构化', ''),
                'source_address': row.get('标准化地址', ''),
                'level': 'UNMATCHED',
                'match_type': 'unmatched',
                'score': 0
            })
        
        # 6. 统计
        stats = self.smart_matcher.get_statistics(all_results)
        
        # 7. 保存分层结果
        self._progress(95, 100, "保存分层结果...")
        self._save_layered_results(source_file, source_df, all_results)
        
        execution_time = str(datetime.now() - start_time)
        self._progress(100, 100, f"完成: 自动匹配率 {stats['auto_match_rate']}%")
        
        self._log(f"[执行器] 任务完成 ====", "info")
        self._log(f"  总记录: {stats['total']}", "info")
        self._log(f"  精确匹配: {stats['exact']} ({stats['exact_rate']}%)", "info")
        self._log(f"  高置信度: {stats['high_confidence']} ({stats['high_confidence_rate']}%)", "info")
        self._log(f"  需确认: {stats['need_review']} ({stats['need_review_rate']}%)", "info")
        self._log(f"  未匹配: {stats['unmatched']} ({100 - stats['match_rate']}%)", "info")
        self._log(f"  自动匹配率: {stats['auto_match_rate']}%（无需人工确认）", "info")
        self._log(f"  耗时: {execution_time}", "info")
        
        return {
            "success": True,
            "task_name": task_name,
            "results": all_results,
            "statistics": stats,
            "source_file": source_file,
            "source_df": source_df,
            "total_source": total_source,
            "target_details": target_details,  # 每个目标表的匹配详情
            "execution_time": execution_time
        }
    
    def _load_file(self, filename: str) -> tuple:
        """加载文件
        
        搜索目录优先级：
        1. 清洗后数据目录（Step3 标准化结果所在位置）
        2. 原始数据目录
        3. 缓存目录
        """
        if not filename or not self.global_config:
            return None, ""
        
        region_info = self.global_config.get_region_info()
        base_folder = region_info.get('base_folder', '')
        province = region_info.get('province', '')
        city = region_info.get('city', '')
        county = region_info.get('county', '')
        
        # 构建区域前缀
        region_prefix = f"{province}{city}{county}" if county else f"{province}{city}"
        
        # 构建搜索目录列表（优先搜索清洗后数据目录）
        search_folders = []
        
        # 清洗后数据目录（Step3 标准化文件所在位置）
        if base_folder and region_prefix:
            search_folders.append(os.path.join(base_folder, f"{region_prefix}_客户数据清洗", "清洗后数据"))
            search_folders.append(os.path.join(base_folder, f"{region_prefix}_GIS数据清洗", "清洗后数据"))
        
        # 原始数据目录
        customer_folder = region_info.get('customer_folder', '')
        shp_folder = region_info.get('shp_folder', '')
        cache_folder = region_info.get('cache_folder', '')
        
        if customer_folder:
            search_folders.append(customer_folder)
        if shp_folder:
            search_folders.append(shp_folder)
        if cache_folder:
            search_folders.append(cache_folder)
        
        # 搜索文件
        for folder in search_folders:
            if folder and os.path.isdir(folder):
                filepath = os.path.join(folder, filename)
                if os.path.exists(filepath):
                    df = self._read_file(filepath)
                    if df is not None:
                        self._log(f"[执行器] 加载文件: {filepath}", "debug")
                        return df, filepath
        
        # 未找到文件，记录调试信息
        self._log(f"[执行器] 文件未找到: {filename}，搜索目录: {search_folders[:3]}...", "warning")
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
    
    def _save_layered_results(self, source_file: str, source_df: pd.DataFrame, results: Dict):
        """保存分层匹配结果
        
        文件命名格式：
        - {源表}_精确匹配_{N}条.csv
        - {源表}_高置信度_{N}条.csv
        - {源表}_需人工确认_{N}条.csv
        - {源表}_未匹配_{N}条.csv
        """
        if not self.global_config:
            return
        
        region_info = self.global_config.get_region_info()
        cache_folder = region_info.get('cache_folder', '')
        if not cache_folder:
            return
        
        result_dir = os.path.join(cache_folder, "match_results")
        os.makedirs(result_dir, exist_ok=True)
        
        # 源表名（去掉扩展名和"_标准化"后缀）
        source_name = os.path.splitext(source_file)[0].replace("_标准化", "")
        
        def safe_name(name: str) -> str:
            return name.replace(" ", "_").replace("/", "_").replace("\\", "_")
        
        source_safe = safe_name(source_name)
        
        # 收集所有目标表名（用于未匹配时的情况）
        all_target_files = set()
        for level, matches in results.items():
            for m in matches:
                target_file = m.get('target_file', '')
                if target_file:
                    all_target_files.add(target_file)
        
        # 先删除该源表的旧结果文件
        for f in os.listdir(result_dir):
            if f.startswith(source_safe) and f.endswith('.csv'):
                try:
                    os.remove(os.path.join(result_dir, f))
                except Exception:
                    pass
        
        # 定义各层级的中文名
        level_names = {
            'exact': '精确匹配',
            'high_confidence': '高置信度',
            'need_review': '需人工确认',
            'unmatched': '未匹配'
        }
        
        saved_files = []
        
        # 获取源表名（去掉扩展名和_标准化后缀）
        source_name_short = os.path.splitext(source_file)[0].replace("_标准化", "")
        
        # 保存每个层级的结果（包含源表+目标表完整数据）
        for level, matches in results.items():
            if not matches:
                continue
            
            level_name = level_names.get(level, level)
            count = len(matches)
            
            # 构建 DataFrame - 包含完整的源表和目标表数据
            rows = []
            for m in matches:
                row = {}
                
                # 获取目标表名（去掉扩展名和_标准化后缀）
                target_file = m.get('target_file', '')
                if not target_file:
                    # 如果 target_file 为空，尝试从已收集的目标表中获取
                    if all_target_files:
                        # 使用第一个找到的目标表名（通常一个层级只有一个目标表）
                        target_file = list(all_target_files)[0]
                    else:
                        target_file = "未知目标表"
                
                target_name_short = os.path.splitext(target_file)[0].replace("_标准化", "") if target_file else "未知表"
                target_name_short = safe_name(target_name_short)
                
                # 1. 源表完整字段（[源:表名]前缀）
                source_data = m.get('source_row_data', {})
                for k, v in source_data.items():
                    row[f'[源:{source_name_short}]{k}'] = v
                
                # 2. 匹配依据字段（【匹配源:表名】和【匹配目标:表名】前缀，黄色高亮）
                # 解析匹配字段信息，提取源表和目标表的匹配字段及值
                match_field = m.get('match_field', '')
                source_value = m.get('source_value', '')
                target_value = m.get('target_value', '')
                
                # 解析 match_field 格式：如 "name=housingest" 或 "POI_结构化"
                if match_field and '=' in match_field:
                    # 格式：源字段=目标字段
                    parts = match_field.split('=')
                    if len(parts) == 2:
                        source_match_field = parts[0].strip()
                        target_match_field = parts[1].strip()
                        if source_match_field and target_match_field:
                            row[f'【匹配源:{source_name_short}】{source_match_field}'] = source_value
                            row[f'【匹配目标:{target_name_short}】{target_match_field}'] = target_value
                        else:
                            # 字段名为空，使用默认
                            row[f'【匹配源:{source_name_short}】匹配字段'] = source_value
                            row[f'【匹配目标:{target_name_short}】匹配字段'] = target_value
                    else:
                        # 无法解析，使用通用字段
                        row[f'【匹配源:{source_name_short}】匹配值'] = source_value
                        row[f'【匹配目标:{target_name_short}】匹配值'] = target_value
                elif match_field:
                    # 单个字段匹配（如 POI_结构化）
                    match_field_name = match_field.strip()
                    if match_field_name:
                        row[f'【匹配源:{source_name_short}】{match_field_name}'] = source_value
                        row[f'【匹配目标:{target_name_short}】{match_field_name}'] = target_value
                    else:
                        row[f'【匹配源:{source_name_short}】匹配字段'] = source_value
                        row[f'【匹配目标:{target_name_short}】匹配字段'] = target_value
                else:
                    # match_field 为空，使用默认字段名
                    row[f'【匹配源:{source_name_short}】匹配值'] = source_value
                    row[f'【匹配目标:{target_name_short}】匹配值'] = target_value
                
                # 3. 匹配元信息
                row['匹配分数'] = m.get('score', 0)
                row['匹配类型'] = m.get('match_type', '')
                row['匹配层级'] = level_name
                
                # 4. 目标表完整字段（[目标:表名]前缀）- 未匹配时为空
                target_data = m.get('target_row_data', {})
                if target_data:
                    row['目标表文件'] = target_file
                    row['目标表行号'] = m.get('target_row', '')
                    for k, v in target_data.items():
                        row[f'[目标:{target_name_short}]{k}'] = v
                
                rows.append(row)
            
            df = pd.DataFrame(rows)
            
            # 重新排列列顺序：源表 | 匹配依据字段 | 匹配元信息 | 目标表
            source_cols = [c for c in df.columns if c.startswith('[源:')]
            match_source_cols = [c for c in df.columns if c.startswith('【匹配源:')]
            match_target_cols = [c for c in df.columns if c.startswith('【匹配目标:')]
            match_meta_cols = [c for c in df.columns if c in ['匹配分数', '匹配类型', '匹配层级']]
            target_cols = [c for c in df.columns if c.startswith('[目标:') or c in ['目标表文件', '目标表行号']]
            
            # 列顺序：源表 | 匹配源字段 | 匹配目标字段 | 匹配元信息 | 目标表
            ordered_cols = source_cols + match_source_cols + match_target_cols + match_meta_cols + target_cols
            # 添加可能遗漏的列
            for c in df.columns:
                if c not in ordered_cols:
                    ordered_cols.append(c)
            
            df = df[[c for c in ordered_cols if c in df.columns]]
            
            filename = f"{source_safe}_{level_name}_{count}条.csv"
            output_path = os.path.join(result_dir, filename)
            df.to_csv(output_path, index=False, encoding='utf-8-sig')
            saved_files.append(filename)
        
        self._log(f"[执行器] 保存 {len(saved_files)} 个分层结果文件到 match_results/", "info")
        for f in saved_files:
            self._log(f"  - {f}", "debug")
    
    def _error_result(self, task_name: str, message: str) -> Dict:
        """错误结果"""
        self._log(f"[执行器] 失败: {message}", "error")
        return {
            "success": False,
            "task_name": task_name,
            "error": message,
            "results": {},
            "statistics": {},
            "total_source": 0,
            "execution_time": ""
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
        """从文件加载任务组"""
        tasks_file = self._get_tasks_file()
        if not tasks_file:
            return []
        if not os.path.exists(tasks_file):
            return []
        try:
            with open(tasks_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                tasks = data.get("tasks", [])
                return tasks
        except Exception as e:
            print(f"[MatchTaskManager] 加载任务失败: {e}")
            return []
    
    def save_tasks(self, tasks: List[Dict]) -> bool:
        """保存任务组到文件"""
        tasks_file = self._get_tasks_file()
        if not tasks_file:
            return False
        try:
            # 确保目录存在
            os.makedirs(os.path.dirname(tasks_file), exist_ok=True)
            with open(tasks_file, 'w', encoding='utf-8') as f:
                json.dump({"tasks": tasks}, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"[MatchTaskManager] 保存任务失败: {e}")
            return False
