"""tools/check_rules.py on good and bad samples: code, structure, areas, tags, baselines, secrets.

Most tests build a small throwaway project with `make_area` (a complete, valid feature area) and
then break one thing, so each rule is shown to fire on exactly the mistake it exists for.
"""

import importlib.util
import subprocess
import textwrap
from pathlib import Path

import pytest

from core import areas

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("check_rules", ROOT / "tools" / "check_rules.py")
check_rules = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check_rules)

STEP = 'from pytest_bdd import given\n\n\n@given("I am here")\ndef a(): pass\n'


def write(root, relative, text):
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        textwrap.dedent(text) if "\n" in text and text.startswith("\n") else text, encoding="utf-8"
    )


def make_area(root, suite="ui", area="auth", feature="login"):
    """A complete valid area: feature, step module calling scenarios(), page or client folder."""
    write(root, f"features/{suite}/{area}/{feature}.feature", f"@{suite}\nFeature: {feature}\n")
    write(root, f"steps/{suite}/{area}/__init__.py", "")
    write(
        root,
        f"steps/{suite}/{area}/test_{feature}_steps.py",
        f'from pytest_bdd import scenarios\n\nscenarios("{suite}/{area}/{feature}.feature")\n',
    )
    owner = "pages" if suite in check_rules.BROWSER_SUITES else "clients"
    write(root, f"{owner}/{area}/__init__.py", "")


def make_registry(root, markers=("ui", "api", "visual", "accessibility", "smoke")):
    """pyproject.toml markers and a docs/TAGS.md that documents them."""
    lines = ",\n".join(f'    "{m}: description"' for m in markers)
    write(root, "pyproject.toml", f"[tool.pytest.ini_options]\nmarkers = [\n{lines},\n]\n")
    write(root, "docs/TAGS.md", "\n".join(f"- `@{m}`" for m in markers) + "\n")


@pytest.fixture(autouse=True)
def no_ambient_secrets(monkeypatch):
    for name in ("APP_PASSWORD", "API_PASSWORD"):
        monkeypatch.delenv(name, raising=False)


# --- the real repository and the shared vocabulary ---------------------------------------------


def test_the_real_repository_passes_every_rule():
    assert check_rules.run_all(ROOT) == []


def test_the_checker_and_core_agree_on_suites_and_reserved_names():
    assert check_rules.SUITES == areas.SUITES
    assert check_rules.RESERVED == areas.RESERVED
    for name in ("auth", "Auth", "ui", "shared", "_x", "a-b", "cart_items"):
        assert check_rules.is_valid_area_name(name) == areas.is_valid_area_name(name)


def test_a_complete_sample_project_passes(tmp_path):
    make_area(tmp_path, "ui", "auth")
    make_area(tmp_path, "api", "auth", "user")
    make_registry(tmp_path)
    assert check_rules.run_all(tmp_path) == []


def test_main_returns_nonzero_on_problems_and_zero_when_clean(tmp_path, capsys):
    write(tmp_path, "features/ui/auth/a.feature", "Feature: x\n")
    assert check_rules.main(["check_rules", str(tmp_path)]) == 1
    assert "FAILED" in capsys.readouterr().out
    (tmp_path / "features" / "ui" / "auth" / "a.feature").unlink()
    assert check_rules.main(["check_rules", str(tmp_path)]) == 0


# --- step files: selectors, URLs, HTTP, duplicates ----------------------------------------------


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
@pytest.mark.parametrize("folder", ["steps/ui/auth", "shared"])
def test_step_files_must_not_contain_selectors_urls_or_http(tmp_path, code, expected, folder):
    write(tmp_path, f"{folder}/test_a.py", f"def a(page):\n    {code}\n")
    errors = check_rules.check_steps(tmp_path)
    assert any(expected in e for e in errors), errors


def test_the_word_requests_in_a_docstring_is_not_raw_http(tmp_path):
    write(tmp_path, "steps/ui/auth/conftest.py", '"""pytest-bdd requests `page` dynamically."""\n')
    assert check_rules.check_steps(tmp_path) == []


def test_duplicate_step_text_is_found_within_a_suite_even_with_different_parameters(tmp_path):
    body = (
        "from pytest_bdd import given, parsers\n"
        '@given("I am here")\ndef a(): pass\n'
        '@given(parsers.parse("I am {x}"))\ndef b(): pass\n'
        '@given(parsers.parse("I am {y}"))\ndef c(): pass\n'
    )
    write(tmp_path, "steps/ui/auth/test_a.py", body)
    errors = check_rules.check_steps(tmp_path)
    assert len(errors) == 1
    assert "duplicate step text 'I am {}'" in errors[0]


def test_the_same_step_text_in_two_areas_of_one_suite_is_a_duplicate(tmp_path):
    write(tmp_path, "steps/ui/auth/test_a.py", STEP)
    write(tmp_path, "steps/ui/cart/test_b.py", STEP)
    assert len(check_rules.check_steps(tmp_path)) == 1


def test_same_step_text_in_different_suites_is_allowed(tmp_path):
    write(tmp_path, "steps/ui/auth/test_a.py", STEP)
    write(tmp_path, "steps/api/auth/test_b.py", STEP)
    assert check_rules.check_steps(tmp_path) == []


@pytest.mark.parametrize("suite", ["ui", "visual", "accessibility"])
def test_a_shared_step_cannot_be_redefined_in_a_browser_suite(tmp_path, suite):
    write(tmp_path, "shared/login_steps.py", STEP)
    write(tmp_path, f"steps/{suite}/auth/test_a.py", STEP)
    errors = check_rules.check_steps(tmp_path)
    assert len(errors) == 1
    assert "duplicate step text 'I am here'" in errors[0]


def test_a_shared_step_may_share_its_wording_with_the_api_suite(tmp_path):
    write(tmp_path, "shared/login_steps.py", STEP)
    write(tmp_path, "steps/api/auth/test_a.py", STEP)
    assert check_rules.check_steps(tmp_path) == []


# --- fragile locators and sleeps -----------------------------------------------------------------


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
@pytest.mark.parametrize("folder", ["pages/auth", "shared", "steps/ui/auth", "core/browser"])
def test_fragile_locators_and_sleeps_are_rejected(tmp_path, code, label, folder):
    write(tmp_path, f"{folder}/p.py", f"def f(page):\n    {code}\n")
    assert any(label in e for e in check_rules.check_locators(tmp_path))


@pytest.mark.parametrize("code", ['page.locator("ul > li")', 'page.locator(".pricebar")'])
def test_short_css_is_allowed_in_pages(tmp_path, code):
    write(tmp_path, "pages/auth/p.py", f"def f(page):\n    {code}\n")
    assert check_rules.check_locators(tmp_path) == []


# --- features: tags ----------------------------------------------------------------------------


@pytest.mark.parametrize("first_line", ["Feature: x", "@smoke", "@wip"])
def test_features_need_a_suite_tag_on_the_first_line(tmp_path, first_line):
    write(tmp_path, "features/ui/auth/a.feature", f"{first_line}\nFeature: x\n")
    assert len(check_rules.check_features(tmp_path)) == 1


def test_a_feature_must_carry_the_tag_of_its_own_suite_folder(tmp_path):
    write(tmp_path, "features/api/auth/a.feature", "@ui\nFeature: x\n")
    errors = check_rules.check_features(tmp_path)
    assert len(errors) == 1
    assert "lives in features/api/ but is tagged ['@ui']" in errors[0]


def test_extra_tags_next_to_the_suite_tag_are_fine(tmp_path):
    write(tmp_path, "features/ui/auth/a.feature", "@ui @smoke\nFeature: x\n")
    assert check_rules.check_features(tmp_path) == []


# --- structure: one area name ties features, steps and pages together ----------------------------


def test_every_suite_gets_the_matching_owner_folder(tmp_path):
    for suite in check_rules.SUITES:
        make_area(tmp_path, suite, "auth", f"f_{suite}")
    assert check_rules.check_structure(tmp_path) == []
    assert (tmp_path / "pages" / "auth").exists()
    assert (tmp_path / "clients" / "auth").exists()


@pytest.mark.parametrize(
    ("relative", "message"),
    [
        ("features/ui/login.feature", "expected features/<suite>/<area>/<name>.feature"),
        ("features/ui/auth/deeper/x.feature", "expected features/<suite>/<area>/<name>.feature"),
        ("features/foo/auth/x.feature", "'foo' is not a suite folder"),
        ("features/ui/Auth/x.feature", "'Auth' is not a valid area name"),
        ("features/ui/shared/x.feature", "'shared' is not a valid area name"),
        ("features/ui/smoke/x.feature", "'smoke' is not a valid area name"),
    ],
)
def test_features_must_sit_in_a_suite_and_a_valid_area_folder(tmp_path, relative, message):
    write(tmp_path, relative, "@ui\nFeature: x\n")
    errors = check_rules.check_structure(tmp_path)
    assert len(errors) == 1
    assert message in errors[0]


def test_a_feature_without_a_steps_folder_is_reported(tmp_path):
    write(tmp_path, "features/ui/cart/x.feature", "@ui\nFeature: x\n")
    write(tmp_path, "pages/cart/__init__.py", "")
    errors = check_rules.check_structure(tmp_path)
    assert errors == ["features/ui/cart/x.feature: missing steps/ui/cart/ (with __init__.py)"]


def test_a_steps_folder_that_never_calls_scenarios_for_the_feature_is_reported(tmp_path):
    make_area(tmp_path, "ui", "auth", "login")
    write(tmp_path, "features/ui/auth/second.feature", "@ui\nFeature: second\n")
    errors = check_rules.check_structure(tmp_path)
    assert len(errors) == 1
    assert 'calls scenarios("ui/auth/second.feature")' in errors[0]


def test_a_browser_feature_needs_a_pages_folder_and_an_api_feature_a_clients_folder(tmp_path):
    make_area(tmp_path, "visual", "auth")
    make_area(tmp_path, "api", "auth", "user")
    (tmp_path / "pages" / "auth" / "__init__.py").unlink()
    (tmp_path / "clients" / "auth" / "__init__.py").unlink()
    errors = check_rules.check_structure(tmp_path)
    assert sorted(e.split(": ")[1] for e in errors) == [
        "missing clients/auth/ (with __init__.py)",
        "missing pages/auth/ (with __init__.py)",
    ]


def test_scenarios_must_point_at_a_feature_that_exists(tmp_path):
    make_area(tmp_path)
    (tmp_path / "features" / "ui" / "auth" / "login.feature").unlink()
    errors = check_rules.check_structure(tmp_path)
    assert errors == [
        "steps/ui/auth/test_login_steps.py: scenarios('ui/auth/login.feature') points at a "
        "missing file"
    ]


def test_scenarios_must_stay_inside_their_own_suite_and_area(tmp_path):
    make_area(tmp_path, "ui", "auth")
    make_area(tmp_path, "ui", "cart", "basket")
    write(
        tmp_path,
        "steps/ui/auth/test_login_steps.py",
        'from pytest_bdd import scenarios\n\nscenarios("ui/cart/basket.feature")\n',
    )
    errors = check_rules.check_structure(tmp_path)
    assert any("is outside ui/auth/" in e for e in errors)


# --- areas stay independent ----------------------------------------------------------------------


def imports(tmp_path, relative, text):
    write(tmp_path, relative, text)
    return check_rules.check_area_independence(tmp_path)


@pytest.mark.parametrize(
    "line",
    [
        "from pages.auth.login_page import LoginPage",  # its own area
        "from pages.components.header import Header",  # reusable components
        "from steps.ui.auth.conftest import something",  # its own steps
        "from clients.auth.user_client import UserClient",
        "import requests",
        "from core.settings import get_settings",
        "from shared.login_steps import *",
    ],
)
def test_a_step_module_may_import_its_own_area_and_shared_code(tmp_path, line):
    assert imports(tmp_path, "steps/ui/auth/test_x.py", line + "\n") == []


@pytest.mark.parametrize(
    ("line", "why"),
    [
        ("from pages.cart.cart_page import CartPage", "pages of another area"),
        ("import pages.cart.cart_page", "pages of another area"),
        ("from clients.cart.client import Client", "clients of another area"),
        ("from steps.ui.cart.conftest import x", "steps of another suite or area"),
        ("from steps.api.auth.conftest import x", "steps of another suite or area"),
    ],
)
def test_a_step_module_may_not_import_another_area_or_suite(tmp_path, line, why):
    errors = imports(tmp_path, "steps/ui/auth/test_x.py", line + "\n")
    assert len(errors) == 1
    assert why in errors[0]


def test_pages_may_use_components_but_not_other_areas(tmp_path):
    ok = "from pages.components.header import Header\nfrom pages.auth.login_page import X\n"
    assert imports(tmp_path, "pages/auth/dashboard_page.py", ok) == []
    errors = imports(tmp_path, "pages/auth/bad.py", "from pages.cart.cart_page import CartPage\n")
    assert len(errors) == 1
    assert "another area's pages" in errors[0]


def test_components_do_not_depend_on_any_area(tmp_path):
    errors = imports(
        tmp_path, "pages/components/header.py", "from pages.auth.login_page import X\n"
    )
    assert len(errors) == 1


def test_clients_may_not_import_another_areas_clients(tmp_path):
    errors = imports(tmp_path, "clients/auth/c.py", "from clients.cart.c import C\n")
    assert len(errors) == 1


def test_shared_code_may_import_any_area(tmp_path):
    assert imports(tmp_path, "shared/fx.py", "from pages.cart.cart_page import CartPage\n") == []


def test_suite_level_conftest_files_are_not_part_of_an_area(tmp_path):
    assert imports(tmp_path, "steps/conftest.py", "from pages.cart.x import Y\n") == []


# --- tags --------------------------------------------------------------------------------------


def test_a_used_tag_must_be_registered(tmp_path):
    make_registry(tmp_path)
    write(tmp_path, "features/ui/auth/a.feature", "@ui @flaky\nFeature: x\n")
    errors = check_rules.check_tags(tmp_path)
    assert errors == [
        "features/ui/auth/a.feature: tag @flaky is not a registered marker in pyproject.toml"
    ]


def test_a_registered_tag_must_be_documented(tmp_path):
    make_registry(tmp_path, markers=("ui", "api", "visual", "accessibility", "smoke", "slow"))
    write(tmp_path, "docs/TAGS.md", "`@ui` `@api` `@visual` `@accessibility` `@smoke`\n")
    write(tmp_path, "features/ui/auth/a.feature", "@ui\nFeature: x\n")
    assert check_rules.check_tags(tmp_path) == ["docs/TAGS.md: tag @slow is not documented"]


def test_a_missing_tags_file_is_reported(tmp_path):
    make_registry(tmp_path)
    (tmp_path / "docs" / "TAGS.md").unlink()
    write(tmp_path, "features/ui/auth/a.feature", "@ui\nFeature: x\n")
    assert check_rules.check_tags(tmp_path) == ["docs/TAGS.md is missing (it lists every tag)"]


def test_tags_on_scenario_lines_count_too(tmp_path):
    make_registry(tmp_path)
    write(tmp_path, "features/ui/auth/a.feature", "@ui\nFeature: x\n\n  @wip\n  Scenario: s\n")
    assert len(check_rules.check_tags(tmp_path)) == 1


def test_no_pyproject_or_no_features_means_nothing_to_check(tmp_path):
    assert check_rules.check_tags(tmp_path) == []
    write(tmp_path, "pyproject.toml", "[tool.pytest.ini_options]\nmarkers = []\n")
    assert check_rules.check_tags(tmp_path) == []


# --- visual baselines (layout, area, orphans, committed local baselines) -----------------------

PNG = b"\x89PNG"


def baseline(root, relative):
    path = root / "baselines" / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(PNG)
    return path


@pytest.fixture
def project(tmp_path):
    make_area(tmp_path, "visual", "auth", "login_visual")
    write(
        tmp_path,
        "steps/visual/auth/test_x_steps.py",
        'def a(assert_matches_baseline, page):\n    assert_matches_baseline("login_page", page)\n'
        '    assert_matches_baseline("inventory_page", page)\n',
    )
    return tmp_path


def test_no_baselines_folder_is_fine(tmp_path):
    assert check_rules.check_baselines(tmp_path) == []


def test_well_formed_baselines_pass(project):
    baseline(project, "linux/chromium/1280x720/auth/login_page.png")
    baseline(project, "windows/webkit/375x667/auth/inventory_page.png")
    assert check_rules.check_baselines(project) == []


@pytest.mark.parametrize(
    ("relative", "message"),
    [
        ("linux/chromium/1280x720/login_page.png", "<WxH>/<area>/<name>.png"),
        ("linux/chromium/login_page.png", "<WxH>/<area>/<name>.png"),
        ("beos/chromium/1280x720/auth/login_page.png", "unknown OS folder 'beos'"),
        ("linux/netscape/1280x720/auth/login_page.png", "unknown browser folder 'netscape'"),
        ("linux/chromium/wide/auth/login_page.png", "is not <width>x<height>"),
        ("linux/chromium/1280x720/cart/login_page.png", "'cart' is not an area"),
        ("linux/chromium/1280x720/auth/old_page.png", "orphan"),
    ],
)
def test_malformed_or_orphan_baselines_are_reported(project, relative, message):
    baseline(project, relative)
    errors = check_rules.check_baselines(project)
    assert len(errors) == 1
    assert message in errors[0]


def test_a_baseline_name_must_be_used_by_a_step_of_the_same_area(project):
    make_area(project, "visual", "cart", "cart_visual")
    baseline(project, "linux/chromium/1280x720/cart/login_page.png")  # name belongs to auth
    errors = check_rules.check_baselines(project)
    assert len(errors) == 1
    assert "no visual step of area 'cart'" in errors[0]


def test_without_visual_steps_names_are_not_checked(tmp_path):
    baseline(tmp_path, "linux/chromium/1280x720/auth/anything.png")
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
    linux = baseline(project, "linux/chromium/1280x720/auth/login_page.png")
    windows = baseline(project, "windows/chromium/1280x720/auth/login_page.png")
    git(project, "add", "-f", str(linux), str(windows))
    errors = check_rules.check_baselines(project)
    assert len(errors) == 1
    assert "windows/chromium" in errors[0]
    assert "local-only baseline is committed" in errors[0]


def test_untracked_local_baselines_are_fine(project):
    git(project, "init", "-q")
    baseline(project, "windows/chromium/1280x720/auth/login_page.png")
    assert check_rules.check_baselines(project) == []


# --- leaked secrets -----------------------------------------------------------------------------


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
    assert [e.replace("\\", "/") for e in errors] == [
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
