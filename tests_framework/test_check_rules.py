"""tools/check_rules.py on good and bad samples: steps, locators, features, baselines, secrets."""

import importlib.util
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("check_rules", ROOT / "tools" / "check_rules.py")
check_rules = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check_rules)


def write(root, relative, text):
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def problems(root):
    return (
        check_rules.check_steps(root)
        + check_rules.check_locators(root)
        + check_rules.check_features(root)
    )


def test_the_real_repository_is_clean():
    assert problems(ROOT) == []


def test_clean_sample_passes(tmp_path):
    write(
        tmp_path,
        "steps/ui/test_a.py",
        'from pytest_bdd import given\n@given("I am here")\ndef a(): pass\n',
    )
    write(tmp_path, "pages/p.py", 'def f(page):\n    return page.get_by_role("button")\n')
    write(tmp_path, "features/ui/a.feature", "@ui\nFeature: a\n")
    assert problems(tmp_path) == []


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        ("page.locator('[data-test=\"x\"]')", "selector"),
        ("page.get_by_role('button')", "selector"),  # locators belong in pages/, not steps
        ("x = 'https://example.com'", "URL"),
        ("import requests", "raw HTTP"),
        ("requests.get('x')", "raw HTTP"),
        ("s.session.post('x')", "raw HTTP"),
        ("page.locator('xpath=//a')", "selector"),
    ],
)
def test_step_files_must_not_contain_selectors_urls_or_http(tmp_path, code, expected):
    write(tmp_path, "steps/ui/test_a.py", f"def a(page):\n    {code}\n")
    errors = check_rules.check_steps(tmp_path)
    if expected is None:
        assert errors == []
    else:
        assert any(expected in e for e in errors), errors


def test_the_word_requests_in_a_docstring_is_not_raw_http(tmp_path):
    write(tmp_path, "steps/ui/conftest.py", '"""pytest-bdd requests `page` dynamically."""\n')
    assert check_rules.check_steps(tmp_path) == []


def test_duplicate_step_text_is_found_within_a_suite_even_with_different_parameters(tmp_path):
    body = (
        "from pytest_bdd import given, parsers\n"
        '@given("I am here")\ndef a(): pass\n'
        '@given(parsers.parse("I am {x}"))\ndef b(): pass\n'
        '@given(parsers.parse("I am {y}"))\ndef c(): pass\n'
    )
    write(tmp_path, "steps/ui/test_a.py", body)
    errors = check_rules.check_steps(tmp_path)
    assert len(errors) == 1
    assert "duplicate step text 'I am {}'" in errors[0]


def test_same_step_text_in_different_suites_is_allowed(tmp_path):
    body = 'from pytest_bdd import given\n@given("I am here")\ndef a(): pass\n'
    write(tmp_path, "steps/ui/test_a.py", body)
    write(tmp_path, "steps/visual/test_b.py", body)
    assert check_rules.check_steps(tmp_path) == []


@pytest.mark.parametrize(
    ("code", "label"),
    [
        ('page.locator("//button")', "XPath"),
        ('page.locator("xpath=//a")', "XPath"),
        ('page.locator("li:nth-child(3)")', "positional"),
        ('page.locator("div > ul > li > a")', "child-combinator"),
        ("time.sleep(2)", "sleep"),
        ("page.wait_for_timeout(500)", "sleep"),
    ],
)
def test_fragile_locators_and_sleeps_are_rejected(tmp_path, code, label):
    write(tmp_path, "pages/p.py", f"def f(page):\n    {code}\n")
    assert any(label in e for e in check_rules.check_locators(tmp_path))


@pytest.mark.parametrize("code", ['page.locator("ul > li")', 'page.locator(".pricebar")'])
def test_short_css_is_allowed_in_pages(tmp_path, code):
    write(tmp_path, "pages/p.py", f"def f(page):\n    {code}\n")
    assert check_rules.check_locators(tmp_path) == []


@pytest.mark.parametrize("first_line", ["Feature: x", "@smoke", "@wip"])
def test_features_need_a_suite_tag_on_the_first_line(tmp_path, first_line):
    write(tmp_path, "features/ui/a.feature", f"{first_line}\nFeature: x\n")
    assert len(check_rules.check_features(tmp_path)) == 1


def test_main_returns_nonzero_on_problems(tmp_path):
    write(tmp_path, "features/ui/a.feature", "Feature: x\n")
    assert check_rules.main(["check_rules", str(tmp_path)]) == 1
    write(tmp_path, "features/ui/a.feature", "@ui\nFeature: x\n")
    assert check_rules.main(["check_rules", str(tmp_path)]) == 0


# --- visual baselines (layout, orphans, committed local baselines) ----------------------------


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


# --- leaked secrets -----------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def no_ambient_secrets(monkeypatch):
    for name in ("APP_PASSWORD", "API_PASSWORD"):
        monkeypatch.delenv(name, raising=False)


@pytest.mark.parametrize(
    "line",
    [
        'API_TOKEN = "abcd1234"',
        "APP_PASSWORD=sup3rsecret",
        "DB_SECRET: hunter22",
        "SECRET_KEY='abcdef'",
    ],
)
def test_assigned_secret_literals_are_reported(tmp_path, line):
    write(tmp_path, "docs/a.md", line + "\n")
    assert len(check_rules.check_secrets(tmp_path)) == 1


@pytest.mark.parametrize(
    "line",
    [
        "APP_PASSWORD=",
        'OK_PASSWORD = os.getenv("X")',
        "SECRET: ${{ secrets.X }}",
        'APP_PASSWORD="$APP_PASSWORD"',
        "API_PASSWORD=<your password>",
        '"accessToken": {"type": "string"}',
        "password = request.password",
    ],
)
def test_placeholders_calls_and_lowercase_names_are_not_reported(tmp_path, line):
    write(tmp_path, "docs/a.md", line + "\n")
    assert check_rules.check_secrets(tmp_path) == []


def test_the_real_value_of_a_secret_setting_is_found_anywhere(tmp_path):
    write(tmp_path, ".env", "APP_PASSWORD=value-from-env-file\n")
    write(tmp_path, "docs/notes.md", "temporary: value-from-env-file\n")
    errors = check_rules.check_secrets(tmp_path)
    assert errors == ["docs\\notes.md:1: contains the value of a secret setting"] or errors == [
        "docs/notes.md:1: contains the value of a secret setting"
    ]


def test_the_real_value_from_the_environment_is_found_too(tmp_path, monkeypatch):
    monkeypatch.setenv("API_PASSWORD", "env-only-value")
    write(tmp_path, "steps/x.py", "x = 'env-only-value'\n")
    assert len(check_rules.check_secrets(tmp_path)) == 1


def test_local_secret_files_and_generated_folders_are_not_scanned(tmp_path):
    write(tmp_path, ".env", "APP_PASSWORD=abcd1234\n")
    write(tmp_path, ".env.stage", "APP_PASSWORD=abcd1234\n")
    write(tmp_path, "reports/x.txt", "APP_PASSWORD=abcd1234\n")
    write(tmp_path, "logs/x.log", "APP_PASSWORD=abcd1234\n")
    assert check_rules.check_secrets(tmp_path) == []


def test_binary_files_are_skipped(tmp_path):
    (tmp_path / "image.png").write_bytes(bytes(range(256)) * 10)
    assert check_rules.check_secrets(tmp_path) == []


def test_the_real_repository_has_no_leaked_secrets():
    assert check_rules.check_secrets(ROOT) == []
