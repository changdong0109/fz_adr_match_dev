# -*- coding: utf-8 -*-
"""
智能多层级地址匹配引擎

核心设计：
1. 读取 Step2 配置获取核心匹配字段（combo_config.json 最后一个字段）
2. 读取 Step3 智能关系获取辅助信息（field_relations.json）
3. 多层级匹配：精确 → 高置信度 → 需确认 → 未匹配
4. 分层输出结果
"""
import os
import json
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Callable, Tuple, Any

# RapidFuzz
try:
    from rapidfuzz import fuzz, process
    HAS_RAPIDFUZZ = True
except ImportError:
    HAS_RAPIDFUZZ = False
    fuzz = None
    process = None


class SmartMatcher:
    """智能多层级地址匹配器"""
    
    # 匹配层级定义
    LEVELS = {
        'EXACT': {'name': '精确匹配', 'color': '🟢', 'need_review': False},
        'HIGH_CONFIDENCE': {'name': '高置信度', 'color': '🔵', 'need_review': False},
        'NEED_REVIEW': {'name': '需人工确认', 'color': '🟡', 'need_review': True},
        'UNMATCHED': {'name': '未匹配', 'color': '⚪', 'need_review': False}
    }
    
    # 默认阈值
    DEFAULT_THRESHOLDS = {
        'high_confidence_min': 95,
        'high_confidence_with_constraint_min': 92,
        'need_review_min': 88,
        'need_review_max': 95
    }
    
    def __init__(self, 
                 global_config,
                 log_callback: Optional[Callable[[str, str], None]] = None,
                 progress_callback: Optional[Callable[[int, int, str], None]] = None):
        self.global_config = global_config
        self._log = log_callback or (lambda m, l: None)
        self._progress = progress_callback or (lambda c, t, m: None)
        
        self._cache_folder = ""
        self._field_relations = {}
        self._match_config = {}
        self._combo_configs = {}
        
        self._load_configs()
    
    def _load_configs(self):
        """加载所有配置"""
        if not self.global_config:
            return
        
        region_info = self.global_config.get_region_info()
        self._cache_folder = region_info.get('cache_folder', '')
        
        if not self._cache_folder:
            return
        
        # 加载智能关系
        relations_file = os.path.join(self._cache_folder, 'field_relations.json')
        if os.path.exists(relations_file):
            try:
                with open(relations_file, 'r', encoding='utf-8') as f:
                    self._field_relations = json.load(f)
                self._log("[SmartMatcher] 已加载智能关系配置", "debug")
            except Exception as e:
                self._log(f"[SmartMatcher] 加载智能关系失败: {e}", "warning")
        
        # 加载匹配阈值配置
        config_file = os.path.join(self._cache_folder, 'match_config.json')
        if os.path.exists(config_file):
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    self._match_config = json.load(f)
                self._log("[SmartMatcher] 已加载匹配阈值配置", "debug")
            except Exception as e:
                self._log(f"[SmartMatcher] 加载匹配配置失败: {e}", "warning")
    
    def _load_combo_config(self, filename: str) -> Optional[Dict]:
        """加载 Step2 的字段组合配置"""
        if filename in self._combo_configs:
            return self._combo_configs[filename]
        
        # 去掉 _标准化 后缀
        base_name = filename.replace('_标准化.csv', '').replace('.csv', '')
        config_file = os.path.join(self._cache_folder, f"{base_name}_combo_config.json")
        
        if os.path.exists(config_file):
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    self._combo_configs[filename] = config
                    return config
            except Exception:
                pass
        
        return None
    
    def _get_core_match_field(self, filename: str) -> Optional[str]:
        """获取核心匹配字段（Step2 配置的最后一个字段）"""
        config = self._load_combo_config(filename)
        if config and config.get('fields'):
            fields = config['fields']
            if fields:
                return fields[-1].get('field')
        return None
    
    def _get_thresholds(self) -> Dict:
        """获取匹配阈值"""
        thresholds = self._match_config.get('thresholds', {})
        return {
            'high_confidence_min': thresholds.get('high_confidence', {}).get('fuzzy_min', 
                                   self.DEFAULT_THRESHOLDS['high_confidence_min']),
            'high_confidence_with_constraint_min': thresholds.get('high_confidence', {}).get('with_constraint_fuzzy_min',
                                   self.DEFAULT_THRESHOLDS['high_confidence_with_constraint_min']),
            'need_review_min': thresholds.get('need_review', {}).get('fuzzy_min',
                               self.DEFAULT_THRESHOLDS['need_review_min']),
            'need_review_max': thresholds.get('need_review', {}).get('fuzzy_max',
                               self.DEFAULT_THRESHOLDS['need_review_max'])
        }
    
    def match(self, 
              source_df: pd.DataFrame, 
              target_df: pd.DataFrame,
              source_file: str,
              target_file: str) -> Dict[str, List[Dict]]:
        """
        执行多层级匹配
        
        Args:
            source_df: 源表 DataFrame
            target_df: 目标表 DataFrame
            source_file: 源表文件名
            target_file: 目标表文件名
        
        Returns:
            {
                'exact': [...],
                'high_confidence': [...],
                'need_review': [...],
                'unmatched': [...]
            }
        """
        if not HAS_RAPIDFUZZ:
            self._log("[SmartMatcher] 缺少 rapidfuzz 库", "error")
            return self._empty_results()
        
        # 获取核心匹配字段
        source_core = self._get_core_match_field(source_file)
        target_core = self._get_core_match_field(target_file)
        
        self._log(f"[SmartMatcher] 源表核心字段: {source_core}", "info")
        self._log(f"[SmartMatcher] 目标表核心字段: {target_core}", "info")
        
        thresholds = self._get_thresholds()
        
        results = {
            'exact': [],
            'high_confidence': [],
            'need_review': [],
            'unmatched': []
        }
        
        matched_source_indices = set()
        total_source = len(source_df)
        
        # ===== 层级1：精确匹配 =====
        self._progress(5, 100, "执行精确匹配...")
        self._log("[SmartMatcher] 层级1: 精确匹配", "info")
        
        # 1.1 核心字段精确匹配
        if source_core and target_core:
            if source_core in source_df.columns and target_core in target_df.columns:
                exact = self._exact_match_by_field(
                    source_df, target_df, source_file, target_file,
                    source_core, target_core, 'core_field_exact'
                )
                for m in exact:
                    results['exact'].append(m)
                    matched_source_indices.add(m['source_idx'])
                self._log(f"[SmartMatcher] 核心字段精确匹配: {len(exact)} 条", "info")
        
        # 1.2 POI_结构化精确匹配
        self._progress(15, 100, "POI精确匹配...")
        if 'POI_结构化' in source_df.columns and 'POI_结构化' in target_df.columns:
            remaining_df = source_df[~source_df.index.isin(matched_source_indices)]
            poi_exact = self._exact_match_by_field(
                remaining_df, target_df, source_file, target_file,
                'POI_结构化', 'POI_结构化', 'poi_exact'
            )
            for m in poi_exact:
                results['exact'].append(m)
                matched_source_indices.add(m['source_idx'])
            self._log(f"[SmartMatcher] POI精确匹配: {len(poi_exact)} 条", "info")
        
        # 1.3 标准化POI抽取包含匹配
        self._progress(25, 100, "POI包含匹配...")
        if '标准化POI抽取' in source_df.columns and 'POI_结构化' in target_df.columns:
            remaining_df = source_df[~source_df.index.isin(matched_source_indices)]
            contains = self._poi_contains_match(
                remaining_df, target_df, source_file, target_file
            )
            for m in contains:
                results['exact'].append(m)
                matched_source_indices.add(m['source_idx'])
            self._log(f"[SmartMatcher] POI包含匹配: {len(contains)} 条", "info")
        
        # ===== 层级2：高置信度匹配 =====
        self._progress(40, 100, "执行高置信度匹配...")
        self._log("[SmartMatcher] 层级2: 高置信度匹配", "info")
        
        remaining_df = source_df[~source_df.index.isin(matched_source_indices)]
        high_conf = self._fuzzy_match(
            remaining_df, target_df, source_file, target_file,
            min_score=thresholds['high_confidence_min'],
            use_constraint=True,
            constraint_min_score=thresholds['high_confidence_with_constraint_min']
        )
        for m in high_conf:
            m['level'] = 'HIGH_CONFIDENCE'
            results['high_confidence'].append(m)
            matched_source_indices.add(m['source_idx'])
        self._log(f"[SmartMatcher] 高置信度匹配: {len(high_conf)} 条", "info")
        
        # ===== 层级3：需确认匹配 =====
        self._progress(70, 100, "执行需确认匹配...")
        self._log("[SmartMatcher] 层级3: 需确认匹配", "info")
        
        remaining_df = source_df[~source_df.index.isin(matched_source_indices)]
        need_review = self._fuzzy_match(
            remaining_df, target_df, source_file, target_file,
            min_score=thresholds['need_review_min'],
            max_score=thresholds['need_review_max'],
            use_constraint=False
        )
        for m in need_review:
            m['level'] = 'NEED_REVIEW'
            results['need_review'].append(m)
            matched_source_indices.add(m['source_idx'])
        self._log(f"[SmartMatcher] 需确认匹配: {len(need_review)} 条", "info")
        
        # ===== 层级4：未匹配 =====
        self._progress(90, 100, "统计未匹配...")
        remaining_df = source_df[~source_df.index.isin(matched_source_indices)]
        for idx in remaining_df.index:
            row = source_df.loc[idx]
            results['unmatched'].append({
                'source_idx': idx,
                'source_row': idx + 1,
                'source_file': source_file,
                'source_poi': row.get('POI_结构化', ''),
                'level': 'UNMATCHED',
                'match_type': 'unmatched',
                'score': 0
            })
        
        self._progress(100, 100, "匹配完成")
        self._log(f"[SmartMatcher] 完成: 精确{len(results['exact'])}, "
                  f"高置信{len(results['high_confidence'])}, "
                  f"需确认{len(results['need_review'])}, "
                  f"未匹配{len(results['unmatched'])}", "info")
        
        return results
    
    def _exact_match_by_field(self,
                              source_df: pd.DataFrame,
                              target_df: pd.DataFrame,
                              source_file: str,
                              target_file: str,
                              source_field: str,
                              target_field: str,
                              match_type: str) -> List[Dict]:
        """按字段精确匹配"""
        matches = []
        
        # 构建目标表索引
        target_index = {}
        for idx, row in target_df.iterrows():
            val = str(row.get(target_field, '')).strip()
            if val and val != 'nan':
                if val not in target_index:
                    target_index[val] = []
                target_index[val].append((idx, row))
        
        # 匹配
        for idx, row in source_df.iterrows():
            source_val = str(row.get(source_field, '')).strip()
            if not source_val or source_val == 'nan':
                continue
            
            if source_val in target_index:
                target_idx, target_row = target_index[source_val][0]  # 取第一个匹配
                matches.append({
                    'source_idx': idx,
                    'source_row': idx + 1,
                    'source_file': source_file,
                    'source_value': source_val,
                    'source_poi': row.get('POI_结构化', ''),
                    'source_address': row.get('标准化地址', ''),
                    'target_idx': target_idx,
                    'target_row': target_idx + 1,
                    'target_file': target_file,
                    'target_value': source_val,
                    'target_poi': target_row.get('POI_结构化', ''),
                    'target_address': target_row.get('标准化地址', ''),
                    'match_type': match_type,
                    'match_field': f"{source_field}={target_field}",
                    'score': 100.0,
                    'level': 'EXACT'
                })
        
        return matches
    
    def _poi_contains_match(self,
                            source_df: pd.DataFrame,
                            target_df: pd.DataFrame,
                            source_file: str,
                            target_file: str) -> List[Dict]:
        """标准化POI抽取包含目标POI的匹配"""
        matches = []
        
        # 构建目标表POI索引
        target_pois = {}
        for idx, row in target_df.iterrows():
            poi = str(row.get('POI_结构化', '')).strip()
            if poi and poi != 'nan' and len(poi) >= 2:
                target_pois[poi] = (idx, row)
        
        # 匹配
        for idx, row in source_df.iterrows():
            poi_list_str = str(row.get('标准化POI抽取', ''))
            if not poi_list_str or poi_list_str == 'nan':
                continue
            
            # 分号分隔的POI列表
            poi_list = [p.strip() for p in poi_list_str.split(';') if p.strip()]
            
            for target_poi, (target_idx, target_row) in target_pois.items():
                if target_poi in poi_list:
                    matches.append({
                        'source_idx': idx,
                        'source_row': idx + 1,
                        'source_file': source_file,
                        'source_value': poi_list_str[:50],
                        'source_poi': row.get('POI_结构化', ''),
                        'source_address': row.get('标准化地址', ''),
                        'target_idx': target_idx,
                        'target_row': target_idx + 1,
                        'target_file': target_file,
                        'target_value': target_poi,
                        'target_poi': target_poi,
                        'target_address': target_row.get('标准化地址', ''),
                        'match_type': 'poi_contains',
                        'match_field': '标准化POI抽取 contains POI_结构化',
                        'score': 100.0,
                        'level': 'EXACT'
                    })
                    break  # 每个源记录只匹配一次
        
        return matches
    
    def _fuzzy_match(self,
                     source_df: pd.DataFrame,
                     target_df: pd.DataFrame,
                     source_file: str,
                     target_file: str,
                     min_score: float = 88,
                     max_score: float = 100,
                     use_constraint: bool = False,
                     constraint_min_score: float = 92) -> List[Dict]:
        """模糊匹配"""
        matches = []
        
        # 准备目标表POI列表
        target_pois = []
        target_indices = []
        target_districts = []
        
        for idx, row in target_df.iterrows():
            poi = str(row.get('POI_结构化', '')).strip()
            if poi and poi != 'nan':
                target_pois.append(poi)
                target_indices.append(idx)
                target_districts.append(str(row.get('区县', '')).strip())
        
        if not target_pois:
            return matches
        
        # 逐条匹配
        for idx, row in source_df.iterrows():
            source_poi = str(row.get('POI_结构化', '')).strip()
            if not source_poi or source_poi == 'nan':
                continue
            
            source_district = str(row.get('区县', '')).strip()
            
            # 使用 rapidfuzz 找最佳匹配
            result = process.extractOne(
                source_poi,
                target_pois,
                scorer=fuzz.ratio
            )
            
            if not result:
                continue
            
            match_poi, score, match_idx = result
            target_idx = target_indices[match_idx]
            target_district = target_districts[match_idx]
            
            # 判断是否满足条件
            accepted = False
            match_type = ''
            
            if use_constraint and source_district and target_district:
                # 区县相同时，使用较低阈值
                if source_district == target_district and score >= constraint_min_score:
                    accepted = True
                    match_type = f'district_poi_{int(score)}'
                elif score >= min_score:
                    accepted = True
                    match_type = f'poi_fuzzy_{int(score)}'
            else:
                # 无约束，直接判断分数范围
                if min_score <= score <= max_score:
                    accepted = True
                    match_type = f'poi_fuzzy_{int(score)}'
            
            if accepted:
                target_row = target_df.loc[target_idx]
                matches.append({
                    'source_idx': idx,
                    'source_row': idx + 1,
                    'source_file': source_file,
                    'source_value': source_poi,
                    'source_poi': source_poi,
                    'source_address': row.get('标准化地址', ''),
                    'source_district': source_district,
                    'target_idx': target_idx,
                    'target_row': target_idx + 1,
                    'target_file': target_file,
                    'target_value': match_poi,
                    'target_poi': match_poi,
                    'target_address': target_row.get('标准化地址', ''),
                    'target_district': target_district,
                    'match_type': match_type,
                    'match_field': 'POI_结构化',
                    'score': round(score, 2),
                    'district_match': source_district == target_district if source_district and target_district else None
                })
        
        return matches
    
    def _empty_results(self) -> Dict[str, List]:
        """返回空结果"""
        return {
            'exact': [],
            'high_confidence': [],
            'need_review': [],
            'unmatched': []
        }
    
    def get_statistics(self, results: Dict[str, List]) -> Dict:
        """获取匹配统计"""
        total = sum(len(v) for v in results.values())
        exact = len(results.get('exact', []))
        high_conf = len(results.get('high_confidence', []))
        need_review = len(results.get('need_review', []))
        unmatched = len(results.get('unmatched', []))
        
        matched = exact + high_conf + need_review
        
        return {
            'total': total,
            'matched': matched,
            'unmatched': unmatched,
            'match_rate': round(matched / total * 100, 2) if total > 0 else 0,
            'exact': exact,
            'exact_rate': round(exact / total * 100, 2) if total > 0 else 0,
            'high_confidence': high_conf,
            'high_confidence_rate': round(high_conf / total * 100, 2) if total > 0 else 0,
            'need_review': need_review,
            'need_review_rate': round(need_review / total * 100, 2) if total > 0 else 0,
            'auto_match': exact + high_conf,  # 无需人工确认的
            'auto_match_rate': round((exact + high_conf) / total * 100, 2) if total > 0 else 0
        }

