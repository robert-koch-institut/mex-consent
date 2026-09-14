import pytest
from pydantic import HttpUrl

from mex.consent.models import EditorValue, SearchResult
from mex.consent.settings import ConsentSettings
from mex.consent.transform import add_external_links_to_results


def test_add_external_links_to_results() -> None:
    search_results = [
        SearchResult(
            identifier="111111111111111",
            stem_type="Resource",
            title=[EditorValue(text="Title 1", badge="EN", href=None, external=False)],
            preview=[],
        ),
        SearchResult(
            identifier="222222222222222",
            stem_type="Activity",
            title=[EditorValue(text="Title 2", badge="EN", href=None, external=False)],
            preview=[],
        ),
    ]

    results = add_external_links_to_results(search_results)

    assert len(results) == 2
    assert results[0].title[0].href == "https://mex.rki.de/records/mex/111111111111111"
    assert results[0].title[0].external is True
    assert results[1].title[0].href == "https://mex.rki.de/records/mex/222222222222222"
    assert results[1].title[0].external is True


@pytest.mark.parametrize(
    "catalog_url",
    ["https://catalog.example", "https://catalog.example/", "https://host/prefix"],
    ids=["bare-host", "trailing-slash", "path-prefix"],
)
def test_add_external_links_to_results_uses_configured_catalog_url(
    settings: ConsentSettings, catalog_url: str
) -> None:
    settings.consent_catalog_url = HttpUrl(catalog_url)
    search_results = [
        SearchResult(
            identifier="111111111111111",
            stem_type="Resource",
            title=[EditorValue(text="Title 1", badge="EN", href=None, external=False)],
            preview=[],
        ),
    ]

    results = add_external_links_to_results(search_results)

    expected = f"{catalog_url.rstrip('/')}/records/mex/111111111111111"
    assert results[0].title[0].href == expected
    assert results[0].title[0].external is True
