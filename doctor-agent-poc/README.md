
# Doctor Agent PoC (Bilingual EN/ZH)

A minimal FastAPI backend that turns a disease or specialty query into:
- A short triage note (non-diagnostic, plain-language).
- A filtered doctor list with specialty, languages, accepted insurances, appointment options, and sources.
- Bilingual output via `lang=en|zh`.

> This is an offline demo using static sample data. No scraping or LLM calls yet.

## 1) Run locally

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload
```

Open Swagger UI: http://127.0.0.1:8000/docs

## 2) Example queries

### Disease (maps to specialties)
```
GET /search/doctors?q=arrhythmia&city=San%20Francisco&state=CA&language=Chinese&lang=en
```

### Specialty directly
```
GET /search/doctors?q=cardiology&city=San%20Francisco&state=CA&insurance=BCBS&lang=zh
```

### Free text (name/org)
```
GET /search/doctors?q=Wei%20Chen&lang=en
```

## 3) Data files
- `data/mapping.json` — disease→specialty mapping (EN/ZH synonyms)
- `data/doctors.json` — sample doctors with insurance & appointment fields

## 4) Next steps
- Replace static data with a real store (Postgres + pgvector/Elasticsearch).
- Add crawlers/APIs for hospital sites + insurer directories.
- Add LLM-based retrieval/summary (RAG) with source snippets.
- Implement insurer alias canonicalization and confidence scores.
