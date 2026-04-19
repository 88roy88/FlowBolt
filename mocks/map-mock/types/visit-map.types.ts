import type { ReactNode } from "react";

export const UNIQUE_COLUMN_ID = "_id_";
export const DEFAULT_EMPTY_VALUES = "empty";

export type SchemaFieldName = string;

export type SchemaAttributeType = {
  showGrid: boolean;
  ontologyType: string;
  dataInstanceId: string;
  colorByHeatMap: boolean;
  isStrokeWidth: boolean;
  isStrokeColor: boolean;
  isLabelField: boolean;
  isColorField: boolean;
  isOpacityField: boolean;
  isDynamic: boolean;
  sourceDataInstanceId: string;
};

export const GEO_DATA_SCHEMA_TYPES = {
  wkt: "wkt",
  WKT: "WKT",
} as const;

export type GeoDataSchemaTypes = keyof typeof GEO_DATA_SCHEMA_TYPES;

export const CATEGORICAL_DATA_SCHEMA_TYPES = {
  ...GEO_DATA_SCHEMA_TYPES,
  string: "string",
  String: "String",
  datetime: "datetime",
  json: "json",
} as const;

export type CategoricalDataSchemaTypes =
  keyof typeof CATEGORICAL_DATA_SCHEMA_TYPES;

export const AGGREGATIONAL_DATA_SCHEMA_TYPES = {
  int: "int",
  float: "float",
  double: "double",
  Integer: "Integer",
  integer: "integer",
  number: "number",
  INT: "INT",
} as const;

export type AggregationalDataSchemaTypes =
  keyof typeof AGGREGATIONAL_DATA_SCHEMA_TYPES;

export const BOOLEAN_DATA_SCHEMA_TYPES = {
  bool: "bool",
  boolean: "boolean",
} as const;

export type BooleanDataSchemaTypes = keyof typeof BOOLEAN_DATA_SCHEMA_TYPES;

export const WILD_CARD_DATA_SCHEMA_TYPE = {
  "*": "*",
} as const;

export const EMPTY_VALUE_DATA_SCHEMA_TYPE = {
  "ערך ריק": "",
} as const;

export const SCHEMA_TYPES = {
  ...CATEGORICAL_DATA_SCHEMA_TYPES,
  ...AGGREGATIONAL_DATA_SCHEMA_TYPES,
  ...WILD_CARD_DATA_SCHEMA_TYPE,
  ...EMPTY_VALUE_DATA_SCHEMA_TYPE,
  ...BOOLEAN_DATA_SCHEMA_TYPES,
} as const;

export type SchemaTypes = keyof typeof SCHEMA_TYPES;

export const dataBasedEmptyValues = ["average", "median", "common"] as const;

export type AggregationOptions =
  | (typeof dataBasedEmptyValues)[number]
  | "sum"
  | "count"
  | "uniqCount"
  | "groupBy";

export type DataBasedEmptyValues = (typeof dataBasedEmptyValues)[number];

export const emptyValuesTypes = [
  DEFAULT_EMPTY_VALUES,
  "zero",
  ...dataBasedEmptyValues,
] as const;

export type EmptyValuesTypes = (typeof emptyValuesTypes)[number];

export const filterColumnValues = ["include", "exclude"] as const;

export type FilterColumnValuesTypes = (typeof filterColumnValues)[number];

export type ColumnTypes = number | string | Date | undefined;

export type FilterColumnValues = {
  type: FilterColumnValuesTypes;
  values: ColumnTypes[];
};

export type SchemaField = {
  key: SchemaFieldName;
  type: SchemaTypes;
  emptyValues?: EmptyValuesTypes;
  displayName?: string;
  attributes?: Partial<SchemaAttributeType>;
  filterValues?: FilterColumnValues;
  description?: string;
};

export type Schema = SchemaField[];

export interface IndexedRow extends Row {
  [UNIQUE_COLUMN_ID]: string;
}

export type RowValue = string | number;

export interface Row {
  [prop: string]: RowValue;
}

export interface UnindexedTable {
  data: Row[];
  schema: Schema;
  noData?: boolean;
  failedParsing?: boolean;
}

export interface IndexedTable extends UnindexedTable {
  data: IndexedRow[];
}

export type Table = IndexedTable | UnindexedTable;

export type IndexedTableDictionary = Record<string, IndexedTable>;
export type UnindexedTableDictionary = Record<string, UnindexedTable>;

export type TableDictionary = IndexedTableDictionary | UnindexedTableDictionary;

export const HOST_STATES = {
  SUCCEEDED: "SUCCEEDED",
  PENDING: "PENDING",
  RUNNING: "RUNNING",
  FAILED: "FAILED",
} as const;

export type HostStatesTypes = keyof typeof HOST_STATES;

type GraphixSettingsKeys =
  | "savingPendingGraph"
  | "previewInCatalog"
  | "openGraphix";

export type GenerateAllowKeys<T extends string> = `allow${Capitalize<T>}`;

export type BooleanSettings<T extends string> = Partial<{
  [Key in T as GenerateAllowKeys<T>]: boolean;
}>;

export type GraphixSettings = BooleanSettings<GraphixSettingsKeys> & {
  savePendingButtonTooltip?: string;
};

export type VisualizationFetchByFields = {
  sourceSystemDataId: boolean;
  schema: boolean;
  externalDataInstanceInfo: DataInstanceInfo & { id: string };
};

export type CustomViewsSettingsKeys = "addingPersonalViews";

export type CustomViewsSettings = BooleanSettings<CustomViewsSettingsKeys>;

export interface DataInstanceInfo {
  sourceSystemDataId: string;
  name?: string;
  icon?: string;
  displayName?: string;
  display?: ReactNode;
  state?: HostStatesTypes;
  graphixSettings?: GraphixSettings;
  visualizationFetchByFields?: VisualizationFetchByFields;
  customViewsSettings?: CustomViewsSettings;
  limitNumber?: number;
}

export type MapDataInstanceInfo = DataInstanceInfo & {
  dataInstanceId?: string;
  datasetId: string;
  datasetDisplayName?: string;
  datasetIcon?: string;
  originalMetadata?: {
    datasetId?: string;
    dataInstanceId?: string;
    dashboardId?: string;
  };
};

export type MapDataInstanceInfoDictionary = Record<string, MapDataInstanceInfo>;

export type MapOption = string;

export type MapOptionKey = keyof MapOption;

export type MapVisualizationOptions = Partial<
  Record<MapOptionKey, { disabled?: boolean }>
>;

export type CommonBaseSpecType = {
  colorByValue?: { [key: string]: string };
};

export interface MapSpec extends CommonBaseSpecType {
  colorByFields?: string[];
  chart?: {
    type: "map";
  };
}

export type BaseVisualization = {
  visualizationId: string;
  sourceSystem: string;
  creationUser: string;
  creationTime: string;
  lastUpdateTime: string;
};

export interface MapVisualization extends BaseVisualization {
  type: "map";
  spec: MapSpec;
}

export const mapType = "map";

export const MAP_VISUALIZATION: MapVisualization & {
  isPending: boolean;
  template: string;
} = {
  type: mapType,
  visualizationId: "map",
  creationUser: "7lalonz@8209",
  sourceSystem: "flow",
  spec: {
    chart: {
      type: mapType,
    },
  },
  creationTime: "",
  lastUpdateTime: "",
  isPending: false,
  template: '{{"hsp":{"text"},"chart":{"type":"map"},"title"}}',
};
