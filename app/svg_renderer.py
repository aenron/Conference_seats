from __future__ import annotations

from html import escape
from pathlib import Path

from app.schemas import RenderOptions, Seat, SeatingPlan


def _text(seat: Seat, fields: list[str]) -> list[str]:
    if seat.role == "reserved": return [seat.label or "预留"]
    if not seat.attendee: return ["空座"]
    values = []
    for field in fields:
        value = getattr(seat.attendee, field, "")
        if value: values.append(str(value))
    return values or [seat.attendee.name]


def _positions(plan: SeatingPlan) -> dict[str, tuple[int, int]]:
    seats = plan.seats; result = {}
    groups: dict[str, list[Seat]] = {}
    for seat in seats: groups.setdefault(seat.zone, []).append(seat)
    def line(group: list[Seat], start: tuple[int, int], step: tuple[int, int]):
        for i, seat in enumerate(group): result[seat.seat_id] = (start[0] + i * step[0], start[1] + i * step[1])
    if plan.layout_type == "surrounding_table":
        line(groups.get("top", []), (180, 100), (100, 0)); line(groups.get("bottom", []), (180, 610), (100, 0)); line(groups.get("left", []), (80, 200), (0, 80)); line(groups.get("right", []), (880, 200), (0, 80))
    elif plan.layout_type == "face_to_face":
        line(groups.get("top", []), (120, 210), (90, 0)); line(groups.get("bottom", []), (120, 500), (90, 0))
    else:
        line(groups.get("head_table", []), (85, 130), (0, 80))
        for row, y in zip(("row_1", "row_2", "row_3"), (200, 370, 540)): line(groups.get(row, []), (380, y), (115, 0))
    return result


def render_svg(plan: SeatingPlan, options: RenderOptions, output: Path) -> None:
    width, height = (1123, 794) if options.paper == "A4-landscape" else (794, 1123)
    positions = _positions(plan)
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 1123 794">', '<rect width="1123" height="794" fill="#ffffff"/>', '<style>text{font-family:"Microsoft YaHei","Noto Sans CJK SC",sans-serif;fill:#17212b}.title{font-size:28px;font-weight:700}.seat{font-size:15px}.sub{font-size:12px;fill:#526170}</style>', f'<text class="title" x="561" y="48" text-anchor="middle">{escape(plan.meeting_title)}</text>']
    if plan.layout_type == "surrounding_table": parts.append('<rect x="180" y="190" width="740" height="350" rx="12" fill="#edf2f5" stroke="#506270" stroke-width="3"/><text x="550" y="370" text-anchor="middle" font-size="24">会议桌</text>')
    elif plan.layout_type == "face_to_face": parts.append('<rect x="100" y="320" width="900" height="90" rx="12" fill="#edf2f5" stroke="#506270" stroke-width="3"/><text x="550" y="375" text-anchor="middle" font-size="22">会议桌</text>')
    else: parts.append('<rect x="170" y="100" width="100" height="570" rx="10" fill="#edf2f5" stroke="#506270" stroke-width="3"/><text x="220" y="400" text-anchor="middle" transform="rotate(-90 220 400)" font-size="20">主桌</text>')
    for seat in plan.seats:
        x, y = positions.get(seat.seat_id, (0, 0)); fill = "#fff" if seat.role in ("attendee", "empty") else "#fff5d7" if seat.role == "reserved" else "#dceaf7"; stroke = "#1e5f8f" if seat.role == "host" else "#8796a3"
        parts.append(f'<rect x="{x}" y="{y}" width="82" height="52" rx="7" fill="{fill}" stroke="{stroke}" stroke-width="{3 if seat.role == "host" else 1}"/>')
        lines = _text(seat, options.show_fields)
        for i, line in enumerate(lines[:2]): parts.append(f'<text class="{"seat" if i == 0 else "sub"}" x="{x + 41}" y="{y + 22 + i * 16}" text-anchor="middle">{escape(line)}</text>')
    parts.append('<text x="1040" y="760" text-anchor="end" class="sub">深色边框：主持人　浅黄：预留</text></svg>')
    output.parent.mkdir(parents=True, exist_ok=True); output.write_text("".join(parts), encoding="utf-8")
