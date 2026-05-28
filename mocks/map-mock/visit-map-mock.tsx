import { MutableRefObject, useRef } from "react";
import {
  MAP_VISUALIZATION,
  type MapDataInstanceInfoDictionary,
  type MapVisualization,
  type MapVisualizationOptions,
  type TableDictionary,
} from "./types/visit-map.types";

interface Props {
  tableDictionary: TableDictionary;
  tableInfoDictionary: MapDataInstanceInfoDictionary;
  mapVisualizationOptions: MapVisualizationOptions;
  visualization?: MapVisualization & {
    isPending: boolean;
    template: string;
  };
  mapServiceRef?: MutableRefObject<any>;
}

export const MapRenderer = ({
  tableDictionary,
  tableInfoDictionary,
  mapVisualizationOptions,
  visualization = MAP_VISUALIZATION,
  mapServiceRef,
}: Props) => {
  const containerRef = useRef<HTMLDivElement>(null);

  const getTableInfo = (dataInstanceId: string) => {
    return tableInfoDictionary[dataInstanceId];
  };

  // displaying the data received in a table in order to show it received as expected
  const renderTable = (
    tableId: string,
    tableData: {
      data: any[];
      schema: any[];
      noData?: boolean;
      failedParsing?: boolean;
    }
  ) => {
    if (tableData.noData) {
      return (
        <div key={tableId} className="mb-5">
          <h3 className="text-lg font-semibold">No Data</h3>
        </div>
      );
    }

    if (tableData.failedParsing) {
      return (
        <div key={tableId} className="mb-5">
          <h3 className="text-lg font-semibold">Failed to parse data</h3>
        </div>
      );
    }

    const { data, schema } = tableData;

    const tableInfo =
      schema.length > 0 && schema[0]?.attributes?.dataInstanceId
        ? getTableInfo(schema[0].attributes.dataInstanceId)
        : null;

    return (
      <div key={tableId} className="mb-8">
        <div className="mb-2.5">
          <h3 className="mb-1 flex items-center gap-2 text-lg font-semibold text-gray-900">
            {tableInfo?.icon && <span>{tableInfo.icon}</span>}
            {tableInfo?.displayName || tableInfo?.name || tableId}
          </h3>

          {tableInfo && (
            <p className="m-0 text-[11px] text-gray-500">
              State: {tableInfo.state} | {data.length} records
            </p>
          )}
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-sm shadow">
            <thead>
              <tr className="bg-gray-100">
                {schema.map((field) => (
                  <th
                    key={field.key}
                    className="border border-gray-300 px-3 py-2 text-left font-semibold text-gray-800"
                  >
                    <div>{field.displayName || field.key}</div>

                    {field.type !== "string" && (
                      <div className="text-[10px] font-normal text-gray-500">
                        {field.type}
                      </div>
                    )}
                  </th>
                ))}
              </tr>
            </thead>

            <tbody>
              {data.map((row, rowIndex) => (
                <tr
                  key={rowIndex}
                  className={rowIndex % 2 === 0 ? "bg-white" : "bg-gray-50"}
                >
                  {schema.map((field) => (
                    <td
                      key={field.key}
                      className="border border-gray-300 px-3 py-2 text-gray-800"
                    >
                      {String(row[field.key] || "")}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    );
  };

  return (
    <div ref={containerRef} className="h-full w-full">
      {visualization && visualization.isPending ? (
        <div className="text-sm text-gray-600">Loading...</div>
      ) : (
        <div>
          <h2 className="mb-5 border-b-2 border-blue-500 pb-2.5 text-2xl font-bold text-gray-900">
            Geographic Data Tables
          </h2>

          {Object.entries(tableDictionary).length === 0 ? (
            <div className="text-sm text-gray-600">No tables available</div>
          ) : (
            Object.entries(tableDictionary).map(([tableId, tableData]) =>
              renderTable(tableId, tableData)
            )
          )}
        </div>
      )}
    </div>
  );
};
