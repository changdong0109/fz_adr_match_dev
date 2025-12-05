# -*- coding: utf-8 -*-
"""
Step5 验证引擎
验证数据库点图层与匹配结果的一致性
"""
import os
import json
import pandas as pd
from typing import List, Dict, Optional, Callable, Tuple
from qgis.core import QgsVectorLayer, QgsFeature, QgsPointXY, QgsDistanceArea, QgsCoordinateTransform, QgsCoordinateReferenceSystem, QgsProject


class ValidationEngine:
    """验证引擎：验证数据库点图层与匹配结果的一致性"""
    
    def __init__(self, log_callback: Optional[Callable[[str, str], None]] = None,
                 progress_callback: Optional[Callable[[int, int, str], None]] = None):
        self._log = log_callback or (lambda msg, level: None)
        self._progress = progress_callback or (lambda c, t, m: None)
        self._cancelled = False
    
    def cancel(self):
        """取消验证"""
        self._cancelled = True
    
    def validate(self,
                 match_result_file: str,
                 original_customer_file: str,
                 db_index: Dict,  # 预先构建的数据库索引（在主线程中构建）
                 shp_index: Dict,  # 预先构建的SHP索引（在主线程中构建，已转换为数据库坐标系）
                original_shp_gid_field: str,
                database_match_field: str,  # 固定为'name'
                source_match_fields: List[str],  # 匹配结果文件中的字段名（用于匹配结果验证）
                deviation_threshold: float = 10.0,
                db_crs: Optional[QgsCoordinateReferenceSystem] = None,
                original_match_fields: Optional[List[str]] = None) -> Dict:  # Step2配置的原始字段名（用于原始客户数据验证）
        """
        执行验证
        
        Args:
            match_result_file: 匹配结果文件路径
            original_customer_file: 原始客户数据文件路径
            db_index: 预先构建的数据库索引（在主线程中构建）
            shp_index: 预先构建的SHP索引（在主线程中构建，已转换为数据库坐标系）
            original_shp_gid_field: 原始SHP图层的GID字段
            database_match_field: 数据库图层匹配字段（固定为'name'）
            source_match_fields: 源表匹配字段列表（多个字段，用于组合匹配数据库的name字段）
            deviation_threshold: 位置偏差阈值（米）
            db_crs: 数据库图层的坐标系（用于距离计算）
        
        Returns:
            验证结果字典
        """
        self._cancelled = False
        
        try:
            # 1. 加载数据（索引已在主线程中构建，直接使用）
            self._progress(5, 100, "加载匹配结果文件...")
            match_df = self._load_csv(match_result_file)
            if match_df is None or match_df.empty:
                return self._error_result("匹配结果文件加载失败")
            
            self._progress(10, 100, "加载原始客户数据文件...")
            original_df = self._load_csv(original_customer_file)
            if original_df is None or original_df.empty:
                return self._error_result("原始客户数据文件加载失败")
            
            # 2. 验证原始客户数据在数据库中的完整性（索引已预先构建）
            # 原始客户数据验证需要使用原始字段名（Step2配置的字段名），而不是匹配结果文件中的字段名
            original_fields = original_match_fields if original_match_fields else source_match_fields  # 如果没有提供，使用source_match_fields作为兜底
            self._progress(30, 100, "验证原始客户数据完整性...")
            original_completeness = self._validate_original_completeness(
                original_df, db_index, original_fields
            )
            
            # 5. 验证匹配结果在数据库中的完整性
            self._progress(50, 100, "验证匹配结果完整性...")
            match_completeness = self._validate_match_completeness(
                match_df, db_index, source_match_fields
            )
            
            # 6. 验证位置偏差（可选，如果原始SHP图层存在）
            self._progress(70, 100, "验证位置偏差...")
            deviation_stats = self._validate_position_deviation(
                match_df, shp_index, db_index,
                original_shp_gid_field, database_match_field,
                source_match_fields,
                deviation_threshold,
                db_crs  # 传递数据库坐标系
            )
            
            # 7. 验证重复数据
            self._progress(85, 100, "验证重复数据...")
            duplicate_stats = self._validate_duplicates(
                match_df, db_index, source_match_fields
            )
            
            # 8. 汇总问题数据
            self._progress(90, 100, "汇总问题数据...")
            problem_data = self._collect_problem_data(
                match_df, original_df, db_index, shp_index,
                match_completeness, deviation_stats, duplicate_stats,
                original_shp_gid_field, database_match_field,
                source_match_fields, deviation_threshold,
                db_crs  # 传递数据库坐标系
            )
            
            self._progress(100, 100, "验证完成")
            
            return {
                "success": True,
                "statistics": {
                    "original_total": len(original_df),
                    "match_total": len(match_df),
                    "original_completeness": original_completeness,
                    "match_completeness": match_completeness,
                    "deviation": deviation_stats,
                    "duplicates": duplicate_stats
                },
                "problem_data": problem_data
            }
        
        except Exception as e:
            self._log(f"[验证引擎] 验证失败: {e}", "error")
            import traceback
            self._log(f"[验证引擎] 错误详情: {traceback.format_exc()}", "error")
            return self._error_result(f"验证失败: {e}")
    
    def _load_csv(self, file_path: str) -> Optional[pd.DataFrame]:
        """加载CSV文件"""
        try:
            for enc in ['utf-8', 'gbk', 'gb2312', 'utf-8-sig']:
                try:
                    return pd.read_csv(file_path, encoding=enc)
                except UnicodeDecodeError:
                    continue
            return None
        except Exception as e:
            self._log(f"[验证引擎] 加载CSV失败: {file_path}, {e}", "error")
            return None
    
    def _build_database_index(self, layer: QgsVectorLayer) -> Dict:
        """
        构建数据库图层索引
        返回: {
            'code': {code值: [feature1, feature2, ...]},  # 通过code字段索引（用于GID匹配）
            'name': {name值: [feature1, feature2, ...]}   # 通过name字段索引（用于字段匹配）
        }
        """
        code_index = {}
        name_index = {}
        features = layer.getFeatures()
        
        code_count = 0
        name_count = 0
        total_features = 0
        processed_features = 0
        
        for feature in features:
            total_features += 1
            processed_features += 1
            # 每处理200个要素更新一次进度，并让出控制权（更频繁，避免卡死）
            if processed_features % 200 == 0:
                self._progress(15, 100, f"构建数据库图层索引... ({processed_features})")
                # 让出控制权，避免UI卡死（在主线程中需要调用processEvents）
                from qgis.PyQt.QtWidgets import QApplication
                QApplication.processEvents()
                # 额外等待，确保UI有时间响应
                from qgis.PyQt.QtCore import QThread
                QThread.msleep(10)
            # 构建code索引（用于GID匹配）
            code_val = str(feature.attribute('code') or '').strip()
            if code_val:
                code_key = code_val.lower()
                if code_key not in code_index:
                    code_index[code_key] = []
                code_index[code_key].append(feature)
                code_count += 1
            
            # 构建name索引（用于字段匹配）
            name_val = str(feature.attribute('name') or '').strip()
            if name_val:
                name_key = name_val.lower()
                if name_key not in name_index:
                    name_index[name_key] = []
                name_index[name_key].append(feature)
                name_count += 1
        
        self._log(f"[验证引擎] 数据库图层索引构建完成: 总要素数={total_features}, code索引={len(code_index)}个唯一值, name索引={len(name_index)}个唯一值", "info")
        
        # 输出前几个code和name值作为示例（用于验证数据是否正确加载）
        code_samples = list(code_index.keys())[:5]
        name_samples = list(name_index.keys())[:5]
        if code_samples:
            self._log(f"[验证引擎] code字段示例值: {code_samples}", "info")
        if name_samples:
            # name值可能很长，只显示前50个字符
            name_samples_short = [n[:50] + "..." if len(n) > 50 else n for n in name_samples]
            self._log(f"[验证引擎] name字段示例值: {name_samples_short}", "info")
        
        # 输出数据库图层的名称，确认使用的是正确的图层
        self._log(f"[验证引擎] 数据库图层名称: {layer.name()}, 数据源: {layer.dataProvider().dataSourceUri() if layer.dataProvider() else 'N/A'}", "info")
        
        return {
            'code': code_index,
            'name': name_index
        }
    
    def _build_shp_index(self, layer: QgsVectorLayer, gid_field: str, coord_transform: Optional[QgsCoordinateTransform] = None) -> Dict:
        """
        构建原始SHP图层索引
        返回: {gid: (x, y)}
        
        Args:
            layer: SHP图层
            gid_field: GID字段名
            coord_transform: 可选的坐标转换器（如果SHP坐标系与数据库坐标系不同）
        """
        index = {}
        features = layer.getFeatures()
        
        processed_features = 0
        for feature in features:
            processed_features += 1
            # 每处理200个要素更新一次进度，并让出控制权（更频繁，避免卡死）
            if processed_features % 200 == 0:
                self._progress(20, 100, f"构建原始SHP图层索引... ({processed_features})")
                # 让出控制权，避免UI卡死（在主线程中需要调用processEvents）
                from qgis.PyQt.QtWidgets import QApplication
                QApplication.processEvents()
                # 额外等待，确保UI有时间响应
                from qgis.PyQt.QtCore import QThread
                QThread.msleep(10)
            gid_val = feature.attribute(gid_field)
            if gid_val is None:
                continue
            
            # 统一转换为整数字符串（GID都是整数）
            try:
                # 先转换为整数，再转为字符串，确保格式统一
                gid_int = int(float(str(gid_val).strip()))
                gid = str(gid_int)
            except (ValueError, TypeError):
                continue
            
            if not gid:
                continue
            
            geom = feature.geometry()
            if geom and geom.type() == 0:  # Point
                point = geom.asPoint()
                original_point = point  # 保存原始坐标用于日志
                
                # 如果提供了坐标转换器，进行坐标转换
                if coord_transform and coord_transform.isValid():
                    try:
                        point = coord_transform.transform(point)
                        # 记录前几个转换示例
                        if len(index) < 3:
                            self._log(f"[验证引擎] 坐标转换示例 (GID={gid}): ({original_point.x():.6f}, {original_point.y():.6f}) -> ({point.x():.6f}, {point.y():.6f})", "info")
                    except Exception as e:
                        self._log(f"[验证引擎] 坐标转换失败 (GID={gid}): {e}", "warning")
                        continue
                elif coord_transform is None and len(index) < 3:
                    # 即使不需要转换，也记录前几个坐标（用于确认）
                    self._log(f"[验证引擎] SHP坐标示例 (GID={gid}, 无需转换): ({point.x():.6f}, {point.y():.6f})", "info")
                
                index[gid] = (point.x(), point.y())
        
        # 添加调试日志
        self._log(f"[验证引擎] 原始SHP图层索引构建完成: 总要素数={len(index)}, 示例GID={list(index.keys())[:5] if index else []}", "info")
        
        return index
    
    def _validate_original_completeness(self, df: pd.DataFrame, db_index: Dict,
                                       source_match_fields: List[str]) -> Dict:
        """
        验证原始客户数据在数据库中的完整性
        
        使用配置的多个字段分别匹配数据库的name字段
        """
        total = len(df)
        found = 0
        missing = 0
        
        name_index = db_index.get('name', {})
        
        for _, row in df.iterrows():
            matched = False
            
            # 用配置的多个字段分别匹配数据库的name字段
            if source_match_fields:
                for field in source_match_fields:
                    val = str(row.get(field, '') or '').strip()
                    if val and val.lower() in name_index:
                        # 字段匹配成功
                        found += 1
                        matched = True
                        break
            
            if not matched:
                missing += 1
        
        return {
            "total": total,
            "found": found,
            "missing": missing,
            "completeness_rate": (found / total * 100) if total > 0 else 0
        }
    
    def _validate_match_completeness(self, match_df: pd.DataFrame, db_index: Dict,
                                    source_match_fields: List[str]) -> Dict:
        """
        验证匹配结果在数据库中的完整性
        
        匹配逻辑：
        1. 优先用匹配结果中的GID匹配数据库的code字段
           - 优先使用[目标:表名]gid字段（通常是数字，如358136.0）
           - 其次使用[目标:表名]code字段（可能带前缀，如GSH00001249）
           - 注意：数据库的code字段是纯数字，所以优先用gid字段匹配
        2. 如果GID匹配不到，再用配置的多个字段分别匹配数据库的name字段
        """
        total = len(match_df)
        found = 0
        missing = 0
        
        code_index = db_index.get('code', {})
        name_index = db_index.get('name', {})
        
        for _, row in match_df.iterrows():
            matched = False
            
            # 1. 优先用GID匹配（优先查找[目标:表名]gid字段，其次查找[目标:表名]code字段）
            # 注意：gid字段通常是数字，code字段可能带前缀（如GSH），所以优先用gid
            target_gid = None
            # 先查找gid字段（优先）
            for col in match_df.columns:
                if '[目标:' in col and 'gid' in col.lower() and 'code' not in col.lower():
                    gid_val = str(row.get(col, '') or '').strip()
                    if gid_val:
                        target_gid = gid_val.lower()
                        break
            # 如果gid字段没有值，再查找code字段
            if not target_gid:
                for col in match_df.columns:
                    if '[目标:' in col and 'code' in col.lower():
                        code_val = str(row.get(col, '') or '').strip()
                        if code_val:
                            target_gid = code_val.lower()
                            break
            
            if target_gid and target_gid in code_index:
                # GID匹配成功
                found += 1
                matched = True
                continue
            
            # 2. 如果GID匹配不到，用配置的多个字段分别匹配数据库的name字段
            if not matched and source_match_fields:
                for field in source_match_fields:
                    val = str(row.get(field, '') or '').strip()
                    if val and val.lower() in name_index:
                        # 字段匹配成功
                        found += 1
                        matched = True
                        break
                
            if not matched:
                missing += 1
        
        return {
            "total": total,
            "found": found,
            "missing": missing,
            "completeness_rate": (found / total * 100) if total > 0 else 0
        }
    
    def _validate_position_deviation(self, match_df: pd.DataFrame, shp_index: Dict,
                                    db_index: Dict, shp_gid_field: str,
                                    db_field: str,
                                    source_fields: List[str],
                                    threshold: float,
                                    db_crs: Optional[QgsCoordinateReferenceSystem] = None) -> Dict:
        """验证位置偏差（支持多个字段组合）"""
        within_threshold = 0
        exceed_threshold = 0
        no_shp_coord = 0
        no_db_coord = 0
        
        # 创建距离计算器
        distance_calc = QgsDistanceArea()
        distance_calc.setEllipsoid('WGS84')
        # 如果提供了数据库坐标系，使用它；否则根据坐标范围判断
        if db_crs and db_crs.isValid():
            distance_calc.setSourceCrs(db_crs, QgsProject.instance().transformContext())
        
        for _, row in match_df.iterrows():
            # 获取原始SHP坐标（通过匹配结果中的目标表GID字段）
            # 优先查找gid字段（不包含code），其次查找其他包含gid的字段
            gid = None
            # 先查找纯gid字段（不包含code）
            for col in match_df.columns:
                if '[目标:' in col and 'gid' in col.lower() and 'code' not in col.lower():
                    gid_val = row.get(col)
                    if gid_val is not None:
                        try:
                            # 统一转换为整数字符串（GID都是整数）
                            gid_int = int(float(str(gid_val).strip()))
                            gid = str(gid_int)
                            break
                        except (ValueError, TypeError):
                            continue
            # 如果没找到，再查找其他包含gid的字段（作为备用）
            if not gid:
                for col in match_df.columns:
                    if '[目标:' in col and 'gid' in col.lower():
                        gid_val = row.get(col)
                        if gid_val is not None:
                            try:
                                # 统一转换为整数字符串（GID都是整数）
                                gid_int = int(float(str(gid_val).strip()))
                                gid = str(gid_int)
                                break
                            except (ValueError, TypeError):
                                continue
            
            # 如果没找到目标表GID字段，尝试使用shp_gid_field
            if not gid:
                gid_val = row.get(shp_gid_field)
                if gid_val is not None:
                    try:
                        gid_int = int(float(str(gid_val).strip()))
                        gid = str(gid_int)
                    except (ValueError, TypeError):
                        pass
            
            if not gid or gid not in shp_index:
                no_shp_coord += 1
                continue
            
            shp_x, shp_y = shp_index[gid]
            # 检查坐标是否有效
            import math
            if not isinstance(shp_x, (int, float)) or not isinstance(shp_y, (int, float)):
                no_shp_coord += 1
                continue
            if math.isnan(shp_x) or math.isnan(shp_y) or math.isinf(shp_x) or math.isinf(shp_y):
                no_shp_coord += 1
                continue
            
            shp_point = QgsPointXY(shp_x, shp_y)
            
            # 1. 优先用GID匹配数据库的code字段
            # 注意：优先使用gid字段（通常是数字），其次使用code字段（可能带前缀）
            target_code = None
            # 先查找gid字段（优先）
            for col in match_df.columns:
                if '[目标:' in col and 'gid' in col.lower() and 'code' not in col.lower():
                    gid_val = str(row.get(col, '') or '').strip()
                    if gid_val:
                        target_code = gid_val.lower()
                        break
            # 如果gid字段没有值，再查找code字段
            if not target_code:
                for col in match_df.columns:
                    if '[目标:' in col and 'code' in col.lower():
                        code_val = str(row.get(col, '') or '').strip()
                        if code_val:
                            target_code = code_val.lower()
                            break
            
            code_index = db_index.get('code', {})
            name_index = db_index.get('name', {})
            db_data = None
            
            if target_code and target_code in code_index:
                # GID匹配成功（使用纯数据索引）
                db_data = code_index[target_code][0] if code_index[target_code] else None
            elif source_fields:
                # 2. 如果GID匹配不到，用配置的多个字段分别匹配数据库的name字段
                for field in source_fields:
                    val = str(row.get(field, '') or '').strip()
                    if val and val.lower() in name_index:
                        db_data = name_index[val.lower()][0] if name_index[val.lower()] else None
                        break
            
            if not db_data or 'x' not in db_data or 'y' not in db_data:
                no_db_coord += 1
                continue
            
            db_x = db_data['x']
            db_y = db_data['y']
            # 检查数据库坐标是否有效
            if not isinstance(db_x, (int, float)) or not isinstance(db_y, (int, float)):
                no_db_coord += 1
                continue
            if math.isnan(db_x) or math.isnan(db_y) or math.isinf(db_x) or math.isinf(db_y):
                no_db_coord += 1
                continue
            
            db_point = QgsPointXY(db_x, db_y)
            
            # 计算距离（如果已设置坐标系，直接使用；否则根据坐标范围判断）
            if not db_crs or not db_crs.isValid():
                # 根据坐标范围判断坐标系：如果坐标在经纬度范围内，使用EPSG:4326；否则使用EPSG:3857
                if abs(shp_x) < 180 and abs(shp_y) < 90 and abs(db_x) < 180 and abs(db_y) < 90:
                    # 经纬度坐标（EPSG:4326）
                    crs = QgsCoordinateReferenceSystem('EPSG:4326')
                else:
                    # 投影坐标（EPSG:3857 Web Mercator）
                    crs = QgsCoordinateReferenceSystem('EPSG:3857')
                distance_calc.setSourceCrs(crs, QgsProject.instance().transformContext())
            
            distance = distance_calc.measureLine(shp_point, db_point)
            
            # 如果距离计算返回NaN，使用简单的欧几里得距离（假设坐标单位是米）
            if math.isnan(distance) or math.isinf(distance):
                distance = math.sqrt((shp_x - db_x) ** 2 + (shp_y - db_y) ** 2)
            
            # 检查距离是否有效
            if math.isnan(distance) or math.isinf(distance):
                no_db_coord += 1
                continue
            
            if distance <= threshold:
                within_threshold += 1
            else:
                exceed_threshold += 1
        
        total_checked = within_threshold + exceed_threshold
        total_attempted = len(match_df)  # 匹配结果总数（尝试检查的所有记录）
        
        # 添加调试日志
        self._log(f"[验证引擎] 位置偏差验证统计: 匹配结果总数={total_attempted}, 成功检查数={total_checked}, 阈值内={within_threshold}, 超过阈值={exceed_threshold}, 无SHP坐标={no_shp_coord}, 无数据库坐标={no_db_coord}", "info")
        
        return {
            "total_attempted": total_attempted,  # 匹配结果总数（尝试检查的所有记录）
            "total_checked": total_checked,  # 成功检查数（同时有SHP坐标和数据库坐标的记录）
            "within_threshold": within_threshold,
            "exceed_threshold": exceed_threshold,
            "no_shp_coord": no_shp_coord,  # 无法从原始SHP图层中获取坐标的记录数
            "no_db_coord": no_db_coord,  # 无法从数据库图层中获取坐标的记录数
            "within_rate": (within_threshold / total_checked * 100) if total_checked > 0 else 0
        }
    
    def _validate_duplicates(self, match_df: pd.DataFrame, db_index: Dict,
                            source_match_fields: List[str]) -> Dict:
        """
        验证重复数据
        
        匹配逻辑：
        1. 优先用GID匹配数据库的code字段
        2. 如果GID匹配不到，再用配置的多个字段分别匹配数据库的name字段
        """
        duplicate_values = set()
        duplicate_records = 0
        
        code_index = db_index.get('code', {})
        name_index = db_index.get('name', {})
        
        for _, row in match_df.iterrows():
            # 1. 优先用GID匹配
            # 注意：优先使用gid字段（通常是数字），其次使用code字段（可能带前缀）
            target_code = None
            # 先查找gid字段（优先）
            for col in match_df.columns:
                if '[目标:' in col and 'gid' in col.lower() and 'code' not in col.lower():
                    gid_val = str(row.get(col, '') or '').strip()
                    if gid_val:
                        target_code = gid_val.lower()
                        break
            # 如果gid字段没有值，再查找code字段
            if not target_code:
                for col in match_df.columns:
                    if '[目标:' in col and 'code' in col.lower():
                        code_val = str(row.get(col, '') or '').strip()
                        if code_val:
                            target_code = code_val.lower()
                            break
            
            if target_code and target_code in code_index:
                if len(code_index[target_code]) > 1:
                    duplicate_values.add(f"code:{target_code}")
                    duplicate_records += len(code_index[target_code])
                continue
            
            # 2. 如果GID匹配不到，用配置的多个字段分别匹配数据库的name字段
            if source_match_fields:
                for field in source_match_fields:
                    val = str(row.get(field, '') or '').strip()
                    if val and val.lower() in name_index:
                        if len(name_index[val.lower()]) > 1:
                            duplicate_values.add(f"name:{val.lower()}")
                            duplicate_records += len(name_index[val.lower()])
                    break
        
        return {
            "duplicate_values": len(duplicate_values),
            "duplicate_records": duplicate_records
        }
    
    def _collect_problem_data(self, match_df: pd.DataFrame, original_df: pd.DataFrame,
                            db_index: Dict, shp_index: Dict,
                            match_completeness: Dict, deviation_stats: Dict,
                            duplicate_stats: Dict,
                            shp_gid_field: str, db_name_field: str,
                            source_fields: List[str],
                            threshold: float,
                            db_crs: Optional[QgsCoordinateReferenceSystem] = None) -> Dict:
        """汇总问题数据（支持多个字段组合）"""
        import time
        start_time = time.time()
        self._log(f"[验证引擎] ========== 开始汇总问题数据 ==========", "info")
        self._log(f"[验证引擎] 输入数据: match_df行数={len(match_df)}, original_df行数={len(original_df)}", "info")
        self._log(f"[验证引擎] 索引大小: code_index={len(db_index.get('code', {}))}, name_index={len(db_index.get('name', {}))}, shp_index={len(shp_index)}", "info")
        
        missing_data = []
        deviation_data = []
        duplicate_data = []
        
        # 1. 缺失数据
        self._log(f"[验证引擎] [阶段1] 开始处理缺失数据...", "info")
        stage1_start = time.time()
        code_index = db_index.get('code', {})
        name_index = db_index.get('name', {})
        self._log(f"[验证引擎] [阶段1] 索引准备完成: code_index大小={len(code_index)}, name_index大小={len(name_index)}", "info")
        
        # 添加调试：记录前几个缺失数据的详细匹配过程
        missing_debug_count = 0
        max_debug_samples = 3
        
        total_rows = len(match_df)
        processed_count = 0
        self._log(f"[验证引擎] [阶段1] 开始遍历match_df，总行数={total_rows}", "info")
        
        for idx, row in match_df.iterrows():
            processed_count += 1
            # 每处理20条数据更新一次进度，并让出控制权（更频繁的更新，避免卡死）
            if processed_count % 20 == 0:
                elapsed = time.time() - stage1_start
                self._log(f"[验证引擎] [阶段1] 进度: {processed_count}/{total_rows} ({processed_count*100//total_rows}%), 已耗时={elapsed:.2f}秒", "info")
                progress = 90 + int((processed_count / total_rows) * 3)  # 90-93%用于缺失数据
                self._progress(progress, 100, f"汇总问题数据... ({processed_count}/{total_rows})")
                # 让出控制权，避免UI卡死（在后台线程中）
                from qgis.PyQt.QtCore import QThread
                QThread.msleep(20)  # 增加等待时间，确保UI有时间响应
            
            row_start_time = time.time()
            matched = False
            debug_info = {}
            
            # 1. 优先用GID匹配数据库的code字段
            # 注意：优先使用gid字段（通常是数字），其次使用code字段（可能带前缀）
            target_code = None
            # 先查找gid字段（优先）
            gid_search_start = time.time()
            for col in match_df.columns:
                if '[目标:' in col and 'gid' in col.lower() and 'code' not in col.lower():
                    gid_val = str(row.get(col, '') or '').strip()
                    if gid_val:
                        target_code = gid_val.lower()
                        debug_info['target_gid'] = gid_val  # 保留原始大小写用于显示
                        debug_info['target_gid_lower'] = target_code
                        debug_info['gid_source'] = 'gid_field'
                        break
            # 如果gid字段没有值，再查找code字段
            if not target_code:
                for col in match_df.columns:
                    if '[目标:' in col and 'code' in col.lower():
                        code_val = str(row.get(col, '') or '').strip()
                        if code_val:
                            target_code = code_val.lower()
                            debug_info['target_gid'] = code_val  # 保留原始大小写用于显示
                            debug_info['target_gid_lower'] = target_code
                            debug_info['gid_source'] = 'code_field'
                            break
            
            if target_code:
                if target_code in code_index:
                    matched = True
                    debug_info['match_method'] = 'gid_match'
                else:
                    debug_info['gid_not_found'] = True
                    # 检查是否有相似的code值（用于调试）
                    similar_codes = [c for c in code_index.keys() if target_code in c or c in target_code][:3]
                    if similar_codes:
                        debug_info['similar_codes'] = similar_codes
            
            # 2. 如果GID匹配不到，用配置的多个字段分别匹配数据库的name字段
            if not matched and source_fields:
                for field in source_fields:
                    val = str(row.get(field, '') or '').strip()
                    if val:
                        val_lower = val.lower()
                        debug_info.setdefault('tried_fields', []).append({
                            'field': field,
                            'value': val,
                            'value_lower': val_lower
                        })
                        
                        if val_lower in name_index:
                            matched = True
                            debug_info['match_method'] = f'field_match_{field}'
                            break
                        else:
                            # 检查是否有相似的name值（用于调试）
                            similar_names = [n for n in name_index.keys() if val_lower in n or n in val_lower][:2]
                            if similar_names:
                                debug_info.setdefault('similar_names', []).extend(similar_names)
            
            if not matched:
                row_dict_start = time.time()
                row_dict = row.to_dict()
                row_dict_time = time.time() - row_dict_start
                if processed_count <= 3:
                    self._log(f"[验证引擎] [阶段1] 第{processed_count}行: row.to_dict()耗时={row_dict_time:.4f}秒", "info")
                
                missing_data.append({
                    "index": idx,
                    "row": row_dict,
                    "db_code": None  # 缺失数据没有匹配到数据库，所以code为None
                })
                
                row_time = time.time() - row_start_time
                if processed_count <= 3:
                    self._log(f"[验证引擎] [阶段1] 第{processed_count}行: 总耗时={row_time:.4f}秒", "info")
                
        stage1_time = time.time() - stage1_start
        self._log(f"[验证引擎] [阶段1] 缺失数据处理完成: 找到{len(missing_data)}条缺失数据, 总耗时={stage1_time:.2f}秒", "info")
        
        # 2. 位置偏差数据
        self._log(f"[验证引擎] [阶段2] 开始处理位置偏差数据...", "info")
        stage2_start = time.time()
        
        # 输出前几个缺失数据的详细调试信息
        if missing_debug_count < max_debug_samples:
                    self._log(f"[验证引擎] 缺失数据调试 #{missing_debug_count + 1}: target_gid={debug_info.get('target_gid', 'None')}, match_method={debug_info.get('match_method', 'None')}", "info")
                    if debug_info.get('tried_fields'):
                        field_info = '; '.join([f"{f['field']}={f['value'][:30]}..." if len(f['value']) > 30 else f"{f['field']}={f['value']}" for f in debug_info['tried_fields'][:2]])
                        self._log(f"[验证引擎]   尝试匹配的字段: {field_info}", "info")
                    if debug_info.get('similar_codes'):
                        self._log(f"[验证引擎]   相似的code值: {debug_info['similar_codes']}", "info")
                    if debug_info.get('similar_names'):
                        self._log(f"[验证引擎]   相似的name值: {debug_info['similar_names'][:3]}", "info")
                    missing_debug_count += 1
        
        distance_calc = QgsDistanceArea()
        distance_calc.setEllipsoid('WGS84')
        self._log(f"[验证引擎] [阶段2] 距离计算器初始化完成", "info")
        
        # 添加调试：记录前几个GID查找失败的情况
        gid_failed_samples = []
        max_failed_samples = 3
        
        processed_count = 0
        total_rows = len(match_df)  # 确保total_rows已定义
        self._log(f"[验证引擎] [阶段2] 开始遍历match_df，总行数={total_rows}", "info")
        for idx, row in match_df.iterrows():
            processed_count += 1
            # 每处理20条数据更新一次进度，并让出控制权（更频繁的更新，避免卡死）
            if processed_count % 20 == 0:
                elapsed = time.time() - stage2_start
                self._log(f"[验证引擎] [阶段2] 进度: {processed_count}/{total_rows} ({processed_count*100//total_rows}%), 已耗时={elapsed:.2f}秒", "info")
                progress = 95 + int((processed_count / total_rows) * 3) if total_rows > 0 else 95  # 95-98%用于位置偏差
                self._progress(progress, 100, f"汇总问题数据... ({processed_count}/{total_rows})")
                # 让出控制权，避免UI卡死（在后台线程中）
                from qgis.PyQt.QtCore import QThread
                QThread.msleep(20)  # 增加等待时间，确保UI有时间响应
            
            row_start_time = time.time()
            # 获取原始SHP坐标（通过匹配结果中的目标表GID字段）
            # 优先查找gid字段（不包含code），其次查找其他包含gid的字段
            gid = None
            gid_field_name = None
            # 先查找纯gid字段（不包含code）
            for col in match_df.columns:
                if '[目标:' in col and 'gid' in col.lower() and 'code' not in col.lower():
                    gid_val = row.get(col)
                    if gid_val is not None:
                        try:
                            # 统一转换为整数字符串（GID都是整数）
                            gid_int = int(float(str(gid_val).strip()))
                            gid = str(gid_int)
                            gid_field_name = col
                            break
                        except (ValueError, TypeError):
                            continue
            # 如果没找到，再查找其他包含gid的字段（作为备用）
            if not gid:
                for col in match_df.columns:
                    if '[目标:' in col and 'gid' in col.lower():
                        gid_val = row.get(col)
                        if gid_val is not None:
                            try:
                                # 统一转换为整数字符串（GID都是整数）
                                gid_int = int(float(str(gid_val).strip()))
                                gid = str(gid_int)
                                gid_field_name = col
                                break
                            except (ValueError, TypeError):
                                continue
            
            if not gid:
                continue
            
            # 在shp_index中查找GID（类型已统一为整数字符串）
            if gid not in shp_index:
                # 记录失败的GID（用于调试）
                if len(gid_failed_samples) < max_failed_samples:
                    gid_failed_samples.append({
                        'gid': gid,
                        'field': gid_field_name,
                        'shp_index_size': len(shp_index),
                        'sample_gids': list(shp_index.keys())[:3] if shp_index else []
                    })
                continue
            
            shp_coord = shp_index[gid]
            
            shp_x, shp_y = shp_coord
            shp_point = QgsPointXY(shp_x, shp_y)
            
            # 1. 优先用GID匹配数据库的code字段
            # 注意：优先使用gid字段（通常是数字），其次使用code字段（可能带前缀）
            target_code = None
            # 先查找gid字段（优先）
            for col in match_df.columns:
                if '[目标:' in col and 'gid' in col.lower() and 'code' not in col.lower():
                    gid_val = str(row.get(col, '') or '').strip()
                    if gid_val:
                        target_code = gid_val.lower()
                        break
            # 如果gid字段没有值，再查找code字段
            if not target_code:
                for col in match_df.columns:
                    if '[目标:' in col and 'code' in col.lower():
                        code_val = str(row.get(col, '') or '').strip()
                        if code_val:
                            target_code = code_val.lower()
                            break
            
            code_index = db_index.get('code', {})
            name_index = db_index.get('name', {})
            db_data = None
            
            if target_code and target_code in code_index:
                # GID匹配成功（使用纯数据索引）
                db_data = code_index[target_code][0] if code_index[target_code] else None
            elif source_fields:
                # 2. 如果GID匹配不到，用配置的多个字段分别匹配数据库的name字段
                for field in source_fields:
                    val = str(row.get(field, '') or '').strip()
                    if val and val.lower() in name_index:
                        db_data = name_index[val.lower()][0] if name_index[val.lower()] else None
                        break
            
            if not db_data or 'x' not in db_data or 'y' not in db_data:
                continue
            
            db_x = db_data['x']
            db_y = db_data['y']
            # 检查数据库坐标是否有效
            import math
            if not isinstance(db_x, (int, float)) or not isinstance(db_y, (int, float)):
                continue
            if math.isnan(db_x) or math.isnan(db_y) or math.isinf(db_x) or math.isinf(db_y):
                continue
            
            db_point = QgsPointXY(db_x, db_y)
            
            # 计算距离（如果已设置坐标系，直接使用；否则根据坐标范围判断）
            if not db_crs or not db_crs.isValid():
                # 根据坐标范围判断坐标系：如果坐标在经纬度范围内，使用EPSG:4326；否则使用EPSG:3857
                if abs(shp_x) < 180 and abs(shp_y) < 90 and abs(db_x) < 180 and abs(db_y) < 90:
                    # 经纬度坐标（EPSG:4326）
                    crs = QgsCoordinateReferenceSystem('EPSG:4326')
                else:
                    # 投影坐标（EPSG:3857 Web Mercator）
                    crs = QgsCoordinateReferenceSystem('EPSG:3857')
                distance_calc.setSourceCrs(crs, QgsProject.instance().transformContext())
            
            distance = distance_calc.measureLine(shp_point, db_point)
            
            # 如果距离计算返回NaN，使用简单的欧几里得距离（假设坐标单位是米）
            if math.isnan(distance) or math.isinf(distance):
                distance = math.sqrt((shp_x - db_x) ** 2 + (shp_y - db_y) ** 2)
            
            # 添加调试日志（前3条）
            if len(deviation_data) < 3:
                self._log(f"[验证引擎] 位置偏差检查 #{len(deviation_data) + 1}: 距离={distance:.2f}米, 阈值={threshold}米, GID={gid}, SHP坐标=({shp_x:.6f}, {shp_y:.6f}), DB坐标=({db_x:.6f}, {db_y:.6f})", "info")
            
            if distance > threshold:
                # 获取匹配到的数据库code（使用纯数据索引）
                db_code_val = db_data.get('code', '').strip() if db_data else ''
                deviation_data.append({
                    "index": idx,
                    "row": row.to_dict(),
                    "deviation": distance,
                    "shp_coord": (shp_x, shp_y),
                    "db_coord": (db_point.x(), db_point.y()),
                    "db_code": db_code_val  # 记录匹配到的数据库code
                })
        
        stage2_time = time.time() - stage2_start
        self._log(f"[验证引擎] [阶段2] 位置偏差数据处理完成: 找到{len(deviation_data)}条偏差数据, 总耗时={stage2_time:.2f}秒", "info")
        
        # 3. 重复数据
        self._log(f"[验证引擎] [阶段3] 开始处理重复数据...", "info")
        stage3_start = time.time()
        code_index = db_index.get('code', {})
        name_index = db_index.get('name', {})
        self._log(f"[验证引擎] [阶段3] 索引准备完成: code_index大小={len(code_index)}, name_index大小={len(name_index)}", "info")
        
        processed_count = 0
        total_rows = len(match_df)  # 确保total_rows已定义
        self._log(f"[验证引擎] [阶段3] 开始遍历match_df，总行数={total_rows}", "info")
        for idx, row in match_df.iterrows():
            processed_count += 1
            # 每处理20条数据更新一次进度，并让出控制权（更频繁的更新，避免卡死）
            if processed_count % 20 == 0:
                elapsed = time.time() - stage3_start
                self._log(f"[验证引擎] [阶段3] 进度: {processed_count}/{total_rows} ({processed_count*100//total_rows if total_rows>0 else 0}%), 已耗时={elapsed:.2f}秒", "info")
                progress = 98 + int((processed_count / total_rows) * 1) if total_rows > 0 else 98  # 98-99%用于重复数据
                self._progress(progress, 100, f"汇总问题数据... ({processed_count}/{total_rows})")
                # 让出控制权，避免UI卡死（在后台线程中）
                from qgis.PyQt.QtCore import QThread
                QThread.msleep(20)  # 增加等待时间，确保UI有时间响应
            # 1. 优先用GID匹配
            # 注意：优先使用gid字段（通常是数字），其次使用code字段（可能带前缀）
            target_code = None
            # 先查找gid字段（优先）
            for col in match_df.columns:
                if '[目标:' in col and 'gid' in col.lower() and 'code' not in col.lower():
                    gid_val = str(row.get(col, '') or '').strip()
                    if gid_val:
                        target_code = gid_val.lower()
                        break
            # 如果gid字段没有值，再查找code字段
            if not target_code:
                for col in match_df.columns:
                    if '[目标:' in col and 'code' in col.lower():
                        code_val = str(row.get(col, '') or '').strip()
                        if code_val:
                            target_code = code_val.lower()
                            break
            
            if target_code and target_code in code_index:
                if len(code_index[target_code]) > 1:
                    # 获取匹配到的数据库code（使用第一个匹配的数据的code）
                    db_code_val = code_index[target_code][0].get('code', '').strip() if code_index[target_code] else ''
                    duplicate_data.append({
                        "index": idx,
                        "row": row.to_dict(),
                        "match_value": f"code:{target_code}",  # 保持原有格式用于匹配
                        "duplicate_count": len(code_index[target_code]),
                        "db_code": db_code_val  # 记录匹配到的数据库code
                    })
                continue
            
            # 2. 如果GID匹配不到，用配置的多个字段分别匹配数据库的name字段
            if source_fields:
                for field in source_fields:
                    val = str(row.get(field, '') or '').strip()
                    if val and val.lower() in name_index:
                        if len(name_index[val.lower()]) > 1:
                            # 获取匹配到的数据库code（使用第一个匹配的数据的code）
                            db_code_val = name_index[val.lower()][0].get('code', '').strip() if name_index[val.lower()] else ''
                            duplicate_data.append({
                                "index": idx,
                                "row": row.to_dict(),
                                "match_value": f"name:{val.lower()}",  # 保持原有格式用于匹配
                                "duplicate_count": len(name_index[val.lower()]),
                                "db_code": db_code_val  # 记录匹配到的数据库code
                            })
                        break
        
        # 输出GID查找失败的调试信息
        if gid_failed_samples:
            self._log(f"[验证引擎] 位置偏差检查：有{len(gid_failed_samples)}个失败示例，前{len(gid_failed_samples)}个失败示例：", "warning")
            for i, sample in enumerate(gid_failed_samples, 1):
                self._log(f"[验证引擎]   失败#{i}: GID={sample.get('gid', 'N/A')}, 字段={sample.get('field', 'N/A')}, SHP索引大小={sample.get('shp_index_size', 0)}, 索引示例GID={sample.get('sample_gids', [])}", "warning")
        
        # 添加日志输出问题数据统计
        stage3_time = time.time() - stage3_start
        self._log(f"[验证引擎] [阶段3] 重复数据处理完成: 找到{len(duplicate_data)}条重复数据, 总耗时={stage3_time:.2f}秒", "info")
        
        total_time = time.time() - start_time
        self._log(f"[验证引擎] ========== 汇总问题数据完成 ==========", "info")
        self._log(f"[验证引擎] 问题数据汇总: 缺失={len(missing_data)}, 偏差={len(deviation_data)}, 重复={len(duplicate_data)}", "info")
        self._log(f"[验证引擎] 总耗时={total_time:.2f}秒 (阶段1={stage1_time:.2f}秒, 阶段2={stage2_time:.2f}秒, 阶段3={stage3_time:.2f}秒)", "info")
        
        return {
            "missing": missing_data,
            "deviation": deviation_data,
            "duplicate": duplicate_data
        }
    
    def _error_result(self, error_msg: str) -> Dict:
        """返回错误结果"""
        return {
            "success": False,
            "error": error_msg,
            "statistics": {},
            "problem_data": {}
        }
