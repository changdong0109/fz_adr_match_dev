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
    def load_shp(file_path: str) -> Tuple[List[Dict], str]:
        """
        加载 SHP 文件（使用 QGIS API）
        
        SHP文件组成：
        - .shp: 几何数据（点、线、面）
        - .shx: 索引文件（快速访问）
        - .dbf: 属性数据（表格数据，包含所有字段）
        - .prj: 投影信息（可选）
        - .cpg: 编码信息（可选，用于.dbf文件）
        
        QGIS会自动查找同名的.shx和.dbf文件，读取完整的SHP数据。
        
        Args:
            file_path: .shp文件路径（QGIS会自动查找同名的.shx和.dbf）
            
        Returns:
            (data_list, geometry_field_name)
            - data_list: 包含属性数据和几何数据的字典列表
            - geometry_field_name: 几何字段名（'geometry'）
        """
        try:
            from qgis.core import QgsVectorLayer, QgsFeature, QgsWkbTypes
            from qgis.PyQt.QtCore import QVariant
            
            data = []
            geometry_col_name = 'geometry'
            
            # 确保文件路径存在
            if not os.path.exists(file_path):
                raise IOError(f"SHP文件不存在: {file_path}")
            
            # 检查必需的辅助文件是否存在
            base_path = os.path.splitext(file_path)[0]
            shx_path = base_path + '.shx'
            dbf_path = base_path + '.dbf'
            
            if not os.path.exists(shx_path):
                raise IOError(f"缺少索引文件: {shx_path}")
            if not os.path.exists(dbf_path):
                raise IOError(f"缺少属性文件: {dbf_path}")
            
            # 使用QGIS API加载SHP文件
            # QGIS会自动处理.shx和.dbf文件
            layer = QgsVectorLayer(file_path, "temp_layer", "ogr")
            
            if not layer.isValid():
                raise IOError(f"无法加载SHP文件: {layer.error().message()}")
            
            # 获取坐标系信息
            crs = layer.crs()
            crs_str = crs.authid() if crs.isValid() else None
            
            # 获取所有字段名（来自.dbf文件）
            fields = layer.fields()
            field_names = [field.name() for field in fields]
            
            # 遍历所有要素
            features = layer.getFeatures()
            for feature in features:
                row = {}
                
                # 获取属性数据（来自.dbf文件）
                for field_name in field_names:
                    value = feature.attribute(field_name)
                    # 处理QVariant类型
                    if isinstance(value, QVariant):
                        if value.isNull():
                            row[field_name] = None
                        else:
                            row[field_name] = value.value()
                    else:
                        row[field_name] = value
                
                # 获取几何数据（来自.shp文件）
                geom = feature.geometry()
                if geom and not geom.isEmpty():
                    # 转换为WKT格式
                    wkt_str = geom.asWkt()
                    row[geometry_col_name] = wkt_str
                else:
                    row[geometry_col_name] = ''
                
                # 如果有坐标系信息，也保存
                if crs_str:
                    row['crs'] = crs_str
                
                data.append(row)
            
            if not data:
                raise ValueError(f"SHP文件为空或没有要素: {file_path}")
            
            return data, geometry_col_name
            
        except ImportError as e:
            raise ImportError(f"QGIS API不可用: {e}")
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
    
    @staticmethod
    def save_to_csv(data: List[Dict], output_path: str, encoding: str = 'utf-8-sig'):
        """
        将数据保存为 CSV 文件
        
        Args:
            data: 数据列表（List[Dict]）
            output_path: 输出文件路径
            encoding: 编码格式（默认 utf-8-sig，支持 Excel 打开）
        """
        if not data:
            raise ValueError("数据为空，无法保存")
        
        try:
            import csv
            # 获取所有字段名（合并所有记录的键）
            all_fields = set()
            for row in data:
                all_fields.update(row.keys())
            fieldnames = sorted(all_fields)
            
            # 确保输出目录存在
            output_dir = os.path.dirname(output_path)
            if output_dir:
                os.makedirs(output_dir, exist_ok=True)
            
            # 写入 CSV
            with open(output_path, 'w', encoding=encoding, newline='') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                for row in data:
                    # 处理 None 值和非字符串值
                    clean_row = {}
                    for key in fieldnames:
                        value = row.get(key)
                        if value is None:
                            clean_row[key] = ''
                        elif isinstance(value, (dict, list)):
                            # 复杂对象转为 JSON 字符串
                            clean_row[key] = json.dumps(value, ensure_ascii=False)
                        else:
                            # 直接转换为字符串（WKT格式的几何数据已经是字符串）
                            clean_row[key] = str(value)
                    writer.writerow(clean_row)
        except Exception as e:
            raise IOError(f"Failed to save CSV: {e}")
    
    @staticmethod
    def convert_to_csv(input_path: str, output_path: str, encoding: str = 'utf-8-sig') -> str:
        """
        将任意支持格式的文件转换为 CSV
        
        Args:
            input_path: 输入文件路径（Excel/SHP/CSV等）
            output_path: 输出 CSV 文件路径
            encoding: 输出编码格式
            
        Returns:
            输出文件路径
        """
        # 加载数据
        data, geometry_col = DataLoader.auto_load(input_path)
        
        # 如果数据为空，抛出异常
        if not data:
            raise ValueError(f"文件 {input_path} 没有数据")
        
        # 保存为 CSV
        DataLoader.save_to_csv(data, output_path, encoding)
        
        return output_path