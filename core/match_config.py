# -*- coding: utf-8 -*-
"""
匹配配置管理

管理匹配阈值、策略等配置
支持持久化到 match_config.json
"""
import os
import json
from typing import Dict, Optional


class MatchConfig:
    """匹配配置管理器"""
    
    # 默认配置
    DEFAULT_CONFIG = {
        "version": "1.0",
        "thresholds": {
            "exact": {
                "description": "精确匹配 - 无需人工确认",
                "conditions": [
                    "核心匹配字段完全相等",
                    "POI_结构化完全相等",
                    "标准化POI抽取包含目标POI"
                ]
            },
            "high_confidence": {
                "description": "高置信度 - 无需人工确认",
                "fuzzy_min": 95,
                "with_constraint_fuzzy_min": 92
            },
            "need_review": {
                "description": "需人工确认",
                "fuzzy_min": 88,
                "fuzzy_max": 95
            },
            "unmatched": {
                "description": "未匹配",
                "fuzzy_max": 88
            }
        },
        "match_priority": [
            {"type": "exact", "field": "core_field", "description": "Step2配置的核心字段精确匹配"},
            {"type": "exact", "field": "POI_结构化", "description": "Step3生成的POI精确匹配"},
            {"type": "contains", "source": "标准化POI抽取", "target": "POI_结构化", "description": "POI包含匹配"},
            {"type": "fuzzy", "field": "POI_结构化", "with_constraint": True, "description": "区县约束+模糊匹配"},
            {"type": "fuzzy", "field": "POI_结构化", "with_constraint": False, "description": "无约束模糊匹配"}
        ]
    }
    
    def __init__(self, global_config):
        self.global_config = global_config
        self._config = None
        self._config_file = None
        self._load()
    
    def _get_config_file(self) -> str:
        """获取配置文件路径"""
        if self._config_file:
            return self._config_file
        
        if not self.global_config:
            return ""
        
        region_info = self.global_config.get_region_info()
        cache_folder = region_info.get('cache_folder', '')
        
        if cache_folder:
            os.makedirs(cache_folder, exist_ok=True)
            self._config_file = os.path.join(cache_folder, "match_config.json")
        
        return self._config_file or ""
    
    def _load(self):
        """加载配置"""
        config_file = self._get_config_file()
        
        if config_file and os.path.exists(config_file):
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    self._config = json.load(f)
                return
            except Exception:
                pass
        
        # 使用默认配置
        self._config = self.DEFAULT_CONFIG.copy()
    
    def save(self) -> bool:
        """保存配置"""
        config_file = self._get_config_file()
        if not config_file:
            return False
        
        try:
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(self._config, f, ensure_ascii=False, indent=2)
            return True
        except Exception:
            return False
    
    def get(self, key: str, default=None):
        """获取配置项"""
        if not self._config:
            return default
        return self._config.get(key, default)
    
    def get_thresholds(self) -> Dict:
        """获取阈值配置"""
        if not self._config:
            return self.DEFAULT_CONFIG['thresholds']
        return self._config.get('thresholds', self.DEFAULT_CONFIG['thresholds'])
    
    def set_threshold(self, level: str, key: str, value) -> bool:
        """设置阈值"""
        if not self._config:
            self._config = self.DEFAULT_CONFIG.copy()
        
        if 'thresholds' not in self._config:
            self._config['thresholds'] = {}
        
        if level not in self._config['thresholds']:
            self._config['thresholds'][level] = {}
        
        self._config['thresholds'][level][key] = value
        return self.save()
    
    def reset_to_default(self) -> bool:
        """重置为默认配置"""
        self._config = self.DEFAULT_CONFIG.copy()
        return self.save()
    
    @property
    def high_confidence_min(self) -> int:
        """高置信度最低分"""
        thresholds = self.get_thresholds()
        return thresholds.get('high_confidence', {}).get('fuzzy_min', 95)
    
    @property
    def high_confidence_with_constraint_min(self) -> int:
        """带约束的高置信度最低分"""
        thresholds = self.get_thresholds()
        return thresholds.get('high_confidence', {}).get('with_constraint_fuzzy_min', 92)
    
    @property
    def need_review_min(self) -> int:
        """需确认最低分"""
        thresholds = self.get_thresholds()
        return thresholds.get('need_review', {}).get('fuzzy_min', 88)
    
    @property
    def need_review_max(self) -> int:
        """需确认最高分"""
        thresholds = self.get_thresholds()
        return thresholds.get('need_review', {}).get('fuzzy_max', 95)

