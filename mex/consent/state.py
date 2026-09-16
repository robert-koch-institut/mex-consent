import asyncio
from collections.abc import Generator
from datetime import datetime
from urllib.parse import urlparse, urlunparse
from zoneinfo import ZoneInfo

import reflex as rx
from reflex.event import EventSpec
from reflex.istate.data import ReflexURL
from requests import RequestException

from mex.common.backend_api.connector import BackendApiConnector, ReferenceFilter
from mex.common.models import (
    AdditiveConsent,
    AnyRuleSetRequest,
    AnyRuleSetResponse,
    ConsentRuleSetRequest,
)
from mex.common.types import ConsentStatus, ConsentType, YearMonthDayTime
from mex.consent.categories import CATEGORY_PAIRS
from mex.consent.exceptions import escalate_error, response_payload
from mex.consent.label_var import label_var
from mex.consent.locale_service import LocaleService
from mex.consent.models import MergedLoginPerson, SearchResult, User
from mex.consent.settings import ConsentSettings
from mex.consent.transform import transform_models_to_search_results

# how long to wait for the last category list to report before showing the rest
CATEGORY_REVEAL_TIMEOUT = 15.0


class State(rx.State):
    """The base state for the app."""

    _locale_service = LocaleService.get()
    _available_locales = _locale_service.get_available_locales()

    current_locale: str = next(
        (x for x in _available_locales if x.id.lower().startswith("de")),
        _available_locales[0],
    ).id
    user: User | None = None
    merged_login_person: MergedLoginPerson | None = None
    target_path_after_login: str | None = None

    @rx.event
    def change_locale(self, locale: str) -> None:
        """Change the current locale to the given one and reload the page.

        Args:
            locale: The locale to change to.
        """
        self.current_locale = locale

    @rx.event
    def logout(self) -> Generator[EventSpec]:
        """Log out a user.

        Straight to `/login` rather than to `/`: landing on the consent page first
        means mounting it without a user and waiting a full round trip for
        `check_ldap_login` to bounce back, which flashes its loading state on the way
        out.
        """
        self.reset()  # type: ignore[no-untyped-call]
        yield rx.redirect("/login")

    @staticmethod
    def _strip_frontend_path(url: ReflexURL) -> str:
        config = rx.config.get_config()
        parsed = urlparse(url)
        path = parsed.path
        if path.startswith(config.frontend_path):
            path = path[len(config.frontend_path) :] or "/"
        return str(urlunparse(parsed._replace(path=path)))

    @rx.event
    def check_ldap_login(self) -> Generator[EventSpec]:
        """Check if a user is logged in to ldap."""
        if self.user is None:
            self.target_path_after_login = self._strip_frontend_path(self.router.url)
            yield rx.redirect("/login", replace=True)

    @label_var(label_id="components.titles.additional_titles")
    def label_additional_titles(self) -> None:
        """Label for titles.additional_titles."""

    @label_var(label_id="components.pagination.next_button")
    def label_pagination_next_button(self) -> None:
        """Label for pagination.next_button."""

    @label_var(label_id="components.pagination.previous_button")
    def label_pagination_previous_button(self) -> None:
        """Label for pagination.previous_button."""

    @label_var(label_id="layout.nav_bar.logout_button")
    def label_nav_bar_logout_button(self) -> None:
        """Label for nav_bar.logout_button."""


class ConsentState(State):
    """State for the consent component."""

    consent_status: SearchResult | None = None
    category_counts: dict[str, int] = {}
    reveal_categories_anyway: bool = False
    # bumped once per visit to the consent page, so that the category lists can tell a
    # fresh visit apart from react mounting them for the second time
    page_load_id: int = 0

    @rx.event
    def report_category_count(self, key: str, total: int) -> None:
        """Record how many items one of the category lists found.

        The lists are `rx.ComponentState` instances, which are generated when the page
        is built and are not substates of this one, so they report their totals up here
        rather than this state reaching down into them.

        Args:
            key: The category pair the count belongs to
            total: How many items reference the user in that role
        """
        self.category_counts = {**self.category_counts, key: total}

    @rx.event(background=True)
    async def reveal_categories_after_timeout(self) -> None:
        """Reveal whatever has arrived in case some list never reports in.

        `fetch_data` reports a zero even when the backend call fails, so the only way
        the counts can stall is an `on_mount` that never fires. Without this the lists
        would stay collapsed forever, leaving the page blank below the user data.
        """
        await asyncio.sleep(CATEGORY_REVEAL_TIMEOUT)
        async with self:
            self.reveal_categories_anyway = True

    @rx.var
    def categories_reported(self) -> int:
        """How many of the category lists have finished loading."""
        return len(self.category_counts)

    @rx.var
    def categories_ready(self) -> bool:
        """Whether the category lists are done loading and can be shown.

        The lists stay hidden until every one of them has reported, so they all paint
        at once instead of popping in one after the other while the page reflows.
        """
        return (
            self.categories_reported >= len(CATEGORY_PAIRS)
            or self.reveal_categories_anyway
        )

    @rx.var
    def show_categories(self) -> bool:
        """Whether the category lists and their empty state may be shown.

        `is_hydrated` goes back to false while the frontend navigates, and the client
        still holds the previous page's state until the new one arrives. Without that
        check, logging back in flashes the results of the session before it. `user`
        keeps the lists hidden after a logout, when the redirect to `/login` has not
        gone through yet.
        """
        return self.is_hydrated and self.user is not None and self.categories_ready

    @rx.var
    def show_category_progress(self) -> bool:
        """Whether the loading bar may be shown.

        It covers the boot and navigation windows, where nothing can be reported yet,
        but not a logged-out page waiting on its redirect, which should stay blank.
        """
        if not self.is_hydrated:
            return True
        return self.user is not None and not self.categories_ready

    @rx.var
    def all_categories_empty(self) -> bool:
        """Whether every category list has reported in without finding anything.

        The length check matters because the counts trickle in one list at a time:
        without it the empty state would flash while the page is still loading.
        """
        return len(self.category_counts) == len(CATEGORY_PAIRS) and not any(
            self.category_counts.values()
        )

    @rx.var
    def consent_md(self) -> str:
        """Get the translated consent markdown, based on the current_locale.

        Returns:
            The translated consent markdown.
        """
        settings = ConsentSettings.get()
        return settings.get_consent_text(self.current_locale)

    @rx.var(cache=False)
    def consent_datetime(self) -> str:
        """Update datetime for a users consent status."""
        if not self.consent_status:
            return ""
        timestamp_str = self.consent_status.title[0].text
        timestamp_dt = datetime.fromisoformat(str(timestamp_str))
        timestamp_local = timestamp_dt.astimezone(ZoneInfo("Europe/Berlin"))
        return timestamp_local.strftime("%d.%m.%Y %H:%M")

    @rx.var
    def is_consent_valid_for_processing(self) -> bool:
        """Check if the consent status badge is VALID_FOR_PROCESSING."""
        if not self.consent_status or not self.consent_status.preview:
            return False
        return self.consent_status.preview[0].badge == "VALID_FOR_PROCESSING"

    @rx.event
    def get_consent(self) -> Generator[EventSpec | None]:
        """Fetch the user's consent status."""
        # runs `on_load` for every visit, so it is where the watchdog is re-armed
        # and where the category lists are told that their cached pages are stale
        self.reveal_categories_anyway = False
        self.page_load_id += 1
        if not self.merged_login_person:
            yield None
            return

        connector = BackendApiConnector.get()
        try:
            response = connector.fetch_preview_items(
                query_string=None,
                entity_type=["MergedConsent"],
                reference_filters=[
                    ReferenceFilter(
                        field="hasDataSubject",
                        identifiers=[str(self.merged_login_person.identifier)],
                    )
                ],
            )
        except RequestException as exc:
            yield None
            yield from escalate_error(
                "backend", "No Consent could be fetched.", response_payload(exc)
            )
        else:
            if response.total > 0:
                self.consent_status = transform_models_to_search_results(
                    [response.items[0]]
                )[0]
            else:
                self.consent_status = None

    @rx.event
    def submit_rule_set(
        self,
        consented: str,
    ) -> Generator[EventSpec | None]:
        """Convert the fields to a rule set and submit it to the backend."""
        if not self.merged_login_person:
            yield None
            return

        is_consenting = consented == "consent"

        # Check if the consent status would actually change
        if (
            self.consent_status
            and self.is_consent_valid_for_processing == is_consenting
        ):
            yield None
            return

        additive_consent = AdditiveConsent(
            hasConsentStatus=(
                ConsentStatus["VALID_FOR_PROCESSING"]
                if is_consenting
                else ConsentStatus["INVALID_FOR_PROCESSING"]
            ),
            hasDataSubject=self.merged_login_person.identifier,
            isIndicatedAtTime=YearMonthDayTime(
                datetime.now(tz=ZoneInfo("Europe/Berlin")).isoformat()
            ),
            hasConsentType=(
                ConsentType["EXPRESSED_CONSENT"] if is_consenting else None
            ),
        )

        rule_set_request = ConsentRuleSetRequest(additive=additive_consent)
        try:
            self._send_rule_set_request(rule_set_request)
        except RequestException as exc:
            self.reset()  # type: ignore[no-untyped-call]
            yield from escalate_error(
                "backend", "error submitting rule set", response_payload(exc)
            )
            return
        else:
            yield type(self).get_consent()  # type: ignore[operator]
            yield type(self).show_submit_success_toast()  # type: ignore[operator]

    def _send_rule_set_request(self, rule_set: AnyRuleSetRequest) -> AnyRuleSetResponse:
        """Send the rule set to the backend."""
        connector = BackendApiConnector.get()
        # TODO(ND): use user auth for backend requests (stop-gap MX-1616)
        if self.consent_status:
            return connector.update_rule_set(self.consent_status.identifier, rule_set)
        return connector.create_rule_set(rule_set)

    @rx.event
    def show_submit_success_toast(self) -> EventSpec:
        """Show a toast for a successfully submitted rule-set."""
        return rx.toast.success(
            title=self.label_save_success_dialog_title,
            description=self.label_save_success_dialog_content,
            class_name="editor-toast",
            close_button=True,
            dismissible=True,
            duration=5000,
        )

    @label_var(
        label_id="consent.consent_status.consented_format", deps=["consent_datetime"]
    )
    def label_consent_status_consented_format(self) -> list[str]:
        """Label for consent.consent_status.consented_format."""
        return [self.consent_datetime]

    @label_var(
        label_id="consent.consent_status.declined_format", deps=["consent_datetime"]
    )
    def label_consent_status_declined_format(self) -> list[str]:
        """Label for consent.consent_status.declined_format."""
        return [self.consent_datetime]

    @label_var(label_id="consent.consent_retraction_denial")
    def label_consent_retraction_denial(self) -> None:
        """Label for consent.consent_retraction_denial."""

    @label_var(label_id="consent.consent_status.no_consent")
    def label_consent_status_no_consent(self) -> None:
        """Label for consent.status.no_consent."""

    @label_var(label_id="consent.category_list.empty")
    def label_category_list_empty(self) -> None:
        """Label for category_list.empty."""

    @label_var(label_id="consent.category_list.loading")
    def label_category_list_loading(self) -> None:
        """Label for category_list.loading."""

    @label_var(label_id="consent.user_data.loading")
    def label_user_data_loading(self) -> None:
        """Label for user_data.loading  ."""

    @label_var(label_id="consent.consent_box.consent_button")
    def label_consent_box_consent_button(self) -> None:
        """Label for consent_box.consent_button."""

    @label_var(label_id="consent.consent_box.no_consent_button")
    def label_consent_box_no_consent_button(self) -> None:
        """Label for consent_box.no_consent_button."""

    @label_var(label_id="consent.save_success_dialog.title")
    def label_save_success_dialog_title(self) -> None:
        """Label for save_success_dialog.title."""

    @label_var(label_id="consent.save_success_dialog.content")
    def label_save_success_dialog_content(self) -> None:
        """Label for save_success_dialog.content."""
