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
from mex.consent.exceptions import escalate_error, response_payload
from mex.consent.label_var import label_var
from mex.consent.locale_service import LocaleService
from mex.consent.models import MergedLoginPerson, SearchResult, User
from mex.consent.settings import ConsentSettings
from mex.consent.transform import transform_models_to_search_results


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
        """Log out a user."""
        self.reset()  # type: ignore[no-untyped-call]
        yield rx.redirect("/")

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

    @label_var(label_id="consent.resources.title")
    def label_resources_title(self) -> None:
        """Label for resources.title."""

    @label_var(label_id="consent.projects.title")
    def label_projects_title(self) -> None:
        """Label for projects.title."""

    @label_var(label_id="consent.publications.title")
    def label_publications_title(self) -> None:
        """Label for publications.title."""

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
