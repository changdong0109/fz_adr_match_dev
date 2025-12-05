"""
CSV还原为SHP文件转换器
将包含geometry字段（WKT格式）的CSV文件还原为SHP格式
"""
import os
from typing import Optional, Callable, Tuple
from pathlib import Path


class CsvToShpConverter:
    """CSV还原为SHP转换器"""
    
    def __init__(self, log_callback: Optional[Callable[[str, str], None]] = None):
        """
        Args:
            log_callback: 日志回调函数，接收 (message, level) 参数
        """
        self._log = log_callback or (lambda msg, level: None)
    
    def convert_csv_to_shp(self, csv_path: str, output_shp_path: str) -> Tuple[bool, str]:
        """
        将CSV文件还原为SHP文件
        
        Args:
            csv_path: 输入的CSV文件路径（必须包含geometry字段，WKT格式）
            output_shp_path: 输出的SHP文件路径（不需要扩展名，会自动生成.shp等文件）
            
        Returns:
            (success, message) - 成功标志和消息
        """
        try:
            from qgis.core import (
                QgsVectorLayer, QgsFields, QgsField, QgsFeature, 
                QgsGeometry, QgsWkbTypes, QgsCoordinateReferenceSystem,
                QgsVectorFileWriter, QgsVectorFileWriterOptions,
                QgsProject
            )
            from qgis.PyQt.QtCore import QVariant
            
            # 检查CSV文件是否存在
            if not os.path.exists(csv_path):
                return False, f"CSV文件不存在: {csv_path}"
            
            # 读取CSV文件
            import csv
            data = []
            field_names = []
            geometry_col = None
            crs_str = None
            
            # 尝试不同的编码
            for encoding in ['utf-8', 'gbk', 'gb2312', 'utf-8-sig']:
                try:
                    with open(csv_path, 'r', encoding=encoding) as f:
                        reader = csv.DictReader(f)
                        field_names = reader.fieldnames or []
                        
                        # 查找geometry字段
                        for col in field_names:
                            if col.lower() == 'geometry':
                                geometry_col = col
                                break
                        
                        if not geometry_col:
                            return False, "CSV文件中未找到geometry字段"
                        
                        # 读取所有数据
                        for row in reader:
                            data.append(row)
                            # 获取CRS信息（从第一行读取）
                            if not crs_str and 'crs' in row:
                                crs_str = row.get('crs', '').strip()
                    break
                except UnicodeDecodeError:
                    continue
            
            if not data:
                return False, "CSV文件为空或无法读取"
            
            self._log(f"[转换器] 读取CSV文件: {len(data)} 条记录", "info")
            
            # 解析第一条记录的几何类型
            first_geom_str = data[0].get(geometry_col, '').strip()
            if not first_geom_str:
                return False, "第一条记录的geometry字段为空，无法确定几何类型"
            
            # 解析WKT格式，确定几何类型
            geom_type = self._detect_geometry_type(first_geom_str)
            if not geom_type:
                return False, f"无法识别几何类型: {first_geom_str[:50]}"
            
            # 创建QGIS字段定义和字段名映射（SHP字段名最多10个字符）
            fields = QgsFields()
            field_name_map = {}  # 原始字段名 -> 短字段名映射
            
            # 添加所有属性字段（排除geometry和crs）
            for field_name in field_names:
                if field_name.lower() not in ['geometry', 'crs']:
                    # SHP文件字段名限制：最多10个字符
                    short_field_name = field_name[:10] if len(field_name) > 10 else field_name
                    # 如果短字段名已存在，添加序号
                    counter = 1
                    original_short = short_field_name
                    while short_field_name in field_name_map.values():
                        suffix = str(counter)[:2]  # 最多2位序号
                        short_field_name = original_short[:10-len(suffix)] + suffix
                        counter += 1
                    
                    field_name_map[field_name] = short_field_name
                    # 根据数据推断字段类型
                    field_type = self._detect_field_type(data, field_name)
                    fields.append(QgsField(short_field_name, field_type))
            
            # 设置坐标系
            crs = None
            if crs_str:
                try:
                    crs = QgsCoordinateReferenceSystem(crs_str)
                    if not crs.isValid():
                        self._log(f"[转换器] 警告: 坐标系无效，使用默认坐标系: {crs_str}", "warning")
                        crs = None
                except Exception as e:
                    self._log(f"[转换器] 警告: 无法解析坐标系 {crs_str}: {e}", "warning")
            
            # 确保输出目录存在
            output_dir = os.path.dirname(output_shp_path)
            if output_dir and not os.path.exists(output_dir):
                os.makedirs(output_dir, exist_ok=True)
            
            # 创建SHP文件写入器
            options = QgsVectorFileWriterOptions()
            options.driverName = "ESRI Shapefile"
            
            # 获取坐标转换上下文
            transform_context = QgsProject.instance().transformContext() if hasattr(QgsProject.instance(), 'transformContext') else None
            
            writer = QgsVectorFileWriter.create(
                output_shp_path,
                fields,
                geom_type,
                crs if crs and crs.isValid() else QgsCoordinateReferenceSystem(),
                transform_context,
                options
            )
            
            if writer.hasError() != QgsVectorFileWriter.NoError:
                return False, f"创建SHP文件失败: {writer.errorMessage()}"
            
            # 写入数据
            success_count = 0
            fail_count = 0
            
            for idx, row in enumerate(data):
                try:
                    feature = QgsFeature(fields)
                    
                    # 设置属性
                    for field in fields:
                        short_field_name = field.name()  # 这是短字段名
                        # 找到对应的原始字段名
                        original_field_name = None
                        for orig, short in field_name_map.items():
                            if short == short_field_name:
                                original_field_name = orig
                                break
                        
                        if original_field_name:
                            value = row.get(original_field_name, None)
                        else:
                            value = row.get(short_field_name, None)
                        
                        # 处理不同类型的值
                        if value is None or value == '':
                            feature.setAttribute(short_field_name, None)
                        else:
                            # 根据字段类型转换值
                            feature.setAttribute(short_field_name, self._convert_value(value, field.type()))
                    
                    # 设置几何
                    geom_str = row.get(geometry_col, '').strip()
                    if geom_str:
                        geom = QgsGeometry.fromWkt(geom_str)
                        if geom and not geom.isEmpty():
                            feature.setGeometry(geom)
                            if writer.addFeature(feature):
                                success_count += 1
                            else:
                                fail_count += 1
                                self._log(f"[转换器] 写入要素失败 (行 {idx+1}): {geom_str[:50]}", "warning")
                        else:
                            fail_count += 1
                            self._log(f"[转换器] 几何解析失败 (行 {idx+1}): {geom_str[:50]}", "warning")
                    else:
                        fail_count += 1
                        self._log(f"[转换器] 几何为空 (行 {idx+1})", "warning")
                        
                except Exception as e:
                    fail_count += 1
                    self._log(f"[转换器] 处理行 {idx+1} 失败: {e}", "error")
            
            # 关闭写入器
            del writer
            
            if success_count > 0:
                message = f"转换成功: {success_count} 条记录"
                if fail_count > 0:
                    message += f"，失败: {fail_count} 条"
                return True, message
            else:
                return False, f"转换失败: 所有 {len(data)} 条记录都无法写入"
                
        except ImportError as e:
            return False, f"QGIS API不可用: {e}"
        except Exception as e:
            return False, f"转换过程出错: {e}"
    
    def _detect_geometry_type(self, wkt_str: str) -> Optional[int]:
        """检测WKT字符串的几何类型"""
        wkt_upper = wkt_str.upper().strip()
        
        if wkt_upper.startswith('POINT'):
            return QgsWkbTypes.Point
        elif wkt_upper.startswith('LINESTRING') or wkt_upper.startswith('MULTILINESTRING'):
            return QgsWkbTypes.LineString
        elif wkt_upper.startswith('POLYGON') or wkt_upper.startswith('MULTIPOLYGON'):
            return QgsWkbTypes.Polygon
        else:
            return None
    
    def _detect_field_type(self, data: list, field_name: str) -> int:
        """根据数据推断字段类型"""
        if not data:
            return QVariant.String
        
        # 检查前100条数据
        sample_size = min(100, len(data))
        sample_values = [row.get(field_name, '') for row in data[:sample_size]]
        
        # 尝试判断类型
        is_int = True
        is_float = True
        
        for val in sample_values:
            if val is None or val == '':
                continue
            try:
                int(str(val))
            except (ValueError, TypeError):
                is_int = False
                break
        
        if is_int:
            return QVariant.Int
        
        for val in sample_values:
            if val is None or val == '':
                continue
            try:
                float(str(val))
            except (ValueError, TypeError):
                is_float = False
                break
        
        if is_float:
            return QVariant.Double
        
        # 默认字符串类型
        return QVariant.String
    
    def _convert_value(self, value, field_type: int) -> any:
        """根据字段类型转换值"""
        from qgis.PyQt.QtCore import QVariant
        
        if value is None or value == '':
            return None
        
        try:
            if field_type == QVariant.Int:
                return int(float(str(value)))
            elif field_type == QVariant.Double:
                return float(str(value))
            else:
                return str(value)
        except (ValueError, TypeError):
            return str(value)

