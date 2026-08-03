from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import uvicorn
from mcp.server.fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse

from app.personnel_service import PersonnelConfigurationError, PersonnelQueryError, query_personnel
from app.schemas import Adjustment, Attendee, RenderOptions, SeatingRules
from app.seating_service import GENERATED_DIR, create_plan, load_plan
from app.svg_renderer import render_svg


mcp = FastMCP("conference-seats-mcp")
BASE_URL = os.getenv("MCP_DOWNLOAD_BASE_URL", "http://127.0.0.1:8100").rstrip("/")


@mcp.tool(name="query_personnel_candidates", description="根据姓名、部门、单位、行政职务或专业技术职务查询参会人员候选名单。返回 candidates 明细和可用于排位的 attendees。所有数组字段传 [] 而不能传 null。")
def query_personnel_candidates(name_keywords: list[str] = [], department_keywords: list[str] = [], organization_keywords: list[str] = [], administrative_title_keywords: list[str] = [], professional_title_keywords: list[str] = [], exclude_keywords: list[str] = [], include_all: bool = False, limit: int = 100) -> dict[str, Any]:
    try:
        data = query_personnel(name_keywords=name_keywords, department_keywords=department_keywords, organization_keywords=organization_keywords, administrative_title_keywords=administrative_title_keywords, professional_title_keywords=professional_title_keywords, exclude_keywords=exclude_keywords, include_all=include_all, limit=limit)
        return {"code": 200, "success": True, "message": "personnel candidates queried successfully", "data": data}
    except (ValueError, PersonnelConfigurationError) as exc:
        return {"code": 400, "success": False, "message": str(exc), "data": {}}
    except PersonnelQueryError as exc:
        return {"code": 500, "success": False, "message": str(exc), "data": {}}


@mcp.tool(name="create_seating_plan", description="生成或更新会议座位方案，并自动校验。layout_type 仅支持 surrounding_table（中央桌四周围坐）、face_to_face（两排相对）和 side_table_and_rows（一侧主桌、另一侧多排）。attendees 必须是人员对象数组，每项至少含 name。若传 existing_plan_id 则在原方案上应用 adjustments；adjustments 支持 assign、swap、reserve、clear。返回 seats、unassigned_attendees、warnings，确认后将 seat_plan_id 交给 render_seating_chart 出图。")
def create_seating_plan(meeting_title: str, layout_type: str, attendees: list[dict[str, Any]], host_name: str | None = None, rules: dict[str, Any] | None = None, adjustments: list[dict[str, Any]] | None = None, existing_plan_id: str | None = None) -> dict[str, Any]:
    try:
        plan = create_plan(meeting_title=meeting_title, layout_type=layout_type, attendees=[Attendee.model_validate(item) for item in attendees], host_name=host_name, rules=SeatingRules.model_validate(rules or {}), adjustments=[Adjustment.model_validate(item) for item in (adjustments or [])], existing_plan_id=existing_plan_id)
        return {"code": 200, "success": True, "message": "seating plan created successfully", "data": plan.model_dump()}
    except Exception as exc:
        return {"code": 400, "success": False, "message": str(exc), "data": {}}


@mcp.tool(name="render_seating_chart", description="将 create_seating_plan 返回的 seat_plan_id 渲染为图形。output_formats 可选 svg、png、pdf；SVG 是主文件。show_fields 可选 name、administrative_title、department。返回可下载文件地址。")
def render_seating_chart(seat_plan_id: str, output_formats: list[str] = ["svg", "png"], paper: str = "A4-landscape", show_fields: list[str] = ["name", "administrative_title"], filename: str = "会议座位图") -> dict[str, Any]:
    try:
        plan, options = load_plan(seat_plan_id), RenderOptions.model_validate({"output_formats": output_formats, "paper": paper, "show_fields": show_fields, "filename": filename})
        safe_name = "".join(char for char in options.filename if char not in '\\/:*?\"<>|').strip() or "会议座位图"
        directory = GENERATED_DIR / "charts" / seat_plan_id
        svg_path = directory / f"{safe_name}.svg"
        render_svg(plan, options, svg_path)
        paths: dict[str, Path] = {"svg": svg_path}
        requested = set(options.output_formats)
        if requested - {"svg"}:
            try:
                import cairosvg
                if "png" in requested:
                    png_path = directory / f"{safe_name}.png"; cairosvg.svg2png(url=str(svg_path), write_to=str(png_path), output_width=2246); paths["png"] = png_path
                if "pdf" in requested:
                    pdf_path = directory / f"{safe_name}.pdf"; cairosvg.svg2pdf(url=str(svg_path), write_to=str(pdf_path)); paths["pdf"] = pdf_path
            except Exception as exc:
                return {
                    "code": 200,
                    "success": True,
                    "message": "SVG 已生成；部分附加格式导出失败",
                    "data": {
                        "svg_url": f"{BASE_URL}/api/v1/download/{seat_plan_id}/{svg_path.name}",
                        "warnings": [f"PNG/PDF 导出失败：{exc}"],
                    },
                }
        data = {f"{kind}_url": f"{BASE_URL}/api/v1/download/{seat_plan_id}/{path.name}" for kind, path in paths.items()}
        return {"code": 200, "success": True, "message": "seating chart rendered successfully", "data": data}
    except Exception as exc:
        return {"code": 400, "success": False, "message": str(exc), "data": {}}


async def download(request: Request) -> FileResponse | JSONResponse:
    plan_id, filename = request.path_params["plan_id"], request.path_params["filename"]
    path = GENERATED_DIR / "charts" / plan_id / filename
    if not path.exists() or path.parent.name != plan_id:
        return JSONResponse({"detail": "file not found"}, status_code=404)
    media = {".svg": "image/svg+xml", ".png": "image/png", ".pdf": "application/pdf"}.get(path.suffix, "application/octet-stream")
    return FileResponse(path, media_type=media, filename=path.name)


if __name__ == "__main__":
    app = mcp.sse_app()
    app.add_route("/api/v1/download/{plan_id}/{filename}", download, methods=["GET"])
    uvicorn.run(app, host="0.0.0.0", port=8100)
