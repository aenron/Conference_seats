from app.personnel_service import PUBLIC_CANDIDATE_FIELDS, PERSONNEL_VIEW_FIELD_DEFAULTS


def test_public_candidate_fields_exclude_private_identifiers():
    assert PUBLIC_CANDIDATE_FIELDS == (
        "name",
        "department",
        "organization",
        "professional_title",
        "management_post_level",
        "administrative_title",
    )
    assert "employee_id" not in PUBLIC_CANDIDATE_FIELDS
    assert "post_level" not in PUBLIC_CANDIDATE_FIELDS


def test_new_personnel_view_uses_leadership_title_field():
    assert PERSONNEL_VIEW_FIELD_DEFAULTS["professional_title"] == (
        "PERSONNEL_COL_PROFESSIONAL_TITLE", "PRZYJSZW"
    )
    assert PERSONNEL_VIEW_FIELD_DEFAULTS["management_post_level"] == (
        "PERSONNEL_COL_MANAGEMENT_POST_LEVEL", "PRGLGWDJ"
    )
    assert PERSONNEL_VIEW_FIELD_DEFAULTS["administrative_title"] == (
        "PERSONNEL_COL_ADMINISTRATIVE_TITLE", "LDZWMC"
    )
