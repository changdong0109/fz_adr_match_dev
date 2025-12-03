# -*- coding: utf-8 -*-
"""
关联数据导出后台 Worker

继承 BaseWorker，符合项目架构规范
"""
import os
from typing import Dict, Any
from .base_worker import BaseWorker

# 大数据量阈值
LARGE_DATA_THRESHOLD = 50000  # 超过 5 万行使用快速模式
VERY_LARGE_THRESHOLD = 100000  # 超过 10 万行强制使用 CSV


class RelationExportWorker(BaseWorker):
    """
    关联数据导出后台线程
    
    继承自 BaseWorker，复用统一的信号和取消机制
    
    大数据量优化策略：
    - 5-10 万行：使用简单 Excel（不带颜色）
    - 超过 10 万行：强制使用 CSV（Excel 太慢）
    """
    
    def __init__(self, exporter, path_a: str, path_b: str, col_a: str, col_b: str,
                 output_path: str, join_type: str, parent=None):
        super().__init__(parent)
        self.exporter = exporter
        self.path_a = path_a
        self.path_b = path_b
        self.col_a = col_a
        self.col_b = col_b
        self.output_path = output_path
        self.join_type = join_type
    
    def do_work(self) -> Dict[str, Any]:
        """执行导出任务"""
        
        self.emit_progress(5, 100, "读取表A...")
        self.emit_log(f"[关联导出] 读取表A: {os.path.basename(self.path_a)}", "info")
        
        df_a = self.exporter.read_file(self.path_a)
        
        if self.is_cancelled:
            return {'cancelled': True}
        
        self.emit_progress(20, 100, "读取表B...")
        self.emit_log(f"[关联导出] 读取表B: {os.path.basename(self.path_b)}", "info")
        
        df_b = self.exporter.read_file(self.path_b)
        
        if self.is_cancelled:
            return {'cancelled': True}
        
        self.emit_progress(40, 100, "执行关联...")
        self.emit_log(f"[关联导出] 表A: {len(df_a)} 行, 表B: {len(df_b)} 行", "info")
        
        result_df, meta = self.exporter.execute_join(
            df_a, df_b, self.col_a, self.col_b, self.join_type
        )
        
        if self.is_cancelled:
            return {'cancelled': True}
        
        row_count = len(result_df)
        
        if row_count == 0:
            self.emit_log("[关联导出] 没有匹配的数据", "warning")
            return {
                'success': True,
                'row_count': 0,
                'message': '没有匹配的数据' if self.join_type == 'inner' else '所有数据都已关联',
                'output_path': ''
            }
        
        self.emit_progress(60, 100, f"准备导出 {row_count:,} 行数据...")
        self.emit_log(f"[关联导出] 数据量: {row_count:,} 行", "info")
        
        # 文件名信息
        file_a_name = os.path.basename(self.path_a).replace('.csv', '').replace('.xlsx', '')
        file_b_name = os.path.basename(self.path_b).replace('.csv', '').replace('.xlsx', '')
        
        # 大数据量判断
        is_very_large = row_count > VERY_LARGE_THRESHOLD
        is_large = row_count > LARGE_DATA_THRESHOLD
        is_excel = self.output_path.lower().endswith('.xlsx')
        
        # 超过 10 万行强制使用 CSV（Excel 太慢会卡死）
        actual_output_path = self.output_path
        format_changed = False
        
        if is_very_large and is_excel:
            actual_output_path = self.output_path.replace('.xlsx', '.csv')
            format_changed = True
            self.emit_log(f"[关联导出] 数据量超过 10 万行，自动切换为 CSV 格式", "warning")
        elif is_large and is_excel:
            self.emit_log(f"[关联导出] 大数据量 ({row_count:,} 行)，使用快速导出模式", "info")
        
        self.emit_progress(70, 100, f"写入文件...")
        
        # 根据数据量选择导出方式
        if format_changed or actual_output_path.lower().endswith('.csv'):
            # CSV 导出（最快）
            self._export_csv_fast(result_df, actual_output_path)
        elif is_large:
            # 大数据量 Excel：不带样式
            self._export_excel_fast(result_df, actual_output_path)
        elif self.join_type == 'inner':
            # 小数据量：带颜色样式
            self.exporter.export_to_excel_with_colors(
                result_df, actual_output_path,
                meta.get('cols_a', []),
                meta.get('join_cols', []),
                meta.get('cols_b', []),
                file_a_name, file_b_name
            )
        else:
            # 非 INNER JOIN
            self._export_excel_fast(result_df, actual_output_path)
        
        self.emit_progress(100, 100, "导出完成")
        
        format_hint = ""
        if format_changed:
            format_hint = "\n\n💡 数据量过大，已自动切换为 CSV 格式"
        elif is_large and is_excel:
            format_hint = "\n\n💡 大数据量使用快速模式，无颜色样式"
        
        self.emit_log(f"[关联导出] 完成: {actual_output_path} ({row_count:,} 行)", "success")
        
        return {
            'success': True,
            'row_count': row_count,
            'message': f"已导出 {row_count:,} 条数据{format_hint}",
            'output_path': actual_output_path
        }
    
    def _export_csv_fast(self, df, output_path: str):
        """快速 CSV 导出"""
        df.to_csv(output_path, index=False, encoding='utf-8-sig')
    
    def _export_excel_fast(self, df, output_path: str):
        """快速 Excel 导出（不带样式，使用 xlsxwriter 更快）"""
        try:
            # xlsxwriter 比 openpyxl 快 3-5 倍
            df.to_excel(output_path, index=False, engine='xlsxwriter')
        except ImportError:
            # 如果没有 xlsxwriter，使用 openpyxl
            df.to_excel(output_path, index=False, engine='openpyxl')
