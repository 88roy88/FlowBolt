# Mirrors mocks/flapi-mock/schemas.ts. Contract tests in
# tests/integrations/flapi/test_models_contract.py guard against drift.
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, RootModel
from pydantic.alias_generators import to_pascal

ParamType = Literal["String", "Integer", "Boolean", "Date"]
FieldType = Literal["String", "Integer", "Decimal", "Boolean", "Date"]
OntologyType = Literal["TEXT", "NUMBER", "BOOLEAN", "DATE"]


class PascalCaseBaseModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_pascal,
        populate_by_name=True,
    )


# -- Search: GET /package/v1/search/{query} ------------------------------


class PackageSearchResult(PascalCaseBaseModel):
    # Trailing underscore avoids shadowing the `id`/`type` builtins.
    id_: int = Field(alias="Id")
    name: str
    type_: Literal["Package"] = Field(default="Package", alias="Type")
    purpose: str = ""
    description: str = ""


# -- Quick params info: GET /package/v1/quick/{id} -----------------------


class QuickParamValueOption(PascalCaseBaseModel):
    name: str
    value: str


class QuickParamDefinition(PascalCaseBaseModel):
    name: str
    display_name: str
    description: str | None = None
    type_: ParamType = Field(alias="Type")
    ontology_type: OntologyType
    is_single_value: bool
    is_required: bool
    is_require_any: bool = False
    value: list[QuickParamValueOption]


class QuickParamsInfo(RootModel[dict[str, list[QuickParamDefinition]]]):
    pass


# -- Run: POST /package/v3/{id} ------------------------------------------


class QuickParams(RootModel[dict[str, dict[ParamType, str | int | bool]]]):
    @classmethod
    def from_values(cls, values: dict[str, str | int | bool]) -> "QuickParams":
        wrapped: dict[str, dict[ParamType, str | int | bool]] = {}
        for name, value in values.items():
            # bool must be checked before int since bool is a subclass of int.
            if isinstance(value, bool):
                wrapped[name] = {"Boolean": value}
            elif isinstance(value, int):
                wrapped[name] = {"Integer": value}
            elif isinstance(value, str):
                wrapped[name] = {"String": value}
            else:
                raise TypeError(
                    f"Unsupported FLAPI quick-param value type for {name!r}: {type(value).__name__}"
                )
        return cls(root=wrapped)


class DataSourceRunResult(BaseModel):
    results: dict[str, Any]


# -- Package metadata: GET /package/v3/{id} ------------------------------


class FieldAttributes(PascalCaseBaseModel):
    ontology_type: OntologyType
    original_ontology_type: OntologyType


class QueryField(PascalCaseBaseModel):
    name: str
    display_name: str
    type_: FieldType = Field(alias="Type")
    is_dynamic: bool
    attributes: FieldAttributes
    description: str | None = None


class Query(PascalCaseBaseModel):
    # uniqueName/originalName are camelCase on the wire, not PascalCase.
    unique_name: str = Field(alias="uniqueName")
    original_name: str = Field(alias="originalName")
    name: str
    results_limit: int
    data_source_name: str
    description: str
    id_: str = Field(alias="Id")
    fields: list[QueryField]


class PackageMetadata(PascalCaseBaseModel):
    id_: int = Field(alias="Id")
    name: str
    description: str
    output_queries_id: list[Any]
    queries: list[Query]
