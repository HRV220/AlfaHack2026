# Схема `ml` — ER-диаграмма

Файл создан скриптом `scripts/er_diagram.py` из применённых миграций (`make er-diagram`); вручную не править.

```mermaid
erDiagram
  cash_gap {
    uuid id PK
    uuid forecast_id
    text inn
    date date
    numeric probability
    numeric deficit
    numeric cushion
    date return_date_p50
    jsonb reasons
    boolean recurring_last_year
  }
  enriched_transaction {
    uuid transaction_id PK
    text inn
    date date
    numeric amount
    text direction
    text category
    numeric category_confidence
    text model_version
  }
  forecast {
    uuid id PK
    text inn
    integer horizon_days
    numeric cushion
    jsonb daily
    text model_version
    timestamp_with_time_zone generated_at
  }
  outbox {
    uuid id PK
    text topic
    text key
    jsonb payload
    timestamp_with_time_zone created_at
    timestamp_with_time_zone published_at
    integer attempts
  }
  processed_events {
    uuid event_id PK
    text topic
    timestamp_with_time_zone processed_at
  }
  profile_snapshot {
    uuid id PK
    text inn
    text version
    timestamp_with_time_zone as_of
    jsonb profile
    timestamp_with_time_zone created_at
  }
  recommendation_log {
    uuid id PK
    text inn
    uuid recommendation_id
    jsonb need
    jsonb result
    jsonb versions
    integer latency_ms
    timestamp_with_time_zone created_at
  }
  recurring_payment {
    uuid id PK
    text inn
    text counterparty
    text category
    integer period_days
    numeric amount
    date next_date
  }
  scoring_log {
    uuid id PK
    text inn
    uuid application_id
    integer application_version
    numeric pd_raw
    numeric pd
    text grade
    jsonb features
    jsonb shap_top10
    text model_version
    integer latency_ms
    timestamp_with_time_zone created_at
  }
  whatif_log {
    uuid id PK
    text inn
    uuid recommendation_id
    jsonb changes
    jsonb result
    integer latency_ms
    timestamp_with_time_zone created_at
  }
  forecast ||--o{ cash_gap : has
```
