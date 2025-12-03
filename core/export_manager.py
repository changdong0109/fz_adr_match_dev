# -*- coding: utf-8 -*-
"""
导出管理器
负责将各类处理结果导出为Excel或CSV
"""
import os
import pandas as pd
from typing import List, Dict, Optional, Callable
from datetime import datetime


class ExportManager:
    """导出管理器"""
    
    def __init__(self, log_callback: Optional[Callable[[str, str], None]] = None):
        self._log = log_callback or (lambda msg, level: None)
    
    def export_dataframe(self, 
                         df: pd.DataFrame, 
                         output_path: str,
                         output_format: str = "xlsx",
                         columns: Optional[List[str]] = None) -> bool:
        """
        导出DataFrame到文件
        
        Args:
            df: 要导出的DataFrame
            output_path: 输出路径
            output_format: 输出格式 (xlsx/csv)
            columns: 要导出的列（None表示全部）
        
        Returns:
            是否成功
        """
        try:
            if df is None or df.empty:
                self._log("[导出] DataFrame为空，跳过", "warning")
                return False
            
            # 选择列
            if columns:
                export_df = df[[c for c in columns if c in df.columns]]
            else:
                export_df = df
            
            # 确保目录存在
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            # 导出
            if output_format.lower() == "xlsx":
                export_df.to_excel(output_path, index=False, engine='openpyxl')
            else:
                export_df.to_csv(output_path, index=False, encoding='utf-8-sig')
            
            self._log(f"[导出] 成功: {output_path} ({len(export_df)} 行)", "info")
            return True
            
        except Exception as e:
            self._log(f"[导出] 失败: {e}", "error")
            return False
    
    def export_from_file(self,
                         input_path: str,
                         output_path: str,
                         output_format: str = "xlsx",
                         columns: Optional[List[str]] = None) -> bool:
        """
        从文件读取并导出
        """
        try:
            # 读取
            if input_path.lower().endswith('.csv'):
                for enc in ['utf-8', 'gbk', 'gb2312', 'utf-8-sig']:
                    try:
                        df = pd.read_csv(input_path, encoding=enc)
                        break
                    except UnicodeDecodeError:
                        continue
            elif input_path.lower().endswith(('.xlsx', '.xls')):
                df = pd.read_excel(input_path)
            else:
                self._log(f"[导出] 不支持的格式: {input_path}", "error")
                return False
            
            return self.export_dataframe(df, output_path, output_format, columns)
            
        except Exception as e:
            self._log(f"[导出] 读取失败: {e}", "error")
            return False
    
    def batch_export(self,
                     files: List[str],
                     output_dir: str,
                     output_format: str = "xlsx",
                     columns: Optional[List[str]] = None) -> Dict:
        """
        批量导出
        
        Returns:
            {
                "success": int,
                "failed": int,
                "files": [...]
            }
        """
        success = 0
        failed = 0
        exported_files = []
        
        for input_path in files:
            if not os.path.exists(input_path):
                failed += 1
                continue
            
            filename = os.path.basename(input_path)
            name_without_ext = os.path.splitext(filename)[0]
            output_path = os.path.join(output_dir, f"{name_without_ext}.{output_format}")
            
            if self.export_from_file(input_path, output_path, output_format, columns):
                success += 1
                exported_files.append(output_path)
            else:
                failed += 1
        
        return {
            "success": success,
            "failed": failed,
            "files": exported_files
        }

