from typing import Final

from pydantic import Field

from mex.common.settings import BaseSettings

# placeholder consent texts, meant to be overridden per deployment
DEFAULT_CONSENT_TEXT_DE: Final = """\
Lorem ipsum amet consectetur in cupidatat laborum velit reprehenderit. Commodo culpa
in id eiusmod sit nisi ad reprehenderit commodo veniam occaecat. Eu occaecat ut non
anim in duis ea consequat. Qui magna nisi ipsum cupidatat officia excepteur
adipisicing. Sint irure voluptate sit est excepteur id dolor nostrud officia.

Sunt dolor sunt qui est amet eu do elit duis nisi. Est sit deserunt ad culpa ea enim
pariatur duis cillum cillum cillum ut commodo. Quis commodo aute non Lorem ut
consequat duis pariatur eu eiusmod duis. Anim consectetur incididunt sunt duis commodo
fugiat enim [Lorem Ipsum](https://example.org/lorem-ipsum) ut ullamco excepteur.
Pariatur est sint elit sit ut occaecat exercitation ex duis occaecat sunt officia
cillum. Sunt aute aliqua aliqua ullamco. Qui est eiusmod in incididunt tempor pariatur
magn officia in minim: [mex@rki.de](mailto:mex@rki.de).

**Ipsum:** Est consectetur cupidatat reprehenderit ullamco elit sit adipisicing
aliqua.
"""
DEFAULT_CONSENT_TEXT_EN: Final = """\
ENGLISH: Lorem ipsum amet consectetur in cupidatat laborum velit reprehenderit.
Commodo culpa in id eiusmod sit nisi ad reprehenderit commodo veniam occaecat. Eu
occaecat ut non anim in duis ea consequat. Qui magna nisi ipsum cupidatat officia
excepteur adipisicing. Sint irure voluptate sit est excepteur id dolor nostrud
officia.

ENGLISH: Sunt dolor sunt qui est amet eu do elit duis nisi. Est sit deserunt ad culpa
ea enim pariatur duis cillum cillum cillum ut commodo. Quis commodo aute non Lorem ut
consequat duis pariatur eu eiusmod duis. Anim consectetur incididunt sunt duis commodo
fugiat enim [Lorem Ipsum](https://example.org/lorem-ipsum) ut ullamco excepteur.
Pariatur est sint elit sit ut occaecat exercitation ex duis occaecat sunt officia
cillum. Sunt aute aliqua aliqua ullamco. Qui est eiusmod in incididunt tempor pariatur
magn officia in minim: [mex@rki.de](mailto:mex@rki.de).

**ENGLISH Ipsum:** Est consectetur cupidatat reprehenderit ullamco elit sit
adipisicing aliqua.
"""


class ConsentSettings(BaseSettings):
    """Settings definition for the consent service."""

    consent_api_host: str = Field(
        "localhost",
        min_length=1,
        max_length=250,
        description="Host that the consent api will run on.",
        validation_alias="MEX_CONSENT_API_HOST",
    )
    consent_api_port: int = Field(
        8041,
        gt=0,
        lt=65536,
        description="Port that the consent api should listen on.",
        validation_alias="MEX_CONSENT_API_PORT",
    )
    consent_frontend_port: int = Field(
        8040,
        gt=0,
        lt=65536,
        description="Port that the consent frontend should serve on.",
        validation_alias="MEX_CONSENT_FRONTEND_PORT",
    )
    consent_api_root_path: str = Field(
        "",
        description="Root path that the consent server should run under.",
        validation_alias="MEX_CONSENT_API_ROOT_PATH",
    )
    consent_text_de: str = Field(
        DEFAULT_CONSENT_TEXT_DE,
        min_length=1,
        description="Markdown of the german consent text shown on the consent page.",
        validation_alias="MEX_CONSENT_TEXT_DE",
    )
    consent_text_en: str = Field(
        DEFAULT_CONSENT_TEXT_EN,
        min_length=1,
        description="Markdown of the english consent text shown on the consent page.",
        validation_alias="MEX_CONSENT_TEXT_EN",
    )

    def get_consent_text(self, locale_id: str) -> str:
        """Get the consent text markdown for the given locale.

        Args:
            locale_id: The locale to get the consent text for

        Returns:
            The consent text of the given locale, defaulting to the german one
        """
        return {
            "de": self.consent_text_de,
            "en": self.consent_text_en,
        }.get(locale_id, self.consent_text_de)
