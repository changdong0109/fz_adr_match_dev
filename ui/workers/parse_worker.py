# -*- coding: utf-8 -*-
"""
地址解析后台 Worker

使用 QThread 实现，确保：
1. UI 不卡死
2. 进度实时更新
3. 支持取消操作
"""
import os
from qgis.PyQt.QtCore import QThread, pyqtSignal
from typing import List, Optional


class ParseWorker(QThread):
    """地址解析后台线程"""
    
    # 信号定义
    progress = pyqtSignal(int, int, str)  # current, total, message
    log = pyqtSignal(str, str)  # message, level
    file_completed = pyqtSignal(str, dict)  # file_name, result
    finished = pyqtSignal(dict)  # summary
    error = pyqtSignal(str)  # error message
    
    def __init__(self, files: List[str], parser, test_limit: int = None, parent=None):
        super().__init__(parent)
        self.files = files
        self.parser = parser
        self.test_limit = test_limit
        self._cancelled = False
        self._region_lookup = None  # 延迟初始化
    
    def cancel(self):
        """取消任务"""
        self._cancelled = True
    
    def _get_region_lookup(self):
        """延迟加载 RegionLookup"""
        if self._region_lookup is None:
            try:
                from ...core.region_lookup import RegionLookup
                self._region_lookup = RegionLookup()
                self.log.emit("[解析任务] 已加载地址补全器", "debug")
            except Exception as e:
                self.log.emit(f"[解析任务] 加载地址补全器失败: {e}", "warning")
        return self._region_lookup
    
    def _complete_region(self, address: str, province: str, city: str, 
                         district: str, street: str) -> Optional[dict]:
        """使用内置行政区划数据补全缺失的省市区县"""
        lookup = self._get_region_lookup()
        if not lookup:
            return None
        
        try:
            result = lookup.complete_address(
                address, 
                known_province=province,
                known_city=city,
                known_area=district,
                known_street=street
            )
            return result
        except Exception:
            return None
    
    def run(self):
        """执行解析任务"""
        import pandas as pd
        
        total_files = len(self.files)
        success_count = 0
        fail_count = 0
        total_rows = 0
        total_cached = 0
        
        self.log.emit(f"[解析任务] 开始处理 {total_files} 个文件", "info")
        
        for file_idx, file_path in enumerate(self.files):
            if self._cancelled:
                self.log.emit("[解析任务] 任务已取消", "warning")
                self.finished.emit({'cancelled': True})
                return
            
            file_name = os.path.basename(file_path)
            self.progress.emit(file_idx, total_files, f"解析 ({file_idx+1}/{total_files}): {file_name}")
            self.log.emit(f"[解析任务] 处理文件: {file_name}", "info")
            
            try:
                # 读取文件
                df = pd.read_csv(file_path, encoding='utf-8-sig')
                
                # 查找地址列
                adr_cols = [c for c in df.columns if c.endswith('_adr_clean')]
                if not adr_cols:
                    fail_count += 1
                    self.log.emit(f"[解析任务] {file_name} 未找到清洗后的地址列", "warning")
                    self.file_completed.emit(file_name, {'success': False, 'error': '未找到地址列'})
                    continue
                
                adr_col = adr_cols[0]
                
                # 测试模式限制行数
                if self.test_limit and len(df) > self.test_limit:
                    df = df.head(self.test_limit)
                    self.log.emit(f"[解析任务] 测试模式: 只处理前 {self.test_limit} 条", "info")
                
                file_rows = len(df)
                file_cached = 0
                
                # 添加输出列
                output_cols = [
                    '标准化地址', '标准化POI抽取', 'POI来源', '省', '市', '区县',
                    '街道镇', '村社区', '道路', '门牌号', 'POI_结构化', '楼号', '单元号', '房间号'
                ]
                for col in output_cols:
                    if col not in df.columns:
                        df[col] = ""
                
                # 计算输出路径（用于分批保存）
                output_path = file_path.replace('_清洗.csv', '_标准化.csv')
                BATCH_SAVE_INTERVAL = 500  # 每 500 行保存一次
                
                # 逐行解析
                for idx, row in df.iterrows():
                    if self._cancelled:
                        # 取消前保存已处理的数据
                        df.to_csv(output_path, index=False, encoding='utf-8-sig')
                        self.log.emit(f"[解析任务] 已保存 {idx} 条已处理数据", "info")
                        self.finished.emit({'cancelled': True})
                        return
                    
                    # 每10行更新一次进度（计算总体百分比）
                    if idx % 10 == 0:
                        # 计算总进度：已完成文件 + 当前文件内进度
                        overall_percent = int((file_idx / total_files + (idx / file_rows) / total_files) * 100)
                        self.progress.emit(
                            overall_percent, 100,
                            f"解析 {file_name}: {idx+1}/{file_rows}"
                        )
                    
                    address = str(row.get(adr_col, "")).strip()
                    if not address:
                        continue
                    
                    # 断点续传：如果已有标准化结果，跳过
                    existing_std = str(df.at[idx, '标准化地址']).strip() if '标准化地址' in df.columns else ""
                    if existing_std and existing_std != 'nan':
                        file_cached += 1  # 视为缓存命中
                        continue
                    
                    # 调用解析器
                    result = self.parser.parse(address)
                    
                    # 获取解析结果
                    province = result.get('province', '')
                    city = result.get('city', '')
                    district = result.get('district', '')
                    street = result.get('street', '')
                    
                    # 如果省市区县缺失，使用 RegionLookup 补全
                    if not province or not city or not district:
                        completed = self._complete_region(
                            address, province, city, district, street
                        )
                        if completed:
                            province = completed.get('province', '') or province
                            city = completed.get('city', '') or city
                            district = completed.get('area', '') or district
                            street = completed.get('street', '') or street
                    
                    # 更新 DataFrame
                    df.at[idx, '标准化地址'] = result.get('std_address', '')
                    df.at[idx, '标准化POI抽取'] = result.get('predict_poi', '')
                    df.at[idx, 'POI来源'] = result.get('predict_poi_source', '')
                    df.at[idx, '省'] = province
                    df.at[idx, '市'] = city
                    df.at[idx, '区县'] = district
                    df.at[idx, '街道镇'] = street
                    df.at[idx, '村社区'] = result.get('village', '')
                    df.at[idx, '道路'] = result.get('road', '')
                    df.at[idx, '门牌号'] = result.get('road_no', '')
                    df.at[idx, 'POI_结构化'] = result.get('poi', '')
                    df.at[idx, '楼号'] = result.get('building_no', '')
                    df.at[idx, '单元号'] = result.get('unit_no', '')
                    df.at[idx, '房间号'] = result.get('room_no', '')
                    
                    # 统计缓存命中
                    if result.get('structure_cached') or result.get('poi_cached'):
                        file_cached += 1
                    
                    # 每 500 行分批保存，防止崩溃丢失数据
                    if (idx + 1) % BATCH_SAVE_INTERVAL == 0:
                        df.to_csv(output_path, index=False, encoding='utf-8-sig')
                        self.log.emit(f"[解析任务] {file_name} 已保存 {idx+1}/{file_rows} 条", "info")
                
                # 最终保存
                df.to_csv(output_path, index=False, encoding='utf-8-sig')
                
                success_count += 1
                total_rows += file_rows
                total_cached += file_cached
                
                self.log.emit(
                    f"[解析任务] {file_name} 完成: {file_rows}条, 缓存命中{file_cached}条",
                    "info"
                )
                self.file_completed.emit(file_name, {
                    'success': True,
                    'rows': file_rows,
                    'cached': file_cached,
                    'output_path': output_path
                })
                
            except Exception as e:
                fail_count += 1
                self.log.emit(f"[解析任务] {file_name} 失败: {e}", "error")
                self.file_completed.emit(file_name, {'success': False, 'error': str(e)})
        
        # 保存缓存
        try:
            self.parser.save_cache()
            self.log.emit("[解析任务] 缓存已保存", "info")
        except Exception as e:
            self.log.emit(f"[解析任务] 保存缓存失败: {e}", "warning")
        
        self.progress.emit(100, 100, f"解析完成: 成功{success_count}个")
        self.log.emit(
            f"[解析任务] 全部完成: 成功{success_count}个，失败{fail_count}个，"
            f"处理{total_rows}行，缓存命中{total_cached}次",
            "info"
        )
        
        self.finished.emit({
            'success_count': success_count,
            'fail_count': fail_count,
            'total_rows': total_rows,
            'total_cached': total_cached
        })
