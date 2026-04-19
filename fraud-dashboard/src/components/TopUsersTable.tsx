import type { RiskUser } from "../types";

interface TopUsersTableProps {
  users: RiskUser[];
}

export default function TopUsersTable({ users }: TopUsersTableProps) {
  if (!users.length) return <p>No users found.</p>;

  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>User</th>
            <th>Risk Score</th>
            <th>Risk Level</th>
            <th>Failed Logins</th>
            <th>Total Amount</th>
          </tr>
        </thead>
        <tbody>
          {users.map((user, idx) => (
            <tr key={`${user.user_id}-${idx}`}>
              <td>{user.user_id}</td>
              <td>{user.risk_score}</td>
              <td>{user.risk_level}</td>
              <td>{user.failed_login_count}</td>
              <td>{user.total_amount}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}