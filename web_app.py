import math
import os
import tempfile
from datetime import datetime, timezone
from html import escape

from flask import Flask, jsonify, render_template, request
from werkzeug.utils import secure_filename

from localizations import get_locale_from_header, get_translations, normalize_locale
from pbix_layout_tool import extract_pbit_model_insights
from pbix_layout_tool import (
    DEFAULT_DIM_PREFIXES,
    DEFAULT_FACT_PREFIXES,
    build_adjacency,
    classify_tables,
    compute_layout,
)

ALLOWED_EXTENSIONS = {"pbit"}
MAX_UPLOAD_SIZE = 50 * 1024 * 1024  # 50 MB

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_SIZE


def _is_allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def _extract_model_insights(uploaded_file) -> dict:
    with tempfile.TemporaryDirectory() as tmpdir:
        source_name = secure_filename(uploaded_file.filename or "model.pbit")
        source_path = os.path.join(tmpdir, source_name)
        uploaded_file.save(source_path)
        return extract_pbit_model_insights(source_path)


def _get_request_locale() -> str:
    explicit_locale = request.values.get("lang")
    if explicit_locale:
        return normalize_locale(explicit_locale)
    return get_locale_from_header(request.headers.get("Accept-Language"))


def _render_index(locale: str, **context):
    return render_template(
        "index.html",
        locale=locale,
        texts=get_translations(locale),
        **context,
    )


def _infer_relationship_metadata(relations: list[dict], table_names: list[str]) -> list[dict]:
    facts, dims, _ = classify_tables(table_names, DEFAULT_FACT_PREFIXES, DEFAULT_DIM_PREFIXES)
    fact_set = set(facts)
    dim_set = set(dims)
    enriched = []

    for relation in relations:
        src = relation["from"]
        dst = relation["to"]
        metadata = dict(relation)
        metadata["from_cardinality"] = "*"
        metadata["to_cardinality"] = "1"
        metadata["filter_direction"] = "single"
        metadata["filter_from"] = dst
        metadata["filter_to"] = src
        metadata["cardinality_label"] = "*:1"
        metadata["direction_label"] = f"{dst} -> {src}"
        metadata["metadata_inferred"] = True

        if src in fact_set and dst in dim_set:
            pass
        elif dst in fact_set and src in dim_set:
            metadata["from_cardinality"] = "1"
            metadata["to_cardinality"] = "*"
            metadata["filter_from"] = src
            metadata["filter_to"] = dst
            metadata["cardinality_label"] = "1:*"
            metadata["direction_label"] = f"{src} -> {dst}"
        else:
            metadata["from_cardinality"] = "?"
            metadata["to_cardinality"] = "?"
            metadata["filter_direction"] = "unknown"
            metadata["filter_from"] = src
            metadata["filter_to"] = dst
            metadata["cardinality_label"] = "?"
            metadata["direction_label"] = "?"

        enriched.append(metadata)

    return enriched


def _estimate_node_sizes(table_names: list[str], table_columns: dict[str, list[str]]) -> dict[str, tuple[int, int]]:
    sizes = {}
    # Keep these close to the actual React Flow table card CSS.
    header_height = 56
    row_height = 36
    min_width = 240
    max_width = 360
    min_height = 140

    for name in table_names:
        columns = table_columns.get(name, [])
        longest = max([len(name)] + [len(column) for column in columns])
        width = max(min_width, min(max_width, 140 + longest * 7))
        visible_rows = max(3, len(columns))
        height = max(min_height, header_height + visible_rows * row_height + 12)
        sizes[name] = (width, height)

    return sizes


def _build_diagram_positions(relations: list[dict], table_columns: dict[str, list[str]]):
    table_names = sorted({r["from"] for r in relations} | {r["to"] for r in relations})
    facts, dims, others = classify_tables(
        table_names, DEFAULT_FACT_PREFIXES, DEFAULT_DIM_PREFIXES
    )
    fact_to_dims, snowflake, orphan_dims = build_adjacency(relations, facts, dims)
    node_sizes = _estimate_node_sizes(table_names, table_columns)

    def width(name: str) -> int:
        return node_sizes.get(name, (260, 180))[0]

    def height(name: str) -> int:
        return node_sizes.get(name, (260, 180))[1]

    positions = {}
    helper_tables = {
        name
        for name in table_names
        if name.startswith("LocalDateTable_")
    }
    helper_owner = {}
    for rel in relations:
        if rel["from"] in helper_tables and rel["to"] not in helper_tables:
            helper_owner[rel["from"]] = rel["to"]
        elif rel["to"] in helper_tables and rel["from"] not in helper_tables:
            helper_owner[rel["to"]] = rel["from"]

    all_snowflake_children = {child for children in snowflake.values() for child in children}
    helper_children = set(helper_tables)
    direct_dims_by_fact = {
        fact_name: [
            dim_name
            for dim_name in fact_to_dims.get(fact_name, [])
            if dim_name not in all_snowflake_children and dim_name not in helper_children
        ]
        for fact_name in facts
    }
    dim_usage = {}
    for fact_name, dim_names in direct_dims_by_fact.items():
        for dim_name in dim_names:
            dim_usage.setdefault(dim_name, set()).add(fact_name)

    shared_dims = sorted([name for name, used_by in dim_usage.items() if len(used_by) > 1])
    fact_order = sorted(
        facts,
        key=lambda name: (len(direct_dims_by_fact.get(name, [])), len(fact_to_dims.get(name, []))),
        reverse=True,
    )
    cluster_center_y = 520
    fact_spacing_x = 1220
    top_gap_y = 320
    bottom_gap_y = 300
    row_gap_x = 110
    helper_gap_x = 46
    helper_gap_y = 40
    placed_dims = set()

    def place_row(names: list[str], center_x: float, y: float, gap_x: int = row_gap_x):
        if not names:
            return
        total_w = sum(width(name) for name in names) + gap_x * (len(names) - 1)
        cursor_x = center_x - total_w / 2
        for name in names:
            positions[name] = (cursor_x, y)
            cursor_x += width(name) + gap_x

    def place_helper_cluster(owner_name: str, side_bias: int = 1, below: bool = True):
        owned_helpers = [name for name, owner in helper_owner.items() if owner == owner_name]
        if owner_name not in positions or not owned_helpers:
            return
        owner_x, owner_y = positions[owner_name]
        owner_w = width(owner_name)
        owner_h = height(owner_name)
        sorted_helpers = sorted(owned_helpers)
        columns = min(2, len(sorted_helpers))
        rows = math.ceil(len(sorted_helpers) / columns)
        col_widths = []
        for column_index in range(columns):
            column_items = sorted_helpers[column_index::columns]
            col_widths.append(max(width(name) for name in column_items))
        total_w = sum(col_widths) + helper_gap_x * (columns - 1)
        start_x = owner_x + (owner_w - total_w) / 2 + side_bias * 18
        anchor_y = owner_y + owner_h + 56 if below else owner_y - 56

        for index, helper_name in enumerate(sorted_helpers):
            row_index = index // columns
            column_index = index % columns
            helper_x = start_x + sum(col_widths[:column_index]) + helper_gap_x * column_index
            if below:
                helper_y = anchor_y + row_index * (height(helper_name) + helper_gap_y)
            else:
                helper_y = anchor_y - (rows - row_index) * (height(helper_name) + helper_gap_y)
            positions[helper_name] = (helper_x, helper_y)

    def place_arc(names: list[str], center_x: float, fact_top_y: float, fact_bottom_y: float, top: bool):
        if not names:
            return
        radius_x = max(280, 180 + len(names) * 80)
        radius_y = 260 if top else 230
        base_angle = math.pi if top else 0
        spread = min(math.pi * 0.9, math.pi * 0.28 * max(len(names) - 1, 1))
        step = spread / max(len(names) - 1, 1)
        start_angle = base_angle - spread / 2

        for index, name in enumerate(names):
            angle = start_angle + index * step
            node_center_x = center_x + math.cos(angle) * radius_x
            node_center_y = (
                fact_top_y + math.sin(angle) * radius_y
                if top
                else fact_bottom_y + math.sin(angle) * radius_y
            )
            positions[name] = (
                node_center_x - width(name) / 2,
                node_center_y - height(name) / 2,
            )

    def place_child_fan(parent_name: str, child_names: list[str], direction: str):
        if parent_name not in positions or not child_names:
            return
        parent_x, parent_y = positions[parent_name]
        parent_w = width(parent_name)
        parent_h = height(parent_name)
        gap_x = 86
        gap_y = 30
        if direction == "right":
            child_x = parent_x + parent_w + 120
        else:
            max_child_w = max(width(name) for name in child_names)
            child_x = parent_x - 120 - max_child_w
        total_h = sum(height(name) for name in child_names) + gap_y * (len(child_names) - 1)
        cursor_y = parent_y + parent_h / 2 - total_h / 2
        for child_name in child_names:
            positions[child_name] = (child_x, cursor_y)
            cursor_y += height(child_name) + gap_y

    snowflake_children = {child for children in snowflake.values() for child in children}

    def role_rank(name: str) -> int:
        if name in facts:
            return 0
        if name in dims and name not in snowflake_children:
            return 1
        if name in snowflake_children:
            return 2
        if name in helper_tables:
            return 3
        return 4

    def resolve_overlaps():
        margin_x = 56
        margin_y = 40
        for _ in range(80):
            moved = False
            names = sorted(
                positions,
                key=lambda name: (role_rank(name), positions[name][1], positions[name][0]),
            )
            for index, left_name in enumerate(names):
                if left_name not in positions:
                    continue
                ax, ay = positions[left_name]
                aw, ah = width(left_name), height(left_name)
                for right_name in names[index + 1 :]:
                    if right_name not in positions:
                        continue
                    bx, by = positions[right_name]
                    bw, bh = width(right_name), height(right_name)
                    overlap_x = min(ax + aw + margin_x, bx + bw + margin_x) - max(ax, bx)
                    overlap_y = min(ay + ah + margin_y, by + bh + margin_y) - max(ay, by)
                    if overlap_x <= 0 or overlap_y <= 0:
                        continue

                    left_rank = role_rank(left_name)
                    right_rank = role_rank(right_name)
                    if left_rank < right_rank:
                        move_name = right_name
                        anchor_name = left_name
                    elif right_rank < left_rank:
                        move_name = left_name
                        anchor_name = right_name
                    else:
                        move_name = right_name
                        anchor_name = left_name

                    mx, my = positions[move_name]
                    ax2, ay2 = positions[anchor_name]
                    anchor_cx = ax2 + width(anchor_name) / 2
                    move_cx = mx + width(move_name) / 2
                    horizontal_bias = -1 if move_cx < anchor_cx else 1

                    if overlap_x < overlap_y:
                        shift_x = overlap_x + 28
                        positions[move_name] = (mx + horizontal_bias * shift_x, my)
                    else:
                        shift_y = overlap_y + 28
                        if role_rank(move_name) >= 3:
                            vertical_bias = 1
                        else:
                            anchor_cy = ay2 + height(anchor_name) / 2
                            move_cy = my + height(move_name) / 2
                            vertical_bias = -1 if move_cy < anchor_cy else 1
                        positions[move_name] = (mx, my + vertical_bias * shift_y)
                    moved = True
            if not moved:
                break

        for _ in range(20):
            moved = False
            names = sorted(
                positions,
                key=lambda name: (role_rank(name), positions[name][1], positions[name][0]),
            )
            for index, left_name in enumerate(names):
                ax, ay = positions[left_name]
                aw, ah = width(left_name), height(left_name)
                for right_name in names[index + 1 :]:
                    bx, by = positions[right_name]
                    bw, bh = width(right_name), height(right_name)
                    overlap_x = min(ax + aw, bx + bw) - max(ax, bx)
                    overlap_y = min(ay + ah, by + bh) - max(ay, by)
                    if overlap_x <= 0 or overlap_y <= 0:
                        continue

                    left_rank = role_rank(left_name)
                    right_rank = role_rank(right_name)
                    move_name = right_name if left_rank <= right_rank else left_name
                    anchor_name = left_name if move_name == right_name else right_name
                    mx, my = positions[move_name]
                    ax2, ay2 = positions[anchor_name]
                    anchor_cx = ax2 + width(anchor_name) / 2
                    move_cx = mx + width(move_name) / 2
                    anchor_cy = ay2 + height(anchor_name) / 2
                    move_cy = my + height(move_name) / 2

                    if overlap_x <= overlap_y:
                        shift_x = overlap_x + 36
                        positions[move_name] = (
                            mx + (-shift_x if move_cx < anchor_cx else shift_x),
                            my,
                        )
                    else:
                        shift_y = overlap_y + 36
                        positions[move_name] = (
                            mx,
                            my + (-shift_y if move_cy < anchor_cy else shift_y),
                        )
                    moved = True
            if not moved:
                break

    fact_centers = {}
    for index, fact_name in enumerate(fact_order):
        if index == 0:
            center_x = 0
        else:
            band = (index + 1) // 2
            center_x = fact_spacing_x * band * (-1 if index % 2 else 1)
        fact_centers[fact_name] = center_x
        positions[fact_name] = (
            center_x - width(fact_name) / 2,
            cluster_center_y - height(fact_name) / 2,
        )

    if shared_dims:
        shared_y = cluster_center_y - top_gap_y - 40
        shared_sorted = sorted(
            shared_dims,
            key=lambda name: sum(fact_centers[fact_name] for fact_name in dim_usage.get(name, set())) / max(len(dim_usage.get(name, set())), 1),
        )
        place_row(shared_sorted, 0, shared_y, gap_x=140)
        for dim_name in shared_sorted:
            placed_dims.add(dim_name)

    for fact_name in fact_order:
        center_x = fact_centers[fact_name]
        fact_x, fact_y = positions[fact_name]
        direct_dims = [name for name in direct_dims_by_fact.get(fact_name, []) if name not in shared_dims]
        top_dims = sorted(direct_dims[: math.ceil(len(direct_dims) / 2)])
        bottom_dims = sorted(direct_dims[math.ceil(len(direct_dims) / 2) :])
        fact_top_y = fact_y - 70
        fact_bottom_y = fact_y + height(fact_name) + 70

        place_arc(top_dims, center_x, fact_top_y, fact_bottom_y, True)
        place_arc(bottom_dims, center_x, fact_top_y, fact_bottom_y, False)

        for dim_name in top_dims + bottom_dims:
            placed_dims.add(dim_name)
            child_names = [
                child for child in snowflake.get(dim_name, []) if child not in helper_children
            ]
            if not child_names or dim_name not in positions:
                continue
            dim_center_x = positions[dim_name][0] + width(dim_name) / 2
            place_child_fan(
                dim_name,
                sorted(child_names),
                "left" if dim_center_x < center_x else "right",
            )
            placed_dims.update(child_names)
            for child_name in child_names:
                child_center_x = positions[child_name][0] + width(child_name) / 2
                place_helper_cluster(
                    child_name,
                    -1 if child_center_x < center_x else 1,
                    below=child_name not in top_dims,
                )

        place_helper_cluster(fact_name, 1, below=True)
        for dim_name in top_dims + bottom_dims:
            dim_center_x = positions[dim_name][0] + width(dim_name) / 2
            place_helper_cluster(
                dim_name,
                -1 if dim_center_x < center_x else 1,
                below=dim_name in bottom_dims,
            )
    for dim_name in shared_dims:
        child_names = [child for child in snowflake.get(dim_name, []) if child not in helper_children]
        if child_names and dim_name in positions:
            used_by = sorted(dim_usage.get(dim_name, set()))
            avg_center_x = sum(fact_centers.get(name, 0) for name in used_by) / max(len(used_by), 1)
            direction = "left" if avg_center_x >= 0 else "right"
            place_child_fan(dim_name, sorted(child_names), direction)
            placed_dims.update(child_names)
        place_helper_cluster(dim_name, 1, below=True)

    remaining_dims = [
        name
        for name in dims
        if name not in placed_dims and name not in positions and name not in helper_children
    ]
    if remaining_dims:
        row_y = max((y + height(name) for name, (_, y) in positions.items()), default=0) + 220
        place_row(sorted(remaining_dims), 0, row_y, gap_x=70)
        for dim_name in sorted(remaining_dims):
            place_helper_cluster(dim_name, 1, below=True)

    remaining_helpers = [name for name in helper_tables if name not in positions]
    if remaining_helpers:
        cursor_x = min((x for x, _ in positions.values()), default=0)
        row_y = max((y + height(name) for name, (_, y) in positions.items()), default=0) + 180
        for helper_name in sorted(remaining_helpers):
            positions[helper_name] = (cursor_x, row_y)
            cursor_x += width(helper_name) + 60

    if others:
        non_helper_others = [name for name in others if name not in helper_tables]
        if non_helper_others:
            row_y = max((y + height(name) for name, (_, y) in positions.items()), default=0) + 220
            cursor_x = min((x for x, _ in positions.values()), default=0)
            for other_name in sorted(non_helper_others):
                positions[other_name] = (cursor_x, row_y)
                cursor_x += width(other_name) + 70

    resolve_overlaps()

    return table_names, facts, dims, snowflake, positions, node_sizes


def _get_table_role(name: str, facts: list[str], dims: list[str], snowflake: dict[str, list[str]]) -> str:
    all_snowflake_children = {child for children in snowflake.values() for child in children}
    if name in facts:
        return "fact"
    if name in all_snowflake_children:
        return "snowflake"
    if name in dims:
        return "dimension"
    return "other"


def _build_diagram_graph(relations: list[dict], table_columns: dict[str, list[str]]) -> dict:
    (
        table_names,
        facts,
        dims,
        snowflake,
        positions,
        node_sizes,
    ) = _build_diagram_positions(relations, table_columns)

    relationship_fields = {}
    for relation in relations:
        relationship_fields.setdefault(relation["from"], set()).add(relation.get("from_column", ""))
        relationship_fields.setdefault(relation["to"], set()).add(relation.get("to_column", ""))

    min_x = min((x for x, _ in positions.values()), default=0)
    min_y = min((y for _, y in positions.values()), default=0)
    pad = 80

    def normalize_xy(name: str) -> tuple[float, float]:
        x, y = positions[name]
        return x - min_x + pad, y - min_y + pad

    nodes = []
    for name in table_names:
        if name not in positions:
            continue
        x, y = normalize_xy(name)
        width, height = node_sizes[name]
        role = _get_table_role(name, facts, dims, snowflake)
        fields = relationship_fields.get(name, set())
        columns = [
            {
                "name": column,
                "isRelationship": column in fields,
            }
            for column in table_columns.get(name, [])
        ]
        nodes.append(
            {
                "id": name,
                "type": "tableNode",
                "position": {"x": round(x, 1), "y": round(y, 1)},
                "data": {
                    "label": name,
                    "role": role,
                    "columns": columns,
                    "width": width,
                    "height": height,
                },
                "draggable": True,
            }
        )

    edges = []
    for index, relation in enumerate(relations):
        if relation.get("filter_direction") == "single":
            source_table = relation.get("filter_from") or relation["from"]
            target_table = relation.get("filter_to") or relation["to"]
        else:
            source_table = relation["from"]
            target_table = relation["to"]

        if source_table == relation["from"]:
            source_column = relation.get("from_column", "")
            source_cardinality = relation.get("from_cardinality", "?")
        else:
            source_column = relation.get("to_column", "")
            source_cardinality = relation.get("to_cardinality", "?")

        if target_table == relation["to"]:
            target_column = relation.get("to_column", "")
            target_cardinality = relation.get("to_cardinality", "?")
        else:
            target_column = relation.get("from_column", "")
            target_cardinality = relation.get("from_cardinality", "?")

        source_x = positions.get(source_table, (0, 0))[0]
        target_x = positions.get(target_table, (0, 0))[0]
        if source_x <= target_x:
            source_side = "right"
            target_side = "left"
        else:
            source_side = "left"
            target_side = "right"

        source_handle = f'{source_side}-source::{source_column or "__default__"}'
        target_handle = f'{target_side}-target::{target_column or "__default__"}'
        edges.append(
            {
                "id": f"edge-{index}",
                "source": source_table,
                "target": target_table,
                "sourceHandle": source_handle,
                "targetHandle": target_handle,
                "type": "relationshipEdge",
                "data": {
                    "fromColumn": source_column,
                    "toColumn": target_column,
                    "fromCardinality": source_cardinality,
                    "toCardinality": target_cardinality,
                    "cardinalityLabel": relation.get("cardinality_label", "?"),
                    "direction": relation.get("filter_direction", "unknown"),
                    "directionLabel": relation.get("direction_label", "?"),
                    "rawFromTable": relation["from"],
                    "rawToTable": relation["to"],
                },
            }
        )

    return {"nodes": nodes, "edges": edges}


def _build_diagram_svg(relations: list[dict], table_columns: dict[str, list[str]], texts: dict[str, str]) -> str:
    table_names, facts, dims, _, positions, node_sizes = _build_diagram_positions(
        relations, table_columns
    )

    if not positions:
        return f"<p>{escape(texts['no_relationships_to_render'])}</p>"

    pad = 80
    min_x = min(x for x, _ in positions.values())
    min_y = min(y for _, y in positions.values())
    max_x = max(x + node_sizes[n][0] for n, (x, _) in positions.items())
    max_y = max(y + node_sizes[n][1] for n, (_, y) in positions.items())
    width = int(max_x - min_x + pad * 2)
    height = int(max_y - min_y + pad * 2)

    def normalize_xy(name: str) -> tuple[float, float]:
        x, y = positions[name]
        return x - min_x + pad, y - min_y + pad

    header_height = 34
    row_height = 24

    def column_anchor(name: str, column_name: str, prefer_right: bool) -> tuple[float, float]:
        x, y = normalize_xy(name)
        width, height = node_sizes[name]
        columns = table_columns.get(name, [])
        if column_name in columns:
            row_index = columns.index(column_name)
        else:
            row_index = 0
        max_rows = max(1, min(len(columns), 18))
        row_index = min(row_index, max_rows - 1)
        anchor_y = y + header_height + row_height * row_index + row_height / 2
        anchor_x = x + width if prefer_right else x
        if not columns:
            anchor_y = y + height / 2
        return anchor_x, anchor_y

    relation_lines = []
    relation_annotations = []
    for rel in relations:
        src = rel["from"]
        dst = rel["to"]
        if src not in positions or dst not in positions:
            continue
        src_x, src_y = normalize_xy(src)
        dst_x, dst_y = normalize_xy(dst)
        src_w, src_h = node_sizes[src]
        dst_w, dst_h = node_sizes[dst]
        src_center_x = src_x + src_w / 2
        dst_center_x = dst_x + dst_w / 2
        from_on_right = src_center_x <= dst_center_x
        to_on_right = dst_center_x < src_center_x
        x1, y1 = column_anchor(src, rel.get("from_column", ""), from_on_right)
        x2, y2 = column_anchor(dst, rel.get("to_column", ""), to_on_right)
        mid_x = (x1 + x2) / 2
        label_x = mid_x
        label_y = y1 + (y2 - y1) / 2

        relation_lines.append(
            f'<path class="relation-line" data-src="{escape(src)}" data-dst="{escape(dst)}" '
            f'd="M {x1:.1f} {y1:.1f} L {mid_x:.1f} {y1:.1f} L {mid_x:.1f} {y2:.1f} L {x2:.1f} {y2:.1f}" '
            'stroke="#8b98a7" stroke-width="2" fill="none" />'
        )
        relation_annotations.append(
            f'<text x="{x1 - 10 if from_on_right else x1 + 10:.1f}" y="{y1 + 4:.1f}" '
            f'text-anchor="{"end" if from_on_right else "start"}" '
            'font-family="Segoe UI, Arial" font-size="12" font-weight="700" fill="#475569">'
            f'{escape(rel["from_cardinality"])}</text>'
        )
        relation_annotations.append(
            f'<text x="{x2 + 10 if to_on_right else x2 - 10:.1f}" y="{y2 + 4:.1f}" '
            f'text-anchor="{"start" if to_on_right else "end"}" '
            'font-family="Segoe UI, Arial" font-size="12" font-weight="700" fill="#475569">'
            f'{escape(rel["to_cardinality"])}</text>'
        )
        if rel["direction_label"] != "?":
            relation_annotations.append(
                f'<g class="relation-annotation" data-src="{escape(src)}" data-dst="{escape(dst)}" '
                f'transform="translate({label_x:.1f},{label_y:.1f})">'
                '<rect x="-48" y="-18" width="96" height="24" rx="12" ry="12" fill="#ffffff" stroke="#d7dee7" />'
                f'<text x="0" y="-2" text-anchor="middle" font-family="Segoe UI, Arial" font-size="11" fill="#334155">'
                f'{escape(rel["cardinality_label"])}'
                '</text>'
                f'<text x="0" y="10" text-anchor="middle" font-family="Segoe UI, Arial" font-size="10" fill="#64748b">'
                f'{escape(rel["direction_label"])}'
                '</text>'
                '</g>'
            )

    nodes = []
    for name in table_names:
        if name not in positions:
            continue
        x, y = normalize_xy(name)
        w, h = node_sizes[name]
        columns = table_columns.get(name, [])
        if name in facts:
            fill = "#ffffff"
            stroke = "#3b82f6"
            header_fill = "#2b579a"
        elif name in dims:
            fill = "#ffffff"
            stroke = "#9d4edd"
            header_fill = "#74489d"
        else:
            fill = "#ffffff"
            stroke = "#64748b"
            header_fill = "#4b5563"

        column_rows = []
        for index, column in enumerate(columns):
            row_y = header_height + row_height * index
            column_rows.append(
                f'<line x1="0" y1="{row_y:.1f}" x2="{w}" y2="{row_y:.1f}" stroke="#e5e7eb" stroke-width="1" />'
            )
            column_rows.append(
                f'<text x="14" y="{row_y + 16:.1f}" font-family="Segoe UI, Arial" '
                f'font-size="12" fill="#334155">{escape(column)}</text>'
            )

        nodes.append(
            (
                f'<g class="node" data-name="{escape(name)}" data-width="{w}" data-height="{h}" '
                f'transform="translate({x:.1f},{y:.1f})">'
                f'<rect x="4" y="4" rx="10" ry="10" width="{w}" height="{h}" fill="#000000" opacity="0.07" />'
                f'<rect x="0" y="0" rx="10" ry="10" width="{w}" height="{h}" '
                f'fill="{fill}" stroke="{stroke}" stroke-width="2" />'
                f'<rect x="0" y="0" rx="10" ry="10" width="{w}" height="{header_height}" fill="{header_fill}" />'
                f'<rect x="0" y="{header_height - 10}" width="{w}" height="10" fill="{header_fill}" />'
                f'<text x="14" y="22" font-family="Segoe UI, Arial" font-size="13" font-weight="700" fill="#ffffff">{escape(name)}</text>'
                + "".join(column_rows)
                + "</g>"
            )
        )

    return (
        f'<svg id="relationship-diagram" viewBox="0 0 {width} {height}" width="100%" height="640" '
        f'xmlns="http://www.w3.org/2000/svg" role="img" aria-label="{escape(texts["diagram_aria_label"])}">'
        '<rect width="100%" height="100%" fill="#f8fafc" />'
        '<g id="relationship-content">'
        '<g id="relationship-edges">'
        + "".join(relation_lines)
        + "</g>"
        + '<g id="relationship-annotations">'
        + "".join(relation_annotations)
        + "</g>"
        + '<g id="relationship-nodes">'
        + "".join(nodes)
        + "</g>"
        + "</g>"
        + "</svg>"
    )


@app.get("/")
def index():
    locale = _get_request_locale()
    return _render_index(locale)


@app.get("/health")
def health():
    return jsonify({"status": "ok", "utc": datetime.now(timezone.utc).isoformat()})


@app.post("/api/extract-relations")
def extract_relations_api():
    locale = _get_request_locale()
    texts = get_translations(locale)
    uploaded_file = request.files.get("file")

    if not uploaded_file or not uploaded_file.filename:
        return jsonify({"error": texts["upload_missing_error"], "locale": locale}), 400

    if not _is_allowed_file(uploaded_file.filename):
        return jsonify({"error": texts["invalid_format_error"], "locale": locale}), 400

    try:
        insights = _extract_model_insights(uploaded_file)
    except Exception as exc:
        return (
            jsonify(
                {
                    "error": texts["extract_failed_error"].format(error=exc),
                    "locale": locale,
                }
            ),
            400,
        )

    enriched_relations = _infer_relationship_metadata(
        insights["relations"], insights.get("tables", [])
    )
    table_columns = insights.get("table_columns", {})
    diagram_svg = _build_diagram_svg(enriched_relations, table_columns, texts)
    diagram_graph = _build_diagram_graph(enriched_relations, table_columns)
    return jsonify(
        {
            "locale": locale,
            "file_name": uploaded_file.filename,
            **{**insights, "relations": enriched_relations},
            "diagram_svg": diagram_svg,
            "diagram_graph": diagram_graph,
        }
    )


@app.post("/extract")
def extract_relations_ui():
    locale = _get_request_locale()
    texts = get_translations(locale)
    uploaded_file = request.files.get("file")

    if not uploaded_file or not uploaded_file.filename:
        return _render_index(locale, error=texts["upload_missing_error"]), 400

    if not _is_allowed_file(uploaded_file.filename):
        return _render_index(locale, error=texts["invalid_format_ui_error"]), 400

    try:
        insights = _extract_model_insights(uploaded_file)
    except Exception as exc:
        return _render_index(
            locale,
            error=texts["process_failed_error"].format(error=exc),
        ), 400

    enriched_relations = _infer_relationship_metadata(
        insights["relations"], insights.get("tables", [])
    )
    table_columns = insights.get("table_columns", {})
    diagram_svg = _build_diagram_svg(enriched_relations, table_columns, texts)
    diagram_graph = _build_diagram_graph(enriched_relations, table_columns)
    result = {
        "file_name": uploaded_file.filename,
        **{**insights, "relations": enriched_relations},
        "diagram_svg": diagram_svg,
        "diagram_graph": diagram_graph,
    }
    return _render_index(locale, result=result)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
