import type {
  DashboardData,
  EventTypeSummary,
  RawEvent,
  RecentBurst,
  RiskDistributionItem,
  RiskUser,
} from "./types";

const DEMO_EVENTS: RawEvent[] = [
  {
    event_id: "demo-0001",
    user_id: "3001",
    event_type: "login_success",
    timestamp: "2026-01-01T12:00:00+00:00",
    ip_address: "203.0.113.11",
    location: "Miami",
    device_id: "device_a",
    amount: 0,
    status: "success",
  },
  {
    event_id: "demo-0002",
    user_id: "3002",
    event_type: "login_success",
    timestamp: "2026-01-01T12:00:05+00:00",
    ip_address: "203.0.113.22",
    location: "Austin",
    device_id: "device_c",
    amount: 0,
    status: "success",
  },
  {
    event_id: "demo-0003",
    user_id: "3001",
    event_type: "trade",
    timestamp: "2026-01-01T12:00:10+00:00",
    ip_address: "203.0.113.11",
    location: "Miami",
    device_id: "device_a",
    amount: 425.5,
    status: "success",
  },
  {
    event_id: "demo-1001",
    user_id: "3002",
    event_type: "login_failed",
    timestamp: "2026-01-01T12:01:00+00:00",
    ip_address: "203.0.113.201",
    location: "New York",
    device_id: "device_901",
    amount: 0,
    status: "failed",
  },
  {
    event_id: "demo-1002",
    user_id: "3002",
    event_type: "login_failed",
    timestamp: "2026-01-01T12:01:03+00:00",
    ip_address: "203.0.113.201",
    location: "New York",
    device_id: "device_901",
    amount: 0,
    status: "failed",
  },
  {
    event_id: "demo-1003",
    user_id: "3002",
    event_type: "password_reset",
    timestamp: "2026-01-01T12:01:06+00:00",
    ip_address: "203.0.113.201",
    location: "New York",
    device_id: "device_901",
    amount: 0,
    status: "success",
  },
  {
    event_id: "demo-1004",
    user_id: "3002",
    event_type: "withdrawal",
    timestamp: "2026-01-01T12:01:12+00:00",
    ip_address: "203.0.113.201",
    location: "New York",
    device_id: "device_901",
    amount: 9500,
    status: "success",
  },
  {
    event_id: "demo-2001",
    user_id: "3004",
    event_type: "mfa_disabled",
    timestamp: "2026-01-01T12:02:00+00:00",
    ip_address: "203.0.113.244",
    location: "Atlanta",
    device_id: "device_944",
    amount: 0,
    status: "success",
  },
  {
    event_id: "demo-2002",
    user_id: "3004",
    event_type: "password_reset",
    timestamp: "2026-01-01T12:02:05+00:00",
    ip_address: "203.0.113.244",
    location: "Atlanta",
    device_id: "device_944",
    amount: 0,
    status: "success",
  },
  {
    event_id: "demo-2003",
    user_id: "3004",
    event_type: "withdrawal",
    timestamp: "2026-01-01T12:02:10+00:00",
    ip_address: "203.0.113.244",
    location: "Atlanta",
    device_id: "device_944",
    amount: 12500,
    status: "success",
  },
  {
    event_id: "demo-3001",
    user_id: "3005",
    event_type: "trade",
    timestamp: "2026-01-01T12:02:20+00:00",
    ip_address: "203.0.113.55",
    location: "Seattle",
    device_id: "device_g",
    amount: 880.25,
    status: "success",
  },
  {
    event_id: "demo-3002",
    user_id: "3003",
    event_type: "withdrawal",
    timestamp: "2026-01-01T12:02:35+00:00",
    ip_address: "203.0.113.33",
    location: "Chicago",
    device_id: "device_d",
    amount: 1200,
    status: "success",
  },
];

const RISK_LEVELS = ["low", "medium", "high", "critical"];

function riskLevel(score: number): string {
  if (score >= 70) return "critical";
  if (score >= 40) return "high";
  if (score >= 20) return "medium";
  return "low";
}

function groupEventsByUser(events: RawEvent[]): Map<string, RawEvent[]> {
  const grouped = new Map<string, RawEvent[]>();
  for (const event of events) {
    const current = grouped.get(event.user_id) ?? [];
    current.push(event);
    grouped.set(event.user_id, current);
  }
  return grouped;
}

function buildUsers(events: RawEvent[]): RiskUser[] {
  return Array.from(groupEventsByUser(events).entries())
    .map(([userId, userEvents]) => {
      const failedLoginCount = userEvents.filter(
        (event) => event.event_type === "login_failed",
      ).length;
      const hasPasswordReset = Number(
        userEvents.some((event) => event.event_type === "password_reset"),
      );
      const hasWithdrawal = Number(
        userEvents.some((event) => event.event_type === "withdrawal"),
      );
      const hasMfaDisabled = Number(
        userEvents.some((event) => event.event_type === "mfa_disabled"),
      );
      const hasLargeWithdrawal = Number(
        userEvents.some(
          (event) => event.event_type === "withdrawal" && event.amount >= 5000,
        ),
      );
      const highVelocityEventFlag = Number(userEvents.length >= 5);
      const passwordResetThenWithdrawalFlag = Number(
        hasPasswordReset && hasWithdrawal,
      );
      const riskScore =
        failedLoginCount * 8
        + hasPasswordReset * 15
        + hasLargeWithdrawal * 25
        + hasMfaDisabled * 20
        + highVelocityEventFlag * 12
        + passwordResetThenWithdrawalFlag * 25;

      return {
        user_id: userId,
        failed_login_count: failedLoginCount,
        has_password_reset: hasPasswordReset,
        has_withdrawal: hasWithdrawal,
        has_mfa_disabled: hasMfaDisabled,
        has_large_withdrawal: hasLargeWithdrawal,
        event_count: userEvents.length,
        total_amount: userEvents.reduce((sum, event) => sum + event.amount, 0),
        high_velocity_event_flag: highVelocityEventFlag,
        password_reset_then_withdrawal_flag: passwordResetThenWithdrawalFlag,
        risk_score: riskScore,
        risk_level: riskLevel(riskScore),
      };
    })
    .toSorted((a, b) => b.risk_score - a.risk_score);
}

function buildRiskDistribution(users: RiskUser[]): RiskDistributionItem[] {
  return RISK_LEVELS.map((level) => ({
    risk_level: level,
    count: users.filter((user) => user.risk_level === level).length,
  })).filter((item) => item.count > 0);
}

function buildEventTypes(events: RawEvent[]): EventTypeSummary[] {
  const counts = new Map<string, number>();
  for (const event of events) {
    counts.set(event.event_type, (counts.get(event.event_type) ?? 0) + 1);
  }
  return Array.from(counts.entries())
    .map(([eventType, count]) => ({ event_type: eventType, count }))
    .toSorted((a, b) => b.count - a.count);
}

function buildRecentBursts(events: RawEvent[]): RecentBurst[] {
  return Array.from(groupEventsByUser(events).entries())
    .map(([userId, userEvents]) => {
      const recentFailedLoginCount = userEvents.filter(
        (event) => event.event_type === "login_failed",
      ).length;
      const hasRecentPasswordReset = Number(
        userEvents.some((event) => event.event_type === "password_reset"),
      );
      const hasRecentWithdrawal = Number(
        userEvents.some((event) => event.event_type === "withdrawal"),
      );
      const burstScore =
        userEvents.length * 5
        + recentFailedLoginCount * 10
        + hasRecentPasswordReset * 15
        + hasRecentWithdrawal * 15;
      const burstLevel = burstScore >= 35 ? "high" : burstScore >= 20 ? "medium" : "low";

      return {
        user_id: userId,
        recent_event_count: userEvents.length,
        recent_failed_login_count: recentFailedLoginCount,
        has_recent_password_reset: hasRecentPasswordReset,
        has_recent_withdrawal: hasRecentWithdrawal,
        burst_score: burstScore,
        burst_level: burstLevel,
      };
    })
    .filter((burst) => ["medium", "high"].includes(burst.burst_level))
    .toSorted((a, b) => b.burst_score - a.burst_score);
}

export function buildDemoDashboardData(tick: number): DashboardData {
  const visibleCount = Math.min(DEMO_EVENTS.length, 4 + (tick % (DEMO_EVENTS.length + 1)));
  const visibleEvents = DEMO_EVENTS.slice(0, visibleCount);
  const users = buildUsers(visibleEvents);
  const alertedUsers = users.filter((user) => ["high", "critical"].includes(user.risk_level));
  const totalEvents = visibleEvents.length;
  const totalRiskScore = users.reduce((sum, user) => sum + user.risk_score, 0);

  return {
    overview: {
      total_users: users.length,
      total_events: totalEvents,
      alerted_users: alertedUsers.length,
      critical_users: users.filter((user) => user.risk_level === "critical").length,
      avg_risk_score: users.length ? totalRiskScore / users.length : 0,
    },
    topUsers: users.slice(0, 10),
    riskDistribution: buildRiskDistribution(users),
    rawEvents: visibleEvents.toReversed().slice(0, 15),
    eventTypes: buildEventTypes(visibleEvents),
    recentBursts: buildRecentBursts(visibleEvents),
  };
}
