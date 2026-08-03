"""Parameterised personnel-view query compatible with llm2word configuration."""
from __future__ import annotations

import os
import re
from typing import Any


class PersonnelConfigurationError(RuntimeError):
    pass


class PersonnelQueryError(RuntimeError):
    pass


_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_$#]*$")


def _column(name: str, default: str) -> str:
    value = os.getenv(name, default).strip()
    if not _IDENTIFIER.fullmatch(value):
        raise PersonnelConfigurationError(f"{name} 不是合法的数据库标识符")
    return value


def _keywords(values: list[str] | None, field: str) -> list[str]:
    if values is None:
        raise ValueError(f"{field} 不能为 null")
    return list(dict.fromkeys(item.strip() for item in values if isinstance(item, str) and item.strip()))


def _database_url_from_env() -> str:
    """Build the same SQLAlchemy URLs supported by llm2word's personnel service."""
    database_type = os.getenv("PERSONNEL_DB_TYPE", "").strip().lower()
    host = os.getenv("PERSONNEL_DB_HOST", "").strip()
    port_text = os.getenv("PERSONNEL_DB_PORT", "").strip()
    username = os.getenv("PERSONNEL_DB_USER", "").strip()
    password = os.getenv("PERSONNEL_DB_PASSWORD", "")
    database = os.getenv("PERSONNEL_DB_NAME", "").strip()
    service_name = os.getenv("PERSONNEL_DB_SERVICE_NAME", database).strip()
    missing = [name for name, value in {
        "PERSONNEL_DB_TYPE": database_type, "PERSONNEL_DB_HOST": host,
        "PERSONNEL_DB_PORT": port_text, "PERSONNEL_DB_USER": username,
        "PERSONNEL_DB_PASSWORD": password,
    }.items() if not value]
    if missing:
        raise PersonnelConfigurationError("未配置 PERSONNEL_DATABASE_URL，且缺少分项配置：" + "、".join(missing))
    try:
        port = int(port_text)
    except ValueError as exc:
        raise PersonnelConfigurationError("PERSONNEL_DB_PORT 必须是整数") from exc
    try:
        from sqlalchemy.engine import URL
    except ImportError as exc:
        raise PersonnelConfigurationError("未安装 SQLAlchemy") from exc
    if database_type in {"oracle", "oracle+oracledb"}:
        if not service_name:
            raise PersonnelConfigurationError("Oracle 连接还需要 PERSONNEL_DB_SERVICE_NAME")
        url = URL.create("oracle+oracledb", username=username, password=password, host=host, port=port, query={"service_name": service_name})
    elif database_type in {"postgres", "postgresql", "postgresql+psycopg"}:
        if not database:
            raise PersonnelConfigurationError("PostgreSQL 连接还需要 PERSONNEL_DB_NAME")
        url = URL.create("postgresql+psycopg", username=username, password=password, host=host, port=port, database=database)
    elif database_type in {"mysql", "mysql+pymysql"}:
        if not database:
            raise PersonnelConfigurationError("MySQL 连接还需要 PERSONNEL_DB_NAME")
        url = URL.create("mysql+pymysql", username=username, password=password, host=host, port=port, database=database, query={"charset": "utf8mb4"})
    else:
        raise PersonnelConfigurationError("PERSONNEL_DB_TYPE 当前支持 oracle、postgresql、mysql")
    return url.render_as_string(hide_password=False)


def query_personnel(*, name_keywords: list[str], department_keywords: list[str], organization_keywords: list[str], administrative_title_keywords: list[str], professional_title_keywords: list[str], exclude_keywords: list[str], include_all: bool, limit: int) -> dict[str, Any]:
    if not 1 <= limit <= 500:
        raise ValueError("limit 必须在 1 到 500 之间")
    url, view = os.getenv("PERSONNEL_DATABASE_URL", "").strip(), os.getenv("PERSONNEL_DB_VIEW", "").strip()
    if not url:
        url = _database_url_from_env()
    if not view:
        raise PersonnelConfigurationError("未配置 PERSONNEL_DB_VIEW")
    schema = os.getenv("PERSONNEL_DB_SCHEMA", "").strip()
    if schema and not _IDENTIFIER.fullmatch(schema):
        raise PersonnelConfigurationError("PERSONNEL_DB_SCHEMA 不是合法的数据库标识符")
    if not _IDENTIFIER.fullmatch(view):
        raise PersonnelConfigurationError("PERSONNEL_DB_VIEW 不是合法的数据库标识符")

    cols = {key: _column(env, default) for key, env, default in [
        ("employee_id", "PERSONNEL_COL_EMPLOYEE_ID", "GH"), ("name", "PERSONNEL_COL_NAME", "XM"),
        ("department", "PERSONNEL_COL_DEPARTMENT", "SZBM"), ("organization", "PERSONNEL_COL_ORGANIZATION", "SZDW"),
        ("professional_title", "PERSONNEL_COL_PROFESSIONAL_TITLE", "PRZYJSZW"),
        ("post_level", "PERSONNEL_COL_POST_LEVEL", "PRGLGWDJ"), ("administrative_title", "PERSONNEL_COL_ADMINISTRATIVE_TITLE", "XZZWMC"),
    ]}
    filters = [("name", _keywords(name_keywords, "name_keywords")), ("department", _keywords(department_keywords, "department_keywords")), ("organization", _keywords(organization_keywords, "organization_keywords")), ("administrative_title", _keywords(administrative_title_keywords, "administrative_title_keywords")), ("professional_title", _keywords(professional_title_keywords, "professional_title_keywords"))]
    excluded = _keywords(exclude_keywords, "exclude_keywords")
    if not include_all and not any(words for _, words in filters):
        raise ValueError("至少提供一个人员筛选关键词；查询全部人员时设置 include_all=true")
    params: dict[str, str] = {}
    clauses: list[str] = []
    n = 0
    for key, words in filters:
        choices = []
        for word in words:
            p = f"p{n}"; n += 1
            params[p] = "%" + word.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
            choices.append(f"COALESCE({cols[key]}, ' ') LIKE :{p} ESCAPE '\\'")
        if choices: clauses.append("(" + " OR ".join(choices) + ")")
    for word in excluded:
        choices = []
        for key in ("name", "department", "organization", "administrative_title", "professional_title"):
            p = f"p{n}"; n += 1; params[p] = f"%{word}%"
            choices.append(f"COALESCE({cols[key]}, ' ') LIKE :{p}")
        clauses.append("NOT (" + " OR ".join(choices) + ")")
    qualified = f"{schema}.{view}" if schema else view
    select = ", ".join(f"{column} AS {alias}" for alias, column in cols.items())
    sql = f"SELECT {select} FROM {qualified}" + (" WHERE " + " AND ".join(clauses) if clauses else "") + f" ORDER BY {cols['department']}, {cols['name']}"
    try:
        from sqlalchemy import create_engine, text
        engine = create_engine(url, pool_pre_ping=True)
        with engine.connect() as connection:
            rows = [dict(row._mapping) for row in connection.execute(text(sql), params).fetchmany(limit + 1)]
        engine.dispose()
    except Exception as exc:
        raise PersonnelQueryError("人员视图查询失败，请检查数据库连接、视图和字段映射") from exc
    candidates, truncated = rows[:limit], len(rows) > limit
    attendees = list(dict.fromkeys(str(row.get("name") or "").strip() for row in candidates if row.get("name")))
    return {"attendees": attendees, "candidates": candidates, "returned_count": len(candidates), "unique_attendee_count": len(attendees), "truncated": truncated}
