"""Tests for flow44.ai.codegen.data_source_module."""

from __future__ import annotations

from flow44.ai.codegen.data_source_module import generate_data_source_module
from flow44.logic.models import (
    DataSourceFieldSchema,
    DataSourceParamsInfo,
    DataSourceQuerySchema,
    ParamDefinition,
    ParamOption,
)


def _empty_params() -> DataSourceParamsInfo:
    return DataSourceParamsInfo(parameters=[], require_any=False)


def _queries(cube_name: str = "items") -> list[DataSourceQuerySchema]:
    return [
        DataSourceQuerySchema(
            name=cube_name,
            display_name=cube_name,
            description="Items cube",
            fields=[
                DataSourceFieldSchema(name="id", display_name="ID", type="int"),
                DataSourceFieldSchema(name="label", display_name="Label", type="string"),
            ],
        )
    ]


class TestNoParams:
    def test_zero_arg_signature_and_empty_body(self) -> None:
        result = generate_data_source_module(
            data_source_id="42",
            sanitized_name="Sales",
            params_info=_empty_params(),
            sample_data={"results": {"sales": [{"id": 1, "amount": 100}]}},
            queries=None,
        )
        assert "import { fetchWithAuth } from '../api/client';" in result
        assert "export async function dataSourceSales(): Promise<SalesResults>" in result
        assert "/api/data-source/42/run" in result
        # No body built; fetchWithAuth called with just the path.
        assert "fetchWithAuth('/api/data-source/42/run')" in result
        assert "const body:" not in result


class TestEnvelopeUnwrap:
    def test_unwraps_data_envelope(self) -> None:
        result = generate_data_source_module(
            data_source_id="1",
            sanitized_name="X",
            params_info=_empty_params(),
            sample_data=None,
            queries=_queries("x"),
        )
        assert "(await res.json()) as XResponse" in result
        assert "return envelope.data;" in result


class TestRequiredParam:
    def test_required_string_param_typed_positional(self) -> None:
        params = DataSourceParamsInfo(
            parameters=[
                ParamDefinition(
                    name="person_id",
                    display_name="Person",
                    type="int",
                    is_required=True,
                    is_single_value=True,
                    options=[],
                    cube_id="people",
                )
            ],
            require_any=False,
        )
        result = generate_data_source_module(
            data_source_id="7",
            sanitized_name="Person",
            params_info=params,
            sample_data=None,
            queries=_queries("person"),
        )
        assert "export async function dataSourcePerson({ personId }: { personId: number }): Promise<PersonResults>" in result
        assert "body['people']['person_id'] = personId;" in result
        assert "fetchWithAuth('/api/data-source/7/run', body);" in result

    def test_schema_only_response_type_when_no_sample(self) -> None:
        result = generate_data_source_module(
            data_source_id="7",
            sanitized_name="Person",
            params_info=_empty_params(),
            sample_data=None,
            queries=_queries("person"),
        )
        # Schema-based interface is emitted.
        assert "export interface PersonPerson" in result
        assert "id: number;" in result
        assert "label: string;" in result
        assert "export interface PersonResponse" in result


class TestMixedParams:
    def test_required_positional_optional_in_options_object(self) -> None:
        params = DataSourceParamsInfo(
            parameters=[
                ParamDefinition(
                    name="type",
                    display_name="Type",
                    type="string",
                    is_required=True,
                    is_single_value=True,
                    options=[],
                    cube_id="tasks",
                ),
                ParamDefinition(
                    name="priority",
                    display_name="Priority",
                    type="string",
                    is_required=False,
                    is_single_value=False,
                    options=[ParamOption(name="low", value="low")],
                    cube_id="tasks",
                ),
                ParamDefinition(
                    name="created_after",
                    display_name="Created after",
                    type="datetime",
                    is_required=False,
                    is_single_value=True,
                    options=[],
                    cube_id="tasks",
                ),
            ],
            require_any=False,
        )
        result = generate_data_source_module(
            data_source_id="55",
            sanitized_name="Mixed",
            params_info=params,
            sample_data=None,
            queries=_queries("mixed"),
        )
        assert "dataSourceMixed({ type, priority, createdAfter }: { type: string; priority?: string; createdAfter?: DateRange })" in result
        assert "body['tasks']['type'] = type;" in result
        assert "if (priority !== undefined) body['tasks']['priority'] = priority;" in result
        assert "if (createdAfter !== undefined) body['tasks']['created_after'] = createdAfter;" in result


class TestArrayParam:
    def test_is_single_value_false_emits_array(self) -> None:
        params = DataSourceParamsInfo(
            parameters=[
                ParamDefinition(
                    name="tags",
                    display_name="Tags",
                    type="string",
                    is_required=True,
                    is_single_value=False,
                    options=[],
                )
            ],
            require_any=False,
        )
        result = generate_data_source_module(
            data_source_id="1",
            sanitized_name="Tagged",
            params_info=params,
            sample_data=None,
            queries=_queries("tagged"),
        )
        assert "dataSourceTagged({ tags }: { tags: string })" in result


class TestTypeCoercion:
    def test_boolean_maps_to_boolean(self) -> None:
        params = DataSourceParamsInfo(
            parameters=[
                ParamDefinition(
                    name="active",
                    display_name="Active",
                    type="bool",
                    is_required=True,
                    is_single_value=True,
                    options=[],
                )
            ],
            require_any=False,
        )
        result = generate_data_source_module(
            data_source_id="1",
            sanitized_name="T",
            params_info=params,
            sample_data=None,
            queries=_queries("t"),
        )
        assert "active: boolean" in result

    def test_date_maps_to_string(self) -> None:
        params = DataSourceParamsInfo(
            parameters=[
                ParamDefinition(
                    name="start_date",
                    display_name="Start",
                    type="datetime",
                    is_required=True,
                    is_single_value=True,
                    options=[],
                )
            ],
            require_any=False,
        )
        result = generate_data_source_module(
            data_source_id="1",
            sanitized_name="T",
            params_info=params,
            sample_data=None,
            queries=_queries("t"),
        )
        assert "startDate: DateRange" in result


class TestReservedWordParamName:
    def test_reserved_word_gets_trailing_underscore_in_identifier(self) -> None:
        # "from" and "delete" are JS/TS reserved words — we must not emit
        # them as bare parameter/property names. The body key stays the
        # original FLAPI name so the upstream request is unchanged.
        params = DataSourceParamsInfo(
            parameters=[
                ParamDefinition(
                    name="from",
                    display_name="From",
                    type="datetime",
                    is_required=True,
                    is_single_value=True,
                    options=[],
                    cube_id="events",
                ),
                ParamDefinition(
                    name="delete",
                    display_name="Delete",
                    type="bool",
                    is_required=False,
                    is_single_value=True,
                    options=[],
                    cube_id="events",
                ),
            ],
            require_any=False,
        )
        result = generate_data_source_module(
            data_source_id="1",
            sanitized_name="R",
            params_info=params,
            sample_data=None,
            queries=_queries("r"),
        )
        assert "from_: DateRange" in result
        assert "delete_?: boolean" in result
        # The body keys still use the FLAPI names.
        assert "body['events']['from'] = from_;" in result
        assert "if (delete_ !== undefined) body['events']['delete'] = delete_;" in result


class TestCubeIdDisambiguation:
    def test_same_param_name_in_different_cubes_gets_cube_prefix(self) -> None:
        # Both cubes expose a param called "start_date"; the generated identifiers
        # must not collide, and each must be wired to the correct cube's body key.
        params = DataSourceParamsInfo(
            parameters=[
                ParamDefinition(
                    name="start_date",
                    display_name="Start date",
                    type="datetime",
                    is_required=True,
                    is_single_value=True,
                    options=[],
                    cube_id="reports",
                ),
                ParamDefinition(
                    name="start_date",
                    display_name="Start date",
                    type="datetime",
                    is_required=True,
                    is_single_value=True,
                    options=[],
                    cube_id="filters",
                ),
                ParamDefinition(
                    name="limit",
                    display_name="Limit",
                    type="int",
                    is_required=False,
                    is_single_value=True,
                    options=[],
                    cube_id="reports",
                ),
            ],
            require_any=False,
        )
        result = generate_data_source_module(
            data_source_id="10",
            sanitized_name="Report",
            params_info=params,
            sample_data=None,
            queries=_queries("report"),
        )
        # Colliding names get cube_id prefix; unique names stay as-is.
        assert "reports_startDate: DateRange" in result
        assert "filters_startDate: DateRange" in result
        assert "limit?: number" in result
        # Each is wired to the correct cube in the body.
        assert "body['reports']['start_date'] = reports_startDate;" in result
        assert "body['filters']['start_date'] = filters_startDate;" in result
        assert "if (limit !== undefined) body['reports']['limit'] = limit;" in result


class TestAllParamTypes:
    def test_all_four_param_types_map_to_correct_ts_types(self) -> None:
        params = DataSourceParamsInfo(
            parameters=[
                ParamDefinition(
                    name="label",
                    display_name="Label",
                    type="string",
                    is_required=True,
                    is_single_value=True,
                    options=[],
                    cube_id="geo",
                ),
                ParamDefinition(
                    name="valid_from",
                    display_name="Valid from",
                    type="datetime",
                    is_required=True,
                    is_single_value=True,
                    options=[],
                    cube_id="geo",
                ),
                ParamDefinition(
                    name="recorded_at",
                    display_name="Recorded at",
                    type="timestamp",
                    is_required=False,
                    is_single_value=True,
                    options=[],
                    cube_id="geo",
                ),
                ParamDefinition(
                    name="area",
                    display_name="Area",
                    type="geographic",
                    is_required=False,
                    is_single_value=True,
                    options=[],
                    cube_id="geo",
                ),
                ParamDefinition(
                    name="is_active",
                    display_name="Is active",
                    type="bool",
                    is_required=False,
                    is_single_value=True,
                    options=[],
                    cube_id="geo",
                ),
            ],
            require_any=False,
        )
        result = generate_data_source_module(
            data_source_id="99",
            sanitized_name="GeoEvent",
            params_info=params,
            sample_data=None,
            queries=_queries("geo_event"),
        )
        assert "label: string" in result
        assert "validFrom: DateRange" in result
        assert "recordedAt?: Date" in result
        assert "area?: WKT" in result
        assert "isActive?: boolean" in result
        assert "body['geo']['label'] = label;" in result
        assert "body['geo']['valid_from'] = validFrom;" in result
        assert "if (recordedAt !== undefined) body['geo']['recorded_at'] = recordedAt;" in result
        assert "if (area !== undefined) body['geo']['area'] = area;" in result
        assert "if (isActive !== undefined) body['geo']['is_active'] = isActive;" in result


class TestRequireAnyGroup:
    def test_require_any_params_are_positional_required(self) -> None:
        params = DataSourceParamsInfo(
            parameters=[
                ParamDefinition(
                    name="email",
                    display_name="Email",
                    type="string",
                    is_required=False,
                    is_require_any=True,
                    is_single_value=True,
                ),
                ParamDefinition(
                    name="phone",
                    display_name="Phone",
                    type="string",
                    is_required=False,
                    is_require_any=True,
                    is_single_value=True,
                ),
            ],
            require_any=True,
        )
        result = generate_data_source_module(
            data_source_id="9",
            sanitized_name="Contact",
            params_info=params,
            sample_data=None,
            queries=_queries("contact"),
        )
        # Both require_any params are treated as required positional for TS typing
        # (runtime OR-validation is the caller's concern; the prompt tells the LLM
        # at least one must be provided).
        assert "dataSourceContact({ email, phone }: { email: string; phone: string })" in result
