# -*- coding: utf-8 -*-
"""
地址补全器

根据内置的行政区划数据（data/regions/*.json）
倒推地址中缺失的省市区县街道信息

数据结构:
- provinces.json: [{code, name}]
- cities.json: [{code, name, provinceCode}]
- areas.json: [{code, name, cityCode}]
- streets.json: [{code, name, areaCode}]
- villages.json: [{code, name, streetCode}]
"""
import os
import json
import re
from typing import Dict, List, Optional, Tuple
from functools import lru_cache


class RegionLookup:
    """地址补全器"""
    
    def __init__(self, data_dir: Optional[str] = None):
        # 默认使用插件内置数据
        if data_dir is None:
            data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "regions")
        
        self.data_dir = data_dir
        self._provinces = {}  # code -> name
        self._cities = {}     # code -> {name, provinceCode}
        self._areas = {}      # code -> {name, cityCode}
        self._streets = {}    # code -> {name, areaCode}
        
        # 反向索引：名称 -> codes
        self._name_to_province = {}  # name -> code
        self._name_to_city = {}      # name -> [codes]
        self._name_to_area = {}      # name -> [codes]
        self._name_to_street = {}    # name -> [codes]
        
        # 常见后缀
        self._area_suffixes = ['区', '县', '市', '旗', '自治县', '自治旗']
        self._street_suffixes = ['街道', '镇', '乡', '街道办事处', '办事处']
        
        self._loaded = False
    
    def _ensure_loaded(self):
        """确保数据已加载"""
        if not self._loaded:
            self._load_data()
            self._loaded = True
    
    def _load_data(self):
        """加载行政区划数据"""
        # 加载省份
        provinces_file = os.path.join(self.data_dir, "provinces.json")
        if os.path.exists(provinces_file):
            with open(provinces_file, 'r', encoding='utf-8') as f:
                for item in json.load(f):
                    code = item['code']
                    name = item['name']
                    self._provinces[code] = name
                    # 建立名称索引（去掉后缀）
                    short_name = name.replace('省', '').replace('市', '').replace('自治区', '').replace('壮族', '').replace('维吾尔', '').replace('回族', '')
                    self._name_to_province[name] = code
                    if short_name != name:
                        self._name_to_province[short_name] = code
        
        # 加载城市
        cities_file = os.path.join(self.data_dir, "cities.json")
        if os.path.exists(cities_file):
            with open(cities_file, 'r', encoding='utf-8') as f:
                for item in json.load(f):
                    code = item['code']
                    name = item['name']
                    province_code = item.get('provinceCode', '')
                    self._cities[code] = {'name': name, 'provinceCode': province_code}
                    # 建立名称索引
                    if name not in self._name_to_city:
                        self._name_to_city[name] = []
                    self._name_to_city[name].append(code)
                    # 去掉后缀的版本
                    short_name = name.replace('市', '').replace('地区', '').replace('盟', '')
                    if short_name != name:
                        if short_name not in self._name_to_city:
                            self._name_to_city[short_name] = []
                        self._name_to_city[short_name].append(code)
        
        # 加载区县
        areas_file = os.path.join(self.data_dir, "areas.json")
        if os.path.exists(areas_file):
            with open(areas_file, 'r', encoding='utf-8') as f:
                for item in json.load(f):
                    code = item['code']
                    name = item['name']
                    city_code = item.get('cityCode', '')
                    self._areas[code] = {'name': name, 'cityCode': city_code}
                    # 建立名称索引
                    if name not in self._name_to_area:
                        self._name_to_area[name] = []
                    self._name_to_area[name].append(code)
                    # 去掉后缀的版本
                    for suffix in self._area_suffixes:
                        if name.endswith(suffix):
                            short_name = name[:-len(suffix)]
                            if short_name and short_name not in self._name_to_area:
                                self._name_to_area[short_name] = []
                            if short_name:
                                self._name_to_area[short_name].append(code)
                            break
        
        # 加载街道
        streets_file = os.path.join(self.data_dir, "streets.json")
        if os.path.exists(streets_file):
            with open(streets_file, 'r', encoding='utf-8') as f:
                for item in json.load(f):
                    code = item['code']
                    name = item['name']
                    area_code = item.get('areaCode', '')
                    self._streets[code] = {'name': name, 'areaCode': area_code}
                    # 建立名称索引
                    if name not in self._name_to_street:
                        self._name_to_street[name] = []
                    self._name_to_street[name].append(code)
                    # 去掉后缀的版本
                    for suffix in self._street_suffixes:
                        if name.endswith(suffix):
                            short_name = name[:-len(suffix)]
                            if short_name and short_name not in self._name_to_street:
                                self._name_to_street[short_name] = []
                            if short_name:
                                self._name_to_street[short_name].append(code)
                            break
    
    def complete_address(self, address: str, known_province: str = '', known_city: str = '', 
                         known_area: str = '', known_street: str = '') -> Dict:
        """
        补全地址中的省市区县街道信息
        
        Args:
            address: 原始地址字符串
            known_province: 已知的省份
            known_city: 已知的城市
            known_area: 已知的区县
            known_street: 已知的街道
        
        Returns:
            {
                'province': '河北省',
                'city': '廊坊市',
                'area': '安次区',
                'street': '银河路街道',
                'confidence': 0.9,  # 置信度
                'method': 'area_lookup'  # 推断方法
            }
        """
        self._ensure_loaded()
        
        result = {
            'province': known_province or '',
            'city': known_city or '',
            'area': known_area or '',
            'street': known_street or '',
            'confidence': 0.0,
            'method': 'none'
        }
        
        # 尝试从地址中提取区县
        if not result['area']:
            result['area'] = self._extract_area_from_address(address)
        
        # 尝试从地址中提取街道
        if not result['street']:
            result['street'] = self._extract_street_from_address(address)
        
        # 根据区县倒推省市
        if result['area'] and (not result['province'] or not result['city']):
            deduced = self._deduce_from_area(result['area'])
            if deduced:
                if not result['province']:
                    result['province'] = deduced.get('province', '')
                if not result['city']:
                    result['city'] = deduced.get('city', '')
                result['confidence'] = 0.9
                result['method'] = 'area_lookup'
        
        # 根据街道倒推省市区
        if result['street'] and (not result['province'] or not result['city'] or not result['area']):
            deduced = self._deduce_from_street(result['street'])
            if deduced:
                if not result['province']:
                    result['province'] = deduced.get('province', '')
                if not result['city']:
                    result['city'] = deduced.get('city', '')
                if not result['area']:
                    result['area'] = deduced.get('area', '')
                result['confidence'] = max(result['confidence'], 0.85)
                result['method'] = 'street_lookup'
        
        # 根据城市倒推省
        if result['city'] and not result['province']:
            deduced = self._deduce_from_city(result['city'])
            if deduced:
                result['province'] = deduced.get('province', '')
                result['confidence'] = max(result['confidence'], 0.95)
                result['method'] = 'city_lookup'
        
        return result
    
    def _extract_area_from_address(self, address: str) -> str:
        """从地址中提取区县名称"""
        if not address:
            return ''
        
        candidates = []
        
        # 方法1：匹配"市"后面的区县（最准确）
        # 例如：廊坊市安次区 -> 安次区
        pattern1 = r'[市州盟]([\u4e00-\u9fa5]{2,6}?)([区县旗])'
        for match in re.finditer(pattern1, address):
            area_name = match.group(1) + match.group(2)
            if area_name in self._name_to_area:
                candidates.append((100, area_name))  # 高优先级
        
        # 方法2：匹配完整的区县名（带后缀）
        pattern2 = r'([\u4e00-\u9fa5]{2,6}?)([区县旗])(?!域|划)'
        for match in re.finditer(pattern2, address):
            area_name = match.group(1) + match.group(2)
            if area_name in self._name_to_area:
                # 避免匹配到省名的一部分（如"河北省"的"北"）
                start_pos = match.start()
                if start_pos > 0:
                    prev_char = address[start_pos - 1]
                    if prev_char in '省市州盟':
                        continue
                candidates.append((len(area_name), area_name))
        
        # 方法3：匹配自治县/自治旗
        pattern3 = r'([\u4e00-\u9fa5]{2,10}?自治[县旗])'
        for match in re.finditer(pattern3, address):
            area_name = match.group(1)
            if area_name in self._name_to_area:
                candidates.append((len(area_name) + 10, area_name))  # 自治县优先
        
        # 去重并按优先级排序
        if candidates:
            # 去重
            seen = set()
            unique = []
            for priority, name in candidates:
                if name not in seen:
                    seen.add(name)
                    unique.append((priority, name))
            unique.sort(reverse=True)
            return unique[0][1]
        
        return ''
    
    def _extract_street_from_address(self, address: str) -> str:
        """从地址中提取街道名称"""
        if not address:
            return ''
        
        # 只使用正则匹配带后缀的街道（xx街道、xx镇、xx乡）
        # 避免短名称的误匹配
        patterns = [
            r'([\u4e00-\u9fa5]{2,10}?(?:街道办事处|街道|办事处))',
            r'([\u4e00-\u9fa5]{2,6}?[镇乡])(?![村])',  # 排除 "xx镇村" 的情况
        ]
        
        candidates = []
        for pattern in patterns:
            for match in re.finditer(pattern, address):
                street_name = match.group(1)
                # 验证是否是有效的街道
                if street_name in self._name_to_street:
                    candidates.append((len(street_name), street_name))
        
        # 优先返回最长的匹配
        if candidates:
            candidates.sort(reverse=True)
            return candidates[0][1]
        
        # 尝试匹配去掉后缀的版本
        for pattern in patterns:
            for match in re.finditer(pattern, address):
                street_name = match.group(1)
                for suffix in self._street_suffixes:
                    if street_name.endswith(suffix):
                        short = street_name[:-len(suffix)]
                        if short in self._name_to_street:
                            return street_name
        return ''
    
    def _deduce_from_area(self, area_name: str) -> Optional[Dict]:
        """根据区县名称倒推省市"""
        codes = self._name_to_area.get(area_name, [])
        
        if not codes:
            # 尝试去掉后缀
            for suffix in self._area_suffixes:
                if area_name.endswith(suffix):
                    short_name = area_name[:-len(suffix)]
                    codes = self._name_to_area.get(short_name, [])
                    if codes:
                        break
        
        if not codes:
            return None
        
        # 取第一个匹配（TODO: 可以根据上下文选择最佳匹配）
        area_code = codes[0]
        area_info = self._areas.get(area_code, {})
        city_code = area_info.get('cityCode', '')
        
        if not city_code:
            return None
        
        city_info = self._cities.get(city_code, {})
        city_name = city_info.get('name', '')
        province_code = city_info.get('provinceCode', '')
        province_name = self._provinces.get(province_code, '')
        
        return {
            'province': province_name,
            'city': city_name,
            'area': self._areas.get(area_code, {}).get('name', area_name)
        }
    
    def _deduce_from_street(self, street_name: str) -> Optional[Dict]:
        """根据街道名称倒推省市区"""
        codes = self._name_to_street.get(street_name, [])
        
        if not codes:
            # 尝试去掉后缀
            for suffix in self._street_suffixes:
                if street_name.endswith(suffix):
                    short_name = street_name[:-len(suffix)]
                    codes = self._name_to_street.get(short_name, [])
                    if codes:
                        break
        
        if not codes:
            return None
        
        # 取第一个匹配
        street_code = codes[0]
        street_info = self._streets.get(street_code, {})
        area_code = street_info.get('areaCode', '')
        
        if not area_code:
            return None
        
        area_info = self._areas.get(area_code, {})
        area_name = area_info.get('name', '')
        city_code = area_info.get('cityCode', '')
        
        city_info = self._cities.get(city_code, {})
        city_name = city_info.get('name', '')
        province_code = city_info.get('provinceCode', '')
        province_name = self._provinces.get(province_code, '')
        
        return {
            'province': province_name,
            'city': city_name,
            'area': area_name,
            'street': self._streets.get(street_code, {}).get('name', street_name)
        }
    
    def _deduce_from_city(self, city_name: str) -> Optional[Dict]:
        """根据城市名称倒推省份"""
        codes = self._name_to_city.get(city_name, [])
        
        if not codes:
            # 尝试去掉后缀
            short_name = city_name.replace('市', '').replace('地区', '').replace('盟', '')
            codes = self._name_to_city.get(short_name, [])
        
        if not codes:
            return None
        
        city_code = codes[0]
        city_info = self._cities.get(city_code, {})
        province_code = city_info.get('provinceCode', '')
        province_name = self._provinces.get(province_code, '')
        
        return {
            'province': province_name,
            'city': self._cities.get(city_code, {}).get('name', city_name)
        }
    
    def get_all_areas_in_city(self, city_name: str) -> List[str]:
        """获取某个城市下的所有区县"""
        self._ensure_loaded()
        
        codes = self._name_to_city.get(city_name, [])
        if not codes:
            codes = self._name_to_city.get(city_name.replace('市', ''), [])
        
        if not codes:
            return []
        
        city_code = codes[0]
        areas = []
        for area_code, area_info in self._areas.items():
            if area_info.get('cityCode', '') == city_code:
                areas.append(area_info.get('name', ''))
        
        return areas
    
    def validate_region(self, province: str, city: str, area: str) -> bool:
        """验证省市区是否匹配"""
        self._ensure_loaded()
        
        # 获取省code
        province_code = self._name_to_province.get(province, '')
        if not province_code:
            province_code = self._name_to_province.get(province.replace('省', ''), '')
        
        if not province_code:
            return False
        
        # 获取市code并验证
        city_codes = self._name_to_city.get(city, [])
        if not city_codes:
            city_codes = self._name_to_city.get(city.replace('市', ''), [])
        
        valid_city_code = None
        for code in city_codes:
            city_info = self._cities.get(code, {})
            if city_info.get('provinceCode', '') == province_code:
                valid_city_code = code
                break
        
        if not valid_city_code:
            return False
        
        # 获取区code并验证
        if area:
            area_codes = self._name_to_area.get(area, [])
            for suffix in self._area_suffixes:
                if area.endswith(suffix):
                    short = area[:-len(suffix)]
                    area_codes.extend(self._name_to_area.get(short, []))
            
            for code in area_codes:
                area_info = self._areas.get(code, {})
                if area_info.get('cityCode', '') == valid_city_code:
                    return True
            return False
        
        return True

