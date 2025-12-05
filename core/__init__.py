# -*- coding: utf-8 -*-
"""
Core模块 - 数据处理与匹配逻辑

主要模块：
- data_loader: 数据加载
- field_detector: 字段检测
- cleaning_rules: 清洗规则配置（可序列化、可自定义）
- data_cleaner: 数据清洗执行器
- ali_address_parser: 阿里云地址解析
- poi_matcher: POI匹配（V11核心逻辑，需要额外依赖）
- poi_utils: POI公共工具函数
- field_relation: 字段关联分析
- export_manager: 导出管理
- match_executor: 匹配任务执行器
"""

# 数据加载
from .data_loader import DataLoader

# 字段检测
from .field_detector import FieldDetector

# 清洗规则配置
from .cleaning_rules import (
    CleaningRules,
    AddressValidator,
    TextSanitizer,
    FieldConfigChecker
)

# 数据清洗
from .data_cleaner import DataCleaner

# 阿里云地址解析
from .ali_address_parser import AliAddressParser

# POI匹配（延迟导入，因为有额外依赖）
# 使用时通过 from core.poi_matcher import POIMatcher 导入
POIMatcher = None  # 占位符，实际使用时延迟导入

def get_poi_matcher():
    """获取 POIMatcher 类（延迟加载）"""
    from .poi_matcher import POIMatcher as _POIMatcher
    return _POIMatcher

# POI工具函数（无额外依赖）
from .poi_utils import (
    NON_POI_KEYWORDS,
    POI_SUFFIXES,
    is_pure_numeric,
    is_non_poi_device,
    clean_poi_for_fuzzy,
    is_admin_only_name,
    normalize_poi,
    get_first_poi
)

# 字段关联分析
from .field_relation import FieldRelationAnalyzer, RelationExporter

# 导出管理
from .export_manager import ExportManager

# 匹配任务执行器（延迟加载 POIMatcher）
from .match_executor import MatchExecutor, MatchTaskManager

# 旧匹配引擎（保留向后兼容）
from .match_engine import MatchEngine
# AddressMatcher 已弃用，不再自动导入
# 如需使用，请直接导入：from core.address_matcher import AddressMatcher


__all__ = [
    # 主要模块
    'DataLoader',
    'FieldDetector',
    'DataCleaner',
    'AliAddressParser',
    'POIMatcher',  # 占位符
    'get_poi_matcher',  # 延迟加载函数
    'FieldRelationAnalyzer',
    'RelationExporter',
    'ExportManager',
    'MatchExecutor',
    'MatchTaskManager',
    
    # 清洗规则模块
    'CleaningRules',
    'AddressValidator',
    'TextSanitizer',
    'FieldConfigChecker',
    
    # POI工具函数
    'NON_POI_KEYWORDS',
    'POI_SUFFIXES',
    'is_pure_numeric',
    'is_non_poi_device',
    'clean_poi_for_fuzzy',
    'is_admin_only_name',
    'normalize_poi',
    'get_first_poi',
    
    # 弃用模块（向后兼容）
    'MatchEngine',
    # 'AddressMatcher',  # 已弃用，不再导出，避免警告
]
