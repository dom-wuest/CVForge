"""Parsing and localised formatting of the "YYYY" / "YYYY-MM" date strings.

Precision is carried by the string's length, not by a separate field: "2023"
means year precision and renders as `2023`, "2021-10" means month precision and
renders as `Oct 2021`. Everything downstream consumes the formatted string, so
this module is the only place that knows month names.

A cover letter's dateline is the one place day precision appears; it has its
own pattern and its own formatter at the bottom of this file, deliberately not
sharing DATE_RE - see the comment there.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

DATE_RE = re.compile(r"^(?P<year>[0-9]{4})(?:-(?P<month>0[1-9]|1[0-2]))?$")

# Abbreviations as they should appear in the rendered CV.
MONTHS: dict[str, list[str]] = {
    "en": ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
    "de": [
        "Jan.",
        "Feb.",
        "März",
        "Apr.",
        "Mai",
        "Juni",
        "Juli",
        "Aug.",
        "Sep.",
        "Okt.",
        "Nov.",
        "Dez.",
    ],
}

# Full month names, for the dateline of a cover letter. A letter is dated to
# the day and spells the month out - "8. September 2026", never "8. Sep. 2026".
MONTHS_FULL: dict[str, list[str]] = {
    "en": [
        "January",
        "February",
        "March",
        "April",
        "May",
        "June",
        "July",
        "August",
        "September",
        "October",
        "November",
        "December",
    ],
    "de": [
        "Januar",
        "Februar",
        "März",
        "April",
        "Mai",
        "Juni",
        "Juli",
        "August",
        "September",
        "Oktober",
        "November",
        "Dezember",
    ],
}

# Day precision is a separate pattern rather than an optional group on DATE_RE:
# a CV entry must NOT accept "2021-10-04", and a letter date must not accept a
# bare "2021". Keeping them apart lets each schema say exactly what it means.
DAY_RE = re.compile(
    r"^(?P<year>[0-9]{4})-(?P<month>0[1-9]|1[0-2])-(?P<day>0[1-9]|[12][0-9]|3[01])$"
)


class DateError(ValueError):
    """A date string that the schema should have rejected."""


@dataclass(frozen=True)
class CvDate:
    year: int
    month: int | None  # None = year precision

    @property
    def iso(self) -> str:
        """Machine-readable form, for HTML `<time datetime="...">`."""
        return f"{self.year:04d}-{self.month:02d}" if self.month else f"{self.year:04d}"

    def display(self, lang: str) -> str:
        if self.month is None:
            return str(self.year)
        months = MONTHS.get(lang) or MONTHS["en"]
        return f"{months[self.month - 1]} {self.year}"


def parse(value: str) -> CvDate:
    """Parse "YYYY" or "YYYY-MM".

    Raises DateError on anything else, including the non-str values YAML
    produces from an unquoted `2021-10` (a datetime.date) - the schema catches
    those first, but this stays defensive because resolve() is also importable.
    """
    if not isinstance(value, str):
        raise DateError(
            f"expected a quoted date string, got {type(value).__name__} {value!r}. "
            'Quote it: "2021-10".'
        )
    m = DATE_RE.match(value)
    if not m:
        raise DateError(f'invalid date {value!r}, expected "YYYY" or "YYYY-MM"')
    month = m.group("month")
    return CvDate(int(m.group("year")), int(month) if month else None)


def display(value: str | None, lang: str, ongoing: str) -> str:
    """Format a date for display, substituting `ongoing` when it is absent."""
    return ongoing if value is None else parse(value).display(lang)


def iso(value: str | None) -> str | None:
    return None if value is None else parse(value).iso


def parse_day(value: str) -> date:
    """Parse "YYYY-MM-DD" into a real date.

    Defensive about non-str for the same reason as parse(): an unquoted
    2026-09-08 in YAML arrives here as a datetime.date already.
    """
    if isinstance(value, date):
        return value
    if not isinstance(value, str):
        raise DateError(
            f"expected a quoted date string, got {type(value).__name__} {value!r}. "
            'Quote it: "2026-09-08".'
        )
    m = DAY_RE.match(value)
    if not m:
        raise DateError(f'invalid date {value!r}, expected "YYYY-MM-DD"')
    try:
        return date(int(m.group("year")), int(m.group("month")), int(m.group("day")))
    except ValueError as exc:  # 2026-02-30 matches the pattern but is not a day
        raise DateError(f"invalid date {value!r}: {exc}") from None


def display_day(value: str | None, lang: str) -> str:
    """Format a full date the way a letter is dated in that language.

    de: "8. September 2026"   en: "8 September 2026"

    None means today, which is what an undated letter should say - the date on
    a cover letter is the date you send it, so defaulting to the build date is
    the correct behaviour rather than a convenience.
    """
    day = date.today() if value is None else parse_day(value)
    months = MONTHS_FULL.get(lang) or MONTHS_FULL["en"]
    month = months[day.month - 1]
    return f"{day.day}. {month} {day.year}" if lang == "de" else f"{day.day} {month} {day.year}"
