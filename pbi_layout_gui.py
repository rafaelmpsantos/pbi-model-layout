#!/usr/bin/env python3
"""
pbi-model-layout GUI v1.0
-------------------------
Graphical interface for the pbi-model-layout tool.
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
        self.root.title("PBI Model Layout v1.1")
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
        
        # Title
        ttk.Label(main_frame, text="Power BI Model Layout Tool", 
                 font=("Segoe UI", 16, "bold")).grid(row=row, column=0, columnspan=3, pady=(0, 20))
        row += 1
        
        # Step 1: Extract Relations
        step1 = ttk.LabelFrame(main_frame, text="Step 1: Extract Relationships", padding="10")
        step1.grid(row=row, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 10))
        step1.columnconfigure(1, weight=1)
        row += 1
        
        ttk.Label(step1, text=".pbit file:").grid(row=0, column=0, sticky=tk.W, pady=5)
        ttk.Entry(step1, textvariable=self.pbit_path).grid(row=0, column=1, sticky=(tk.W, tk.E), padx=5)
        ttk.Button(step1, text="Browse...", command=self.browse_pbit).grid(row=0, column=2, padx=5)
        
        ttk.Button(step1, text="Extract Relations", command=self.extract_relations,
                  style="Accent.TButton").grid(row=1, column=1, pady=10)
        
        # Step 2: Apply Layout
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
        
        # Output log
        log_frame = ttk.LabelFrame(main_frame, text="Output", padding="10")
        log_frame.grid(row=row, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        main_frame.rowconfigure(row, weight=1)
        row += 1
        
        self.log_text = scrolledtext.ScrolledText(log_frame, height=12, wrap=tk.WORD,
                                                  font=("Consolas", 9), state="disabled")
        self.log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Status bar
        self.status_var = tk.StringVar(value="Ready")
        status_bar = ttk.Label(main_frame, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        status_bar.grid(row=row, column=0, columnspan=3, sticky=(tk.W, tk.E))
        
        # Styles
        style = ttk.Style()
        style.configure("Accent.TButton", font=("Segoe UI", 10, "bold"))
        
    def log(self, message):
        self.log_text.configure(state="normal")
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)
        self.log_text.configure(state="disabled")
        self.log_text.update()
        
    def browse_pbix(self):
        filename = filedialog.askopenfilename(
            title="Select .pbix file",
            filetypes=[("Power BI files", "*.pbix"), ("All files", "*.*")]
        )
        if filename:
            self.pbix_path.set(filename)
            if not self.output_path.get():
                base, ext = os.path.splitext(filename)
                self.output_path.set(f"{base}_arranged{ext}")
                
    def browse_pbit(self):
        filename = filedialog.askopenfilename(
            title="Select .pbit file",
            filetypes=[("Power BI Template", "*.pbit"), ("All files", "*.*")]
        )
        if filename:
            self.pbit_path.set(filename)
            if not self.relations_path.get():
                folder = os.path.dirname(filename)
                self.relations_path.set(os.path.join(folder, "relations.json"))
                
    def browse_relations(self):
        filename = filedialog.askopenfilename(
            title="Select relations.json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if filename:
            self.relations_path.set(filename)
            
    def browse_output(self):
        filename = filedialog.asksaveasfilename(
            title="Save output as",
            defaultextension=".pbix",
            filetypes=[("Power BI files", "*.pbix"), ("All files", "*.*")]
        )
        if filename:
            self.output_path.set(filename)
    
    def disable_controls(self):
        """Disable main UI controls when preview is open"""
        for widget in self.option_widgets:
            widget.configure(state="disabled")
    
    def enable_controls(self):
        """Re-enable controls when preview closes"""
        for widget in self.option_widgets:
            if isinstance(widget, ttk.Combobox):
                widget.configure(state="readonly")
            else:
                widget.configure(state="normal")
    
    def compute_layout_with_mode(self, fact_tables, dim_tables, other_tables,
                                 fact_to_dims, snowflake, orphan_dims,
                                 radius, node_sizes):
        """Compute layout based on selected mode"""
        mode = self.layout_mode.get()
        
        if mode == "auto":
            return pbi.compute_layout(
                fact_tables, dim_tables, other_tables,
                fact_to_dims, snowflake, orphan_dims,
                radius=radius, table_width=250, table_height=200,
                node_sizes=node_sizes
            )
        elif mode == "grid":
            return self._grid_layout(fact_tables, dim_tables, other_tables,
                                    fact_to_dims, snowflake, node_sizes)
        elif mode == "horizontal":
            return self._horizontal_layout(fact_tables, dim_tables, other_tables,
                                          fact_to_dims, snowflake, node_sizes)
        elif mode == "star":
            return self._star_layout(fact_tables, dim_tables, other_tables,
                                    fact_to_dims, snowflake, orphan_dims,
                                    radius, node_sizes)
        elif mode == "vertical_stack":
            return self._vertical_stack_layout(fact_tables, dim_tables, other_tables,
                                              fact_to_dims, snowflake, node_sizes)
        
        return pbi.compute_layout(fact_tables, dim_tables, other_tables,
                                 fact_to_dims, snowflake, orphan_dims,
                                 radius=radius, table_width=250, table_height=200,
                                 node_sizes=node_sizes)
    
    def _grid_layout(self, facts, dims, others, fact_to_dims, snowflake, node_sizes):
        positions = {}
        COL_GAP, ROW_GAP = 200, 150  # Even more spacing
        def w(n): return node_sizes.get(n, (250, 0))[0] if node_sizes else 250
        def h(n): return node_sizes.get(n, (0, 200))[1] if node_sizes else 200
        
        y = 0
        fact_col_w = max((w(f) for f in facts), default=250)
        for f in facts:
            positions[f] = (0, y)
            y += h(f) + ROW_GAP
        
        x = fact_col_w + COL_GAP
        y_dims = y
        for d in dims:
            positions[d] = (x, y_dims)
            x += w(d) + COL_GAP
        
        if others:
            x_other = 0
            y_other = max(positions.values(), key=lambda p: p[1])[1] + 200 + ROW_GAP
            for o in others:
                positions[o] = (x_other, y_other)
                x_other += w(o) + COL_GAP
        return positions
    
    def _horizontal_layout(self, facts, dims, others, fact_to_dims, snowflake, node_sizes):
        positions = {}
        COL_GAP, ROW_GAP = 200, 150  # Even more spacing
        def w(n): return node_sizes.get(n, (250, 0))[0] if node_sizes else 250
        def h(n): return node_sizes.get(n, (0, 200))[1] if node_sizes else 200
        
        x = 0
        fact_height = max((h(f) for f in facts), default=200)
        for f in facts:
            positions[f] = (x, 0)
            x += w(f) + COL_GAP
        
        y_start = fact_height + ROW_GAP
        x = 0
        for f in facts:
            y = y_start
            for d in fact_to_dims.get(f, []):
                positions[d] = (x, y)
                y += h(d) + ROW_GAP
            x += w(f) + COL_GAP
        
        for d in dims:
            if d not in positions:
                positions[d] = (x, y_start)
                y_start += h(d) + ROW_GAP
        return positions
    
    def _star_layout(self, facts, dims, others, fact_to_dims, snowflake, orphan_dims, radius, node_sizes):
        import math
        positions = {}
        def w(n): return node_sizes.get(n, (250, 0))[0] if node_sizes else 250
        def h(n): return node_sizes.get(n, (0, 200))[1] if node_sizes else 200
        
        if len(facts) == 1:
            f = facts[0]
            positions[f] = (0, 0)
            fact_dims = fact_to_dims.get(f, [])
            n = len(fact_dims)
            for i, d in enumerate(fact_dims):
                angle = math.radians(-90 + (360 * i / max(n, 1)))
                x = radius * math.cos(angle) - w(d) / 2
                y = radius * math.sin(angle) - h(d) / 2
                positions[d] = (x, y)
        else:
            stars_per_row = 2
            star_spacing = radius * 4.5
            for idx, f in enumerate(facts):
                row = idx // stars_per_row
                col = idx % stars_per_row
                fx = col * star_spacing
                fy = row * star_spacing
                positions[f] = (fx, fy)
                
                fact_dims = fact_to_dims.get(f, [])
                n = len(fact_dims)
                for i, d in enumerate(fact_dims):
                    angle = math.radians(-90 + (360 * i / max(n, 1)))
                    x = fx + radius * math.cos(angle) - w(d) / 2
                    y = fy + radius * math.sin(angle) - h(d) / 2
                    positions[d] = (x, y)
        return positions
    
    def _vertical_stack_layout(self, facts, dims, others, fact_to_dims, snowflake, node_sizes):
        """Vertical stack: facts vertical left, dims inline to the right, snowflakes at edges/below"""
        positions = {}
        COL_GAP, ROW_GAP = 200, 150
        def w(n): return node_sizes.get(n, (250, 0))[0] if node_sizes else 250
        def h(n): return node_sizes.get(n, (0, 200))[1] if node_sizes else 200
        
        # Get all snowflake children
        all_snowflake = set()
        for children in snowflake.values():
            all_snowflake.update(children)
        
        y = 0
        for f in facts:
            positions[f] = (0, y)
            
            # Get dims for this fact (excluding snowflakes)
            fact_dims = [d for d in fact_to_dims.get(f, []) if d not in all_snowflake]
            
            if fact_dims:
                # Calculate center position for fact
                total_dim_width = sum(w(d) for d in fact_dims) + COL_GAP * (len(fact_dims) - 1)
                
                # Place dims inline to the right
                x = COL_GAP
                for d in fact_dims:
                    positions[d] = (x, y)
                    
                    # Place snowflake children below this dim
                    if d in snowflake:
                        snowflake_y = y + h(d) + ROW_GAP // 2
                        snowflake_x = x
                        for child in snowflake[d]:
                            positions[child] = (snowflake_x, snowflake_y)
                            snowflake_x += w(child) + COL_GAP // 2
                    
                    x += w(d) + COL_GAP
            
            y += max(h(f), max([h(d) for d in fact_dims], default=0)) + ROW_GAP
        
        # Place unconnected dims at the end
        x = COL_GAP
        for d in dims:
            if d not in positions:
                positions[d] = (x, y)
                x += w(d) + COL_GAP
        
        return positions
    
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
                dim_prefs = [p.strip() for p in self.dim_prefixes.get().split(",")]
                radius_val = int(self.radius.get())
                
                layout = pbi.read_diagram_layout(pbix)
                if not layout:
                    raise ValueError("No DiagramLayout found")
                
                table_names = pbi.extract_table_names(layout)
                fact_tables, dim_tables, other_tables = pbi.classify_tables(
                    table_names, fact_prefs, dim_prefs
                )
                
                fact_to_dims, snowflake, orphan_dims = {}, {}, set(dim_tables)
                relations = self.relations_path.get()
                if relations and os.path.isfile(relations):
                    rels = pbi.parse_relations(relations)
                    fact_to_dims, snowflake, orphan_dims = pbi.build_adjacency(
                        rels, fact_tables, dim_tables
                    )
                
                node_sizes = pbi.extract_node_sizes(layout)
                positions = self.compute_layout_with_mode(
                    fact_tables, dim_tables, other_tables,
                    fact_to_dims, snowflake, orphan_dims,
                    radius_val, node_sizes
                )
                
                self.cached_positions = positions
                self.cached_metadata = {
                    'fact_tables': fact_tables,
                    'dim_tables': dim_tables,
                    'other_tables': other_tables,
                    'fact_to_dims': fact_to_dims,
                    'snowflake': snowflake,
                    'node_sizes': node_sizes
                }
                
                self.log("✓ Layout computed\n")
                self.status_var.set("Opening preview...")
                
                self.root.after(0, lambda: self.show_preview(positions, node_sizes,
                                                            fact_tables, dim_tables,
                                                            other_tables, snowflake,
                                                            fact_to_dims))
            except Exception as e:
                import traceback
                self.log(f"\n✗ Error: {str(e)}\n{traceback.format_exc()}")
                self.status_var.set("Failed")
                messagebox.showerror("Error", str(e))
        
        threading.Thread(target=run, daemon=True).start()
    
    def show_preview(self, positions, node_sizes, facts, dims, others, snowflake, fact_to_dims):
        # If preview already exists, just refresh the content
        if self.preview_window and self.preview_window.winfo_exists():
            # Store current window geometry
            geometry = self.preview_window.geometry()
            state = self.preview_window.state()
            self.preview_window.destroy()
            # Recreate with same geometry
            self._create_preview_window(positions, node_sizes, facts, dims, others, 
                                       snowflake, fact_to_dims, geometry, state)
            return
        
        # First time opening - disable main UI
        self.disable_controls()
        self._create_preview_window(positions, node_sizes, facts, dims, others, 
                                    snowflake, fact_to_dims)
    
    def _create_preview_window(self, positions, node_sizes, facts, dims, others, 
                               snowflake, fact_to_dims, geometry=None, state=None):
        """Create or recreate preview window"""
        preview = tk.Toplevel(self.root)
        preview.title("Layout Preview")
        
        if geometry:
            preview.geometry(geometry)
            if state:
                preview.state(state)
        else:
            preview.geometry("1200x800")
        
        self.preview_window = preview
        
        def on_close():
            self.enable_controls()
            self.preview_window = None
            preview.destroy()
        
        preview.protocol("WM_DELETE_WINDOW", on_close)
        
        # Control bar
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
        
        radius_label = ttk.Label(ctrl, text="Radius:")
        radius_label.pack(side=tk.LEFT, padx=(20, 5))
        radius_var = tk.StringVar(value=self.radius.get())
        radius_spin = ttk.Spinbox(ctrl, from_=100, to=1000, increment=50,
                                 textvariable=radius_var, width=8)
        radius_spin.pack(side=tk.LEFT, padx=5)
        ToolTip(radius_label, "Distance (in pixels) between fact and dimensions in star layout")
        
        # Zoom controls
        ttk.Label(ctrl, text="Zoom:").pack(side=tk.LEFT, padx=(20, 5))
        zoom_var = tk.DoubleVar(value=1.0)
        zoom_label = ttk.Label(ctrl, text="100%", width=6)
        zoom_label.pack(side=tk.LEFT, padx=5)
        
        def refresh():
            self.layout_mode.set(mode_var.get())
            self.radius.set(radius_var.get())
            self.preview_layout()  # This will preserve window state
        
        def save_current_layout():
            """Save the current layout positions and close preview"""
            self.cached_positions = dict(current_positions)
            self.status_var.set("Layout saved - ready to apply")
            on_close()  # Close the preview window
            messagebox.showinfo("Layout Saved", 
                              "Layout saved!\n\nClick 'Apply Layout' to write to file.")
        
        mode_combo.bind("<<ComboboxSelected>>", lambda e: refresh())
        ttk.Button(ctrl, text="Refresh", command=refresh).pack(side=tk.LEFT, padx=5)
        ttk.Button(ctrl, text="Save Layout", command=save_current_layout).pack(side=tk.LEFT, padx=5)
        
        # Canvas frame
        canvas_frame = ttk.Frame(preview)
        canvas_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        
        canvas = tk.Canvas(canvas_frame, bg="#1e1e1e", highlightthickness=0)
        h_scroll = ttk.Scrollbar(canvas_frame, orient=tk.HORIZONTAL, command=canvas.xview)
        v_scroll = ttk.Scrollbar(canvas_frame, orient=tk.VERTICAL, command=canvas.yview)
        canvas.configure(xscrollcommand=h_scroll.set, yscrollcommand=v_scroll.set)
        
        h_scroll.pack(side=tk.BOTTOM, fill=tk.X)
        v_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Compute snowflake children
        all_snowflake = set()
        for children in snowflake.values():
            all_snowflake.update(children)
        
        if not positions:
            canvas.create_text(600, 400, text="No tables", fill="white", font=("Segoe UI", 14))
            return
        
        # Make positions mutable for drag-and-drop
        current_positions = dict(positions)
        
        # State for interactions
        drag_state = {
            'dragging_table': None,
            'start_x': 0, 
            'start_y': 0,
            'table_start_pos': None
        }
        
        def redraw_canvas(scale_factor):
            canvas.delete("all")
            
            # Increased spacing to match layout algorithms
            EXTRA_SPACING = 200  # Match layout spacing
            
            # Calculate bounds with wider boxes and spacing
            min_x = min(x for x, y in current_positions.values())
            min_y = min(y for x, y in current_positions.values())
            max_x = max(x + node_sizes.get(n, (250, 0))[0] * 1.5 + EXTRA_SPACING 
                       for n, (x, y) in current_positions.items())
            max_y = max(y + node_sizes.get(n, (0, 200))[1] + EXTRA_SPACING 
                       for n, (x, y) in current_positions.items())
            
            content_w = max_x - min_x
            content_h = max_y - min_y
            
            # Apply zoom
            scale = scale_factor
            
            # Add padding for relationship boxes
            padding = 150
            canvas_w = content_w * scale + padding * 2
            canvas_h = content_h * scale + padding * 2
            
            offset_x = padding - min_x * scale
            offset_y = padding - min_y * scale
            
            canvas.configure(scrollregion=(0, 0, canvas_w, canvas_h))
            
            # Build reverse relationship lookup
            dim_rels = {}
            for fact, related_dims in fact_to_dims.items():
                for dim in related_dims:
                    if dim not in dim_rels:
                        dim_rels[dim] = []
                    dim_rels[dim].append({'table': fact, 'type': 'Fact', 'dir': '1:*'})
            
            for parent, children in snowflake.items():
                for child in children:
                    if child not in dim_rels:
                        dim_rels[child] = []
                    dim_rels[child].append({'table': parent, 'type': 'Snowflake', 'dir': '1:*'})
            
            # Draw tables
            table_bounds = {}  # Store for click detection
            
            for name, (x, y) in current_positions.items():
                orig_w = node_sizes.get(name, (250, 0))[0] if node_sizes else 250
                h = node_sizes.get(name, (0, 200))[1] if node_sizes else 200
                w = orig_w * 1.5
                
                x1 = x * scale + offset_x
                y1 = y * scale + offset_y
                x2 = x1 + w * scale
                y2 = y1 + h * scale
                
                table_bounds[name] = (x1, y1, x2, y2)
                
                # Color by type
                if name in facts:
                    fill, outline, text_color = "#3a3a5c", "#5a5aff", "#aaaaff"
                elif name in all_snowflake:
                    fill, outline, text_color = "#3a4a3a", "#5aaa5a", "#aaffaa"
                elif name in dims:
                    fill, outline, text_color = "#4a3a3a", "#aa5a5a", "#ffaaaa"
                else:
                    fill, outline, text_color = "#3a3a3a", "#666666", "#aaaaaa"
                
                # Highlight if being dragged
                if drag_state['dragging_table'] == name:
                    outline = "#ffff00"
                    fill = fill.replace("3a", "5a")  # Lighter
                
                canvas.create_rectangle(x1, y1, x2, y2, fill=fill, outline=outline, 
                                      width=3 if drag_state['dragging_table'] == name else 2,
                                      tags=f"table_{name}")
                
                font_size = max(10, int(12 * scale))
                canvas.create_text(x1 + (w*scale)/2, y1 + (h*scale)/2, text=name,
                                 fill=text_color, font=("Segoe UI", font_size, "bold"),
                                 tags=f"table_{name}")
                
                # Relationship info boxes
                if name in dim_rels and scale > 0.2:
                    info_y = y2 + 5
                    info_font = max(8, int(9 * scale))
                    
                    for rel in dim_rels[name]:
                        rel_text = f"→ {rel['table']} ({rel['dir']})"
                        box_h = 20 * scale
                        
                        canvas.create_rectangle(x1, info_y, x2, info_y + box_h,
                                              fill="#2a2a2a", outline="#555555", width=1)
                        canvas.create_text(x1 + (w*scale)/2, info_y + box_h/2,
                                         text=rel_text, fill="#888888",
                                         font=("Consolas", info_font))
                        info_y += box_h + 3
            
            # Store for event handlers
            redraw_canvas.table_bounds = table_bounds
            redraw_canvas.scale = scale
            redraw_canvas.offset_x = offset_x
            redraw_canvas.offset_y = offset_y
            
            # Legend
            lx, ly = 20, 20
            canvas.create_rectangle(lx, ly, lx + 180, ly + 100,
                                  fill="#2a2a2a", outline="#555555", width=1)
            canvas.create_text(lx + 90, ly + 10, text="Legend",
                             fill="white", font=("Segoe UI", 10, "bold"))
            
            canvas.create_rectangle(lx + 10, ly + 30, lx + 30, ly + 45,
                                  fill="#3a3a5c", outline="#5a5aff", width=2)
            canvas.create_text(lx + 40, ly + 37, text="Fact Tables",
                             fill="#aaaaff", font=("Segoe UI", 9), anchor=tk.W)
            
            canvas.create_rectangle(lx + 10, ly + 55, lx + 30, ly + 70,
                                  fill="#4a3a3a", outline="#aa5a5a", width=2)
            canvas.create_text(lx + 40, ly + 62, text="Dimensions",
                             fill="#ffaaaa", font=("Segoe UI", 9), anchor=tk.W)
            
            canvas.create_rectangle(lx + 10, ly + 80, lx + 30, ly + 95,
                                  fill="#3a4a3a", outline="#5aaa5a", width=2)
            canvas.create_text(lx + 40, ly + 87, text="Snowflake",
                             fill="#aaffaa", font=("Segoe UI", 9), anchor=tk.W)
        
        # Event handlers - drag tables only
        def on_mouse_down(event):
            # Check if clicking on a table
            if hasattr(redraw_canvas, 'table_bounds'):
                for name, (x1, y1, x2, y2) in redraw_canvas.table_bounds.items():
                    if x1 <= event.x <= x2 and y1 <= event.y <= y2:
                        drag_state['dragging_table'] = name
                        drag_state['start_x'] = event.x
                        drag_state['start_y'] = event.y
                        drag_state['table_start_pos'] = current_positions[name]
                        canvas.config(cursor="hand2")
                        return
        
        def on_mouse_move(event):
            if drag_state['dragging_table']:
                # Move table
                dx = (event.x - drag_state['start_x']) / redraw_canvas.scale
                dy = (event.y - drag_state['start_y']) / redraw_canvas.scale
                
                name = drag_state['dragging_table']
                orig_x, orig_y = drag_state['table_start_pos']
                current_positions[name] = (orig_x + dx, orig_y + dy)
                
                # Update cached positions for apply
                self.cached_positions = dict(current_positions)
                
                redraw_canvas(zoom_var.get())
        
        def on_mouse_up(event):
            drag_state['dragging_table'] = None
            canvas.config(cursor="")
        
        canvas.bind("<ButtonPress-1>", on_mouse_down)
        canvas.bind("<B1-Motion>", on_mouse_move)
        canvas.bind("<ButtonRelease-1>", on_mouse_up)
        
        # Mouse wheel zoom
        def on_mousewheel(event):
            current = zoom_var.get()
            if event.delta > 0:
                new_zoom = min(current * 1.1, 3.0)
            else:
                new_zoom = max(current / 1.1, 0.3)
            zoom_var.set(new_zoom)
            zoom_label.config(text=f"{int(new_zoom*100)}%")
            redraw_canvas(new_zoom)
        
        canvas.bind("<MouseWheel>", on_mousewheel)
        canvas.bind("<Button-4>", lambda e: on_mousewheel(type('obj', (object,), {'delta': 120})()))
        canvas.bind("<Button-5>", lambda e: on_mousewheel(type('obj', (object,), {'delta': -120})()))
        
        # Calculate initial zoom to fit everything with proper spacing
        canvas.update()
        canvas_w = canvas.winfo_width() - 40  # Account for scrollbars
        canvas_h = canvas.winfo_height() - 40
        
        SPACING_BUFFER = 200  # Match EXTRA_SPACING
        min_x = min(x for x, y in current_positions.values())
        min_y = min(y for x, y in current_positions.values())
        max_x = max(x + node_sizes.get(n, (250, 0))[0] * 1.5 + SPACING_BUFFER
                   for n, (x, y) in current_positions.items())
        max_y = max(y + node_sizes.get(n, (0, 200))[1] + SPACING_BUFFER
                   for n, (x, y) in current_positions.items())
        
        content_w = max_x - min_x
        content_h = max_y - min_y
        
        if content_w > 0 and content_h > 0:
            initial_zoom = min(canvas_w / content_w, canvas_h / content_h) * 0.85
            initial_zoom = max(0.2, min(initial_zoom, 1.0))  # Clamp between 20% and 100%
        else:
            initial_zoom = 1.0
        
        zoom_var.set(initial_zoom)
        zoom_label.config(text=f"{int(initial_zoom*100)}%")
        
        # Initial draw
        redraw_canvas(initial_zoom)
        
        # Buttons
        btn_frame = ttk.Frame(preview)
        btn_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Label(btn_frame, text="Click table to drag | Scroll to zoom | Use scrollbars to navigate").pack(side=tk.LEFT, padx=10, font=("Segoe UI", 9))
        
        ttk.Button(btn_frame, text="Reset Zoom", 
                  command=lambda: [zoom_var.set(initial_zoom), 
                                  zoom_label.config(text=f"{int(initial_zoom*100)}%"), 
                                  redraw_canvas(initial_zoom)]).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(btn_frame, text="Quit without Save",
                  command=on_close).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(btn_frame, text="Apply This Layout",
                  command=lambda: [on_close(), self.apply_layout()],
                  style="Accent.TButton").pack(side=tk.RIGHT, padx=5)
        ttk.Button(btn_frame, text="Close", command=on_close).pack(side=tk.RIGHT, padx=5)
        
        self.status_var.set("Preview ready")
        
        preview = tk.Toplevel(self.root)
        preview.title("Layout Preview")
        preview.geometry("1200x800")
        self.preview_window = preview
        
        def on_close():
            self.enable_controls()
            self.preview_window = None
            preview.destroy()
        
        preview.protocol("WM_DELETE_WINDOW", on_close)
        
        # Control bar
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
        
        # Zoom controls
        ttk.Label(ctrl, text="Zoom:").pack(side=tk.LEFT, padx=(20, 5))
        zoom_var = tk.DoubleVar(value=1.0)
        zoom_label = ttk.Label(ctrl, text="100%", width=6)
        zoom_label.pack(side=tk.LEFT, padx=5)
        
        def refresh():
            self.layout_mode.set(mode_var.get())
            self.radius.set(radius_var.get())
            on_close()
            self.preview_layout()
        
        mode_combo.bind("<<ComboboxSelected>>", lambda e: refresh())
        ttk.Button(ctrl, text="Refresh", command=refresh).pack(side=tk.LEFT, padx=5)
        
        # Canvas frame
        canvas_frame = ttk.Frame(preview)
        canvas_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        
        canvas = tk.Canvas(canvas_frame, bg="#1e1e1e", highlightthickness=0)
        h_scroll = ttk.Scrollbar(canvas_frame, orient=tk.HORIZONTAL, command=canvas.xview)
        v_scroll = ttk.Scrollbar(canvas_frame, orient=tk.VERTICAL, command=canvas.yview)
        canvas.configure(xscrollcommand=h_scroll.set, yscrollcommand=v_scroll.set)
        
        h_scroll.pack(side=tk.BOTTOM, fill=tk.X)
        v_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # State for panning
        pan_state = {'dragging': False, 'start_x': 0, 'start_y': 0}
        
        def on_mouse_down(event):
            pan_state['dragging'] = True
            pan_state['start_x'] = event.x
            pan_state['start_y'] = event.y
            canvas.config(cursor="fleur")
        
        def on_mouse_move(event):
            if pan_state['dragging']:
                dx = event.x - pan_state['start_x']
                dy = event.y - pan_state['start_y']
                canvas.xview_scroll(int(-dx), "units")
                canvas.yview_scroll(int(-dy), "units")
                pan_state['start_x'] = event.x
                pan_state['start_y'] = event.y
        
        def on_mouse_up(event):
            pan_state['dragging'] = False
            canvas.config(cursor="")
        
        canvas.bind("<ButtonPress-1>", on_mouse_down)
        canvas.bind("<B1-Motion>", on_mouse_move)
        canvas.bind("<ButtonRelease-1>", on_mouse_up)
        
        # Compute snowflake children
        all_snowflake = set()
        for children in snowflake.values():
            all_snowflake.update(children)
        
        if not positions:
            canvas.create_text(600, 400, text="No tables", fill="white", font=("Segoe UI", 14))
            return
        
        def redraw_canvas(scale_factor):
            canvas.delete("all")
            
            # Calculate bounds
            min_x = min(x for x, y in positions.values())
            min_y = min(y for x, y in positions.values())
            max_x = max(x + node_sizes.get(n, (250, 0))[0] * 1.5 for n, (x, y) in positions.items())
            max_y = max(y + node_sizes.get(n, (0, 200))[1] for n, (x, y) in positions.items())
            
            content_w = max_x - min_x
            content_h = max_y - min_y
            
            # Apply zoom
            scale = scale_factor * 0.85
            
            # Add padding for relationship boxes
            padding = 100
            canvas_w = content_w * scale + padding * 2
            canvas_h = content_h * scale + padding * 2
            
            offset_x = padding - min_x * scale
            offset_y = padding - min_y * scale
            
            canvas.configure(scrollregion=(0, 0, canvas_w, canvas_h))
            
            # Build reverse relationship lookup
            dim_rels = {}
            for fact, related_dims in fact_to_dims.items():
                for dim in related_dims:
                    if dim not in dim_rels:
                        dim_rels[dim] = []
                    dim_rels[dim].append({'table': fact, 'type': 'Fact', 'dir': '1:*'})
            
            for parent, children in snowflake.items():
                for child in children:
                    if child not in dim_rels:
                        dim_rels[child] = []
                    dim_rels[child].append({'table': parent, 'type': 'Snowflake', 'dir': '1:*'})
            
            # Draw tables with wider boxes
            for name, (x, y) in positions.items():
                orig_w = node_sizes.get(name, (250, 0))[0] if node_sizes else 250
                h = node_sizes.get(name, (0, 200))[1] if node_sizes else 200
                
                # Make boxes 1.5x wider for better text display
                w = orig_w * 1.5
                
                x1 = x * scale + offset_x
                y1 = y * scale + offset_y
                x2 = x1 + w * scale
                y2 = y1 + h * scale
                
                # Color by type
                if name in facts:
                    fill, outline, text_color = "#3a3a5c", "#5a5aff", "#aaaaff"
                elif name in all_snowflake:
                    fill, outline, text_color = "#3a4a3a", "#5aaa5a", "#aaffaa"
                elif name in dims:
                    fill, outline, text_color = "#4a3a3a", "#aa5a5a", "#ffaaaa"
                else:
                    fill, outline, text_color = "#3a3a3a", "#666666", "#aaaaaa"
                
                canvas.create_rectangle(x1, y1, x2, y2, fill=fill, outline=outline, width=2)
                
                # Larger font for table names
                font_size = max(10, int(12 * scale))
                canvas.create_text(x1 + (w*scale)/2, y1 + (h*scale)/2, text=name,
                                 fill=text_color, font=("Segoe UI", font_size, "bold"))
                
                # Relationship info boxes
                if name in dim_rels and scale > 0.2:
                    info_y = y2 + 5
                    info_font = max(8, int(9 * scale))
                    
                    for rel in dim_rels[name]:
                        rel_text = f"→ {rel['table']} ({rel['dir']})"
                        box_h = 20 * scale
                        
                        canvas.create_rectangle(x1, info_y, x2, info_y + box_h,
                                              fill="#2a2a2a", outline="#555555", width=1)
                        canvas.create_text(x1 + (w*scale)/2, info_y + box_h/2,
                                         text=rel_text, fill="#888888",
                                         font=("Consolas", info_font))
                        info_y += box_h + 3
            
            # Legend
            lx, ly = 20, 20
            canvas.create_rectangle(lx, ly, lx + 180, ly + 100,
                                  fill="#2a2a2a", outline="#555555", width=1)
            canvas.create_text(lx + 90, ly + 10, text="Legend",
                             fill="white", font=("Segoe UI", 10, "bold"))
            
            canvas.create_rectangle(lx + 10, ly + 30, lx + 30, ly + 45,
                                  fill="#3a3a5c", outline="#5a5aff", width=2)
            canvas.create_text(lx + 40, ly + 37, text="Fact Tables",
                             fill="#aaaaff", font=("Segoe UI", 9), anchor=tk.W)
            
            canvas.create_rectangle(lx + 10, ly + 55, lx + 30, ly + 70,
                                  fill="#4a3a3a", outline="#aa5a5a", width=2)
            canvas.create_text(lx + 40, ly + 62, text="Dimensions",
                             fill="#ffaaaa", font=("Segoe UI", 9), anchor=tk.W)
            
            canvas.create_rectangle(lx + 10, ly + 80, lx + 30, ly + 95,
                                  fill="#3a4a3a", outline="#5aaa5a", width=2)
            canvas.create_text(lx + 40, ly + 87, text="Snowflake",
                             fill="#aaffaa", font=("Segoe UI", 9), anchor=tk.W)
        
        # Mouse wheel zoom
        def on_mousewheel(event):
            current = zoom_var.get()
            if event.delta > 0:
                new_zoom = min(current * 1.1, 3.0)
            else:
                new_zoom = max(current / 1.1, 0.3)
            zoom_var.set(new_zoom)
            zoom_label.config(text=f"{int(new_zoom*100)}%")
            redraw_canvas(new_zoom)
        
        canvas.bind("<MouseWheel>", on_mousewheel)  # Windows
        canvas.bind("<Button-4>", lambda e: on_mousewheel(type('obj', (object,), {'delta': 120})()))  # Linux scroll up
        canvas.bind("<Button-5>", lambda e: on_mousewheel(type('obj', (object,), {'delta': -120})()))  # Linux scroll down
        
        # Initial draw
        redraw_canvas(1.0)
        
        # Buttons
        btn_frame = ttk.Frame(preview)
        btn_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Label(btn_frame, text="Click-drag to pan | Scroll to zoom").pack(side=tk.LEFT, padx=10)
        
        ttk.Button(btn_frame, text="Reset Zoom", 
                  command=lambda: [zoom_var.set(1.0), zoom_label.config(text="100%"), redraw_canvas(1.0)]).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(btn_frame, text="Apply This Layout",
                  command=lambda: [on_close(), self.apply_layout()],
                  style="Accent.TButton").pack(side=tk.RIGHT, padx=5)
        ttk.Button(btn_frame, text="Close", command=on_close).pack(side=tk.RIGHT, padx=5)
        
        self.status_var.set("Preview ready")
    
    def apply_layout(self):
        pbix = self.pbix_path.get()
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
                dim_prefs = [p.strip() for p in self.dim_prefixes.get().split(",")]
                radius_val = int(self.radius.get())
                
                layout = pbi.read_diagram_layout(pbix)
                if not layout:
                    raise ValueError("No DiagramLayout found")
                
                table_names = pbi.extract_table_names(layout)
                fact_tables, dim_tables, other_tables = pbi.classify_tables(
                    table_names, fact_prefs, dim_prefs
                )
                
                self.log(f"Found {len(table_names)} tables")
                self.log(f"  Facts: {len(fact_tables)}")
                self.log(f"  Dims: {len(dim_tables)}\n")
                
                fact_to_dims, snowflake, orphan_dims = {}, {}, set(dim_tables)
                relations = self.relations_path.get()
                if relations and os.path.isfile(relations):
                    rels = pbi.parse_relations(relations)
                    fact_to_dims, snowflake, orphan_dims = pbi.build_adjacency(
                        rels, fact_tables, dim_tables
                    )
                    self.log(f"Loaded {len(rels)} relationships\n")
                
                node_sizes = pbi.extract_node_sizes(layout)
                
                if self.cached_positions and self.cached_metadata:
                    positions = self.cached_positions
                    self.log("Using cached layout\n")
                else:
                    positions = self.compute_layout_with_mode(
                        fact_tables, dim_tables, other_tables,
                        fact_to_dims, snowflake, orphan_dims,
                        radius_val, node_sizes
                    )
                
                self.log("Layout computed\n")
                
                from copy import deepcopy
                modified = pbi.apply_positions(deepcopy(layout), positions, 250, 200)
                
                if self.create_tabs.get():
                    self.log("Generating tabs...\n")
                    modified = pbi.create_diagram_tabs(
                        modified, fact_tables, fact_to_dims, snowflake,
                        radius=radius_val, table_width=250, table_height=200,
                        node_sizes=node_sizes
                    )
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