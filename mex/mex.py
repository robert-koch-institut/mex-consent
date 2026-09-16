import reflex as rx
from reflex.components.radix import themes

from mex.consent.api.main import api as consent_api
from mex.consent.categories import validate_category_pairs
from mex.consent.consent import index as consent_index
from mex.consent.login.main import index as login_index
from mex.consent.state import ConsentState, State
from mex.consent.utils import load_settings

app = rx.App(
    theme=themes.theme(
        accent_color="blue",
        has_background=False,
        appearance="light",
    ),
    style={
        ">a": {"opacity": "0"},
        ".truncate": {
            "overflow": "hidden",
            "text-overflow": "ellipsis",
            "white-space": "nowrap",
        },
        # the consent page's loading bar pulses its empty track while it waits for the
        # first category to report in, see `loading_progress`
        "@keyframes mex-progress-pulse": {
            "0%, 100%": {"opacity": "1"},
            "50%": {"opacity": "0.4"},
        },
    },
    api_transformer=consent_api,
)
app.add_page(
    consent_index,
    route="/",
    title="MEx Consent",
    on_load=[
        State.check_ldap_login,
        ConsentState.get_consent,
        ConsentState.reveal_categories_after_timeout,
    ],
)
app.add_page(
    login_index,
    route="/login",
    title="MEx Consent | Login",
)
app.register_lifespan_task(
    load_settings,
)
app.register_lifespan_task(
    validate_category_pairs,
)
