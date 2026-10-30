from datetime import UTC, datetime

from app.rules import revival_score

NOW = datetime(2026, 10, 31, tzinfo=UTC)

def test_due_stale_high_value_lead_gets_high_priority():
    result = revival_score({"status":"proposal","last_contact_at":"2026-09-01T00:00:00+00:00","next_follow_up_at":"2026-10-01T00:00:00+00:00","deal_value":12000}, now=NOW)
    assert result["score"] == 95
    assert any("overdue" in reason for reason in result["reasons"])

def test_do_not_contact_is_not_prioritized():
    assert revival_score({"status":"do_not_contact"}, now=NOW)["score"] == 0

def test_missing_contact_history_is_explained():
    result = revival_score({"status":"new"}, now=NOW)
    assert result["score"] == 30
    assert any("No last-contact date" in reason for reason in result["reasons"])

def test_maximum_current_priority_combination_scores_95():
    result = revival_score({"status":"negotiation","last_contact_at":"2026-01-01T00:00:00+00:00","next_follow_up_at":"2026-01-01T00:00:00+00:00","deal_value":50000}, now=NOW)
    assert result["score"] == 95
