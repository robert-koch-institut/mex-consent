import reflex as rx

from mex.consent.categories import CATEGORY_PAIRS
from mex.consent.consent_category_list import ConsentCategoryList
from mex.consent.layout import page
from mex.consent.state import ConsentState

# the waiting pulse of the loading bar, keyed to `mex-progress-pulse` in the app style
PROGRESS_PULSE_ANIMATION = "mex-progress-pulse 1.4s ease-in-out infinite"


def user_data() -> rx.Component:
    """Render the user data section with name and email."""
    return rx.cond(
        ConsentState.merged_login_person,
        rx.hstack(
            rx.icon(
                "circle-user",
                size=64,
                style=rx.Style(color="var(--accent-11)"),
            ),
            rx.vstack(
                rx.text(
                    ConsentState.merged_login_person.full_name,  # type: ignore  [union-attr]
                    style=rx.Style(
                        fontWeight="var(--font-weight-bold)",
                        fontSize="var(--font-size-6)",
                    ),
                ),
                rx.foreach(
                    ConsentState.merged_login_person.email,  # type: ignore[union-attr, arg-type]
                    lambda email: rx.link(
                        email,
                        href="mailto:" + email,
                        high_contrast=True,
                        custom_attrs={"data-testid": "user-email"},
                    ),
                ),
                # orcid ids already arrive as full https://orcid.org/... urls
                rx.foreach(
                    ConsentState.merged_login_person.orcid_id,  # type: ignore[union-attr, arg-type]
                    lambda orcid_id: rx.link(
                        orcid_id,
                        href=orcid_id,
                        high_contrast=True,
                        is_external=True,
                        custom_attrs={"data-testid": "user-orcid-id"},
                    ),
                ),
                spacing="0",
            ),
            align="center",
            spacing="4",
            style=rx.Style(
                marginBottom="var(--space-4)",
            ),
            custom_attrs={"data-testid": "user-data"},
        ),
        # the same gate as the progress bar: while booting or loading this says so,
        # but a hydrated page without a user is on its way out and stays blank
        rx.cond(
            ConsentState.show_category_progress,
            rx.text(
                ConsentState.label_user_data_loading,
                custom_attrs={"data-testid": "user-data"},
            ),
            rx.fragment(),
        ),
    )


def consent_box() -> rx.Component:
    """Render the consent box with text and buttons."""
    return rx.card(
        rx.vstack(
            rx.markdown(ConsentState.consent_md),
            consent_status(),
            rx.hstack(
                rx.button(
                    ConsentState.label_consent_box_consent_button,
                    on_click=ConsentState.submit_rule_set("consent"),  # type: ignore[operator]
                    disabled=ConsentState.is_consent_valid_for_processing,
                    color_scheme="jade",
                    custom_attrs={"data-testid": "accept-consent-button"},
                ),
                rx.spacer(),
                rx.button(
                    ConsentState.label_consent_box_no_consent_button,
                    on_click=ConsentState.submit_rule_set("denial"),  # type: ignore[operator]
                    disabled=ConsentState.consent_status.bool(),  # type: ignore[union-attr]
                    color_scheme="tomato",
                    custom_attrs={"data-testid": "denial-consent-button"},
                ),
                style=rx.Style(padding="var(--space-4) 0"),
            ),
            rx.cond(
                ConsentState.is_consent_valid_for_processing,
                rx.text(
                    ConsentState.label_consent_retraction_denial,
                    style=rx.Style(
                        color="var(--gray-11)",
                    ),
                    custom_attrs={"data-testid": "consent-change-blocked-info"},
                ),
            ),
            style=rx.Style(
                display="flex",
                width="100%",
            ),
        ),
        style=rx.Style(
            backgroundColor="var(--accent-3)",
            padding="var(--space-4)",
        ),
        custom_attrs={"data-testid": "consent-box"},
    )


def consent_status() -> rx.Component:
    """Render the current consent status for the user."""
    return rx.hstack(
        rx.text(f"{ConsentState.merged_login_person.full_name}:"),  # type: ignore[union-attr]
        rx.cond(
            ConsentState.consent_status,
            rx.cond(
                ConsentState.is_consent_valid_for_processing,
                rx.text(
                    ConsentState.label_consent_status_consented_format,
                    color_scheme="jade",
                ),
                rx.text(
                    ConsentState.label_consent_status_declined_format,
                    color_scheme="tomato",
                ),
            ),
            rx.text(
                ConsentState.label_consent_status_no_consent,
                color_scheme="gray",
            ),
        ),
        custom_attrs={"data-testid": "consent-status"},
    )


def loading_progress() -> rx.Component:
    """Render one progress bar while the category lists are still fetching.

    Each list reports its count once its fetch lands, so the number of reports is the
    progress. One bar replaces the one-spinner-per-list the page used to show, which
    flashed a spinner for every role the user could hold, most of them empty.

    The page is served before the frontend has hydrated, and no event handler runs
    until it has, so there is a stretch at the start where nothing can be reported yet.
    That stretch pulses the empty bar instead of handing radix a bar with no value at
    all: radix reads a missing value as indeterminate, and its indeterminate animation
    fakes a fill to 90% before it starts pulsing 12.5 seconds in, so every page load
    played the fake fill and then dropped back to the real first count.

    The same `rx.progress` is rendered throughout, rather than swapping between two of
    them on whether anything has been reported: a swap unmounts one bar and mounts
    another, which reads as a restart of its own.
    """
    return rx.cond(
        ConsentState.show_category_progress,
        rx.vstack(
            rx.text(
                ConsentState.label_category_list_loading,
                style=rx.Style(color="var(--gray-11)"),
            ),
            rx.progress(
                value=ConsentState.categories_reported,
                max=len(CATEGORY_PAIRS),
                style=rx.Style(
                    width="100%",
                    # a zero-width indicator has nothing to animate, so the pulse is
                    # on the track, and it stops as soon as there is real progress
                    animation=rx.cond(
                        ConsentState.categories_reported > 0,
                        "none",
                        PROGRESS_PULSE_ANIMATION,
                    ),
                ),
            ),
            style=rx.Style(
                marginBottom="var(--space-8)",
                width="100%",
            ),
            custom_attrs={"data-testid": "category-loading-progress"},
        ),
        rx.fragment(),
    )


def no_items_message() -> rx.Component:
    """Render a hint for users that are not referenced by any item."""
    return rx.cond(
        ConsentState.show_categories & ConsentState.all_categories_empty,
        rx.callout(
            ConsentState.label_category_list_empty,
            icon="info",
            style=rx.Style(
                marginBottom="var(--space-8)",
                width="100%",
            ),
            custom_attrs={"data-testid": "no-items-message"},
        ),
    )


def index() -> rx.Component:
    """Return the index for the merge and extracted search component."""
    return page(
        rx.vstack(
            user_data(),
            loading_progress(),
            # one list per role the user can be referenced in, each collapsing to
            # nothing while it is empty, so only the roles that apply show up
            *[
                ConsentCategoryList.create(pair.stem_type, pair.field)
                for pair in CATEGORY_PAIRS
            ],
            no_items_message(),
            rx.spacer(direction="column"),
            rx.box(
                consent_box(),
                style=rx.Style(
                    justifyContent="center",
                    display="flex",
                    width="100%",
                ),
            ),
            style=rx.Style(
                width="100%",
                align="center",
                justify="center",
                flexGrow="1",
            ),
            custom_attrs={"data-testid": "consent-index"},
        ),
    )
