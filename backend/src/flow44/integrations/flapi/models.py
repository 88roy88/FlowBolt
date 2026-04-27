# Mirrors mocks/flapi-mock/schemas.ts. Contract tests in
# tests/integrations/flapi/test_models_contract.py guard against drift.
from typing import Any, Literal, TypeAlias

from pydantic import BaseModel, ConfigDict, Field, RootModel, field_validator
from pydantic.alias_generators import to_pascal

# Wire vocabulary — authoritative per FLAPI. Quick-params types are
# PascalCase; schema field types are lowercase with a few legacy tags.
ParamType = Literal["String", "Int", "Double", "Boolean", "DateTime"]   # "Haphoch"
FieldType = Literal["string", "int", "double", "bool", "datetime", "Haphoch", "wkt",
    "float", "geojson", "GeoEllipse", "Object", "Int", "String", "Integer", "Decimal", "Boolean"]
OntologyType = Literal["TEXT", "GEOMETRY", "TOOLID", "PSTN", "IMEI", "IMSI", "TIME", "CELL", "OCR"]


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


# -- Quick params info: GET /package/v1/quick/{id} -----------------------


class QuickParamValueOption(PascalCaseBaseModel):
    name: str
    value: str


class QuickParamDefinition(PascalCaseBaseModel):
    name: str
    display_name: str
    description: str | None = None
    type_: ParamType = Field(alias="Type")
    ontology_type: OntologyType | str | None = None
    is_single_value: bool
    is_required: bool
    is_require_any: bool = False
    value: list[QuickParamValueOption]

    @field_validator("type_", mode="before")
    def _normalize_type(cls, v: object) -> object:
        return v.capitalize() if isinstance(v, str) else v

    @field_validator("ontology_type", mode="before")
    def _normalize_ontology_type(cls, v: object) -> object:
        return v.upper() if isinstance(v, str) else v


class QuickParamsInfo(RootModel[dict[str, list[QuickParamDefinition]]]):
    pass


# -- Run: POST /package/v3/{id} ------------------------------------------


QuickParamsScalar: TypeAlias = str | int | float | bool
QuickParamsValue: TypeAlias = QuickParamsScalar | list[QuickParamsScalar]


class QuickParams(RootModel[dict[str, dict[str, list[dict[str, Any]]]]]):
    @classmethod
    def from_values(cls, values: dict[str, QuickParamsValue], *, info: QuickParamsInfo | None = None) -> "QuickParams":
        param_to_group: dict[str, str] = {}
        if info:
            for group_key, defs in info.root.items():
                for d in defs:
                    param_to_group[d.name] = group_key
        print("param_to_group:", param_to_group)
        wrapped: dict[str, dict[str, list[dict[str, Any]]]] = {}
        print("values:", values.items())
        for name, value in values.items():
            group_key = param_to_group.get(name, "default")
            if group_key not in wrapped:
                wrapped[group_key] = {}
            scalar_values = value if isinstance(value, list) else [value]
            wrapped[group_key][name] = [{"Value": v, "Name": v} for v in scalar_values]
        return cls(root=wrapped)


class DataSourceRunResult(BaseModel):
    results: dict[str, Any]


# -- Package metadata: GET /package/v3/{id} ------------------------------


class FieldAttributes(PascalCaseBaseModel):
    ontology_type: OntologyType | None = None
    original_ontology_type: OntologyType | None = None

    @field_validator("ontology_type", "original_ontology_type", mode="before")
    @classmethod
    def normalize_case(cls, v: str | None) -> str | None:
        """Normalize ontology type to uppercase to handle case variations."""
        if isinstance(v, str):
            return v.upper()
        return v


class QueryField(PascalCaseBaseModel):
    name: str
    display_name: str
    type_: FieldType = Field(alias="Type")
    is_dynamic: bool | None = None
    attributes: FieldAttributes = Field(default_factory=FieldAttributes)
    description: str | None = None

    @field_validator("type_", mode="before")
    @classmethod
    def normalize_field_type(cls, v: str) -> str:
        """Normalize field type to handle case variations and type name aliases."""
        type_mapping = {
            "int": "Integer",
            "number": "Integer",
            "num": "Integer",
            "str": "String",
            "text": "String",
            "double": "double",
            "decimal": "Decimal",
            "bool": "Boolean",
            "boolean": "Boolean",
            "datetime": "datetime",
            "time": "datetime",
            "geometry": "wkt",
            "geojson": "geojson",
            "geoellipse": "GeoEllipse",
            "object": "Object",
        }
        if isinstance(v, str):
            normalized = v.lower()
            return type_mapping.get(normalized, v)
        return v


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
