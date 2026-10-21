# Схема `docs` — ER-диаграмма

Файл создан скриптом `scripts/er_diagram.py` из применённых миграций (`make er-diagram`); вручную не править.

```mermaid
erDiagram
  extracted_field {
    bigint id PK
    uuid parse_job_id
    text name
    jsonb value
    numeric confidence
    integer page
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
  parse_job {
    uuid id PK
    uuid document_id
    uuid application_id
    text inn
    text type
    text storage_key
    text status
    text error
    timestamp_with_time_zone created_at
    timestamp_with_time_zone started_at
    timestamp_with_time_zone finished_at
  }
  processed_events {
    uuid event_id PK
    text topic
    timestamp_with_time_zone processed_at
  }
  validation_result {
    bigint id PK
    uuid parse_job_id
    text check_name
    boolean passed
    jsonb details
  }
  parse_job ||--o{ extracted_field : has
  parse_job ||--o{ validation_result : has
```
