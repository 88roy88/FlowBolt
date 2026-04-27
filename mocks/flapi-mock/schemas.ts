import { Type, Static } from '@sinclair/typebox';

// Shared literal unions — mirrors FLAPI wire vocabulary (see
// backend/src/flow44/integrations/flapi/models.py). FieldType is lowercase
// with legacy tags; ParamType (quick-params) is PascalCase; OntologyType is
// the post-narrowing set.
const FieldType = Type.Union([
  Type.Literal('string'),
  Type.Literal('int'),
  Type.Literal('double'),
  Type.Literal('bool'),
  Type.Literal('datetime'),
  Type.Literal('Haphoch'),
  Type.Literal('wkt'),
  Type.Literal('dynamic'),
  Type.Literal('float'),
  Type.Literal('geojson'),
  Type.Literal('GeoEllipse'),
  Type.Literal('Object'),
  Type.Literal('Int'),
]);

const ParamType = Type.Union([
  Type.Literal('String'),
  Type.Literal('Int'),
  Type.Literal('Double'),
  Type.Literal('Boolean'),
  Type.Literal('DateTime'),
]);

const OntologyType = Type.Union([
  Type.Literal('TEXT'),
  Type.Literal('GEOMETRY'),
  Type.Literal('TOOLID'),
  Type.Literal('PSTN'),
  Type.Literal('IMEI'),
  Type.Literal('IMSI'),
  Type.Literal('TIME'),
  Type.Literal('CELL'),
  Type.Literal('OCR'),
]);

const SearchResultType = Type.Literal('Package');

// Error types
export const ErrorBodySchema = Type.Object({
  error: Type.Object({
    code: Type.String(),
    message: Type.String(),
    details: Type.Optional(Type.Unknown()),
  }),
});

export type ErrorBody = Static<typeof ErrorBodySchema>;


// Package Metadata types
export const FieldAttributesSchema = Type.Object({
  OntologyType: OntologyType,
  OriginalOntologyType: OntologyType,
});

export const QueryFieldSchema = Type.Object({
  Name: Type.String(),
  DisplayName: Type.String(),
  Type: FieldType,
  IsDynamic: Type.Boolean(),
  Attributes: FieldAttributesSchema,
  Description: Type.Union([Type.String(), Type.Null()]),
});

export const QuerySchema = Type.Object({
  uniqueName: Type.String(),
  originalName: Type.String(),
  Name: Type.String(),
  ResultsLimit: Type.Number(),
  DataSourceName: Type.String(),
  Description: Type.String(),
  id: Type.String(),
  Fields: Type.Array(QueryFieldSchema),
});

export const PackageMetadataSchema = Type.Object({
  Description: Type.String(),
  Id: Type.Number(),
  Name: Type.String(),
  OutputQueriesId: Type.Array(Type.Unknown()),
  Queries: Type.Array(QuerySchema),
});

export type PackageMetadata = Static<typeof PackageMetadataSchema>;

// Search Result types
export const SearchResultSchema = Type.Object({
  Id: Type.Number(),
  Name: Type.String(),
  Type: SearchResultType,
  Purpose: Type.String(),
  Description: Type.String(),
});

export type SearchResult = Static<typeof SearchResultSchema>;

// Quick Param types
export const QuickParamValueSchema = Type.Object({
  Name: Type.String(),
  Value: Type.String(),
});

export const QuickParamDefinitionSchema = Type.Object({
  Name: Type.String(),
  DisplayName: Type.String(),
  Description: Type.Union([Type.String(), Type.Null()]),

  Type: ParamType,
  OntologyType: OntologyType,

  IsSingleValue: Type.Boolean(),
  IsRequired: Type.Boolean(),
  IsRequireAny: Type.Boolean(),   // Is it even exist?

  Value: Type.Array(QuickParamValueSchema),
});

export type QuickParamDefinition = Static<typeof QuickParamDefinitionSchema>;

// Run Result types
export const RunResultSchema = Type.Object({
  results: Type.Record(Type.String(), Type.Unknown()),
});

export type RunResult = Static<typeof RunResultSchema>;

// Health check
export const HealthSchema = Type.Object({
  ok: Type.Boolean(),
  mock: Type.Boolean(),
});

export type Health = Static<typeof HealthSchema>;

// Error helper
export const errorBody = (code: string, message: string, details?: unknown): ErrorBody => {
  const body: ErrorBody = { error: { code, message } };
  if (details !== undefined) body.error.details = details;
  return body;
};
