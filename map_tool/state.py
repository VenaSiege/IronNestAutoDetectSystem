"""地图状态与唯一性规则。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional

from map_tool.models import (
    BIG_COLS,
    BIG_ROWS,
    NUMBER_LABELS,
    REFERENCE_LABELS,
    CellCoordinate,
    Marker,
)


@dataclass
class PlaceResult:
    """描述一次放置操作的结果。"""

    marker: Marker
    replaced_marker: Optional[Marker]
    removed_iron_nest: Optional[Marker]


class MapState:
    """管理全部标识点和保存状态。"""

    def __init__(self) -> None:
        """初始化空地图。"""
        self._markers: dict[tuple[str, int, int, int], Marker] = {}

    def clear(self) -> None:
        """清空全部标识点。"""
        self._markers.clear()

    def all_markers(self) -> list[Marker]:
        """返回全部标识点。"""
        return list(self._markers.values())

    def get_marker(self, coordinate: CellCoordinate) -> Optional[Marker]:
        """读取指定小格的标识点。"""
        return self._markers.get(coordinate.to_key())

    def set_markers(self, markers: Iterable[Marker]) -> None:
        """整体替换状态，并做基础校验。"""
        new_state = MapState()
        for marker in markers:
            new_state._validate_marker(marker)
            existing = new_state.get_marker(marker.coordinate())
            if existing is not None:
                raise ValueError("加载失败：同一小格存在多个标识。")
            if marker.type == "iron_nest" and new_state.find_iron_nest() is not None:
                raise ValueError("加载失败：铁巢只能存在一个。")
            if marker.type == "observation" and new_state.is_label_taken("observation", marker.label):
                raise ValueError("加载失败：观测点编号重复。")
            if marker.type == "reference" and new_state.is_label_taken("reference", marker.label):
                raise ValueError("加载失败：参考点编号重复。")
            if marker.type == "enemy_target" and new_state.is_label_taken("enemy_target", marker.label):
                raise ValueError("加载失败：敌军目标点编号重复。")
            new_state._markers[marker.coordinate().to_key()] = marker
        self._markers = new_state._markers

    def remove_marker(self, coordinate: CellCoordinate) -> Optional[Marker]:
        """删除指定小格的标识点。"""
        return self._markers.pop(coordinate.to_key(), None)

    def find_iron_nest(self) -> Optional[Marker]:
        """查找当前铁巢。"""
        for marker in self._markers.values():
            if marker.type == "iron_nest":
                return marker
        return None

    def markers_in_big_cell(self, big_col: str, big_row: int) -> list[Marker]:
        """获取某个大格内的全部标识点。"""
        return [
            marker
            for marker in self._markers.values()
            if marker.big_col == big_col and marker.big_row == big_row
        ]

    def is_label_taken(self, marker_type: str, label: str) -> bool:
        """检查某类编号是否已被占用。"""
        return any(
            marker.type == marker_type and marker.label == label
            for marker in self._markers.values()
        )

    def next_label(self, marker_type: str) -> Optional[str]:
        """分配当前最小未使用编号。"""
        if marker_type in {"observation", "enemy_target"}:
            candidates = NUMBER_LABELS
        elif marker_type == "reference":
            candidates = REFERENCE_LABELS
        else:
            return None

        for label in candidates:
            if not self.is_label_taken(marker_type, label):
                return label
        return None

    def place_marker(
        self,
        marker_type: str,
        coordinate: CellCoordinate,
        name: str = "",
    ) -> PlaceResult:
        """按业务规则在指定位置放置标识点。"""
        self._validate_coordinate(coordinate)
        replaced_marker = self.get_marker(coordinate)
        removed_iron_nest = None

        if marker_type == "iron_nest":
            label = "铁巢"
            current_iron_nest = self.find_iron_nest()
            if current_iron_nest is not None and current_iron_nest.coordinate() != coordinate:
                removed_iron_nest = self.remove_marker(current_iron_nest.coordinate())
        elif marker_type in {"observation", "reference", "enemy_target"}:
            label = self.next_label(marker_type) or ""
            if not label:
                raise ValueError("该类型编号已用尽，无法继续新增。")
        else:
            raise ValueError("未知标识点类型。")

        if replaced_marker is not None:
            self.remove_marker(coordinate)

        marker = Marker(
            type=marker_type,
            big_col=coordinate.big_col,
            big_row=coordinate.big_row,
            small_x=coordinate.small_x,
            small_y=coordinate.small_y,
            label=label,
            name=name,
        )
        self._validate_marker(marker)
        self._markers[coordinate.to_key()] = marker
        return PlaceResult(
            marker=marker,
            replaced_marker=replaced_marker,
            removed_iron_nest=removed_iron_nest,
        )

    def _validate_coordinate(self, coordinate: CellCoordinate) -> None:
        """校验坐标是否合法。"""
        if coordinate.big_col not in BIG_COLS:
            raise ValueError("大格列坐标非法。")
        if coordinate.big_row not in BIG_ROWS:
            raise ValueError("大格行坐标非法。")
        if not 0 <= coordinate.small_x <= 9:
            raise ValueError("小格横坐标非法。")
        if not 0 <= coordinate.small_y <= 9:
            raise ValueError("小格纵坐标非法。")

    def _validate_marker(self, marker: Marker) -> None:
        """校验标识点字段。"""
        self._validate_coordinate(marker.coordinate())
        if marker.type not in {"iron_nest", "observation", "reference", "enemy_target"}:
            raise ValueError("标识点类型非法。")
        if marker.type == "reference" and marker.label not in REFERENCE_LABELS:
            raise ValueError("参考点编号非法。")
        if marker.type in {"observation", "enemy_target"} and marker.label not in NUMBER_LABELS:
            raise ValueError("数字编号非法。")
