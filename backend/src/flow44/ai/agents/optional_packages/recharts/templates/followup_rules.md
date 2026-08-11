### recharts — charts
- recharts is already installed — add or edit charts with it rather than hand-rolling SVG.
- Match the chart pattern already in the file: reuse its ResponsiveContainer wrapper and numeric height rather than introducing a second layout approach.
- Give any new series a dataKey that exists on the objects already passed as `data`, and set its color with stroke/fill props.
