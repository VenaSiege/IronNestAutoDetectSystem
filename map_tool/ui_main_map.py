"""大地图视图。"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable

from map_tool.models import BIG_COLS, BIG_ROWS, Marker, marker_detail_text, marker_summary_text
from map_tool.state import MapState


class MainMapView(ttk.Frame):
    """绘制大地图网格。"""

    SUMMARY_LIMIT = 4
    MIN_CELL_SIZE = 28
    MAX_CELL_SIZE = 88

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
        self.cell_size = 42
        self.grid_left = 60
        self.grid_top = 60
        self.axis_margin = 30
        self.outer_padding = 16
        self.summary_font_size = 8
        self.axis_font_size = 10
        self.summary_line_height = 10
        self.canvas = tk.Canvas(self, bg="white", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Button-1>", self._handle_left_click)
        self.canvas.bind("<Motion>", self._handle_motion)
        self.canvas.bind("<Leave>", lambda _event: self.on_hover(""))

    def redraw(self) -> None:
        """重绘整个大地图。"""
        self._update_layout_metrics()
        self.canvas.delete("all")
        for col_index, big_col in enumerate(BIG_COLS):
            x = self.grid_left + col_index * self.cell_size
            self.canvas.create_text(
                x + self.cell_size / 2,
                self.grid_top - self.axis_margin / 2,
                text=big_col,
                font=("Microsoft YaHei UI", self.axis_font_size, "bold"),
            )

        for row_index, big_row in enumerate(reversed(BIG_ROWS)):
            y = self.grid_top + row_index * self.cell_size
            self.canvas.create_text(
                self.grid_left - self.axis_margin / 2,
                y + self.cell_size / 2,
                text=str(big_row),
                font=("Microsoft YaHei UI", self.axis_font_size, "bold"),
            )
            for col_index, big_col in enumerate(BIG_COLS):
                x = self.grid_left + col_index * self.cell_size
                self.canvas.create_rectangle(
                    x,
                    y,
                    x + self.cell_size,
                    y + self.cell_size,
                    outline="#666666",
                )
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
        self._update_layout_metrics()
        inner_x = x - self.grid_left
        inner_y = y - self.grid_top
        if inner_x < 0 or inner_y < 0:
            return None
        col_index = inner_x // self.cell_size
        row_index = inner_y // self.cell_size
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
                x + max(4, int(self.cell_size * 0.08)),
                y + max(4, int(self.cell_size * 0.08)) + index * self.summary_line_height,
                text=line,
                anchor="nw",
                fill=color,
                font=("Microsoft YaHei UI", self.summary_font_size, "bold"),
            )

    def _update_layout_metrics(self) -> None:
        """根据当前画布尺寸更新布局参数。"""
        canvas_width = max(self.canvas.winfo_width(), 600)
        canvas_height = max(self.canvas.winfo_height(), 400)
        self.axis_margin = max(28, min(48, int(min(canvas_width, canvas_height) * 0.06)))
        self.outer_padding = max(12, int(self.axis_margin * 0.45))

        available_width = max(200, canvas_width - self.axis_margin - self.outer_padding * 2)
        available_height = max(120, canvas_height - self.axis_margin - self.outer_padding * 2)
        computed_cell = int(
            min(
                available_width / len(BIG_COLS),
                available_height / len(BIG_ROWS),
            )
        )
        self.cell_size = max(self.MIN_CELL_SIZE, min(self.MAX_CELL_SIZE, computed_cell))

        grid_width = self.cell_size * len(BIG_COLS)
        grid_height = self.cell_size * len(BIG_ROWS)
        content_width = grid_width + self.axis_margin
        content_height = grid_height + self.axis_margin

        offset_x = max(self.outer_padding, int((canvas_width - content_width) / 2))
        offset_y = max(self.outer_padding, int((canvas_height - content_height) / 2))
        self.grid_left = offset_x + self.axis_margin
        self.grid_top = offset_y + self.axis_margin

        self.axis_font_size = max(10, min(16, int(self.cell_size * 0.28)))
        self.summary_font_size = max(8, min(14, int(self.cell_size * 0.20)))
        self.summary_line_height = max(self.summary_font_size + 1, int(self.cell_size * 0.21))
