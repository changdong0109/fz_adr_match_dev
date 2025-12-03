# -*- coding: utf-8 -*-
"""
清洗规则配置模块

设计原则：
1. 规则配置化，与清洗逻辑解耦
2. 支持默认规则 + 用户自定义规则
3. 规则可序列化，便于保存和加载
"""
import re
from typing import Dict, List, Set, Optional
from dataclasses import dataclass, field


@dataclass
class CleaningRules:
    """
    清洗规则配置类
    
    使用方式：
        rules = CleaningRules.default()  # 获取默认规则
        rules = CleaningRules.from_dict(config)  # 从配置加载
    """
    
    # ==================== 噪声词配置 ====================
    # 这些词会从文本中移除
    noise_keywords: List[str] = field(default_factory=list)
    
    # 占位词（无意义的词）
    placeholder_words: List[str] = field(default_factory=list)
    
    # ==================== 地址关键词配置 ====================
    # 包含这些关键词的文本被认为是有效地址（不剔除）
    address_keywords: List[str] = field(default_factory=list)
    
    # 村级关键词（包含这些的保留，可用于匹配）
    village_keywords: List[str] = field(default_factory=list)
    
    # ==================== 纯行政区配置 ====================
    # 只有匹配这些模式的才被判定为"纯行政区"并剔除
    pure_admin_patterns: List[str] = field(default_factory=list)
    
    # ==================== 非地址字段名 ====================
    # 配置了这些字段名会触发警告
    non_address_field_names: Set[str] = field(default_factory=set)
    
    # 地址相关字段名关键词
    address_field_keywords: List[str] = field(default_factory=list)
    
    @classmethod
    def default(cls) -> 'CleaningRules':
        """获取默认规则配置"""
        return cls(
            # 噪声关键字
            noise_keywords=[
                # 燃气压力级别
                '高压', '中压', '低压', '高压A', '高压B', '中压A', '中压B',
                '低压A', '低压B', '高压a', '高压b', '中压a', '中压b', '低压a', '低压b',
                # 异常标记
                'nan', 'NaN', 'NAN', 'null', 'NULL', 'None', 'NONE',
                # 技术代号
                '_A', '_B', '_a', '_b'
            ],
            
            # 占位词
            placeholder_words=[
                '无单元', '无号', '无楼', '无栋', '无门', '无室', '无层',
                '无门牌', '无门牌号', '无编号', '无房号',
                '暂无', '未知', '不详', '待定'
            ],
            
            # 具体地址关键词（包含则保留）
            address_keywords=[
                # 建筑标识
                '号', '栋', '楼', '层', '室', '单元', '幢', '座', '门', '排', '户', '期',
                # 住宅小区
                '小区', '花园', '公寓', '大厦', '广场', '中心', '城', '苑', '园', '庄', '庭',
                '府', '湾', '郡', '岸', '里', '坊', '阁', '居', '家园', '嘉园', '佳园',
                '名城', '新城', '家属院', '宿舍', '回迁', '安置', '尊府',
                # 商业场所
                '超市', '商店', '店', '公司', '厂', '企业', '集团', '有限', '商城', '市场',
                '医院', '学校', '学院', '大学', '酒店', '宾馆', '银行', '餐厅', '饭店',
                '食堂', '车间', '仓库', '锅炉', '门脸', '底商',
                # 道路标识
                '路', '道', '街', '巷', '胡同', '弄',
                # GIS设备相关
                '平房', '别墅', '物流', '清真寺', '食品', '门站', '调压',
            ],
            
            # 村级关键词（包含则保留，可用于GIS匹配）
            village_keywords=[
                '镇', '乡', '村', '街道', '社区', '屯', '庄', '营', '寨', '办事处'
            ],
            
            # 纯行政区正则模式（匹配则剔除）
            # 只剔除：xx省、xx市、xx区、xx省xx市、xx市xx区、xx省xx市xx区
            pure_admin_patterns=[
                # 单级
                r'^[\u4e00-\u9fa5]{2,10}(省|自治区)$',
                r'^[\u4e00-\u9fa5]{2,10}市$',
                r'^[\u4e00-\u9fa5]{2,10}(区|县)$',
                # 两级
                r'^[\u4e00-\u9fa5]{2,10}(省|自治区)[\u4e00-\u9fa5]{2,10}市$',
                r'^[\u4e00-\u9fa5]{2,10}市[\u4e00-\u9fa5]{2,10}(区|县)$',
                # 三级
                r'^[\u4e00-\u9fa5]{2,10}(省|自治区)[\u4e00-\u9fa5]{2,10}市[\u4e00-\u9fa5]{2,10}(区|县)$',
            ],
            
            # 非地址字段名（配置这些会警告）
            non_address_field_names={
                'crs', 'epsg', 'geometry', 'gid', 'guid', 'id', 'code', 'dno',
                'angle', 'xcoordinat', 'ycoordinat', 'x', 'y', 'lat', 'lng', 'lon',
                'crttime', 'modtime', 'crtuser', 'moduser', 'data_type',
                'groundelev', 'pipetopele', 'burieddept'
            },
            
            # 地址字段名关键词
            address_field_keywords=[
                'location', 'address', 'addr', 'housingest', 'userlocati',
                '地址', '位置', '住址', '小区', '楼栋', 'buildingno', 'houseno'
            ]
        )
    
    def to_dict(self) -> Dict:
        """序列化为字典"""
        return {
            'noise_keywords': self.noise_keywords,
            'placeholder_words': self.placeholder_words,
            'address_keywords': self.address_keywords,
            'village_keywords': self.village_keywords,
            'pure_admin_patterns': self.pure_admin_patterns,
            'non_address_field_names': list(self.non_address_field_names),
            'address_field_keywords': self.address_field_keywords
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'CleaningRules':
        """从字典加载"""
        return cls(
            noise_keywords=data.get('noise_keywords', []),
            placeholder_words=data.get('placeholder_words', []),
            address_keywords=data.get('address_keywords', []),
            village_keywords=data.get('village_keywords', []),
            pure_admin_patterns=data.get('pure_admin_patterns', []),
            non_address_field_names=set(data.get('non_address_field_names', [])),
            address_field_keywords=data.get('address_field_keywords', [])
        )


class AddressValidator:
    """
    地址验证器
    
    职责：判断文本是否为有效地址
    与清洗器解耦，便于测试和扩展
    """
    
    def __init__(self, rules: Optional[CleaningRules] = None):
        self.rules = rules or CleaningRules.default()
        # 预编译正则
        self._compiled_patterns = [
            re.compile(p) for p in self.rules.pure_admin_patterns
        ]
    
    def is_pure_admin_region(self, text: str) -> bool:
        """
        判断是否为纯行政区（应该剔除）
        
        只有以下格式才剔除：
        - xx省、xx市、xx区
        - xx省xx市、xx市xx区
        - xx省xx市xx区
        
        其他所有情况都保留
        """
        if not text:
            return False
        
        text = text.strip()
        
        # 1. 包含数字则保留
        if re.search(r'\d', text):
            return False
        
        # 2. 包含具体地址关键词则保留
        for keyword in self.rules.address_keywords:
            if keyword in text:
                return False
        
        # 3. 去除非中文字符
        clean_text = re.sub(r'[^\u4e00-\u9fa5]', '', text)
        if not clean_text:
            return True
        
        # 4. 包含村级关键词则保留
        for kw in self.rules.village_keywords:
            if kw in clean_text:
                return False
        
        # 5. 匹配纯行政区模式
        for pattern in self._compiled_patterns:
            if pattern.match(clean_text):
                return True
        
        return False
    
    def has_valid_content(self, text: str) -> bool:
        """检查文本是否有有效地址内容"""
        if not text:
            return False
        
        # 包含中文
        if not re.search(r'[\u4e00-\u9fa5]', text):
            return False
        
        return True


class TextSanitizer:
    """
    文本清洗器
    
    职责：清洗单个文本片段（去噪声、去占位词等）
    """
    
    def __init__(self, rules: Optional[CleaningRules] = None):
        self.rules = rules or CleaningRules.default()
    
    def sanitize(self, text: str) -> str:
        """清洗文本片段"""
        if not text:
            return ""
        
        result = str(text)
        
        # 1. 去除噪声关键字
        for keyword in self.rules.noise_keywords:
            result = result.replace(keyword, '')
        
        # 2. 去除占位词
        for word in self.rules.placeholder_words:
            result = result.replace(word, '')
        
        # 3. 清理连续的"无"
        result = re.sub(r'无(?=\d)', '', result)
        result = re.sub(r'无{2,}', '', result)
        
        return result.strip()


class FieldConfigChecker:
    """
    字段配置检查器
    
    职责：检查用户配置的字段是否合理
    """
    
    def __init__(self, rules: Optional[CleaningRules] = None):
        self.rules = rules or CleaningRules.default()
    
    def check(self, df, fields: List[str], file_name: str) -> List[str]:
        """
        检查字段配置，返回警告列表
        """
        import pandas as pd
        warnings = []
        
        # 检查非地址字段
        bad_fields = [
            f for f in fields 
            if f.lower() in self.rules.non_address_field_names
        ]
        if bad_fields:
            warnings.append(
                f"❌ {file_name}: 配置了非地址字段 [{', '.join(bad_fields)}]"
            )
        
        # 检查字段内容
        no_chinese_fields = []
        for field in fields:
            if field in df.columns:
                sample = df[field].dropna().astype(str).head(100)
                has_chinese = any(
                    bool(re.search(r'[\u4e00-\u9fa5]', str(v)))
                    for v in sample
                )
                if not has_chinese and len(sample) > 0:
                    val = str(sample.iloc[0])[:20]
                    no_chinese_fields.append(f"{field}={val}")
        
        if no_chinese_fields:
            warnings.append(
                f"⚠️ {file_name}: 字段不含中文 [{', '.join(no_chinese_fields)}]"
            )
        
        # 建议可能的地址字段
        suggested = []
        configured_lower = {f.lower() for f in fields}
        for col in df.columns:
            col_lower = col.lower()
            if any(kw in col_lower for kw in self.rules.address_field_keywords):
                if col_lower not in configured_lower:
                    sample = df[col].dropna().astype(str).head(10)
                    has_chinese = any(
                        bool(re.search(r'[\u4e00-\u9fa5]', str(v)))
                        for v in sample
                    )
                    if has_chinese:
                        val = str(sample.iloc[0])[:15] if len(sample) > 0 else ""
                        suggested.append(f"{col}({val})")
        
        if suggested:
            warnings.append(
                f"💡 {file_name}: 建议配置 [{', '.join(suggested[:3])}]"
            )
        
        return warnings

