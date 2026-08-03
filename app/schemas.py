from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


LayoutType = Literal["surrounding_table", "face_to_face", "side_table_and_rows"]


class Attendee(BaseModel):
    employee_id: str | None = None
    name: str = Field(min_length=1)
    department: str = ""
    organization: str = ""
    administrative_title: str = ""
    professional_title: str = ""
    priority: int = 0
    seat_preference: str | None = None

    @field_validator("name")
    @classmethod
    def trim_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("name 不能为空")
        return value


class SeatingRules(BaseModel):
    seat_count: int | None = Field(default=None, ge=1, le=300)
    keep_department_together: bool = False
    order_by: list[Literal["priority", "administrative_title", "department", "name"]] = Field(
        default_factory=lambda: ["priority", "administrative_title", "department", "name"]
    )


class Adjustment(BaseModel):
    type: Literal["assign", "swap", "reserve", "clear"]
    seat_id: str | None = None
    attendee_name: str | None = None
    seat_a: str | None = None
    seat_b: str | None = None
    label: str | None = None


class Seat(BaseModel):
    seat_id: str
    zone: str
    index: int
    role: Literal["host", "attendee", "reserved", "empty"] = "empty"
    attendee: Attendee | None = None
    label: str | None = None


class SeatingPlan(BaseModel):
    seat_plan_id: str
    meeting_title: str = "会议座位图"
    layout_type: LayoutType
    host_name: str | None = None
    seats: list[Seat]
    unassigned_attendees: list[Attendee] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class RenderOptions(BaseModel):
    output_formats: list[Literal["svg", "png", "pdf"]] = Field(default_factory=lambda: ["svg", "png"])
    paper: Literal["A4-landscape", "A4-portrait"] = "A4-landscape"
    show_fields: list[Literal["name", "administrative_title", "department"]] = Field(
        default_factory=lambda: ["name", "administrative_title"]
    )
    filename: str = "会议座位图"
    theme: Literal["formal"] = "formal"


def as_model_list(items: list[dict[str, Any]] | list[Attendee]) -> list[Attendee]:
    return [item if isinstance(item, Attendee) else Attendee.model_validate(item) for item in items]
