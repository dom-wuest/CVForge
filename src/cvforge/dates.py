"""Parsing and localised formatting of the "YYYY" / "YYYY-MM" date strings.

Precision is carried by the string's length, not by a separate field: "2023"
means year precision and renders as `2023`, "2021-10" means month precision and
renders as `Oct 2021`. Everything downstream consumes the formatted string, so
this module is the only place that knows month names.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

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
