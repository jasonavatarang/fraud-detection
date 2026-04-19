interface StatCardProps {
  title: string;
  value: string | number;
}

export default function StatCard({ title, value }: StatCardProps) {
  return (
    <div className="stat-card">
      <div className="stat-title">{title}</div>
      <div className="stat-value">{value}</div>
    </div>
  );
}