"""
阿里云地址解析模块
职责：封装阿里云地址解析 API 调用，提供缓存机制
"""
import time
import json
import hmac
import base64
import random
import logging
import urllib.parse
import threading
import os
from typing import Callable, Dict, Any, List, Optional

logger = logging.getLogger("ali_address")


class RateLimiter:
    """请求限速器 - 令牌桶算法
    
    优化点：
    1. 使用令牌桶算法，允许突发请求
    2. 充分利用 QPS 配额，减少不必要的等待
    """
    
    def __init__(self, qps: int, burst: int = 3):
        """
        Args:
            qps: 每秒请求数限制
            burst: 允许的突发请求数
        """
        self.qps = max(qps, 1)
        self.interval = 1.0 / self.qps
        self.burst = burst
        self.lock = threading.Lock()
        self.tokens = float(burst)  # 令牌桶
        self.last_time = time.monotonic()
    
    def acquire(self):
        """获取请求许可"""
        with self.lock:
            now = time.monotonic()
            # 补充令牌
            elapsed = now - self.last_time
            self.tokens = min(self.burst, self.tokens + elapsed * self.qps)
            self.last_time = now
            
            if self.tokens >= 1:
                # 有令牌，立即放行
                self.tokens -= 1
                return
            
            # 无令牌，计算等待时间
            wait = (1 - self.tokens) / self.qps
        
        if wait > 0:
            time.sleep(wait)
            with self.lock:
                self.tokens = 0
                self.last_time = time.monotonic()


class AliAddressParser:
    """阿里云地址解析器"""
    
    # API 配置
    VERSION = "2019-11-18"
    ENDPOINT = "https://address-purification.cn-hangzhou.aliyuncs.com/"
    SERVICE_CODE = "addrp"
    
    # 限速配置
    REQUEST_QPS = 10
    REQUEST_TIMEOUT = 5
    REQUEST_RETRIES = 2
    
    # 缓存配置
    AUTO_SAVE_INTERVAL = 50  # 每 N 条新缓存自动保存一次
    
    def __init__(
        self,
        access_key_id: str,
        access_key_secret: str,
        app_key: str,
        default_province: str = "",
        default_city: str = "",
        cache_folder: str = "",
        log_callback: Optional[Callable[[str, str], None]] = None
    ):
        """
        初始化解析器
        
        Args:
            access_key_id: 阿里云 AccessKey ID
            access_key_secret: 阿里云 AccessKey Secret
            app_key: 应用 Key
            default_province: 默认省份
            default_city: 默认城市
            cache_folder: 缓存文件夹路径
            log_callback: 日志回调函数
        """
        self.access_key_id = access_key_id
        self.access_key_secret = access_key_secret
        self.app_key = app_key
        self.default_province = default_province
        self.default_city = default_city
        self.cache_folder = cache_folder
        self.log_callback = log_callback
        
        # 内存缓存（业务层，快速访问）
        # 分别缓存两个 API 的结果，便于复用
        self._structure_cache: Dict[str, Dict[str, Any]] = {}  # StructureAddress 缓存（原始地址 -> 结构化结果）
        self._poi_cache: Dict[str, str] = {}  # PredictPOI 缓存（标准化地址 -> POI预测结果）
        self._cache_lock = threading.Lock()
        
        # 缓存脏标记（用于后台持久化）
        self._cache_dirty_count = 0
        self._save_lock = threading.Lock()
        self._saving = False
        
        # 限速器
        self._rate_limiter = RateLimiter(self.REQUEST_QPS)
        
        # 从磁盘加载缓存（后台线程，不阻塞初始化）
        if cache_folder:
            load_thread = threading.Thread(target=self._load_disk_cache, daemon=True)
            load_thread.start()
    
    def _log(self, message: str, level: str = "info"):
        """输出日志"""
        if self.log_callback:
            self.log_callback(message, level)
        if level == "error":
            logger.error(message)
        else:
            logger.info(message)
    
    def _percent_encode(self, value: str) -> str:
        """URL 编码"""
        res = urllib.parse.quote(str(value), safe='')
        return res.replace('+', '%20').replace('*', '%2A').replace('%7E', '~')
    
    def _sign_string(self, params: Dict[str, Any]) -> str:
        """生成签名"""
        sorted_params = sorted(params.items())
        canonicalized = "&".join(
            f"{self._percent_encode(k)}={self._percent_encode(v)}" for k, v in sorted_params
        )
        to_sign = f"GET&%2F&{self._percent_encode(canonicalized)}"
        h = hmac.new((self.access_key_secret + "&").encode(), to_sign.encode(), "sha1")
        return base64.b64encode(h.digest()).decode()
    
    def _call_api(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """调用阿里云 API"""
        try:
            import requests
        except ImportError:
            self._log("[API] requests 库未安装", "error")
            return {"error": "requests 库未安装"}
        
        self._rate_limiter.acquire()
        
        action = params.get("Action", "Unknown")
        text = params.get("Text", "")[:30]  # 只显示前30字符
        
        self._log(f"[API] 调用 {action}: {text}...", "debug")
        
        url = self.ENDPOINT + "?" + "&".join(
            f"{self._percent_encode(k)}={self._percent_encode(v)}" for k, v in params.items()
        )
        
        try:
            resp = requests.get(url, timeout=self.REQUEST_TIMEOUT)
            data = resp.json()
            
            # 检查是否有错误
            if "Code" in data and data["Code"] != "OK":
                self._log(f"[API] {action} 错误: {data.get('Message', data.get('Code'))}", "warning")
            else:
                self._log(f"[API] {action} 成功", "debug")
            
            return data
        except requests.exceptions.Timeout:
            self._log(f"[API] {action} 超时", "error")
            return {"error": "请求超时"}
        except requests.exceptions.ConnectionError:
            self._log(f"[API] {action} 网络错误", "error")
            return {"error": "网络连接失败"}
        except Exception as e:
            self._log(f"[API] {action} 异常: {e}", "error")
            return {"error": str(e)}
    
    def structure_address(self, text: str) -> Dict[str, Any]:
        """
        结构化地址解析
        
        Args:
            text: 地址文本
            
        Returns:
            解析结果字典
        """
        for attempt in range(self.REQUEST_RETRIES + 1):
            params = {
                "Action": "StructureAddress",
                "Version": self.VERSION,
                "Format": "JSON",
                "AccessKeyId": self.access_key_id,
                "SignatureMethod": "HMAC-SHA1",
                "SignatureVersion": "1.0",
                "SignatureNonce": str(random.random()),
                "Timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "AppKey": self.app_key,
                "ServiceCode": self.SERVICE_CODE,
                "Text": text,
                "DefaultProvince": self.default_province,
                "DefaultCity": self.default_city
            }
            params["Signature"] = self._sign_string(params)
            
            data = self._call_api(params)
            
            if "error" in data:
                if attempt == self.REQUEST_RETRIES:
                    self._log(f"[API] StructureAddress 失败: {text} | {data['error']}", "error")
                continue
            
            try:
                # 打印完整的 API 返回
                self._log(f"[API] StructureAddress 完整返回: {json.dumps(data, ensure_ascii=False)}", "debug")
                
                raw_data = data.get("Data", "{}")
                
                # Data 可能是字符串或已解析的字典
                if isinstance(raw_data, str):
                    inner = json.loads(raw_data)
                else:
                    inner = raw_data
                
                # 打印解析后的 inner
                self._log(f"[API] StructureAddress inner: {json.dumps(inner, ensure_ascii=False)}", "debug")
                
                if isinstance(inner, dict):
                    structure = inner.get("structure", {})
                    
                    # structure 可能是字典，也可能是字符串格式 "key1=value1 key2=value2"
                    if isinstance(structure, dict):
                        self._log(f"[API] StructureAddress structure(dict): {json.dumps(structure, ensure_ascii=False)}", "debug")
                        return structure
                    elif isinstance(structure, str):
                        # 解析字符串格式的 structure
                        parsed = {}
                        for token in structure.split():
                            if "=" in token:
                                k, v = token.split("=", 1)
                                parsed[k] = v
                        self._log(f"[API] StructureAddress structure(str->dict): {json.dumps(parsed, ensure_ascii=False)}", "debug")
                        return parsed
                    else:
                        self._log(f"[API] StructureAddress structure 类型异常: {type(structure)}", "warning")
                        return {}
                else:
                    return {}
            except Exception as e:
                self._log(f"[API] 解析 StructureAddress 响应失败: {e}", "debug")
                continue
        
        return {}
        
        return {}
    
    def predict_poi(self, text: str) -> str:
        """
        POI 预测
        
        Args:
            text: 地址文本
            
        Returns:
            POI 名称
        """
        params = {
            "Action": "PredictPOI",
            "Version": self.VERSION,
            "Format": "JSON",
            "AccessKeyId": self.access_key_id,
            "SignatureMethod": "HMAC-SHA1",
            "SignatureVersion": "1.0",
            "SignatureNonce": str(random.random()),
            "Timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "AppKey": self.app_key,
            "ServiceCode": self.SERVICE_CODE,
            "Text": text,
            "DefaultProvince": self.default_province,
            "DefaultCity": self.default_city
        }
        params["Signature"] = self._sign_string(params)
        
        data = self._call_api(params)
        
        # 打印完整的 API 返回
        self._log(f"[API] PredictPOI 完整返回: {json.dumps(data, ensure_ascii=False)}", "debug")
        
        if "Data" in data and not data.get("error"):
            try:
                raw_data = data["Data"]
                # Data 可能是字符串或已解析的字典
                if isinstance(raw_data, str):
                    inner = json.loads(raw_data)
                else:
                    inner = raw_data
                
                # 打印解析后的 inner
                self._log(f"[API] PredictPOI inner: {json.dumps(inner, ensure_ascii=False)}", "debug")
                
                if isinstance(inner, dict):
                    poi_predict = inner.get("poi_predict", "") or ""
                    self._log(f"[API] PredictPOI 结果: {poi_predict}", "debug")
                    return poi_predict
                # 成功但无 POI，返回空字符串
                return ""
            except Exception as e:
                self._log(f"[API] 解析 PredictPOI 响应失败: {e}", "debug")
                return None  # 解析失败，返回 None
        
        # API 调用失败，返回 None（不是空字符串）
        return None
    
    def parse(self, text: str) -> Dict[str, Any]:
        """
        完整解析流程（带缓存）
        
        流程：
        1. 调用 StructureAddress 获取结构化结果
        2. 拼接标准化地址：省市区 + 街道/镇 + 村/社区 + 道路 + 门牌号 + POI + 楼号 + 单元号
        3. 基于标准化地址调用 PredictPOI
        
        Args:
            text: 原始地址文本
            
        Returns:
            {
                "original": str,           # 原始地址
                "std_address": str,        # 标准化地址（拼接后）
                "province": str,           # 省
                "city": str,               # 市
                "district": str,           # 区/县
                "street": str,             # 街道/镇
                "village": str,            # 村/社区
                "road": str,               # 道路
                "road_no": str,            # 门牌号
                "poi": str,                # POI（结构化返回）
                "building_no": str,        # 楼号
                "unit_no": str,            # 单元号
                "room_no": str,            # 房间号
                "predict_poi": str,        # POI预测结果
                "predict_poi_source": str, # POI来源: structure/predict/empty
                "cached": bool             # 是否来自缓存
            }
        """
        text = text.strip()
        if not text:
            return self._empty_result(text)
        
        structure_cached = False
        poi_cached = False
        
        # 1. 检查 StructureAddress 缓存
        with self._cache_lock:
            if text in self._structure_cache:
                st = self._structure_cache[text]
                structure_cached = True
                self._log(f"[API] StructureAddress [缓存命中]: {text[:30]}...", "info")
            else:
                st = None
        
        # 如果缓存未命中，调用 StructureAddress API
        if st is None:
            self._log(f"[API] StructureAddress [调用API]: {text[:30]}...", "info")
            st = self.structure_address(text)
            
            # 确保 st 是字典
            if not isinstance(st, dict):
                self._log(f"[API] StructureAddress 返回非字典类型: {type(st)}, 值: {st}", "warning")
                st = {}
            
            # 只有成功返回（非空字典）才保存到缓存
            if st:
                with self._cache_lock:
                    self._structure_cache[text] = st
                    self._cache_dirty_count += 1
            else:
                self._log(f"[API] StructureAddress 返回空，不缓存: {text[:30]}...", "warning")
        
        # 2. 提取各个字段（阿里云 API 字段名映射）
        province = st.get("prov", "") or st.get("province", "") or ""
        city = st.get("city", "") or ""
        district = st.get("district", "") or ""
        street = st.get("town", "") or ""  # 街道/镇
        village = st.get("village", "") or ""  # 村/社区
        road = st.get("road", "") or ""
        road_no = st.get("roadNo", "") or st.get("roadno", "") or ""  # 门牌号
        poi = st.get("poi", "") or ""
        building_no = st.get("houseno", "") or ""  # 楼号
        unit_no = st.get("cellno", "") or ""  # 单元号
        room_no = st.get("roomno", "") or ""  # 房间号
        
        # 3. 拼接标准化地址：省市区 + 街道/镇 + 村/社区 + 道路 + 门牌号 + POI + 楼号 + 单元号
        std_parts = [
            province, city, district,
            street, village,
            road, road_no,
            poi,
            f"{building_no}号楼" if building_no else "",
            f"{unit_no}单元" if unit_no else ""
        ]
        std_address = ''.join([p for p in std_parts if p])
        
        # 4. 检查 PredictPOI 缓存（以标准化地址为 key）
        predict_poi = ""
        predict_poi_source = "empty"
        
        if std_address:
            with self._cache_lock:
                if std_address in self._poi_cache:
                    predict_poi = self._poi_cache[std_address]
                    poi_cached = True
                    if predict_poi:
                        predict_poi_source = "predict"
                    self._log(f"[API] PredictPOI [缓存命中]: {std_address[:30]}...", "info")
                else:
                    predict_poi = None
            
            # 如果缓存未命中，调用 PredictPOI API
            if predict_poi is None:
                self._log(f"[API] PredictPOI [调用API]: {std_address[:30]}...", "info")
                predict_poi = self.predict_poi(std_address)
                
                # 只有 API 成功（返回非 None）才保存到缓存
                # None 表示 API 失败，空字符串表示成功但无 POI
                if predict_poi is not None:
                    with self._cache_lock:
                        self._poi_cache[std_address] = predict_poi
                        self._cache_dirty_count += 1
                    
                    if predict_poi:
                        predict_poi_source = "predict"
                else:
                    self._log(f"[API] PredictPOI 调用失败，不缓存: {std_address[:30]}...", "warning")
                    predict_poi = ""  # 失败时设为空字符串，不影响后续逻辑
            
            # 如果预测为空，使用结构化返回的 POI
            if not predict_poi and poi:
                predict_poi = poi
                predict_poi_source = "structure"
        
        result = {
            "original": text,
            "std_address": std_address,
            "province": province,
            "city": city,
            "district": district,
            "street": street,
            "village": village,
            "road": road,
            "road_no": road_no,
            "poi": poi,
            "building_no": building_no,
            "unit_no": unit_no,
            "room_no": room_no,
            "predict_poi": predict_poi,
            "predict_poi_source": predict_poi_source,
            "structure_cached": structure_cached,
            "poi_cached": poi_cached,
            "cached": structure_cached and poi_cached  # 两个都命中才算完全缓存
        }
        
        # 触发后台自动持久化（不阻塞业务）
        self._auto_save_if_needed()
        
        return result
    
    def _empty_result(self, text: str = "") -> Dict[str, Any]:
        """返回空结果"""
        return {
            "original": text,
            "std_address": "",
            "province": "",
            "city": "",
            "district": "",
            "street": "",
            "village": "",
            "road": "",
            "road_no": "",
            "poi": "",
            "building_no": "",
            "unit_no": "",
            "room_no": "",
            "predict_poi": "",
            "predict_poi_source": "empty",
            "structure_cached": False,
            "poi_cached": False,
            "cached": False
        }
    
    def _auto_save_if_needed(self):
        """检查是否需要自动保存（后台执行，不阻塞业务）"""
        if self._cache_dirty_count >= self.AUTO_SAVE_INTERVAL:
            self._async_save_cache()
    
    def _async_save_cache(self):
        """异步保存缓存到磁盘（后台线程）"""
        with self._save_lock:
            if self._saving:
                return  # 已有保存任务在执行
            self._saving = True
        
        def do_save():
            try:
                self.save_cache_to_disk()
                with self._cache_lock:
                    self._cache_dirty_count = 0
            finally:
                with self._save_lock:
                    self._saving = False
        
        save_thread = threading.Thread(target=do_save, daemon=True)
        save_thread.start()
    
    def parse_batch(
        self,
        texts: List[str],
        progress_callback: Optional[Callable[[int, int], None]] = None,
        cancel_check: Optional[Callable[[], bool]] = None
    ) -> List[Dict[str, Any]]:
        """
        批量解析
        
        Args:
            texts: 地址文本列表
            progress_callback: 进度回调 (current, total)
            cancel_check: 取消检查函数
            
        Returns:
            解析结果列表
        """
        results = []
        total = len(texts)
        
        for idx, text in enumerate(texts):
            # 检查取消
            if cancel_check and cancel_check():
                self._log("[API] 批量解析已取消")
                break
            
            # 更新进度
            if progress_callback:
                progress_callback(idx + 1, total)
            
            result = self.parse(text)
            results.append(result)
        
        # 批量解析完成后，强制保存缓存（后台执行）
        if self._cache_dirty_count > 0:
            self._async_save_cache()
        
        return results
    
    def flush_cache(self):
        """强制将缓存持久化到磁盘（同步执行，用于程序退出前调用）"""
        with self._cache_lock:
            structure_size = len(self._structure_cache)
            poi_size = len(self._poi_cache)
        
        if structure_size > 0 or poi_size > 0:
            self.save_cache_to_disk()
            with self._cache_lock:
                self._cache_dirty_count = 0
        else:
            self._log("[API] 缓存为空，无需保存", "debug")
    
    def get_cache_stats(self) -> Dict[str, int]:
        """获取缓存统计"""
        with self._cache_lock:
            return {
                "structure": len(self._structure_cache),  # StructureAddress 缓存数
                "poi": len(self._poi_cache),  # PredictPOI 缓存数
                "total": len(self._structure_cache) + len(self._poi_cache)
            }
    
    def _get_cache_file_path(self) -> str:
        """获取缓存文件路径"""
        if not self.cache_folder:
            return ""
        return os.path.join(self.cache_folder, "api_cache.json")
    
    def _load_disk_cache(self):
        """从磁盘加载缓存（分别加载两个 API 的缓存）"""
        cache_file = self._get_cache_file_path()
        if not cache_file or not os.path.exists(cache_file):
            return
        
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                disk_cache = json.load(f)
            
            # 分别加载两个 API 的缓存
            structure_cache = disk_cache.get("structure", {})
            poi_cache = disk_cache.get("poi", {})
            
            with self._cache_lock:
                self._structure_cache.update(structure_cache)
                self._poi_cache.update(poi_cache)
            
            self._log(f"[API] 已加载缓存: StructureAddress {len(structure_cache)} 条, PredictPOI {len(poi_cache)} 条")
        except Exception as e:
            self._log(f"[API] 加载缓存失败: {e}", "error")
    
    def save_cache(self):
        """保存缓存（别名方法）"""
        self.save_cache_to_disk()
    
    def save_cache_to_disk(self):
        """保存缓存到磁盘（分别保存两个 API 的缓存）"""
        cache_file = self._get_cache_file_path()
        if not cache_file:
            self._log("[API] 未配置缓存目录，跳过保存", "warning")
            return
        
        try:
            os.makedirs(os.path.dirname(cache_file), exist_ok=True)
            with self._cache_lock:
                cache_data = {
                    "structure": dict(self._structure_cache),  # StructureAddress 缓存
                    "poi": dict(self._poi_cache)  # PredictPOI 缓存
                }
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)
            self._log(f"[API] 缓存已保存到: {cache_file}")
            self._log(f"[API] StructureAddress {len(cache_data['structure'])} 条, PredictPOI {len(cache_data['poi'])} 条", "info")
        except Exception as e:
            self._log(f"[API] 保存缓存失败: {e}", "error")
    
    def clear_cache(self):
        """清空缓存"""
        with self._cache_lock:
            self._structure_cache.clear()
            self._poi_cache.clear()
        self._log("[API] 缓存已清空（StructureAddress + PredictPOI）")
    
    def test_connection(self) -> Dict[str, Any]:
        """
        测试 API 连接
        
        Returns:
            {"success": bool, "message": str}
        """
        self._log("[API] 开始测试连接...", "info")
        self._log(f"[API] AccessKey ID: {self.access_key_id[:8]}****", "info")
        self._log(f"[API] App Key: {self.app_key}", "info")
        self._log(f"[API] 默认省市: {self.default_province} {self.default_city}", "info")
        
        try:
            result = self.structure_address("北京市朝阳区")
            if result:
                self._log(f"[API] 测试成功，返回结果: {result}", "info")
                return {"success": True, "message": "连接成功"}
            else:
                self._log("[API] 测试失败，API 返回空结果", "warning")
                return {"success": False, "message": "API 返回空结果，请检查配置"}
        except Exception as e:
            self._log(f"[API] 测试异常: {e}", "error")
            return {"success": False, "message": f"连接失败: {e}"}

