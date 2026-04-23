import { Type, Static } from '@sinclair/typebox';

// Shared literal unions
const FieldType = Type.Union([
  Type.Literal('String'),
  Type.Literal('Integer'),
  Type.Literal('Decimal'),
  Type.Literal('Boolean'),
  Type.Literal('Date'),
]);

const ParamType = Type.Union([
  Type.Literal('String'),
  Type.Literal('Integer'),
  Type.Literal('Boolean'),
  Type.Literal('Date'),
]);

const OntologyType = Type.Union([
  Type.Literal('TEXT'),
  Type.Literal('NUMBER'),
  Type.Literal('BOOLEAN'),
  Type.Literal('DATE'),
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
  Id: Type.String(),
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
