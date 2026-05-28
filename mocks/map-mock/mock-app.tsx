import { stubGeoResults } from "./constants/mock-data";
import {
  type TableDictionary,
  UNIQUE_COLUMN_ID,
  type MapDataInstanceInfoDictionary,
} from "./types/visit-map.types";
import { MapRenderer } from "./visit-map-mock";

const stubGeoData = [
  {
    id: "geo_table_1",
    dataInstanceId: "geo_table_1", // cube identifier
    datasetId: "geo_dataset_1", // package identifier
    name: "Geo Data",
    displayName: "Geo Data",
    data: stubGeoResults,
  },
];

function inferSchema(data: any[]): any[] {
  if (!data.length) return [];

  return Object.keys(data[0]).map((key) => ({
    key,
    type: typeof data[0][key],
  }));
}

const createTableDictionary = (rawTables: any[] = []): TableDictionary => {
  const tableDictionary: TableDictionary = {};

  rawTables.forEach((table) => {
    const dataInstanceId = table.dataInstanceId || table.id;
    const data = Array.isArray(table.data) ? table.data : [];

    const indexedData = data.map((row: any, index: number) => ({
      ...row,
      [UNIQUE_COLUMN_ID]: `${dataInstanceId}_${index}`,
    }));

    tableDictionary[dataInstanceId] = {
      data: indexedData,
      schema: table.schema?.length ? table.schema : inferSchema(data),
      noData: data.length === 0,
      failedParsing: false,
    };
  });

  return tableDictionary;
};

const createTableInfoDictionary = (
  rawTables: any[] = []
): MapDataInstanceInfoDictionary => {
  const tableInfoDictionary: MapDataInstanceInfoDictionary = {};

  rawTables.forEach((table) => {
    const dataInstanceId = table.dataInstanceId || table.id;
    const datasetId = table.datasetId || "default_dataset";

    tableInfoDictionary[dataInstanceId] = {
      sourceSystemDataId: dataInstanceId,
      dataInstanceId,
      datasetId,
      name: table.name || dataInstanceId,
      displayName: table.displayName || table.name || dataInstanceId,
      state: "SUCCEEDED",
      originalMetadata: {
        datasetId,
        dataInstanceId,
      },
    };
  });

  return tableInfoDictionary;
};
export const MockApp = () => {
  const tableDictionary = createTableDictionary(stubGeoData);
  const tableInfoDictionary = createTableInfoDictionary(stubGeoData);

  return (
    <div
      style={{
        width: "50vw",
        height: "100vh",
        position: "absolute",
        left: "2rem",
        top: "2rem",
      }}
    >
      <MapRenderer
        tableDictionary={tableDictionary}
        tableInfoDictionary={tableInfoDictionary}
        mapVisualizationOptions={{}}
      />
    </div>
  );
};
