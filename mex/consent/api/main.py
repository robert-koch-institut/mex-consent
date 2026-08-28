from importlib.metadata import version

from fastapi import FastAPI
from fastapi.responses import PlainTextResponse

from mex.common.connector import CONNECTOR_STORE
from mex.common.models import VersionStatus

api = FastAPI(
    title="mex-consent",
    version="v0",
    contact={"name": "MEx Team", "email": "mex@rki.de"},
    description="GDPR consent micro-site for employees.",
)


@api.get("/_system/check", tags=["system"])
def check_system_status() -> VersionStatus:
    """Check that the consent server is healthy and responsive."""
    return VersionStatus(status="ok", version=version("mex-consent"))


@api.get("/_system/metrics", response_class=PlainTextResponse, tags=["system"])
def get_prometheus_metrics() -> str:
    """Get connector metrics for prometheus."""
    return "\n\n".join(
        f"# TYPE {key} counter\n{key} {value}"
        for key, value in CONNECTOR_STORE.metrics().items()
    )
