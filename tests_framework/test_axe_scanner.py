"""core.accessibility.axe_scanner with a fake axe (no browser)."""

from types import SimpleNamespace

import pytest

from core.accessibility import axe_scanner
from core.accessibility.axe_scanner import WCAG_TAGS, blocking, describe, scan


def violation(rule, impact, nodes=1):
    return {"id": rule, "impact": impact, "help": f"{rule} help", "nodes": [{}] * nodes}


@pytest.fixture
def fake_axe(monkeypatch):
    calls = {}
    attachments = []

    class FakeAxe:
        def run(self, page, options=None):
            calls["page"] = page
            calls["options"] = options
            return SimpleNamespace(response={"violations": calls["violations"]})

    monkeypatch.setattr(axe_scanner, "Axe", FakeAxe)
    monkeypatch.setattr(axe_scanner, "attach_json", lambda data, name: attachments.append(name))
    calls["violations"] = []
    return calls, attachments


def test_scan_runs_only_the_wcag_tags_and_returns_every_violation(fake_axe):
    calls, attachments = fake_axe
    calls["violations"] = [violation("image-alt", "critical"), violation("region", "minor")]
    result = scan("PAGE")
    assert [v["id"] for v in result] == ["image-alt", "region"]
    assert calls["page"] == "PAGE"
    assert calls["options"] == {"runOnly": {"type": "tag", "values": WCAG_TAGS}}
    assert attachments == ["Accessibility violations (2)"]


def test_scan_with_no_violations(fake_axe):
    _, attachments = fake_axe
    assert scan("PAGE") == []
    assert attachments == ["Accessibility violations (0)"]


@pytest.mark.parametrize(
    ("threshold", "expected"),
    [
        ("critical", ["a"]),
        ("serious", ["a", "b"]),
        ("moderate", ["a", "b", "c"]),
        ("minor", ["a", "b", "c", "d"]),
    ],
)
def test_blocking_keeps_violations_at_or_above_the_threshold(threshold, expected):
    found = [
        violation("a", "critical"),
        violation("b", "serious"),
        violation("c", "moderate"),
        violation("d", "minor"),
    ]
    assert [v["id"] for v in blocking(found, threshold)] == expected


def test_a_violation_without_impact_counts_as_minor():
    found = [violation("x", None)]
    assert blocking(found, "minor") == found
    assert blocking(found, "moderate") == []


def test_describe_lists_rule_impact_count_and_help():
    text = describe([violation("image-alt", "critical", nodes=3), violation("label", "serious")])
    assert "image-alt (critical, 3 element(s)): image-alt help" in text
    assert "label (serious, 1 element(s)): label help" in text
    assert "; " in text
