import datetime


def iso_duration(delta: datetime.timedelta) -> str:
    """A timedelta as an ISO 8601 duration, written as recent pydantic writes one: P1DT2H3M4.5S,
    PT0S for none, and a leading - for a negative one (-PT1M30S)."""
    sign = "-" if delta < datetime.timedelta(0) else ""
    delta = abs(delta)
    hours, rest = divmod(delta.seconds, 3600)
    minutes, seconds = divmod(rest, 60)
    date = f"{delta.days}D" if delta.days else ""
    time = "".join(
        f"{amount}{unit}" for amount, unit in ((hours, "H"), (minutes, "M")) if amount
    ) + _seconds(seconds, delta.microseconds)
    if not date and not time:
        return "PT0S"
    return f"{sign}P{date}" + (f"T{time}" if time else "")


def _seconds(seconds: int, microseconds: int) -> str:
    if not seconds and not microseconds:
        return ""
    if not microseconds:
        return f"{seconds}S"
    return f"{seconds}.{microseconds:06d}".rstrip("0") + "S"
