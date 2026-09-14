from dataclasses import dataclass
from typing import Final

from mex.common.exceptions import MExError
from mex.common.models import MERGED_MODEL_CLASSES
from mex.consent.models import MODEL_CONFIG_BY_STEM_TYPE

# the annotation marker that identifies a field as pointing at a merged person
PERSON_IDENTIFIER_TYPE: Final = "MergedPersonIdentifier"

# stem types whose person references are not content the user should review here:
# their own consent records are already summarized by the consent box, person to
# person links are identity plumbing, and access platforms and primary sources
# describe infrastructure rather than something a person is mentioned in
EXCLUDED_STEM_TYPES: Final[frozenset[str]] = frozenset(
    {
        "AccessPlatform",
        "Consent",
        "Person",
        "PrimarySource",
    }
)

# a model's own identifier is typed like a person reference on `MergedPerson`,
# but it is the primary key, not a reference to somebody else
EXCLUDED_FIELDS: Final[frozenset[str]] = frozenset({"identifier"})


@dataclass(frozen=True, order=True)
class CategoryPair:
    """One list on the consent page: an entity type and the field referencing you."""

    stem_type: str
    field: str

    @property
    def entity_type(self) -> str:
        """Return the merged entity type to query the backend for."""
        return f"Merged{self.stem_type}"

    @property
    def key(self) -> str:
        """Return a stable key to report this pair's item count under."""
        return f"{self.stem_type}.{self.field}"

    @property
    def test_id(self) -> str:
        """Return the `data-testid` the rendered list carries."""
        return f"user-{self.stem_type.lower()}-{self.field.lower()}"


def derive_category_pairs() -> list[CategoryPair]:
    """Find every merged model field that can reference a person.

    Deriving these instead of listing them by hand means a new referencing field in
    `mex-model` shows up on the consent page without a code change here. Sorting the
    result keeps the order stable, which matters because `rx.ComponentState.create`
    names the states it generates after the order they are created in.

    Returns:
        The person-referencing (stem type, field) pairs, minus the excluded ones
    """
    pairs = [
        CategoryPair(stem_type, field_name)
        for model in MERGED_MODEL_CLASSES
        if (stem_type := model.__name__.removeprefix("Merged"))
        not in EXCLUDED_STEM_TYPES
        for field_name, field in model.model_fields.items()
        if field_name not in EXCLUDED_FIELDS
        and PERSON_IDENTIFIER_TYPE in str(field.annotation)
    ]
    return sorted(pairs)


CATEGORY_PAIRS: Final = derive_category_pairs()


def validate_category_pairs() -> None:
    """Check that every derived pair can actually be rendered.

    `transform_models_to_title` looks each stem type up in `models.yaml`, so a pair
    without an entry there would only fail once a user happens to be referenced by
    one. Failing at startup instead turns a new `mex-model` entity type into an
    obvious deployment error rather than a sporadic one.

    Raises:
        MExError: If a derived stem type has no entry in `models.yaml`
    """
    missing = sorted(
        {pair.stem_type for pair in CATEGORY_PAIRS} - set(MODEL_CONFIG_BY_STEM_TYPE)
    )
    if missing:
        msg = (
            f"Missing models.yaml entries for stem types: {', '.join(missing)}. "
            "Add a title and preview config for them, or exclude them in "
            "`EXCLUDED_STEM_TYPES`."
        )
        raise MExError(msg)
