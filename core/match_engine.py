"""
地址匹配引擎 - 精准匹配 + 模糊匹配
"""

from typing import List, Dict, Tuple, Optional
import difflib
import re


class MatchEngine:
    """多种匹配策略的组合引擎"""

    def __init__(self, fuzzy_threshold: float = 0.7):
        """
        Args:
            fuzzy_threshold: 模糊匹配的相似度阈值 (0-1)
        """
        self.fuzzy_threshold = fuzzy_threshold

    def exact_match(
        self,
        left_data: List[Dict],
        right_data: List[Dict],
        left_key: str,
        right_key: str
    ) -> List[Dict]:
        """
        精准字段匹配

        Args:
            left_data: 左表数据
            right_data: 右表数据
            left_key: 左表匹配字段
            right_key: 右表匹配字段

        Returns:
            匹配结果列表 [{'left': left_row, 'right': right_row, 'match_type': 'exact'}, ...]
        """
        # 建立右表的快速查找索引
        right_index = {}
        for row in right_data:
            key = str(row.get(right_key, '')).strip().lower()
            if key:
                if key not in right_index:
                    right_index[key] = []
                right_index[key].append(row)

        matches = []
        for left_row in left_data:
            left_val = str(left_row.get(left_key, '')).strip().lower()
            if left_val and left_val in right_index:
                for right_row in right_index[left_val]:
                    matches.append({
                        'left': left_row,
                        'right': right_row,
                        'match_type': 'exact',
                        'confidence': 1.0,
                        'matched_field_left': left_key,
                        'matched_field_right': right_key,
                    })

        return matches

    def fuzzy_match(
        self,
        left_data: List[Dict],
        right_data: List[Dict],
        left_key: str,
        right_key: str
    ) -> List[Dict]:
        """
        模糊字段匹配（基于相似度）

        Args:
            left_data: 左表数据
            right_data: 右表数据
            left_key: 左表匹配字段
            right_key: 右表匹配字段

        Returns:
            匹配结果列表
        """
        matches = []

        for left_row in left_data:
            left_val = str(left_row.get(left_key, '')).strip()
            if not left_val:
                continue

            best_match = None
            best_score = 0.0

            for right_row in right_data:
                right_val = str(right_row.get(right_key, '')).strip()
                if not right_val:
                    continue

                # 计算相似度
                score = self._similarity_score(left_val, right_val)

                if score > best_score:
                    best_score = score
                    best_match = right_row

            # 如果相似度超过阈值，记录匹配
            if best_score >= self.fuzzy_threshold and best_match is not None:
                matches.append({
                    'left': left_row,
                    'right': best_match,
                    'match_type': 'fuzzy',
                    'confidence': best_score,
                    'matched_field_left': left_key,
                    'matched_field_right': right_key,
                })

        return matches

    def multi_field_match(
        self,
        left_data: List[Dict],
        right_data: List[Dict],
        field_pairs: List[Tuple[str, str]]
    ) -> List[Dict]:
        """
        多字段组合匹配（如：省 + 市 + 区 + 街道）

        Args:
            left_data: 左表数据
            right_data: 右表数据
            field_pairs: [(left_field, right_field), ...]

        Returns:
            匹配结果列表
        """
        # 建立右表多字段组合索引
        right_index = {}
        for row in right_data:
            key_parts = []
            for _, right_field in field_pairs:
                val = str(row.get(right_field, '')).strip().lower()
                key_parts.append(val)
            key = '|'.join(key_parts)
            if key and not all(p == '' for p in key_parts):
                if key not in right_index:
                    right_index[key] = []
                right_index[key].append(row)

        matches = []
        for left_row in left_data:
            key_parts = []
            for left_field, _ in field_pairs:
                val = str(left_row.get(left_field, '')).strip().lower()
                key_parts.append(val)
            key = '|'.join(key_parts)

            if key and not all(p == '' for p in key_parts):
                if key in right_index:
                    for right_row in right_index[key]:
                        matches.append({
                            'left': left_row,
                            'right': right_row,
                            'match_type': 'multi_field_exact',
                            'confidence': 1.0,
                            'matched_fields': field_pairs,
                        })

        return matches

    @staticmethod
    def _similarity_score(s1: str, s2: str) -> float:
        """
        计算两个字符串的相似度（0-1）
        使用 difflib.SequenceMatcher
        """
        if s1 == s2:
            return 1.0
        
        if not s1 or not s2:
            return 0.0

        # 基础相似度
        matcher = difflib.SequenceMatcher(None, s1, s2)
        ratio = matcher.ratio()

        # 如果长度差异太大，降低分数
        len_diff = abs(len(s1) - len(s2))
        max_len = max(len(s1), len(s2))
        len_penalty = len_diff / max_len * 0.2  # 最多降低 0.2

        return max(0.0, ratio - len_penalty)

    def batch_match(
        self,
        left_data: List[Dict],
        right_data: List[Dict],
        strategies: List[Dict]
    ) -> List[Dict]:
        """
        批量匹配 - 按优先级尝试多种策略

        Args:
            left_data: 左表
            right_data: 右表
            strategies: [
                {'type': 'exact', 'left_key': 'address', 'right_key': 'address'},
                {'type': 'fuzzy', 'left_key': 'address', 'right_key': 'address'},
                ...
            ]

        Returns:
            合并去重后的匹配结果
        """
        all_matches = []
        matched_left_ids = set()

        for strategy in strategies:
            strategy_type = strategy.get('type', 'exact')

            if strategy_type == 'exact':
                matches = self.exact_match(
                    left_data, right_data,
                    strategy['left_key'], strategy['right_key']
                )
            elif strategy_type == 'fuzzy':
                matches = self.fuzzy_match(
                    left_data, right_data,
                    strategy['left_key'], strategy['right_key']
                )
            elif strategy_type == 'multi_field':
                matches = self.multi_field_match(
                    left_data, right_data,
                    strategy['field_pairs']
                )
            else:
                continue

            # 去重：如果左表记录已匹配，跳过
            for match in matches:
                left_id = id(match['left'])
                if left_id not in matched_left_ids:
                    all_matches.append(match)
                    matched_left_ids.add(left_id)

        return all_matches
