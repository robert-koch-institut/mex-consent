import os
import sys
from pathlib import Path

import uvicorn
from reflex.config import environment, get_config, reload_config
from reflex.constants import Env, LogLevel
from reflex.istate.manager import reset_disk_state_manager
from reflex.reflex import run
from reflex.utils.console import set_log_level
from reflex.utils.exec import get_app_instance

from mex.consent.frontend import create_frontend_app, get_build_directory
from mex.consent.logging import UVICORN_LOGGING_CONFIG
from mex.consent.settings import ConsentSettings


def consent_api() -> None:  # pragma: no cover
    """Start the consent api."""
    settings = ConsentSettings.get()

    # Set the log level.
    set_log_level(LogLevel.INFO)

    # Set environment variables.
    environment.REFLEX_ENV_MODE.set(Env.PROD)
    environment.REFLEX_SKIP_COMPILE.set(True)
    environment.REFLEX_USE_GRANIAN.set(False)
    environment.REFLEX_SSR.set(False)

    # Delete the states folder if it exists.
    reset_disk_state_manager()  # type: ignore[no-untyped-call]

    # Reload the config to make sure the env vars are persistent.
    reload_config()

    # Run the api.
    uvicorn.run(
        get_app_instance(),  # type: ignore[no-untyped-call]
        host=settings.consent_api_host,
        port=settings.consent_api_port,
        root_path=settings.consent_api_root_path,
        log_config=UVICORN_LOGGING_CONFIG,
        headers=[("server", "mex-consent")],
    )


def consent_frontend() -> None:  # pragma: no cover
    """Serve the pre-built consent frontend."""
    settings = ConsentSettings.get()
    config = get_config()

    # Pick the build matching the frontend path.
    build_directory = get_build_directory(
        settings.consent_frontend_directory, config.frontend_path
    )

    # Serve the frontend.
    uvicorn.run(
        create_frontend_app(build_directory, config.frontend_path, config.api_url),
        host=settings.consent_frontend_host,
        port=settings.consent_frontend_port,
        log_config=UVICORN_LOGGING_CONFIG,
        headers=[("server", "mex-consent")],
    )


def main() -> None:  # pragma: no cover
    """Start the consent api together with frontend."""
    # Set environment variables.
    environment.REFLEX_USE_GRANIAN.set(False)
    environment.REFLEX_SSR.set(False)
    if (tests := Path("tests")).exists():
        environment.REFLEX_HOT_RELOAD_EXCLUDE_PATHS.set([tests])

    if "win32" in sys.platform:
        # bun cache is not working correctly on windows
        # https://github.com/oven-sh/bun/issues/20886
        os.environ["BUN_OPTIONS"] = "--no-cache"

    # Run consent service.
    run.main()
