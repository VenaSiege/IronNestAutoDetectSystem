"""应用控制器与主窗口。"""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import font
from tkinter import filedialog, messagebox, simpledialog, ttk
from typing import Optional

from map_tool.models import CellCoordinate, Marker
from map_tool.state import MapState
from map_tool.storage import load_markers, save_markers
from map_tool.ui_main_map import MainMapView
from map_tool.ui_zoom_map import ZoomMapView


class MapToolApp:
    """协调界面、状态和文件操作。"""

    def __init__(self) -> None:
        """初始化主窗口和全部视图。"""
        self.root = tk.Tk()
        self.root.title("铁巢自动化侦察系统")
        self.root.geometry("980x720")
        default_font = font.nametofont("TkDefaultFont")
        default_font.configure(family="Microsoft YaHei UI", size=10)
        text_font = font.nametofont("TkTextFont")
        text_font.configure(family="Microsoft YaHei UI", size=10)
        menu_font = font.nametofont("TkMenuFont")
        menu_font.configure(family="Microsoft YaHei UI", size=10)

        self.state = MapState()
        self.current_file_path: Optional[str] = None

        self.status_var = tk.StringVar(value="就绪")
        self.view_mode = "main"

        self._build_menu()
        self._build_layout()
        self.show_main_map()

    def run(self) -> None:
        """启动 Tkinter 主循环。"""
        self.root.mainloop()

    def _build_menu(self) -> None:
        """创建菜单栏。"""
        menu_bar = tk.Menu(self.root)
        file_menu = tk.Menu(menu_bar, tearoff=False)
        file_menu.add_command(label="新建", command=self.new_map)
        file_menu.add_command(label="打开", command=self.open_map)
        file_menu.add_command(label="保存", command=self.save_map)
        file_menu.add_command(label="另存为", command=self.save_map_as)
        menu_bar.add_cascade(label="文件", menu=file_menu)
        self.root.config(menu=menu_bar)

    def _build_layout(self) -> None:
        """创建主布局和视图容器。"""
        self.container = ttk.Frame(self.root, padding=12)
        self.container.pack(fill="both", expand=True)

        self.main_map_view = MainMapView(
            self.container,
            state=self.state,
            on_open_zoom=self.open_zoom_map,
            on_hover=self.set_status,
        )
        self.zoom_map_view = ZoomMapView(
            self.container,
            state=self.state,
            on_hover=self.set_status,
            on_place_request=self.handle_place_request,
            on_clear_request=self.handle_clear_request,
            on_back=self.show_main_map,
        )

        status_bar = ttk.Label(self.root, textvariable=self.status_var, anchor="w", relief="sunken")
        status_bar.pack(fill="x", side="bottom")

    def set_status(self, text: str) -> None:
        """更新状态栏文本。"""
        self.status_var.set(text or "就绪")

    def show_main_map(self) -> None:
        """切换回大地图视图。"""
        self.view_mode = "main"
        self.zoom_map_view.pack_forget()
        self.main_map_view.pack(fill="both", expand=True)
        self.main_map_view.redraw()
        self.root.title("铁巢自动化侦察系统")
        self.set_status("大地图视图")

    def open_zoom_map(self, big_col: str, big_row: int) -> None:
        """进入某个大格的放大视图。"""
        self.view_mode = "zoom"
        self.main_map_view.pack_forget()
        self.zoom_map_view.pack(fill="both", expand=True)
        self.zoom_map_view.set_big_cell(big_col, big_row)
        self.root.title(f"铁巢自动化侦察系统 - {big_col}{big_row}")
        self.set_status(f"{big_col}{big_row}")

    def refresh_views(self) -> None:
        """按当前模式刷新界面。"""
        self.main_map_view.redraw()
        self.zoom_map_view.redraw()

    def handle_place_request(
        self,
        coordinate: CellCoordinate,
        existing: Optional[Marker],
        marker_type: str,
    ) -> None:
        """处理来自右键菜单的放置请求。"""
        if existing is not None:
            confirm = messagebox.askyesno(
                "覆盖确认",
                f"当前小格已有标识“{existing.label if existing.type != 'iron_nest' else '铁巢'}”，是否覆盖？",
                parent=self.root,
            )
            if not confirm:
                return

        name = ""
        if marker_type == "enemy_target":
            name = simpledialog.askstring("敌军目标点", "请输入敌军目标点名称：", parent=self.root) or ""
            if not name.strip():
                messagebox.showinfo("操作取消", "敌军目标点名称不能为空。", parent=self.root)
                return
            name = name.strip()

        try:
            result = self.state.place_marker(marker_type, coordinate, name=name)
        except ValueError as error:
            messagebox.showerror("放置失败", str(error), parent=self.root)
            return

        self.refresh_views()
        if result.removed_iron_nest is not None:
            self.set_status(f"铁巢已移动到 {coordinate.big_col}{coordinate.big_row} / {coordinate.small_x}:{coordinate.small_y}")
        else:
            self.set_status(f"已放置 {self._marker_type_name(marker_type)}")

    def handle_clear_request(self, coordinate: CellCoordinate, existing: Optional[Marker]) -> None:
        """处理清除当前小格标识的请求。"""
        if existing is None:
            messagebox.showinfo("清除标识", "当前小格没有标识可清除。", parent=self.root)
            return
        self.state.remove_marker(coordinate)
        self.refresh_views()
        self.set_status(f"已清除 {coordinate.big_col}{coordinate.big_row} / {coordinate.small_x}:{coordinate.small_y}")

    def new_map(self) -> None:
        """新建空地图。"""
        self.state.clear()
        self.current_file_path = None
        self.refresh_views()
        self.show_main_map()
        self.set_status("已新建空地图")

    def open_map(self) -> None:
        """打开并加载 JSON 地图文件。"""
        file_path = filedialog.askopenfilename(
            parent=self.root,
            title="打开地图文件",
            filetypes=[("JSON 文件", "*.json")],
        )
        if not file_path:
            return

        try:
            markers = load_markers(file_path)
            self.state.set_markers(markers)
        except Exception as error:
            messagebox.showerror("打开失败", f"无法加载文件：{error}", parent=self.root)
            return

        self.current_file_path = file_path
        self.refresh_views()
        if self.view_mode == "main":
            self.show_main_map()
        else:
            self.zoom_map_view.redraw()
        self.set_status(f"已打开 {Path(file_path).name}")

    def save_map(self) -> None:
        """保存到当前文件，若不存在则转为另存为。"""
        if not self.current_file_path:
            self.save_map_as()
            return
        self._save_to_path(self.current_file_path)

    def save_map_as(self) -> None:
        """选择新路径进行保存。"""
        file_path = filedialog.asksaveasfilename(
            parent=self.root,
            title="另存为",
            defaultextension=".json",
            filetypes=[("JSON 文件", "*.json")],
        )
        if not file_path:
            return
        self._save_to_path(file_path)

    def _save_to_path(self, file_path: str) -> None:
        """把当前状态保存到指定路径。"""
        try:
            save_markers(file_path, self.state.all_markers())
        except Exception as error:
            messagebox.showerror("保存失败", f"无法保存文件：{error}", parent=self.root)
            return

        self.current_file_path = file_path
        self.set_status(f"已保存到 {Path(file_path).name}")

    def _marker_type_name(self, marker_type: str) -> str:
        """返回中文标识类型名。"""
        names = {
            "iron_nest": "铁巢",
            "observation": "观测点",
            "reference": "参考点",
            "enemy_target": "敌军目标点",
        }
        return names.get(marker_type, marker_type)
