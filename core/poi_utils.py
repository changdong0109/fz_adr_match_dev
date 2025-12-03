# -*- coding: utf-8 -*-
"""
POI公共工具函数
从 poi_matcher.py 和 ali_address_parser.py 抽取，避免重复
"""
import re
from typing import List


# ================== 常量定义 ==================

# 非POI关键词（设备、管线等）
NON_POI_KEYWORDS: List[str] = [
    "管路", "管线", "支线", "支管", "分线", "分支",
    "阀室", "阀门", "阀井",
    "调压", "调压站", "调压柜", "调压箱", "调峰",
    "机房", "配电室", "泵房", "井", "井室",
    "站房", "加气站", "门站",
    "压力计", "供水", "回水", "供热站", "热力站", "锅炉房", "热源厂"
]

# POI后缀（用于判断是否为有效POI）
POI_SUFFIXES: List[str] = [
    "小区", "家属院", "社区", "花园", "家园", "生活区",
    "广场", "大厦", "大楼", "公园", "商城", "市场", "商厦",
    "城邦", "府", "苑", "城", "园", "号院", "公寓", "里",
    "村", "庄", "屯", "乡", "镇", "街", "路",
    "工业园", "产业园", "学院", "大学", "学校",
    "医院", "中心", "公司", "厂"
]


# ================== 工具函数 ==================

def is_pure_numeric(s: str) -> bool:
    """判断是否为纯数字"""
    return bool(re.fullmatch(r"[0-9]+", (s or "").strip()))


def is_non_poi_device(name: str) -> bool:
    """
    判断是否为非POI（设备、管线等）
    这些不应该作为匹配对象
    """
    if not name:
        return False
    s = str(name)
    
    # 调压+数字 模式
    if re.search(r"调[0-9]+", s):
        return True
    
    # 包含非POI关键词
    for kw in NON_POI_KEYWORDS:
        if kw in s:
            return True
    
    return False


def clean_poi_for_fuzzy(poi: str) -> str:
    """
    清洗POI用于模糊匹配
    去除数字、符号、括号内容
    """
    if not poi:
        return ""
    
    # 去除数字、符号
    s = re.sub(r"[0-9#\-]+", "", poi)
    return s.strip()


def is_admin_only_name(name: str) -> bool:
    """
    判断是否仅为行政区划名称（省/市/区/县等）
    这些作为匹配对象价值不大
    """
    if not name:
        return False
    
    n = str(name).strip()
    
    # 以省/市/区/县/乡/镇/街道结尾，且不包含POI后缀
    if re.fullmatch(r".+(省|市|区|县|乡|镇|街道办事处|街道)$", n):
        if not any(suf in n for suf in POI_SUFFIXES):
            return True
    
    return False


def normalize_poi(poi: str) -> str:
    """
    标准化POI名称
    - 去除首尾空格
    - 去除括号及其内容
    - 去除尾部数字编号
    """
    if not poi:
        return ""
    
    s = poi.strip()
    
    # 去除尾部 _数字
    s = re.sub(r"_[0-9]+$", "", s)
    
    # 去除括号内容
    s = re.sub(r"[（(][^（）()]*[)）]", "", s)
    
    return s.strip()


def get_first_poi(poi_str: str, separator: str = ";") -> str:
    """
    从分隔符分隔的POI列表中获取第一个
    """
    if not poi_str:
        return ""
    
    parts = poi_str.split(separator)
    return parts[0].strip() if parts else ""

