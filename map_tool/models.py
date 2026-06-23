"""数据模型与地图常量。"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Optional

BIG_COLS = [chr(code) for code in range(ord("A"), ord("T") + 1)]
BIG_ROWS = list(range(1, 11))
SMALL_RANGE = list(range(10))
REFERENCE_LABELS = [chr(code) for code in range(ord("A"), ord("Z") + 1)]
NUMBER_LABELS = [str(number) for number in range(1, 10)]


@dataclass(frozen=True)
class CellCoordinate:
    """表示一个完整的小格坐标。"""

    big_col: str
    big_row: int
    small_x: int
    small_y: int

    def to_key(self) -> tuple[str, int, int, int]:
        """转换为可哈希坐标键。"""
        return (self.big_col, self.big_row, self.small_x, self.small_y)


@dataclass
class Marker:
    """表示地图上的一个标识点。"""

    type: str
    big_col: str
    big_row: int
    small_x: int
    small_y: int
    label: str
    name: str = ""

    def coordinate(self) -> CellCoordinate:
        """返回当前标识点对应的格子坐标。"""
        return CellCoordinate(
            big_col=self.big_col,
            big_row=self.big_row,
            small_x=self.small_x,
            small_y=self.small_y,
        )

    def to_dict(self) -> dict[str, object]:
        """转换为可保存的字典。"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "Marker":
        """从字典恢复标识点。"""
        return cls(
            type=str(data["type"]),
            big_col=str(data["big_col"]),
            big_row=int(data["big_row"]),
            small_x=int(data["small_x"]),
            small_y=int(data["small_y"]),
            label=str(data["label"]),
            name=str(data.get("name", "")),
        )


def marker_display_text(marker: Optional[Marker]) -> str:
    """生成标识点的界面显示文本。"""
    if marker is None:
        return ""
    if marker.type == "iron_nest":
        return "铁"
    return marker.label


def marker_summary_text(marker: Marker) -> str:
    """生成大地图中的标识摘要文本。"""
    prefix_map = {
        "iron_nest": "铁",
        "observation": "观",
        "reference": "参",
        "enemy_target": "敌",
    }
    prefix = prefix_map.get(marker.type, "")
    if marker.type == "iron_nest":
        return prefix
    return f"{prefix}{marker.label}"


def marker_detail_text(marker: Marker) -> str:
    """生成状态栏中的标识详情文本。"""
    summary = marker_summary_text(marker)
    if marker.type == "enemy_target" and marker.name:
        return f"{summary}({marker.name})"
    return summary
