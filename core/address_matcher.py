# -*- coding: utf-8 -*-
"""
[已弃用] 高级地址匹配器

⚠️ 警告：此模块已弃用，请使用 poi_matcher.POIMatcher 替代
保留此模块仅为向后兼容

新代码请使用：
    from core.poi_matcher import POIMatcher
    matcher = POIMatcher(log_callback=...)
    result = matcher.match(left_df, right_df, ...)
"""
import warnings
warnings.warn(
    "AddressMatcher 已弃用，请使用 POIMatcher 替代",
    DeprecationWarning,
    stacklevel=2
)

import re
from typing import List, Dict, Optional, Callable
import pandas as pd

try:
    from rapidfuzz import fuzz, process
    HAS_RAPIDFUZZ = True
except ImportError:
    HAS_RAPIDFUZZ = False
    fuzz = None
    process = None


class AddressMatcher:
    """[已弃用] 高级地址匹配器 - 请使用 POIMatcher"""
    
    NON_POI_KEYWORDS = [
        "管路", "管线", "支线", "支管", "分线", "分支",
        "阀室", "阀门", "阀井", "调压", "调压站", "调压柜",
    ]
    
    POI_SUFFIXES = [
        "小区", "家属院", "社区", "花园", "家园",
        "广场", "大厦", "大楼", "公园", "商城",
    ]
    
    def __init__(self, 
                 fuzzy_threshold: float = 0.7,
                 log_callback: Optional[Callable[[str, str], None]] = None):
        self.fuzzy_threshold = fuzzy_threshold
        self._log = log_callback or (lambda msg, level: None)
        self._log("[AddressMatcher] 警告: 此类已弃用，请使用 POIMatcher", "warning")
    
    def match(self,
              source_df: pd.DataFrame,
              target_df: pd.DataFrame,
              field_pairs: List[Dict],
              source_filter: str = "",
              target_filter: str = "") -> Dict:
        """[已弃用] 执行匹配"""
        self._log("[AddressMatcher] match() 已弃用", "warning")
        return {
            "matched": pd.DataFrame(),
            "unmatched_source": source_df,
            "unmatched_target": target_df,
            "stats": {"total": 0, "matched": 0}
        }

