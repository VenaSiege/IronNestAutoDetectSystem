"""小格放大视图。"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable, Optional

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

    CELL_SIZE = 52
    PADDING = 38

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

        toolbar = ttk.Frame(self)
        toolbar.pack(fill="x", pady=(0, 6))
        self.title_var = tk.StringVar(value="")
        ttk.Button(toolbar, text="返回大地图", command=on_back).pack(side="left")
        ttk.Label(toolbar, textvariable=self.title_var).pack(side="left", padx=(12, 0))

        width = self.PADDING * 2 + len(SMALL_RANGE) * self.CELL_SIZE
        height = self.PADDING * 2 + len(SMALL_RANGE) * self.CELL_SIZE
        self.canvas = tk.Canvas(self, width=width, height=height, bg="white", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
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
        self.canvas.delete("all")
        for value in SMALL_RANGE:
            x = self.PADDING + value * self.CELL_SIZE
            self.canvas.create_text(x + self.CELL_SIZE / 2, 18, text=str(value), font=("Microsoft YaHei UI", 10, "bold"))

        for row_index, small_y in enumerate(reversed(SMALL_RANGE)):
            y = self.PADDING + row_index * self.CELL_SIZE
            self.canvas.create_text(18, y + self.CELL_SIZE / 2, text=str(small_y), font=("Microsoft YaHei UI", 10, "bold"))
            for small_x in SMALL_RANGE:
                x = self.PADDING + small_x * self.CELL_SIZE
                self.canvas.create_rectangle(x, y, x + self.CELL_SIZE, y + self.CELL_SIZE, outline="#666666")
                marker = self.state.get_marker(
                    CellCoordinate(
                        big_col=self.current_big_col,
                        big_row=self.current_big_row,
                        small_x=small_x,
                        small_y=small_y,
                    )
                )
                if marker is not None:
                    self._draw_marker(x, y, marker)

    def _draw_marker(self, x: int, y: int, marker: Marker) -> None:
        """在小格中绘制标识点。"""
        style = MARKER_STYLES[marker.type]
        self.canvas.create_oval(
            x + 8,
            y + 8,
            x + self.CELL_SIZE - 8,
            y + self.CELL_SIZE - 8,
            fill=style["fill"],
            outline=style["outline"],
            width=2,
        )
        self.canvas.create_text(
            x + self.CELL_SIZE / 2,
            y + self.CELL_SIZE / 2,
            text=marker_display_text(marker),
            fill=style["text"],
            font=("Microsoft YaHei UI", 11, "bold"),
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
        inner_x = x - self.PADDING
        inner_y = y - self.PADDING
        if inner_x < 0 or inner_y < 0:
            return None
        col_index = inner_x // self.CELL_SIZE
        row_index = inner_y // self.CELL_SIZE
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
