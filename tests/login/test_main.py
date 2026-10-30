import time

import pytest
from playwright.sync_api import Page, WebSocketRoute, expect

from tests.conftest import ldap_credentials


@pytest.mark.integration
def test_login_logout(base_url: str, page: Page) -> None:
    username, password = ldap_credentials()
    page.goto(base_url)

    page.wait_for_url(f"{base_url}/login")
    page.get_by_test_id("input-username").fill(username)
    page.get_by_test_id("input-password").fill(password)
    page.screenshot(path="tests_login_test_main-test_login_logout-on-load.png")

    page.get_by_test_id("login-button").click()
    expect(page.get_by_test_id("nav-bar")).to_be_visible()
    expect(page.get_by_test_id("page-body")).to_be_visible()
    page.screenshot(path="tests_login_test_main-test_login_logout-after-login.png")

    expect(page.get_by_test_id("user-menu")).to_be_visible()
    expect(page.get_by_test_id("logout-button")).to_be_visible()
    page.get_by_test_id("logout-button").click()
    page.wait_for_url(f"{base_url}/login")
    page.screenshot(path="tests_login_test_main-test_login_logout-after-logout.png")
    expect(page.get_by_test_id("login-button")).to_be_visible()
    expect(page.get_by_test_id("nav-bar")).not_to_be_visible()
    expect(page.get_by_test_id("page-body")).not_to_be_visible()


@pytest.mark.integration
def test_login_with_enter_key(base_url: str, page: Page) -> None:
    username, password = ldap_credentials()
    page.goto(base_url)

    page.wait_for_url(f"{base_url}/login")
    page.get_by_test_id("input-username").fill(username)
    password_input = page.get_by_test_id("input-password")
    password_input.fill(password)
    page.screenshot(path="tests_login_test_main-test_login_with_enter_key-on-load.png")

    password_input.press("Enter")
    expect(page.get_by_test_id("nav-bar")).to_be_visible()
    expect(page.get_by_test_id("page-body")).to_be_visible()
    page.screenshot(
        path="tests_login_test_main-test_login_with_enter_key-after-login.png"
    )


@pytest.mark.integration
def test_redirect_to_login_does_not_flash_page(base_url: str, page: Page) -> None:
    # record whether the page body ever mounts, which a plain visibility check after
    # the redirect would miss, because it is gone again by the time playwright looks
    page.add_init_script(
        """
        new MutationObserver((_, observer) => {
            if (document.querySelector('[data-testid="page-body"]')) {
                window.pageBodyMounted = true;
                observer.disconnect();
            }
        }).observe(document, {childList: true, subtree: true});
        """
    )

    # on localhost the redirect outruns the first paint, so the flash only shows up
    # once the websocket is as slow as it is behind the proxies on stage
    def delay_websocket(ws: WebSocketRoute) -> None:
        server = ws.connect_to_server()

        def forward_late(message: str | bytes) -> None:
            time.sleep(1)
            server.send(message)

        ws.on_message(forward_late)
        server.on_message(ws.send)

    page.route_web_socket("**/*", delay_websocket)
    page.goto(base_url)

    page.wait_for_url(f"{base_url}/login")
    expect(page.get_by_test_id("login-button")).to_be_visible()
    assert page.evaluate("window.pageBodyMounted === undefined")
