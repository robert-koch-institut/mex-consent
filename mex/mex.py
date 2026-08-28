import reflex as rx
from reflex.components.radix import themes

from mex.consent.api.main import api as consent_api
from mex.consent.consent import index as consent_index
from mex.consent.login.main import index as login_index
from mex.consent.state import ConsentState, State
from mex.consent.utils import load_settings

app = rx.App(
    theme=themes.theme(accent_color="blue", has_background=False),
    style={
        ">a": {"opacity": "0"},
        ".truncate": {
            "overflow": "hidden",
            "text-overflow": "ellipsis",
            "white-space": "nowrap",
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
