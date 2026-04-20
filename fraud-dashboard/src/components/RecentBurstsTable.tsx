
export default function RecentBurstsTable({ bursts }: RecentBurstsTableProps) {
  if (!bursts.length) return <p>No suspicious bursts detected.</p>;

  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>User</th>
            <th>Burst Score</th>
            <th>Level</th>
            <th>Events (5m)</th>
            <th>Failed Logins</th>
            <th>Password Reset</th>
            <th>Withdrawal</th>
          </tr>
        </thead>
        <tbody>
          {bursts.map((burst, idx) => (
            <tr key={`${burst.user_id}-${idx}`}>
              <td>{burst.user_id}</td>
              <td>{burst.burst_score}</td>
              <td>{burst.burst_level}</td>
              <td>{burst.recent_event_count}</td>
              <td>{burst.recent_failed_login_count}</td>
              <td>{burst.has_recent_password_reset ? "Yes" : "No"}</td>
              <td>{burst.has_recent_withdrawal ? "Yes" : "No"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}