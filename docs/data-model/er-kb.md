# Схема `kb` — ER-диаграмма

Файл создан скриптом `scripts/er_diagram.py` из применённых миграций (`make er-diagram`); вручную не править.

```mermaid
erDiagram
  article {
    uuid id PK
    text slug
    text title
    text body
    text source
    _text tags
    timestamp_with_time_zone updated_at
  }
  chunk {
    uuid id PK
    uuid article_id
    integer ord
    text text
    vector embedding
    tsvector tsv
  }
  article ||--o{ chunk : has
```
