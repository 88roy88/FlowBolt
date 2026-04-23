import { Type, Static } from '@sinclair/typebox';

// Error types
export const ErrorBodySchema = Type.Object({
  error: Type.Object({
    code: Type.String(),
    message: Type.String(),
    details: Type.Optional(Type.Unknown()),
  }),
});

export type ErrorBody = Static<typeof ErrorBodySchema>;

// Tag types
export const TagSchema = Type.Object({
  value: Type.String(),
  label: Type.String(),
});

export type Tag = Static<typeof TagSchema>;

// Package Metadata types
export const FieldAttributesSchema = Type.Object({
  ShowOnGrid: Type.Boolean(),
  OntologyType: Type.String(),
  OriginalOntologyType: Type.String(),
});

export const QueryFieldSchema = Type.Object({
  Name: Type.String(),
  DisplayName: Type.String(),
  Type: Type.String(),
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
  Metadata: Type.Record(Type.String(), Type.Unknown()),
  Id: Type.String(),
  queryExecutionConfiguration: Type.Record(Type.String(), Type.Unknown()),
  Fields: Type.Array(QueryFieldSchema),
});

export const PackageMetadataSchema = Type.Object({
  Description: Type.String(),
  CreatedBy: Type.String(),
  ChangedBy: Type.String(),
  CreationDate: Type.String(),
  UpdatedDate: Type.String(),
  Tags: Type.Array(TagSchema),
  Subjects: Type.Array(Type.Unknown()),
  Id: Type.Number(),
  QualityPercents: Type.Number(),
  QualityFeatures: Type.Union([Type.Unknown(), Type.Null()]),
  Name: Type.String(),
  OutputQueriesId: Type.Array(Type.Unknown()),
  maintenanceStandard: Type.Record(Type.String(), Type.Unknown()),
  Links: Type.Array(Type.Unknown()),
  Queries: Type.Array(QuerySchema),
});

export type FieldAttributes = Static<typeof FieldAttributesSchema>;
export type QueryField = Static<typeof QueryFieldSchema>;
export type Query = Static<typeof QuerySchema>;
export type PackageMetadata = Static<typeof PackageMetadataSchema>;

// Search Result types
export const SearchResultSchema = Type.Object({
  Purpose: Type.String(),
  Description: Type.String(),
  UserName: Type.String(),
  TimedPackagesCount: Type.Number(),
  Tags: Type.String(),
  Subjects: Type.String(),
  CreationDate: Type.String(),
  UpdatedDate: Type.String(),
  Type: Type.String(),
  QualityPercents: Type.Number(),
  IsOld: Type.Boolean(),
  LastUseDate: Type.String(),
  InformationFileName: Type.Union([Type.Unknown(), Type.Null()]),
  IsTimedPackage: Type.Boolean(),
  IsProductPackage: Type.Boolean(),
  CreatedBy: Type.String(),
  Path: Type.String(),
  DirectoryId: Type.Number(),
  IsEditPermitted: Type.Boolean(),
  IsViewPermitted: Type.Boolean(),
  IsPublic: Type.Boolean(),
  Name: Type.String(),
  Id: Type.Number(),
});

export type SearchResult = Static<typeof SearchResultSchema>;

// Quick Param types
export const QuickParamValueSchema = Type.Object({
  Name: Type.String(),
  Value: Type.String(),
});

export const QuickParamDefinitionSchema = Type.Object({
  Name: Type.String(),
  ColumnName: Type.String(),
  Type: Type.String(),
  DisplayName: Type.String(),
  IsSingleValue: Type.Boolean(),
  IsRequired: Type.Boolean(),
  Visible: Type.Boolean(),
  Value: Type.Array(QuickParamValueSchema),
  IsDynamic: Type.Boolean(),
  IsExcel: Type.Boolean(),
  OntologyType: Type.String(),
  Attributes: Type.Array(Type.Unknown()),
  id: Type.String(),
  data: Type.Record(Type.String(), Type.Unknown()),
  quickParameterInfo: Type.Object({
    DisplayName: Type.String(),
    Description: Type.String(),
    RequiredType: Type.Object({
      IsRequired: Type.Boolean(),
      IsRequireAny: Type.Boolean(),
      DisplayName: Type.String(),
      disabledToolTipText: Type.String(),
    }),
  }),
  parameterIndex: Type.Number(),
  QueryId: Type.String(),
  QueryDisplayName: Type.String(),
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
