"""把结构化知识树渲染为可持久化、可点击放大的 SVG 思维导图。"""

from __future__ import annotations

import hashlib
import html
import json
import math
from datetime import datetime
from typing import Any

from database import get_db

NODE_WIDTH = 210
NODE_HEIGHT = 58
DEPTH_GAP = 92
ROW_GAP = 26
PALETTE = (
    ("#26345D", "#FFFFFF", "#26345D"),
    ("#EEF2FF", "#303A63", "#8997D8"),
    ("#EAF8F3", "#225849", "#7FC8AF"),
    ("#FFF4E6", "#704D23", "#E6B875"),
)


def _clean_node(node: Any, depth: int = 0, budget: list[int] | None = None) -> dict | None:
    if budget is None:
        budget = [32]
    if budget[0] <= 0 or depth > 3 or not isinstance(node, dict):
        return None
    label = str(node.get("label") or node.get("name") or "").strip()[:60]
    if not label:
        return None
    budget[0] -= 1
    children = []
    for child in node.get("children") or []:
        cleaned = _clean_node(child, depth + 1, budget)
        if cleaned:
            children.append(cleaned)
    return {"label": label, "children": children}


def _wrap_label(label: str, width: int = 12) -> list[str]:
    value = label.strip()
    if len(value) <= width:
        return [value]
    return [value[:width], value[width : width * 2 - 1] + ("…" if len(value) > width * 2 - 1 else "")]


def render_mind_map_svg(root: dict, title: str) -> str:
    """稳定的左到右树布局；连接线和节点文字均为真正 SVG 元素。"""
    positions: dict[int, tuple[int, float, dict]] = {}
    leaf_cursor = [0]
    max_depth = [0]

    def assign(node: dict, depth: int) -> float:
        max_depth[0] = max(max_depth[0], depth)
        children = node.get("children") or []
        if children:
            child_y = [assign(child, depth + 1) for child in children]
            y = sum(child_y) / len(child_y)
        else:
            y = float(leaf_cursor[0])
            leaf_cursor[0] += 1
        positions[id(node)] = (depth, y, node)
        return y

    assign(root, 0)
    rows = max(1, leaf_cursor[0])
    width = 90 + (max_depth[0] + 1) * NODE_WIDTH + max_depth[0] * DEPTH_GAP + 70
    height = max(360, 112 + rows * (NODE_HEIGHT + ROW_GAP))
    top = 82

    def xy(node: dict) -> tuple[float, float]:
        depth, row, _ = positions[id(node)]
        x = 54 + depth * (NODE_WIDTH + DEPTH_GAP)
        if rows == 1:
            y = height / 2 - NODE_HEIGHT / 2 + 20
        else:
            y = top + row * (NODE_HEIGHT + ROW_GAP)
        return x, y

    connectors: list[str] = []
    nodes: list[str] = []

    def draw(node: dict) -> None:
        depth = positions[id(node)][0]
        x, y = xy(node)
        fill, text_color, border = PALETTE[min(depth, len(PALETTE) - 1)]
        for child in node.get("children") or []:
            child_x, child_y = xy(child)
            start_x, start_y = x + NODE_WIDTH, y + NODE_HEIGHT / 2
            end_x, end_y = child_x, child_y + NODE_HEIGHT / 2
            bend = max(36, (end_x - start_x) * 0.48)
            connectors.append(
                f'<path d="M {start_x:.1f} {start_y:.1f} '
                f'C {start_x + bend:.1f} {start_y:.1f}, '
                f'{end_x - bend:.1f} {end_y:.1f}, {end_x:.1f} {end_y:.1f}" '
                f'fill="none" stroke="#AEB7D0" stroke-width="2.2" />'
            )
            draw(child)

        label_lines = _wrap_label(str(node.get("label") or ""))
        text_y = y + (24 if len(label_lines) == 2 else 35)
        tspans = "".join(
            f'<tspan x="{x + NODE_WIDTH / 2:.1f}" dy="{0 if index == 0 else 19}">'
            f"{html.escape(line)}</tspan>"
            for index, line in enumerate(label_lines)
        )
        nodes.append(
            f'<g class="mind-node depth-{depth}">'
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{NODE_WIDTH}" height="{NODE_HEIGHT}" '
            f'rx="16" fill="{fill}" stroke="{border}" stroke-width="1.6" />'
            f'<text x="{x + NODE_WIDTH / 2:.1f}" y="{text_y:.1f}" '
            f'text-anchor="middle" fill="{text_color}" font-size="15" '
            f'font-weight="{700 if depth == 0 else 600}">{tspans}</text></g>'
        )

    draw(root)
    escaped_title = html.escape(title)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'role="img" aria-label="{escaped_title}思维导图">'
        '<rect width="100%" height="100%" fill="#FBFCFF"/>'
        '<defs><filter id="shadow" x="-20%" y="-20%" width="140%" height="140%">'
        '<feDropShadow dx="0" dy="4" stdDeviation="6" flood-color="#28345F" flood-opacity=".08"/>'
        '</filter></defs>'
        f'<text x="54" y="43" fill="#26345D" font-size="21" font-weight="700">{escaped_title}</text>'
        '<text x="54" y="65" fill="#8B94AA" font-size="12">点击可放大查看 · 已持久保存</text>'
        f'<g filter="url(#shadow)">{"".join(connectors)}{"".join(nodes)}</g>'
        "</svg>"
    )


def persist_mind_map(user_id: int, title: str, root: dict) -> dict:
    cleaned = _clean_node(root) or {"label": title[:60] or "知识导图", "children": []}
    title = str(title or cleaned["label"]).strip()[:100]
    svg = render_mind_map_svg(cleaned, title)
    payload = json.dumps({"title": title, "root": cleaned}, ensure_ascii=False)
    digest = hashlib.sha256(
        f"mind-map:{user_id}:{payload}".encode("utf-8")
    ).hexdigest()
    conn = get_db()
    existing = conn.execute(
        "SELECT id, svg_content FROM generated_images WHERE user_id = ? AND prompt_hash = ? LIMIT 1",
        (user_id, digest),
    ).fetchone()
    if existing:
        map_id = int(existing["id"])
        svg = existing["svg_content"] or svg
    else:
        conn.execute(
            """INSERT INTO generated_images
               (user_id, prompt_hash, prompt_text, svg_content, file_path, provider, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                user_id,
                digest,
                payload,
                svg,
                "",
                "deterministic-mind-map-v1",
                datetime.now().isoformat(),
            ),
        )
        conn.commit()
        row = conn.execute(
            "SELECT id FROM generated_images WHERE user_id = ? AND prompt_hash = ? LIMIT 1",
            (user_id, digest),
        ).fetchone()
        map_id = int(row["id"])
    conn.close()
    return {
        "id": map_id,
        "title": title,
        "root": cleaned,
        "svg": svg,
        "persistent": True,
    }


def get_mind_map(user_id: int, map_id: int) -> dict | None:
    conn = get_db()
    row = conn.execute(
        """SELECT id, prompt_text, svg_content, created_at
           FROM generated_images
           WHERE id = ? AND user_id = ? AND provider = 'deterministic-mind-map-v1'""",
        (map_id, user_id),
    ).fetchone()
    conn.close()
    if not row:
        return None
    data = json.loads(row["prompt_text"] or "{}")
    return {
        "id": int(row["id"]),
        "title": data.get("title", "思维导图"),
        "root": data.get("root") or {},
        "svg": row["svg_content"] or "",
        "created_at": row["created_at"],
        "persistent": True,
    }
