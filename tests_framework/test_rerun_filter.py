"""The --only-rerun filter in pytest.ini retries infrastructure errors and nothing else.

pytest-rerunfailures matches each pattern against "ClassName: message" of every exception in the
chain (no module path). These tests apply the real patterns with the plugin's own matcher.
"""

import configparser
import shlex
from pathlib import Path
from types import SimpleNamespace

import pytest
import requests
from pytest_rerunfailures import _try_match_error

ROOT = Path(__file__).resolve().parent.parent


def load_patterns() -> list[str]:
    parser = configparser.ConfigParser(interpolation=None)
    parser.read(ROOT / "pytest.ini")
    options = shlex.split(parser["pytest"]["addopts"])
    return [o.split("=", 1)[1] for o in options if o.startswith("--only-rerun=")]


PATTERNS = load_patterns()


def retried(exc: BaseException) -> bool:
    return _try_match_error(PATTERNS, SimpleNamespace(value=exc))


def test_the_patterns_are_present():
    assert len(PATTERNS) >= 2


@pytest.mark.parametrize(
    "exc",
    [
        requests.exceptions.ConnectTimeout("Connection to host timed out"),
        requests.exceptions.ReadTimeout("Read timed out"),
        requests.exceptions.ConnectionError("Max retries exceeded"),
        TimeoutError("The read operation timed out"),
        ConnectionResetError("reset by peer"),
        RuntimeError("Page.goto: net::ERR_NAME_NOT_RESOLVED at https://example.invalid"),
    ],
    ids=lambda e: type(e).__name__,
)
def test_infrastructure_errors_are_retried(exc):
    assert retried(exc)


def test_a_playwright_timeout_is_retried():
    from playwright._impl._errors import TimeoutError as PlaywrightTimeout

    assert retried(PlaywrightTimeout("Page.goto: Timeout 30000ms exceeded."))


@pytest.mark.parametrize(
    "exc",
    [
        AssertionError("Page URL expected to be inventory. Timeout 5000ms exceeded"),
        AssertionError("visual mismatch for 'login_page': 2.0% of pixels differ"),
        AssertionError("assert 400 == 200"),
        KeyError("accessToken"),
        ValueError("invalid literal"),
    ],
    ids=lambda e: type(e).__name__ + ":" + str(e)[:25],
)
def test_assertion_and_logic_failures_are_never_retried(exc):
    assert not retried(exc)


def test_an_assertion_raised_while_handling_a_timeout_is_still_retried():
    # the matcher follows the exception chain, so the original infrastructure error is found
    try:
        try:
            raise requests.exceptions.ReadTimeout("Read timed out")
        except requests.exceptions.ReadTimeout:
            raise AssertionError("login failed") from None
    except AssertionError as error:
        wrapped = error
    assert not retried(wrapped)  # "from None" hides the cause: treated as a real failure

    try:
        try:
            raise requests.exceptions.ReadTimeout("Read timed out")
        except requests.exceptions.ReadTimeout:
            raise AssertionError("login failed")  # noqa: B904 (context is kept on purpose)
    except AssertionError as error:
        chained = error
    assert retried(chained)
