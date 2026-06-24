"""小格放大视图。"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable, Optional

from map_tool.geometry import enemy_marker_relation_text
from map_tool.models import SMALL_RANGE, CellCoordinate, Marker, marker_display_text
from map_tool.state import MapState

MARKER_STYLES = {
    "iron_nest": {"fill": "#d1242f", "outline": "#911b23", "text": "white"},
    "observation": {"fill": "#1f6feb", "outline": "#0d419d", "text": "white"},
    "reference": {"fill": "#2da44e", "outline": "#1a7f37", "text": "white"},
    "enemy_target": {"fill": "#f0883e", "outline": "#9a4d00", "text": "white"},
}


class ZoomMapView(ttk.Frame):
    """绘制大格放大后的小格地图。"""

    FIXED_CELL_SIZE = 68
    FIXED_AXIS_MARGIN = 44
    FIXED_OUTER_PADDING = 20

    def __init__(
        self,
        master: tk.Misc,
        state: MapState,
        on_hover: Callable[[str], None],
        on_place_request: Callable[[CellCoordinate, Optional[Marker], str], None],
        on_clear_request: Callable[[CellCoordinate, Optional[Marker]], None],
        on_back: Callable[[], None],
    ) -> None:
        """初始化放大视图。"""
        super().__init__(master)
        self.state = state
        self.on_hover = on_hover
        self.on_place_request = on_place_request
        self.on_clear_request = on_clear_request
        self.current_big_col = "A"
        self.current_big_row = 1
        self.cell_size = self.FIXED_CELL_SIZE
        self.grid_left = 60
        self.grid_top = 60
        self.axis_margin = self.FIXED_AXIS_MARGIN
        self.outer_padding = self.FIXED_OUTER_PADDING
        self.axis_font_size = 13
        self.marker_font_size = 16
        self._redraw_after_id: Optional[str] = None

        toolbar = ttk.Frame(self)
        toolbar.pack(fill="x", pady=(0, 6))
        self.title_var = tk.StringVar(value="")
        ttk.Button(toolbar, text="返回大地图", command=on_back).pack(side="left")
        ttk.Label(toolbar, textvariable=self.title_var).pack(side="left", padx=(12, 0))

        self.canvas = tk.Canvas(self, bg="white", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Configure>", self._schedule_redraw)
        self.canvas.bind("<Button-3>", self._show_menu)
        self.canvas.bind("<Motion>", self._handle_motion)
        self.canvas.bind("<Leave>", lambda _event: self.on_hover(""))

        self.menu = tk.Menu(self, tearoff=False)
        self.menu.add_command(label="放置铁巢", command=lambda: self._trigger_place("iron_nest"))
        self.menu.add_command(label="放置观测点", command=lambda: self._trigger_place("observation"))
        self.menu.add_command(label="放置参考点", command=lambda: self._trigger_place("reference"))
        self.menu.add_command(label="放置敌军目标点", command=lambda: self._trigger_place("enemy_target"))
        self.menu.add_separator()
        self.menu.add_command(label="清除当前小格标识", command=self._trigger_clear)

        self._menu_coordinate: Optional[CellCoordinate] = None

    def set_big_cell(self, big_col: str, big_row: int) -> None:
        """切换当前放大的大格。"""
        self.current_big_col = big_col
        self.current_big_row = big_row
        self.title_var.set(f"{big_col}{big_row} 大格 - 小格视图")
        self.redraw()

    def redraw(self) -> None:
        """重绘当前大格的小格视图。"""
        self._redraw_after_id = None
        self._update_layout_metrics()
        local_markers = {
            (marker.small_x, marker.small_y): marker
            for marker in self.state.markers_in_big_cell(self.current_big_col, self.current_big_row)
        }
        self.canvas.delete("all")
        for value in SMALL_RANGE:
            x = self.grid_left + value * self.cell_size
            self.canvas.create_text(
                x + self.cell_size / 2,
                self.grid_top - self.axis_margin / 2,
                text=str(value),
                font=("Microsoft YaHei UI", self.axis_font_size, "bold"),
            )

        for row_index, small_y in enumerate(reversed(SMALL_RANGE)):
            y = self.grid_top + row_index * self.cell_size
            self.canvas.create_text(
                self.grid_left - self.axis_margin / 2,
                y + self.cell_size / 2,
                text=str(small_y),
                font=("Microsoft YaHei UI", self.axis_font_size, "bold"),
            )
            for small_x in SMALL_RANGE:
                x = self.grid_left + small_x * self.cell_size
                self.canvas.create_rectangle(
                    x,
                    y,
                    x + self.cell_size,
                    y + self.cell_size,
                    outline="#666666",
                )
                marker = local_markers.get((small_x, small_y))
                if marker is not None:
                    self._draw_marker(x, y, marker)

    def _draw_marker(self, x: int, y: int, marker: Marker) -> None:
        """在小格中绘制标识点。"""
        style = MARKER_STYLES[marker.type]
        marker_margin = max(8, int(self.cell_size * 0.15))
        marker_outline_width = max(2, int(self.cell_size * 0.04))
        self.canvas.create_oval(
            x + marker_margin,
            y + marker_margin,
            x + self.cell_size - marker_margin,
            y + self.cell_size - marker_margin,
            fill=style["fill"],
            outline=style["outline"],
            width=marker_outline_width,
        )
        self.canvas.create_text(
            x + self.cell_size / 2,
            y + self.cell_size / 2,
            text=marker_display_text(marker),
            fill=style["text"],
            font=("Microsoft YaHei UI", self.marker_font_size, "bold"),
        )

    def _show_menu(self, event: tk.Event) -> None:
        """在右键位置弹出操作菜单。"""
        coordinate = self._locate_small_cell(event.x, event.y)
        if coordinate is None:
            return
        self._menu_coordinate = coordinate
        self.menu.tk_popup(event.x_root, event.y_root)

    def _handle_motion(self, event: tk.Event) -> None:
        """更新当前鼠标对应的小格信息。"""
        coordinate = self._locate_small_cell(event.x, event.y)
        if coordinate is None:
            self.on_hover("")
            return
        marker = self.state.get_marker(coordinate)
        marker_text = ""
        if marker is not None:
            marker_text = f" / {marker_display_text(marker)}"
            if marker.type == "enemy_target" and marker.name:
                marker_text += f"({marker.name})"
            relation_text = enemy_marker_relation_text(marker, self.state.find_iron_nest())
            if relation_text:
                marker_text += f" / {relation_text}"
        self.on_hover(
            f"{coordinate.big_col}{coordinate.big_row} / {coordinate.small_x}:{coordinate.small_y}{marker_text}"
        )

    def _trigger_place(self, marker_type: str) -> None:
        """把菜单操作转发给上层控制器。"""
        if self._menu_coordinate is None:
            return
        existing = self.state.get_marker(self._menu_coordinate)
        self.on_place_request(self._menu_coordinate, existing, marker_type)

    def _trigger_clear(self) -> None:
        """把清除操作转发给上层控制器。"""
        if self._menu_coordinate is None:
            return
        existing = self.state.get_marker(self._menu_coordinate)
        self.on_clear_request(self._menu_coordinate, existing)

    def _locate_small_cell(self, x: int, y: int) -> CellCoordinate | None:
        """将画布坐标转换为小格坐标。"""
        self._update_layout_metrics()
        inner_x = x - self.grid_left
        inner_y = y - self.grid_top
        if inner_x < 0 or inner_y < 0:
            return None
        col_index = inner_x // self.cell_size
        row_index = inner_y // self.cell_size
        if col_index >= len(SMALL_RANGE) or row_index >= len(SMALL_RANGE):
            return None
        small_x = int(col_index)
        small_y = list(reversed(SMALL_RANGE))[int(row_index)]
        return CellCoordinate(
            big_col=self.current_big_col,
            big_row=self.current_big_row,
            small_x=small_x,
            small_y=small_y,
        )

    def _update_layout_metrics(self) -> None:
        """使用固定尺寸更新小格视图布局。"""
        canvas_width = max(self.canvas.winfo_width(), 420)
        canvas_height = max(self.canvas.winfo_height(), 420)
        self.cell_size = self.FIXED_CELL_SIZE
        self.axis_margin = self.FIXED_AXIS_MARGIN
        self.outer_padding = self.FIXED_OUTER_PADDING
        grid_width = self.cell_size * len(SMALL_RANGE)
        grid_height = self.cell_size * len(SMALL_RANGE)
        content_width = grid_width + self.axis_margin
        content_height = grid_height + self.axis_margin

        offset_x = max(self.outer_padding, int((canvas_width - content_width) / 2))
        offset_y = max(self.outer_padding, int((canvas_height - content_height) / 2))
        self.grid_left = offset_x + self.axis_margin
        self.grid_top = offset_y + self.axis_margin

        self.axis_font_size = 13
        self.marker_font_size = 16

    def _schedule_redraw(self, _event: tk.Event) -> None:
        """在画布尺寸稳定后补一次重绘。"""
        if not self.winfo_ismapped():
            return
        if self._redraw_after_id is not None:
            self.after_cancel(self._redraw_after_id)
        self._redraw_after_id = self.after(10, self.redraw)
