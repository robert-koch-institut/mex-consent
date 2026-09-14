from typing import cast

import reflex as rx

from mex.consent.locale_service import LocaleService, MExLocale
from mex.consent.models import User
from mex.consent.state import State

locale_service = LocaleService.get()

# The nav bar is a solid accent surface, so its children cannot rely on the
# theme's default foreground colors. These vars are declared on the nav bar and
# inherited by everything inside it.
NAV_BAR_PALETTE = {
    "--nav-bar-bg": "var(--accent-11)",
    "--nav-bar-fg": "var(--accent-contrast)",
    "--nav-bar-button-bg": "var(--accent-12)",
    "--nav-bar-button-bg-hover": (
        "color-mix(in srgb, var(--accent-12) 70%, var(--accent-11))"
    ),
}


def logout_button() -> rx.Component:
    """Return a logout button with a trailing arrow icon."""
    return rx.button(
        State.label_nav_bar_logout_button,
        rx.icon("arrow-right", size=18),
        on_click=State.logout,
        variant="solid",
        style=rx.Style(
            margin="0",
            # fixed width, so translating the label does not shift the nav bar
            width="calc(140px * var(--scaling))",
            backgroundColor="var(--nav-bar-button-bg)",
            color="var(--nav-bar-fg)",
        ),
        _hover={"backgroundColor": "var(--nav-bar-button-bg-hover)"},
        custom_attrs={"data-testid": "logout-button"},
    )


def user_menu() -> rx.Component:
    """Return a flat user menu with the user's name and a logout button."""
    return rx.hstack(
        rx.text(
            cast("User", State.user).name,
            style=rx.Style(userSelect="none", whiteSpace="nowrap"),
        ),
        logout_button(),
        spacing="3",
        style=rx.Style(alignItems="center"),
        custom_attrs={"data-testid": "user-menu"},
    )


def language_switcher_segment(locale: MExLocale) -> rx.Component:
    """Render one segment of the language switcher for the given locale."""
    is_current = State.current_locale == locale.id
    return rx.button(
        locale.code,
        on_click=State.change_locale(locale.id),  # type: ignore[operator]
        title=locale.label,
        variant="ghost",
        radius="none",
        style=rx.Style(
            margin="0",
            paddingLeft="var(--space-3)",
            paddingRight="var(--space-3)",
            fontWeight="var(--font-weight-bold)",
            backgroundColor=rx.cond(
                is_current, "var(--nav-bar-button-bg)", "transparent"
            ),
            color="var(--nav-bar-fg)",
        ),
        _hover={"backgroundColor": "var(--nav-bar-button-bg-hover)"},
        custom_attrs={
            "data-testid": f"language-switcher-{locale.id}",
            "aria-pressed": is_current,
        },
    )


def language_switcher() -> rx.Component:
    """Render a language switcher with one button segment per available locale."""
    return rx.hstack(
        rx.foreach(
            locale_service.get_available_locales(),
            language_switcher_segment,
        ),
        spacing="0",
        style=rx.Style(
            alignItems="stretch",
            border="1px solid var(--nav-bar-button-bg)",
            borderRadius="var(--radius-3)",
            overflow="hidden",
        ),
        custom_attrs={"data-testid": "language-switcher"},
    )


def mex_wordmark() -> rx.Component:
    """Return the MEx wordmark, tinted with the surrounding text color.

    The svg is used as a mask rather than an image, so that the same asset works
    on the light login card and on the solid accent nav bar.
    """
    return rx.box(
        style=rx.Style(
            {
                # the intrinsic size of assets/mex-logo.svg is 66x25
                "height": "calc(25px * var(--scaling))",
                "width": "calc(66px * var(--scaling))",
                "flexShrink": "0",
                "backgroundColor": "currentColor",
                "maskImage": "url(/mex-logo.svg)",
                "maskRepeat": "no-repeat",
                "maskSize": "contain",
                "maskPosition": "center",
                "WebkitMaskImage": "url(/mex-logo.svg)",
                "WebkitMaskRepeat": "no-repeat",
                "WebkitMaskSize": "contain",
                "WebkitMaskPosition": "center",
            }
        ),
        role="img",
        aria_label="MEx",
    )


def consent_logo() -> rx.Component:
    """Return the consent logo with the MEx wordmark and the app name."""
    return rx.hstack(
        mex_wordmark(),
        rx.heading(
            "Consent",
            weight="medium",
            style=rx.Style(userSelect="none"),
        ),
        spacing="3",
        align="center",
        custom_attrs={"data-testid": "app-logo"},
    )


def nav_bar() -> rx.Component:
    """Return a navigation bar component."""
    return rx.vstack(
        rx.box(
            style=rx.Style(
                height="var(--space-6)",
                width="100%",
                backdropFilter="var(--backdrop-filter-panel)",
            ),
        ),
        rx.card(
            rx.hstack(
                consent_logo(),
                rx.spacer(),
                rx.hstack(
                    language_switcher(),
                    user_menu(),
                    style=rx.Style(alignItems="center"),
                    spacing="7",
                ),
                justify="between",
                align_items="center",
            ),
            size="2",
            custom_attrs={"data-testid": "nav-bar"},
            style=rx.Style(
                {
                    **NAV_BAR_PALETTE,
                    # radix paints the card surface on a ::before pseudo element
                    "--card-background-color": "var(--nav-bar-bg)",
                    "color": "var(--nav-bar-fg)",
                    "width": "100%",
                    "marginTop": "calc(-1 * var(--base-card-border-width))",
                }
            ),
        ),
        spacing="0",
        style=rx.Style(
            maxWidth="var(--app-max-width)",
            minWidth="var(--app-min-width)",
            position="fixed",
            top="0",
            width="100%",
            zIndex="1000",
        ),
    )


def page(*children: rx.Component) -> rx.Component:
    """Return a page fragment with navigation bar and given children.

    Args:
        *children: Components to render in the page body
    """
    page_content = [
        nav_bar(),
        rx.hstack(
            *children,
            style=rx.Style(
                maxWidth="var(--app-max-width)",
                minWidth="var(--app-min-width)",
                padding="calc(var(--space-6) * 4) var(--space-6) var(--space-6)",
                width="100%",
            ),
            custom_attrs={"data-testid": "page-body"},
        ),
    ]

    return rx.cond(
        State.user,
        rx.center(
            *page_content,
            style=rx.Style(
                {
                    "--app-max-width": "calc(1480px * var(--scaling))",
                    "--app-min-width": "calc(800px * var(--scaling))",
                    "width": "100%",
                }
            ),
        ),
        rx.center(
            rx.spinner(size="3"),
            style=rx.Style(marginTop="40vh"),
        ),
    )
