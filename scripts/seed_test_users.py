"""Seed the backend with artificial data and matching LDAP test users.

Run this against a backend with write access, e.g. the one from `compose.yaml`:

    MEX_BACKEND_API_KEY=write_key uv run python scripts/seed_test_users.py

Because `mex-artificial` draws all of its values from a fixed seed, the items are
deterministic: the same seed always yields the same persons, hence the same LDAP
accounts. Only the identifiers vary, because the backend assigns those, and it keeps
assigning the same ones as long as it is not flushed, which makes re-runs idempotent.

The first couple of artificial persons are anchored on their LDAP account name, so that
logging into the consent service as one of them resolves to the very person that the
artificial activities and resources reference. The same persons are rendered into
`assets/raw-data/ldap/data.ldif.TEMPLATE`, which seeds the LDAP mock, so run this
script whenever the seed or the item count below changes to keep both sides in sync.
"""

import unicodedata
from dataclasses import dataclass
from hashlib import blake2b
from pathlib import Path
from typing import Any, Final
from uuid import UUID

from mex.artificial.helpers import create_artificial_extracted_items
from mex.common.backend_api.connector import BackendApiConnector
from mex.common.cli import entrypoint
from mex.common.logging import logger
from mex.common.models import AnyExtractedModel, ExtractedPerson
from mex.common.types import Identifier, IdentityProvider
from mex.consent.settings import ConsentSettings

# keep the seed and count stable, otherwise the ldif template needs regenerating
SEED: Final = 0
COUNT: Final = 100

LDIF_PATH: Final = (
    Path(__file__).parent.parent / "assets" / "raw-data" / "ldap" / "data.ldif.TEMPLATE"
)
LDAP_BASE_DN: Final = "dc=ldapmock,dc=local"
LDAP_DOMAIN: Final = "ldapmock.local"
LDAP_DEPARTMENT: Final = "FG99"
LDAP_USER_COUNT: Final = 3
# the groups mirror the access levels of the mock: test users take turns, so that
# every other one of them ends up with write instead of just read access
LDAP_WRITE_ACCESS_GROUP: Final = "Abteilung_21"
LDAP_READ_ACCESS_GROUP: Final = "Fachgebiet_99"

# faker produces german words, which ldap account names cannot carry verbatim
UMLAUT_TRANSLATION: Final = str.maketrans(
    {
        "Ä": "Ae",
        "Ö": "Oe",
        "Ü": "Ue",
        "ß": "ss",
        "ä": "ae",
        "ö": "oe",
        "ü": "ue",
    }
)


@dataclass(frozen=True)
class LDAPTestUser:
    """An LDAP account that was derived from an artificial person."""

    uid: str
    given_name: str
    surname: str
    employee_id: str
    object_guid: UUID

    @property
    def display_name(self) -> str:
        """Return the full name of this account."""
        return f"{self.given_name} {self.surname}"

    @property
    def mail(self) -> str:
        """Return the mock email address of this account."""
        return f"{self.uid}@{LDAP_DOMAIN}"

    @property
    def password(self) -> str:
        """Return the cleartext password of this account."""
        return f"{self.uid}_password"

    @property
    def dn(self) -> str:
        """Return the distinguished name of this account."""
        return f"uid={self.uid},{LDAP_BASE_DN}"


def _ascii_words(values: list[str]) -> list[str]:
    """Split the given values into capitalized, ascii-only single words."""
    words = []
    for value in values:
        for word in value.translate(UMLAUT_TRANSLATION).split():
            ascii_word = "".join(
                character
                for character in unicodedata.normalize("NFKD", word)
                if character.isascii() and character.isalnum()
            )
            if ascii_word:
                words.append(ascii_word.capitalize())
    return words


def _split_name(person: ExtractedPerson) -> tuple[str, str]:
    """Reduce the name lists of an artificial person to one given name and surname."""
    fallback = _ascii_words([person.identifierInPrimarySource])
    given_names = (
        _ascii_words(person.givenName)
        or _ascii_words(person.fullName)
        or _ascii_words(person.familyName)
        or fallback
    )
    surnames = (
        _ascii_words(person.familyName)
        or _ascii_words(person.fullName)
        or _ascii_words(person.givenName)
        or fallback
    )
    return given_names[0], surnames[-1]


def _object_guid(uid: str) -> UUID:
    """Derive a stable object guid from an LDAP account name."""
    return UUID(bytes=blake2b(uid.encode(), digest_size=16).digest(), version=4)


def _to_ldap_test_users(persons: list[ExtractedPerson]) -> list[LDAPTestUser]:
    """Derive one LDAP account per given artificial person."""
    users: list[LDAPTestUser] = []
    taken_uids: set[str] = set()
    for person in persons:
        given_name, surname = _split_name(person)
        uid = f"{given_name}{surname[0]}"
        while uid in taken_uids:
            uid = f"{uid}X"
        taken_uids.add(uid)
        users.append(
            LDAPTestUser(
                uid=uid,
                given_name=given_name,
                surname=surname,
                employee_id=person.identifierInPrimarySource,
                object_guid=_object_guid(uid),
            )
        )
    return users


def _anchor_person_on_account(
    person: ExtractedPerson, user: LDAPTestUser
) -> ExtractedPerson:
    """Rewrite an artificial person to match the LDAP account derived from it.

    Anchoring the person on its LDAP account name makes the backend assign the same
    identifiers to the person that it assigns when that account logs in.
    """
    return person.model_copy(
        update={
            "identifierInPrimarySource": user.uid,
            "email": [user.mail],
            "familyName": [user.surname],
            "fullName": [user.display_name],
            "givenName": [user.given_name],
        }
    )


def _replace_references(
    item: AnyExtractedModel,
    replacements: dict[Identifier, Identifier],
) -> AnyExtractedModel:
    """Point all references of the given item at the replacement identifiers."""
    update: dict[str, Any] = {}
    for field in type(item).model_fields:
        value = getattr(item, field)
        if isinstance(value, list):
            replaced = [
                replacements.get(entry, entry)
                if isinstance(entry, Identifier)
                else entry
                for entry in value
            ]
            if replaced != value:
                update[field] = replaced
        elif isinstance(value, Identifier) and value in replacements:
            update[field] = replacements[value]
    return item.model_copy(update=update) if update else item


def _render_ldif(users: list[LDAPTestUser]) -> str:
    """Render the LDAP test users and their group memberships as an ldif document."""
    blocks = [
        "\n".join(
            [
                f"# {user.display_name}",
                f"dn: {user.dn}",
                "objectClass: top",
                "objectClass: person",
                "objectClass: inetOrgPerson",
                "objectClass: customPerson",
                "objectCategory: Person",
                f"cn: {user.display_name}",
                f"displayName: {user.display_name}",
                f"sn: {user.surname}",
                f"givenName: {user.given_name}",
                f"employeeID: {user.employee_id}",
                f"sAMAccountName: {user.uid}",
                f"objectGUID: {user.object_guid}",
                f"department: {LDAP_DEPARTMENT}",
                f"mail: {user.mail}",
                f"uid: {user.uid}",
                f"userPassword: {user.password}",
            ]
        )
        for user in users
    ]
    for group, remainder, access in (
        (LDAP_WRITE_ACCESS_GROUP, 0, "write"),
        (LDAP_READ_ACCESS_GROUP, 1, "read"),
    ):
        members = [user for index, user in enumerate(users) if index % 2 == remainder]
        member_uids = ", ".join(member.uid for member in members)
        blocks.append(
            "\n".join(
                [
                    f"# {group} group ({access} access: {member_uids})",
                    f"dn: cn={group},{LDAP_BASE_DN}",
                    "objectClass: top",
                    "objectClass: groupOfNames",
                    f"cn: {group}",
                    *(f"member: {member.dn}" for member in members),
                ]
            )
        )
    return "\n\n".join(blocks) + "\n"


@entrypoint()
def seed_test_users() -> None:
    """Ingest artificial items and refresh the LDAP test user template."""
    settings = ConsentSettings.get()
    # only the backend may assign identifiers, it rejects items that bring their own
    settings.identity_provider = IdentityProvider.BACKEND

    items = create_artificial_extracted_items(seed=SEED, count=COUNT)
    persons = [item for item in items if isinstance(item, ExtractedPerson)]
    test_persons = persons[:LDAP_USER_COUNT]
    users = _to_ldap_test_users(test_persons)

    anchored = [
        _anchor_person_on_account(person, user)
        for person, user in zip(test_persons, users, strict=True)
    ]
    anchored_by_original_id = {
        person.identifierInPrimarySource: anchor
        for person, anchor in zip(test_persons, anchored, strict=True)
    }
    replacements: dict[Identifier, Identifier] = {
        person.stableTargetId: anchor.stableTargetId
        for person, anchor in zip(test_persons, anchored, strict=True)
    }
    seeded = [
        anchored_by_original_id.get(item.identifierInPrimarySource)
        or _replace_references(item, replacements)
        for item in items
    ]

    LDIF_PATH.write_text(_render_ldif(users), encoding="utf-8")
    logger.info("wrote %s ldap test users to %s", len(users), LDIF_PATH)

    connector = BackendApiConnector.get()
    connector.ingest(seeded)
    logger.info("ingested %s artificial items", len(seeded))


if __name__ == "__main__":
    seed_test_users()
