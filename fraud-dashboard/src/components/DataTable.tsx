interface Column<T> {
  key: keyof T;
  label: string;
}

interface DataTableProps<T extends Record<string, unknown>> {
  rows: T[];
  columns: Column<T>[];
}

export default function DataTable<T extends Record<string, unknown>>({
  rows,
  columns,
}: DataTableProps<T>) {
  if (!rows.length) return <p>No data available.</p>;

  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            {columns.map((col) => (
              <th key={String(col.key)}>{col.label}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, idx) => (
            <tr key={idx}>
              {columns.map((col) => (
                <td key={String(col.key)}>
                  {String(row[col.key] ?? "")}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}