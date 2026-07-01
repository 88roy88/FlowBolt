# Mirrors mocks/flapi-mock/schemas.ts. Contract tests in
# tests/integrations/flapi/test_models_contract.py guard against drift.
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, RootModel, field_validator
from pydantic.alias_generators import to_pascal

# Wire vocabulary — authoritative per FLAPI. Quick-params types are
# PascalCase; schema field types are lowercase with a few legacy tags.
ParamType = Literal["String", "Int", "Double", "Boolean", "Datetime", "Timestamp", "Haphoch", "File"] | str
FieldType = (
    Literal[
        "string",
        "datetime",
        "boolean",
        "int",
        "double",
        "float",
        "geojson",
        "wkt",
        "geoellipse",
        "object",
        # Non standard but existant types:
        "bool",
        "date",
        "haphoch",
        "decimal",
        "dynamic",
        "number",
        "html",
        "range",
        "boundingrectangle",
        "spatial",
        "relative",
        "long",
        "time",
        "text",
        "date",
        "pid",
        "",
    ]
    | str
)
# OntologyType = Literal["TEXT", "GEOMETRY", "TOOLID", "PSTN", "IMEI", "IMSI", "TIME"]

type CubeId = str
type QueryDisplayName = str


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
    purpose: str | None = None
    description: str | None = ""


# -- Run: POST /package/v3/{id} ------------------------------------------


class _OptionValueItem(BaseModel):
    Name: str | None
    Value: int | float | str | None = None


class _GeoOptionValueItem(BaseModel):
    Name: str | None
    Type: str
    Value: Any


class _DateRangeValue(BaseModel):
    From: str
    To: str


class _TimebackValue(BaseModel):
    TimeBackValue: int | float
    TimeBackUnit: Literal["second", "minute", "hour", "day", "week", "month", "year"]


class _TimestampRelative(BaseModel):
    Unit: Literal["seconds", "minutes", "hours", "days", "weeks", "months", "years"]
    Value: int
    Direction: Literal["before", "after"]


class _GeographicValueItem(BaseModel):
    value: str | list[str]
    radius: float | None = None


type QuickParamScalar = str | int | float | bool

type _TimestampValue = datetime | Literal["now"] | _TimestampRelative

type QuickParamValue = (
    _OptionValueItem
    | list[_OptionValueItem]
    | _DateRangeValue
    | list[_DateRangeValue]
    | _TimebackValue
    | list[_TimebackValue]
    | _GeographicValueItem
    | list[_GeographicValueItem]
    | _GeoOptionValueItem
    | list[_GeoOptionValueItem]
    | _TimestampValue
    | list[_TimestampValue]
    | QuickParamScalar
    | list[QuickParamScalar]
)


class QuickParams(RootModel[dict[CubeId, dict[str, QuickParamValue]]]):
    pass


class DataSourceRunResult(BaseModel):
    results: dict[QueryDisplayName, Any]


# -- Quick params info: GET /package/v1/quick/{id} -----------------------


class QuickParamDefinition(PascalCaseBaseModel):
    name: str
    display_name: str
    description: str | None = None
    type_: ParamType = Field(alias="Type")
    # ontology_type: OntologyType
    is_single_value: bool
    is_required: bool
    is_require_any: bool = False
    value: QuickParamValue

    @field_validator("type_", mode="before")
    def _normalize_type(cls, v: object) -> object:
        return v.capitalize() if isinstance(v, str) else v


class QuickParamsInfo(RootModel[dict[CubeId, list[QuickParamDefinition]]]):
    pass


# -- Package metadata: GET /package/v3/{id} ------------------------------


# class FieldAttributes(PascalCaseBaseModel):
#     ontology_type: OntologyType | None = None
#     original_ontology_type: OntologyType | None = None
#
#     @field_validator("ontology_type", "original_ontology_type", mode="before")
#     def _normalize_ontology_type(cls, v: object) -> object:
#         return v.upper() if isinstance(v, str) else v


class QueryField(PascalCaseBaseModel):
    name: str
    display_name: str
    type_: FieldType = Field(alias="Type")
    is_dynamic: bool | None = None
    # attributes: FieldAttributes = Field(default_factory=FieldAttributes)
    description: str | None = None

    @field_validator("type_", mode="before")
    def _normalize_type(cls, v: object) -> object:
        return v.lower() if isinstance(v, str) else v


class Query(PascalCaseBaseModel):
    # uniqueName/originalName are camelCase on the wire, not PascalCase.
    unique_name: str = Field(alias="uniqueName")
    original_name: str = Field(alias="originalName")
    name: str
    results_limit: int
    data_source_name: str
    description: str
    id_: str = Field(alias="id")
    fields: list[QueryField]


class PackageMetadata(PascalCaseBaseModel):
    id_: int = Field(alias="Id")
    name: str
    description: str
    # output_queries_id: list[Any]
    queries: list[Query]
