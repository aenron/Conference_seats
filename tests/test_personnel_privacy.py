from app.personnel_service import PUBLIC_CANDIDATE_FIELDS


def test_public_candidate_fields_exclude_private_identifiers():
    assert PUBLIC_CANDIDATE_FIELDS == (
        "name",
        "department",
        "organization",
        "professional_title",
        "administrative_title",
    )
    assert "employee_id" not in PUBLIC_CANDIDATE_FIELDS
    assert "post_level" not in PUBLIC_CANDIDATE_FIELDS
