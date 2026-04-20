export interface OverviewStats {
  total_users: number;
  total_events: number;
  alerted_users: number;
  critical_users: number;
  avg_risk_score: number;
}

export interface RiskUser {
  user_id: string;
  failed_login_count: number;
  has_password_reset: number;
  has_withdrawal: number;
  has_mfa_disabled: number;
  has_large_withdrawal: number;
  event_count: number;
  total_amount: number;
  high_velocity_event_flag: number;
  password_reset_then_withdrawal_flag: number;
  risk_score: number;
  risk_level: string;
}
interface RecentBurst {
  user_id: string;
  recent_event_count: number;
  recent_failed_login_count: number;
  has_recent_password_reset: number;
  has_recent_withdrawal: number;
  burst_score: number;
  burst_level: string;
}


export interface RiskDistributionItem {
  risk_level: string;
  count: number;
}

export interface RawEvent {
  event_id: string;
  user_id: string;
  event_type: string;
  timestamp: string;
  ip_address: string;
  location: string;
  device_id: string;
  amount: number;
  status: string;
}

export interface EventTypeSummary {
  event_type: string;
  count: number;
}