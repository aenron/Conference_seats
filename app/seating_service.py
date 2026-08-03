from __future__ import annotations

import json
import uuid
from pathlib import Path

from app.schemas import Adjustment, Attendee, LayoutType, Seat, SeatingPlan, SeatingRules


GENERATED_DIR = Path("generated_files")
PLAN_DIR = GENERATED_DIR / "plans"


def _seat_specs(layout_type: LayoutType, requested_count: int | None) -> list[tuple[str, int]]:
    defaults: dict[str, list[tuple[str, int]]] = {
        "surrounding_table": [("top", 7), ("right", 5), ("bottom", 7), ("left", 5)],
        "face_to_face": [("top", 10), ("bottom", 10)],
        "side_table_and_rows": [("head_table", 6), ("row_1", 5), ("row_2", 5), ("row_3", 5)],
    }
    specs = defaults[layout_type]
    if requested_count is None:
        return specs
    seats: list[tuple[str, int]] = []
    zones = [name for name, _ in specs]
    for index in range(requested_count):
        seats.append((zones[index % len(zones)], index // len(zones) + 1))
    return seats


def _rank(attendee: Attendee, rules: SeatingRules) -> tuple:
    title_rank = {"院长": 100, "副院长": 90, "所长": 80, "副所长": 70, "主任": 60, "副主任": 50, "处长": 40, "副处长": 30}
    output = []
    for field in rules.order_by:
        if field == "priority": output.append(-attendee.priority)
        elif field == "administrative_title": output.append(-title_rank.get(attendee.administrative_title, 0))
        else: output.append(getattr(attendee, field) or "")
    return tuple(output)


def _ordered(attendees: list[Attendee], rules: SeatingRules) -> list[Attendee]:
    return sorted(attendees, key=lambda item: _rank(item, rules))


def _save(plan: SeatingPlan) -> None:
    PLAN_DIR.mkdir(parents=True, exist_ok=True)
    (PLAN_DIR / f"{plan.seat_plan_id}.json").write_text(plan.model_dump_json(indent=2), encoding="utf-8")


def load_plan(seat_plan_id: str) -> SeatingPlan:
    path = PLAN_DIR / f"{seat_plan_id}.json"
    if not path.exists():
        raise ValueError(f"未找到座位方案: {seat_plan_id}")
    return SeatingPlan.model_validate_json(path.read_text(encoding="utf-8"))


def _warnings(plan: SeatingPlan, original: list[Attendee]) -> list[str]:
    result: list[str] = []
    assigned = [seat.attendee.name for seat in plan.seats if seat.attendee]
    duplicates = sorted({name for name in assigned if assigned.count(name) > 1})
    if duplicates: result.append("人员被重复安排：" + "、".join(duplicates))
    originals = {person.name for person in original}
    unexpected = sorted(set(assigned) - originals)
    if unexpected: result.append("安排了不在参会名单中的人员：" + "、".join(unexpected))
    if plan.unassigned_attendees: result.append("以下人员未安排座位：" + "、".join(person.name for person in plan.unassigned_attendees))
    if plan.host_name and not any(seat.role == "host" and seat.attendee and seat.attendee.name == plan.host_name for seat in plan.seats):
        result.append("主持人未安排至主持席：" + plan.host_name)
    return result


def _apply_adjustments(plan: SeatingPlan, attendees: list[Attendee], adjustments: list[Adjustment]) -> None:
    by_id = {seat.seat_id: seat for seat in plan.seats}
    by_name = {person.name: person for person in attendees}
    for operation in adjustments:
        if operation.type == "swap":
            if not operation.seat_a or not operation.seat_b or operation.seat_a not in by_id or operation.seat_b not in by_id:
                plan.warnings.append("换座操作的 seat_a 或 seat_b 无效")
                continue
            first, second = by_id[operation.seat_a], by_id[operation.seat_b]
            first.attendee, second.attendee = second.attendee, first.attendee
            first.role, second.role = second.role, first.role
        else:
            if not operation.seat_id or operation.seat_id not in by_id:
                plan.warnings.append("调整操作的 seat_id 无效")
                continue
            seat = by_id[operation.seat_id]
            if operation.type == "clear": seat.attendee, seat.role, seat.label = None, "empty", None
            elif operation.type == "reserve": seat.attendee, seat.role, seat.label = None, "reserved", operation.label or "预留"
            elif operation.type == "assign":
                person = by_name.get(operation.attendee_name or "")
                if not person:
                    plan.warnings.append(f"无法安排不存在的人员：{operation.attendee_name or ''}")
                else: seat.attendee, seat.role, seat.label = person, "attendee", None


def create_plan(*, meeting_title: str, layout_type: LayoutType, attendees: list[Attendee], host_name: str | None, rules: SeatingRules, adjustments: list[Adjustment], existing_plan_id: str | None) -> SeatingPlan:
    names = [person.name for person in attendees]
    duplicate_names = sorted({name for name in names if names.count(name) > 1})
    if existing_plan_id:
        plan = load_plan(existing_plan_id)
        if plan.layout_type != layout_type:
            raise ValueError("更新方案时 layout_type 必须与原方案一致")
        plan.meeting_title, plan.host_name = meeting_title or plan.meeting_title, host_name or plan.host_name
    else:
        specs = _seat_specs(layout_type, rules.seat_count)
        seats = [Seat(seat_id=f"{zone}-{index:02d}", zone=zone, index=index) for zone, index in specs]
        plan = SeatingPlan(seat_plan_id=f"plan-{uuid.uuid4().hex[:12]}", meeting_title=meeting_title, layout_type=layout_type, host_name=host_name, seats=seats)
        ordered = _ordered(attendees, rules)
        host = next((person for person in ordered if person.name == host_name), None)
        host_seat = next((seat for seat in seats if seat.zone in ("top", "head_table")), seats[0] if seats else None)
        if host and host_seat:
            host_seat.attendee, host_seat.role = host, "host"
            ordered.remove(host)
        empty_seats = [seat for seat in seats if not seat.attendee]
        for seat, person in zip(empty_seats, ordered): seat.attendee, seat.role = person, "attendee"
    plan.warnings = []
    _apply_adjustments(plan, attendees, adjustments)
    assigned_names = {seat.attendee.name for seat in plan.seats if seat.attendee}
    plan.unassigned_attendees = [person for person in attendees if person.name not in assigned_names]
    plan.warnings.extend(_warnings(plan, attendees))
    if duplicate_names: plan.warnings.append("参会名单存在重名：" + "、".join(duplicate_names))
    _save(plan)
    return plan
