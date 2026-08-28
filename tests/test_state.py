from unittest.mock import MagicMock

from pytest import MonkeyPatch

from mex.consent.models import User
from mex.consent.state import State


def test_state_logout(monkeypatch: MonkeyPatch) -> None:
    state = State(
        user=User(name="Test", write_access=True),
        parent_state=MagicMock(),
    )
    monkeypatch.setattr(State, "_mark_dirty", MagicMock(spec=State._mark_dirty))

    assert state.user
    assert "/" in str(list(state.logout()))  # type: ignore[operator]
    assert state.user is None


def test_state_check_login_pass() -> None:
    state = State(user=User(name="Test", write_access=True))
    assert state.user

    assert list(state.check_ldap_login()) == []  # type: ignore[operator]


def test_state_check_login_fail() -> None:
    state = State()
    assert state.user is None

    assert "/login" in str(list(state.check_ldap_login()))  # type: ignore[operator]
