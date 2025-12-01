"""
字段关联关系分析器
使用 pandas + NetworkX 分析多源数据的字段值关联关系

职责：
- 读取多个清洗后的 CSV 文件
- 计算跨文件字段间的值重叠
- 构建 NetworkX 关系图
- 运行图算法（社区发现、中心性等）
- 生成洞察报告
"""

import os
from typing import Dict, List, Tuple, Set, Any, Optional, Callable
from collections import defaultdict


class FieldRelationAnalyzer:
    """字段关联关系分析器"""
    
    def __init__(self, log_callback: Optional[Callable[[str, str], None]] = None,
                 progress_callback: Optional[Callable[[float, str], None]] = None):
        """
        初始化分析器
        
        Args:
            log_callback: 日志回调函数 (message, level)
            progress_callback: 进度回调函数 (percent 0-100, message)
        """
        self._log_callback = log_callback
        self._progress_callback = progress_callback
        self._graph = None
        self._field_values: Dict[str, Set] = {}  # "文件.字段" -> 值集合
        self._field_info: Dict[str, Dict] = {}   # "文件.字段" -> {file, field, count, ...}
        self._communities: List[Set[str]] = []
        self._centrality: Dict[str, float] = {}
        self._insights: List[Dict[str, Any]] = []
        self._files_loaded = 0
    
    def _log(self, message: str, level: str = "info"):
        """记录日志"""
        if self._log_callback:
            self._log_callback(message, level)
    
    def _progress(self, percent: float, message: str):
        """更新进度"""
        if self._progress_callback:
            self._progress_callback(percent, message)
    
    def load_files(self, file_paths: List[str]) -> int:
        """
        加载多个清洗后的 CSV 文件
        
        Args:
            file_paths: CSV 文件路径列表
            
        Returns:
            成功加载的文件数量
        """
        import pandas as pd
        
        self._field_values.clear()
        self._field_info.clear()
        self._files_loaded = 0
        total_files = len(file_paths)
        
        for idx, file_path in enumerate(file_paths):
            # 更新进度
            percent = (idx / total_files) * 50  # 加载占 0-50%
            self._progress(percent, f"加载文件 {idx+1}/{total_files}...")
            if not os.path.exists(file_path):
                self._log(f"[关联分析] 文件不存在: {file_path}", "warning")
                continue
            
            file_name = os.path.basename(file_path)
            
            try:
                # 根据文件类型读取
                file_lower = file_path.lower()
                if file_lower.endswith('.xlsx') or file_lower.endswith('.xls'):
                    # Excel 文件
                    df = pd.read_excel(file_path)
                else:
                    # CSV 文件
                    try:
                        df = pd.read_csv(file_path, encoding='utf-8')
                    except UnicodeDecodeError:
                        df = pd.read_csv(file_path, encoding='gbk')
                
                # 提取每个字段的值集合
                for col in df.columns:
                    # 跳过可能的索引列或无意义列
                    if col.lower() in ['unnamed: 0', 'index', '']:
                        continue
                    
                    field_key = f"{file_name}.{col}"
                    
                    # 获取非空唯一值
                    values = df[col].dropna().astype(str).unique()
                    value_set = set(values)
                    
                    # 过滤掉空字符串和纯空白
                    value_set = {v.strip() for v in value_set if v.strip()}
                    
                    if len(value_set) > 0:
                        self._field_values[field_key] = value_set
                        self._field_info[field_key] = {
                            'file': file_name,
                            'field': col,
                            'unique_count': len(value_set),
                            'total_count': len(df[col].dropna()),
                        }
                
                self._files_loaded += 1
                self._log(f"[关联分析] 已加载: {file_name}，{len(df.columns)} 个字段", "debug")
                
            except Exception as e:
                self._log(f"[关联分析] 加载文件失败 {file_name}: {e}", "error")
        
        total_fields = len(self._field_values)
        self._log(f"[关联分析] 共加载 {self._files_loaded} 个文件，{total_fields} 个有效字段", "info")
        return self._files_loaded
    
    def build_relation_graph(self, min_overlap: int = 1, min_jaccard: float = 0.0) -> Any:
        """
        构建字段关联图
        
        Args:
            min_overlap: 最小重叠值数量（过滤噪声）
            min_jaccard: 最小 Jaccard 相似度
            
        Returns:
            NetworkX Graph 对象
        """
        try:
            import networkx as nx
        except ImportError:
            self._log("[关联分析] 需要安装 networkx: pip install networkx", "error")
            return None
        
        self._graph = nx.Graph()
        
        # 添加节点
        for field_key, info in self._field_info.items():
            self._graph.add_node(
                field_key,
                file=info['file'],
                field=info['field'],
                unique_count=info['unique_count'],
                total_count=info['total_count']
            )
        
        # 计算跨文件字段间的值重叠
        field_keys = list(self._field_values.keys())
        edge_count = 0
        total_keys = len(field_keys)
        
        for i, key_a in enumerate(field_keys):
            # 更新进度（构建图占 50-80%）
            if i % 20 == 0:  # 每20个更新一次，避免太频繁
                percent = 50 + (i / total_keys) * 30
                self._progress(percent, f"构建关联图 {i}/{total_keys}...")
            
            file_a = self._field_info[key_a]['file']
            values_a = self._field_values[key_a]
            
            for key_b in field_keys[i+1:]:
                file_b = self._field_info[key_b]['file']
                
                # 只关注跨文件的关联
                if file_a == file_b:
                    continue
                
                values_b = self._field_values[key_b]
                
                # 计算交集
                common = values_a & values_b
                overlap_count = len(common)
                
                if overlap_count < min_overlap:
                    continue
                
                # 计算 Jaccard 相似度
                union_count = len(values_a | values_b)
                jaccard = overlap_count / union_count if union_count > 0 else 0
                
                if jaccard < min_jaccard:
                    continue
                
                # 计算包含度
                containment_a = overlap_count / len(values_a) if values_a else 0
                containment_b = overlap_count / len(values_b) if values_b else 0
                
                # 添加边
                self._graph.add_edge(
                    key_a, key_b,
                    weight=jaccard,
                    overlap_count=overlap_count,
                    containment_a=containment_a,
                    containment_b=containment_b,
                    common_values=list(common)[:20]  # 最多存20个共同值
                )
                edge_count += 1
        
        self._log(f"[关联分析] 图构建完成：{len(self._graph.nodes)} 个节点，{edge_count} 条边", "info")
        return self._graph
    
    def find_communities(self) -> List[Set[str]]:
        """
        社区发现（找出哪些字段是一"簇"）
        
        Returns:
            社区列表，每个社区是一个字段集合
        """
        if self._graph is None or len(self._graph.edges) == 0:
            self._communities = []
            return self._communities
        
        try:
            import networkx as nx
            from networkx.algorithms import community
            
            # 使用 Louvain 算法发现社区
            self._communities = list(community.louvain_communities(self._graph, weight='weight'))
            self._log(f"[关联分析] 发现 {len(self._communities)} 个社区/簇", "info")
            
        except Exception as e:
            self._log(f"[关联分析] 社区发现失败: {e}", "warning")
            # 降级：使用连通分量
            import networkx as nx
            self._communities = [set(c) for c in nx.connected_components(self._graph)]
        
        return self._communities
    
    def get_centrality(self) -> Dict[str, float]:
        """
        计算节点中心性（找出"核心"字段）
        
        Returns:
            字段 -> 中心性得分
        """
        if self._graph is None:
            return {}
        
        try:
            import networkx as nx
            
            if len(self._graph.edges) > 0:
                # 使用度中心性
                self._centrality = nx.degree_centrality(self._graph)
            else:
                self._centrality = {node: 0.0 for node in self._graph.nodes}
                
        except Exception as e:
            self._log(f"[关联分析] 中心性计算失败: {e}", "warning")
            self._centrality = {}
        
        return self._centrality
    
    def get_insights(self) -> List[Dict[str, Any]]:
        """
        生成洞察报告（基于业务价值筛选）
        
        Returns:
            洞察列表，每个洞察包含 type, title, description, data
        """
        self._insights = []
        
        if self._graph is None:
            return self._insights
        
        import networkx as nx
        
        # 辅助函数：从 field_key 提取文件名
        def get_file(field_key: str) -> str:
            return field_key.split('.')[0] if '.' in field_key else field_key
        
        # 1. 跨文件字段簇（只显示包含多个不同文件的有意义簇）
        if self._communities:
            cross_file_communities = []
            for comm in self._communities:
                files_in_comm = set(get_file(f) for f in comm)
                # 只保留跨越至少2个文件的簇
                if len(files_in_comm) >= 2 and len(comm) >= 2:
                    cross_file_communities.append(list(comm))
            
            if cross_file_communities:
                # 按簇大小排序，显示最大的几个
                cross_file_communities.sort(key=lambda x: -len(x))
                self._insights.append({
                    'type': 'community',
                    'title': f'发现 {len(cross_file_communities)} 个跨文件字段簇',
                    'description': '这些字段跨越多个文件，可能是关联键',
                    'data': cross_file_communities[:5]  # 只显示前5个最大的
                })
        
        # 2. 核心字段（中心性最高，且有实际关联）
        if self._centrality:
            # 过滤：只保留有连接的节点
            connected_centrality = [(k, v) for k, v in self._centrality.items() 
                                    if v > 0 and self._graph.degree(k) >= 2]
            if connected_centrality:
                sorted_centrality = sorted(connected_centrality, key=lambda x: -x[1])
                top_central = sorted_centrality[:5]
                self._insights.append({
                    'type': 'central',
                    'title': '核心关联字段',
                    'description': '与多个其他字段有值重叠',
                    'data': top_central
                })
        
        # 3. 孤岛统计（只显示数字，不列出具体字段）
        isolated = [n for n in self._graph.nodes if self._graph.degree(n) == 0]
        total_nodes = len(self._graph.nodes)
        connected_nodes = total_nodes - len(isolated)
        if total_nodes > 0:
            self._insights.append({
                'type': 'stats',
                'title': '字段关联统计',
                'description': f'共 {total_nodes} 个字段，{connected_nodes} 个有关联，{len(isolated)} 个独立',
                'data': {'total': total_nodes, 'connected': connected_nodes, 'isolated': len(isolated)}
            })
        
        # 辅助函数：获取字段名（不含文件名）
        def get_field_name(full_name: str) -> str:
            return full_name.split('.')[-1] if '.' in full_name else full_name
        
        # 4. 高关联对（跨文件，且**字段名不同**才有洞察价值）
        high_relations = []
        diff_name_relations = []  # 不同名的高关联（更有价值）
        for u, v, data in self._graph.edges(data=True):
            # 只统计跨文件的高关联
            if get_file(u) != get_file(v) and data.get('weight', 0) > 0.6:
                overlap = data.get('overlap_count', 0)
                field_u = get_field_name(u)
                field_v = get_field_name(v)
                
                # 字段名不同才是真正有价值的发现
                if field_u.lower() != field_v.lower():
                    diff_name_relations.append((u, v, data['weight'], overlap))
                elif data.get('weight', 0) > 0.8:
                    high_relations.append((u, v, data['weight'], overlap))
        
        # 优先显示不同名的高关联（这才是真正的洞察）
        if diff_name_relations:
            diff_name_relations.sort(key=lambda x: (-x[3], -x[2]))
            display_data = [(r[0], r[1], r[2]) for r in diff_name_relations[:5]]
            self._insights.append({
                'type': 'high_relation',
                'title': f'🔥 发现 {len(diff_name_relations)} 对异名高关联字段',
                'description': '不同名但值高度重叠，可能是潜在的关联关系',
                'data': display_data
            })
        
        # 同名高关联作为补充信息
        if high_relations and not diff_name_relations:
            high_relations.sort(key=lambda x: (-x[3], -x[2]))
            display_data = [(r[0], r[1], r[2]) for r in high_relations[:3]]
            self._insights.append({
                'type': 'high_relation',
                'title': f'同名高关联字段 ({len(high_relations)} 对)',
                'description': '跨文件的同名字段值重叠（通常是相同含义的字段）',
                'data': display_data
            })
        
        # 5. 疑似外键（跨文件，不同名，包含度高）
        foreign_keys = []
        for u, v, data in self._graph.edges(data=True):
            # 只统计跨文件的
            if get_file(u) == get_file(v):
                continue
            
            overlap = data.get('overlap_count', 0)
            # 至少有10个共同值才有意义
            if overlap < 10:
                continue
            
            field_u = get_field_name(u)
            field_v = get_field_name(v)
            
            # 过滤同名字段（同名字段的包含关系没有洞察价值）
            if field_u.lower() == field_v.lower():
                continue
            
            containment_a = data.get('containment_a', 0)
            containment_b = data.get('containment_b', 0)
            
            if containment_a > 0.9:
                foreign_keys.append((u, v, overlap, containment_a))
            elif containment_b > 0.9:
                foreign_keys.append((v, u, overlap, containment_b))
        
        if foreign_keys:
            # 按共同值数排序
            foreign_keys.sort(key=lambda x: -x[2])
            display_data = [(r[0], r[1], f'{r[2]}个值') for r in foreign_keys[:5]]
            self._insights.append({
                'type': 'foreign_key',
                'title': f'🔑 发现 {len(foreign_keys)} 对疑似外键关系',
                'description': '不同名字段之间存在包含关系，可能是外键',
                'data': display_data
            })
        
        return self._insights
    
    def get_relations(self, top_n: int = None) -> List[Dict[str, Any]]:
        """
        获取关联关系列表
        
        Args:
            top_n: 返回前 N 个关联，None 表示返回全部
            
        Returns:
            关联列表，每个包含 field_a, field_b, jaccard, overlap_count, common_values
        """
        if self._graph is None:
            return []
        
        relations = []
        for u, v, data in self._graph.edges(data=True):
            relations.append({
                'field_a': u,
                'field_b': v,
                'jaccard': data.get('weight', 0),
                'overlap_count': data.get('overlap_count', 0),
                'containment_a': data.get('containment_a', 0),
                'containment_b': data.get('containment_b', 0),
                'common_values': data.get('common_values', [])
            })
        
        # 按共同值数从高到低排序（次要按 Jaccard）
        relations.sort(key=lambda x: (-x['overlap_count'], -x['jaccard']))
        return relations if top_n is None else relations[:top_n]
    
    def get_fields(self) -> List[Dict[str, Any]]:
        """
        获取字段列表
        
        Returns:
            字段列表，每个包含 field_key, file, field, unique_count
        """
        fields = []
        for field_key, info in self._field_info.items():
            fields.append({
                'field_key': field_key,
                'file': info['file'],
                'field': info['field'],
                'unique_count': info['unique_count'],
                'total_count': info['total_count']
            })
        return fields
    
    def get_graph_layout(self, layout_type: str = 'spring') -> Dict[str, Tuple[float, float]]:
        """
        获取图布局坐标（用于可视化）
        
        Args:
            layout_type: 布局类型 ('spring', 'kamada_kawai', 'circular')
            
        Returns:
            节点 -> (x, y) 坐标
        """
        if self._graph is None or len(self._graph.nodes) == 0:
            return {}
        
        import networkx as nx
        
        try:
            if layout_type == 'spring':
                pos = nx.spring_layout(self._graph, k=2, iterations=50, seed=42)
            elif layout_type == 'kamada_kawai':
                pos = nx.kamada_kawai_layout(self._graph)
            elif layout_type == 'circular':
                pos = nx.circular_layout(self._graph)
            else:
                pos = nx.spring_layout(self._graph, seed=42)
            
            # 归一化到 0-400 范围（便于 UI 渲染）
            if pos:
                min_x = min(p[0] for p in pos.values())
                max_x = max(p[0] for p in pos.values())
                min_y = min(p[1] for p in pos.values())
                max_y = max(p[1] for p in pos.values())
                
                scale_x = 350 / (max_x - min_x) if max_x != min_x else 1
                scale_y = 200 / (max_y - min_y) if max_y != min_y else 1
                
                normalized = {}
                for node, (x, y) in pos.items():
                    nx_coord = 30 + (x - min_x) * scale_x
                    ny_coord = 30 + (y - min_y) * scale_y
                    normalized[node] = (nx_coord, ny_coord)
                
                return normalized
                
        except Exception as e:
            self._log(f"[关联分析] 布局计算失败: {e}", "warning")
        
        return {}
    
    def get_node_community(self) -> Dict[str, int]:
        """
        获取每个节点所属的社区编号
        
        Returns:
            节点 -> 社区编号
        """
        node_community = {}
        for i, comm in enumerate(self._communities):
            for node in comm:
                node_community[node] = i
        return node_community
    
    def analyze(self, file_paths: List[str], min_overlap: int = 1) -> Dict[str, Any]:
        """
        一键分析（加载 + 构建图 + 社区 + 中心性 + 洞察）
        
        Args:
            file_paths: CSV 文件路径列表
            min_overlap: 最小重叠值数量
            
        Returns:
            完整分析结果
        """
        # 加载文件
        self.load_files(file_paths)
        
        if len(self._field_values) == 0:
            return {
                'success': False,
                'message': '没有找到有效字段',
                'fields': [],
                'relations': [],
                'insights': [],
                'layout': {},
                'communities': []
            }
        
        # 构建图
        self.build_relation_graph(min_overlap=min_overlap)
        
        # 社区发现
        self._progress(85, "社区发现...")
        self.find_communities()
        
        # 中心性
        self._progress(90, "计算中心性...")
        self.get_centrality()
        
        # 洞察
        self._progress(95, "生成洞察...")
        insights = self.get_insights()
        
        self._progress(100, "完成")
        return {
            'success': True,
            'message': f'分析完成：{self._files_loaded} 个文件，{len(self._field_values)} 个字段',
            'fields': self.get_fields(),
            'relations': self.get_relations(),
            'insights': insights,
            'layout': self.get_graph_layout(),
            'communities': [list(c) for c in self._communities],
            'node_community': self.get_node_community(),
            'centrality': self._centrality
        }


class RelationExporter:
    """
    关联数据导出器
    
    职责：
    - 读取两个表文件
    - 执行 INNER JOIN / LEFT ANTI JOIN / RIGHT ANTI JOIN
    - 格式化输出（Excel 带颜色区分 / CSV）
    - 保存导出元数据
    
    遵循 Core 层规范：无 UI 依赖，纯业务逻辑
    """
    
    # 导出类型常量
    JOIN_INNER = 'inner'       # 关联数据（两表都有）
    JOIN_LEFT_ONLY = 'left_only'   # A表未关联数据
    JOIN_RIGHT_ONLY = 'right_only'  # B表未关联数据
    
    def __init__(self, log_callback: Optional[Callable[[str, str], None]] = None):
        """
        初始化导出器
        
        Args:
            log_callback: 日志回调函数 (message, level)
        """
        self._log_callback = log_callback
    
    def _log(self, message: str, level: str = "info"):
        """记录日志"""
        if self._log_callback:
            self._log_callback(message, level)
    
    @staticmethod
    def read_file(path: str) -> 'pd.DataFrame':
        """
        读取 CSV/Excel 文件
        
        Args:
            path: 文件路径
            
        Returns:
            pandas DataFrame
            
        Raises:
            FileNotFoundError: 文件不存在
            ValueError: 无法读取文件
        """
        import pandas as pd
        
        if not os.path.exists(path):
            raise FileNotFoundError(f"文件不存在: {path}")
        
        try:
            if path.lower().endswith('.xlsx') or path.lower().endswith('.xls'):
                return pd.read_excel(path)
            else:
                try:
                    return pd.read_csv(path, encoding='utf-8')
                except:
                    return pd.read_csv(path, encoding='gbk')
        except Exception as e:
            raise ValueError(f"无法读取文件 {path}: {e}")
    
    def execute_join(
        self,
        df_a: 'pd.DataFrame',
        df_b: 'pd.DataFrame',
        col_a: str,
        col_b: str,
        join_type: str = 'inner'
    ) -> Tuple['pd.DataFrame', Dict[str, Any]]:
        """
        执行表关联操作
        
        Args:
            df_a: 表A的 DataFrame
            df_b: 表B的 DataFrame  
            col_a: 表A的关联字段
            col_b: 表B的关联字段
            join_type: 关联类型 ('inner', 'left_only', 'right_only')
            
        Returns:
            (结果DataFrame, 元信息字典)
            元信息包含: join_type, row_count, cols_a, cols_b, join_cols
            
        Raises:
            ValueError: 字段不存在
        """
        import pandas as pd
        
        # 验证字段存在
        if col_a not in df_a.columns:
            raise ValueError(f"字段 {col_a} 不存在于表A")
        if col_b not in df_b.columns:
            raise ValueError(f"字段 {col_b} 不存在于表B")
        
        meta = {
            'join_type': join_type,
            'original_a_count': len(df_a),
            'original_b_count': len(df_b),
            'cols_a': [],
            'cols_b': [],
            'join_cols': []
        }
        
        if join_type == self.JOIN_INNER:
            # INNER JOIN: 两表都有的数据
            result, meta = self._inner_join(df_a, df_b, col_a, col_b, meta)
        elif join_type == self.JOIN_LEFT_ONLY:
            # LEFT ANTI JOIN: A表有但B表没有的数据
            result, meta = self._left_anti_join(df_a, df_b, col_a, col_b, meta)
        else:  # right_only
            # RIGHT ANTI JOIN: B表有但A表没有的数据
            result, meta = self._right_anti_join(df_a, df_b, col_a, col_b, meta)
        
        meta['row_count'] = len(result)
        return result, meta
    
    def _inner_join(
        self, df_a: 'pd.DataFrame', df_b: 'pd.DataFrame',
        col_a: str, col_b: str, meta: Dict
    ) -> Tuple['pd.DataFrame', Dict]:
        """执行 INNER JOIN"""
        import pandas as pd
        
        cols_a_other = [c for c in df_a.columns if c != col_a]
        cols_b_other = [c for c in df_b.columns if c != col_b]
        
        # 给列加前缀以区分来源
        df_a_prefixed = df_a.copy()
        df_a_prefixed.columns = [f"[A]{c}" if c != col_a else c for c in df_a.columns]
        
        df_b_prefixed = df_b.copy()
        df_b_prefixed.columns = [f"[B]{c}" if c != col_b else c for c in df_b.columns]
        
        # 执行 INNER JOIN
        merged = pd.merge(
            df_a_prefixed, df_b_prefixed,
            left_on=col_a, right_on=col_b,
            how='inner', suffixes=('', '_dup')
        )
        
        # 重命名关联字段
        join_col_a = f"【关联A】{col_a}"
        join_col_b = f"【关联B】{col_b}"
        
        merged.rename(columns={col_a: join_col_a}, inplace=True)
        if col_b in merged.columns:
            merged.rename(columns={col_b: join_col_b}, inplace=True)
        elif f"{col_b}_dup" in merged.columns:
            merged.rename(columns={f"{col_b}_dup": join_col_b}, inplace=True)
        
        # 整理列顺序：表A列 | 关联字段 | 表B列
        cols_a_prefixed = [f"[A]{c}" for c in cols_a_other]
        cols_b_prefixed = [f"[B]{c}" for c in cols_b_other]
        join_cols = [c for c in [join_col_a, join_col_b] if c in merged.columns]
        
        final_cols = [c for c in cols_a_prefixed + join_cols + cols_b_prefixed if c in merged.columns]
        merged = merged[final_cols]
        
        meta['cols_a'] = cols_a_prefixed
        meta['cols_b'] = cols_b_prefixed
        meta['join_cols'] = join_cols
        
        return merged, meta
    
    def _left_anti_join(
        self, df_a: 'pd.DataFrame', df_b: 'pd.DataFrame',
        col_a: str, col_b: str, meta: Dict
    ) -> Tuple['pd.DataFrame', Dict]:
        """执行 LEFT ANTI JOIN（A表中没有匹配到B表的数据）"""
        b_values = set(df_b[col_b].dropna().astype(str))
        mask = ~df_a[col_a].astype(str).isin(b_values)
        result = df_a[mask].copy()
        
        # 重命名关联字段
        unmatched_col = f"【未匹配】{col_a}"
        result.rename(columns={col_a: unmatched_col}, inplace=True)
        
        meta['join_cols'] = [unmatched_col]
        return result, meta
    
    def _right_anti_join(
        self, df_a: 'pd.DataFrame', df_b: 'pd.DataFrame',
        col_a: str, col_b: str, meta: Dict
    ) -> Tuple['pd.DataFrame', Dict]:
        """执行 RIGHT ANTI JOIN（B表中没有匹配到A表的数据）"""
        a_values = set(df_a[col_a].dropna().astype(str))
        mask = ~df_b[col_b].astype(str).isin(a_values)
        result = df_b[mask].copy()
        
        # 重命名关联字段
        unmatched_col = f"【未匹配】{col_b}"
        result.rename(columns={col_b: unmatched_col}, inplace=True)
        
        meta['join_cols'] = [unmatched_col]
        return result, meta
    
    def export_to_excel_with_colors(
        self,
        df: 'pd.DataFrame',
        output_path: str,
        cols_a: List[str],
        join_cols: List[str],
        cols_b: List[str],
        file_a_name: str,
        file_b_name: str
    ) -> bool:
        """
        导出为带颜色区分的 Excel 文件
        
        Args:
            df: 要导出的 DataFrame
            output_path: 输出路径
            cols_a: 表A的列名列表
            join_cols: 关联字段列名列表
            cols_b: 表B的列名列表
            file_a_name: 表A的名称（用于图例）
            file_b_name: 表B的名称（用于图例）
            
        Returns:
            是否成功
        """
        try:
            import xlsxwriter
        except ImportError:
            self._log("xlsxwriter 未安装，使用普通 Excel 导出", "warning")
            df.to_excel(output_path, index=False)
            return True
        
        try:
            workbook = xlsxwriter.Workbook(output_path)
            worksheet = workbook.add_worksheet("关联数据")
            
            # 定义格式
            header_a = workbook.add_format({
                'bold': True, 'bg_color': '#DBEAFE', 'border': 1,
                'align': 'center', 'valign': 'vcenter'
            })
            header_join = workbook.add_format({
                'bold': True, 'bg_color': '#FEF3C7', 'border': 1,
                'align': 'center', 'valign': 'vcenter'
            })
            header_b = workbook.add_format({
                'bold': True, 'bg_color': '#D1FAE5', 'border': 1,
                'align': 'center', 'valign': 'vcenter'
            })
            cell_format = workbook.add_format({'border': 1})
            
            # 写入表头
            for col_idx, col_name in enumerate(df.columns):
                if col_name in cols_a:
                    fmt = header_a
                elif col_name in join_cols:
                    fmt = header_join
                elif col_name in cols_b:
                    fmt = header_b
                else:
                    fmt = header_join  # 默认黄色
                worksheet.write(0, col_idx, col_name, fmt)
            
            # 写入数据
            for row_idx, row in enumerate(df.values, start=1):
                for col_idx, value in enumerate(row):
                    if value is None or (isinstance(value, float) and str(value) == 'nan'):
                        worksheet.write(row_idx, col_idx, '', cell_format)
                    else:
                        worksheet.write(row_idx, col_idx, value, cell_format)
            
            # 冻结首行
            worksheet.freeze_panes(1, 0)
            
            # 自动调整列宽
            for col_idx, col_name in enumerate(df.columns):
                max_len = max(len(str(col_name)), df.iloc[:, col_idx].astype(str).str.len().max())
                worksheet.set_column(col_idx, col_idx, min(max_len + 2, 50))
            
            # 添加图例说明 sheet
            legend_sheet = workbook.add_worksheet("图例说明")
            legend_sheet.write(0, 0, "颜色说明", workbook.add_format({'bold': True, 'font_size': 14}))
            legend_sheet.write(2, 0, "🔵 蓝色", header_a)
            legend_sheet.write(2, 1, f"表A ({file_a_name}) 的字段")
            legend_sheet.write(3, 0, "🟡 黄色", header_join)
            legend_sheet.write(3, 1, "关联字段（用于匹配的字段）")
            legend_sheet.write(4, 0, "🟢 绿色", header_b)
            legend_sheet.write(4, 1, f"表B ({file_b_name}) 的字段")
            legend_sheet.set_column(0, 0, 15)
            legend_sheet.set_column(1, 1, 40)
            
            workbook.close()
            return True
            
        except Exception as e:
            self._log(f"Excel 导出失败: {e}", "error")
            # 降级为普通导出
            df.to_excel(output_path, index=False)
            return True
    
    def export(
        self,
        path_a: str,
        path_b: str,
        col_a: str,
        col_b: str,
        output_path: str,
        join_type: str = 'inner'
    ) -> Dict[str, Any]:
        """
        完整导出流程
        
        Args:
            path_a: 表A文件路径
            path_b: 表B文件路径
            col_a: 表A关联字段
            col_b: 表B关联字段
            output_path: 输出路径
            join_type: 关联类型
            
        Returns:
            {
                'success': bool,
                'message': str,
                'row_count': int,
                'output_path': str
            }
        """
        import json
        from datetime import datetime
        
        try:
            # 读取文件
            self._log(f"[导出] 读取表A: {path_a}", "debug")
            df_a = self.read_file(path_a)
            self._log(f"[导出] 读取表B: {path_b}", "debug")
            df_b = self.read_file(path_b)
            
            self._log(f"[导出] 表A: {len(df_a)} 行, 表B: {len(df_b)} 行", "info")
            
            # 执行关联
            result_df, meta = self.execute_join(df_a, df_b, col_a, col_b, join_type)
            
            if len(result_df) == 0:
                return {
                    'success': True,
                    'message': '没有匹配的数据' if join_type == 'inner' else '所有数据都已关联',
                    'row_count': 0,
                    'output_path': ''
                }
            
            # 导出文件
            file_a_name = os.path.basename(path_a).replace('.csv', '').replace('.xlsx', '')
            file_b_name = os.path.basename(path_b).replace('.csv', '').replace('.xlsx', '')
            
            if output_path.lower().endswith('.xlsx') and join_type == self.JOIN_INNER:
                self.export_to_excel_with_colors(
                    result_df, output_path,
                    meta.get('cols_a', []),
                    meta.get('join_cols', []),
                    meta.get('cols_b', []),
                    file_a_name, file_b_name
                )
            elif output_path.lower().endswith('.xlsx'):
                result_df.to_excel(output_path, index=False)
            else:
                result_df.to_csv(output_path, index=False, encoding='utf-8-sig')
            
            self._log(f"[导出] 完成: {output_path} ({len(result_df)} 行)", "success")
            
            return {
                'success': True,
                'message': self._get_result_message(join_type, len(result_df), file_a_name, file_b_name),
                'row_count': len(result_df),
                'output_path': output_path
            }
            
        except FileNotFoundError as e:
            return {'success': False, 'message': str(e), 'row_count': 0, 'output_path': ''}
        except ValueError as e:
            return {'success': False, 'message': str(e), 'row_count': 0, 'output_path': ''}
        except Exception as e:
            self._log(f"[导出] 失败: {e}", "error")
            return {'success': False, 'message': f"导出失败: {e}", 'row_count': 0, 'output_path': ''}
    
    def _get_result_message(self, join_type: str, count: int, file_a: str, file_b: str) -> str:
        """生成结果消息"""
        if join_type == self.JOIN_INNER:
            return f"已导出 {count:,} 条关联数据\n\n🔵 表A: {file_a}\n🟢 表B: {file_b}"
        elif join_type == self.JOIN_LEFT_ONLY:
            return f"已导出 {count:,} 条 {file_a} 未关联数据\n\n这些数据在 {file_b} 中没有匹配"
        else:
            return f"已导出 {count:,} 条 {file_b} 未关联数据\n\n这些数据在 {file_a} 中没有匹配"

