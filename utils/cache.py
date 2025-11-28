"""
Simple caching helper for workflow steps.
Caches stored as JSON files under plugin `cache/` directory.
"""
import json
from pathlib import Path
from typing import Any


CACHE_DIR = Path(__file__).parent.parent / 'cache'
CACHE_DIR.mkdir(exist_ok=True)


def save_cache(name: str, data: Any) -> Path:
    p = CACHE_DIR / f"{name}.json"
    with open(p, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return p


def load_cache(name: str):
    p = CACHE_DIR / f"{name}.json"
    if not p.exists():
        return None
    with open(p, 'r', encoding='utf-8') as f:
        return json.load(f)


def list_caches():
    return [p.name for p in CACHE_DIR.glob('*.json')]
