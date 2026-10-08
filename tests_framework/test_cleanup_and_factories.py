"""core.data.cleanup and core.data.factories."""

import pytest

from core.data.cleanup import Cleanup
from core.data.factories import random_password, unique, username_for


def test_callbacks_run_in_reverse_order():
    order = []
    cleanup = Cleanup()
    cleanup.register(lambda: order.append("first"))
    cleanup.register(lambda: order.append("second"))
    assert cleanup.run_all() == []
    assert order == ["second", "first"]


def test_a_failing_callback_does_not_stop_the_others_and_is_reported():
    ran = []

    def boom():
        raise RuntimeError("nope")

    cleanup = Cleanup()
    cleanup.register(lambda: ran.append("a"), "a")
    cleanup.register(boom, "boom")
    cleanup.register(lambda: ran.append("c"), "c")
    assert cleanup.run_all() == ["boom"]
    assert ran == ["c", "a"]


def test_registry_is_empty_after_running():
    calls = []
    cleanup = Cleanup()
    cleanup.register(lambda: calls.append(1))
    cleanup.run_all()
    cleanup.run_all()
    assert calls == [1]


def test_unique_values_do_not_repeat_and_keep_the_prefix():
    values = {unique("user") for _ in range(200)}
    assert len(values) == 200
    assert all(v.startswith("user-") for v in values)


def test_random_passwords_are_unique():
    assert random_password() != random_password()


def test_known_roles_resolve_and_unknown_roles_fail_clearly():
    assert username_for("standard") == "standard_user"
    assert username_for("no_username") == ""
    with pytest.raises(KeyError, match="unknown user role 'ghost'"):
        username_for("ghost")
