"""
测试数据生成脚本

生成示例 CSV/Excel 数据用于测试地址匹配功能
"""

import csv
import json
from pathlib import Path


def generate_test_data():
    """生成测试数据文件"""
    
    # 示例数据 1：左表（主表 - 管网数据）
    left_data = [
        {
            'id': 'MW001',
            'province': '北京市',
            'city': '北京市',
            'district': '朝阳区',
            'street': '建国路',
            'building': '1号',
            'coordinate': '39.9,116.4',
            'pipe_type': '供水管'
        },
        {
            'id': 'MW002',
            'province': '北京市',
            'city': '北京市',
            'district': '朝阳区',
            'street': '建国路',
            'building': '5号',
            'coordinate': '39.91,116.41',
            'pipe_type': '供水管'
        },
        {
            'id': 'MW003',
            'province': '北京市',
            'city': '北京市',
            'district': '朝阳区',
            'street': '东三环',
            'building': '2号',
            'coordinate': '39.92,116.42',
            'pipe_type': '排水管'
        },
        {
            'id': 'MW004',
            'province': '上海市',
            'city': '上海市',
            'district': '浦东新区',
            'street': '浦东大道',
            'building': '100号',
            'coordinate': '31.2,121.5',
            'pipe_type': '供水管'
        },
    ]
    
    # 示例数据 2：右表（待匹配表 - Excel 数据）
    right_data = [
        {
            'record_id': 'EX001',
            'address_province': '北京',
            'address_city': '北京',
            'address_district': '朝阳',
            'address_street': '建国路',
            'address_number': '1',
            'company': '天然气公司'
        },
        {
            'record_id': 'EX002',
            'address_province': '北京',
            'address_city': '北京',
            'address_district': '朝阳',
            'address_street': '建国路',
            'address_number': '5号',
            'company': '自来水公司'
        },
        {
            'record_id': 'EX003',
            'address_province': '北京',
            'address_city': '北京市',
            'address_district': '朝阳区',
            'address_street': '东三环中路',
            'address_number': '2',
            'company': '污水处理公司'
        },
        {
            'record_id': 'EX004',
            'address_province': '上海',
            'address_city': '上海',
            'address_district': '浦东新区',
            'address_street': '浦东大道',
            'address_number': '100号',
            'company': '供水公司'
        },
    ]
    
    # 输出目录
    output_dir = Path(__file__).parent.parent / 'test_data'
    output_dir.mkdir(exist_ok=True)
    
    # 生成 CSV（左表）
    csv_path = output_dir / 'test_left.csv'
    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=left_data[0].keys())
        writer.writeheader()
        writer.writerows(left_data)
    print(f"✓ 生成测试数据: {csv_path}")
    
    # 生成 JSON（右表）
    json_path = output_dir / 'test_right.geojson'
    geojson = {
        'type': 'FeatureCollection',
        'features': [
            {
                'type': 'Feature',
                'properties': row,
                'geometry': {
                    'type': 'Point',
                    'coordinates': [0, 0]  # 占位
                }
            }
            for row in right_data
        ]
    }
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(geojson, f, ensure_ascii=False, indent=2)
    print(f"✓ 生成测试数据: {json_path}")
    
    print(f"\n测试数据已生成到: {output_dir}")
    print(f"左表 (CSV): {len(left_data)} 条记录")
    print(f"右表 (GeoJSON): {len(right_data)} 条记录")
    
    return output_dir


if __name__ == '__main__':
    generate_test_data()
