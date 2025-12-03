"""
数据清洗模块
职责：根据用户配置的字段组合，对数据进行清洗和拼接

架构设计：
- CleaningRules: 规则配置（可序列化、可自定义）
- AddressValidator: 地址验证器（判断是否有效地址）
- TextSanitizer: 文本清洗器（去噪声、去占位词）
- FieldConfigChecker: 字段配置检查器
- DataCleaner: 清洗执行器（组合以上组件）
"""
import os
import re
from typing import Callable, Dict, List, Optional, Tuple
import pandas as pd

# 导入规则模块
from .cleaning_rules import (
    CleaningRules, 
    AddressValidator, 
    TextSanitizer, 
    FieldConfigChecker
)


class DataCleaner:
    """
    数据清洗器
    
    职责：执行清洗流程，不关心具体规则
    规则由 CleaningRules 配置类提供
    """
    
    def __init__(self, 
                 log_callback: Optional[Callable[[str, str], None]] = None,
                 rules: Optional[CleaningRules] = None):
        """
        初始化清洗器
        
        Args:
            log_callback: 日志回调函数 (message, level)
            rules: 清洗规则配置，默认使用 CleaningRules.default()
        """
        self.log_callback = log_callback
        
        # 初始化规则和组件
        self.rules = rules or CleaningRules.default()
        self.validator = AddressValidator(self.rules)
        self.sanitizer = TextSanitizer(self.rules)
        self.config_checker = FieldConfigChecker(self.rules)
        
        # 为了向后兼容，保留类属性引用
        self.SPECIFIC_ADDRESS_KEYWORDS = self.rules.address_keywords
    
    def _log(self, message: str, level: str = "info"):
        """输出日志"""
        if self.log_callback:
            self.log_callback(message, level)
    
    def _move_id_columns_to_front(self, df: pd.DataFrame) -> pd.DataFrame:
        """将ID追溯字段移到首列"""
        id_cols = ['_record_id', '_source_file', '_source_row']
        existing_id_cols = [c for c in id_cols if c in df.columns]
        
        if not existing_id_cols:
            return df
        
        # 重新排列列：ID字段在前，其他字段在后
        other_cols = [c for c in df.columns if c not in existing_id_cols]
        new_order = existing_id_cols + other_cols
        
        return df[new_order]
    
    def clean_file(
        self,
        file_path: str,
        field_config: List[Dict],
        output_dir: str,
        province: str,
        city: str,
        county: str,
        source_type: str,
        progress_callback: Optional[Callable[[int, int], None]] = None,
        cancel_check: Optional[Callable[[], bool]] = None
    ) -> Dict:
        """
        清洗单个文件
        
        Args:
            file_path: 源文件路径
            field_config: 字段配置列表 [{role, field}, ...]
            output_dir: 输出基础目录（用户基目录）
            province: 省
            city: 市
            county: 县（可选）
            source_type: 数据源类型（"客户采集数据" / "GIS 数据" / "其他"）
            progress_callback: 进度回调 (current, total)
            cancel_check: 取消检查函数，返回True表示取消
            
        Returns:
            {
                "success": bool,
                "valid_count": int,
                "invalid_count": int,
                "valid_file": str,
                "invalid_file": str,
                "error": str (如果失败)
            }
        """
        try:
            # 读取源文件
            file_name = os.path.basename(file_path)
            file_stem = os.path.splitext(file_name)[0]
            
            self._log(f"[清洗] 开始处理：{file_name}")
            
            df = pd.read_csv(file_path, encoding='utf-8')
            total_rows = len(df)
            
            if total_rows == 0:
                return {
                    "success": False,
                    "error": "文件为空",
                    "valid_count": 0,
                    "invalid_count": 0
                }
            
            # 获取配置的字段列表
            fields = [f['field'] for f in field_config if f.get('field')]
            if not fields:
                return {
                    "success": False,
                    "error": "未配置任何字段",
                    "valid_count": 0,
                    "invalid_count": 0
                }
            
            # 检查字段是否存在
            missing_fields = [f for f in fields if f not in df.columns]
            if missing_fields:
                return {
                    "success": False,
                    "error": f"字段不存在：{', '.join(missing_fields)}",
                    "valid_count": 0,
                    "invalid_count": 0
                }
            
            # === 智能字段配置检查 ===
            field_warnings = self._check_field_config(df, fields, file_stem)
            if field_warnings:
                for warning in field_warnings:
                    self._log(warning, "warning")
            
            # 新增清洗后字段列名
            clean_column_name = f"{file_stem}_adr_clean"
            
            # 分析字段特征（全数字且无差异的忽略）
            ignore_fields = self._get_ignore_fields(df, fields)
            active_fields = [f for f in fields if f not in ignore_fields]
            
            if ignore_fields:
                self._log(f"[清洗] 忽略无效字段：{', '.join(ignore_fields)}")
            
            # 清洗数据
            valid_rows = []
            invalid_rows = []
            
            for idx, row in df.iterrows():
                # 检查是否取消
                if cancel_check and cancel_check():
                    self._log("[清洗] 任务已取消")
                    return {
                        "success": False,
                        "error": "任务已取消",
                        "valid_count": len(valid_rows),
                        "invalid_count": len(invalid_rows)
                    }
                
                # 更新进度
                if progress_callback:
                    progress_callback(idx + 1, total_rows)
                
                # 检查是否为空行（配置字段全为空）
                if self._is_empty_row(row, active_fields):
                    # 为剔除数据添加追溯ID
                    row_with_id = row.copy()
                    row_num = idx + 2
                    row_with_id['_record_id'] = f"{file_stem}_{row_num}"
                    row_with_id['_source_file'] = file_name
                    row_with_id['_source_row'] = row_num
                    invalid_rows.append((row_with_id, "全空行"))
                    continue
                
                # 构建清洗后的文本
                clean_text = self._build_clean_text(row, active_fields)
                
                # 检查清洗后文本是否有效（先检查空，再检查纯行政区）
                if not clean_text.strip():
                    # 尝试从所有非空字段中提取地址信息（放宽条件）
                    fallback_text = self._extract_any_address(row)
                    if fallback_text:
                        # 找到了有效地址，使用回退文本
                        clean_text = fallback_text
                        self._log(f"[清洗] 行{idx+1} 使用回退地址提取: {clean_text[:30]}...", "debug")
                    else:
                        # 记录原始值用于调试
                        original_values = [str(row.get(f, '')) for f in active_fields if pd.notna(row.get(f))]
                        self._log(f"[清洗] 行{idx+1} 清洗后为空，原始值：{original_values}", "debug")
                        # 为剔除数据也添加追溯ID
                        row_with_id = row.copy()
                        row_num = idx + 2
                        row_with_id['_record_id'] = f"{file_stem}_{row_num}"
                        row_with_id['_source_file'] = file_name
                        row_with_id['_source_row'] = row_num
                        invalid_rows.append((row_with_id, "清洗后为空"))
                        continue
                
                # 检查是否为纯行政区行（使用更严格的判断）
                if self._is_pure_region_row(clean_text):
                    # 再次确认：如果原始数据有楼栋/单元等信息，则不应剔除
                    has_building_info = self._has_building_info(row)
                    if has_building_info:
                        self._log(f"[清洗] 行{idx+1} 虽判定为纯行政区但有楼栋信息，保留: {clean_text}", "debug")
                    else:
                        # 为剔除数据添加追溯ID
                        row_with_id = row.copy()
                        row_num = idx + 2
                        row_with_id['_record_id'] = f"{file_stem}_{row_num}"
                        row_with_id['_source_file'] = file_name
                        row_with_id['_source_row'] = row_num
                        invalid_rows.append((row_with_id, "纯行政区"))
                        continue
                
                # 有效数据 - 添加追溯ID字段
                row_copy = row.copy()
                row_copy[clean_column_name] = clean_text
                
                # 生成唯一记录ID（用于后续关联追溯）
                # 格式：文件名_行号（行号从1开始，与Excel行号一致）
                row_num = idx + 2  # +2 因为: idx从0开始(+1), CSV有表头行(+1)
                row_copy['_record_id'] = f"{file_stem}_{row_num}"
                row_copy['_source_file'] = file_name
                row_copy['_source_row'] = row_num
                
                valid_rows.append(row_copy)
            
            # 创建输出目录（规范化路径，避免混合斜杠）
            # 文件夹名：{省}{市}{县}_客户数据清洗 或 {省}{市}{县}_GIS数据清洗
            type_folder = self._get_type_folder_name(source_type)
            region_prefix = f"{province}{city}{county}".strip()
            clean_folder_name = f"{region_prefix}_{type_folder}"
            clean_base_dir = os.path.normpath(os.path.join(output_dir, clean_folder_name))
            
            valid_dir = os.path.normpath(os.path.join(clean_base_dir, "清洗后数据"))
            invalid_dir = os.path.normpath(os.path.join(clean_base_dir, "异常数据"))
            
            try:
                os.makedirs(valid_dir, exist_ok=True)
                os.makedirs(invalid_dir, exist_ok=True)
            except Exception as e:
                self._log(f"[清洗] 创建输出目录失败：{e}", "error")
                return {
                    "success": False,
                    "error": f"创建输出目录失败：{e}",
                    "valid_count": len(valid_rows),
                    "invalid_count": len(invalid_rows)
                }
            
            # 保存有效数据
            valid_file = ""
            valid_save_error = None
            if valid_rows:
                valid_df = pd.DataFrame(valid_rows)
                # 将ID字段移到首列
                valid_df = self._move_id_columns_to_front(valid_df)
                valid_file = os.path.normpath(os.path.join(valid_dir, f"{file_stem}_清洗.csv"))
                try:
                    valid_df.to_csv(valid_file, index=False, encoding='utf-8-sig')
                    self._log(f"[清洗] 有效数据已保存：{valid_file}")
                except PermissionError:
                    valid_save_error = "permission"
                    self._log(f"[清洗] 保存有效数据失败：文件被占用，请先关闭 - {valid_file}", "error")
                except Exception as e:
                    valid_save_error = str(e)
                    self._log(f"[清洗] 保存有效数据失败：{e}", "error")
            
            # 保存无效数据
            invalid_file = ""
            invalid_save_error = None
            if invalid_rows:
                invalid_df = pd.DataFrame([r[0] for r in invalid_rows])
                # 添加剔除原因列
                invalid_df['_剔除原因'] = [r[1] for r in invalid_rows]
                # 将ID字段移到首列
                invalid_df = self._move_id_columns_to_front(invalid_df)
                invalid_file = os.path.normpath(os.path.join(invalid_dir, f"{file_stem}_剔除.csv"))
                try:
                    invalid_df.to_csv(invalid_file, index=False, encoding='utf-8-sig')
                    self._log(f"[清洗] 异常数据已保存：{invalid_file}")
                except PermissionError:
                    invalid_save_error = "permission"
                    self._log(f"[清洗] 保存异常数据失败：文件被占用，请先关闭 - {invalid_file}", "error")
                except Exception as e:
                    invalid_save_error = str(e)
                    self._log(f"[清洗] 保存异常数据失败：{e}", "error")
            
            # 检查是否有保存错误
            has_permission_error = (valid_save_error == "permission" or invalid_save_error == "permission")
            has_save_error = valid_save_error is not None or invalid_save_error is not None
            
            if has_save_error:
                self._log(f"[清洗] 部分完成：有效 {len(valid_rows)} 条，剔除 {len(invalid_rows)} 条（保存时有错误）", "warning")
            else:
                self._log(f"[清洗] 完成：有效 {len(valid_rows)} 条，剔除 {len(invalid_rows)} 条", "success")
            
            return {
                "success": not has_save_error,
                "valid_count": len(valid_rows),
                "invalid_count": len(invalid_rows),
                "valid_file": valid_file if not valid_save_error else "",
                "invalid_file": invalid_file if not invalid_save_error else "",
                "has_permission_error": has_permission_error,
                "error": "文件被占用，请先关闭相关CSV文件" if has_permission_error else None
            }
            
        except Exception as e:
            self._log(f"[清洗] 处理失败：{e}", "error")
            return {
                "success": False,
                "error": str(e),
                "valid_count": 0,
                "invalid_count": 0
            }
    
    def _get_type_folder_name(self, source_type: str) -> str:
        """根据数据源类型获取文件夹名称"""
        if source_type == "GIS 数据":
            return "GIS数据清洗"
        elif source_type == "客户采集数据":
            return "客户数据清洗"
        else:
            return "数据清洗"
    
    def _get_ignore_fields(self, df: pd.DataFrame, fields: List[str]) -> List[str]:
        """
        获取应该忽略的字段（全数字且无差异）
        
        Args:
            df: 数据框
            fields: 字段列表
            
        Returns:
            应该忽略的字段列表
        """
        ignore_fields = []
        
        for field in fields:
            values = df[field].dropna().astype(str).str.strip()
            values = values[values != '']
            
            if len(values) == 0:
                ignore_fields.append(field)
                continue
            
            # 检查是否全为相同的纯数字
            unique_values = values.unique()
            if len(unique_values) == 1:
                val = unique_values[0]
                if val.isdigit():
                    ignore_fields.append(field)
        
        return ignore_fields
    
    def _check_field_config(self, df: pd.DataFrame, fields: List[str], file_name: str) -> List[str]:
        """
        智能检查字段配置是否合理
        
        委托给 FieldConfigChecker 组件处理
        """
        return self.config_checker.check(df, fields, file_name)
    
    def _is_empty_row(self, row: pd.Series, fields: List[str]) -> bool:
        """
        检查是否为空行（所有配置字段为空）
        
        Args:
            row: 数据行
            fields: 字段列表
            
        Returns:
            是否为空行
        """
        for field in fields:
            val = row.get(field)
            if pd.notna(val) and str(val).strip():
                return False
        return True
    
    def _is_pure_region_row(self, text: str) -> bool:
        """
        检查是否为纯行政区行
        
        委托给 AddressValidator 组件处理
        
        只剔除纯粹的省/市/区级别：xx省、xx市、xx区、xx省xx市等
        其他所有情况都保留（包括镇、村、街道等）
        """
        return self.validator.is_pure_admin_region(text)
    
    def _sanitize_segment(self, text: str) -> str:
        """
        去除噪声关键字和冗余占位词
        
        委托给 TextSanitizer 组件处理
        """
        return self.sanitizer.sanitize(text)
    
    def _contains_chinese(self, text: str) -> bool:
        """
        检查是否包含中文字符
        
        Args:
            text: 文本
            
        Returns:
            是否包含中文
        """
        if not text:
            return False
        return bool(re.search(r'[\u4e00-\u9fa5]', str(text)))
    
    def _extract_any_address(self, row: pd.Series) -> str:
        """
        从行数据的所有字段中尝试提取地址信息（回退机制）
        
        常见地址字段名：location, address, userlocati, housingest 等
        """
        address_field_names = [
            'location', 'address', 'userlocati', 'housingest', 
            'addr', '地址', '位置', '住址', 'loc'
        ]
        
        for col in row.index:
            col_lower = str(col).lower()
            # 检查是否是地址相关字段
            if any(name in col_lower for name in address_field_names):
                val = row.get(col)
                if pd.notna(val):
                    text = str(val).strip()
                    # 如果包含中文且长度足够，认为是有效地址
                    if self._contains_chinese(text) and len(text) > 2:
                        return self._sanitize_segment(text)
        
        return ""
    
    def _has_building_info(self, row: pd.Series) -> bool:
        """
        检查行数据是否有楼栋/单元/门牌等建筑信息
        
        常见字段名：buildingno, houseno, unit, floor 等
        """
        building_field_names = [
            'buildingno', 'houseno', 'unit', 'floor', 'room',
            '楼', '栋', '单元', '门牌', '房号', '层'
        ]
        
        building_keywords = ['栋', '号', '楼', '单元', '层', '室', '排', '户', '期']
        
        for col in row.index:
            col_lower = str(col).lower()
            # 检查字段名
            if any(name in col_lower for name in building_field_names):
                val = row.get(col)
                if pd.notna(val):
                    text = str(val).strip()
                    if text and text not in ['无', 'nan', 'None', '']:
                        return True
            
            # 检查字段值是否包含建筑关键词
            val = row.get(col)
            if pd.notna(val):
                text = str(val)
                for kw in building_keywords:
                    if kw in text:
                        return True
        
        return False
    
    def _build_clean_text(self, row: pd.Series, fields: List[str]) -> str:
        """
        按配置字段顺序拼接清洗后的文本，并去除重复内容
        
        Args:
            row: 数据行
            fields: 字段列表（已排除忽略字段）
            
        Returns:
            拼接后的文本
        """
        segments = []
        
        for field in fields:
            val = row.get(field)
            if pd.isna(val):
                continue
            
            # 转字符串并去除前后空白
            text = str(val).strip()
            if not text:
                continue
            
            # 去除噪声关键字和冗余词
            text = self._sanitize_segment(text)
            if not text:
                continue
            
            # 检查是否包含中文（不含中文则不纳入拼接）
            if not self._contains_chinese(text):
                continue
            
            segments.append(text)
        
        # 拼接后进行去重处理
        result = ''.join(segments)
        result = self._remove_duplicates(result)
        
        return result
    
    def _remove_duplicates(self, text: str) -> str:
        """
        去除拼接后文本中的重复内容
        
        例如：
        - "32090部队院内...32090部队集训队" -> "32090部队院内...集训队"
        - "河北省廊坊市河北省廊坊市xxx" -> "河北省廊坊市xxx"
        
        Args:
            text: 拼接后的文本
            
        Returns:
            去重后的文本
        """
        if not text or len(text) < 6:
            return text
        
        result = text
        
        # 1. 去除连续重复的行政区划（如 "河北省廊坊市河北省廊坊市"）
        # 匹配连续重复的省市区
        result = re.sub(r'([\u4e00-\u9fa5]{2,}(?:省|市|区|县))\1+', r'\1', result)
        
        # 2. 去除重复的地点名称（如 "32090部队...32090部队"）
        # 使用滑动窗口查找重复片段
        result = self._remove_repeated_phrases(result, min_len=4, max_len=15)
        
        return result
    
    def _remove_repeated_phrases(self, text: str, min_len: int = 4, max_len: int = 15) -> str:
        """
        去除文本中重复出现的短语
        
        Args:
            text: 原始文本
            min_len: 最小短语长度
            max_len: 最大短语长度
            
        Returns:
            去重后的文本
        """
        if not text:
            return text
        
        result = text
        
        # 从长到短尝试匹配重复短语
        for phrase_len in range(max_len, min_len - 1, -1):
            i = 0
            while i < len(result) - phrase_len:
                phrase = result[i:i + phrase_len]
                # 检查这个短语是否在后面重复出现
                rest = result[i + phrase_len:]
                if phrase in rest:
                    # 找到重复，移除后面的重复部分
                    pos = rest.find(phrase)
                    # 只移除完全相同的短语，保留第一次出现
                    result = result[:i + phrase_len + pos] + rest[pos + phrase_len:]
                else:
                    i += 1
        
        return result

