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
        self._markers_by_big_cell: dict[tuple[str, int], list[Marker]] = {}
        self._labels_by_type: dict[str, set[str]] = {
            "observation": set(),
            "reference": set(),
            "enemy_target": set(),
        }
        self._iron_nest_key: tuple[str, int, int, int] | None = None

    def clear(self) -> None:
        """清空全部标识点。"""
        self._markers.clear()
        self._markers_by_big_cell.clear()
        for labels in self._labels_by_type.values():
            labels.clear()
        self._iron_nest_key = None

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
            coordinate = marker.coordinate()
            if new_state.get_marker(coordinate) is not None:
                raise ValueError("加载失败：同一小格存在多个标识。")
            if marker.type == "iron_nest" and new_state._iron_nest_key is not None:
                raise ValueError("加载失败：铁巢只能存在一个。")
            if marker.type == "observation" and marker.label in new_state._labels_by_type["observation"]:
                raise ValueError("加载失败：观测点编号重复。")
            if marker.type == "reference" and marker.label in new_state._labels_by_type["reference"]:
                raise ValueError("加载失败：参考点编号重复。")
            if marker.type == "enemy_target" and marker.label in new_state._labels_by_type["enemy_target"]:
                raise ValueError("加载失败：敌军目标点编号重复。")
            new_state._add_marker(marker)
        self._markers = new_state._markers
        self._markers_by_big_cell = new_state._markers_by_big_cell
        self._labels_by_type = new_state._labels_by_type
        self._iron_nest_key = new_state._iron_nest_key

    def remove_marker(self, coordinate: CellCoordinate) -> Optional[Marker]:
        """删除指定小格的标识点。"""
        marker = self._markers.pop(coordinate.to_key(), None)
        if marker is None:
            return None
        big_cell_key = (marker.big_col, marker.big_row)
        markers = self._markers_by_big_cell.get(big_cell_key)
        if markers is not None:
            markers[:] = [item for item in markers if item.coordinate().to_key() != coordinate.to_key()]
            if not markers:
                del self._markers_by_big_cell[big_cell_key]
        if marker.type in self._labels_by_type:
            self._labels_by_type[marker.type].discard(marker.label)
        if marker.type == "iron_nest" and self._iron_nest_key == coordinate.to_key():
            self._iron_nest_key = None
        return marker

    def find_iron_nest(self) -> Optional[Marker]:
        """查找当前铁巢。"""
        if self._iron_nest_key is None:
            return None
        return self._markers.get(self._iron_nest_key)

    def markers_in_big_cell(self, big_col: str, big_row: int) -> list[Marker]:
        """获取某个大格内的全部标识点。"""
        return list(self._markers_by_big_cell.get((big_col, big_row), []))

    def is_label_taken(self, marker_type: str, label: str) -> bool:
        """检查某类编号是否已被占用。"""
        return label in self._labels_by_type.get(marker_type, set())

    def next_label(self, marker_type: str) -> Optional[str]:
        """分配当前最小未使用编号。"""
        if marker_type in {"observation", "enemy_target"}:
            candidates = NUMBER_LABELS
        elif marker_type == "reference":
            candidates = REFERENCE_LABELS
        else:
            return None

        taken_labels = self._labels_by_type.get(marker_type, set())
        for label in candidates:
            if label not in taken_labels:
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
        self._add_marker(marker)
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

    def _add_marker(self, marker: Marker) -> None:
        """把标识点写入主存储和索引。"""
        coordinate_key = marker.coordinate().to_key()
        self._markers[coordinate_key] = marker
        big_cell_key = (marker.big_col, marker.big_row)
        self._markers_by_big_cell.setdefault(big_cell_key, []).append(marker)
        if marker.type in self._labels_by_type:
            self._labels_by_type[marker.type].add(marker.label)
        if marker.type == "iron_nest":
            self._iron_nest_key = coordinate_key
