# -*- coding: utf-8 -*-
"""
QGIS 官方任务系统封装

统一处理所有耗时任务，确保：
1. UI 永不卡死
2. 进度实时更新
3. 详细日志输出
4. 支持取消操作

覆盖任务：
- Step2: CleanQgsTask (数据清洗)
- Step3: ParseQgsTask (地址解析), RelationAnalyzeTask (关联分析)
- Step4: MatchQgsTask (匹配执行)
- Step5: ExportQgsTask (结果导出)
"""
from qgis.core import QgsTask, QgsApplication, QgsMessageLog, Qgis
from qgis.PyQt.QtCore import pyqtSignal, QObject
from typing import Callable, Optional, Any, Dict, List
import traceback
import os


class TaskSignals(QObject):
    """
    任务信号类 - 用于后台线程与主线程通信
    """
    progress_updated = pyqtSignal(int, str)  # percent, message
    log_message = pyqtSignal(str, str)  # message, level
    task_completed = pyqtSignal(dict)  # result
    task_failed = pyqtSignal(str)  # error message
    file_completed = pyqtSignal(str, dict)  # file_name, result (单文件完成)


class BaseQgsTask(QgsTask):
    """QGIS 后台任务基类"""
    
    def __init__(self, description: str, signals: TaskSignals = None):
        super().__init__(description, QgsTask.CanCancel)
        self.signals = signals or TaskSignals()
        self._result = {}
    
    def run(self) -> bool:
        try:
            self._result = self.do_work() or {}
            return not self._result.get('cancelled', False)
        except Exception as e:
            error_msg = f"{str(e)}\n{traceback.format_exc()}"
            self.signals.task_failed.emit(error_msg)
            QgsMessageLog.logMessage(f"任务失败: {error_msg}", "地址匹配", Qgis.Critical)
            return False
    
    def finished(self, result: bool):
        if result:
            self.signals.task_completed.emit(self._result)
        elif self.isCanceled():
            self.signals.task_completed.emit({'cancelled': True})
    
    def do_work(self) -> dict:
        raise NotImplementedError("子类必须实现 do_work 方法")
    
    def update_progress(self, percent: int, message: str = ""):
        self.setProgress(percent)
        if message:
            self.signals.progress_updated.emit(percent, message)
    
    def log(self, message: str, level: str = "info"):
        self.signals.log_message.emit(message, level)
        qgis_level = {"info": Qgis.Info, "warning": Qgis.Warning, 
                     "error": Qgis.Critical, "success": Qgis.Success}.get(level, Qgis.Info)
        QgsMessageLog.logMessage(message, "地址匹配", qgis_level)


def run_qgis_task(task: BaseQgsTask):
    """运行 QGIS 任务"""
    QgsApplication.taskManager().addTask(task)


# ==================== Step2: 清洗任务 ====================

class CleanQgsTask(BaseQgsTask):
    """数据清洗任务"""
    
    def __init__(self, files: list, cleaner, output_dir: str,
                 province: str, city: str, county: str, signals: TaskSignals = None):
        super().__init__("数据清洗", signals)
        self.files = files
        self.cleaner = cleaner
        self.output_dir = output_dir
        self.province = province
        self.city = city
        self.county = county
    
    def do_work(self) -> dict:
        total = len(self.files)
        success_count = fail_count = total_valid = total_invalid = 0
        
        self.log(f"[清洗任务] 开始处理 {total} 个文件", "info")
        
        for idx, file_info in enumerate(self.files):
            if self.isCanceled():
                self.log("[清洗任务] 任务已取消", "warning")
                return {'cancelled': True}
            
            file_name = file_info['file_name']
            percent = int((idx / total) * 100)
            self.update_progress(percent, f"清洗 ({idx+1}/{total}): {file_name}")
            self.log(f"[清洗任务] 处理文件: {file_name}", "info")
            
            try:
                result = self.cleaner.clean_file(
                    file_path=file_info['file_path'],
                    field_config=file_info['field_config'],
                    output_dir=self.output_dir,
                    province=self.province,
                    city=self.city,
                    county=self.county,
                    source_type=file_info.get('source_type', '其他')
                )
                
                if result.get('success'):
                    success_count += 1
                    total_valid += result.get('valid_count', 0)
                    total_invalid += result.get('invalid_count', 0)
                    self.log(f"[清洗任务] {file_name} 完成: 有效{result.get('valid_count', 0)}条", "info")
                    self.signals.file_completed.emit(file_name, result)
                else:
                    fail_count += 1
                    self.log(f"[清洗任务] {file_name} 失败: {result.get('error', '未知错误')}", "error")
            except Exception as e:
                fail_count += 1
                self.log(f"[清洗任务] {file_name} 异常: {e}", "error")
        
        self.update_progress(100, f"清洗完成: 成功{success_count}个")
        self.log(f"[清洗任务] 全部完成: 成功{success_count}个，失败{fail_count}个", "info")
        
        return {'success': True, 'success_count': success_count, 'fail_count': fail_count,
                'total_valid': total_valid, 'total_invalid': total_invalid}


# ==================== Step3: 解析任务 ====================

class ParseQgsTask(BaseQgsTask):
    """地址解析任务"""
    
    def __init__(self, files: list, parser, test_limit: int = None, signals: TaskSignals = None):
        super().__init__("地址解析", signals)
        self.files = files
        self.parser = parser
        self.test_limit = test_limit
    
    def do_work(self) -> dict:
        import pandas as pd
        
        total = len(self.files)
        success_count = fail_count = total_rows = total_cached = 0
        
        self.log(f"[解析任务] 开始处理 {total} 个文件", "info")
        
        for file_idx, file_path in enumerate(self.files):
            if self.isCanceled():
                self.log("[解析任务] 任务已取消", "warning")
                return {'cancelled': True}
            
            file_name = os.path.basename(file_path)
            percent = int((file_idx / total) * 100)
            self.update_progress(percent, f"解析 ({file_idx+1}/{total}): {file_name}")
            self.log(f"[解析任务] 处理文件: {file_name}", "info")
            
            try:
                df = pd.read_csv(file_path, encoding='utf-8-sig')
                adr_cols = [c for c in df.columns if c.endswith('_adr_clean')]
                if not adr_cols:
                    fail_count += 1
                    self.log(f"[解析任务] {file_name} 未找到地址列", "warning")
                    continue
                
                adr_col = adr_cols[0]
                if self.test_limit and len(df) > self.test_limit:
                    df = df.head(self.test_limit)
                
                file_rows = len(df)
                file_cached = 0
                
                # 添加输出列
                for col in ['标准化地址', '标准化POI抽取', 'POI来源', '省', '市', '区县',
                           '街道镇', '村社区', '道路', '门牌号', 'POI_结构化', '楼号', '单元号', '房间号']:
                    if col not in df.columns:
                        df[col] = ""
                
                # 逐行解析（带进度更新）
                for idx, row in df.iterrows():
                    if self.isCanceled():
                        return {'cancelled': True}
                    
                    # 每10行更新一次进度
                    if idx % 10 == 0:
                        inner_percent = int((file_idx / total + (idx / file_rows) / total) * 100)
                        self.update_progress(inner_percent, f"解析 {file_name}: {idx+1}/{file_rows}")
                    
                    address = str(row.get(adr_col, "")).strip()
                    if not address:
                        continue
                    
                    result = self.parser.parse(address)
                    
                    df.at[idx, '标准化地址'] = result.get('std_address', '')
                    df.at[idx, '标准化POI抽取'] = result.get('predict_poi', '')
                    df.at[idx, 'POI来源'] = result.get('predict_poi_source', '')
                    df.at[idx, '省'] = result.get('province', '')
                    df.at[idx, '市'] = result.get('city', '')
                    df.at[idx, '区县'] = result.get('district', '')
                    df.at[idx, '街道镇'] = result.get('street', '')
                    df.at[idx, '村社区'] = result.get('village', '')
                    df.at[idx, '道路'] = result.get('road', '')
                    df.at[idx, '门牌号'] = result.get('road_no', '')
                    df.at[idx, 'POI_结构化'] = result.get('poi', '')
                    df.at[idx, '楼号'] = result.get('building_no', '')
                    df.at[idx, '单元号'] = result.get('unit_no', '')
                    df.at[idx, '房间号'] = result.get('room_no', '')
                    
                    if result.get('structure_cached') or result.get('poi_cached'):
                        file_cached += 1
                
                # 保存
                output_path = file_path.replace('_清洗.csv', '_标准化.csv')
                df.to_csv(output_path, index=False, encoding='utf-8-sig')
                
                success_count += 1
                total_rows += file_rows
                total_cached += file_cached
                
                self.log(f"[解析任务] {file_name} 完成: {file_rows}条, 缓存{file_cached}条", "info")
                self.signals.file_completed.emit(file_name, {
                    'success': True, 'rows': file_rows, 'cached': file_cached
                })
                
            except Exception as e:
                fail_count += 1
                self.log(f"[解析任务] {file_name} 失败: {e}", "error")
        
        try:
            self.parser.save_cache()
            self.log("[解析任务] 缓存已保存", "info")
        except:
            pass
        
        self.update_progress(100, f"解析完成: 成功{success_count}个")
        self.log(f"[解析任务] 全部完成: 成功{success_count}个，失败{fail_count}个", "info")
        
        return {'success': True, 'success_count': success_count, 'fail_count': fail_count,
                'total_rows': total_rows, 'total_cached': total_cached}


# ==================== Step3: 关联分析任务 ====================

class RelationAnalyzeTask(BaseQgsTask):
    """字段关联分析任务"""
    
    def __init__(self, files: list, sample_size: int = 1000, signals: TaskSignals = None):
        super().__init__("关联分析", signals)
        self.files = files
        self.sample_size = sample_size
    
    def do_work(self) -> dict:
        import pandas as pd
        
        total_files = len(self.files)
        if total_files == 0:
            return {'success': False, 'error': '没有可分析的文件'}
        
        self.log(f"[关联分析] 开始分析 {total_files} 个文件", "info")
        
        # 1. 加载数据
        self.update_progress(0, "加载数据...")
        file_data = {}
        
        for i, file_path in enumerate(self.files):
            if self.isCanceled():
                return {'cancelled': True}
            
            file_name = os.path.basename(file_path)
            percent = int((i / total_files) * 30)
            self.update_progress(percent, f"加载 ({i+1}/{total_files}): {file_name}")
            
            try:
                df = self._read_file(file_path)
                if df is not None and not df.empty:
                    if len(df) > self.sample_size:
                        df = df.sample(n=self.sample_size, random_state=42)
                    file_data[file_name] = df
                    self.log(f"[关联分析] 加载 {file_name}: {len(df)}行", "info")
            except Exception as e:
                self.log(f"[关联分析] 加载 {file_name} 失败: {e}", "warning")
        
        if not file_data:
            return {'success': False, 'error': '没有有效数据'}
        
        # 2. 提取字段值
        self.update_progress(30, "提取字段值...")
        field_values = {}
        
        for file_name, df in file_data.items():
            if self.isCanceled():
                return {'cancelled': True}
            
            for col in df.columns:
                if col.startswith('_'):
                    continue
                
                key = f"{file_name}.{col}"
                values = df[col].dropna().astype(str).tolist()
                values = [v for v in values if v.strip() and not v.replace('.', '').isdigit()]
                if values:
                    field_values[key] = set(values[:500])
        
        self.log(f"[关联分析] 提取到 {len(field_values)} 个字段", "info")
        
        # 3. 计算关联
        self.update_progress(50, "计算关联关系...")
        relations = []
        field_keys = list(field_values.keys())
        total_pairs = len(field_keys) * (len(field_keys) - 1) // 2
        checked = 0
        
        for i, key1 in enumerate(field_keys):
            if self.isCanceled():
                return {'cancelled': True}
            
            for key2 in field_keys[i + 1:]:
                checked += 1
                if checked % 200 == 0:
                    progress = 50 + int(checked / max(total_pairs, 1) * 40)
                    self.update_progress(progress, f"分析关联... {checked}/{total_pairs}")
                
                set1 = field_values[key1]
                set2 = field_values[key2]
                
                if not set1 or not set2:
                    continue
                
                intersection = set1 & set2
                if len(intersection) < 3:
                    continue
                
                union = set1 | set2
                jaccard = len(intersection) / len(union) if union else 0
                
                if jaccard >= 0.1:
                    file1, field1 = key1.rsplit('.', 1)
                    file2, field2 = key2.rsplit('.', 1)
                    relations.append({
                        'file1': file1, 'field1': field1,
                        'file2': file2, 'field2': field2,
                        'overlap': len(intersection),
                        'jaccard': round(jaccard, 3),
                        'sample_values': list(intersection)[:5]
                    })
        
        relations.sort(key=lambda x: x['jaccard'], reverse=True)
        
        self.update_progress(100, f"分析完成: {len(relations)}对关联")
        self.log(f"[关联分析] 完成: 发现 {len(relations)} 对关联字段", "info")
        
        return {'success': True, 'relations': relations,
                'total_fields': len(field_values), 'total_relations': len(relations)}
    
    def _read_file(self, file_path: str):
        import pandas as pd
        try:
            if file_path.lower().endswith('.csv'):
                for enc in ['utf-8', 'gbk', 'utf-8-sig']:
                    try:
                        return pd.read_csv(file_path, encoding=enc)
                    except:
                        continue
            elif file_path.lower().endswith(('.xlsx', '.xls')):
                return pd.read_excel(file_path)
        except:
            pass
        return None


# ==================== Step4: 匹配任务 ====================

class MatchQgsTask(BaseQgsTask):
    """匹配执行任务"""
    
    def __init__(self, executor, task_groups: list, signals: TaskSignals = None):
        super().__init__("地址匹配", signals)
        self.executor = executor
        self.task_groups = task_groups
    
    def do_work(self) -> dict:
        total = len(self.task_groups)
        results = []
        success_count = fail_count = 0
        total_matched = total_unmatched = 0
        
        self.log(f"[匹配任务] 开始处理 {total} 个任务组", "info")
        
        for idx, group in enumerate(self.task_groups):
            if self.isCanceled():
                self.log("[匹配任务] 任务已取消", "warning")
                return {'cancelled': True}
            
            group_name = group.get('name', f'任务组{idx + 1}')
            percent = int((idx / total) * 100)
            self.update_progress(percent, f"匹配 ({idx+1}/{total}): {group_name}")
            self.log(f"[匹配任务] 处理: {group_name}", "info")
            
            try:
                result = self.executor.execute_task_group(group)
                results.append(result)
                
                if result.get('success'):
                    success_count += 1
                    total_matched += result.get('total_matched', 0)
                    total_unmatched += result.get('total_unmatched', 0)
                    self.log(f"[匹配任务] {group_name} 完成: 匹配{result.get('total_matched', 0)}条", "info")
                    self.signals.file_completed.emit(group_name, result)
                else:
                    fail_count += 1
                    self.log(f"[匹配任务] {group_name} 失败", "error")
                    
            except Exception as e:
                fail_count += 1
                self.log(f"[匹配任务] {group_name} 异常: {e}", "error")
        
        self.update_progress(100, f"匹配完成: 成功{success_count}个")
        self.log(f"[匹配任务] 全部完成: 成功{success_count}个，匹配{total_matched}条", "info")
        
        return {'success': True, 'results': results, 'success_count': success_count,
                'fail_count': fail_count, 'total_matched': total_matched, 'total_unmatched': total_unmatched}


# ==================== Step5: 导出任务 ====================

class ExportQgsTask(BaseQgsTask):
    """结果导出任务"""
    
    def __init__(self, export_config: dict, signals: TaskSignals = None):
        super().__init__("导出结果", signals)
        self.export_config = export_config
    
    def do_work(self) -> dict:
        import pandas as pd
        
        files = self.export_config.get('files', [])
        output_dir = self.export_config.get('output_dir', '')
        output_format = self.export_config.get('format', 'xlsx')
        
        total = len(files)
        success_count = fail_count = 0
        output_files = []
        
        self.log(f"[导出任务] 开始导出 {total} 个文件", "info")
        
        os.makedirs(output_dir, exist_ok=True)
        
        for idx, file_info in enumerate(files):
            if self.isCanceled():
                self.log("[导出任务] 任务已取消", "warning")
                return {'cancelled': True}
            
            file_path = file_info.get('path', '')
            file_name = os.path.basename(file_path)
            percent = int((idx / total) * 100)
            self.update_progress(percent, f"导出 ({idx+1}/{total}): {file_name}")
            
            try:
                # 读取文件
                if file_path.lower().endswith('.csv'):
                    df = pd.read_csv(file_path, encoding='utf-8-sig')
                else:
                    df = pd.read_excel(file_path)
                
                # 生成输出路径
                base_name = os.path.splitext(file_name)[0]
                if output_format == 'xlsx':
                    output_file = os.path.join(output_dir, f"{base_name}.xlsx")
                    df.to_excel(output_file, index=False, engine='openpyxl')
                else:
                    output_file = os.path.join(output_dir, f"{base_name}.csv")
                    df.to_csv(output_file, index=False, encoding='utf-8-sig')
                
                output_files.append(output_file)
                success_count += 1
                self.log(f"[导出任务] {file_name} 导出成功", "info")
                self.signals.file_completed.emit(file_name, {'success': True, 'output': output_file})
                
            except Exception as e:
                fail_count += 1
                self.log(f"[导出任务] {file_name} 导出失败: {e}", "error")
        
        self.update_progress(100, f"导出完成: 成功{success_count}个")
        self.log(f"[导出任务] 全部完成: 成功{success_count}个，失败{fail_count}个", "info")
        
        return {'success': True, 'success_count': success_count, 'fail_count': fail_count,
                'output_files': output_files}
