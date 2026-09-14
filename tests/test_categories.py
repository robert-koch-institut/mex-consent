import pytest

from mex.common.exceptions import MExError
from mex.consent.categories import (
    CATEGORY_PAIRS,
    EXCLUDED_STEM_TYPES,
    CategoryPair,
    derive_category_pairs,
    validate_category_pairs,
)
from mex.consent.models import MODEL_CONFIG_BY_STEM_TYPE


def test_derive_category_pairs_finds_every_person_reference() -> None:
    assert derive_category_pairs() == [
        CategoryPair("Activity", "contact"),
        CategoryPair("Activity", "externalAssociate"),
        CategoryPair("Activity", "involvedPerson"),
        CategoryPair("BibliographicResource", "creator"),
        CategoryPair("BibliographicResource", "editor"),
        CategoryPair("BibliographicResource", "editorOfSeries"),
        CategoryPair("Resource", "contact"),
        CategoryPair("Resource", "contributor"),
        CategoryPair("Resource", "creator"),
        CategoryPair("ResourceSeries", "contact"),
    ]


def test_derive_category_pairs_skips_excluded_stem_types() -> None:
    stem_types = {pair.stem_type for pair in derive_category_pairs()}
    assert not stem_types & EXCLUDED_STEM_TYPES


def test_derive_category_pairs_skips_own_identifier() -> None:
    # `MergedPerson.identifier` is typed like a person reference but is the
    # primary key, and `Person` is excluded outright, so neither may show up
    assert not [pair for pair in derive_category_pairs() if pair.field == "identifier"]


def test_derive_category_pairs_is_sorted() -> None:
    # the order decides the names reflex gives the generated component states,
    # so it has to stay stable between runs
    pairs = derive_category_pairs()
    assert pairs == sorted(pairs)


@pytest.mark.parametrize(
    ("pair", "entity_type", "key", "test_id"),
    [
        (
            CategoryPair("Resource", "contact"),
            "MergedResource",
            "Resource.contact",
            "user-resource-contact",
        ),
        (
            CategoryPair("BibliographicResource", "editorOfSeries"),
            "MergedBibliographicResource",
            "BibliographicResource.editorOfSeries",
            "user-bibliographicresource-editorofseries",
        ),
    ],
    ids=["resource-contact", "bibliographic-resource-editor-of-series"],
)
def test_category_pair_properties(
    pair: CategoryPair, entity_type: str, key: str, test_id: str
) -> None:
    assert pair.entity_type == entity_type
    assert pair.key == key
    assert pair.test_id == test_id


def test_validate_category_pairs_passes_for_derived_pairs() -> None:
    validate_category_pairs()


def test_validate_category_pairs_raises_on_missing_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    incomplete = {
        stem_type: config
        for stem_type, config in MODEL_CONFIG_BY_STEM_TYPE.items()
        if stem_type != "ResourceSeries"
    }
    monkeypatch.setattr("mex.consent.categories.MODEL_CONFIG_BY_STEM_TYPE", incomplete)
    with pytest.raises(MExError, match="ResourceSeries"):
        validate_category_pairs()


def test_category_pairs_are_derived_at_import() -> None:
    assert derive_category_pairs() == CATEGORY_PAIRS
