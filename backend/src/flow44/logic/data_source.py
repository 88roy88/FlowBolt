import logging

from pydantic import ValidationError

from flow44.integrations.flapi import (
    FlapiUpstreamError,
    QuickParams,
    data_source_client,
)
from flow44.integrations.flapi import models as flapi_models
from flow44.logic.models import (
    DataSource,
    DataSourceFieldSchema,
    DataSourceParamsInfo,
    DataSourceQuerySchema,
    DataSourceResult,
    DataSourceUsage,
    FieldType,
    ParamDefinition,
    ParamOption,
    ParamType,
    ParamValue,
    parse_param_value,
)

logger = logging.getLogger(__name__)

__all__ = [
    "DataSource",
    "DataSourceParamsInfo",
    "DataSourceResult",
    "DataSourceUsage",
    "FlapiUpstreamError",
    "can_run_without_params",
    "fetch_data_source",
    "get_display_name",
    "get_params_info",
    "get_usage",
    "run_data_source",
    "search_data_sources",
]


# -- FLAPI -> domain conversions -----------------------------------------

# FLAPI speaks its own vocabulary (PascalCase quick-param types, a wider
# lowercase-plus-legacy field-type set). The rest of the app doesn't care —
# these two mappers are the single seam that translates into the narrow
# domain Literals. Keep them exhaustive; unmapped values fall back to
# "string" so the UI still renders, but should be reported and added.
_FLAPI_PARAM_TYPE: dict[flapi_models.ParamType, ParamType] = {
    "String": "string",
    "Int": "int",
    "Double": "double",
    "Boolean": "bool",
    "DateTime": "datetime",
    "Timestamp": "timestamp",
}

_FLAPI_FIELD_TYPE: dict[str, FieldType] = {
    "string": "string",
    "int": "int",
    "double": "double",
    "bool": "bool",
    "datetime": "datetime",
    "wkt": "wkt",
    # "Haphoch" isn't a meaningful type for us — render as plain string.
    "Haphoch": "string",
}


def _to_domain_field_type(t: str) -> FieldType:
    mapped = _FLAPI_FIELD_TYPE.get(t)
    if mapped is None:
        logger.warning("Unmapped FLAPI field type %r — falling back to 'string'", t)
        return "string"
    return mapped


def _to_data_source(result: flapi_models.PackageSearchResult) -> DataSource:
    return DataSource(
        id=result.id_,
        name=result.name,
        description=result.description or None,
    )


def _to_params_info(info: flapi_models.QuickParamsInfo) -> DataSourceParamsInfo:
    parameters: list[ParamDefinition] = []
    require_any = False

    for cube_id, param_list in info.root.items():
        for p in param_list:
            options = [ParamOption(name=opt.name, value=opt.value) for opt in p.value]
            parameters.append(
                ParamDefinition(
                    name=p.name,
                    display_name=p.display_name,
                    description=p.description,
                    type=_FLAPI_PARAM_TYPE[p.type_],
                    is_required=p.is_required,
                    is_single_value=p.is_single_value,
                    is_require_any=p.is_require_any,
                    options=options,
                    cube_id=cube_id,
                )
            )
            if p.is_require_any:
                require_any = True

    return DataSourceParamsInfo(parameters=parameters, require_any=require_any)


def _to_result(raw: flapi_models.DataSourceRunResult) -> DataSourceResult:
    return DataSourceResult(data=raw.results)


# -- Public API ----------------------------------------------------------


async def search_data_sources(
    query_or_id: str | int,
    *,
    authorization: str | None = None,
) -> list[DataSource]:
    results = await data_source_client.search(query_or_id, authorization=authorization)
    return [_to_data_source(r) for r in results]


async def get_params_info(
    data_source_id: str | int,
    *,
    authorization: str | None = None,
) -> DataSourceParamsInfo:
    info = await data_source_client.get_quick_params_info(
        data_source_id, authorization=authorization
    )
    return _to_params_info(info)


async def run_data_source(
    data_source_id: str | int,
    *,
    authorization: str | None = None,
    params: QuickParams | None = None,
) -> DataSourceResult:
    raw = await data_source_client.run_data_source(
        data_source_id,
        authorization=authorization,
        quick_params=params,
    )
    return _to_result(raw)


async def get_display_name(
    data_source_id: str | int,
    *,
    authorization: str | None = None,
) -> str:
    results = await search_data_sources(data_source_id, authorization=authorization)
    if not results:
        raise LookupError(f"Data source {data_source_id} not found")
    name = results[0].name.strip()
    if not name:
        raise LookupError(f"Data source {data_source_id} has no display name")
    return name


async def fetch_data_source(
    data_source_id: str | int,
    *,
    authorization: str | None = None,
) -> tuple[str, DataSourceResult]:
    name = await get_display_name(data_source_id, authorization=authorization)
    result = await run_data_source(data_source_id, authorization=authorization)
    return name, result


def _default_for(param: ParamDefinition) -> ParamValue | None:
    # Returns the smallest concrete value we can send: a scalar for single-value
    # params, a one-element list for multi-value params. None means the options
    # list is empty or the first option can't be parsed.
    if not param.options:
        return None
    try:
        parsed = parse_param_value(param.options[0].value, param.type)
    except ValueError:
        return None
    return parsed if param.is_single_value else [parsed]


def _minimal_params_for(params_info: DataSourceParamsInfo) -> QuickParams | None:
    if not params_info.parameters:
        return QuickParams(root={})

    defaults: dict[str, tuple[str, ParamValue]] = {}

    if params_info.require_any:
        satisfied = False
        for param in params_info.parameters:
            if not param.is_require_any:
                continue
            value = _default_for(param)
            if value is None:
                continue
            defaults[param.name] = (param.cube_id, value)
            satisfied = True
            break
        if not satisfied:
            return None

    for param in params_info.parameters:
        if not param.is_required or param.name in defaults:
            continue
        value = _default_for(param)
        if value is None:
            return None
        defaults[param.name] = (param.cube_id, value)

    grouped: dict[str, dict[str, ParamValue]] = {}
    for name, (cube_id, value) in defaults.items():
        grouped.setdefault(cube_id, {})[name] = value
    return QuickParams(root=grouped)


async def can_run_without_params(
    data_source_id: str | int,
    *,
    authorization: str | None = None,
) -> tuple[bool, QuickParams | None]:
    params_info = await get_params_info(data_source_id, authorization=authorization)
    minimal = _minimal_params_for(params_info)
    return minimal is not None, minimal


async def get_usage(
    data_source_id: str | int,
    *,
    authorization: str | None = None,
) -> DataSourceUsage:
    metadata = await data_source_client.get_metadata(
        data_source_id, authorization=authorization
    )
    if not metadata.queries:
        # Planner relies on at least one query for its schema-only TS fallback.
        raise FlapiUpstreamError(
            f"Data source {data_source_id} has no queries in metadata",
        )

    queries = [
        DataSourceQuerySchema(
            # `original_name` is what the run endpoint returns as the cube key
            # in `results`; `name` is its display form. Don't mix them up — the
            # codegen uses `name` as a TS property key and a mismatch yields
            # a Response type whose fields never resolve at runtime.
            name=query.original_name,
            display_name=query.name,
            description=query.description,
            fields=[
                DataSourceFieldSchema(
                    name=field.name,
                    display_name=field.display_name,
                    type=_to_domain_field_type(field.type_),
                    description=field.description,
                )
                for field in query.fields
            ],
        )
        for query in metadata.queries
    ]

    params_info = await get_params_info(data_source_id, authorization=authorization)
    minimal = _minimal_params_for(params_info)
    can_run = minimal is not None

    sample: dict[str, object] | None = None
    if minimal is not None:
        try:
            result = await run_data_source(
                data_source_id,
                authorization=authorization,
                params=minimal,
            )
            sample = result.data
        except (FlapiUpstreamError, ValidationError) as exc:
            logger.debug("Skipping sample for data source %s: %s", data_source_id, exc)

    return DataSourceUsage(
        queries=queries,
        params=params_info,
        can_run=can_run,
        sample=sample,
    )
