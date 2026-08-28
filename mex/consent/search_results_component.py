from collections.abc import Callable
from dataclasses import dataclass, field

import reflex as rx

from mex.consent.components import (
    icon_by_stem_type,
    render_additional_titles,
    render_title,
    render_value,
)
from mex.consent.models import EditorValue, SearchResult


@dataclass
class SearchResultsListItemOptions:
    """Options for rendering a search results list item."""

    render_title_fn: Callable[[SearchResult, int], rx.Component] | None = None
    render_prepend_fn: Callable[[SearchResult, int], rx.Component] | None = None
    render_append_fn: Callable[[SearchResult, int], rx.Component] | None = None


@dataclass
class SearchResultsListOptions:
    """Options for rendering a search results list."""

    item_options: SearchResultsListItemOptions = field(
        default_factory=SearchResultsListItemOptions
    )


def _render_properties(
    properties: list[EditorValue], property_type: str
) -> rx.Component:
    """Render a list of properties."""
    return rx.hstack(
        rx.foreach(
            properties,
            render_value,
        ),
        style=rx.Style(
            color="var(--gray-12)",
            fontWeight="var(--font-weight-light)",
            max_width="100%",
        ),
        wrap="wrap",
        align="center",
        custom_attrs={"data-testid": f"display-properties-{property_type}"},
    )


def _search_results_item(
    item: SearchResult, index: int, options: SearchResultsListItemOptions
) -> rx.Component:
    """Render a search results item."""
    title = render_title(item.title[0])

    title_line_children = [
        icon_by_stem_type(
            item.stem_type,
            size=22,
            style=rx.Style(color=rx.color("accent", 11), flex="0 0 22px"),
        ),
        title,
        render_additional_titles(item.title[1:]),
    ]

    if options.render_title_fn:
        title_line_children.append(options.render_title_fn(item, index))

    vstack_children: list[rx.Component] = [
        rx.hstack(*title_line_children, align="center")
    ]
    vstack_children.append(_render_properties(item.preview, "preview"))

    card_content = []
    if options.render_prepend_fn:
        card_content.append(options.render_prepend_fn(item, index))

    card_content.append(
        rx.vstack(
            *vstack_children,
            align="stretch",
            style=rx.Style(width="100%", flex="1", min_width="0"),
        )
    )

    if options.render_append_fn:
        card_content.append(options.render_append_fn(item, index))

    # give every card the height of a single-line snippet, so that the list reads
    # as an even stack: vertical card padding + vstack gap + title and preview row
    # (each 1.5em, the line height of the text they contain)
    height = "calc(2 * var(--card-padding) + var(--space-3) + 3em)"

    return rx.card(
        rx.hstack(
            *card_content,
            align="stretch",
        ),
        class_name="search-result-card",
        custom_attrs={"data-testid": f"search-result-{item.identifier}"},
        style=rx.Style(
            width="100%",
            flex="0 0 auto",
            height=height,
        ),
    )


def search_results_list(
    items: list[SearchResult] | rx.Var[list[SearchResult]],
    options: SearchResultsListOptions | None = None,
    style: rx.Style | None = None,
) -> rx.Component:
    """Render a list of search results items."""
    options = options or SearchResultsListOptions()

    used_style = rx.Style(overflow="auto")
    used_style.update(style or {})

    return rx.cond(
        items,
        rx.vstack(
            rx.foreach(
                items, lambda x, i: _search_results_item(x, i, options.item_options)
            ),
            style=used_style,
            custom_attrs={"data-testid": "search-results-list"},
        ),
    )
