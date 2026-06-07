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
            queries=_queries("sales"),
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
            queries=_queries("x"),
        )
        assert "(await res.json()) as { data: XResults }" in result
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
            queries=_queries("person"),
        )
        assert "export async function dataSourcePerson({\n  personId,\n}: {\n  personId: number; // Person\n}): Promise<PersonResults>" in result
        assert "body['people']['person_id'] = personId;" in result
        assert "fetchWithAuth('/api/data-source/7/run', {" in result
        assert "method: 'POST'" in result
        assert "body: JSON.stringify(body)" in result

    def test_schema_only_response_type_when_no_sample(self) -> None:
        result = generate_data_source_module(
            data_source_id="7",
            sanitized_name="Person",
            params_info=_empty_params(),
            queries=_queries("person"),
        )
        # Schema-based interface is emitted.
        assert "export interface PersonPerson" in result
        assert "id: number;" in result
        assert "label: string;" in result
        assert "export interface PersonResults" in result


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
            queries=_queries("mixed"),
        )
        assert "  type,\n  priority,\n  createdAfter,\n}: {\n  type: string;\n  priority?: string | string[];\n  createdAfter?: { From: Date; To: Date };" in result
        assert "body['tasks']['type'] = type;" in result
        assert "if (priority !== undefined) {\n    body['tasks']['priority'] = priority;\n  }" in result
        assert "if (createdAfter !== undefined) {\n    body['tasks']['created_after'] = createdAfter;\n  }" in result


class TestDisplayNameComment:
    def test_comment_only_on_non_redundant_display_name(self) -> None:
        # "name" / "Name" → redundant → no comment
        # "dept_id" / "Department" → different → comment emitted
        params = DataSourceParamsInfo(
            parameters=[
                ParamDefinition(
                    name="name",
                    display_name="Name",
                    type="string",
                    is_required=True,
                    is_single_value=True,
                    options=[],
                    cube_id="employees",
                ),
                ParamDefinition(
                    name="dept_id",
                    display_name="Department",
                    type="string",
                    is_required=True,
                    is_single_value=True,
                    options=[],
                    cube_id="employees",
                ),
            ],
            require_any=False,
        )
        result = generate_data_source_module(
            data_source_id="1",
            sanitized_name="Employee",
            params_info=params,
            queries=_queries("employee"),
        )
        assert "name: string;\n  deptId: string; // Department" in result
        assert "name: string; // Name" not in result


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
            queries=_queries("tagged"),
        )
        assert "tags: string | string[];" in result

    def test_is_single_value_true_does_not_emit_array(self) -> None:
        params = DataSourceParamsInfo(
            parameters=[
                ParamDefinition(
                    name="tags",
                    display_name="Tags",
                    type="string",
                    is_required=True,
                    is_single_value=True,
                    options=[],
                )
            ],
            require_any=False,
        )
        result = generate_data_source_module(
            data_source_id="1",
            sanitized_name="Tagged",
            params_info=params,
            queries=_queries("tagged"),
        )
        assert "tags: string;" in result
        assert "string[]" not in result


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
            queries=_queries("t"),
        )
        assert "startDate: { From: Date; To: Date }" in result


class TestTypeDefs:
    def _make(self, param_type: str) -> str:
        return generate_data_source_module(
            data_source_id="1",
            sanitized_name="T",
            params_info=DataSourceParamsInfo(
                parameters=[
                    ParamDefinition(
                        name="p",
                        display_name="P",
                        type=param_type,  # type: ignore[arg-type]
                        is_required=True,
                        is_single_value=True,
                        options=[],
                    )
                ],
                require_any=False,
            ),
            queries=_queries("t"),
        )

    def test_daterange_typedef_emitted_for_datetime_param(self) -> None:
        result = self._make("datetime")
        assert "{ From: Date; To: Date }" in result
        assert "type WKT" not in result

    def test_wkt_typedef_emitted_for_geographic_param(self) -> None:
        result = self._make("geographic")
        assert "type WKT = string;" in result
        assert "type DateRange" not in result

    def test_no_typedefs_for_string_param(self) -> None:
        result = self._make("string")
        assert "type DateRange" not in result
        assert "type WKT" not in result


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
            queries=_queries("r"),
        )
        assert "from_: { From: Date; To: Date }" in result
        assert "delete_?: boolean" in result
        # The body keys still use the FLAPI names.
        assert "body['events']['from'] = from_;" in result
        assert "if (delete_ !== undefined) {\n    body['events']['delete'] = delete_;\n  }" in result


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
            queries=_queries("report"),
        )
        # Colliding names get cube_id prefix; unique names stay as-is.
        assert "reports_startDate: { From: Date; To: Date }" in result
        assert "filters_startDate: { From: Date; To: Date }" in result
        assert "limit?: number" in result
        # Each is wired to the correct cube in the body.
        assert "body['reports']['start_date'] = reports_startDate;" in result
        assert "body['filters']['start_date'] = filters_startDate;" in result
        assert "if (limit !== undefined) {\n    body['reports']['limit'] = limit;\n  }" in result


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
            queries=_queries("geo_event"),
        )
        assert "label: string" in result
        assert "validFrom: { From: Date; To: Date }" in result
        assert "recordedAt?: Date" in result
        assert "area?: WKT" in result
        assert "isActive?: boolean" in result
        assert "body['geo']['label'] = label;" in result
        assert "body['geo']['valid_from'] = validFrom;" in result
        assert "if (recordedAt !== undefined) {\n    body['geo']['recorded_at'] = recordedAt;\n  }" in result
        assert "if (area !== undefined) {\n    body['geo']['area'] = area;\n  }" in result
        assert "if (isActive !== undefined) {\n    body['geo']['is_active'] = isActive;\n  }" in result


class TestRequireAnyGroup:
    def test_require_any_params_are_optional_in_signature(self) -> None:
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
            queries=_queries("contact"),
        )
        assert "  email,\n  phone,\n}: {\n  email?: string;\n  phone?: string;" in result

    def test_require_any_jsdoc_comment_lists_param_names(self) -> None:
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
            queries=_queries("contact"),
        )
        assert "/** At least one of the following must be provided: email, phone. */" in result

    def test_no_jsdoc_comment_when_no_require_any(self) -> None:
        params = DataSourceParamsInfo(
            parameters=[
                ParamDefinition(
                    name="user_id",
                    display_name="User ID",
                    type="int",
                    is_required=True,
                    is_single_value=True,
                ),
            ],
            require_any=False,
        )
        result = generate_data_source_module(
            data_source_id="1",
            sanitized_name="User",
            params_info=params,
            queries=_queries("user"),
        )
        assert "/** At least one" not in result


class TestResultsKeyUsesDisplayName:
    def test_results_key_and_date_conversion_use_display_name(self) -> None:
        # query.name="rows" differs from display_name="Order Rows"
        # Results interface key and date conversion must use display_name, not name
        queries = [
            DataSourceQuerySchema(
                name="rows",
                display_name="Order Rows",
                description="",
                fields=[
                    DataSourceFieldSchema(name="id", display_name="ID", type="int"),
                    DataSourceFieldSchema(name="created_at", display_name="Created at", type="datetime"),
                ],
            )
        ]
        result = generate_data_source_module(
            data_source_id="1",
            sanitized_name="Sales",
            params_info=_empty_params(),
            queries=queries,
        )
        assert '"Order Rows": SalesRows[]' in result
        assert "    for (const row of envelope.data['Order Rows'])" in result
        assert "rows: SalesRows[]" not in result
        assert "envelope.data['rows']" not in result


class TestDatetimeFieldConversion:
    def test_datetime_fields_converted_to_date_in_body(self) -> None:
        queries = [
            DataSourceQuerySchema(
                name="events",
                display_name="Events",
                description="",
                fields=[
                    DataSourceFieldSchema(name="id", display_name="ID", type="int"),
                    DataSourceFieldSchema(name="created_at", display_name="Created at", type="datetime"),
                    DataSourceFieldSchema(name="label", display_name="Label", type="string"),
                    DataSourceFieldSchema(name="updated_at", display_name="Updated at", type="datetime"),
                ],
            )
        ]
        result = generate_data_source_module(
            data_source_id="5",
            sanitized_name="Event",
            params_info=_empty_params(),
            queries=queries,
        )
        # Interface uses Date
        assert "created_at: Date;" in result
        assert "updated_at: Date;" in result
        # Conversion loops emitted after envelope cast
        assert "  try {\n" in result
        assert "    for (const row of envelope.data['Events'])" in result
        assert "      if (row['created_at'] != null) row['created_at'] = new Date(row['created_at'] as unknown as string);" in result
        assert "      if (row['updated_at'] != null) row['updated_at'] = new Date(row['updated_at'] as unknown as string);" in result
        assert "  } catch (e) {\n    console.warn('Failed to convert date fields', e);\n  }" in result
        # Non-datetime fields don't get a conversion line
        assert "row['id']" not in result
        assert "row['label']" not in result

    def test_no_datetime_fields_no_conversion_loop(self) -> None:
        result = generate_data_source_module(
            data_source_id="1",
            sanitized_name="Plain",
            params_info=_empty_params(),
            queries=_queries("plain"),
        )
        assert "for (const row of" not in result
        assert "new Date(" not in result
