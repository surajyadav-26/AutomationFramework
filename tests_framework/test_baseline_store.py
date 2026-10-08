"""core.visual.baseline_store."""

import platform

import pytest

from core.visual import baseline_store

VIEWPORT = {"width": 1280, "height": 720}


@pytest.mark.parametrize(
    ("system", "folder"), [("Linux", "linux"), ("Windows", "windows"), ("Darwin", "macos")]
)
def test_os_name_maps_platform(monkeypatch, system, folder):
    monkeypatch.setattr(platform, "system", lambda: system)
    assert baseline_store.os_name() == folder


def test_unsupported_os_raises(monkeypatch):
    monkeypatch.setattr(platform, "system", lambda: "Plan9")
    with pytest.raises(RuntimeError, match="unsupported OS"):
        baseline_store.os_name()


def test_baseline_path_is_keyed_by_os_browser_and_viewport(monkeypatch):
    monkeypatch.setattr(platform, "system", lambda: "Linux")
    path = baseline_store.baseline_path("login_page", "firefox", VIEWPORT)
    expected = baseline_store.BASELINE_DIR / "linux" / "firefox" / "1280x720" / "login_page.png"
    assert path == expected


def test_different_browsers_and_viewports_never_share_a_path(monkeypatch):
    monkeypatch.setattr(platform, "system", lambda: "Linux")
    paths = {
        baseline_store.baseline_path("p", "chromium", VIEWPORT),
        baseline_store.baseline_path("p", "firefox", VIEWPORT),
        baseline_store.baseline_path("p", "chromium", {"width": 375, "height": 667}),
    }
    assert len(paths) == 3


def test_save_creates_missing_folders(tmp_path):
    target = tmp_path / "linux" / "chromium" / "1280x720" / "x.png"
    baseline_store.save(target, b"data")
    assert target.read_bytes() == b"data"
