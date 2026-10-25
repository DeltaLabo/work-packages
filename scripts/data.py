"""Preserve the original CSV schema, IDs, entered text and unknown columns."""

import csv
from datetime import datetime
from io import StringIO
from pathlib import Path
import re
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = "data/work_packages.csv"
FIELDS = ("id", "title", "description", "objectives", "tasks", "equipment", "deliverables",
          "work breakdown", "payment", "supervisor", "professor")
EDITABLE = FIELDS[1:]
LIST_FIELDS = ("objectives", "tasks", "equipment", "deliverables", "work breakdown")
REQUIRED = ("title", "description", "objectives", "tasks", "deliverables")
LABELS = {field: field.title() for field in EDITABLE}


def parse_csv(text):
    reader = csv.DictReader(StringIO(text.lstrip("\ufeff"), newline=""))
    columns = reader.fieldnames or []
    if len(set(columns)) != len(columns) or any(field not in columns for field in FIELDS):
        raise ValueError("The work-package CSV has missing or duplicate columns.")
    rows = []
    for row in reader:
        if None in row or any(value is None for value in row.values()):
            raise ValueError("A work-package CSV row has the wrong number of columns.")
        rows.append(dict(row))
    ids = [row["id"] for row in rows]
    if any(not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", value) for value in ids) or len(set(ids)) != len(ids):
        raise ValueError("Work-package IDs must be nonempty, unique letters/numbers, hyphens or underscores.")
    return columns, rows


def read_local():
    raw = (ROOT / DATA_PATH).read_bytes()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("latin-1")
    return parse_csv(text)


def write_csv(columns, rows):
    stream = StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue()


def values(data):
    result = {}
    for field in EDITABLE:
        value = str(data.get(field, ""))
        maximum = 300 if field == "title" else 10000
        if len(value) > maximum or any(ord(c) < 32 and c not in "\n\r\t" for c in value):
            raise ValueError(f"{LABELS[field]} contains unsupported text or is too long.")
        if field in REQUIRED and not value.strip():
            raise ValueError(f"{LABELS[field]} is required.")
        result[field] = value
    return result


def items(value):
    return [item.strip() for item in re.split(r"[;\n]+", value) if item.strip()]


def issuance_year():
    return datetime.now(ZoneInfo("America/Costa_Rica")).year


def next_id(rows, year):
    year = str(year)
    if not re.fullmatch(r"20\d{2}", year):
        raise ValueError("Unsupported work-package year.")
    pattern = re.compile(r"^(\d+)" + year + r"$")
    used = [int(match.group(1)) for row in rows if (match := pattern.fullmatch(row["id"]))]
    return f"{max(used, default=0)+1:02d}{year}"


def apply_change(columns, rows, proposed, original, year):
    proposed = values(proposed)
    if original is None:
        saved = {column: "" for column in columns}
        saved.update(id=next_id(rows, year), **proposed)
        return rows + [saved], saved
    code = original["id"]
    current = next((row for row in rows if row["id"] == code), None)
    if current is None:
        raise ValueError("This work package no longer exists. Refresh before editing.")
    changed = [field for field in EDITABLE if proposed[field] != original.get(field, "")]
    if not changed:
        raise ValueError("There are no changes to save.")
    if any(current[field] != original.get(field, "") for field in changed):
        raise ValueError("A field you edited changed after you opened it. Refresh and review before saving.")
    saved = {**current, **{field: proposed[field] for field in changed}}
    values(saved)
    return [saved if row["id"] == code else row for row in rows], saved
