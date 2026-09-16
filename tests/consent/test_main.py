import re
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from playwright.sync_api import Page, expect

from tests.conftest import ldap_credentials, set_generous_timeouts


@pytest.fixture
def login_ldap_user(
    page: Page,
    base_url: str,
) -> Page:
    username, password = ldap_credentials()
    # these tests log in themselves, so they opt into the longer timeouts here
    set_generous_timeouts(page)
    page.goto(base_url)
    page.get_by_test_id("input-username").fill(username)
    page.get_by_test_id("input-password").fill(password)
    page.get_by_test_id("login-button").click()
    expect(page.get_by_test_id("nav-bar")).to_be_visible()
    page.screenshot(path="tests_ldap_login.png")
    return page


@pytest.fixture
def consent_page(
    base_url: str,
    login_ldap_user: Page,
) -> Page:
    page = login_ldap_user
    page.goto(base_url)
    page_body = page.get_by_test_id("page-body")
    expect(page_body).to_be_visible()
    # the category lists collapse until they have found something, so gate on the
    # consent box instead: the per-list assertions below wait for their own list
    expect(page.get_by_test_id("consent-box")).to_be_visible()
    page.screenshot(path="tests_consent_test_main-test_index-on-load.png")
    return page


@pytest.mark.integration
@pytest.mark.usefixtures("load_dummy_data")
def test_projects_and_resources(consent_page: Page) -> None:
    page = consent_page
    resources_section = page.get_by_test_id("user-resource-contact")
    expect(resources_section).to_be_visible()
    expect(resources_section).to_contain_text("Bioinformatics Resource 1")
    projects_section = page.get_by_test_id("user-activity-contact")
    expect(projects_section).to_be_visible()
    expect(projects_section).to_contain_text("Aktivität 1")
    # the dummy data references the user as a contact only, so every other role
    # collapses instead of rendering an empty list
    expect(page.get_by_test_id("user-resource-creator")).not_to_be_visible()
    expect(page.get_by_test_id("no-items-message")).not_to_be_visible()


@pytest.mark.integration
@pytest.mark.usefixtures("load_dummy_data")
def test_preview_identifiers_are_resolved(consent_page: Page) -> None:
    page = consent_page
    # the previews arrive holding bare identifiers, which render as nothing until
    # `resolve_previews` has swapped in the referenced item's title. "OU1" is the
    # short name of the organizational unit the dummy resources are in charge of,
    # so it only shows up once that resolving has actually run
    resources_section = page.get_by_test_id("user-resource-contact")
    expect(resources_section).to_be_visible()
    expect(
        resources_section.get_by_test_id("display-properties-preview").first
    ).to_contain_text("OU1")


@pytest.mark.integration
@pytest.mark.usefixtures("load_multi_role_data")
def test_item_referencing_user_twice_shows_in_both_lists(consent_page: Page) -> None:
    page = consent_page
    # the same resource names the user as contact and as creator, so it is listed
    # under both roles instead of being deduplicated into one of them
    contact_section = page.get_by_test_id("user-resource-contact")
    expect(contact_section).to_be_visible()
    expect(contact_section).to_contain_text("Resource With Two Roles")
    creator_section = page.get_by_test_id("user-resource-creator")
    expect(creator_section).to_be_visible()
    expect(creator_section).to_contain_text("Resource With Two Roles")


@pytest.mark.integration
def test_no_items_message(consent_page: Page) -> None:
    # no data fixture, so the graph holds nothing referencing the logged-in user
    page = consent_page
    expect(page.get_by_test_id("no-items-message")).to_be_visible()
    expect(page.get_by_test_id("user-resource-contact")).not_to_be_visible()
    expect(page.get_by_test_id("user-activity-contact")).not_to_be_visible()


@pytest.mark.integration
@pytest.mark.usefixtures("load_dummy_data")
def test_single_page_list_hides_pagination(consent_page: Page) -> None:
    page = consent_page
    # two resources at a page size of five fit on one page, so the pagination
    # controls stay out of the way
    resources_section = page.get_by_test_id("user-resource-contact")
    expect(resources_section).to_be_visible()
    expect(
        resources_section.get_by_test_id("pagination-page-select")
    ).not_to_be_visible()


@pytest.mark.integration
@pytest.mark.usefixtures("load_pagination_dummy_data")
def test_pagination(consent_page: Page) -> None:
    page = consent_page

    res_list = page.get_by_test_id("user-resource-contact")
    pagination_previous = res_list.get_by_test_id("pagination-previous-button")
    pagination_next = res_list.get_by_test_id("pagination-next-button")
    pagination_page_select = res_list.get_by_test_id("pagination-page-select")

    pagination_page_select.scroll_into_view_if_needed()
    page.screenshot(path="tests_consent_test_main_test_pagination.png")

    # check if:
    # - previous is disabled
    # - select shows all expected page numbers
    # - next is enabled
    expect(pagination_previous).to_be_disabled()
    expect(pagination_page_select).to_have_text("1")
    pagination_page_select.click()
    opt1 = page.get_by_role("option", name="1", exact=True)
    expect(opt1).to_be_visible()
    expect(opt1).to_have_attribute("data-state", "checked")
    expect(page.get_by_role("option", name="2", exact=True)).to_be_visible()
    expect(page.get_by_role("option", name="3", exact=True)).to_be_visible()
    expect(pagination_next).to_be_enabled()

    # Navigate to the last page (page 21)
    page.get_by_role("option", name="21", exact=True).click()
    expect(pagination_previous).to_be_enabled()
    expect(pagination_page_select).to_have_text("21")
    expect(pagination_next).to_be_disabled()

    # Test going back one page
    pagination_previous.click()
    expect(pagination_previous).to_be_enabled()
    expect(pagination_page_select).to_have_text("20")
    expect(pagination_next).to_be_enabled()


@pytest.mark.integration
@pytest.mark.usefixtures("load_dummy_data")
def test_index(consent_page: Page) -> None:
    username, _ = ldap_credentials()
    page = consent_page

    # load page and check user information is visible
    user_data = page.get_by_test_id("user-data")
    expect(user_data).to_be_visible()
    expect(user_data).to_contain_text(username)
    expect(user_data).to_contain_text(f"{username}@rki.com")

    # the email and orcid id are links, the latter opening in a new tab
    email_link = page.get_by_test_id("user-email").first
    expect(email_link).to_have_attribute("href", f"mailto:{username}@rki.com")
    orcid_link = page.get_by_test_id("user-orcid-id").first
    expect(orcid_link).to_have_attribute("target", "_blank")
    expect(orcid_link).to_have_attribute("href", re.compile(r"^https://orcid\.org/"))

    # check consent box and buttons are visible
    consent_box = page.get_by_test_id("consent-box")
    expect(consent_box).to_be_visible()

    # the progress bar covers the category lists while they load and goes away once
    # every one of them has reported in
    expect(page.get_by_test_id("user-resource-contact")).to_be_visible()
    expect(page.get_by_test_id("category-loading-progress")).not_to_be_visible()


@pytest.mark.integration
@pytest.mark.usefixtures("load_dummy_data")
def test_submit_consent(consent_page: Page) -> None:
    page = consent_page
    today = datetime.now(tz=ZoneInfo("Europe/Berlin")).strftime("%d.%m.%Y")

    consent_status = page.get_by_test_id("consent-status")
    consent_status.scroll_into_view_if_needed()

    # submit the denial first: once positive consent is valid, retraction is
    # prohibited and the denial button becomes disabled, so it has to be tested
    # before consent is given
    denial_button = page.get_by_test_id("denial-consent-button")
    denial_button.click()
    page.screenshot(path="tests_consent_test_main-test_submit_consent_invalid.png")
    toast = page.locator(".editor-toast").first
    expect(toast).to_be_visible()
    expect(toast).to_have_attribute("data-type", "success")
    expect(consent_status).to_contain_text(f"Sie haben Ihre Ablehnung am {today}")

    # check if given consent is submitted
    page.get_by_test_id("accept-consent-button").click()
    page.screenshot(path="tests_consent_test_main-test_submit_consent_valid.png")
    toast = page.locator(".editor-toast").first
    expect(toast).to_be_visible()
    expect(toast).to_have_attribute("data-type", "success")
    expect(page.get_by_test_id("consent-status")).to_contain_text(
        f"Sie haben Ihre Einwilligung am {today}"
    )

    # check if denial button is disabled after positive consent
    expect(denial_button).to_be_disabled()
