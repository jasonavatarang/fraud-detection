import type { RiskUser } from "../types";

interface AlertsTableProps {
  alerts: RiskUser[];
}

export default function AlertsTable({ alerts }: AlertsTableProps) {
  if (!alerts.length) return <p>No active alerts.</p>;

  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>User</th>
            <th>Risk Score</th>
            <th>Risk Level</th>
            <th>Events</th>
            <th>Total Amount</th>
          </tr>
        </thead>
        <tbody>
          {alerts.map((alert, idx) => (
            <tr key={`${alert.user_id}-${idx}`}>
              <td>{alert.user_id}</td>
              <td>{alert.risk_score}</td>
              <td>{alert.risk_level}</td>
              <td>{alert.event_count}</td>
              <td>{alert.total_amount}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}