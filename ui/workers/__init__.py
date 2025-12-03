# -*- coding: utf-8 -*-
"""
UI Workers - 后台任务线程

使用 QgsTask 方案（QGIS 官方推荐）
- 与 QGIS 状态栏集成，显示进度
- 用户可在 QGIS 界面看到所有任务
- 支持取消、暂停等操作

覆盖所有耗时任务：
- Step2: CleanQgsTask (数据清洗)
- Step3: ParseQgsTask (地址解析), RelationAnalyzeTask (关联分析)
- Step4: MatchQgsTask (匹配执行)
- Step5: ExportQgsTask (结果导出)
"""

# QgsTask 方案（QGIS 官方推荐）
from .qgis_task import (
    TaskSignals,
    BaseQgsTask,
    run_qgis_task,
    # Step2
    CleanQgsTask,
    # Step3
    ParseQgsTask,
    RelationAnalyzeTask,
    # Step4
    MatchQgsTask,
    # Step5
    ExportQgsTask,
)

# QThread 方案（主要使用）
from .base_worker import BaseWorker
from .clean_worker import CleanWorker
from .parse_worker import ParseWorker
from .relation_worker import RelationWorker
from .match_worker import MatchWorker
from .export_worker import ExportWorker
from .relation_export_worker import RelationExportWorker

__all__ = [
    # 通用
    'TaskSignals',
    'BaseQgsTask',
    'run_qgis_task',
    
    # QgsTask 任务（备选）
    'CleanQgsTask',
    'ParseQgsTask',
    'RelationAnalyzeTask',
    'MatchQgsTask',
    'ExportQgsTask',
    
    # QThread Worker（主要使用）
    'BaseWorker',
    'CleanWorker', 
    'ParseWorker',
    'RelationWorker',
    'MatchWorker',
    'ExportWorker',
    'RelationExportWorker',
]

