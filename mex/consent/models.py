from importlib.resources import files

import yaml
from pydantic import BaseModel, TypeAdapter

from mex.common.types import MergedPersonIdentifier


class EditorValue(BaseModel):
    """Model for describing atomic values in the editor."""

    text: str | None = None
    identifier: str | None = None
    badge: str | None = None
    href: str | None = None
    external: bool = False


class User(BaseModel):
    """Info on the currently logged-in user."""

    name: str
    write_access: bool


class MergedLoginPerson(BaseModel):
    """Info on the currently logged-in user from the merged login endpoint."""

    identifier: MergedPersonIdentifier | None = None
    full_name: list[str] | None = None
    email: list[str] | None = None
    orcid_id: list[str] | None = None


class ModelConfig(BaseModel):
    """Configuration for how to display an entity type in the frontend."""

    title: str
    preview: list[str] = []


MODEL_CONFIG_BY_STEM_TYPE = TypeAdapter(dict[str, ModelConfig]).validate_python(
    yaml.safe_load(files("mex.consent").joinpath("models.yaml").open())
)
LANGUAGE_VALUE_NONE = "None"


class SearchResult(BaseModel):
    """Search result preview."""

    identifier: str
    stem_type: str
    title: list[EditorValue]
    preview: list[EditorValue]
