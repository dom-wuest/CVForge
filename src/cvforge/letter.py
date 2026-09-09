"""Load -> validate -> derive -> write build/letter-<slug>.json.

The letter's sibling to resolve.py, and it works the same way: the Typst
renderer reads the resolved JSON and nothing else.

The one structural difference is where the sender comes from. A letter names
nobody but the recipient; your own name, tagline, contacts, address and
signature are read from the CV and from data/private.yaml, so a letterhead
cannot drift out of step with the CV it is stapled to. That is why this module
calls resolve.resolve() rather than reimplementing it.

A letter is always profile=full - it carries a postal address by definition -
and is never exported. There is deliberately no --profile flag for it.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from . import dates, i18n, paths, resolve
from .resolve import ResolveError

# Keys of the structured address in data/private.yaml, in the order a German
# letter prints them. `country` is last and usually absent.
ADDRESS_KEYS = ("street", "postal_code", "city", "country")

# Shown when data/private.yaml is missing, so the letter still builds on a
# fresh clone rather than failing - the same promise the CV makes.
PLACEHOLDER_ADDRESS = {
    "street": "Musterstraße 1",
    "postal_code": "00000",
    "city": "Musterstadt",
    "country": None,
}


# ─────────────────────────────────────────────────────────────────────────────
# Private data
# ─────────────────────────────────────────────────────────────────────────────


def private_letter() -> tuple[dict[str, Any], list[str]]:
    """The sender's postal address and signature, from data/private.yaml.

    Returns (values, notes). Never raises for a missing file: a fresh clone
    builds a letter with a placeholder address and a typed name, and says so.
    """
    notes: list[str] = []

    if not paths.PRIVATE.is_file():
        notes.append(
            "no data/private.yaml; using a placeholder address and no signature "
            "(copy data/private.example.yaml to start)"
        )
        return {"address": dict(PLACEHOLDER_ADDRESS), "signature": None}, notes

    private = resolve.load_yaml(paths.PRIVATE)

    address = private.get("address") or {}
    if not isinstance(address, dict):
        raise ResolveError("data/private.yaml: `address` must be a mapping")
    unknown = sorted(set(address) - set(ADDRESS_KEYS))
    if unknown:
        notes.append(f"data/private.yaml: ignoring unknown address key(s): {', '.join(unknown)}")
    resolved_address = {key: address.get(key) or None for key in ADDRESS_KEYS}

    missing = [k for k in ("street", "postal_code", "city") if not resolved_address[k]]
    if missing:
        for key in missing:
            resolved_address[key] = PLACEHOLDER_ADDRESS[key]
        notes.append(
            "data/private.yaml has no `address` block; using placeholders for: "
            + ", ".join(missing)
        )

    signature = private.get("signature") or None
    if signature:
        # A missing signature file is a hard Typst error, not a blank space, so
        # it is dropped here with a note rather than blowing up the compile.
        if (paths.ROOT / signature).is_file():
            notes.append(f"signature: {signature}")
        else:
            notes.append(f"signature file not found, using the typed name only: {signature}")
            signature = None
    else:
        notes.append("data/private.yaml declares no `signature`; using the typed name only")

    return {"address": resolved_address, "signature": signature}, notes


# ─────────────────────────────────────────────────────────────────────────────
# Derivation
# ─────────────────────────────────────────────────────────────────────────────


def _return_line(name: str, address: dict[str, Any]) -> str:
    """The small line above the address field, for a window envelope.

    DIN 5008 separates its parts with a middle dot; it exists so a letter that
    cannot be delivered finds its way back without opening the envelope.
    """
    city = " ".join(p for p in (address.get("postal_code"), address.get("city")) if p)
    parts = [name, address.get("street"), city]
    return " · ".join(p for p in parts if p)


def _reference_label(data: dict[str, Any], labels: dict[str, str]) -> str:
    """What this employer calls their reference number.

    Every career portal has its own word for it - Kennziffer, Referenznummer,
    Job-ID, Role ID, Req ID - and quoting the posting's own term back is the
    whole point of printing the number at all. So the label is per application,
    not per language, and `labels.subject_reference` is only the fallback.

    One value for both places it appears: the info block and the subject line
    disagreeing about what the number is called would read as a mistake.
    """
    return data["job"].get("reference_label") or labels["subject_reference"]


def subject_line(data: dict[str, Any], labels: dict[str, str]) -> str:
    """'Bewerbung als Rendering Engineer – Kennziffer REQ-2026-114'.

    DIN 5008 prints the subject without the word "Betreff", so neither does
    this. An explicit `subject` in the YAML wins.
    """
    if data.get("subject"):
        return data["subject"]

    subject = f"{labels['subject_prefix']} {data['job']['title']}"
    reference = data["job"].get("reference")
    if reference:
        subject += f"{i18n.META_SEP}{_reference_label(data, labels)} {reference}"
    return subject


def _info_block(data: dict[str, Any], labels: dict[str, str]) -> list[dict[str, Any]]:
    """The block beside the address field: reference and where you found it.

    `source` is a full phrase in the letter's own language rather than a
    labelled field, because "Ihre Anzeige auf StepStone vom 04.09.2026" is one
    idea and splitting it into portal + date would only make it harder to word.
    """
    block: list[dict[str, Any]] = []
    if data["job"].get("reference"):
        block.append({"label": _reference_label(data, labels), "value": data["job"]["reference"]})
    if data["job"].get("source"):
        block.append({"label": None, "value": data["job"]["source"]})
    return block


def _sender_contacts(
    contacts: list[dict[str, Any]], wanted: list[str] | None
) -> list[dict[str, Any]]:
    """Pick the letterhead contacts, in the order the CV lists them.

    Ordering by the CV rather than by `sender_contacts` is deliberate: the two
    documents should present the same identity the same way round, and the
    letter's list is a filter, not a layout instruction.
    """
    if not wanted:
        return contacts
    keep = set(wanted)
    return [c for c in contacts if c["id"] in keep]


def derive(data: dict[str, Any], slug: str, cv: dict[str, Any], private: dict) -> dict[str, Any]:
    """Assemble the artifact the Typst letter template reads."""
    lang = data["meta"]["lang"]
    labels = i18n.letter_labels(lang)
    data = resolve.clean(data)

    recipient = data["recipient"]
    address = private["address"]

    return {
        "meta": {
            "lang": lang,
            "slug": slug,
            # Stamped after validation, exactly as the CV does it - this is a
            # property of the build, not of the source, so it is not in the
            # schema. Nothing may publish an artifact that is not "public",
            # and a letter never is.
            "profile": "full",
            "doctype": "letter",
            "name": cv["meta"]["name"],
            "tagline": cv["meta"]["tagline"],
            "date_display": dates.display_day(data["meta"].get("date"), lang),
        },
        "sender": {
            "address": address,
            "return_line": _return_line(cv["meta"]["name"], address),
            "contacts": _sender_contacts(cv["contacts"], data.get("sender_contacts")),
            "signature": private["signature"],
        },
        "recipient": {
            "company": recipient["company"],
            "department": recipient.get("department"),
            "person": recipient.get("person"),
            "street": recipient.get("street"),
            "postal_code": recipient.get("postal_code"),
            "city": recipient.get("city"),
            "country": recipient.get("country"),
        },
        "info": _info_block(data, labels),
        "subject": subject_line(data, labels),
        "salutation": recipient.get("salutation") or labels["salutation_default"],
        "body": data["body"],
        "closing": data.get("closing") or labels["closing"],
        "enclosures": data.get("enclosures") or [],
        "labels": labels,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Entry points
# ─────────────────────────────────────────────────────────────────────────────


def validate_letter(data: dict[str, Any], slug: str) -> None:
    source = paths.letter_source(slug)
    resolve.validate_against(data, paths.LETTER_SCHEMA, paths.display(source))

    declared = data["meta"]["slug"]
    if declared != slug:
        raise ResolveError(
            f"at $.meta.slug: declared {declared!r} but the file is "
            f"{paths.display(source)}. A copied letter builds under the wrong "
            f"name otherwise."
        )


def resolve_letter(slug: str) -> tuple[dict[str, Any], list[str]]:
    source = paths.letter_source(slug)
    if not source.is_file():
        known = (
            sorted(
                p.name
                for p in paths.APPLICATIONS.glob("*")
                # _template is the scaffold, not something you can build
                if p.is_dir() and not p.name.startswith("_")
            )
            if paths.APPLICATIONS.is_dir()
            else []
        )
        hint = f" Known applications: {', '.join(known)}." if known else ""
        raise ResolveError(
            f"no such application: {paths.display(source)}."
            f" Create it with `cvforge new {slug}`.{hint}"
        )

    data = resolve.load_yaml(source)
    validate_letter(data, slug)

    lang = data["meta"]["lang"]
    if not paths.source(lang).is_file():
        raise ResolveError(
            f"{paths.display(source)} declares lang={lang!r}, but "
            f"{paths.display(paths.source(lang))} does not exist"
        )

    # The sender identity IS the CV's, resolved the same way. `full` is not a
    # choice here: a letter without a postal address is not a letter.
    cv, cv_notes = resolve.resolve(lang, "full", quiet=True)

    unknown = sorted(set(data.get("sender_contacts") or []) - {c["id"] for c in cv["contacts"]})
    if unknown:
        raise ResolveError(
            f"at $.sender_contacts: no contact with id(s) {', '.join(unknown)} in "
            f"{paths.display(paths.source(lang))}"
        )

    private, notes = private_letter()
    return derive(data, slug, cv, private), cv_notes + notes


def write_letter(slug: str, *, quiet: bool = False) -> Path:
    data, notes = resolve_letter(slug)
    target = paths.letter_resolved(slug)
    target.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False)
    target.write_text(text + "\n", encoding="utf-8")
    if not quiet:
        for note in notes:
            print(f"  note: {note}")
        print(f"  wrote {paths.display(target)}  (slug={slug}, lang={data['meta']['lang']})")
    return target
