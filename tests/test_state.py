from typing import cast
from unittest.mock import MagicMock

import pytest
import reflex as rx
from pytest import MonkeyPatch

from mex.consent import state as state_module
from mex.consent.categories import CategoryPair
from mex.consent.models import User
from mex.consent.state import ConsentState, State

_PAIR = CategoryPair("Resource", "contact")
_OTHER_PAIR = CategoryPair("Activity", "contact")


def test_state_logout(monkeypatch: MonkeyPatch) -> None:
    state = State(
        user=User(name="Test", write_access=True),
        parent_state=MagicMock(),
    )
    monkeypatch.setattr(State, "_mark_dirty", MagicMock(spec=State._mark_dirty))

    assert state.user
    # straight to the login page, not via `/`, which would flash the consent page
    assert "/login" in str(list(state.logout()))  # type: ignore[operator]
    assert state.user is None


def test_state_check_login_pass() -> None:
    state = State(user=User(name="Test", write_access=True))
    assert state.user

    assert list(state.check_ldap_login()) == []  # type: ignore[operator]


def test_state_check_login_fail() -> None:
    state = State()
    assert state.user is None

    assert "/login" in str(list(state.check_ldap_login()))  # type: ignore[operator]


@pytest.mark.parametrize(
    ("category_counts", "expected_reported", "expected_ready"),
    [
        ({}, 0, False),
        ({_PAIR.key: 3}, 1, False),
        ({_PAIR.key: 3, _OTHER_PAIR.key: 0}, 2, True),
    ],
    ids=["nothing-reported", "half-reported", "all-reported"],
)
def test_consent_state_category_progress(
    monkeypatch: MonkeyPatch,
    category_counts: dict[str, int],
    expected_reported: int,
    *,
    expected_ready: bool,
) -> None:
    monkeypatch.setattr(state_module, "CATEGORY_PAIRS", [_PAIR, _OTHER_PAIR])
    consent_state = ConsentState(
        parent_state=MagicMock(),
        category_counts=category_counts,
    )

    assert consent_state.categories_reported == expected_reported
    assert consent_state.categories_ready is expected_ready


def test_consent_state_logout_resets_category_counts(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(State, "_mark_dirty", MagicMock(spec=State._mark_dirty))
    monkeypatch.setattr(state_module, "CATEGORY_PAIRS", [_PAIR, _OTHER_PAIR])
    root = State(parent_state=MagicMock())
    consent_state = cast("ConsentState", root.substates[ConsentState.get_name()])
    consent_state.category_counts = {_PAIR.key: 3, _OTHER_PAIR.key: 0}

    list(root.logout())  # type: ignore[operator]

    # `reset` recurses into the substates, so the counts start over on the next visit
    assert consent_state.category_counts == {}


def test_consent_state_categories_ready_after_timeout(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setattr(state_module, "CATEGORY_PAIRS", [_PAIR, _OTHER_PAIR])
    consent_state = ConsentState(
        parent_state=MagicMock(),
        category_counts={_PAIR.key: 3},
        reveal_categories_anyway=True,
    )

    # one list never reported, but the watchdog fired, so the rest is shown anyway
    assert consent_state.categories_reported == 1
    assert consent_state.categories_ready is True


def _build_consent_state(
    counts: dict[str, int],
    *,
    is_hydrated: bool,
    has_user: bool,
) -> ConsentState:
    """Build a real root/State/ConsentState chain.

    `is_hydrated` belongs to the reflex root state and `user` to `State`, so neither
    can be passed to `ConsentState` directly - they have to be set on their owners.
    """
    root = rx.State(_reflex_internal_init=True)  # type: ignore[call-arg]
    root.is_hydrated = is_hydrated
    state = root.substates[State.get_name()]
    state.user = User(name="Test", write_access=True) if has_user else None
    consent_state = cast("ConsentState", state.substates[ConsentState.get_name()])
    consent_state.category_counts = counts
    return consent_state


@pytest.mark.parametrize(
    ("is_hydrated", "has_user", "counts", "expected"),
    [
        (False, False, {}, (True, False)),
        (False, True, {_PAIR.key: 1, _OTHER_PAIR.key: 1}, (True, False)),
        (True, False, {}, (False, False)),
        (True, True, {}, (True, False)),
        (True, True, {_PAIR.key: 1}, (True, False)),
        (True, True, {_PAIR.key: 1, _OTHER_PAIR.key: 0}, (False, True)),
    ],
    ids=[
        "booting",
        "navigating-with-stale-counts",
        "logged-out-awaiting-redirect",
        "hydrated-nothing-reported",
        "hydrated-half-reported",
        "hydrated-all-reported",
    ],
)
def test_consent_state_reveal_gates(
    monkeypatch: MonkeyPatch,
    counts: dict[str, int],
    expected: tuple[bool, bool],
    *,
    is_hydrated: bool,
    has_user: bool,
) -> None:
    monkeypatch.setattr(state_module, "CATEGORY_PAIRS", [_PAIR, _OTHER_PAIR])
    consent_state = _build_consent_state(
        counts, is_hydrated=is_hydrated, has_user=has_user
    )

    assert (
        consent_state.show_category_progress,
        consent_state.show_categories,
    ) == expected
