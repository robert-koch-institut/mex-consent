import asyncio
from collections.abc import AsyncGenerator, Generator
from typing import Any, cast

import reflex as rx
from reflex.event import EventSpec
from requests import RequestException

from mex.common.backend_api.connector import BackendApiConnector, ReferenceFilter
from mex.consent.categories import CategoryPair
from mex.consent.exceptions import escalate_error, response_payload
from mex.consent.locale_service import LocaleService
from mex.consent.models import SearchResult
from mex.consent.pagination_component import (
    PaginationStateMixin,
    build_pagination_options,
    pagination,
)
from mex.consent.search_results_component import search_results_list
from mex.consent.state import ConsentState, State
from mex.consent.transform import (
    add_external_links_to_results,
    transform_models_to_search_results,
)
from mex.consent.utils import resolve_editor_value

# the msgid of the pattern that joins the entity type and the field label
TITLE_FORMAT_LABEL_ID = "consent.category_list.title_format"


def build_category_title(pair: CategoryPair) -> rx.Var[str]:
    """Build a heading that names the entity type and the role the user holds.

    Both halves come from the catalogs that `mex-model` already ships, so a new
    reference field needs no new message of its own. The pair is fixed when the page
    is built and the locales are known at import time, so we translate every locale up
    front and let reflex switch between them, instead of resolving translations in a
    computed var that would have to reach into another state.

    Args:
        pair: The entity type and reference field to build the heading for

    Returns:
        A var resolving to the heading for the currently selected locale
    """
    locale_service = LocaleService.get()
    cases = [
        (
            locale.id,
            locale_service.get_ui_label(locale.id, TITLE_FORMAT_LABEL_ID).format(
                locale_service.get_ui_label(locale.id, pair.stem_type),
                locale_service.get_field_label(
                    locale.id, pair.stem_type, pair.field, n=2
                ),
            ),
        )
        for locale in locale_service.get_available_locales()
    ]
    return cast("rx.Var[str]", rx.match(State.current_locale, *cases, cases[0][1]))


def fetch_page(
    entity_type: str,
    reference_field: str,
    identifier: str,
    skip: int,
    limit: int,
) -> tuple[list[SearchResult], int]:
    """Fetch one page of items referencing the given person in one role.

    This is a plain function rather than a method because it runs in a worker thread:
    `BackendApiConnector` is synchronous, and calling it on the event loop stalls every
    other event for the session, including the logout button.

    Args:
        entity_type: The merged entity type to query
        reference_field: The field that has to reference the person
        identifier: The merged person identifier to filter on
        skip: How many items to skip
        limit: How many items to return

    Returns:
        The page of search results and the total number of matching items
    """
    connector = BackendApiConnector.get()
    response = connector.fetch_merged_items(
        entity_type=[entity_type],
        reference_filters=[
            ReferenceFilter(field=reference_field, identifiers=[identifier])
        ],
        skip=skip,
        limit=limit,
    )
    results = add_external_links_to_results(
        transform_models_to_search_results(response.items)
    )
    return results, response.total


class ConsentCategoryList(rx.ComponentState, PaginationStateMixin):
    """ComponentState to show the items referencing a user in one specific role."""

    entity_type: str = ""
    reference_field: str = ""
    category_key: str = ""
    items: list[SearchResult] = []
    limit = 5

    @rx.event(background=True)
    async def fetch_data(self) -> AsyncGenerator[EventSpec | None]:
        """Fetch the page of items that reference the user in this role.

        Filtering on a single reference field lets the backend do the paging, so this
        only ever transfers the items that are about to be rendered, and the total it
        returns is exact.

        This is a background event on purpose. Reflex holds one exclusive lock per
        session for the whole duration of a foreground event, and ten of these fire at
        once on mount, so running them in the foreground queued every other event -
        most visibly the logout button, which did nothing until all ten had finished.
        """
        async with self:
            consent_state = await self.get_state(ConsentState)
            merged_login_person = consent_state.merged_login_person
            entity_type = self.entity_type
            reference_field = self.reference_field
            category_key = self.category_key
            limit = self.limit
            requested_skip = self.skip

        if not merged_login_person or not entity_type:
            yield None
            return

        identifier = str(merged_login_person.identifier)
        try:
            results, total = await asyncio.to_thread(
                fetch_page,
                entity_type,
                reference_field,
                identifier,
                requested_skip,
                limit,
            )
            async with self:
                self.set_total(total)  # type:ignore[operator]
                clamped_skip = self.skip
            if clamped_skip != requested_skip:
                # the total shrank and clamped us onto an earlier page than the one
                # we asked for, so fetch the page we actually ended up on
                results, _ = await asyncio.to_thread(
                    fetch_page,
                    entity_type,
                    reference_field,
                    identifier,
                    clamped_skip,
                    limit,
                )
        except RequestException as exc:
            async with self:
                self.set_current_page(1)  # type:ignore[operator]
                self.set_total(0)  # type:ignore[operator]
                self.items = []
            yield ConsentState.report_category_count(category_key, 0)  # type:ignore[operator]
            for event in escalate_error(
                "backend", "error fetching merged items", response_payload(exc)
            ):
                yield event
            return

        async with self:
            self.items = results
        yield ConsentState.report_category_count(category_key, total)  # type:ignore[operator]

        # resolving happens here rather than in an event of its own: both would be
        # background events started from the same handler, so they would run at the
        # same time and the resolver would loop over items that are not fetched yet.
        # the list has already painted by now, the report above sent its delta.
        # iterate `self.items`, not the local `results`: only mutations that go
        # through the state's mutable proxy mark it dirty and reach the frontend
        for result in self.items:
            for preview in result.preview:
                if preview.identifier and not preview.text:
                    async with self:
                        await resolve_editor_value(preview)

    @rx.event
    def initialize(
        self, entity_type: str, reference_field: str, category_key: str
    ) -> Generator[EventSpec | None]:
        """Initialize the component state."""
        self.entity_type = entity_type
        self.reference_field = reference_field
        self.category_key = category_key

        yield type(self).fetch_data

    @rx.event
    def cleanup(self) -> None:
        """Cleanup the component state.

        These states hang off the root state, not off `State`, so `State.logout` does
        not reach them and this is the only thing that clears them. The counts they
        report live on `ConsentState`, which logout does reset.
        """
        self.entity_type = ""
        self.reference_field = ""
        self.category_key = ""
        self.items = []
        self.reset_pagination()  # type: ignore[operator]

    @classmethod
    def get_component(
        cls,
        stem_type: str,
        reference_field: str,
        **props: dict[str, Any],
    ) -> rx.Component:
        """Get a list of the items referencing the user in one specific role."""
        pair = CategoryPair(stem_type, reference_field)
        style = rx.Style(width="100%")
        style.update(props.pop("style", rx.Style()))
        # the box has to stay mounted even while the list is empty, because on_mount
        # is what triggers the fetch that decides whether it has anything to show;
        # collapsing it with `display` keeps it out of the surrounding stack's layout.
        # waiting for `categories_ready` holds every list back until all of them have
        # reported, so they appear together instead of popping in one at a time
        style["display"] = rx.cond(
            ConsentState.show_categories & (cls.total > 0), "block", "none"
        )

        return rx.box(
            rx.cond(
                cls.total > 0,
                rx.vstack(
                    rx.text(
                        build_category_title(pair),
                        weight="bold",
                        style=rx.Style(
                            textTransform="uppercase",
                        ),
                    ),
                    search_results_list(cls.items, style=rx.Style(width="100%")),
                    rx.cond(
                        cls.max_page > 1,
                        pagination(
                            build_pagination_options(
                                cls,
                                cls.fetch_data,
                            )
                        ),
                    ),
                    style=rx.Style(
                        textAlign="center",
                        marginBottom="var(--space-8)",
                        width="100%",
                    ),
                    custom_attrs={"data-testid": pair.test_id},
                ),
            ),
            # deliberately not debounced: with one list per reference field, ten of
            # these mount at once, and debouncing them dropped roughly one `on_mount`
            # per page load at random. A list that never fetches never reports its
            # count, which silently suppresses the "nothing found" message, so a
            # duplicate fetch under react strict mode is the cheaper trade
            on_mount=cls.initialize(  # type:ignore[operator]
                pair.entity_type, pair.field, pair.key
            ),
            on_unmount=cls.cleanup,
            style=style,
        )
