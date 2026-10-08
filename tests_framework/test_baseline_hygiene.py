"""tools/check_rules.py check_baselines: baseline layout, orphans, and committed local baselines."""

import importlib.util
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("check_rules", ROOT / "tools" / "check_rules.py")
check_rules = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check_rules)

PNG = b"\x89PNG"


def baseline(root, relative):
    path = root / "baselines" / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(PNG)
    return path


@pytest.fixture
def project(tmp_path):
    steps = tmp_path / "steps" / "visual"
    steps.mkdir(parents=True)
    (steps / "test_x_steps.py").write_text(
        'def a(assert_matches_baseline, page):\n    assert_matches_baseline("login_page", page)\n'
        '    assert_matches_baseline("inventory_page", page)\n'
    )
    return tmp_path


def test_no_baselines_folder_is_fine(tmp_path):
    assert check_rules.check_baselines(tmp_path) == []


def test_well_formed_baselines_pass(project):
    baseline(project, "linux/chromium/1280x720/login_page.png")
    baseline(project, "linux/webkit/375x667/inventory_page.png")
    assert check_rules.check_baselines(project) == []


@pytest.mark.parametrize(
    ("relative", "message"),
    [
        ("linux/chromium/login_page.png", "expected baselines/<os>/<browser>/<WxH>/<name>.png"),
        ("beos/chromium/1280x720/login_page.png", "unknown OS folder 'beos'"),
        ("linux/netscape/1280x720/login_page.png", "unknown browser folder 'netscape'"),
        ("linux/chromium/wide/login_page.png", "is not <width>x<height>"),
        ("linux/chromium/1280x720/old_page.png", "orphan"),
    ],
)
def test_malformed_or_orphan_baselines_are_reported(project, relative, message):
    baseline(project, relative)
    errors = check_rules.check_baselines(project)
    assert len(errors) == 1
    assert message in errors[0]


def test_without_visual_steps_names_are_not_checked(tmp_path):
    baseline(tmp_path, "linux/chromium/1280x720/anything.png")
    assert check_rules.check_baselines(tmp_path) == []


def git(root, *args):
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", *args],
        cwd=root,
        check=True,
        capture_output=True,
    )


def test_committed_windows_baselines_are_reported_but_linux_ones_are_fine(project):
    git(project, "init", "-q")
    linux = baseline(project, "linux/chromium/1280x720/login_page.png")
    windows = baseline(project, "windows/chromium/1280x720/login_page.png")
    git(project, "add", "-f", str(linux), str(windows))
    errors = check_rules.check_baselines(project)
    assert len(errors) == 1
    assert "windows/chromium" in errors[0]
    assert "local-only baseline is committed" in errors[0]


def test_untracked_local_baselines_are_fine(project):
    git(project, "init", "-q")
    baseline(project, "windows/chromium/1280x720/login_page.png")
    assert check_rules.check_baselines(project) == []


def test_the_real_repository_baselines_are_clean():
    assert check_rules.check_baselines(ROOT) == []
