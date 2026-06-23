"""大地图视图。"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable

from map_tool.models import BIG_COLS, BIG_ROWS, Marker, marker_detail_text, marker_summary_text
from map_tool.state import MapState


class MainMapView(ttk.Frame):
    """绘制大地图网格。"""

    CELL_SIZE = 42
    PADDING = 36
    SUMMARY_LIMIT = 4

    def __init__(
        self,
        master: tk.Misc,
        state: MapState,
        on_open_zoom: Callable[[str, int], None],
        on_hover: Callable[[str], None],
    ) -> None:
        """初始化大地图视图。"""
        super().__init__(master)
        self.state = state
        self.on_open_zoom = on_open_zoom
        self.on_hover = on_hover

        width = self.PADDING * 2 + len(BIG_COLS) * self.CELL_SIZE
        height = self.PADDING * 2 + len(BIG_ROWS) * self.CELL_SIZE
        self.canvas = tk.Canvas(self, width=width, height=height, bg="white", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Button-1>", self._handle_left_click)
        self.canvas.bind("<Motion>", self._handle_motion)
        self.canvas.bind("<Leave>", lambda _event: self.on_hover(""))

    def redraw(self) -> None:
        """重绘整个大地图。"""
        self.canvas.delete("all")
        for col_index, big_col in enumerate(BIG_COLS):
            x = self.PADDING + col_index * self.CELL_SIZE
            self.canvas.create_text(x + self.CELL_SIZE / 2, 18, text=big_col, font=("Microsoft YaHei UI", 10, "bold"))

        for row_index, big_row in enumerate(reversed(BIG_ROWS)):
            y = self.PADDING + row_index * self.CELL_SIZE
            self.canvas.create_text(18, y + self.CELL_SIZE / 2, text=str(big_row), font=("Microsoft YaHei UI", 10, "bold"))
            for col_index, big_col in enumerate(BIG_COLS):
                x = self.PADDING + col_index * self.CELL_SIZE
                self.canvas.create_rectangle(x, y, x + self.CELL_SIZE, y + self.CELL_SIZE, outline="#666666")
                markers = self._sorted_markers(self.state.markers_in_big_cell(big_col, big_row))
                if markers:
                    self._draw_big_cell_summary(x, y, markers)

    def _handle_left_click(self, event: tk.Event) -> None:
        """点击大格后进入放大视图。"""
        result = self._locate_big_cell(event.x, event.y)
        if result is None:
            return
        self.on_open_zoom(*result)

    def _handle_motion(self, event: tk.Event) -> None:
        """更新鼠标悬停信息。"""
        result = self._locate_big_cell(event.x, event.y)
        if result is None:
            self.on_hover("")
            return
        big_col, big_row = result
        markers = self._sorted_markers(self.state.markers_in_big_cell(big_col, big_row))
        if not markers:
            self.on_hover(f"{big_col}{big_row}")
            return
        details = " / ".join(marker_detail_text(marker) for marker in markers)
        self.on_hover(f"{big_col}{big_row} / {details}")

    def _locate_big_cell(self, x: int, y: int) -> tuple[str, int] | None:
        """将画布坐标转换为大格坐标。"""
        inner_x = x - self.PADDING
        inner_y = y - self.PADDING
        if inner_x < 0 or inner_y < 0:
            return None
        col_index = inner_x // self.CELL_SIZE
        row_index = inner_y // self.CELL_SIZE
        if col_index >= len(BIG_COLS) or row_index >= len(BIG_ROWS):
            return None
        big_col = BIG_COLS[int(col_index)]
        big_row = list(reversed(BIG_ROWS))[int(row_index)]
        return (big_col, big_row)

    def _sorted_markers(self, markers: list[Marker]) -> list[Marker]:
        """按固定顺序整理大格内标识。"""
        type_order = {
            "iron_nest": 0,
            "observation": 1,
            "reference": 2,
            "enemy_target": 3,
        }
        return sorted(
            markers,
            key=lambda marker: (
                type_order.get(marker.type, 99),
                marker.label,
                marker.small_y,
                marker.small_x,
            ),
        )

    def _draw_big_cell_summary(self, x: int, y: int, markers: list[Marker]) -> None:
        """在大格内部绘制标识摘要。"""
        visible_markers = markers[: self.SUMMARY_LIMIT]
        if len(markers) > self.SUMMARY_LIMIT:
            visible_markers = markers[: self.SUMMARY_LIMIT - 1]

        lines = [marker_summary_text(marker) for marker in visible_markers]
        if len(markers) > self.SUMMARY_LIMIT:
            lines.append(f"+{len(markers) - len(visible_markers)}")

        color_map = {
            "iron_nest": "#d1242f",
            "observation": "#1f6feb",
            "reference": "#2da44e",
            "enemy_target": "#f0883e",
        }

        for index, line in enumerate(lines):
            color = "#222222"
            if index < len(visible_markers):
                color = color_map.get(visible_markers[index].type, "#222222")
            self.canvas.create_text(
                x + 4,
                y + 4 + index * 9,
                text=line,
                anchor="nw",
                fill=color,
                font=("Microsoft YaHei UI", 7, "bold"),
            )
