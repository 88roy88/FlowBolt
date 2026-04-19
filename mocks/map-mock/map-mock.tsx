import { useRef } from "react";

import {
  MAP_VISUALIZATION,
  type MapDataInstanceInfoDictionary,
  type MapVisualization,
  type MapVisualizationOptions,
  type TableDictionary,
} from "./types/visit-map.types"

interface Props {
  tableDictionary: TableDictionary;
  tableInfoDictionary: MapDataInstanceInfoDictionary;
  mapVisualizationOptions: MapVisualizationOptions;
  visualization?: MapVisualization & {
    isPending: boolean;
    template: string;
  };
  mapServiceRef?: React.MutableRefObject<any>;
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
        <div key={tableId} style={{ marginBottom: "20px" }}>
          <h3>No Data</h3>
        </div>
      );
    }

    if (tableData.failedParsing) {
      return (
        <div key={tableId} style={{ marginBottom: "20px" }}>
          <h3>Failed to parse data</h3>
        </div>
      );
    }

    const { data, schema } = tableData;

    const tableInfo =
      schema.length > 0 && schema[0]?.attributes?.dataInstanceId
        ? getTableInfo(schema[0].attributes.dataInstanceId)
        : null;

    return (
      <div key={tableId} style={{ marginBottom: "30px" }}>
        <div style={{ marginBottom: "10px" }}>
          <h3
            style={{
              margin: "0 0 5px 0",
              display: "flex",
              alignItems: "center",
              gap: "8px",
            }}
          >
            {tableInfo?.icon && <span>{tableInfo.icon}</span>}
            {tableInfo?.displayName || tableInfo?.name || tableId}
          </h3>

          {tableInfo && (
            <p style={{ margin: "0", color: "#888", fontSize: "11px" }}>
              State: {tableInfo.state} | {data.length} records
            </p>
          )}
        </div>

        <table
          style={{
            width: "100%",
            fontSize: "12px",
            boxShadow: "0 1px 3px rgba(0,0,0,0.1)",
          }}
        >
          <thead>
            <tr style={{ backgroundColor: "#f5f5f5" }}>
              {schema.map((field) => (
                <th
                  key={field.key}
                  style={{
                    border: "1px solid #ddd",
                    padding: "8px 12px",
                    textAlign: "left",
                    fontWeight: "600",
                    color: "#333",
                  }}
                >
                  <div>{field.displayName || field.key}</div>
                  {field.type !== "string" && (
                    <div
                      style={{
                        fontSize: "10px",
                        color: "#888",
                        fontWeight: "400",
                      }}
                    >
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
                style={{
                  backgroundColor: rowIndex % 2 === 0 ? "#fff" : "#f9f9f9",
                }}
              >
                {schema.map((field) => (
                  <td
                    key={field.key}
                    style={{
                      border: "1px solid #ddd",
                      padding: "8px 12px",
                      color: "#333",
                    }}
                  >
                    {String(row[field.key] || "")}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  };

  return (
    <div ref={containerRef} style={{ height: "100%", width: "100%" }}>
      {visualization && visualization.isPending ? (
        <div>Loading...</div>
      ) : (
        <div>
          <h2
            style={{
              marginBottom: "20px",
              borderBottom: "2px solid #3B82F6",
              paddingBottom: "10px",
            }}
          >
            Geographic Data Tables
          </h2>

          {Object.entries(tableDictionary).length === 0 ? (
            <div>No tables available</div>
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
