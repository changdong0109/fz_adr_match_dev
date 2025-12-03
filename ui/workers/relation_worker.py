# -*- coding: utf-8 -*-
"""
关联分析 Worker
在后台线程执行字段关联分析，避免阻塞UI
"""
import os
from .base_worker import BaseWorker
from typing import List, Dict, Optional


class RelationWorker(BaseWorker):
    """关联分析后台线程"""
    
    def __init__(self, 
                 files: List[str],  # 文件路径列表
                 sample_size: int = 1000,  # 采样大小
                 parent=None):
        super().__init__(parent)
        self.files = files
        self.sample_size = sample_size
    
    def do_work(self) -> dict:
        """执行关联分析"""
        import pandas as pd
        
        total_files = len(self.files)
        if total_files == 0:
            return {'success': False, 'error': '没有可分析的文件'}
        
        self.emit_log(f"[关联分析] 开始分析 {total_files} 个文件", "info")
        
        # 1. 加载数据
        self.emit_progress(0, 100, "加载数据...")
        file_data = {}
        
        for i, file_path in enumerate(self.files):
            if self.is_cancelled:
                return {'cancelled': True}
            
            file_name = os.path.basename(file_path)
            self.emit_progress(int(i / total_files * 30), 100, f"加载: {file_name}")
            
            try:
                df = self._read_file(file_path)
                if df is not None and not df.empty:
                    # 采样以提高性能
                    if len(df) > self.sample_size:
                        df = df.sample(n=self.sample_size, random_state=42)
                    file_data[file_name] = df
            except Exception as e:
                self.emit_log(f"[关联分析] 加载 {file_name} 失败: {e}", "warning")
        
        if not file_data:
            return {'success': False, 'error': '没有有效数据'}
        
        # 2. 提取字段值
        self.emit_progress(30, 100, "提取字段值...")
        field_values = {}  # {file.field: set(values)}
        
        for file_name, df in file_data.items():
            if self.is_cancelled:
                return {'cancelled': True}
            
            for col in df.columns:
                # 跳过系统字段
                if col.startswith('_'):
                    continue
                
                key = f"{file_name}.{col}"
                values = df[col].dropna().astype(str).tolist()
                # 只保留非空、非纯数字的值
                values = [v for v in values if v.strip() and not v.replace('.', '').isdigit()]
                if values:
                    field_values[key] = set(values[:500])  # 限制值数量
        
        # 3. 计算关联关系
        self.emit_progress(50, 100, "计算关联关系...")
        relations = []
        field_keys = list(field_values.keys())
        total_pairs = len(field_keys) * (len(field_keys) - 1) // 2
        checked = 0
        
        for i, key1 in enumerate(field_keys):
            if self.is_cancelled:
                return {'cancelled': True}
            
            for key2 in field_keys[i + 1:]:
                checked += 1
                if checked % 100 == 0:
                    progress = 50 + int(checked / total_pairs * 40)
                    self.emit_progress(progress, 100, f"分析中... {checked}/{total_pairs}")
                
                # 计算重叠
                set1 = field_values[key1]
                set2 = field_values[key2]
                
                if not set1 or not set2:
                    continue
                
                intersection = set1 & set2
                if len(intersection) < 3:  # 至少3个共同值
                    continue
                
                # 计算相似度
                union = set1 | set2
                jaccard = len(intersection) / len(union) if union else 0
                
                if jaccard >= 0.1:  # 10% 相似度阈值
                    file1, field1 = key1.rsplit('.', 1)
                    file2, field2 = key2.rsplit('.', 1)
                    
                    relations.append({
                        'file1': file1,
                        'field1': field1,
                        'file2': file2,
                        'field2': field2,
                        'overlap': len(intersection),
                        'jaccard': round(jaccard, 3),
                        'sample_values': list(intersection)[:5]
                    })
        
        # 4. 排序和返回
        self.emit_progress(95, 100, "整理结果...")
        relations.sort(key=lambda x: x['jaccard'], reverse=True)
        
        self.emit_log(f"[关联分析] 完成，发现 {len(relations)} 对关联字段", "info")
        self.emit_progress(100, 100, "完成")
        
        return {
            'success': True,
            'relations': relations,
            'total_fields': len(field_values),
            'total_relations': len(relations)
        }
    
    def _read_file(self, file_path: str):
        """读取文件"""
        import pandas as pd
        
        try:
            if file_path.lower().endswith('.csv'):
                for enc in ['utf-8', 'gbk', 'utf-8-sig']:
                    try:
                        return pd.read_csv(file_path, encoding=enc)
                    except UnicodeDecodeError:
                        continue
            elif file_path.lower().endswith(('.xlsx', '.xls')):
                return pd.read_excel(file_path)
        except Exception:
            pass
        return None

