import reflex as rx
from reflex.event import EventHandler
from reflex.istate.proxy import StateProxy

from mex.consent.consent_category_list import ConsentCategoryList


def test_background_event_can_reach_its_own_event_handlers() -> None:
    """Pin the class lookup `fetch_data` uses to chain into `resolve_previews`.

    Inside a background event reflex passes a `StateProxy` as `self`, so `type(self)`
    is the proxy class and carries none of the state's event handlers, while
    `self.__class__` forwards to the state underneath. Yielding the wrong one raises
    only after the items have been sent, so the list still paints and just never
    resolves its identifiers - which no rendering assertion notices.
    """
    component = ConsentCategoryList.create("Resource", "contact")
    state_cls = component.State
    assert state_cls is not None
    root = rx.State(_reflex_internal_init=True)  # type: ignore[call-arg]
    proxy = StateProxy(
        state_cls(_reflex_internal_init=True, parent_state=root)  # type: ignore[call-arg]
    )

    # mypy types `__class__` as the proxy's own, which is exactly the assumption
    # that made the original mistake look correct, so it needs telling otherwise
    assert proxy.__class__ is state_cls  # type: ignore[comparison-overlap]
    assert isinstance(proxy.__class__.resolve_previews, EventHandler)  # type: ignore[attr-defined]
    # the trap: `type()` looks past the proxy's forwarding and finds nothing
    assert not hasattr(type(proxy), "resolve_previews")
