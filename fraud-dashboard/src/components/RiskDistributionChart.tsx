import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import type { RiskDistributionItem } from "../types";

interface RiskDistributionChartProps {
  data: RiskDistributionItem[];
}

export default function RiskDistributionChart({
  data,
}: RiskDistributionChartProps) {
  if (!data.length) return <p>No risk distribution data available.</p>;

  return (
    <div style={{ width: "100%", height: 300 }}>
      <ResponsiveContainer>
        <BarChart data={data}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="risk_level" />
          <YAxis />
          <Tooltip />
          <Bar dataKey="count" />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}