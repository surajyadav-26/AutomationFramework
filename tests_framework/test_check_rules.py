"""tools/check_rules.py on good and bad samples, and on the real repository."""

import importlib.util
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
