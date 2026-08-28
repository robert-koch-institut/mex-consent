from collections.abc import Generator
from dataclasses import dataclass
from typing import Any, Literal

import reflex as rx
from reflex.event import EventSpec
from requests import RequestException

from mex.common.backend_api.connector import BackendApiConnector, ReferenceFilter
from mex.common.models import AnyMergedModel
from mex.consent.exceptions import escalate_error, response_payload
from mex.consent.models import MergedLoginPerson, SearchResult
from mex.consent.pagination_component import (
    PaginationStateMixin,
    build_pagination_options,
    pagination,
)
from mex.consent.search_results_component import search_results_list
from mex.consent.state import ConsentState
from mex.consent.transform import (
    add_external_links_to_results,
    transform_models_to_search_results,
)
from mex.consent.utils import resolve_editor_value


@dataclass
class CategoryListConfig:
    """Config to store consent category list settings."""

    entity_type: str
    reference_fields: list[str]


CATEGORY_CONFIG: dict[str, CategoryListConfig] = {
    "resources": CategoryListConfig(
        "MergedResource", ["contact", "contributor", "creator"]
    ),
    "publications": CategoryListConfig(
        "MergedBibliographicResource", ["creator", "editor", "editorOfSeries"]
    ),
    "projects": CategoryListConfig("MergedActivity", ["contact", "involvedPerson"]),
}


def fetch_referencing_items(
    config: CategoryListConfig, identifier: str
) -> list[AnyMergedModel]:
    """Fetch the items that reference the given person in any of the config's fields.

    The backend combines multiple reference filters with AND, so it cannot answer
    "referenced by this person in any of these roles" in a single query. Until it can,
    we ask one reference field at a time and deduplicate here, because the same item
    can reference the same person in several of the fields at once.

    Args:
        config: Config of the category to fetch the items for
        identifier: Identifier of the merged person the items should reference

    Raises:
        RequestException: If any of the searches was not accepted, crashes or times out

    Returns:
        The deduplicated items, in the order of the config's reference fields
    """
    connector = BackendApiConnector.get()
    items_by_identifier: dict[str, AnyMergedModel] = {}
    for reference_field in config.reference_fields:
        for item in connector.fetch_all_merged_items(
            entity_type=[config.entity_type],
            reference_filters=[
                ReferenceFilter(field=reference_field, identifiers=[identifier])
            ],
        ):
            items_by_identifier.setdefault(str(item.identifier), item)
    return list(items_by_identifier.values())


class ConsentCategoryList(rx.ComponentState, PaginationStateMixin):
    """ComponentState to show user specific items with pagination."""

    config: CategoryListConfig | None = None
    merged_login_person: MergedLoginPerson | None = None
    category: str = ""
    is_loading = False
    items: list[SearchResult] = []
    limit = 5

    @rx.event
    def fetch_data(self) -> Generator[EventSpec | None]:
        """Fetch user-related data based on category."""
        if not self.merged_login_person or not self.config:
            yield None
            return

        self.is_loading = True
        yield None

        try:
            merged_items = fetch_referencing_items(
                self.config, str(self.merged_login_person.identifier)
            )
        except RequestException as exc:
            self.is_loading = False
            self.set_current_page(1)  # type:ignore[operator]
            self.set_total(0)  # type:ignore[operator]
            self.items = []
            yield None
            yield from escalate_error(
                "backend", "error fetching merged items", response_payload(exc)
            )
            return

        transformed_results = transform_models_to_search_results(merged_items)
        transformed_results = add_external_links_to_results(transformed_results)

        self.is_loading = False
        # the backend cannot paginate the union, so we page through it ourselves;
        # setting the total first clamps the current page that we then slice for
        self.set_total(len(transformed_results))  # type:ignore[operator]
        self.items = transformed_results[self.skip : self.skip + self.limit]

    @rx.event(background=True)
    async def resolve_identifiers(self) -> None:
        """Resolve identifiers to human-readable display values."""
        for result in self.items:
            for preview in result.preview:
                if preview.identifier and not preview.text:
                    async with self:
                        await resolve_editor_value(preview)

    @rx.event
    def initialize(
        self, category: str, merged_login_person: MergedLoginPerson | None
    ) -> Generator[EventSpec | None]:
        """Initialize the component state."""
        self.category = category
        self.merged_login_person = merged_login_person

        config = CATEGORY_CONFIG.get(category)
        if not config:
            err_msg = f"Invalid category {category}."
            raise ValueError(err_msg)
        self.config = config

        yield type(self).fetch_data  # type:ignore[misc]
        yield type(self).resolve_identifiers

    @rx.event
    def cleanup(self) -> None:
        """Cleanup the component state."""
        self.category = ""
        self.items = []
        self.is_loading = False
        self.config = None
        self.reset_pagination()  # type: ignore[operator]

    @classmethod
    def get_component(
        cls,
        category: Literal["resources", "publications", "projects"],
        merged_login_person: MergedLoginPerson | None,
        **props: dict[str, Any],
    ) -> rx.Component:
        """Get the category list component."""
        title = getattr(ConsentState, f"label_{category}_title")
        style = props.pop("style", rx.Style())

        return rx.box(
            rx.cond(
                cls.is_loading,
                rx.center(
                    rx.spinner(size="3"),
                    style=rx.Style(
                        width="100%",
                        marginBottom="var(--space-8)",
                    ),
                ),
                rx.vstack(
                    rx.text(
                        title,
                        weight="bold",
                        style=rx.Style(
                            textTransform="uppercase",
                        ),
                    ),
                    search_results_list(cls.items, style=rx.Style(width="100%")),
                    pagination(
                        build_pagination_options(
                            cls,
                            cls.fetch_data(category),  # type:ignore[operator]
                            cls.resolve_identifiers,
                        )
                    ),
                    style=rx.Style(
                        textAlign="center",
                        marginBottom="var(--space-8)",
                    ),
                    custom_attrs={"data-testid": f"user-{category}"},
                ),
            ),
            on_mount=cls.initialize(category, merged_login_person).debounce(500),  # type:ignore[operator]
            on_unmount=cls.cleanup,
            style=style,
        )
