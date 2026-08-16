### recharts — charts
Use recharts for dashboard charts (LineChart / BarChart / AreaChart / PieChart):
```tsx
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';
<ResponsiveContainer width="100%" height={300}>
  <LineChart data={rows}>
    <XAxis dataKey="date" /><YAxis /><Tooltip />
    <Line dataKey="value" stroke="#2563eb" />
  </LineChart>
</ResponsiveContainer>
```
Why: a chart with no height renders blank — always wrap it in ResponsiveContainer with a numeric height.
Why: data is an array of objects whose keys match each dataKey; transform data-source rows into that shape first.
Why: set series colors with stroke/fill string props — SVG ignores Tailwind classes (Tailwind still styles the surrounding card).
Use recharts only for charts; for a single KPI prefer plain text with Tailwind.
