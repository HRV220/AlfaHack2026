# Схема `core` — ER-диаграмма

Файл создан скриптом `scripts/er_diagram.py` из применённых миграций (`make er-diagram`); вручную не править.

```mermaid
erDiagram
  applicant_role {
    uuid id PK
    uuid company_id
    text role
    boolean authority_confirmed
    timestamp_with_time_zone selected_at
  }
  application {
    uuid id PK
    uuid company_id
    uuid recommendation_id
    integer current_version
    text status
    text phone
    text email
    text status_text
    text next_step_text
    uuid decision_id
    timestamp_with_time_zone created_at
    timestamp_with_time_zone updated_at
    timestamp_with_time_zone submitted_at
  }
  application_version {
    uuid application_id PK
    integer version PK
    uuid company_id
    jsonb params
    jsonb company
    jsonb applicant_role
    jsonb clarification
    _text prefilled_fields
    jsonb checklist
    timestamp_with_time_zone created_at
  }
  chat_session {
    uuid id PK
    uuid company_id
    text stage
    uuid need_id
    uuid recommendation_id
    uuid application_id
    uuid insight_id
    boolean assistant_enabled
    timestamp_with_time_zone created_at
  }
  clarification_request {
    uuid id PK
    uuid application_id
    uuid company_id
    text type
    text document_type
    text text
    text status
    text requested_by
    timestamp_with_time_zone created_at
    jsonb reply
  }
  company {
    uuid id PK
    text inn
    timestamp_with_time_zone created_at
  }
  consent {
    uuid application_id PK
    uuid company_id
    boolean given
    timestamp_with_time_zone given_at
  }
  contract {
    uuid application_id PK
    uuid company_id
    text product_code
    numeric amount
    integer term_months
    numeric rate
    numeric payment
    numeric overpayment
    jsonb schedule
    text disclaimer
    boolean signed
    timestamp_with_time_zone signed_at
    timestamp_with_time_zone generated_at
  }
  decision {
    uuid id PK
    uuid application_id
    integer application_version
    uuid company_id
    text outcome
    text stop_reason
    numeric pd_raw
    numeric pd
    text grade
    numeric amount_requested
    numeric amount_approved
    numeric rate
    integer term_months
    numeric payment
    jsonb reason_codes
    jsonb shap_top10
    jsonb features
    _text review_triggers
    uuid recommendation_id
    jsonb versions
    timestamp_with_time_zone decided_at
    text final_outcome
    jsonb underwriter
    jsonb clarifications
  }
  document {
    uuid id PK
    uuid application_id
    uuid company_id
    text type
    text filename
    text mime
    integer size_bytes
    text storage_key
    text status
    text reject_reason
    jsonb parse_result
    jsonb edits
    timestamp_with_time_zone uploaded_at
    timestamp_with_time_zone updated_at
  }
  escalation {
    uuid id PK
    uuid company_id
    text reason
    uuid session_id
    uuid application_id
    text summary
    text status
    timestamp_with_time_zone created_at
    text closed_comment
  }
  feed_impression {
    bigint id PK
    uuid company_id
    uuid feed_item_id
    jsonb reasons
    timestamp_with_time_zone shown_at
  }
  feed_item {
    uuid id PK
    text type
    text title
    text text
    date published_at
    boolean demo
    _text tags
  }
  insight {
    uuid id PK
    uuid company_id
    jsonb gap
    integer days_until
    uuid recommendation_id
    text status
    timestamp_with_time_zone created_at
  }
  message {
    uuid id PK
    uuid session_id
    uuid company_id
    text role
    text text
    uuid need_id
    uuid recommendation_id
    text question_id
    _uuid action_ids
    boolean blocked_by_guard
    timestamp_with_time_zone created_at
  }
  need {
    uuid id PK
    uuid company_id
    integer version
    text origin
    text text
    jsonb fields
    boolean non_target
    integer questions_asked
    numeric proposed_amount
    uuid insight_id
    timestamp_with_time_zone created_at
    timestamp_with_time_zone updated_at
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
  pending_action {
    uuid id PK
    uuid session_id
    uuid company_id
    text type
    text label
    jsonb payload
    text status
    timestamp_with_time_zone expires_at
  }
  processed_events {
    uuid event_id PK
    text topic
    timestamp_with_time_zone processed_at
  }
  recommendation {
    uuid id PK
    uuid company_id
    uuid need_id
    uuid previous_id
    text trigger
    jsonb need_snapshot
    text profile_version
    text weights_profile
    jsonb evaluations
    text best_product_code
    _text alternative_product_codes
    numeric proposed_amount
    jsonb versions
    integer latency_ms
    timestamp_with_time_zone created_at
  }
  registry_snapshot {
    text inn PK
    text kpp
    text ogrn
    text name
    text opf
    text manager_name
    text address
    text okved
    text industry_group
    text registry_status
    date registered_at
    date liquidated_at
    text origin
    timestamp_with_time_zone fetched_at
  }
  status_history {
    bigint id PK
    uuid application_id
    uuid company_id
    text from_status
    text to_status
    text actor
    text reason
    timestamp_with_time_zone created_at
  }
  company ||--o{ applicant_role : has
  company ||--o{ application : has
  recommendation ||--o{ application : has
  application ||--o{ application_version : has
  company ||--o{ application_version : has
  application ||--o{ chat_session : has
  company ||--o{ chat_session : has
  insight ||--o{ chat_session : has
  need ||--o{ chat_session : has
  recommendation ||--o{ chat_session : has
  application ||--o{ clarification_request : has
  company ||--o{ clarification_request : has
  application ||--o{ consent : has
  company ||--o{ consent : has
  application ||--o{ contract : has
  company ||--o{ contract : has
  application ||--o{ decision : has
  company ||--o{ decision : has
  recommendation ||--o{ decision : has
  application ||--o{ document : has
  company ||--o{ document : has
  application ||--o{ escalation : has
  chat_session ||--o{ escalation : has
  company ||--o{ escalation : has
  company ||--o{ feed_impression : has
  feed_item ||--o{ feed_impression : has
  company ||--o{ insight : has
  recommendation ||--o{ insight : has
  chat_session ||--o{ message : has
  company ||--o{ message : has
  need ||--o{ message : has
  recommendation ||--o{ message : has
  company ||--o{ need : has
  chat_session ||--o{ pending_action : has
  company ||--o{ pending_action : has
  company ||--o{ recommendation : has
  need ||--o{ recommendation : has
  recommendation ||--o{ recommendation : has
  application ||--o{ status_history : has
  company ||--o{ status_history : has
```
