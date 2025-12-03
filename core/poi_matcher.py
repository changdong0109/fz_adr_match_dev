# -*- coding: utf-8 -*-
"""
POI匹配引擎 - 基于V11逻辑
直接使用Step3产出的POI数据进行匹配（不再调用API）

匹配优先级：模糊强(90) → 语义强(0.82) → 语义弱(0.75) → 模糊弱(75)

输出字段（产品化）：
- 源表：文件名、行号、名称、标准化地址、POI
- 目标表：文件名、行号、名称、标准化地址、POI
- 匹配信息：匹配类型、匹配分数、POI来源
"""
import os
import re
from typing import Dict, Any, List, Tuple, Optional, Callable
import pandas as pd
import numpy as np

# 导入公共工具函数
from .poi_utils import (
    NON_POI_KEYWORDS, POI_SUFFIXES,
    is_pure_numeric, is_non_poi_device, 
    clean_poi_for_fuzzy, is_admin_only_name
)

# RapidFuzz - 延迟检查
HAS_RAPIDFUZZ = False
RAPIDFUZZ_ERROR = None
fuzz = None
process = None
try:
    from rapidfuzz import fuzz, process
    HAS_RAPIDFUZZ = True
except Exception as e:
    RAPIDFUZZ_ERROR = str(e)

# SentenceTransformer - 延迟检查
HAS_SENTENCE_TRANSFORMER = False
SENTENCE_TRANSFORMER_ERROR = None
SentenceTransformer = None
try:
    from sentence_transformers import SentenceTransformer
    HAS_SENTENCE_TRANSFORMER = True
except Exception as e:
    SENTENCE_TRANSFORMER_ERROR = str(e)


# ================== 模型与匹配参数（V11原样保留） ==================
EMB_MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
FUZZY_STRONG_THRESHOLD = 90
FUZZY_WEAK_THRESHOLD = 75
SEMANTIC_STRONG = 0.82
SEMANTIC_WEAK = 0.75


class POIMatcher:
    """
    POI匹配器
    使用Step3产出的POI数据进行匹配
    """
    
    def __init__(self, log_callback: Optional[Callable[[str, str], None]] = None):
        self._log = log_callback or (lambda msg, level: None)
        self._model = None
        self._model_loaded = False
        self._dependencies_checked = False
    
    def _check_dependencies(self):
        """检查必需依赖"""
        if self._dependencies_checked:
            return True
        
        errors = []
        if not HAS_RAPIDFUZZ:
            errors.append(f"rapidfuzz: {RAPIDFUZZ_ERROR or '未安装'}")
        if not HAS_SENTENCE_TRANSFORMER:
            errors.append(f"sentence-transformers: {SENTENCE_TRANSFORMER_ERROR or '未安装'}")
        
        if errors:
            detail = "\n".join(errors)
            self._log(f"[POI匹配] 依赖检查失败:\n{detail}", "error")
            msg = "缺少必需依赖库，请在OSGeo4W Shell中执行:\npip install sentence-transformers rapidfuzz tqdm"
            self._log(f"[POI匹配] {msg}", "error")
            raise ImportError(msg)
        
        self._dependencies_checked = True
        return True
    
    def _ensure_model(self):
        """确保模型已加载"""
        self._check_dependencies()
        
        if not self._model_loaded:
            self._log("[POI匹配] 加载语义模型...", "info")
            self._model = SentenceTransformer(EMB_MODEL_NAME)
            self._model_loaded = True
            self._log("[POI匹配] 语义模型加载完成", "info")
    
    def match(self,
              left_df: pd.DataFrame,
              right_df: pd.DataFrame,
              left_file: str = "",
              right_file: str = "",
              left_poi_col: str = "标准化POI抽取",
              right_poi_col: str = "标准化POI抽取",
              left_addr_col: str = "标准化地址",
              right_addr_col: str = "标准化地址",
              left_name_col: str = "",
              right_name_col: str = "",
              progress_callback: Optional[Callable[[int, int, str], None]] = None
              ) -> pd.DataFrame:
        """
        执行POI匹配
        
        Args:
            left_df: 源表 DataFrame
            right_df: 目标表 DataFrame
            left_file: 源表文件名（用于结果追溯）
            right_file: 目标表文件名
            left_poi_col: 源表POI列名
            right_poi_col: 目标表POI列名
            left_addr_col: 源表标准化地址列名
            right_addr_col: 目标表标准化地址列名
            left_name_col: 源表名称列名（可选，用于显示）
            right_name_col: 目标表名称列名（可选）
            progress_callback: 进度回调 (current, total, message)
        
        Returns:
            匹配结果 DataFrame，包含完整追溯字段
        """
        # 确保模型已加载
        self._ensure_model()
        
        # 检查必需列
        if left_poi_col not in left_df.columns:
            self._log(f"[POI匹配] 源表缺少POI列: {left_poi_col}", "error")
            return pd.DataFrame()
        if right_poi_col not in right_df.columns:
            self._log(f"[POI匹配] 目标表缺少POI列: {right_poi_col}", "error")
            return pd.DataFrame()
        
        # 提取数据
        left_pois = left_df[left_poi_col].fillna("").astype(str).tolist()
        right_pois = right_df[right_poi_col].fillna("").astype(str).tolist()
        
        # 提取地址列（可选）
        left_addrs = left_df[left_addr_col].fillna("").astype(str).tolist() if left_addr_col in left_df.columns else [""] * len(left_df)
        right_addrs = right_df[right_addr_col].fillna("").astype(str).tolist() if right_addr_col in right_df.columns else [""] * len(right_df)
        
        # 提取名称列（可选）
        left_names = left_df[left_name_col].fillna("").astype(str).tolist() if left_name_col and left_name_col in left_df.columns else [""] * len(left_df)
        right_names = right_df[right_name_col].fillna("").astype(str).tolist() if right_name_col and right_name_col in right_df.columns else [""] * len(right_df)
        
        # 提取追溯ID字段（用于关联分析）
        left_record_ids = left_df['_record_id'].fillna("").astype(str).tolist() if '_record_id' in left_df.columns else [""] * len(left_df)
        right_record_ids = right_df['_record_id'].fillna("").astype(str).tolist() if '_record_id' in right_df.columns else [""] * len(right_df)
        
        self._log(f"[POI匹配] 源表 {len(left_pois)} 条, 目标表 {len(right_pois)} 条", "info")
        
        # 预处理目标表
        if progress_callback:
            progress_callback(0, 100, "预处理目标表...")
        
        right_poi_clean_list, right_level_list = self._preprocess_right(right_pois)
        
        # 编码目标表向量
        if progress_callback:
            progress_callback(10, 100, "编码目标表向量...")
        
        right_vecs = self._encode_sentences([clean_poi_for_fuzzy(p) for p in right_poi_clean_list])
        
        # 执行匹配
        results: List[Dict[str, Any]] = []
        total_left = len(left_pois)
        
        for idx in range(total_left):
            if progress_callback and idx % 50 == 0:
                progress = 10 + int((idx / total_left) * 85)
                progress_callback(progress, 100, f"匹配中 {idx + 1}/{total_left}")
            
            # 获取源表第一个POI
            left_poi_raw = left_pois[idx]
            left_poi = self._get_first_poi(left_poi_raw)
            
            # 执行单条匹配
            match_result = self._match_one(
                left_poi=left_poi,
                right_pois=right_pois,
                right_poi_clean_list=right_poi_clean_list,
                right_level_list=right_level_list,
                right_vecs=right_vecs
            )
            
            # 构建完整结果记录
            matched_idx = match_result.get("matched_index")
            
            result_row = {
                # === 追溯ID（核心关联字段）===
                "源表记录ID": left_record_ids[idx],
                "目标表记录ID": right_record_ids[matched_idx] if matched_idx is not None else "",
                
                # === 源表信息 ===
                "源表文件": left_file,
                "源表行号": idx + 1,
                "源表名称": left_names[idx],
                "源表标准化地址": left_addrs[idx],
                "源表POI原始": left_poi_raw,
                "源表POI": left_poi,
                
                # === 目标表信息 ===
                "目标表文件": right_file if matched_idx is not None else "",
                "目标表行号": (matched_idx + 1) if matched_idx is not None else None,
                "目标表名称": right_names[matched_idx] if matched_idx is not None else "",
                "目标表标准化地址": right_addrs[matched_idx] if matched_idx is not None else "",
                "目标表POI原始": right_pois[matched_idx] if matched_idx is not None else "",
                "目标表POI": match_result.get("right_poi", ""),
                
                # === 匹配信息 ===
                "匹配类型": match_result.get("match_type_zh", ""),
                "匹配类型代码": match_result.get("match_type", ""),
                "匹配分数": match_result.get("score", 0.0),
                "POI来源": match_result.get("poi_source", ""),
                "是否匹配": "是" if matched_idx is not None else "否"
            }
            
            results.append(result_row)
        
        if progress_callback:
            progress_callback(100, 100, "匹配完成")
        
        result_df = pd.DataFrame(results)
        
        # 统计
        matched_count = len(result_df[result_df["是否匹配"] == "是"])
        self._log(f"[POI匹配] 完成: 匹配 {matched_count}/{total_left} 条 ({matched_count/total_left*100:.1f}%)", "info")
        
        return result_df
    
    def _preprocess_right(self, right_pois: List[str]) -> Tuple[List[str], List[str]]:
        """预处理目标表（POI + 行政区过滤）"""
        right_poi_clean_list: List[str] = []
        right_level_list: List[str] = []
        
        for poi_raw in right_pois:
            poi = self._get_first_poi(poi_raw)
            
            if is_admin_only_name(poi):
                right_poi_clean_list.append("")
                right_level_list.append("admin")
            else:
                poi_clean = clean_poi_for_fuzzy(poi)
                if not poi_clean:
                    right_poi_clean_list.append(poi_raw)
                    right_level_list.append("poi")
                else:
                    right_poi_clean_list.append(poi_clean)
                    right_level_list.append("poi")
        
        return right_poi_clean_list, right_level_list
    
    def _get_first_poi(self, poi_str: str) -> str:
        """从分号分隔的POI列表中获取第一个"""
        if not poi_str:
            return ""
        parts = poi_str.split(";")
        return parts[0].strip() if parts else ""
    
    def _encode_sentences(self, texts: List[str]) -> np.ndarray:
        """编码文本为向量"""
        if not texts or self._model is None:
            return np.zeros((len(texts), 384), dtype=np.float32)
        
        return self._model.encode(
            texts,
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False
        )
    
    def _match_one(self,
                   left_poi: str,
                   right_pois: List[str],
                   right_poi_clean_list: List[str],
                   right_level_list: List[str],
                   right_vecs: np.ndarray) -> Dict[str, Any]:
        """匹配单条记录（V11核心逻辑）"""
        # 空值检查
        if not left_poi or not left_poi.strip():
            return {
                "matched_index": None,
                "right_poi": "",
                "match_type": "empty_left",
                "match_type_zh": "源表POI为空",
                "score": 0.0,
                "poi_source": "empty"
            }
        
        # 非POI过滤
        if is_pure_numeric(left_poi) or is_non_poi_device(left_poi):
            return {
                "matched_index": None,
                "right_poi": "",
                "match_type": "non_poi_left",
                "match_type_zh": "源表为非地点类",
                "score": 0.0,
                "poi_source": "rule"
            }
        
        # 清洗POI
        left_poi_clean = clean_poi_for_fuzzy(left_poi)
        
        if not left_poi_clean:
            return {
                "matched_index": None,
                "right_poi": "",
                "match_type": "no_poi_left",
                "match_type_zh": "源表无可用POI主体",
                "score": 0.0,
                "poi_source": "step3"
            }
        
        # 获取候选
        candidates_idx = [
            i for i, lvl in enumerate(right_level_list)
            if lvl == "poi" and right_poi_clean_list[i]
        ]
        
        if not candidates_idx:
            return {
                "matched_index": None,
                "right_poi": "",
                "match_type": "no_poi_right",
                "match_type_zh": "目标表无可用POI主体",
                "score": 0.0,
                "poi_source": "step3"
            }
        
        cand_pois_clean = [right_poi_clean_list[i] for i in candidates_idx]
        
        best = {
            "matched_index": None,
            "right_poi": "",
            "match_type": None,
            "match_type_zh": "",
            "score": 0.0,
            "poi_source": "step3"
        }
        
        # 1. 模糊强匹配
        if cand_pois_clean:
            match_result = process.extractOne(
                left_poi_clean,
                cand_pois_clean,
                scorer=fuzz.partial_ratio
            )
            if match_result:
                match, fuzzy_score, idx_local = match_result
                if fuzzy_score >= FUZZY_STRONG_THRESHOLD:
                    real_idx = candidates_idx[idx_local]
                    best.update({
                        "matched_index": real_idx,
                        "right_poi": self._get_first_poi(right_pois[real_idx]),
                        "match_type": "fuzzy_strong_poi",
                        "match_type_zh": "模糊强匹配",
                        "score": float(fuzzy_score)
                    })
                    return best
        
        # 2. 语义匹配
        if self._model is not None:
            left_vec = self._encode_sentences([left_poi_clean])[0:1]
            cand_vecs = right_vecs[candidates_idx]
            
            sims = cand_vecs @ left_vec.T
            sims = sims.reshape(-1)
            top_idx_local = int(np.argmax(sims))
            top_sim = float(sims[top_idx_local])
            
            if top_sim >= SEMANTIC_STRONG:
                real_idx = candidates_idx[top_idx_local]
                best.update({
                    "matched_index": real_idx,
                    "right_poi": self._get_first_poi(right_pois[real_idx]),
                    "match_type": "semantic_strong_poi",
                    "match_type_zh": "语义强匹配",
                    "score": round(top_sim * 100, 2)
                })
                return best
            
            if top_sim >= SEMANTIC_WEAK:
                real_idx = candidates_idx[top_idx_local]
                best.update({
                    "matched_index": real_idx,
                    "right_poi": self._get_first_poi(right_pois[real_idx]),
                    "match_type": "semantic_weak_poi",
                    "match_type_zh": "语义弱匹配",
                    "score": round(top_sim * 100, 2)
                })
        
        # 3. 模糊弱匹配
        if cand_pois_clean:
            match_result = process.extractOne(
                left_poi_clean,
                cand_pois_clean,
                scorer=fuzz.partial_ratio
            )
            if match_result:
                match, fuzzy_score, idx_local = match_result
                if fuzzy_score >= FUZZY_WEAK_THRESHOLD and fuzzy_score > best["score"]:
                    real_idx = candidates_idx[idx_local]
                    best.update({
                        "matched_index": real_idx,
                        "right_poi": self._get_first_poi(right_pois[real_idx]),
                        "match_type": "fuzzy_weak_poi",
                        "match_type_zh": "模糊弱匹配",
                        "score": float(fuzzy_score)
                    })
        
        # 4. 未匹配
        if best["matched_index"] is None:
            best["match_type"] = "unmatched"
            best["match_type_zh"] = "未匹配"
            best["score"] = 0.0
        
        return best
    
    def get_match_statistics(self, result_df: pd.DataFrame) -> Dict[str, Any]:
        """获取匹配统计信息"""
        if result_df.empty:
            return {"total": 0, "matched": 0, "unmatched": 0, "match_rate": 0}
        
        total = len(result_df)
        matched = len(result_df[result_df["是否匹配"] == "是"])
        type_counts = result_df["匹配类型"].value_counts().to_dict()
        
        return {
            "total": total,
            "matched": matched,
            "unmatched": total - matched,
            "match_rate": round(matched / total * 100, 2),
            "type_breakdown": type_counts
        }
    
    def match_large(self,
                    left_df: pd.DataFrame,
                    right_df: pd.DataFrame,
                    batch_size: int = 500,
                    **kwargs) -> pd.DataFrame:
        """大数据量匹配（分批处理）"""
        total_rows = len(left_df)
        
        if total_rows <= batch_size:
            return self.match(left_df, right_df, **kwargs)
        
        self._ensure_model()
        progress_callback = kwargs.get("progress_callback")
        
        results = []
        num_batches = (total_rows + batch_size - 1) // batch_size
        
        self._log(f"[POI匹配] 大数据量匹配: {total_rows} 条, 分 {num_batches} 批处理", "info")
        
        for batch_idx in range(num_batches):
            start_idx = batch_idx * batch_size
            end_idx = min(start_idx + batch_size, total_rows)
            
            batch_df = left_df.iloc[start_idx:end_idx].copy()
            
            if progress_callback:
                progress = int((batch_idx / num_batches) * 100)
                progress_callback(progress, 100, f"处理批次 {batch_idx + 1}/{num_batches}")
            
            batch_kwargs = kwargs.copy()
            batch_kwargs["progress_callback"] = None
            
            batch_result = self.match(batch_df, right_df, **batch_kwargs)
            results.append(batch_result)
        
        if results:
            final_result = pd.concat(results, ignore_index=True)
            if progress_callback:
                progress_callback(100, 100, "匹配完成")
            return final_result
        
        return pd.DataFrame()

