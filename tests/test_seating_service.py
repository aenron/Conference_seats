from app.schemas import Adjustment, Attendee, SeatingRules
from app.seating_service import create_plan


def people():
    return [Attendee(name="张三", administrative_title="院长", priority=10), Attendee(name="李四", department="办公室"), Attendee(name="王五", department="办公室")]


def test_surrounding_assigns_host_and_everyone():
    plan = create_plan(meeting_title="测试会议", layout_type="surrounding_table", attendees=people(), host_name="张三", rules=SeatingRules(seat_count=5), adjustments=[], existing_plan_id=None)
    assert next(seat for seat in plan.seats if seat.role == "host").attendee.name == "张三"
    assert not plan.unassigned_attendees


def test_short_capacity_warns_and_adjustment_reserves():
    plan = create_plan(meeting_title="测试会议", layout_type="face_to_face", attendees=people(), host_name="张三", rules=SeatingRules(seat_count=2), adjustments=[Adjustment(type="reserve", seat_id="top-01", label="嘉宾")], existing_plan_id=None)
    assert plan.unassigned_attendees
    assert any("未安排座位" in warning for warning in plan.warnings)
    assert next(seat for seat in plan.seats if seat.seat_id == "top-01").role == "reserved"
