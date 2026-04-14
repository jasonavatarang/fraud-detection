# fraud-detection

# BackStory
I was hacked through my robhinhood brokerage account by someone with an ip adress in russia with an iphone 15 pro. I had my account froze, spent hours on call wiht robhinhood support, gone through multiple protocols to unrestrict my account. I missed out on possble opportunity cost/profit, emtionally restless wiht how safe my account really is and the unoterhox protocls needed to secure my funds. This is an attempt to solve and create a system to help prevent this.

# Description
## Possible features

* ingests account acitivy logs
* process them with PySpark
* computes a risk score
* stores resutls in Postgres
* exposes alerts thorugh FastAPI
* possibly add kafk, ml anomaly detection, dashboard

## what system should detect
* login from new IP
* login from new location
* password reset followed by withdrawal
* multiple failed logins
* unusual transaction amount
* device change before trade/transfer
* rapid sequence of sensitive actions

# Core Stack
* Python
* PySpark (reads raw events and computes suspciious patterns) --> user_risk_summary, alert_events
* PostgreSQL
* FastAPI
* Docer Compose
## thinking about
* kafka
* react
* redis
* kubernetes
* apache spark
* hadoop

# data models
  | Events.csv     | Description |
| ----------- | ----------- |
| event_id     |      |
| user_id  |      |
| event_type  |  login_sucess, login_failed, password_reset, trade, withdrawal, mfa_disabled, profile_change|
| timestamp | ||
|ip_address| ||
|location| ||
|device_id| ||
|amount| ||
|status| ||

# feature logic ideas
## Rule 1
More than 3 failed logins within 1 hour: high risk
## Rule 2
Password reset followed by withdrawal within 30 minutes: critical risk
## Rule 3
MFA disabled before profile change or withdrawal: critical risk
## Rule 4
Login from a new location and a new device: medium/high risk
## Rule 5
Withdrawal over threshold: medium risk (higher if combined with new device/location)

