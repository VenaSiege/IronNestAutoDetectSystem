"""几何计算与地图坐标换算。"""

from __future__ import annotations

import math
from dataclasses import dataclass

from map_tool.models import BIG_COLS, BIG_ROWS, CellCoordinate, Marker, marker_detail_text

BIG_CELL_KM = 1.0
SMALL_CELL_KM = 0.1
SMALL_CELLS_PER_BIG = 10
MAP_WIDTH_KM = len(BIG_COLS) * BIG_CELL_KM
MAP_HEIGHT_KM = len(BIG_ROWS) * BIG_CELL_KM
MAX_SMALL_COL_INDEX = len(BIG_COLS) * SMALL_CELLS_PER_BIG - 1
MAX_SMALL_ROW_INDEX = len(BIG_ROWS) * SMALL_CELLS_PER_BIG - 1
BIG_COL_INDEX = {col: index for index, col in enumerate(BIG_COLS)}
EPSILON = 1e-9


@dataclass(frozen=True)
class PlanePoint:
    """表示地图上的连续平面点。"""

    x_km: float
    y_km: float


@dataclass(frozen=True)
class CalculationCandidate:
    """表示一次定位计算得到的候选点。"""

    point: PlanePoint
    coordinate: CellCoordinate
    big_label: str
    small_label: str
    distance_to_iron_nest_km: float | None
    bearing_from_iron_nest_deg: float | None

    def summary_text(self) -> str:
        """生成候选点的简要显示文本。"""
        text = (
            f"{self.big_label} / {self.small_label} / "
            f"连续坐标({self.point.x_km:.3f}, {self.point.y_km:.3f})km"
        )
        if self.distance_to_iron_nest_km is not None and self.bearing_from_iron_nest_deg is not None:
            text += (
                f" / 距铁巢{self.distance_to_iron_nest_km:.2f}km"
                f" / 铁巢方位角{self.bearing_from_iron_nest_deg:.1f}°"
            )
        return text


def marker_to_plane_point(marker: Marker) -> PlanePoint:
    """把标识点中心换算为连续平面坐标。"""
    big_col_index = BIG_COL_INDEX[marker.big_col]
    x_km = ((big_col_index * SMALL_CELLS_PER_BIG) + marker.small_x + 0.5) * SMALL_CELL_KM
    y_km = (((marker.big_row - 1) * SMALL_CELLS_PER_BIG) + marker.small_y + 0.5) * SMALL_CELL_KM
    return PlanePoint(x_km=x_km, y_km=y_km)


def point_within_map(point: PlanePoint) -> bool:
    """判断连续坐标是否位于地图范围内。"""
    return (
        0.0 <= point.x_km <= MAP_WIDTH_KM
        and 0.0 <= point.y_km <= MAP_HEIGHT_KM
    )


def plane_point_to_nearest_cell(point: PlanePoint) -> CellCoordinate:
    """把连续平面坐标吸附到最近小格。"""
    small_col_index = round((point.x_km / SMALL_CELL_KM) - 0.5)
    small_row_index = round((point.y_km / SMALL_CELL_KM) - 0.5)

    small_col_index = min(max(small_col_index, 0), MAX_SMALL_COL_INDEX)
    small_row_index = min(max(small_row_index, 0), MAX_SMALL_ROW_INDEX)

    big_col = BIG_COLS[small_col_index // SMALL_CELLS_PER_BIG]
    big_row = (small_row_index // SMALL_CELLS_PER_BIG) + 1
    small_x = small_col_index % SMALL_CELLS_PER_BIG
    small_y = small_row_index % SMALL_CELLS_PER_BIG
    return CellCoordinate(big_col=big_col, big_row=big_row, small_x=small_x, small_y=small_y)


def coordinate_labels(coordinate: CellCoordinate) -> tuple[str, str]:
    """返回大格与小格的显示标签。"""
    return (f"{coordinate.big_col}{coordinate.big_row}", f"{coordinate.small_x}:{coordinate.small_y}")


def distance_km(point_a: PlanePoint, point_b: PlanePoint) -> float:
    """计算两点欧氏距离。"""
    return math.hypot(point_b.x_km - point_a.x_km, point_b.y_km - point_a.y_km)


def bearing_deg(origin: PlanePoint, target: PlanePoint) -> float:
    """计算以正 y 轴为 0° 的顺时针方位角。"""
    dx = target.x_km - origin.x_km
    dy = target.y_km - origin.y_km
    angle = math.degrees(math.atan2(dx, dy))
    if angle < 0:
        angle += 360.0
    return round(angle, 1)


def bearing_direction(theta_deg: float) -> tuple[float, float]:
    """把方位角转换为方向向量。"""
    theta = math.radians(theta_deg)
    return (math.sin(theta), math.cos(theta))


def validate_bearing(theta_deg: float) -> None:
    """校验方位角范围。"""
    if not 0.0 <= theta_deg < 360.0:
        raise ValueError("方位角必须在 0.0 到 360.0 之间。")


def validate_distance(distance_value: float) -> None:
    """校验距离输入。"""
    if distance_value <= 0:
        raise ValueError("距离必须大于 0。")


def intersect_bearings(origin_a: PlanePoint, bearing_a: float, origin_b: PlanePoint, bearing_b: float) -> list[PlanePoint]:
    """计算两条方位角射线的交点。"""
    validate_bearing(bearing_a)
    validate_bearing(bearing_b)
    dx_a, dy_a = bearing_direction(bearing_a)
    dx_b, dy_b = bearing_direction(bearing_b)

    determinant = dx_b * dy_a - dx_a * dy_b
    if abs(determinant) < EPSILON:
        raise ValueError("两条射线平行或近似平行，无法交会。")

    diff_x = origin_b.x_km - origin_a.x_km
    diff_y = origin_b.y_km - origin_a.y_km
    t_a = (diff_x * (-dy_b) + diff_y * dx_b) / determinant
    t_b = (dx_a * diff_y - dy_a * diff_x) / determinant
    if t_a < 0 or t_b < 0:
        raise ValueError("交点位于射线反向延长线上，无法确定有效目标点。")

    return [PlanePoint(origin_a.x_km + dx_a * t_a, origin_a.y_km + dy_a * t_a)]


def intersect_circles(center_a: PlanePoint, radius_a: float, center_b: PlanePoint, radius_b: float) -> list[PlanePoint]:
    """计算两个圆的交点。"""
    validate_distance(radius_a)
    validate_distance(radius_b)

    dx = center_b.x_km - center_a.x_km
    dy = center_b.y_km - center_a.y_km
    center_distance = math.hypot(dx, dy)

    if center_distance < EPSILON and abs(radius_a - radius_b) < EPSILON:
        raise ValueError("两个圆完全重合，无法确定唯一目标点。")
    if center_distance > radius_a + radius_b + EPSILON:
        raise ValueError("两个圆没有交点。")
    if center_distance < abs(radius_a - radius_b) - EPSILON:
        raise ValueError("一个圆被另一个圆包含，无法交会。")
    if center_distance < EPSILON:
        raise ValueError("两个圆圆心重合，无法交会。")

    base_distance = (radius_a**2 - radius_b**2 + center_distance**2) / (2 * center_distance)
    height_square = radius_a**2 - base_distance**2
    if height_square < -EPSILON:
        raise ValueError("两个圆没有交点。")
    height = math.sqrt(max(height_square, 0.0))

    base_x = center_a.x_km + base_distance * dx / center_distance
    base_y = center_a.y_km + base_distance * dy / center_distance

    offset_x = -dy * (height / center_distance)
    offset_y = dx * (height / center_distance)

    first = PlanePoint(base_x + offset_x, base_y + offset_y)
    second = PlanePoint(base_x - offset_x, base_y - offset_y)
    if distance_km(first, second) < EPSILON:
        return [first]
    return [first, second]


def intersect_bearing_circle(origin: PlanePoint, theta_deg: float, center: PlanePoint, radius_km: float) -> list[PlanePoint]:
    """计算射线与圆的交点。"""
    validate_bearing(theta_deg)
    validate_distance(radius_km)
    dx, dy = bearing_direction(theta_deg)
    offset_x = origin.x_km - center.x_km
    offset_y = origin.y_km - center.y_km

    a_value = dx * dx + dy * dy
    b_value = 2 * (offset_x * dx + offset_y * dy)
    c_value = offset_x * offset_x + offset_y * offset_y - radius_km * radius_km
    discriminant = b_value * b_value - 4 * a_value * c_value
    if discriminant < -EPSILON:
        raise ValueError("射线与圆没有交点。")

    sqrt_value = math.sqrt(max(discriminant, 0.0))
    candidates: list[PlanePoint] = []
    for t_value in sorted(((-b_value - sqrt_value) / (2 * a_value), (-b_value + sqrt_value) / (2 * a_value))):
        if t_value < -EPSILON:
            continue
        point = PlanePoint(origin.x_km + dx * t_value, origin.y_km + dy * t_value)
        if not any(distance_km(point, existing) < EPSILON for existing in candidates):
            candidates.append(point)
    if not candidates:
        raise ValueError("交点全部位于射线反向延长线上。")
    return candidates


def project_reference_point(origin: PlanePoint, theta_deg: float, distance_value: float) -> PlanePoint:
    """按原点、方位角和距离投影参考点。"""
    validate_bearing(theta_deg)
    validate_distance(distance_value)
    dx, dy = bearing_direction(theta_deg)
    return PlanePoint(origin.x_km + dx * distance_value, origin.y_km + dy * distance_value)


def marker_choice_text(marker: Marker) -> str:
    """生成下拉选择中的标识文本。"""
    return f"{marker_detail_text(marker)} @ {marker.big_col}{marker.big_row} / {marker.small_x}:{marker.small_y}"


def enemy_marker_relation_text(marker: Marker, iron_nest_marker: Marker | None) -> str:
    """生成敌军目标点相对铁巢的距离和方位角文本。"""
    if marker.type != "enemy_target" or iron_nest_marker is None:
        return ""
    iron_point = marker_to_plane_point(iron_nest_marker)
    marker_point = marker_to_plane_point(marker)
    return (
        f"距铁巢{distance_km(iron_point, marker_point):.2f}km"
        f" / 铁巢方位角{bearing_deg(iron_point, marker_point):.1f}°"
    )
