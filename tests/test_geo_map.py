# Byline: Claude Code · Fable 5 · 2026-07-05 · ported 2026-08-14 (Codex · GPT-5)
"""server/tools/visualizers/geo_map.py — schema validation, column mapping, adaptive features,
HTML + Evidence-source outputs. No network (geocode stays off)."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from server.tools.visualizers.geo_map import SCHEMA_FIELDS, build_geo_map, run

POINTS = [
    {
        "id": "a",
        "label": "Alpha",
        "lat": 43.1,
        "lng": -83.6,
        "weight": 10,
        "group": "G1",
        "first_seen": "2023-01-06 22:28:00-05:00",
        "last_seen": "2023-12-31 20:54:00-05:00",
    },
    {
        "id": "b",
        "label": "Beta",
        "lat": 43.2,
        "lng": -83.7,
        "weight": 3,
        "group": "G2",
        "first_seen": "2023-04-09 16:31:00-04:00",
        "last_seen": "2023-12-31 14:31:00-05:00",
    },
    {"id": "c", "label": "", "lat": 42.9, "lng": -83.3, "weight": 1, "group": "", "first_seen": "", "last_seen": ""},
]


def test_records_input_builds_html(tmp_path: Path) -> None:
    out = tmp_path / "m.html"
    res = run({"records": POINTS, "title": "T", "out_html": str(out)})
    assert res["rows"] == 3 and res["skipped"] == 0
    html = out.read_text()
    assert '"label":"Alpha"' in html
    assert res["features"] == {"dates": True, "group": True, "weight": True}


def test_csv_path_input_with_mapping(tmp_path: Path) -> None:
    src = tmp_path / "other_report.csv"
    with src.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["latitude", "longitude", "hits", "case_no"])
        w.writeheader()
        w.writerow({"latitude": "43.5", "longitude": "-83.9", "hits": "7", "case_no": "X-1"})
    out = tmp_path / "m.html"
    res = run(
        {
            "path": str(src),
            "mapping": {"lat": "latitude", "lng": "longitude", "weight": "hits"},
            "out_html": str(out),
        }
    )
    assert res["rows"] == 1
    # unmapped extra column rides along verbatim for popup transparency
    assert '"case_no":"X-1"' in out.read_text()


def test_csv_text_input(tmp_path: Path) -> None:
    res = run({"csv_text": "lat,lng\n1.5,2.5\n", "out_html": str(tmp_path / "m.html")})
    assert res["rows"] == 1
    assert res["features"] == {"dates": False, "group": False, "weight": False}


def test_missing_required_field_names_the_fix(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="required field 'lat'.*mapping"):
        run({"records": [{"y": 1, "x": 2}], "out_html": str(tmp_path / "m.html")})


def test_mapping_rejects_unknown_schema_field(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="unknown schema fields"):
        run({"records": POINTS, "mapping": {"altitude": "z"}, "out_html": str(tmp_path / "m.html")})


def test_bad_rows_skipped_with_warnings(tmp_path: Path) -> None:
    rows = POINTS + [{"lat": "not-a-number", "lng": "-83.0"}, {"lat": 99.0, "lng": 200.0}]
    res = run({"records": rows, "out_html": str(tmp_path / "m.html")})
    assert res["rows"] == 3 and res["skipped"] == 2
    assert len(res["warnings"]) >= 2


def test_evidence_source_export_round_trips_timestamps(tmp_path: Path) -> None:
    ev = tmp_path / "locations.csv"
    build_geo_map(records=POINTS, out_html=str(tmp_path / "m.html"), evidence_source_out=str(ev), weight_label="visits")
    got = list(csv.DictReader(ev.open()))
    assert len(got) == 3
    a = next(r for r in got if r["cluster_id"] == "a")
    # naive + offset reconstructs the original string byte-for-byte
    assert a["first_seen"] + a["utc_offset_first"] == "2023-01-06 22:28:00-05:00"
    assert a["visits"] == "10" and a["group_label"] == "G1"
    c = next(r for r in got if r["cluster_id"] == "c")
    assert c["group_label"] == "Unclustered" and c["group_id"] == "-1"


def test_schema_template_files_agree_with_code() -> None:
    root = Path(__file__).resolve().parents[1] / "server" / "tools" / "visualizers"
    schema = json.loads((root / "geo_map_schema.json").read_text())
    assert set(schema["properties"]) == set(SCHEMA_FIELDS)
    header = (root / "geo_map_template.csv").read_text().splitlines()[0].split(",")
    assert set(header) == set(SCHEMA_FIELDS)


def test_template_csv_itself_builds(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1] / "server" / "tools" / "visualizers"
    res = run({"path": str(root / "geo_map_template.csv"), "out_html": str(tmp_path / "m.html")})
    assert res["rows"] == 3 and not res["skipped"]
