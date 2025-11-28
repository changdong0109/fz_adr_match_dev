"""
数据加载器 - 支持 CSV、Excel、SHP 等多种格式
"""

import os
import json
from typing import List, Dict, Tuple, Optional
from pathlib import Path


class DataLoader:
    """多格式数据加载器"""

    @staticmethod
    def load_csv(file_path: str, encoding: str = 'utf-8') -> List[Dict]:
        """加载 CSV 文件"""
        try:
            import csv
            data = []
            with open(file_path, 'r', encoding=encoding) as f:
                reader = csv.DictReader(f)
                for row in reader:
                    data.append(row)
            return data
        except Exception as e:
            raise IOError(f"Failed to load CSV: {e}")

    @staticmethod
    def load_excel(file_path: str, sheet_name: str = None) -> List[Dict]:
        """加载 Excel 文件"""
        try:
            import openpyxl
            wb = openpyxl.load_workbook(file_path, data_only=True)
            
            if sheet_name is None:
                sheet = wb.active
            else:
                sheet = wb[sheet_name]
            
            data = []
            headers = None
            
            for row_idx, row in enumerate(sheet.iter_rows(values_only=True)):
                if row_idx == 0:
                    headers = row
                else:
                    if headers:
                        row_dict = {headers[i]: row[i] for i in range(len(headers)) if i < len(row)}
                        data.append(row_dict)
            
            return data
        except ImportError:
            raise ImportError("openpyxl not installed. Run: pip install openpyxl")
        except Exception as e:
            raise IOError(f"Failed to load Excel: {e}")

    @staticmethod
    def load_shp(file_path: str) -> Tuple[List[Dict], List[str]]:
        """
        加载 SHP 文件（需要 fiona 或 shapefile）
        
        Returns:
            (data_list, geometry_field_name)
        """
        try:
            import fiona
            data = []
            geometry_col_name = 'geometry'
            
            with fiona.open(file_path) as src:
                for feature in src:
                    row = dict(feature['properties'])
                    row[geometry_col_name] = feature['geometry']
                    data.append(row)
            
            return data, geometry_col_name
        except ImportError:
            raise ImportError("fiona not installed. Run: pip install fiona")
        except Exception as e:
            raise IOError(f"Failed to load SHP: {e}")

    @staticmethod
    def load_geojson(file_path: str) -> Tuple[List[Dict], str]:
        """加载 GeoJSON 文件"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                geojson = json.load(f)
            
            data = []
            for feature in geojson.get('features', []):
                row = dict(feature.get('properties', {}))
                row['geometry'] = feature.get('geometry')
                data.append(row)
            
            return data, 'geometry'
        except Exception as e:
            raise IOError(f"Failed to load GeoJSON: {e}")

    @staticmethod
    def auto_load(file_path: str) -> Tuple[List[Dict], Optional[str]]:
        """
        自动检测格式并加载

        Returns:
            (data, geometry_column_name or None)
        """
        file_path = str(file_path)
        ext = Path(file_path).suffix.lower()
        
        try:
            if ext == '.csv':
                # 尝试不同编码
                for encoding in ['utf-8', 'gbk', 'gb2312', 'latin-1']:
                    try:
                        return DataLoader.load_csv(file_path, encoding), None
                    except:
                        continue
                raise IOError(f"Cannot load CSV with any supported encoding")
            
            elif ext in ['.xlsx', '.xls']:
                return DataLoader.load_excel(file_path), None
            
            elif ext == '.shp':
                return DataLoader.load_shp(file_path)
            
            elif ext == '.geojson':
                return DataLoader.load_geojson(file_path)
            
            else:
                raise ValueError(f"Unsupported file format: {ext}")
        
        except Exception as e:
            raise Exception(f"Error loading {file_path}: {e}")
