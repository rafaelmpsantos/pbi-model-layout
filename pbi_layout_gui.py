#!/usr/bin/env python3
"""
pbi-model-layout GUI v1.2
-------------------------
Graphical interface for the pbi-model-layout tool.
v1.2: Power BI Model View visualization
  - Relationship fields inside containers
  - L-shaped connector lines
  - Cardinality symbols (* many side, 1 one side)
  - Click highlighting: blue line + blue bold field text in both containers
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import os
import sys
import json
import threading
from pathlib import Path

# Import core functions
try:
    import pbix_layout_tool as pbi
except ImportError:
    messagebox.showerror("Error", "Could not find pbix_layout_tool.py\nMake sure it's in the same folder.")
    sys.exit(1)


class ToolTip:
    """Simple tooltip widget"""
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tooltip = None
        widget.bind("<Enter>", self.show)
        widget.bind("<Leave>", self.hide)

    def show(self, event=None):
        x, y, _, _ = self.widget.bbox("insert")
        x += self.widget.winfo_rootx() + 25
        y += self.widget.winfo_rooty() + 25
        self.tooltip = tk.Toplevel(self.widget)
        self.tooltip.wm_overrideredirect(True)
        self.tooltip.wm_geometry(f"+{x}+{y}")
        label = tk.Label(self.tooltip, text=self.text, background="#ffffe0",
                         relief=tk.SOLID, borderwidth=1, font=("Segoe UI", 9))
        label.pack()

    def hide(self, event=None):
        if self.tooltip:
            self.tooltip.destroy()
            self.tooltip = None


class PBILayoutGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("PBI Model Layout v1.2")
        self.root.geometry("800x750")

        # Variables
        self.pbix_path = tk.StringVar()
        self.pbit_path = tk.StringVar()
        self.relations_path = tk.StringVar()
        self.output_path = tk.StringVar()
        self.fact_prefixes = tk.StringVar(value="fct_,fact_,FCT_,FACT_,Fact_,Fct_")
        self.dim_prefixes = tk.StringVar(value="dim_,DIM_,Dim_,d_,D_")
        self.radius = tk.StringVar(value="520")
        self.layout_mode = tk.StringVar(value="auto")
        self.create_tabs = tk.BooleanVar(value=False)

        # Cache for preview
        self.cached_positions = None
        self.cached_metadata = None

        # Track if preview is open
        self.preview_window = None
        self.option_widgets = []

        self.setup_ui()

    def setup_ui(self):
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)

        row = 0

        ttk.Label(main_frame, text="Power BI Model Layout Tool",
                  font=("Segoe UI", 16, "bold")).grid(row=row, column=0, columnspan=3, pady=(0, 20))
        row += 1

        # Step 1
        step1 = ttk.LabelFrame(main_frame, text="Step 1: Extract Relationships", padding="10")
        step1.grid(row=row, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 10))
        step1.columnconfigure(1, weight=1)
        row += 1

        ttk.Label(step1, text=".pbit file:").grid(row=0, column=0, sticky=tk.W, pady=5)
        ttk.Entry(step1, textvariable=self.pbit_path).grid(row=0, column=1, sticky=(tk.W, tk.E), padx=5)
        ttk.Button(step1, text="Browse...", command=self.browse_pbit).grid(row=0, column=2, padx=5)
        ttk.Button(step1, text="Extract Relations", command=self.extract_relations,
                   style="Accent.TButton").grid(row=1, column=1, pady=10)

        # Step 2
        step2 = ttk.LabelFrame(main_frame, text="Step 2: Apply Layout", padding="10")
        step2.grid(row=row, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 10))
        step2.columnconfigure(1, weight=1)
        row += 1

        ttk.Label(step2, text=".pbix file:").grid(row=0, column=0, sticky=tk.W, pady=5)
        ttk.Entry(step2, textvariable=self.pbix_path).grid(row=0, column=1, sticky=(tk.W, tk.E), padx=5)
        ttk.Button(step2, text="Browse...", command=self.browse_pbix).grid(row=0, column=2, padx=5)

        ttk.Label(step2, text="relations.json:").grid(row=1, column=0, sticky=tk.W, pady=5)
        ttk.Entry(step2, textvariable=self.relations_path).grid(row=1, column=1, sticky=(tk.W, tk.E), padx=5)
        ttk.Button(step2, text="Browse...", command=self.browse_relations).grid(row=1, column=2, padx=5)

        ttk.Label(step2, text="Output file:").grid(row=2, column=0, sticky=tk.W, pady=5)
        ttk.Entry(step2, textvariable=self.output_path).grid(row=2, column=1, sticky=(tk.W, tk.E), padx=5)
        ttk.Button(step2, text="Browse...", command=self.browse_output).grid(row=2, column=2, padx=5)

        # Options
        opts = ttk.LabelFrame(main_frame, text="Options", padding="10")
        opts.grid(row=row, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 10))
        opts.columnconfigure(1, weight=1)
        row += 1

        ttk.Label(opts, text="Layout mode:").grid(row=0, column=0, sticky=tk.W, pady=5)
        mode_combo = ttk.Combobox(opts, textvariable=self.layout_mode,
                                  values=["auto", "grid", "horizontal", "star", "vertical_stack"],
                                  state="readonly", width=20)
        mode_combo.grid(row=0, column=1, sticky=tk.W, padx=5)
        self.option_widgets.append(mode_combo)

        ttk.Label(opts, text="Fact prefixes:").grid(row=1, column=0, sticky=tk.W, pady=5)
        fact_entry = ttk.Entry(opts, textvariable=self.fact_prefixes)
        fact_entry.grid(row=1, column=1, sticky=(tk.W, tk.E), padx=5)
        self.option_widgets.append(fact_entry)

        ttk.Label(opts, text="Dim prefixes:").grid(row=2, column=0, sticky=tk.W, pady=5)
        dim_entry = ttk.Entry(opts, textvariable=self.dim_prefixes)
        dim_entry.grid(row=2, column=1, sticky=(tk.W, tk.E), padx=5)
        self.option_widgets.append(dim_entry)

        tabs_check = ttk.Checkbutton(opts, text="Create diagram tabs (one per fact)",
                                     variable=self.create_tabs)
        tabs_check.grid(row=3, column=0, columnspan=2, sticky=tk.W, pady=5)
        self.option_widgets.append(tabs_check)

        # Action buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=row, column=0, columnspan=3, pady=10)
        row += 1

        self.preview_btn = ttk.Button(button_frame, text="Preview Layout",
                                      command=self.preview_layout, style="Accent.TButton")
        self.preview_btn.pack(side=tk.LEFT, padx=5)
        self.option_widgets.append(self.preview_btn)

        self.apply_btn = ttk.Button(button_frame, text="Apply Layout",
                                    command=self.apply_layout, style="Accent.TButton")
        self.apply_btn.pack(side=tk.LEFT, padx=5)
        self.option_widgets.append(self.apply_btn)

        # Log
        log_frame = ttk.LabelFrame(main_frame, text="Output", padding="10")
        log_frame.grid(row=row, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        main_frame.rowconfigure(row, weight=1)
        row += 1

        self.log_text = scrolledtext.ScrolledText(log_frame, height=12, wrap=tk.WORD,
                                                  font=("Consolas", 9))
        self.log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # Status bar
        self.status_var = tk.StringVar(value="Ready")
        ttk.Label(main_frame, textvariable=self.status_var,
                  relief=tk.SUNKEN, anchor=tk.W).grid(row=row, column=0, columnspan=3, sticky=(tk.W, tk.E))

        style = ttk.Style()
        style.configure("Accent.TButton", font=("Segoe UI", 10, "bold"))

    def log(self, message):
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)
        self.log_text.update()

    def browse_pbix(self):
        filename = filedialog.askopenfilename(
            title="Select .pbix file",
            filetypes=[("Power BI files", "*.pbix"), ("All files", "*.*")])
        if filename:
            self.pbix_path.set(filename)
            if not self.output_path.get():
                base, ext = os.path.splitext(filename)
                self.output_path.set(f"{base}_arranged{ext}")

    def browse_pbit(self):
        filename = filedialog.askopenfilename(
            title="Select .pbit file",
            filetypes=[("Power BI Template", "*.pbit"), ("All files", "*.*")])
        if filename:
            self.pbit_path.set(filename)
            if not self.relations_path.get():
                self.relations_path.set(os.path.join(os.path.dirname(filename), "relations.json"))

    def browse_relations(self):
        filename = filedialog.askopenfilename(
            title="Select relations.json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")])
        if filename:
            self.relations_path.set(filename)

    def browse_output(self):
        filename = filedialog.asksaveasfilename(
            title="Save output as", defaultextension=".pbix",
            filetypes=[("Power BI files", "*.pbix"), ("All files", "*.*")])
        if filename:
            self.output_path.set(filename)

    def disable_controls(self):
        for widget in self.option_widgets:
            widget.configure(state="disabled")

    def enable_controls(self):
        for widget in self.option_widgets:
            if isinstance(widget, ttk.Combobox):
                widget.configure(state="readonly")
            else:
                widget.configure(state="normal")

    # ------------------------------------------------------------------
    # Layout algorithms
    # ------------------------------------------------------------------
    def compute_layout_with_mode(self, fact_tables, dim_tables, other_tables,
                                 fact_to_dims, snowflake, orphan_dims, radius, node_sizes):
        mode = self.layout_mode.get()
        if mode == "auto":
            return pbi.compute_layout(fact_tables, dim_tables, other_tables,
                                      fact_to_dims, snowflake, orphan_dims,
                                      radius=radius, table_width=250, table_height=200,
                                      node_sizes=node_sizes)
        elif mode == "grid":
            return self._grid_layout(fact_tables, dim_tables, other_tables,
                                     fact_to_dims, snowflake, node_sizes)
        elif mode == "horizontal":
            return self._horizontal_layout(fact_tables, dim_tables, other_tables,
                                           fact_to_dims, snowflake, node_sizes)
        elif mode == "star":
            return self._star_layout(fact_tables, dim_tables, other_tables,
                                     fact_to_dims, snowflake, orphan_dims, radius, node_sizes)
        elif mode == "vertical_stack":
            return self._vertical_stack_layout(fact_tables, dim_tables, other_tables,
                                               fact_to_dims, snowflake, node_sizes)
        return pbi.compute_layout(fact_tables, dim_tables, other_tables,
                                  fact_to_dims, snowflake, orphan_dims,
                                  radius=radius, table_width=250, table_height=200,
                                  node_sizes=node_sizes)

    def _grid_layout(self, facts, dims, others, fact_to_dims, snowflake, node_sizes):
        """
        Facts stack vertically on the left.
        Dims + their snowflake children run in a horizontal row below.
        Snowflake children are placed directly to the right of their parent dim.
        """
        positions = {}
        COL_GAP, ROW_GAP = 60, 50
        def w(n): return node_sizes.get(n, (250, 0))[0] if node_sizes else 250
        def h(n): return node_sizes.get(n, (0, 200))[1] if node_sizes else 200

        all_snowflake_children = {c for ch in snowflake.values() for c in ch}

        # Facts column
        y = 0
        fact_col_w = max((w(f) for f in facts), default=250)
        for f in facts:
            positions[f] = (0, y)
            y += h(f) + ROW_GAP

        fact_block_bottom = y

        # Dims row: plain dims, then snowflake parents + their children inline
        snowflake_parents = set(snowflake.keys())
        plain_dims = [d for d in dims if d not in all_snowflake_children and d not in snowflake_parents]

        x = fact_col_w + COL_GAP
        # Place plain dims
        for d in plain_dims:
            positions[d] = (x, fact_block_bottom)
            x += w(d) + COL_GAP

        # Place snowflake groups: parent then children stacked to its right
        for d in dims:
            if d in snowflake_parents and d not in all_snowflake_children:
                positions[d] = (x, fact_block_bottom)
                x += w(d) + COL_GAP
                # Children placed to the right of parent, same row
                for child in snowflake.get(d, []):
                    positions[child] = (x, fact_block_bottom)
                    x += w(child) + COL_GAP

        if others:
            x_other, y_other = 0, fact_block_bottom + 300 + ROW_GAP
            for o in others:
                positions[o] = (x_other, y_other)
                x_other += w(o) + COL_GAP
        return positions

    def _horizontal_layout(self, facts, dims, others, fact_to_dims, snowflake, node_sizes):
        """
        Facts in a row at the top.
        Below each fact: its direct dims stacked vertically.
        Snowflake children placed directly below their parent dim.
        """
        positions = {}
        COL_GAP, ROW_GAP = 80, 50
        def w(n): return node_sizes.get(n, (250, 0))[0] if node_sizes else 250
        def h(n): return node_sizes.get(n, (0, 200))[1] if node_sizes else 200

        all_snowflake_children = {c for ch in snowflake.values() for c in ch}

        # Facts in a horizontal row
        x = 0
        fact_height = max((h(f) for f in facts), default=200)
        for f in facts:
            positions[f] = (x, 0)
            x += w(f) + COL_GAP

        # Below each fact: its dims, and each dim's snowflake children below it
        y_start = fact_height + ROW_GAP
        x = 0
        for f in facts:
            y = y_start
            for d in fact_to_dims.get(f, []):
                if d in positions:
                    x += w(d) + COL_GAP
                    continue
                positions[d] = (x, y)
                y += h(d) + ROW_GAP
                # Snowflake children stacked below parent dim
                for child in snowflake.get(d, []):
                    positions[child] = (x, y)
                    y += h(child) + ROW_GAP
            x += w(f) + COL_GAP

        # Orphan dims
        for d in dims:
            if d not in positions and d not in all_snowflake_children:
                positions[d] = (x, y_start)
                x += w(d) + COL_GAP
        return positions

    def _star_layout(self, facts, dims, others, fact_to_dims, snowflake, orphan_dims, radius, node_sizes):
        """
        Single fact: classic star with fact at centre, dims in a ring.
        Snowflake children placed adjacent (pushed outward along the same angle).
        Multiple facts: 2-column grid of stars.
        """
        import math
        positions = {}
        def w(n): return node_sizes.get(n, (250, 0))[0] if node_sizes else 250
        def h(n): return node_sizes.get(n, (0, 200))[1] if node_sizes else 200

        all_snowflake_children = {c for ch in snowflake.values() for c in ch}
        SNOWFLAKE_PUSH = 320

        def place_star(cx, cy, fact, r):
            positions[fact] = (cx, cy)
            fact_dims = [d for d in fact_to_dims.get(fact, []) if d not in all_snowflake_children]
            n = len(fact_dims)
            for i, d in enumerate(fact_dims):
                angle = math.radians(-90 + (360 * i / max(n, 1)))
                dx = cx + r * math.cos(angle) - w(d) / 2
                dy = cy + r * math.sin(angle) - h(d) / 2
                positions[d] = (dx, dy)
                # Snowflake children pushed further along same angle
                for j, child in enumerate(snowflake.get(d, [])):
                    push = SNOWFLAKE_PUSH * (j + 1)
                    positions[child] = (
                        cx + (r + push) * math.cos(angle) - w(child) / 2,
                        cy + (r + push) * math.sin(angle) - h(child) / 2
                    )

        if len(facts) == 1:
            place_star(0, 0, facts[0], radius)
        else:
            stars_per_row = 2
            star_spacing = radius * 3
            for idx, f in enumerate(facts):
                row, col = divmod(idx, stars_per_row)
                place_star(col * star_spacing, row * star_spacing, f, radius)
        return positions

    def _vertical_stack_layout(self, facts, dims, others, fact_to_dims, snowflake, node_sizes):
        """
        Each fact followed immediately by its dims in a horizontal row below it.
        Snowflake children placed to the right of their parent dim in the same row.
        """
        positions = {}
        COL_GAP, ROW_GAP = 60, 50
        def w(n): return node_sizes.get(n, (250, 0))[0] if node_sizes else 250
        def h(n): return node_sizes.get(n, (0, 200))[1] if node_sizes else 200

        all_snowflake_children = {c for ch in snowflake.values() for c in ch}

        y = 0
        for f in facts:
            positions[f] = (0, y)
            y_dim_row = y + h(f) + ROW_GAP

            x = w(f) + COL_GAP
            row_height = 0
            for d in fact_to_dims.get(f, []):
                if d in positions:
                    continue
                positions[d] = (x, y_dim_row)
                row_height = max(row_height, h(d))
                x += w(d) + COL_GAP
                # Snowflake children inline to the right of parent
                for child in snowflake.get(d, []):
                    positions[child] = (x, y_dim_row)
                    row_height = max(row_height, h(child))
                    x += w(child) + COL_GAP

            y = y_dim_row + row_height + ROW_GAP

        # Orphan dims below everything
        x = COL_GAP
        for d in dims:
            if d not in positions and d not in all_snowflake_children:
                positions[d] = (x, y)
                x += w(d) + COL_GAP
        return positions

    # ------------------------------------------------------------------
    # Extract & apply workflow
    # ------------------------------------------------------------------
    def extract_relations(self):
        pbit = self.pbit_path.get()
        if not pbit or not os.path.isfile(pbit):
            messagebox.showerror("Error", "Please select a valid .pbit file")
            return
        output = self.relations_path.get() or "relations.json"
        self.log_text.delete(1.0, tk.END)
        self.log(f"Extracting from: {pbit}\n")
        self.status_var.set("Extracting...")

        def run():
            try:
                import io
                old_stdout = sys.stdout
                sys.stdout = io.StringIO()
                pbi.extract_relations_from_pbit(pbit, output)
                output_text = sys.stdout.getvalue()
                sys.stdout = old_stdout
                self.log(output_text)
                self.log(f"\n✓ Success! Saved to: {output}")
                self.status_var.set("Complete")
                self.relations_path.set(output)
                messagebox.showinfo("Success", f"Relationships extracted!\n\n{output}")
            except Exception as e:
                sys.stdout = old_stdout
                self.log(f"\n✗ Error: {str(e)}")
                self.status_var.set("Failed")
                messagebox.showerror("Error", str(e))

        threading.Thread(target=run, daemon=True).start()

    def preview_layout(self):
        pbix = self.pbix_path.get()
        if not pbix or not os.path.isfile(pbix):
            messagebox.showerror("Error", "Please select a valid .pbix file")
            return
        self.log_text.delete(1.0, tk.END)
        self.log("Computing layout...\n")
        self.status_var.set("Computing...")

        def run():
            try:
                fact_prefs = [p.strip() for p in self.fact_prefixes.get().split(",")]
                dim_prefs  = [p.strip() for p in self.dim_prefixes.get().split(",")]
                radius_val = int(self.radius.get())

                layout = pbi.read_diagram_layout(pbix)
                if not layout:
                    raise ValueError("No DiagramLayout found")

                table_names = pbi.extract_table_names(layout)
                fact_tables, dim_tables, other_tables = pbi.classify_tables(
                    table_names, fact_prefs, dim_prefs)

                fact_to_dims, snowflake, orphan_dims = {}, {}, set(dim_tables)
                relations = self.relations_path.get()
                if relations and os.path.isfile(relations):
                    rels = pbi.parse_relations(relations)
                    fact_to_dims, snowflake, orphan_dims = pbi.build_adjacency(
                        rels, fact_tables, dim_tables)

                node_sizes = pbi.extract_node_sizes(layout)
                positions = self.compute_layout_with_mode(
                    fact_tables, dim_tables, other_tables,
                    fact_to_dims, snowflake, orphan_dims,
                    radius_val, node_sizes)

                self.cached_positions = positions
                self.cached_metadata = {
                    'fact_tables': fact_tables, 'dim_tables': dim_tables,
                    'other_tables': other_tables, 'fact_to_dims': fact_to_dims,
                    'snowflake': snowflake, 'node_sizes': node_sizes
                }

                self.log("✓ Layout computed\n")
                self.status_var.set("Opening preview...")
                self.root.after(0, lambda: self.show_preview(
                    positions, node_sizes, fact_tables, dim_tables,
                    other_tables, snowflake, fact_to_dims))

            except Exception as e:
                import traceback
                self.log(f"\n✗ Error: {str(e)}\n{traceback.format_exc()}")
                self.status_var.set("Failed")
                messagebox.showerror("Error", str(e))

        threading.Thread(target=run, daemon=True).start()

    def show_preview(self, positions, node_sizes, facts, dims, others, snowflake, fact_to_dims):
        if self.preview_window and self.preview_window.winfo_exists():
            geometry = self.preview_window.geometry()
            state = self.preview_window.state()
            self.preview_window.destroy()
            self._create_preview_window(positions, node_sizes, facts, dims, others,
                                        snowflake, fact_to_dims, geometry, state)
            return
        self.disable_controls()
        self._create_preview_window(positions, node_sizes, facts, dims, others,
                                    snowflake, fact_to_dims)

    # ==================================================================
    # PREVIEW WINDOW  (all canvas drawing lives here)
    # ==================================================================
    def _create_preview_window(self, positions, node_sizes, facts, dims, others,
                                snowflake, fact_to_dims, geometry=None, state=None):
        preview = tk.Toplevel(self.root)
        preview.title("Layout Preview - Power BI Model View")
        preview.geometry(geometry or "1200x800")
        if state:
            preview.state(state)
        self.preview_window = preview

        def on_close():
            self.enable_controls()
            self.preview_window = None
            preview.destroy()

        preview.protocol("WM_DELETE_WINDOW", on_close)

        # --- Control bar ---
        ctrl = ttk.Frame(preview)
        ctrl.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(ctrl, text=f"Tables: {len(positions)} | Facts: {len(facts)} | Dims: {len(dims)}",
                  font=("Segoe UI", 10)).pack(side=tk.LEFT, padx=10)

        ttk.Label(ctrl, text="Layout:").pack(side=tk.LEFT, padx=(20, 5))
        mode_var = tk.StringVar(value=self.layout_mode.get())
        mode_combo = ttk.Combobox(ctrl, textvariable=mode_var,
                                  values=["auto", "grid", "horizontal", "star", "vertical_stack"],
                                  state="readonly", width=15)
        mode_combo.pack(side=tk.LEFT, padx=5)

        ttk.Label(ctrl, text="Radius:").pack(side=tk.LEFT, padx=(20, 5))
        radius_var = tk.StringVar(value=self.radius.get())
        radius_spin = ttk.Spinbox(ctrl, from_=100, to=1000, increment=50,
                                  textvariable=radius_var, width=8)
        radius_spin.pack(side=tk.LEFT, padx=5)

        ttk.Label(ctrl, text="Zoom:").pack(side=tk.LEFT, padx=(20, 5))
        zoom_var   = tk.DoubleVar(value=1.0)
        zoom_label = ttk.Label(ctrl, text="100%", width=6)
        zoom_label.pack(side=tk.LEFT, padx=5)

        def refresh():
            self.layout_mode.set(mode_var.get())
            self.radius.set(radius_var.get())
            self.preview_layout()

        mode_combo.bind("<<ComboboxSelected>>", lambda e: refresh())
        ttk.Button(ctrl, text="Refresh", command=refresh).pack(side=tk.LEFT, padx=5)

        # --- Canvas ---
        canvas_frame = ttk.Frame(preview)
        canvas_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        canvas   = tk.Canvas(canvas_frame, bg="#f0f0f0", highlightthickness=0)
        h_scroll = ttk.Scrollbar(canvas_frame, orient=tk.HORIZONTAL, command=canvas.xview)
        v_scroll = ttk.Scrollbar(canvas_frame, orient=tk.VERTICAL,   command=canvas.yview)
        canvas.configure(xscrollcommand=h_scroll.set, yscrollcommand=v_scroll.set)
        h_scroll.pack(side=tk.BOTTOM, fill=tk.X)
        v_scroll.pack(side=tk.RIGHT,  fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # ------------------------------------------------------------------
        # Precompute relationship metadata
        # ------------------------------------------------------------------
        all_snowflake = set()
        for children in (snowflake or {}).values():
            all_snowflake.update(children)

        # Build rel_edges and table_fields
        # rel_edges: list of {fact, dim, field, kind}
        # table_fields: table -> ordered list[str]  (only FK fields)
        def build_rel_data():
            table_fields_map = {}   # table -> list[str]  ordered
            rel_edges        = []

            def add_field(table, field):
                if table not in table_fields_map:
                    table_fields_map[table] = []
                if field not in table_fields_map[table]:
                    table_fields_map[table].append(field)

            for fact, dim_list in (fact_to_dims or {}).items():
                for dim in dim_list:
                    field = f"{dim.lower()}_id"
                    add_field(fact, field)
                    add_field(dim, field)
                    rel_edges.append({'fact': fact, 'dim': dim,
                                      'field': field, 'kind': 'star'})

            for parent, children in (snowflake or {}).items():
                for child in children:
                    field = f"{parent.lower()}_id"
                    add_field(child, field)
                    add_field(parent, field)
                    rel_edges.append({'fact': child, 'dim': parent,
                                      'field': field, 'kind': 'snowflake'})

            return table_fields_map, rel_edges

        TABLE_FIELDS, REL_EDGES = build_rel_data()

        # ------------------------------------------------------------------
        # Geometry constants
        # ------------------------------------------------------------------
        HEADER_H     = 56    # logical px  – tall enough for uppercase label at 13pt
        FIELD_LINE   = 30    # logical px  per field row
        FIELD_PAD    = 14    # logical px  top-padding inside body
        FIELD_BOTTOM = 12    # logical px  bottom padding
        MIN_W        = 220   # minimum table width
        FIELD_CHAR_W = 8     # px per character for Consolas field text (logical)

        def table_logical_size(name):
            """Return (logical_w, logical_h) for a table."""
            orig_w   = node_sizes.get(name, (250, 0))[0] if node_sizes else 250
            name_px  = len(name) * 11 + 48   # header label: wider font estimate
            fields   = TABLE_FIELDS.get(name, [])
            max_field_px = (max((len(f) for f in fields), default=0) * FIELD_CHAR_W + 28)
            logical_w = max(orig_w, name_px, max_field_px, MIN_W)
            fields   = TABLE_FIELDS.get(name, [])
            body_h   = FIELD_PAD + len(fields) * FIELD_LINE + FIELD_BOTTOM if fields else FIELD_BOTTOM
            logical_h = HEADER_H + body_h
            return logical_w, logical_h

        def table_canvas_geom(name, x, y, scale, off_x, off_y):
            """Return (x1,y1,x2,y2, hdr_h_canvas, field_y_list) in canvas coords."""
            lw, lh  = table_logical_size(name)
            x1      = x * scale + off_x
            y1      = y * scale + off_y
            x2      = x1 + lw * scale
            y2      = y1 + lh * scale
            hdr_c   = HEADER_H * scale
            fields  = TABLE_FIELDS.get(name, [])
            fys     = [y1 + hdr_c + (FIELD_PAD + i * FIELD_LINE + FIELD_LINE / 2) * scale
                       for i in range(len(fields))]
            return x1, y1, x2, y2, hdr_c, fys

        # ------------------------------------------------------------------
        # Mutable state shared by draw & events
        # ------------------------------------------------------------------
        current_positions = dict(positions)

        # Store draw-time artefacts so event handlers can find them
        draw_state = {
            'geom'          : {},   # name -> (x1,y1,x2,y2,hdr,fys)
            'edge_line_ids' : {},   # edge_idx -> [seg1_id, seg2_id]
            'field_item_ids': {},   # (table, field) -> canvas item id
            'scale'         : 1.0,
        }

        # Selection state - covers both edge-click and table-click modes
        selection = {
            'edge_idx'     : None,   # index into REL_EDGES, or None
            'line_ids'     : [],     # canvas ids of highlighted connector segments
            'field_ids'    : [],     # canvas ids of highlighted field text items
            'table_name'   : None,   # name of clicked table, or None
            'border_ids'   : [],     # canvas ids of table highlight borders
        }

        # Precompute adjacency: table -> set of directly related tables
        table_neighbors = {}
        for edge in REL_EDGES:
            f, d = edge['fact'], edge['dim']
            table_neighbors.setdefault(f, set()).add(d)
            table_neighbors.setdefault(d, set()).add(f)

        def clear_selection():
            scale = draw_state['scale']
            for lid in selection['line_ids']:
                try:
                    canvas.itemconfig(lid, fill="#adb5bd", width=1)
                except Exception:
                    pass
            for fid in selection['field_ids']:
                try:
                    fs = max(1, int(11 * scale))
                    canvas.itemconfig(fid, fill="#495057",
                                      font=("Consolas", fs, "normal"))
                except Exception:
                    pass
            for bid in selection['border_ids']:
                try:
                    canvas.delete(bid)
                except Exception:
                    pass
            selection['edge_idx']   = None
            selection['line_ids']   = []
            selection['field_ids']  = []
            selection['table_name'] = None
            selection['border_ids'] = []

        def apply_selection(edge_idx):
            if edge_idx is None:
                return
            scale   = draw_state['scale']
            ids     = draw_state['edge_line_ids'].get(edge_idx, [])
            seg_ids = ids[:2]   # first two items are line segments; [2],[3] are symbols
            for lid in seg_ids:
                try:
                    canvas.itemconfig(lid, fill="#0078d4", width=2)
                except Exception:
                    pass

            edge  = REL_EDGES[edge_idx]
            field = edge['field']
            fids  = []
            for tbl in (edge['fact'], edge['dim']):
                fid = draw_state['field_item_ids'].get((tbl, field))
                if fid:
                    fs = max(1, int(11 * scale))
                    try:
                        canvas.itemconfig(fid, fill="#0078d4",
                                          font=("Consolas", fs, "bold"))
                    except Exception:
                        pass
                    fids.append(fid)

            selection['edge_idx']  = edge_idx
            selection['line_ids']  = seg_ids
            selection['field_ids'] = fids

        def apply_table_selection(name):
            """Highlight the clicked table + all directly related tables."""
            geom  = draw_state['geom']
            scale = draw_state['scale']
            if name not in geom:
                return

            neighbors = table_neighbors.get(name, set())
            highlight_tables = {name} | neighbors
            border_ids = []

            for tbl in highlight_tables:
                if tbl not in geom:
                    continue
                x1, y1, x2, y2, hdr_h, _ = geom[tbl]
                color     = "#0078d4" if tbl == name else "#5ba3d9"
                thickness = 3        if tbl == name else 2
                bid = canvas.create_rectangle(
                    x1 - 1, y1 - 1, x2 + 1, y2 + 1,
                    outline=color, width=thickness, fill="",
                    tags="table_highlight")
                border_ids.append(bid)

            selection['table_name'] = name
            selection['border_ids'] = border_ids

        # ------------------------------------------------------------------
        # Main draw function
        # ------------------------------------------------------------------
        def redraw_canvas(scale):
            canvas.delete("all")
            draw_state['scale'] = scale

            if not current_positions:
                canvas.create_text(600, 400, text="No tables",
                                   fill="#666", font=("Segoe UI", 14))
                return

            # --- Compute offset so content starts at PADDING ---
            EXTRA  = 800
            PADDING = 150

            # Raw canvas coords without offset
            raw = {}
            for name, (x, y) in current_positions.items():
                lw, lh = table_logical_size(name)
                raw[name] = (x * scale, y * scale,
                             x * scale + lw * scale,
                             y * scale + lh * scale)

            min_rx = min(v[0] for v in raw.values())
            min_ry = min(v[1] for v in raw.values())
            max_rx = max(v[2] for v in raw.values()) + EXTRA
            max_ry = max(v[3] for v in raw.values()) + EXTRA

            off_x = PADDING - min_rx
            off_y = PADDING - min_ry

            canvas_w = (max_rx - min_rx) + PADDING * 2
            canvas_h = (max_ry - min_ry) + PADDING * 2
            canvas.configure(scrollregion=(0, 0, canvas_w, canvas_h))

            # Build final geometry
            geom = {}
            for name, (x, y) in current_positions.items():
                geom[name] = table_canvas_geom(name, x, y, scale, off_x, off_y)
            draw_state['geom'] = geom

            # --- Count connections per side for slot distribution ---
            fact_total = {}   # fact table -> # outgoing connections
            dim_total  = {}   # dim  table -> # incoming connections
            for edge in REL_EDGES:
                f, d = edge['fact'], edge['dim']
                if f in geom and d in geom:
                    fact_total[f] = fact_total.get(f, 0) + 1
                    dim_total[d]  = dim_total.get(d, 0) + 1

            # ----------------------------------------------------------
            # PASS 1: Draw L-shaped relationship lines (BEHIND tables)
            # ----------------------------------------------------------
            edge_line_ids = {}
            fact_idx = {}   # running slot index for fact right edge
            dim_idx  = {}   # running slot index for dim  top  edge

            for edge_idx, edge in enumerate(REL_EDGES):
                f, d = edge['fact'], edge['dim']
                if f not in geom or d not in geom:
                    continue

                fx1, fy1, fx2, fy2, f_hdr, _ = geom[f]
                dx1, dy1, dx2, dy2, d_hdr, _ = geom[d]

                line_color = "#adb5bd"

                # Fact / source: exit RIGHT edge, distributed vertically in body
                n_from   = fact_total.get(f, 1)
                i_from   = fact_idx.get(f, 0)
                fact_idx[f] = i_from + 1
                body_h_f = fy2 - fy1 - f_hdr
                from_x   = fx2
                from_y   = fy1 + f_hdr + body_h_f * (i_from + 1) / (n_from + 1)

                # Dim / target: enter TOP edge, distributed horizontally
                n_to    = dim_total.get(d, 1)
                i_to    = dim_idx.get(d, 0)
                dim_idx[d] = i_to + 1
                body_w_d = dx2 - dx1
                to_x    = dx1 + body_w_d * (i_to + 1) / (n_to + 1)
                to_y    = dy1

                # L-shape: horizontal then vertical
                seg1 = canvas.create_line(
                    from_x, from_y, to_x, from_y,
                    fill=line_color, width=1,
                    tags=("relationship", f"edge_{edge_idx}"))

                seg2 = canvas.create_line(
                    to_x, from_y, to_x, to_y,
                    fill=line_color, width=1,
                    tags=("relationship", f"edge_{edge_idx}"))

                # Store geometry for cardinality symbols (drawn after tables in pass 2.5)
                edge_line_ids[edge_idx] = [seg1, seg2, from_x, from_y, to_x, to_y]

            # edge_line_ids will be finalised in PASS 2.5 after table containers are drawn

            # ----------------------------------------------------------
            # PASS 2: Draw table containers ON TOP of lines
            # ----------------------------------------------------------
            field_item_ids = {}

            for name, (x1, y1, x2, y2, hdr_h, fys) in geom.items():
                # Drop shadow
                canvas.create_rectangle(x1 + 3, y1 + 3, x2 + 3, y2 + 3,
                                        fill="#d0d0d0", outline="",
                                        tags=f"table_{name}")
                # Body
                canvas.create_rectangle(x1, y1, x2, y2,
                                        fill="#ffffff", outline="#dee2e6", width=1,
                                        tags=f"table_{name}")

                # Header color
                if name in facts:
                    hdr_fill = "#2b3e96"
                elif name in all_snowflake:
                    hdr_fill = "#2d7a4f"
                elif name in dims:
                    hdr_fill = "#8b4b7a"
                else:
                    hdr_fill = "#6c757d"

                canvas.create_rectangle(x1, y1, x2, y1 + hdr_h,
                                        fill=hdr_fill, outline="",
                                        tags=f"table_{name}")

                # Header label - font scales with zoom, minimum 1pt so tk doesn't error
                hdr_fs = max(1, int(13 * scale))
                canvas.create_text(
                    x1 + (x2 - x1) / 2, y1 + hdr_h / 2,
                    text=name.upper(), fill="#ffffff",
                    font=("Segoe UI", hdr_fs, "bold"),
                    width=(x2 - x1) - 12,
                    tags=f"table_{name}")

                # Separator + field rows
                fields = TABLE_FIELDS.get(name, [])
                if fields:
                    canvas.create_line(x1, y1 + hdr_h, x2, y1 + hdr_h,
                                       fill="#dee2e6", width=1,
                                       tags=f"table_{name}")

                    if scale > 0.15:
                        field_fs = max(1, int(11 * scale))
                        for i, field in enumerate(fields):
                            fid = canvas.create_text(
                                x1 + 12 * scale, fys[i],
                                text=field, fill="#495057",
                                font=("Consolas", field_fs, "normal"),
                                anchor=tk.W, tags=f"table_{name}")
                            field_item_ids[(name, field)] = fid

            draw_state['field_item_ids'] = field_item_ids

            # ----------------------------------------------------------
            # PASS 2.5: Cardinality symbols ON TOP of table containers
            # ----------------------------------------------------------
            sym_fs   = max(1, int(11 * scale))
            sym_font = ("Segoe UI", sym_fs, "bold")

            for edge_idx, ids in edge_line_ids.items():
                seg1, seg2, from_x, from_y, to_x, to_y = ids

                many_id = canvas.create_text(
                    from_x - 8 * scale, from_y,
                    text="*", fill="#555e6b", font=sym_font,
                    tags=("cardinality", f"edge_{edge_idx}"))

                one_id = canvas.create_text(
                    to_x, to_y - 10 * scale,
                    text="1", fill="#555e6b", font=sym_font,
                    tags=("cardinality", f"edge_{edge_idx}"))

                # Replace raw geometry with final [seg1, seg2, many_id, one_id]
                edge_line_ids[edge_idx] = [seg1, seg2, many_id, one_id]

            draw_state['edge_line_ids'] = edge_line_ids

            # ----------------------------------------------------------
            # PASS 3: Legend (always on top)
            # ----------------------------------------------------------
            lx, ly = 20, 20
            canvas.create_rectangle(lx + 2, ly + 2, lx + 152, ly + 102,
                                     fill="#d0d0d0", outline="")
            canvas.create_rectangle(lx, ly, lx + 150, ly + 100,
                                     fill="#ffffff", outline="#dee2e6", width=1)
            canvas.create_text(lx + 75, ly + 12, text="Table Types",
                                fill="#212529", font=("Segoe UI", 9, "bold"))
            for dy, color, label in [
                (28, "#2b3e96", "Fact"),
                (48, "#8b4b7a", "Dimension"),
                (68, "#2d7a4f", "Snowflake"),
                (85, "#6c757d", "Other"),
            ]:
                canvas.create_rectangle(lx + 10, ly + dy, lx + 22, ly + dy + 10,
                                         fill=color, outline="")
                canvas.create_text(lx + 28, ly + dy + 5, text=label,
                                    fill="#212529", font=("Segoe UI", 8), anchor=tk.W)

            # Restore active selection after redraw
            if selection['edge_idx'] is not None:
                apply_selection(selection['edge_idx'])
            if selection['table_name'] is not None:
                apply_table_selection(selection['table_name'])

        # ------------------------------------------------------------------
        # Drag / pan state
        # ------------------------------------------------------------------
        drag_state = {
            'mode': None,
            'dragging_table': None,
            'start_x': 0,
            'start_y': 0,
            'table_start_pos': None,
        }

        # ------------------------------------------------------------------
        # Event handlers
        # ------------------------------------------------------------------
        def on_mouse_down(event):
            cx = canvas.canvasx(event.x)
            cy = canvas.canvasy(event.y)

            # 1. Hit-test relationship lines (±4 px tolerance)
            hit = canvas.find_overlapping(cx - 4, cy - 4, cx + 4, cy + 4)
            for item_id in reversed(hit):   # top-most first
                for tag in canvas.gettags(item_id):
                    if tag.startswith("edge_"):
                        idx = int(tag.split("_")[1])
                        clear_selection()
                        apply_selection(idx)
                        return

            # 2. Clear selection
            clear_selection()

            # 3. Hit-test tables - select table or start drag
            for name, (x1, y1, x2, y2, hdr_h, _) in draw_state['geom'].items():
                if x1 <= cx <= x2 and y1 <= cy <= y2:
                    # Always highlight the table and its neighbors on click
                    apply_table_selection(name)
                    # Start drag
                    drag_state['mode']            = 'drag_table'
                    drag_state['dragging_table']  = name
                    drag_state['start_x']         = event.x
                    drag_state['start_y']         = event.y
                    drag_state['table_start_pos'] = current_positions[name]
                    canvas.config(cursor="hand2")
                    return

            # 4. Pan
            drag_state['mode']    = 'pan'
            drag_state['start_x'] = event.x
            drag_state['start_y'] = event.y
            canvas.config(cursor="fleur")

        def on_mouse_move(event):
            if drag_state['mode'] == 'drag_table' and drag_state['dragging_table']:
                scale = draw_state['scale']
                dx = (event.x - drag_state['start_x']) / scale
                dy = (event.y - drag_state['start_y']) / scale
                name = drag_state['dragging_table']
                ox, oy = drag_state['table_start_pos']
                current_positions[name] = (ox + dx, oy + dy)
                self.cached_positions = dict(current_positions)
                redraw_canvas(zoom_var.get())

            elif drag_state['mode'] == 'pan':
                # Smooth pan
                sr = canvas.cget("scrollregion")
                if sr:
                    try:
                        sr_x1, sr_y1, sr_x2, sr_y2 = map(float, sr.split())
                        sr_w = sr_x2 - sr_x1
                        sr_h = sr_y2 - sr_y1
                    except (ValueError, AttributeError):
                        sr_w, sr_h = 1, 1
                else:
                    sr_w = max(canvas.winfo_width(), 1)
                    sr_h = max(canvas.winfo_height(), 1)

                dx_px = event.x - drag_state['start_x']
                dy_px = event.y - drag_state['start_y']
                drag_state['start_x'] = event.x
                drag_state['start_y'] = event.y

                # Current view fractions
                x0, x1 = canvas.xview()
                y0, y1 = canvas.yview()

                # Shift by the pixel delta expressed as a fraction of scroll region
                new_x0 = x0 - dx_px / sr_w
                new_y0 = y0 - dy_px / sr_h

                # Clamp to [0, 1 - view_size]
                view_w_frac = x1 - x0
                view_h_frac = y1 - y0
                new_x0 = max(0.0, min(new_x0, 1.0 - view_w_frac))
                new_y0 = max(0.0, min(new_y0, 1.0 - view_h_frac))

                canvas.xview_moveto(new_x0)
                canvas.yview_moveto(new_y0)

        def on_mouse_up(event):
            drag_state['mode']           = None
            drag_state['dragging_table'] = None
            canvas.config(cursor="")

        canvas.bind("<ButtonPress-1>",  on_mouse_down)
        canvas.bind("<B1-Motion>",      on_mouse_move)
        canvas.bind("<ButtonRelease-1>", on_mouse_up)

        def on_mousewheel(event):
            cur      = zoom_var.get()
            new_zoom = min(cur * 1.1, 3.0) if event.delta > 0 else max(cur / 1.1, 0.2)
            zoom_var.set(new_zoom)
            zoom_label.config(text=f"{int(new_zoom * 100)}%")
            redraw_canvas(new_zoom)

        canvas.bind("<MouseWheel>", on_mousewheel)
        canvas.bind("<Button-4>",   lambda e: on_mousewheel(type('o', (object,), {'delta':  120})()))
        canvas.bind("<Button-5>",   lambda e: on_mousewheel(type('o', (object,), {'delta': -120})()))

        # ------------------------------------------------------------------
        # Initial zoom-to-fit
        # ------------------------------------------------------------------
        canvas.update()
        cw = canvas.winfo_width()  - 40   # small margin
        ch = canvas.winfo_height() - 40

        min_x = min(x for x, y in current_positions.values())
        min_y = min(y for x, y in current_positions.values())
        max_x = max(x + table_logical_size(n)[0] for n, (x, y) in current_positions.items())
        max_y = max(y + table_logical_size(n)[1] for n, (x, y) in current_positions.items())

        content_w = max_x - min_x
        content_h = max_y - min_y
        if content_w > 0 and content_h > 0:
            initial_zoom = min(cw / content_w, ch / content_h) * 0.90
            initial_zoom = max(0.1, min(initial_zoom, 2.0))
        else:
            initial_zoom = 1.0

        zoom_var.set(initial_zoom)
        zoom_label.config(text=f"{int(initial_zoom * 100)}%")
        redraw_canvas(initial_zoom)

        # ------------------------------------------------------------------
        # Bottom button bar
        # ------------------------------------------------------------------
        btn_frame = ttk.Frame(preview)
        btn_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(btn_frame,
                  text="Click table to highlight related  |  Click line to highlight  |  Drag to move/pan  |  Scroll to zoom",
                  font=("Segoe UI", 9)).pack(side=tk.LEFT, padx=10)

        ttk.Button(btn_frame, text="Reset Zoom",
                   command=lambda: [zoom_var.set(initial_zoom),
                                    zoom_label.config(text=f"{int(initial_zoom * 100)}%"),
                                    redraw_canvas(initial_zoom)]).pack(side=tk.LEFT, padx=5)

        ttk.Button(btn_frame, text="Apply This Layout",
                   command=lambda: [on_close(), self.apply_layout()],
                   style="Accent.TButton").pack(side=tk.RIGHT, padx=5)
        ttk.Button(btn_frame, text="Close", command=on_close).pack(side=tk.RIGHT, padx=5)

        self.status_var.set("Preview ready - click a relationship line to highlight it")

    # ------------------------------------------------------------------
    # Apply layout to .pbix
    # ------------------------------------------------------------------
    def apply_layout(self):
        pbix   = self.pbix_path.get()
        output = self.output_path.get()

        if not pbix or not os.path.isfile(pbix):
            messagebox.showerror("Error", "Please select a valid .pbix file")
            return
        if not output:
            messagebox.showerror("Error", "Please specify an output path")
            return

        self.log_text.delete(1.0, tk.END)
        self.log(f"Processing: {pbix}\n")
        self.status_var.set("Processing...")

        def run():
            try:
                fact_prefs = [p.strip() for p in self.fact_prefixes.get().split(",")]
                dim_prefs  = [p.strip() for p in self.dim_prefixes.get().split(",")]
                radius_val = int(self.radius.get())

                layout = pbi.read_diagram_layout(pbix)
                if not layout:
                    raise ValueError("No DiagramLayout found")

                table_names = pbi.extract_table_names(layout)
                fact_tables, dim_tables, other_tables = pbi.classify_tables(
                    table_names, fact_prefs, dim_prefs)

                self.log(f"Found {len(table_names)} tables")
                self.log(f"  Facts: {len(fact_tables)}")
                self.log(f"  Dims:  {len(dim_tables)}\n")

                fact_to_dims, snowflake, orphan_dims = {}, {}, set(dim_tables)
                relations = self.relations_path.get()
                if relations and os.path.isfile(relations):
                    rels = pbi.parse_relations(relations)
                    fact_to_dims, snowflake, orphan_dims = pbi.build_adjacency(
                        rels, fact_tables, dim_tables)
                    self.log(f"Loaded {len(rels)} relationships\n")

                node_sizes = pbi.extract_node_sizes(layout)

                if self.cached_positions and self.cached_metadata:
                    positions = self.cached_positions
                    self.log("Using cached layout\n")
                else:
                    positions = self.compute_layout_with_mode(
                        fact_tables, dim_tables, other_tables,
                        fact_to_dims, snowflake, orphan_dims,
                        radius_val, node_sizes)

                self.log("Layout computed\n")

                from copy import deepcopy
                modified = pbi.apply_positions(deepcopy(layout), positions, 250, 200)

                if self.create_tabs.get():
                    self.log("Generating tabs...\n")
                    modified = pbi.create_diagram_tabs(
                        modified, fact_tables, fact_to_dims, snowflake,
                        radius=radius_val, table_width=250, table_height=200,
                        node_sizes=node_sizes)
                    self.log(f"Created {len(modified['diagrams'])} diagrams\n")

                new_json = json.dumps(modified, indent=2, ensure_ascii=False).encode("utf-16-le")
                pbi.repack_pbix(pbix, output, {pbi.DIAGRAM_LAYOUT_PATH: new_json})

                self.log(f"\n✓ Success!\n{output}")
                self.status_var.set("Complete")
                messagebox.showinfo("Success", f"Layout applied!\n\n{output}")

            except Exception as e:
                import traceback
                self.log(f"\n✗ Error: {str(e)}\n{traceback.format_exc()}")
                self.status_var.set("Failed")
                messagebox.showerror("Error", str(e))

        threading.Thread(target=run, daemon=True).start()


def main():
    root = tk.Tk()
    app = PBILayoutGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()