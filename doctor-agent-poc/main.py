
from fastapi import FastAPI, Query
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import json, os
from functools import lru_cache

app = FastAPI(title="Doctor Agent PoC (EN/ZH)", version="0.1.0")

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

# -----------------------
# Models
# -----------------------

class Insurance(BaseModel):
    payer_code: Optional[str] = None
    payer_name: Optional[str] = None
    plan: Optional[str] = None
    verified_at: Optional[str] = None
    source: Optional[str] = None

class Portal(BaseModel):
    type: Optional[str] = None
    url: Optional[str] = None

class Appointment(BaseModel):
    phone: Optional[str] = None
    online_portals: Optional[List[Portal]] = None
    walk_in: Optional[bool] = None

class Location(BaseModel):
    clinic_name: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip: Optional[str] = None

class Rating(BaseModel):
    source: Optional[str] = None
    rating: Optional[float] = None
    count: Optional[int] = None
    url: Optional[str] = None

class Source(BaseModel):
    source: Optional[str] = None
    url: Optional[str] = None
    crawled_at: Optional[str] = None

class Doctor(BaseModel):
    doctor_id: str
    full_name: str
    name_variants: Optional[List[str]] = None
    npi: Optional[str] = None
    licenses: Optional[List[Dict[str, Any]]] = None
    specialties: List[str] = Field(default_factory=list)
    conditions: Optional[List[str]] = None
    languages: Optional[List[str]] = None
    education: Optional[List[Dict[str, Any]]] = None
    experience: Optional[List[Dict[str, Any]]] = None
    insurances: Optional[List[Insurance]] = None
    appointment: Optional[Appointment] = None
    locations: Optional[List[Location]] = None
    ratings: Optional[List[Rating]] = None
    last_updated: Optional[str] = None
    sources: Optional[List[Source]] = None

# -----------------------
# Data loaders
# -----------------------

@lru_cache(maxsize=1)
def load_mapping() -> List[Dict[str, Any]]:
    with open(os.path.join(DATA_DIR, "mapping.json"), "r", encoding="utf-8") as f:
        return json.load(f)

@lru_cache(maxsize=1)
def load_doctors() -> List[Doctor]:
    with open(os.path.join(DATA_DIR, "doctors.json"), "r", encoding="utf-8") as f:
        raw = json.load(f)
    return [Doctor(**d) for d in raw]

def normalize(s: Optional[str]) -> str:
    if not s:
        return ""
    return s.strip().lower()

def detect_specialties_from_query(q: str) -> List[str]:
    qn = normalize(q)
    specs = set()
    # if q looks like a specialty directly
    for d in load_doctors():
        for sp in d.specialties:
            if normalize(sp) in qn:
                specs.add(sp)
    # otherwise use mapping by conditions/synonyms
    if not specs:
        for item in load_mapping():
            for cond in item.get("condition", []):
                if normalize(cond) and normalize(cond) in qn:
                    for sp in item.get("specialties", []):
                        specs.add(sp)
    return list(specs)

def doctor_matches_filters(d: Doctor, city: Optional[str], state: Optional[str],
                           insurance: Optional[str], language: Optional[str]) -> bool:
    if city:
        if not any(normalize(loc.city) == normalize(city) for loc in (d.locations or []) if loc and loc.city):
            return False
    if state:
        if not any(normalize(loc.state) == normalize(state) for loc in (d.locations or []) if loc and loc.state):
            return False
    if insurance:
        ins_norm = normalize(insurance)
        if not any(ins_norm in (normalize(i.payer_code) or "") or ins_norm in (normalize(i.payer_name) or "") for i in (d.insurances or [])):
            return False
    if language:
        if not any(normalize(language) in normalize(l) for l in (d.languages or [])):
            return False
    return True

def compute_score(d: Doctor, specs: List[str], q: str,
                  city: Optional[str], state: Optional[str], insurance: Optional[str], language: Optional[str]) -> float:
    score = 0.0
    qn = normalize(q)
    # Specialty match
    if specs:
        score += sum(1.0 for sp in d.specialties if sp in specs)
    # Name/org keyword presence
    if qn and (qn in normalize(d.full_name) or any(qn in normalize(v) for v in (d.name_variants or []))):
        score += 0.5
    # Filters
    if city and any(normalize(loc.city) == normalize(city) for loc in (d.locations or []) if loc and loc.city):
        score += 0.3
    if state and any(normalize(loc.state) == normalize(state) for loc in (d.locations or []) if loc and loc.state):
        score += 0.2
    if insurance and any(normalize(insurance) in ((normalize(i.payer_code) or "") + " " + (normalize(i.payer_name) or "")) for i in (d.insurances or [])):
        score += 0.4
    if language and any(normalize(language) in normalize(l) for l in (d.languages or [])):
        score += 0.2
    return score

def triage_note(lang: str, q: str, specs: List[str]) -> str:
    if lang == "zh":
        if specs:
            return f"根据您的查询“{q}”，建议首先考虑以下科室：{', '.join(specs)}。如出现胸痛、呼吸困难、晕厥等急症，请立刻拨打 911 或前往急诊。此信息仅供参考，不构成诊断。"
        else:
            return f"未能从“{q}”明确识别科室。建议提供具体症状或已知诊断，并在紧急情况下拨打 911。此信息仅供参考，不构成诊断。"
    # default en
    if specs:
        return f"For your query '{q}', consider the following specialties: {', '.join(specs)}. If you have red-flag symptoms (e.g., chest pain, shortness of breath, syncope), call 911 or go to the ER. This is not medical advice."
    else:
        return f"Could not confidently map '{q}' to a specialty. Please provide more detail on symptoms or a known diagnosis. For emergencies, call 911. This is not medical advice."

# -----------------------
# Schemas for responses
# -----------------------

class DoctorCard(BaseModel):
    doctor_id: str
    name: str
    specialties: List[str]
    languages: List[str] = []
    insurances: List[str] = []
    appointment: Dict[str, Any] = {}
    location: Dict[str, Any] = {}
    sources: List[Dict[str, Any]] = []
    score: float

class SearchResponse(BaseModel):
    analysis: Dict[str, Any]
    doctors: List[DoctorCard]

# -----------------------
# Endpoints
# -----------------------

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/search/doctors", response_model=SearchResponse)
def search_doctors(q: str = Query(..., description="Disease or specialty or free text"),
                   city: Optional[str] = None,
                   state: Optional[str] = None,
                   zip: Optional[str] = None,
                   insurance: Optional[str] = Query(None, description="payer_code or payer_name"),
                   language: Optional[str] = Query(None, description="Preferred spoken language (e.g., Chinese, English)"),
                   limit: int = 20,
                   offset: int = 0,
                   lang: str = Query("en", pattern="^(en|zh)$")):

    doctors = load_doctors()
    specs = detect_specialties_from_query(q)

    # Filter
    filtered = [d for d in doctors if doctor_matches_filters(d, city, state, insurance, language)]
    # If no filters applied and query is free text, include all for scoring; else use filtered list
    candidates = filtered if (city or state or insurance or language) else doctors

    # Score and sort
    scored = [
        (compute_score(d, specs, q, city, state, insurance, language), d)
        for d in candidates
        if (not specs) or any(sp in d.specialties for sp in specs) or (normalize(q) in (normalize(d.full_name)))
    ]
    scored.sort(key=lambda x: x[0], reverse=True)

    rows = []
    for score, d in scored[offset: offset + limit]:
        ins_list = []
        for ins in (d.insurances or []):
            parts = []
            if ins.payer_name: parts.append(ins.payer_name)
            if ins.plan: parts.append(f"({ins.plan})")
            ins_list.append(" ".join(parts) if parts else ins.payer_code or "")
        appt = {
            "phone": d.appointment.phone if d.appointment else None,
            "online_portals": [{"type": p.type, "url": p.url} for p in (d.appointment.online_portals or [])] if d.appointment else []
        }
        loc = {}
        if d.locations:
            loc = {"clinic_name": d.locations[0].clinic_name, "city": d.locations[0].city, "state": d.locations[0].state}
        rows.append(DoctorCard(
            doctor_id=d.doctor_id,
            name=f"{d.full_name}",
            specialties=d.specialties,
            languages=d.languages or [],
            insurances=ins_list,
            appointment=appt,
            location=loc,
            sources=[s.model_dump() for s in (d.sources or [])],
            score=round(score, 3)
        ))

    analysis = {
        "specialties": specs,
        "triage_note": triage_note(lang, q, specs)
    }
    return SearchResponse(analysis=analysis, doctors=rows)
