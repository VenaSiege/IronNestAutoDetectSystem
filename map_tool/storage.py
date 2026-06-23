"""JSON 保存与加载。"""

from __future__ import annotations

import json
from pathlib import Path

from map_tool.models import Marker

FILE_VERSION = 1


def save_markers(file_path: str, markers: list[Marker]) -> None:
    """将标识点保存到 JSON 文件。"""
    payload = {
        "version": FILE_VERSION,
        "markers": [marker.to_dict() for marker in markers],
    }
    Path(file_path).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def load_markers(file_path: str) -> list[Marker]:
    """从 JSON 文件加载标识点。"""
    raw_text = Path(file_path).read_text(encoding="utf-8")
    payload = json.loads(raw_text)
    if not isinstance(payload, dict):
        raise ValueError("文件内容不是合法对象。")
    if payload.get("version") != FILE_VERSION:
        raise ValueError("文件版本不受支持。")
    raw_markers = payload.get("markers")
    if not isinstance(raw_markers, list):
        raise ValueError("文件缺少 markers 列表。")
    return [Marker.from_dict(item) for item in raw_markers]
