from datetime import UTC, datetime


def parse_datetime(value):
    if not value:
        return None
    try:
        result = datetime.fromisoformat(value)
    except (ValueError, AttributeError):
        return None
    return result.replace(tzinfo=UTC) if result.tzinfo is None else result


def revival_score(lead, now=None):
    """Explainable heuristic score from 0-100; not a predictive model."""
    now = now or datetime.now(timezone.utc)
    status = str(lead.get("status", "new")).lower()
    if lead.get("opted_out") or status in {"won", "lost", "do_not_contact", "unqualified"}:
        return {"score": 0, "reasons": [f"Lead status is {status}; do not prioritize."]}
    score, reasons = 20, ["Base score for an active lead."]
    last = parse_datetime(lead.get("last_contact_at"))
    if last:
        days = max(0, (now - last).days)
        if days >= 30:
            score += 30
        elif days >= 14:
            score += 22
        elif days >= 7:
            score += 14
        elif days >= 3:
            score += 6
        if days >= 3:
            reasons.append(f"No contact for {days} days.")
    else:
        score += 10
        reasons.append("No last-contact date recorded; verify contact history.")
    due = parse_datetime(lead.get("next_follow_up_at"))
    if due and due <= now:
        score += 20
        reasons.append("A follow-up is due or overdue.")
    try:
        value = float(lead.get("deal_value") or 0)
    except (TypeError, ValueError):
        value = 0
    if value >= 10000:
        score += 15
        reasons.append("High deal value (>= 10,000).")
    elif value >= 1000:
        score += 8
        reasons.append("Meaningful deal value (>= 1,000).")
    if status in {"proposal", "negotiation"}:
        score += 10
        reasons.append(f"Lead is in the {status} stage.")
    return {"score": min(100, score), "reasons": reasons}
