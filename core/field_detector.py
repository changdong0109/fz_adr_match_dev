"""
字段检测与关联关系推断模块

自动识别常见的地址字段（省、市、区、街道等）、ID 字段、时间字段等，
并推断不同数据源之间的字段关联关系。
"""

import re
from typing import List, Dict, Tuple, Set


class FieldDetector:
    """字段类型检测与关联推断"""

    # 常见地址字段名（中英文变体）
    ADDRESS_FIELD_PATTERNS = {
        'province': ['省', 'province', 'prov', '省份'],
        'city': ['市', 'city', '地级市'],
        'district': ['区', 'district', '县', '旗', '自治区'],
        'street': ['街道', 'street', '街', '路', '道', '巷', '弄'],
        'address': ['地址', 'address', '详细地址', '全地址'],
        'building': ['楼', 'building', '号', '栋'],
        'community': ['社区', 'community', '小区', '园区'],
    }

    # ID/标识字段
    ID_FIELD_PATTERNS = {
        'id': ['id', 'ID', 'uid', 'UID', '编号', '代码', 'code', 'CODE'],
        'name': ['name', 'NAME', '名称', '姓名'],
        'phone': ['phone', 'tel', 'telephone', '电话', '手机'],
        'email': ['email', 'mail', '邮箱'],
    }

    def __init__(self):
        pass

    def detect_field_type(self, field_name: str, sample_values: List = None) -> Dict:
        """
        检测单个字段的类型和用途

        Args:
            field_name: 字段名
            sample_values: 字段值样本（可选，用于更精准的推断）

        Returns:
            {
                'name': str,
                'inferred_type': 'address'|'id'|'numeric'|'date'|'text',
                'category': 'province'|'city'|'district'|'street'|...|None,
                'confidence': float (0-1),
            }
        """
        result = {
            'name': field_name,
            'inferred_type': 'text',
            'category': None,
            'confidence': 0.0,
        }

        # 规范化字段名（去空格、转小写）
        normalized = field_name.strip().lower().replace(' ', '')

        # 检测地址相关字段
        for category, patterns in self.ADDRESS_FIELD_PATTERNS.items():
            for pattern in patterns:
                if normalized.find(pattern.lower()) != -1:
                    result['inferred_type'] = 'address'
                    result['category'] = category
                    result['confidence'] = 0.8
                    break
            if result['category']:
                break

        # 检测 ID/标识字段
        if not result['category']:
            for id_type, patterns in self.ID_FIELD_PATTERNS.items():
                for pattern in patterns:
                    if normalized.find(pattern.lower()) != -1:
                        result['inferred_type'] = id_type
                        result['category'] = id_type
                        result['confidence'] = 0.7
                        break
                if result['category']:
                    break

        # 如果有样本值，进一步推断
        if sample_values:
            result = self._refine_with_samples(result, sample_values)

        return result

    def _refine_with_samples(self, field_info: Dict, sample_values: List) -> Dict:
        """基于样本值进一步精化字段类型推断"""
        if not sample_values:
            return field_info

        # 检查是否全数字（ID/年份/代码）
        numeric_count = sum(1 for v in sample_values if isinstance(v, (int, float)) or (isinstance(v, str) and v.isdigit()))
        numeric_ratio = numeric_count / len(sample_values) if sample_values else 0

        if numeric_ratio > 0.8:
            if field_info['inferred_type'] == 'text':
                field_info['inferred_type'] = 'numeric'
                field_info['confidence'] = 0.6

        # 检查是否包含日期模式
        date_pattern = r'^\d{4}[-/]\d{1,2}[-/]\d{1,2}'
        date_count = sum(1 for v in sample_values if isinstance(v, str) and re.match(date_pattern, v))
        if date_count / len(sample_values) > 0.7:
            field_info['inferred_type'] = 'date'
            field_info['confidence'] = 0.8

        return field_info

    def detect_dataset_fields(self, data: List[Dict]) -> List[Dict]:
        """
        检测整个数据集的所有字段及其类型

        Args:
            data: 数据列表，每条是 dict

        Returns:
            字段信息列表
        """
        if not data:
            return []

        fields = []
        first_row = data[0]

        for field_name in first_row.keys():
            # 收集样本值（前 10 行）
            sample_values = [row.get(field_name) for row in data[:10] if row.get(field_name) is not None]
            field_info = self.detect_field_type(field_name, sample_values)
            fields.append(field_info)

        return fields

    def infer_field_relationships(self, datasets: Dict[str, List[Dict]]) -> List[Tuple]:
        """
        推断不同数据源之间的字段关联关系

        Args:
            datasets: {'source1': [data], 'source2': [data], ...}

        Returns:
            [(source1_field, source2_field, similarity_score), ...]
        """
        relationships = []

        # 获取所有数据源的字段信息
        dataset_fields = {}
        for source_name, data in datasets.items():
            dataset_fields[source_name] = self.detect_dataset_fields(data)

        # 比较不同数据源的字段
        source_names = list(datasets.keys())
        for i in range(len(source_names)):
            for j in range(i + 1, len(source_names)):
                source1, source2 = source_names[i], source_names[j]
                fields1 = dataset_fields[source1]
                fields2 = dataset_fields[source2]

                # 匹配同类字段
                for f1 in fields1:
                    for f2 in fields2:
                        score = self._field_similarity(f1, f2)
                        if score > 0.5:  # 相似度阈值
                            relationships.append((
                                source1, f1['name'],
                                source2, f2['name'],
                                score
                            ))

        return sorted(relationships, key=lambda x: x[4], reverse=True)

    def _field_similarity(self, field1: Dict, field2: Dict) -> float:
        """计算两个字段的相似度（0-1）"""
        score = 0.0

        # 同类字段高相似度
        if field1['category'] and field1['category'] == field2['category']:
            score += 0.8
        # 同类型字段次高相似度
        elif field1['inferred_type'] == field2['inferred_type']:
            score += 0.4

        # 字段名相似度（编辑距离）
        name_sim = self._string_similarity(field1['name'], field2['name'])
        score += name_sim * 0.3

        return min(score, 1.0)

    @staticmethod
    def _string_similarity(s1: str, s2: str) -> float:
        """简单字符串相似度（Levenshtein 比例）"""
        s1 = s1.lower()
        s2 = s2.lower()

        if s1 == s2:
            return 1.0
        if not s1 or not s2:
            return 0.0

        # 简化：如果一个是另一个的子串
        if s1 in s2 or s2 in s1:
            return 0.7

        # 共同字符数 / 最大长度
        common = sum(1 for c in s1 if c in s2)
        return common / max(len(s1), len(s2))
