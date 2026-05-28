from typing import Any, Literal, TypeAlias, assert_never

from pydantic import BaseModel, Field, RootModel, computed_field

# Domain-side vocabulary. The FLAPI adapter translates into these;
# the rest of the app is agnostic to FLAPI's wire spellings.
ParamType = Literal["string", "int", "double", "bool", "datetime", "timestamp", "geographic"]
FieldType = Literal["string", "int", "double", "bool", "datetime", "wkt"]

ParamScalar: TypeAlias = str | int | float | bool
ParamValue: TypeAlias = ParamScalar | list[ParamScalar]


class DataSource(BaseModel):
    id: int
    name: str
    description: str | None = None


class ParamOption(BaseModel):
    name: str
    value: str


class ParamDefinition(BaseModel):
    name: str
    display_name: str
    description: str | None = None
    type: ParamType
    is_required: bool
    is_single_value: bool
    is_require_any: bool = False
    options: list[ParamOption] = Field(default_factory=list)
    cube_id: str = ""
    query_id: str = ""

    @computed_field
    def default_values(self) -> ParamScalar | list[ParamScalar] | None:
        if not self.options:
            return None
        if self.is_single_value:
            return parse_param_value(self.options[0].value, self.type)
        return [parse_param_value(opt.value, self.type) for opt in self.options]


def parse_param_value(value: str, param_type: ParamType) -> ParamScalar:
    # Option values arrive as strings; the caller needs them typed.
    match param_type:
        case "string" | "datetime" | "timestamp" | "geographic":
            return value
        case "int":
            try:
                return int(value)
            except ValueError as exc:
                raise ValueError(f"Cannot parse {value!r} as int") from exc
        case "double":
            try:
                return float(value)
            except ValueError as exc:
                raise ValueError(f"Cannot parse {value!r} as double") from exc
        case "bool":
            return value.strip().lower() in ("true", "1", "yes")
        case _:
            assert_never(param_type)


class DataSourceParamsInfo(BaseModel):
    parameters: list[ParamDefinition]
    # True when one or more parameters are part of a "provide at least one" group.
    require_any: bool = False


class DataSourceParams(RootModel[dict[str, ParamValue]]):
    pass


class DataSourceResult(BaseModel):
    data: dict[str, Any]


class DataSourceFieldSchema(BaseModel):
    name: str
    display_name: str
    type: FieldType
    description: str | None = None


class DataSourceQuerySchema(BaseModel):
    name: str
    display_name: str
    description: str
    fields: list[DataSourceFieldSchema]


class CanRunResponse(BaseModel):
    can_run: bool


class DataSourceUsage(BaseModel):
    queries: list[DataSourceQuerySchema]
    params: DataSourceParamsInfo
    can_run: bool = False
    sample: dict[str, Any] | None = None
