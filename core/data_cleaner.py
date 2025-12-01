"""
数据清洗模块
职责：根据用户配置的字段组合，对数据进行清洗和拼接
"""
import os
import re
from typing import Callable, Dict, List, Optional, Tuple
import pandas as pd


class DataCleaner:
    """数据清洗器"""
    
    # 噪声关键字列表（燃气压力级别、异常标记等）
    NOISE_KEYWORDS = [
        # 燃气压力级别
        '高压', '中压', '低压', '高压A', '高压B', '中压A', '中压B', '低压A', '低压B',
        '高压a', '高压b', '中压a', '中压b', '低压a', '低压b',
        # 异常标记
        'nan', 'NaN', 'NAN', 'null', 'NULL', 'None', 'NONE',
        # 技术代号
        '_A', '_B', '_a', '_b'
    ]
    
    # 冗余占位词列表（需要清洗掉的无意义词）
    PLACEHOLDER_WORDS = [
        '无单元', '无号', '无楼', '无栋', '无门', '无室', '无层',
        '无门牌', '无门牌号', '无编号', '无房号',
        '暂无', '未知', '不详', '待定'
    ]
    
    # 纯行政区正则（严格匹配：只有省市区县+街道/乡镇/村，无其他内容）
    # 例如："河北省廊坊市" "广阳区新开路街道" 是纯行政区
    # 但 "新开路街道未来城1栋" 不是纯行政区（有具体地址信息）
    REGION_PATTERN = re.compile(
        r'^[\s]*([\u4e00-\u9fa5]{2,}(省|自治区|市|区|县|街道办事处|街道|乡|镇|村|社区|新区|开发区|办事处))[\s]*$'
    )
    
    # 具体地址关键词（有这些词说明不是纯行政区）
    SPECIFIC_ADDRESS_KEYWORDS = [
        '号', '栋', '楼', '层', '室', '单元', '幢', '座', '门',
        '小区', '花园', '公寓', '大厦', '广场', '中心', '城', '苑', '园', '庄', '庭',
        '超市', '商店', '店', '公司', '厂', '企业', '集团', '有限',
        '医院', '学校', '酒店', '宾馆', '银行', '餐厅', '饭店',
        '路', '道', '街', '巷', '胡同', '弄', '里'
    ]
    
    def __init__(self, log_callback: Optional[Callable[[str, str], None]] = None):
        """
        初始化清洗器
        
        Args:
            log_callback: 日志回调函数 (message, level)
        """
        self.log_callback = log_callback
    
    def _log(self, message: str, level: str = "info"):
        """输出日志"""
        if self.log_callback:
            self.log_callback(message, level)
    
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
                    invalid_rows.append((row, "全空行"))
                    continue
                
                # 构建清洗后的文本
                clean_text = self._build_clean_text(row, active_fields)
                
                # 检查清洗后文本是否有效（先检查空，再检查纯行政区）
                if not clean_text.strip():
                    # 记录原始值用于调试
                    original_values = [str(row.get(f, '')) for f in active_fields]
                    self._log(f"[清洗] 行{idx+1} 清洗后为空，原始值：{original_values}", "debug")
                    invalid_rows.append((row, "清洗后为空"))
                    continue
                
                # 检查是否为纯行政区行
                if self._is_pure_region_row(clean_text):
                    invalid_rows.append((row, "纯行政区"))
                    continue
                
                # 有效数据
                row_copy = row.copy()
                row_copy[clean_column_name] = clean_text
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
        检查是否为纯行政区行（只有省市区街道村等，无具体地址）
        
        判断规则：
        1. 如果包含数字（门牌号等），不是纯行政区
        2. 如果包含具体地址关键词（小区、超市、公司等），不是纯行政区
        3. 如果文本较长（>15个中文字符），不是纯行政区
        4. 只有完全匹配行政区划正则时，才是纯行政区
        
        Args:
            text: 清洗后的文本
            
        Returns:
            是否为纯行政区
        """
        if not text:
            return False
        
        text = text.strip()
        
        # 1. 包含数字则不是纯行政区（门牌号、楼号等）
        if re.search(r'\d', text):
            return False
        
        # 2. 包含具体地址关键词则不是纯行政区
        for keyword in self.SPECIFIC_ADDRESS_KEYWORDS:
            if keyword in text:
                return False
        
        # 3. 提取中文字符，如果太长则不是纯行政区
        chinese_chars = re.findall(r'[\u4e00-\u9fa5]', text)
        if len(chinese_chars) > 15:
            return False
        
        # 4. 去除空白符号后检查是否完全匹配行政区划正则
        clean_text = re.sub(r'[^\u4e00-\u9fa5]', '', text)
        if not clean_text:
            return True
        
        return bool(self.REGION_PATTERN.match(clean_text))
    
    def _sanitize_segment(self, text: str) -> str:
        """
        去除噪声关键字和冗余占位词
        
        Args:
            text: 原始文本
            
        Returns:
            清洗后的文本
        """
        if not text:
            return ""
        
        result = str(text)
        
        # 1. 去除噪声关键字
        for keyword in self.NOISE_KEYWORDS:
            result = result.replace(keyword, '')
        
        # 2. 去除冗余占位词
        for word in self.PLACEHOLDER_WORDS:
            result = result.replace(word, '')
        
        # 3. 清理连续的"无"（如 "无无" -> ""，"无1059" -> "1059"）
        # 匹配 "无" 后面直接跟数字或其他内容的情况
        result = re.sub(r'无(?=\d)', '', result)  # "无1059" -> "1059"
        result = re.sub(r'无{2,}', '', result)     # "无无无" -> ""
        
        return result.strip()
    
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

