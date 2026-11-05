import json

import pytest

from fleet.config import Paths
from fleet.generate import generate


def test_reproducible_and_expected_counts(tmp_path):
    a, b = Paths(tmp_path / "a"), Paths(tmp_path / "b")
    manifest = generate(a, 6, 4)
    assert manifest == generate(b, 6, 4)
    assert a.reference.read_bytes() == b.reference.read_bytes()
    lines = []
    for source in sorted(a.landing.glob("*.jsonl")):
        assert source.read_bytes() == (b.landing / source.name).read_bytes()
        lines.extend(source.read_text().splitlines())
    assert len(lines) == manifest["raw_lines"]
    assert len(lines) - len(set(lines)) == 3
    assert manifest["raw_lines"] == manifest["expected_silver_events"] + 9


def test_scd2_dimension_transfer(paths):
    generate(paths, 4, 4)
    versions = [json.loads(line) for line in paths.reference.read_text().splitlines()]
    moved = [row for row in versions if row["vehicle_id"] == "EV-004"]
    assert len(moved) == 2
    assert moved[0]["valid_to"] == moved[1]["valid_from"]
    assert moved[0]["region"] == "Austin" and moved[1]["region"] == "Denver"


@pytest.mark.parametrize("vehicles,days", [(0, 1), (501, 1), (1, 0), (1, 91)])
def test_generator_bounds(paths, vehicles, days):
    with pytest.raises(ValueError):
        generate(paths, vehicles, days)


def test_generator_refuses_to_rewrite_landing(paths):
    generate(paths, 1, 1)
    with pytest.raises(ValueError, match="already contains"):
        generate(paths, 1, 1)
