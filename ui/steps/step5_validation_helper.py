# -*- coding: utf-8 -*-
"""
Step5 验证功能辅助模块
包含：CSV保存、分页显示等功能
"""
import os
import pandas as pd
from datetime import datetime
from typing import List, Dict, Optional
from pathlib import Path


def save_problems_to_csv(problems: List[Dict], cache_folder: str, identifier: str = "validation") -> Optional[str]:
    """
    保存问题数据为CSV文件
    
    Args:
        problems: 问题数据列表
        cache_folder: 缓存文件夹路径
        identifier: 文件标识符（用于生成文件名）
    
    Returns:
        CSV文件路径，如果保存失败则返回None
    """
    if not problems:
        return None
    
    try:
        # 确保目录存在
        os.makedirs(cache_folder, exist_ok=True)
        
        # 生成文件名：验证问题数据_标识_时间戳.csv
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_name = f"验证问题数据_{identifier}_{timestamp}.csv"
        file_path = os.path.join(cache_folder, file_name)
        
        # 转换为DataFrame
        df_data = []
        for problem in problems:
            row = {
                "目标表GID": problem.get('target_gid', ''),
                "数据库code": problem.get('db_code', '') or '-',
                "源表匹配值": problem.get('match_value', ''),
                "状态": problem.get('status', ''),
                "偏差距离": f"{problem.get('deviation', 0):.2f}米" if problem.get('deviation') is not None else "-",
                "原始坐标": f"({problem.get('shp_coord', [0, 0])[0]:.6f}, {problem.get('shp_coord', [0, 0])[1]:.6f})" if problem.get('shp_coord') and len(problem.get('shp_coord', [])) >= 2 else "-",
                "数据库坐标": f"({problem.get('db_coord', [0, 0])[0]:.6f}, {problem.get('db_coord', [0, 0])[1]:.6f})" if problem.get('db_coord') and len(problem.get('db_coord', [])) >= 2 else "-",
                "问题类型": problem.get('type', ''),
            }
            df_data.append(row)
        
        df = pd.DataFrame(df_data)
        
        # 保存为CSV（使用UTF-8编码，带BOM以支持Excel打开）
        df.to_csv(file_path, index=False, encoding='utf-8-sig')
        
        return file_path
    except Exception as e:
        print(f"[验证辅助] 保存CSV失败: {e}")
        return None


class PaginationHelper:
    """分页辅助类"""
    
    def __init__(self, page_size: int = 100):
        """
        初始化分页辅助类
        
        Args:
            page_size: 每页显示的数据条数
        """
        self.page_size = page_size
        self.current_page = 1
        self.total_items = 0
        self.total_pages = 0
    
    def set_total_items(self, total: int):
        """设置总数据条数"""
        self.total_items = total
        self.total_pages = (total + self.page_size - 1) // self.page_size if total > 0 else 1
        # 确保当前页不超过总页数
        if self.current_page > self.total_pages:
            self.current_page = self.total_pages if self.total_pages > 0 else 1
    
    def get_page_data(self, all_data: List) -> List:
        """获取当前页的数据"""
        if not all_data:
            return []
        
        start_idx = (self.current_page - 1) * self.page_size
        end_idx = start_idx + self.page_size
        return all_data[start_idx:end_idx]
    
    def go_to_page(self, page: int) -> bool:
        """
        跳转到指定页
        
        Returns:
            是否成功跳转
        """
        if 1 <= page <= self.total_pages:
            self.current_page = page
            return True
        return False
    
    def next_page(self) -> bool:
        """下一页"""
        return self.go_to_page(self.current_page + 1)
    
    def prev_page(self) -> bool:
        """上一页"""
        return self.go_to_page(self.current_page - 1)
    
    def first_page(self) -> bool:
        """第一页"""
        return self.go_to_page(1)
    
    def last_page(self) -> bool:
        """最后一页"""
        return self.go_to_page(self.total_pages)
    
    def get_page_info(self) -> Dict:
        """获取分页信息"""
        return {
            'current_page': self.current_page,
            'total_pages': self.total_pages,
            'total_items': self.total_items,
            'page_size': self.page_size,
            'start_item': (self.current_page - 1) * self.page_size + 1 if self.total_items > 0 else 0,
            'end_item': min(self.current_page * self.page_size, self.total_items),
        }

