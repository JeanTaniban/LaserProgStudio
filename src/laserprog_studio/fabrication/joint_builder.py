# -*- coding: utf-8 -*-
"""Stable wrapper for the joint_builder tool UI.

The computational core lives in `joint_builder_core.py`; this module keeps the
public imports used by LaserProg Studio and the toolbox.
"""
from __future__ import annotations

from .joint_builder_core import *  # type: ignore  # noqa: F401,F403


class ToolFrame(ttk.Frame):
    def __init__(self, parent: tk.Widget, app_context) -> None:
        super().__init__(parent)
        self.context = app_context
        self.settings = AutoSaveSettings(self.context.settings_dir / f"{TOOL_ID}.json", DEFAULT_SETTINGS)
        self._save_after_id: str | None = None
        self.vars: dict[str, tk.Variable] = {}

        self._build_ui()
        self._load_vars_from_settings()
        self._connect_autosave()

        self.context.model_store.subscribe(self._sync_selection_labels)
        self._sync_selection_labels()

    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=1)

        ttk.Label(self, text="Joint builder (prototype)", font=("Segoe UI", 14, "bold")).grid(
            row=0, column=0, sticky="w", pady=(0, 10)
        )

        self.selection_label = ttk.Label(self, text="", foreground="#444", justify="left")
        self.selection_label.grid(row=1, column=0, sticky="ew", pady=(0, 8))

        self.vars = {
            "method": tk.StringVar(),
            "touch_tolerance_mm": tk.StringVar(),
            "clearance_mm": tk.StringVar(),
            "joint_size_mm": tk.StringVar(),
            "joint_count": tk.StringVar(),
            "joint_edge_margin_mm": tk.StringVar(),
            "single_depth_probe": tk.BooleanVar(),
            "debug_log": tk.BooleanVar(),
        }

        row = 2
        ttk.Label(self, text="Method").grid(row=row, column=0, sticky="w")
        row += 1
        ttk.Combobox(self, textvariable=self.vars["method"], state="readonly", values=list(METHOD_LABELS.values())).grid(
            row=row, column=0, sticky="ew", pady=(0, 8)
        )
        row += 1

        row = self._add_float("Contact tolerance", "touch_tolerance_mm", row)
        row = self._add_float("Joint clearance", "clearance_mm", row)
        row = self._add_float("Joint size", "joint_size_mm", row)
        row = self._add_int("Joint count", "joint_count", row)
        row = self._add_float("Edge margin", "joint_edge_margin_mm", row)
        one_probe = ttk.Checkbutton(
            self,
            text="Compute depth once (fast)",
            variable=self.vars["single_depth_probe"],
        )
        one_probe.grid(row=row, column=0, sticky="w", pady=(0, 6))
        row += 1
        dbg = ttk.Checkbutton(self, text="Enable debug log (joint_builder_debug.log)", variable=self.vars["debug_log"])
        dbg.grid(row=row, column=0, sticky="w", pady=(0, 6))
        row += 1

        self.preview_btn = ttk.Button(self, text="Generate joint (preview)", command=self._generate_preview)
        self.preview_btn.grid(row=row, column=0, sticky="ew", pady=(10, 0))
        row += 1

        ttk.Label(
            self,
            text="Tip: click 2 boards in the view (A then B). Click again to remove.",
            foreground="#555",
            wraplength=380,
        ).grid(row=row, column=0, sticky="ew", pady=(10, 0))

    def _add_float(self, label: str, key: str, row: int) -> int:
        line = ttk.Frame(self)
        line.grid(row=row, column=0, sticky="ew", pady=3)
        line.columnconfigure(1, weight=1)
        ttk.Label(line, text=label).grid(row=0, column=0, sticky="w", padx=(0, 10))
        ttk.Entry(line, textvariable=self.vars[key], width=10).grid(row=0, column=1, sticky="w")
        ttk.Label(line, text="mm", foreground="#555").grid(row=0, column=2, sticky="w", padx=(6, 0))
        return row + 1

    def _add_int(self, label: str, key: str, row: int) -> int:
        line = ttk.Frame(self)
        line.grid(row=row, column=0, sticky="ew", pady=3)
        line.columnconfigure(1, weight=1)
        ttk.Label(line, text=label).grid(row=0, column=0, sticky="w", padx=(0, 10))
        ttk.Entry(line, textvariable=self.vars[key], width=10).grid(row=0, column=1, sticky="w")
        return row + 1

    def _load_vars_from_settings(self) -> None:
        method = str(self.settings.data.get("method", DEFAULT_SETTINGS["method"]))
        self.vars["method"].set(METHOD_LABELS.get(method, list(METHOD_LABELS.values())[0]))
        self.vars["touch_tolerance_mm"].set(str(self.settings.data.get("touch_tolerance_mm", DEFAULT_SETTINGS["touch_tolerance_mm"])))
        self.vars["clearance_mm"].set(str(self.settings.data.get("clearance_mm", DEFAULT_SETTINGS["clearance_mm"])))
        self.vars["joint_size_mm"].set(str(self.settings.data.get("joint_size_mm", DEFAULT_SETTINGS["joint_size_mm"])))
        self.vars["joint_count"].set(str(self.settings.data.get("joint_count", DEFAULT_SETTINGS["joint_count"])))
        self.vars["joint_edge_margin_mm"].set(str(self.settings.data.get("joint_edge_margin_mm", DEFAULT_SETTINGS["joint_edge_margin_mm"])))
        self.vars["single_depth_probe"].set(bool(self.settings.data.get("single_depth_probe", DEFAULT_SETTINGS["single_depth_probe"])))
        self.vars["debug_log"].set(bool(self.settings.data.get("debug_log", DEFAULT_SETTINGS["debug_log"])))

    def _connect_autosave(self) -> None:
        for var in self.vars.values():
            var.trace_add("write", self._schedule_save)

    def _schedule_save(self, *_args) -> None:
        if self._save_after_id is not None:
            self.after_cancel(self._save_after_id)
        self._save_after_id = self.after(250, self._save_now)

    def _save_now(self) -> None:
        self._save_after_id = None
        try:
            self.settings.data["method"] = self._method_code()
            self.settings.data["touch_tolerance_mm"] = float(self.vars["touch_tolerance_mm"].get().strip().replace(",", "."))
            self.settings.data["clearance_mm"] = float(self.vars["clearance_mm"].get().strip().replace(",", "."))
            self.settings.data["joint_size_mm"] = float(self.vars["joint_size_mm"].get().strip().replace(",", "."))
            self.settings.data["joint_count"] = int(float(self.vars["joint_count"].get().strip().replace(",", ".")))
            self.settings.data["joint_edge_margin_mm"] = float(self.vars["joint_edge_margin_mm"].get().strip().replace(",", "."))
            self.settings.data["single_depth_probe"] = bool(self.vars["single_depth_probe"].get())
            self.settings.data["debug_log"] = bool(self.vars["debug_log"].get())
            self.settings.save()
        except Exception:
            pass

    def _method_code(self) -> str:
        raw = self.vars["method"].get().strip()
        for k, v in METHOD_LABELS.items():
            if raw == v:
                return k
        return "tab_slot_simple"

    def _sync_selection_labels(self) -> None:
        a, b = self.context.model_store.selected_pair
        meshes = self.context.model_store.meshes

        def name(i: int | None) -> str:
            if i is None:
                return "(none)"
            if 0 <= i < len(meshes):
                return f"{i+1}. {meshes[i].name}"
            return f"{i+1}. (invalid)"

        self.selection_label.configure(text=f"Selection:\nA = {name(a)}\nB = {name(b)}")
        self.preview_btn.configure(state=("normal" if a is not None and b is not None else "disabled"))

    def _generate_preview(self) -> None:
        try:
            base_meshes = self.context.model_store.meshes
            a, b = self.context.model_store.selected_pair
            if a is None or b is None:
                raise ValueError("Select 2 boards (A and B) in the 3D view.")

            touch_tol = float(self.vars["touch_tolerance_mm"].get().strip().replace(",", "."))
            clearance = float(self.vars["clearance_mm"].get().strip().replace(",", "."))
            joint_size = float(self.vars["joint_size_mm"].get().strip().replace(",", "."))
            joint_count = int(float(self.vars["joint_count"].get().strip().replace(",", ".")))
            joint_edge_margin = float(self.vars["joint_edge_margin_mm"].get().strip().replace(",", "."))
            single_depth_probe = bool(self.vars["single_depth_probe"].get())
            debug_enabled = bool(self.vars["debug_log"].get())
            try:
                from laserprog_studio.services.debug_mode import is_debug_mode_enabled
                debug_enabled = bool(debug_enabled and is_debug_mode_enabled())
            except Exception:
                debug_enabled = False

            if touch_tol <= 0 or joint_size <= 0 or joint_count <= 0 or joint_edge_margin < 0:
                raise ValueError("Invalid tolerance/size/count/edge margin.")
            if joint_size + 2.0 * clearance < 0.2:
                raise ValueError("Clearance is too negative: the female slot would become smaller than 0.2 mm.")

            debug_cb = None
            if debug_enabled:
                log_path = self.context.settings_dir / f"{TOOL_ID}_debug.log"

                def _dbg(tag: str, payload: dict) -> None:
                    record = {
                        "ts": datetime.now().isoformat(timespec="seconds"),
                        "tag": tag,
                        "tool": TOOL_ID,
                        "a": self.context.model_store.selected_pair[0],
                        "b": self.context.model_store.selected_pair[1],
                        "payload": payload,
                    }
                    log_path.parent.mkdir(parents=True, exist_ok=True)
                    with log_path.open("a", encoding="utf-8") as f:
                        f.write(json.dumps(record, ensure_ascii=False) + "\n")

                debug_cb = _dbg
                try:
                    debug_cb(
                        "start",
                        {
                            "touch_tol": float(touch_tol),
                            "clearance": float(clearance),
                            "joint_size": float(joint_size),
                            "joint_count": int(joint_count),
                            "joint_edge_margin": float(joint_edge_margin),
                            "single_depth_probe": bool(single_depth_probe),
                            "log_path": str(log_path),
                            "debug_log_version": int(DEBUG_LOG_VERSION),
                        },
                    )
                except Exception as log_exc:
                    messagebox.showwarning("Joint builder", f"Cannot write debug log:\n{log_exc}")
                    debug_cb = None

            mesh_a2, mesh_b2 = apply_tab_slot_simple(
                base_meshes[a],
                base_meshes[b],
                touch_tolerance=touch_tol,
                clearance=clearance,
                joint_size=joint_size,
                joint_count=joint_count,
                joint_edge_margin=joint_edge_margin,
                single_depth_probe=single_depth_probe,
                debug=debug_cb,
            )

            out = list(base_meshes)
            out[a] = mesh_a2
            out[b] = mesh_b2
            self.context.model_store.set_preview_meshes(out, source_path=self.context.model_store.source_path)
            if debug_cb is not None:
                try:
                    debug_cb("done", {"status": "ok"})
                except Exception:
                    pass
        except Exception as exc:
            try:
                if "debug_cb" in locals() and debug_cb is not None:
                    debug_cb("error", {"error": str(exc)})
            except Exception:
                pass
            messagebox.showerror("Joint builder", str(exc))

