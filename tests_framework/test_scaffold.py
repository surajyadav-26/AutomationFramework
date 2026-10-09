"""tools/scaffold.py: what it plans, what it refuses, and that its output passes every gate.

The last test scaffolds a whole new area into a scratch copy of the project and runs the rules
checker, ruff, the architecture rules, mypy and pytest against the result.
"""

import importlib.util
import io
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from core import areas

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("scaffold", ROOT / "tools" / "scaffold.py")
scaffold = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scaffold)


def run(args, root):
    out = io.StringIO()
    code = scaffold.main(["scaffold", *args], root=root, out=out)
    return code, out.getvalue()


# --- vocabulary ----------------------------------------------------------------------------------


def test_the_scaffold_and_core_agree_on_suites_and_reserved_names():
    assert scaffold.SUITES == areas.SUITES
    assert scaffold.RESERVED == areas.RESERVED
    for name in ("cart", "Cart", "ui", "shared", "_x", "a-b", "order_history", "1a"):
        assert scaffold.is_valid_name(name) == areas.is_valid_area_name(name)


def test_names_become_titles_and_class_names():
    assert scaffold.words("cart") == ("Cart", "Cart")
    assert scaffold.words("order_history") == ("Order History", "OrderHistory")


# --- the plan ------------------------------------------------------------------------------------


def test_a_ui_and_api_area_gets_features_steps_page_fixture_and_client():
    plan = scaffold.plan_area("cart", ("ui", "api"))
    assert sorted(plan) == [
        "clients/cart/__init__.py",
        "clients/cart/cart_client.py",
        "features/api/cart/cart.feature",
        "features/ui/cart/cart.feature",
        "pages/cart/__init__.py",
        "pages/cart/cart_page.py",
        "shared/cart_fixtures.py",
        "steps/api/cart/__init__.py",
        "steps/api/cart/conftest.py",
        "steps/api/cart/test_cart_steps.py",
        "steps/ui/cart/__init__.py",
        "steps/ui/cart/conftest.py",
        "steps/ui/cart/test_cart_steps.py",
    ]


def test_an_api_only_area_has_no_pages_and_a_browser_only_area_has_no_client():
    api_only = scaffold.plan_area("billing", ("api",))
    assert not any(path.startswith(("pages/", "shared/")) for path in api_only)
    assert "clients/billing/billing_client.py" in api_only
    browser_only = scaffold.plan_area("billing", ("visual", "accessibility"))
    assert not any(path.startswith("clients/") for path in browser_only)
    assert "shared/billing_fixtures.py" in browser_only


def test_each_feature_is_tagged_with_its_suite_and_has_one_wiring_scenario():
    plan = scaffold.plan_area("order_history", ("ui", "api"))
    ui = plan["features/ui/order_history/order_history.feature"]
    assert ui.startswith("@ui\nFeature: Order History\n")
    assert ui.count("Scenario:") == 1
    assert "Given the order_history page object is available" in ui
    assert (
        "Given the order_history client is available"
        in plan["features/api/order_history/order_history.feature"]
    )


def test_steps_call_scenarios_for_their_own_feature_file():
    plan = scaffold.plan_area("cart", ("visual",))
    assert 'scenarios("visual/cart/cart.feature")' in plan["steps/visual/cart/test_cart_steps.py"]


def test_class_names_follow_the_area_name():
    plan = scaffold.plan_area("order_history", ("ui", "api"))
    assert "class OrderHistoryPage(BasePage):" in plan["pages/order_history/order_history_page.py"]
    assert "class OrderHistoryClient:" in plan["clients/order_history/order_history_client.py"]
    assert "def order_history_page(" in plan["shared/order_history_fixtures.py"]


def test_generated_python_is_valid_python():
    plans = [scaffold.plan_area("cart", scaffold.SUITES), scaffold.plan_component("side_menu")]
    for plan in plans:
        for path, content in plan.items():
            if path.endswith(".py"):
                compile(content, path, "exec")


def test_a_component_is_a_base_component_rooted_on_its_own_test_id():
    plan = scaffold.plan_component("side_menu")
    code = plan["pages/components/side_menu.py"]
    assert "class SideMenu(BaseComponent):" in code
    assert 'page.get_by_test_id("side_menu")' in code


# --- suites option -------------------------------------------------------------------------------


def test_suites_are_parsed_deduplicated_and_validated():
    assert scaffold.parse_suites("ui, api,ui") == ("ui", "api")
    for bad in ("", "ui,mobile", ","):
        with pytest.raises(ValueError, match="--suites must list some of"):
            scaffold.parse_suites(bad)


# --- the command ---------------------------------------------------------------------------------


def test_creating_an_area_writes_the_files_and_explains_the_next_steps(tmp_path):
    code, text = run(["area", "cart"], tmp_path)
    assert code == 0
    assert (tmp_path / "features" / "ui" / "cart" / "cart.feature").exists()
    assert (tmp_path / "features" / "api" / "cart" / "cart.feature").exists()  # default: ui, api
    assert not (tmp_path / "features" / "visual").exists()
    assert "Created 13 file(s) for the area 'cart'" in text
    assert "Next:" in text
    assert "CODEOWNERS" in text


def test_a_dry_run_writes_nothing(tmp_path):
    code, text = run(["area", "cart", "--dry-run"], tmp_path)
    assert code == 0
    assert "Would create:" in text
    assert list(tmp_path.iterdir()) == []


def test_existing_files_are_never_overwritten_and_nothing_partial_is_written(tmp_path):
    write_first = tmp_path / "pages" / "cart" / "cart_page.py"
    write_first.parent.mkdir(parents=True)
    write_first.write_text("# mine\n")
    code, text = run(["area", "cart"], tmp_path)
    assert code == 1
    assert "Nothing written" in text
    assert "pages/cart/cart_page.py" in text
    assert write_first.read_text() == "# mine\n"
    assert not (tmp_path / "features").exists()  # not even the files that were free


def test_scaffolding_the_same_area_twice_is_refused(tmp_path):
    assert run(["area", "cart"], tmp_path)[0] == 0
    assert run(["area", "cart"], tmp_path)[0] == 1


@pytest.mark.parametrize("name", ["Cart", "ui", "shared", "smoke", "components", "a-b", "1x"])
def test_invalid_names_are_refused_with_an_explanation(tmp_path, name):
    code, text = run(["area", name], tmp_path)
    assert code == 2
    assert "not a valid area name" in text
    assert list(tmp_path.iterdir()) == []


def test_usage_errors(tmp_path):
    assert run([], tmp_path)[0] == 2
    assert run(["area"], tmp_path)[0] == 2
    assert run(["widget", "x"], tmp_path)[0] == 2
    assert run(["area", "cart", "--suites"], tmp_path)[0] == 2
    code, text = run(["area", "cart", "--suites", "ui,mobile"], tmp_path)
    assert code == 2
    assert "--suites must list some of" in text


def test_creating_a_component(tmp_path):
    code, text = run(["component", "modal"], tmp_path)
    assert code == 0
    assert (tmp_path / "pages" / "components" / "modal.py").exists()
    assert "component 'modal'" in text
    assert run(["component", "modal"], tmp_path)[0] == 1  # exists now


# --- the output passes every gate ---------------------------------------------------------------

COPIED_FOLDERS = ("core", "pages", "clients", "shared", "steps", "features", "tools", "docs")
COPIED_FOLDERS += ("config", "test_data")
COPIED_FILES = ("pyproject.toml", "conftest.py", "requirements.in", "requirements.lock")
COPIED_FILES += (".python-version", "README.md", ".env.example")


@pytest.fixture(scope="module")
def scratch_project(tmp_path_factory):
    """A copy of the working tree (without caches, secrets or baselines) to scaffold into."""
    target = tmp_path_factory.mktemp("scratch")
    ignore = shutil.ignore_patterns("__pycache__", "*.pyc")
    for folder in COPIED_FOLDERS:
        shutil.copytree(ROOT / folder, target / folder, ignore=ignore)
    for name in COPIED_FILES:
        shutil.copy(ROOT / name, target / name)
    return target


def tool(scratch, *command):
    env = {
        **os.environ,
        "PYTHONPATH": str(scratch),
        "ALLURE_AUTO_OPEN": "false",
        "APP_PASSWORD": "dummy-ui",
        "API_PASSWORD": "dummy-api",
        "API_MODE": "stub",
    }
    return subprocess.run(
        [sys.executable, *command], cwd=scratch, env=env, capture_output=True, text=True
    )


def assert_ok(result, what):
    assert result.returncode == 0, (
        f"{what} failed:\n{result.stdout[-1500:]}\n{result.stderr[-800:]}"
    )


def test_a_scaffolded_area_and_component_pass_every_gate_and_their_wiring_tests_run(
    scratch_project,
):
    scratch = scratch_project
    assert_ok(tool(scratch, "tools/check_rules.py"), "check_rules before scaffolding")
    assert_ok(
        tool(
            scratch, "tools/scaffold.py", "area", "cart", "--suites", "ui,api,visual,accessibility"
        ),
        "scaffold area",
    )
    assert_ok(tool(scratch, "tools/scaffold.py", "component", "modal"), "scaffold component")

    assert_ok(tool(scratch, "tools/check_rules.py"), "check_rules")
    assert_ok(tool(scratch, "-m", "ruff", "check", "."), "ruff check")
    assert_ok(tool(scratch, "-m", "ruff", "format", "--check", "."), "ruff format")
    lint = subprocess.run(
        ["lint-imports"], cwd=scratch, capture_output=True, text=True,
        env={**os.environ, "PYTHONPATH": str(scratch)},
    )  # fmt: skip
    assert_ok(lint, "lint-imports")
    assert_ok(tool(scratch, "-m", "mypy"), "mypy")

    tests = tool(scratch, "-m", "pytest", "steps", "--area", "cart", "-q", "-p", "no:cacheprovider")
    assert_ok(tests, "the new area's wiring tests")
    assert "4 passed" in tests.stdout  # one wiring scenario in each of the four suites
