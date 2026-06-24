"""目标定位计算弹窗。"""

from __future__ import annotations

import tkinter as tk
from dataclasses import dataclass
from tkinter import messagebox, ttk
from typing import Callable

from map_tool.geometry import (
    CalculationCandidate,
    PlanePoint,
    bearing_deg,
    coordinate_labels,
    distance_km,
    intersect_bearings,
    intersect_bearing_circle,
    intersect_circles,
    marker_choice_text,
    marker_to_plane_point,
    plane_point_to_nearest_cell,
    point_within_map,
    project_reference_point,
)
from map_tool.models import Marker


@dataclass(frozen=True)
class CalculationSelection:
    """描述一次写回请求。"""

    mode: str
    candidate: CalculationCandidate
    name: str


class CalculationDialog(tk.Toplevel):
    """处理敌军定位和参考点自动计算。"""

    MODES = {
        "triangle": "三角测距",
        "circle": "圆弧交叉测距",
        "mixed": "混合测距",
        "reference": "参考点自动计算",
    }

    def __init__(
        self,
        master: tk.Misc,
        origin_markers: list[Marker],
        observation_markers: list[Marker],
        iron_nest_marker: Marker | None,
        on_apply: Callable[[CalculationSelection], None],
    ) -> None:
        """初始化计算弹窗。"""
        super().__init__(master)
        self.title("目标定位计算")
        self.transient(master)
        self.grab_set()
        self.resizable(False, False)

        self.origin_markers = origin_markers
        self.observation_markers = observation_markers
        self.iron_nest_marker = iron_nest_marker
        self.on_apply = on_apply
        self.candidates: list[CalculationCandidate] = []

        self.mode_var = tk.StringVar(value="triangle")
        self.origin_a_var = tk.StringVar()
        self.origin_b_var = tk.StringVar()
        self.angle_a_var = tk.StringVar()
        self.angle_b_var = tk.StringVar()
        self.distance_a_var = tk.StringVar()
        self.distance_b_var = tk.StringVar()
        self.name_var = tk.StringVar()
        self.result_var = tk.StringVar(value="请先输入参数并点击“计算”。")

        self.origin_choices = {marker_choice_text(marker): marker for marker in origin_markers}
        self.observation_choices = {marker_choice_text(marker): marker for marker in observation_markers}
        self.mode_display_to_key = {label: key for key, label in self.MODES.items()}
        self.mode_key_to_display = dict(self.MODES)

        self._build_layout()
        self._apply_mode_layout()
        self._set_default_choices()

    def _build_layout(self) -> None:
        """构建弹窗布局。"""
        body = ttk.Frame(self, padding=12)
        body.pack(fill="both", expand=True)

        ttk.Label(body, text="计算模式").grid(row=0, column=0, sticky="w", pady=4)
        mode_box = ttk.Combobox(
            body,
            state="readonly",
            values=list(self.mode_display_to_key),
            width=18,
        )
        mode_box.grid(row=0, column=1, sticky="ew", pady=4)
        mode_box.set(self.mode_key_to_display[self.mode_var.get()])
        mode_box.bind("<<ComboboxSelected>>", lambda _event: self._apply_mode_layout())
        self.mode_box = mode_box

        ttk.Label(body, text="原点 1").grid(row=1, column=0, sticky="w", pady=4)
        self.origin_a_box = ttk.Combobox(body, state="readonly", textvariable=self.origin_a_var, width=40)
        self.origin_a_box.grid(row=1, column=1, sticky="ew", pady=4)

        self.origin_b_label = ttk.Label(body, text="原点 2")
        self.origin_b_label.grid(row=2, column=0, sticky="w", pady=4)
        self.origin_b_box = ttk.Combobox(body, state="readonly", textvariable=self.origin_b_var, width=40)
        self.origin_b_box.grid(row=2, column=1, sticky="ew", pady=4)

        self.angle_a_label = ttk.Label(body, text="方位角 1 (°)")
        self.angle_a_label.grid(row=3, column=0, sticky="w", pady=4)
        self.angle_a_entry = ttk.Entry(body, textvariable=self.angle_a_var, width=20)
        self.angle_a_entry.grid(row=3, column=1, sticky="w", pady=4)

        self.angle_b_label = ttk.Label(body, text="方位角 2 (°)")
        self.angle_b_label.grid(row=4, column=0, sticky="w", pady=4)
        self.angle_b_entry = ttk.Entry(body, textvariable=self.angle_b_var, width=20)
        self.angle_b_entry.grid(row=4, column=1, sticky="w", pady=4)

        self.distance_a_label = ttk.Label(body, text="距离 1 (km)")
        self.distance_a_label.grid(row=5, column=0, sticky="w", pady=4)
        self.distance_a_entry = ttk.Entry(body, textvariable=self.distance_a_var, width=20)
        self.distance_a_entry.grid(row=5, column=1, sticky="w", pady=4)

        self.distance_b_label = ttk.Label(body, text="距离 2 (km)")
        self.distance_b_label.grid(row=6, column=0, sticky="w", pady=4)
        self.distance_b_entry = ttk.Entry(body, textvariable=self.distance_b_var, width=20)
        self.distance_b_entry.grid(row=6, column=1, sticky="w", pady=4)

        self.name_label = ttk.Label(body, text="敌军名称")
        self.name_label.grid(row=7, column=0, sticky="w", pady=4)
        self.name_entry = ttk.Entry(body, textvariable=self.name_var, width=24)
        self.name_entry.grid(row=7, column=1, sticky="w", pady=4)

        button_row = ttk.Frame(body)
        button_row.grid(row=8, column=0, columnspan=2, sticky="ew", pady=(8, 6))
        ttk.Button(button_row, text="计算", command=self._calculate).pack(side="left")
        ttk.Button(button_row, text="写入结果", command=self._apply_selected_result).pack(side="left", padx=(8, 0))
        ttk.Button(button_row, text="关闭", command=self.destroy).pack(side="right")

        ttk.Label(body, text="候选结果").grid(row=9, column=0, sticky="nw", pady=(6, 4))
        self.result_list = tk.Listbox(body, height=4, width=70, exportselection=False)
        self.result_list.grid(row=9, column=1, sticky="ew", pady=(6, 4))
        self.result_list.bind("<<ListboxSelect>>", lambda _event: self._update_result_detail())

        ttk.Label(body, text="结果详情").grid(row=10, column=0, sticky="nw", pady=4)
        ttk.Label(body, textvariable=self.result_var, wraplength=520, justify="left").grid(
            row=10,
            column=1,
            sticky="w",
            pady=4,
        )

        body.columnconfigure(1, weight=1)

    def _set_default_choices(self) -> None:
        """设置初始下拉项。"""
        if self.origin_choices:
            first = next(iter(self.origin_choices))
            self.origin_a_var.set(first)
            self.origin_b_var.set(first)
        if len(self.origin_choices) > 1:
            self.origin_b_var.set(list(self.origin_choices)[1])
        if self.observation_choices:
            self.origin_a_var.set(next(iter(self.observation_choices)))

    def _apply_mode_layout(self) -> None:
        """根据模式切换字段可见性与候选列表。"""
        mode = self.mode_display_to_key[self.mode_box.get()]
        self.mode_var.set(mode)
        if mode == "reference":
            self.origin_a_box.configure(values=list(self.observation_choices))
        else:
            self.origin_a_box.configure(values=list(self.origin_choices))
        self.origin_b_box.configure(values=list(self.origin_choices))

        visible = {
            "triangle": {"origin_b": True, "angle_a": True, "angle_b": True, "distance_a": False, "distance_b": False, "name": True},
            "circle": {"origin_b": True, "angle_a": False, "angle_b": False, "distance_a": True, "distance_b": True, "name": True},
            "mixed": {"origin_b": True, "angle_a": True, "angle_b": False, "distance_a": False, "distance_b": True, "name": True},
            "reference": {"origin_b": False, "angle_a": True, "angle_b": False, "distance_a": True, "distance_b": False, "name": False},
        }[mode]

        self._toggle_row(self.origin_b_label, self.origin_b_box, visible["origin_b"])
        self._toggle_row(self.angle_a_label, self.angle_a_entry, visible["angle_a"])
        self._toggle_row(self.angle_b_label, self.angle_b_entry, visible["angle_b"])
        self._toggle_row(self.distance_a_label, self.distance_a_entry, visible["distance_a"])
        self._toggle_row(self.distance_b_label, self.distance_b_entry, visible["distance_b"])
        self._toggle_row(self.name_label, self.name_entry, visible["name"])
        if mode == "reference":
            self.name_var.set("")
        self.result_var.set("请先输入参数并点击“计算”。")
        self.result_list.delete(0, tk.END)
        self.candidates.clear()

    def _toggle_row(self, label_widget: ttk.Label, field_widget: tk.Widget, visible: bool) -> None:
        """显示或隐藏某一输入行。"""
        if visible:
            label_widget.grid()
            field_widget.grid()
        else:
            label_widget.grid_remove()
            field_widget.grid_remove()

    def _calculate(self) -> None:
        """执行定位计算。"""
        try:
            candidates = self._build_candidates()
        except ValueError as error:
            messagebox.showerror("计算失败", str(error), parent=self)
            return

        self.candidates = candidates
        self.result_list.delete(0, tk.END)
        for candidate in candidates:
            self.result_list.insert(tk.END, f"{candidate.big_label} / {candidate.small_label}")

        if candidates:
            self.result_list.selection_set(0)
            self._update_result_detail()

    def _build_candidates(self) -> list[CalculationCandidate]:
        """按当前模式构建候选结果。"""
        mode = self.mode_var.get()
        origin_a = self._get_origin_marker(self.origin_a_var.get(), reference_mode=(mode == "reference"))
        origin_a_point = marker_to_plane_point(origin_a)
        iron_point = None if self.iron_nest_marker is None else marker_to_plane_point(self.iron_nest_marker)
        candidates: list[PlanePoint]

        if mode == "triangle":
            origin_b = self._get_origin_marker(self.origin_b_var.get())
            origin_b_point = marker_to_plane_point(origin_b)
            self._validate_distinct_origins(origin_a, origin_b)
            candidates = intersect_bearings(
                origin_a_point,
                float(self.angle_a_var.get()),
                origin_b_point,
                float(self.angle_b_var.get()),
            )
        elif mode == "circle":
            origin_b = self._get_origin_marker(self.origin_b_var.get())
            origin_b_point = marker_to_plane_point(origin_b)
            self._validate_distinct_origins(origin_a, origin_b)
            candidates = intersect_circles(
                origin_a_point,
                float(self.distance_a_var.get()),
                origin_b_point,
                float(self.distance_b_var.get()),
            )
        elif mode == "mixed":
            origin_b = self._get_origin_marker(self.origin_b_var.get())
            origin_b_point = marker_to_plane_point(origin_b)
            self._validate_distinct_origins(origin_a, origin_b)
            candidates = intersect_bearing_circle(
                origin_a_point,
                float(self.angle_a_var.get()),
                origin_b_point,
                float(self.distance_b_var.get()),
            )
        elif mode == "reference":
            candidates = [
                project_reference_point(
                    origin_a_point,
                    float(self.angle_a_var.get()),
                    float(self.distance_a_var.get()),
                )
            ]
        else:
            raise ValueError("未知计算模式。")

        normalized: list[CalculationCandidate] = []
        for point in candidates:
            if not point_within_map(point):
                continue
            coordinate = plane_point_to_nearest_cell(point)
            big_label, small_label = coordinate_labels(coordinate)
            distance_value = None
            bearing_value = None
            if iron_point is not None and mode != "reference":
                distance_value = distance_km(iron_point, point)
                bearing_value = bearing_deg(iron_point, point)
            normalized.append(
                CalculationCandidate(
                    point=point,
                    coordinate=coordinate,
                    big_label=big_label,
                    small_label=small_label,
                    distance_to_iron_nest_km=None if distance_value is None else round(distance_value, 2),
                    bearing_from_iron_nest_deg=bearing_value,
                )
            )
        if not normalized:
            raise ValueError("计算结果全部落在地图范围外，无法写入。")
        return normalized

    def _get_origin_marker(self, choice_text: str, reference_mode: bool = False) -> Marker:
        """从下拉文本中取回标识点。"""
        source = self.observation_choices if reference_mode else self.origin_choices
        marker = source.get(choice_text)
        if marker is None:
            raise ValueError("请选择有效原点。")
        return marker

    def _validate_distinct_origins(self, origin_a: Marker, origin_b: Marker) -> None:
        """校验两个原点不相同。"""
        if origin_a.coordinate() == origin_b.coordinate() and origin_a.type == origin_b.type and origin_a.label == origin_b.label:
            raise ValueError("两个原点不能相同。")

    def _update_result_detail(self) -> None:
        """刷新当前选中候选点的详情。"""
        selection = self.result_list.curselection()
        if not selection:
            self.result_var.set("请先输入参数并点击“计算”。")
            return
        self.result_var.set(self.candidates[selection[0]].summary_text())

    def _apply_selected_result(self) -> None:
        """把当前选中结果写回地图。"""
        selection = self.result_list.curselection()
        if not selection:
            messagebox.showinfo("写入结果", "请先计算并选择一个候选点。", parent=self)
            return
        mode = self.mode_var.get()
        if mode != "reference" and not self.name_var.get().strip():
            messagebox.showinfo("写入结果", "请输入敌军目标点名称。", parent=self)
            return
        self.on_apply(
            CalculationSelection(
                mode=mode,
                candidate=self.candidates[selection[0]],
                name=self.name_var.get().strip(),
            )
        )
        self.destroy()
