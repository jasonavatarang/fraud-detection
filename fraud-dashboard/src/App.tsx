import { useEffect, useState } from "react";
import axios from "axios";
import StatCard from "./components/StatCard";
import RecentBurstsTable from "./components/RecentBurstsTable";
import TopUsersTable from "./components/TopUsersTable";
import RiskDistributionChart from "./components/RiskDistributionChart";
import DataTable from "./components/DataTable";
import type {
  OverviewStats,
  RiskUser,
  RiskDistributionItem,
  RawEvent,
  EventTypeSummary,
  RecentBurst
} from "./types";
import "./index.css";

const API_BASE = "http://localhost:8000";

export default function App() {
  const [overview, setOverview] = useState<OverviewStats | null>(null);
  const [alerts, setAlerts] = useState<RiskUser[]>([]);
  const [topUsers, setTopUsers] = useState<RiskUser[]>([]);
  const [riskDistribution, setRiskDistribution] = useState<RiskDistributionItem[]>([]);
  const [rawEvents, setRawEvents] = useState<RawEvent[]>([]);
  const [eventTypes, setEventTypes] = useState<EventTypeSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [recentBursts, setRecentBursts] = useState<any[]>([]);

  const fetchData = async () => {
    try {
      const [
  overviewRes,
  burstsRes,
  topUsersRes,
  riskDistributionRes,
  rawEventsRes,
  eventTypesRes,
] = await Promise.all([
  axios.get<OverviewStats[] | OverviewStats>(`${API_BASE}/stats/overview`),
  axios.get<RecentBurst[]>(`${API_BASE}/stats/recent-bursts`),
  axios.get<RiskUser[]>(`${API_BASE}/stats/top-users?limit=10`),
  axios.get<RiskDistributionItem[]>(`${API_BASE}/stats/risk-distribution`),
  axios.get<RawEvent[]>(`${API_BASE}/raw-events?limit=15`),
  axios.get<EventTypeSummary[]>(`${API_BASE}/stats/event-types`),
]);

      const overviewData = Array.isArray(overviewRes.data)
        ? overviewRes.data[0]
        : overviewRes.data;

      setOverview(overviewData ?? null);
      // setAlerts(alertsRes.data ?? []);
      setRecentBursts(burstsRes.data ?? []);
      setTopUsers(topUsersRes.data ?? []);
      setRiskDistribution(riskDistributionRes.data ?? []);
      setRawEvents(rawEventsRes.data ?? []);
      setEventTypes(eventTypesRes.data ?? []);
    } catch (error) {
      console.error("Failed to fetch dashboard data:", error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 5000);
    return () => clearInterval(interval);
  }, []);

  if (loading) {
    return (
      <div className="page">
        <h2>Loading dashboard...</h2>
      </div>
    );
  }

  return (
    <div className="page">
      <header className="header">
        <h1>Fraud Risk Platform Dashboard</h1>
        <p>Kafka + Spark Streaming + PostgreSQL + FastAPI + Redis</p>
      </header>

      <section className="stats-grid">
        <StatCard title="Total Users" value={overview?.total_users ?? 0} />
        <StatCard title="Total Events" value={overview?.total_events ?? 0} />
        <StatCard title="Alerted Users" value={overview?.alerted_users ?? 0} />
        <StatCard title="Critical Users" value={overview?.critical_users ?? 0} />
        <StatCard
          title="Avg Risk Score"
          value={Number(overview?.avg_risk_score ?? 0).toFixed(2)}
        />
      </section>

      <section className="grid two-col">
        <div className="card">
          <h2>Risk Distribution</h2>
          <RiskDistributionChart data={riskDistribution} />
        </div>

        <div className="card">
          <h2>Event Type Distribution</h2>
          <DataTable<EventTypeSummary>
            rows={eventTypes}
            columns={[
              { key: "event_type", label: "Event Type" },
              { key: "count", label: "Count" },
            ]}
          />
        </div>
      </section>

      <section className="grid two-col">
        <div className="card">
          <h2>Top Risky Users</h2>
          <TopUsersTable users={topUsers} />
        </div>

     <div className="card">
  <h2>Recent Suspicious Bursts</h2>
  <RecentBurstsTable bursts={recentBursts} />
</div>
      </section>

      <section className="card">
        <h2>Recent Raw Events</h2>
        <DataTable<RawEvent>
          rows={rawEvents}
          columns={[
            { key: "event_id", label: "Event ID" },
            { key: "user_id", label: "User ID" },
            { key: "event_type", label: "Event Type" },
            { key: "location", label: "Location" },
            { key: "amount", label: "Amount" },
            { key: "status", label: "Status" },
            { key: "timestamp", label: "Timestamp" },
          ]}
        />
      </section>
    </div>
  );
}