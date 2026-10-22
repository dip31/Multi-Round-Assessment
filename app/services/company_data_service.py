"""
Phase 4A: Company Historical Data & Pattern Foundation service.

Responsibilities:
- CRUD for CompanyHistoricalData (manual, file-upload, and pre-seeded records)
- Robust multi-format document extraction (PDF, DOCX, CSV, XLSX, JSON)
- Topic taxonomy and equivalence normalization
- Multi-source evidence combination, evidence count, and confidence level
- EDI5 pre-seeded benchmark fallback
- TPO pattern review & approval
"""

import csv
import io
import json
import logging
import os
import re
import zipfile
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.company_data import (
    CompanyHistoricalData,
    CompanyPattern,
    SUPPORTED_FILE_TYPES,
)
from app.schemas.company_data import CompanyHistoricalDataCreate
from app.services.topic_taxonomy import (
    TOPIC_TAXONOMY,
    extract_topics_from_text,
    get_topic_category,
    normalize_topic,
)
from app.services.edi5_benchmark_seeds import (
    EDI5_BENCHMARKS,
    benchmark_role_compatible,
    list_available_benchmarks,
    seed_edi5_fallback_data,
)

logger = logging.getLogger(__name__)

HISTORICAL_UPLOAD_DIR = os.path.join(os.getcwd(), "uploads", "company_historical")
os.makedirs(HISTORICAL_UPLOAD_DIR, exist_ok=True)


# ── Helpers ───────────────────────────────────────────────────────────

def _normalize_key(company_name: str, target_role: str) -> tuple[str, str]:
    """Normalize company + role key for consistent lookups."""
    return company_name.strip(), target_role.strip()


_NAMED_ROUND_KEYWORDS = {
    "aptitude": ["aptitude", "written test", "screening test", "online assessment", "online test", "quants", "mcq test", "national qualifier"],
    "coding": ["coding", "programming", "dsa", "code test", "code challenge", "hackathon", "lab test", "machine coding", "hands-on coding"],
    "technical_interview": ["technical interview", "tech interview", "tech round", "system design"],
    "hr_interview": ["hr round", "hr interview", "behavioural", "behavioral", "managerial round", "personal interview", "culture fit"],
}


def _detect_round_heading(line_l: str) -> Optional[str]:
    """Detect an explicit round/stage section heading on a text line.

    Only headings that NAME a round are treated as evidence of that round.
    An explicit round name written into the heading wins over a numbered
    sequence (e.g. ``Round 2: Technical Interview`` maps to
    ``technical_interview``). A bare numbered marker such as ``Round 2``
    with no round name is NOT evidence of any round and yields ``None`` —
    numbered positions must never auto-inject aptitude/coding/etc. into
    historical rounds. Returns ``None`` when the line is not a heading.
    """
    line_l = (line_l or "").lower().strip()
    if not line_l:
        return None
    numbered_match = re.search(r'\b(?:round|stage|phase|level|step)\s*(1|2|3|4|first|second|third|fourth|i{1,3}|iv)\b', line_l)
    heading_marker = bool(re.search(r'\b(?:round|stage|phase|level|step)\b', line_l))
    explicit = next(
        (
            round_key
            for round_key, keywords in _NAMED_ROUND_KEYWORDS.items()
            if any(keyword in line_l for keyword in keywords)
        ),
        None,
    )
    if numbered_match and explicit:
        return explicit
    if explicit and heading_marker:
        return explicit
    return None


def _taxonomy_round_for_topic(canonical_topic: str) -> Optional[str]:
    """Taxonomy-defined assessment round for a topic, without the generic funnel.

    ``get_default_round_for_topic`` returns ``coding`` for topics that are not
    present in the canonical taxonomy. Evidence-based round attribution must
    never funnel unknown topics into the coding round, so this helper returns
    ``None`` unless the topic is actually known to the taxonomy.
    """
    info = TOPIC_TAXONOMY.get(canonical_topic)
    if not info:
        return None
    return info.get("default_round", "coding")


# Contextual enrichment of ALREADY-DETECTED rounds from the same company
# document. When a normalized document topic belongs (by taxonomy) to a round
# the document did NOT contain, that topic is "orphaned" for this document. A
# detected round whose assessment context matches the topic's category may
# enrich from it. Constraints:
# - the topic MUST be present in the same document (never taxonomy/role defaults),
# - the topic's own taxonomy round MUST NOT be among the detected rounds (we
#   never steal a topic away from a round the document actually has),
# - only category-compatible topics enrich (no unrelated leakage).
# This enriches existing rounds; it NEVER invents or removes rounds.
_ORPHAN_TOPIC_CATEGORIES: Dict[str, Set[str]] = {
    "coding": {
        "Core CS",
        "Programming Languages",
        "Data Engineering & Cloud",
        "AI & Data Science",
    },
    "technical_interview": {
        "Core CS",
        "Programming Languages",
        "Data Engineering & Cloud",
        "AI & Data Science",
    },
    "aptitude": {"Aptitude"},
    "hr_interview": {"Behavioral"},
}


def _contextual_round_topics(
    current: List[str],
    round_type: str,
    detected_rounds: List[str],
    doc_topics: List[str],
    max_topics: int = 5,
) -> List[str]:
    """Fill an existing round's topics from the SAME document's evidence.

    ``current`` topics are preserved first (round-scoped / taxonomy-attributed
    evidence), then eligible orphaned topics are appended in evidence-frequency
    order up to ``max_topics``. See ``_ORPHAN_TOPIC_CATEGORIES`` for the rules.
    """
    picked = [str(t) for t in (current or [])]
    seen = {t.casefold() for t in picked}
    allowed = _ORPHAN_TOPIC_CATEGORIES.get(round_type)
    if not allowed:
        return picked
    for topic in doc_topics:
        if len(picked) >= max_topics:
            break
        if topic.casefold() in seen:
            continue
        if _taxonomy_round_for_topic(topic) in detected_rounds:
            continue
        if get_topic_category(topic) in allowed:
            picked.append(topic)
            seen.add(topic.casefold())
    return picked


def _extract_docx_text(file_bytes: bytes) -> str:
    """Extract raw text from a .docx file paragraph-by-paragraph without external dependencies."""
    try:
        with zipfile.ZipFile(io.BytesIO(file_bytes)) as z:
            if "word/document.xml" in z.namelist():
                xml_content = z.read("word/document.xml")
                tree = ET.fromstring(xml_content)
                paras = []
                for p in tree.iter():
                    if p.tag.endswith("}p"):
                        p_text = "".join(node.text for node in p.iter() if node.text and node.tag.endswith("}t"))
                        if p_text.strip():
                            paras.append(p_text.strip())
                if paras:
                    return "\n".join(paras)
                # Fallback to all text nodes
                texts = [node.text for node in tree.iter() if node.text and node.tag.endswith("}t")]
                return "\n".join(texts)
    except Exception as e:
        logger.warning(f"DOCX extraction warning: {e}")
    return ""


def _extract_xlsx_text(file_bytes: bytes) -> str:
    """Extract raw text strings from a .xlsx spreadsheet without external dependencies."""
    try:
        lines: List[str] = []
        with zipfile.ZipFile(io.BytesIO(file_bytes)) as z:
            if "xl/sharedStrings.xml" in z.namelist():
                xml_content = z.read("xl/sharedStrings.xml")
                tree = ET.fromstring(xml_content)
                for si in tree.iter():
                    if si.tag.endswith("}si"):
                        t = "".join(node.text for node in si.iter() if node.text and node.tag.endswith("}t"))
                        if t.strip():
                            lines.append(t.strip())
        return "\n".join(lines)
    except Exception as e:
        logger.warning(f"XLSX extraction warning: {e}")
    return ""


# ── Historical Data CRUD ──────────────────────────────────────────────

def add_manual_historical_data(
    db: Session,
    payload: CompanyHistoricalDataCreate,
    created_by_id: int,
) -> CompanyHistoricalData:
    """Add a manually-entered historical drive record with normalized topics."""
    company, role = _normalize_key(payload.company_name, payload.target_role)

    raw_data = dict(payload.raw_data or {})
    # Normalize topics list if provided
    if "topics" in raw_data and isinstance(raw_data["topics"], list):
        normed_topics = []
        for t in raw_data["topics"]:
            nt = normalize_topic(str(t))
            if nt and nt not in normed_topics:
                normed_topics.append(nt)
        raw_data["topics"] = normed_topics

    item = CompanyHistoricalData(
        company_name=company,
        target_role=role,
        label=payload.label,
        source_type="manual",
        raw_data=raw_data,
        created_by_id=created_by_id,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def add_file_historical_data(
    db: Session,
    company_name: str,
    target_role: str,
    label: str,
    file_bytes: bytes,
    original_filename: str,
    created_by_id: int,
) -> CompanyHistoricalData:
    """Store an uploaded file and extract structured assessment characteristics."""
    import uuid as _uuid

    company, role = _normalize_key(company_name, target_role)
    ext = os.path.splitext(original_filename)[-1].lower().lstrip(".")

    if ext not in SUPPORTED_FILE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Unsupported file type '.{ext}'. "
                f"Supported: {', '.join('.' + t for t in SUPPORTED_FILE_TYPES)}"
            ),
        )

    file_size = len(file_bytes)
    if file_size > 20 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File size exceeds 20 MB limit.",
        )

    unique_name = f"{created_by_id}_{_uuid.uuid4().hex[:8]}_{original_filename}"
    file_path = os.path.join(HISTORICAL_UPLOAD_DIR, unique_name)
    with open(file_path, "wb") as f:
        f.write(file_bytes)

    raw_data = _extract_from_file(file_bytes, ext, original_filename)

    item = CompanyHistoricalData(
        company_name=company,
        target_role=role,
        label=label or original_filename,
        source_type="file_upload",
        file_name=original_filename,
        file_path=file_path,
        file_size=file_size,
        raw_data=raw_data,
        created_by_id=created_by_id,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def _extract_from_file(file_bytes: bytes, ext: str, filename: str) -> Dict[str, Any]:
    """Extract structured data from uploaded file using taxonomy and rule-based patterns."""
    raw_data: Dict[str, Any] = {"source_file": filename, "raw_text": ""}

    if ext == "json":
        try:
            parsed = json.loads(file_bytes.decode("utf-8", errors="replace"))
            if isinstance(parsed, dict):
                raw_data.update(parsed)
            elif isinstance(parsed, list):
                raw_data["entries"] = parsed
            # Normalize topics if present
            if "topics" in raw_data and isinstance(raw_data["topics"], list):
                raw_data["topics"] = list(dict.fromkeys(normalize_topic(str(t)) for t in raw_data["topics"] if t))
        except Exception as e:
            logger.warning(f"JSON parse failed for {filename}: {e}")
            raw_data["parse_error"] = str(e)

    elif ext == "csv":
        try:
            text = file_bytes.decode("utf-8", errors="replace")
            reader = csv.DictReader(io.StringIO(text))
            rows = list(reader)
            raw_data["csv_rows"] = rows
            raw_data["csv_headers"] = reader.fieldnames or []
            raw_data.update(_normalize_csv_rows(rows))
        except Exception as e:
            logger.warning(f"CSV parse failed for {filename}: {e}")
            raw_data["parse_error"] = str(e)

    elif ext == "pdf":
        try:
            import fitz  # PyMuPDF
            doc = fitz.open(stream=file_bytes, filetype="pdf")
            text = ""
            for page_num in range(len(doc)):
                text += doc[page_num].get_text() + "\n"
            doc.close()
            raw_data["raw_text"] = text
            raw_data.update(_extract_from_text(text))
        except Exception as e:
            logger.warning(f"PDF extraction failed for {filename}: {e}")
            raw_data["parse_error"] = str(e)

    elif ext == "docx":
        text = _extract_docx_text(file_bytes)
        raw_data["raw_text"] = text
        raw_data.update(_extract_from_text(text))

    elif ext == "xlsx":
        text = _extract_xlsx_text(file_bytes)
        raw_data["raw_text"] = text
        raw_data.update(_extract_from_text(text))

    return raw_data


def _normalize_csv_rows(rows: List[Dict]) -> Dict[str, Any]:
    """Extract and normalize assessment fields from tabular CSV rows."""
    result: Dict[str, Any] = {}
    if not rows:
        return result

    def _norm(s: str) -> str:
        return (s or "").lower().strip().replace(" ", "_")

    rounds_seen: List[str] = []
    topics_seen: List[str] = []
    years_seen: List[int] = []
    round_patterns: Dict[str, Any] = {}
    difficulties_seen: List[str] = []
    question_types_seen: List[str] = []

    for row in rows:
        normed = {_norm(k): str(v).strip() for k, v in row.items() if v is not None}

        # Check for round column or row representing a round
        round_val = (
            normed.get("round") or normed.get("round_name") or normed.get("rounds") or
            normed.get("stage") or normed.get("phase") or normed.get("assessment_round")
        )
        current_round_key = None
        if round_val:
            for r in round_val.replace(";", ",").split(","):
                r_clean = r.strip().lower().replace(" ", "_")
                if "aptitude" in r_clean or "written" in r_clean or "screening" in r_clean:
                    current_round_key = "aptitude"
                elif "coding" in r_clean or "code" in r_clean or "programming" in r_clean:
                    current_round_key = "coding"
                elif "tech" in r_clean or "design" in r_clean:
                    current_round_key = "technical_interview"
                elif "hr" in r_clean or "behav" in r_clean or "cultural" in r_clean:
                    current_round_key = "hr_interview"
                elif r_clean:
                    current_round_key = r_clean
                if current_round_key and current_round_key not in rounds_seen:
                    rounds_seen.append(current_round_key)

        # Check for topics / skills
        topics_val = (
            normed.get("topics") or normed.get("topic") or normed.get("skills") or
            normed.get("skill") or normed.get("syllabus") or normed.get("concepts") or
            normed.get("focus_areas") or normed.get("subtopic") or normed.get("category")
        )
        row_topics = []
        if topics_val:
            for t in topics_val.replace(";", ",").split(","):
                canon = normalize_topic(t)
                if canon:
                    topics_seen.append(canon)
                    row_topics.append(canon)

        # Year
        year_val = normed.get("year") or normed.get("batch")
        if year_val:
            try:
                y = int(re.search(r'\d{4}', str(year_val)).group())
                if 2015 <= y <= 2030:
                    years_seen.append(y)
            except Exception:
                pass

        # Difficulty
        diff_val = normed.get("difficulty") or normed.get("level") or normed.get("complexity")
        diff_row_value = None
        if diff_val:
            d_lower = diff_val.lower().strip()
            if any(w in d_lower for w in ["hard", "complex", "difficult"]):
                diff_row_value = "hard"
            elif any(w in d_lower for w in ["easy", "basic", "simple"]):
                diff_row_value = "easy"
            elif any(w in d_lower for w in ["medium", "moderate"]):
                diff_row_value = "medium"
            if diff_row_value:
                difficulties_seen.append(diff_row_value)

        # Question type
        qtype_val = normed.get("question_type") or normed.get("question_types") or normed.get("type") or normed.get("format")
        if qtype_val:
            for qt in qtype_val.replace(";", ",").split(","):
                q_clean = qt.strip()
                if "mcq" in q_clean.lower() or "multiple choice" in q_clean.lower():
                    question_types_seen.append("MCQ")
                elif "coding" in q_clean.lower() or "problem" in q_clean.lower():
                    question_types_seen.append("Coding")
                elif "system design" in q_clean.lower():
                    question_types_seen.append("System Design")
                elif "behavioral" in q_clean.lower() or "hr" in q_clean.lower():
                    question_types_seen.append("Behavioral")
                elif q_clean:
                    question_types_seen.append(q_clean.title())

        # Construct round-level details if row represents a round
        if current_round_key:
            rp = round_patterns.setdefault(current_round_key, {})
            dur = normed.get("duration") or normed.get("duration_minutes") or normed.get("time") or normed.get("time_limit")
            q_cnt = normed.get("questions") or normed.get("question_count") or normed.get("problem_count") or normed.get("tasks")
            if dur:
                try:
                    rp["duration_minutes"] = int(re.search(r'\d+', str(dur)).group())
                except Exception:
                    pass
            if q_cnt:
                try:
                    rp["question_count"] = int(re.search(r'\d+', str(q_cnt)).group())
                except Exception:
                    pass
            if diff_row_value:
                rp["difficulty"] = diff_row_value
            if row_topics:
                existing_f = rp.setdefault("focus_areas", [])
                for rt in row_topics:
                    if rt not in existing_f:
                        existing_f.append(rt)

    if rounds_seen:
        result["rounds"] = list(dict.fromkeys(rounds_seen))
    if topics_seen:
        result["topics"] = list(dict.fromkeys(topics_seen))
    if years_seen:
        result["year"] = max(years_seen)
    if difficulties_seen:
        result["difficulty"] = Counter(difficulties_seen).most_common(1)[0][0]
    if question_types_seen:
        result["question_types"] = list(dict.fromkeys(question_types_seen))
    if round_patterns:
        result["round_patterns"] = round_patterns

    return result


def _extract_from_text(text: str) -> Dict[str, Any]:
    """Deep text extraction: scans taxonomy, round blocks, durations, questions, and difficulties."""
    result: Dict[str, Any] = {}
    if not text:
        return result

    text_lower = text.lower()

    # ── 1. Taxonomy Topics Extraction ─────────────────────────────────
    extracted_taxonomy = extract_topics_from_text(text)
    topics_list = [canonical for canonical, _ in extracted_taxonomy]

    # Explicit skill/topic lines (e.g. "Topics Covered: Docker, Kubernetes, SQL, Microservices")
    explicit_patterns = [
        r'(?:topics?(?:\s+covered|\s+tested)?|technical\s+skills?|key\s+skills?|syllabus|concepts?|focus\s*areas?|key\s*topics?)[:\s–-]+([^\n\r]+)',
    ]
    for pattern in explicit_patterns:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            raw_line = match.group(1)
            # Split on commas, bullets, semicolons, or pipes
            chunks = re.split(r'[,;•\*\-/|]', raw_line)
            for chunk in chunks:
                cleaned_item = chunk.strip()
                if cleaned_item and len(cleaned_item) > 1:
                    normed = normalize_topic(cleaned_item)
                    if normed and normed not in topics_list:
                        topics_list.append(normed)

    if topics_list:
        result["topics"] = topics_list

    # ── 2. Rounds Extraction ──────────────────────────────────────────
    ROUND_KEYWORDS = {
        "aptitude": [
            "aptitude", "quantitative", "logical reasoning", "verbal", "analytical", "quants",
            "online assessment", "online test", "written test", "screening test", "mcq test", "national qualifier"
        ],
        "coding": [
            "coding", "programming", "algorithm", "data structure", "dsa", "hands-on coding",
            "coding round", "coding challenge", "hackathon", "lab test"
        ],
        "technical_interview": [
            "technical interview", "tech interview", "system design", "tech round", "machine coding",
            "technical round 1", "technical round 2", "tech discussion"
        ],
        "hr_interview": [
            "hr interview", "hr round", "behavioural", "behavioral", "culture fit",
            "managerial round", "personal interview", "final interview"
        ],
    }
    detected_rounds = []
    round_order = ["aptitude", "coding", "technical_interview", "hr_interview"]
    for round_key in round_order:
        keywords = ROUND_KEYWORDS[round_key]
        if any(kw in text_lower for kw in keywords):
            detected_rounds.append(round_key)

    if detected_rounds:
        result["rounds"] = detected_rounds

    # ── 3. Question Formats & Types ───────────────────────────────────
    detected_qtypes = []
    if any(k in text_lower for k in ["mcq", "multiple choice", "objective", "quants"]):
        detected_qtypes.append("MCQ")
    if any(k in text_lower for k in ["coding problem", "code test", "programming problem", "dsa problem", "coding", "hands-on"]):
        detected_qtypes.append("Coding")
    if any(k in text_lower for k in ["system design", "architecture", "hld", "lld"]):
        detected_qtypes.append("System Design")
    if any(k in text_lower for k in ["behavioral", "hr", "situational", "leadership"]):
        detected_qtypes.append("Behavioral")
    if any(k in text_lower for k in ["live coding", "whiteboard", "pair programming"]):
        detected_qtypes.append("Live Coding")
    if any(k in text_lower for k in ["subjective", "theory", "essay", "short answer"]):
        detected_qtypes.append("Subjective / Theory")
    if any(k in text_lower for k in ["puzzle", "puzzles", "brain teaser"]):
        detected_qtypes.append("Puzzles")

    if detected_qtypes:
        result["question_types"] = detected_qtypes

    # ── 4. Difficulty Extraction ──────────────────────────────────────
    explicit_diff_match = re.search(r'\b(?:difficulty(?:\s*level)?[:\s\-–]+(easy|medium|hard|moderate|challenging|basic))\b', text_lower)
    if explicit_diff_match:
        val = explicit_diff_match.group(1)
        if val in ("hard", "challenging"):
            result["difficulty"] = "hard"
        elif val in ("medium", "moderate"):
            result["difficulty"] = "medium"
        elif val in ("easy", "basic"):
            result["difficulty"] = "easy"
    else:
        # Check using word boundaries
        if re.search(r'\b(?:hard|complex|very difficult)\b', text_lower):
            result["difficulty"] = "hard"
        elif re.search(r'\b(?:medium|moderate|average)\b', text_lower):
            result["difficulty"] = "medium"
        elif re.search(r'\b(?:easy|basic|simple)\b', text_lower):
            result["difficulty"] = "easy"

    # ── 5. Duration & Question Count Extraction ───────────────────────
    # Overall duration
    dur_match = re.search(r'(\d+)\s*(?:minutes|mins|min\b)', text_lower)
    if dur_match:
        try:
            result["duration_minutes"] = int(dur_match.group(1))
        except Exception:
            pass

    # Overall question count
    qc_match = re.search(r'(\d+)\s*(?:questions|mcqs|problems|tasks)\b', text_lower)
    if qc_match:
        try:
            result["question_count"] = int(qc_match.group(1))
        except Exception:
            pass

    # ── 6. Section & Round Patterns Extraction ────────────────────────
    # Scan for explicit round sections (e.g. "Round 1: Aptitude (60 mins,
    # 30 questions)...", "Stage 2 — Coding", "Technical Interview (45 mins)").
    # Topics are attributed to a round ONLY when they appear inside that
    # round's own section; global mentions are kept at the document level.
    round_patterns: Dict[str, Any] = {}
    lines = text.splitlines()
    current_round: Optional[str] = None
    section_lines: List[str] = []

    def _flush_section() -> None:
        if current_round is None:
            return
        section_text = " ".join(section_lines)
        section_topics = [canonical for canonical, _ in extract_topics_from_text(section_text)]
        rp = round_patterns.setdefault(current_round, {})
        if section_topics:
            rp["focus_areas"] = list(dict.fromkeys([*(rp.get("focus_areas") or []), *section_topics]))

    for line in lines:
        line_l = line.lower().strip()
        if not line_l:
            continue
        detected = _detect_round_heading(line_l)
        if detected and detected != current_round:
            _flush_section()
            current_round = detected
            section_lines = [line_l]
        elif detected == current_round:
            section_lines.append(line_l)
        elif current_round:
            section_lines.append(line_l)

        if current_round:
            rp = round_patterns.setdefault(current_round, {})
            # Look for duration on this line (first occurrence wins)
            d_m = re.search(r'(\d+)\s*(?:minutes|mins|min\b)', line_l)
            if d_m and "duration_minutes" not in rp:
                rp["duration_minutes"] = int(d_m.group(1))
            # Look for question count on this line (first occurrence wins)
            q_m = re.search(r'(\d+)\s*(?:questions|mcqs|problems|tasks)\b', line_l)
            if q_m and "question_count" not in rp:
                rp["question_count"] = int(q_m.group(1))
            # Explicit per-round difficulty statement (e.g. "Difficulty: Hard")
            diff_m = re.search(r'\b(?:difficulty(?:\s*level)?|level|complexity)[:\s\-–]+(easy|medium|hard|moderate|challenging|basic)\b', line_l)
            if diff_m and "difficulty" not in rp:
                diff_clean = diff_m.group(1)
                if diff_clean in ("hard", "challenging"):
                    rp["difficulty"] = "hard"
                elif diff_clean in ("medium", "moderate"):
                    rp["difficulty"] = "medium"
                else:
                    rp["difficulty"] = "easy"

    _flush_section()

    if round_patterns:
        result["round_patterns"] = round_patterns

    # ── 7. Year Extraction ────────────────────────────────────────────
    year_match = re.search(r'\b(201[5-9]|202[0-9]|2030)\b', text)
    if year_match:
        result["year"] = int(year_match.group(1))

    return result


def list_historical_data(
    db: Session,
    company_name: Optional[str] = None,
    target_role: Optional[str] = None,
) -> List[CompanyHistoricalData]:
    """List historical data records, optionally filtered by company and/or role."""
    q = db.query(CompanyHistoricalData).order_by(CompanyHistoricalData.created_at.desc())
    if company_name:
        q = q.filter(CompanyHistoricalData.company_name.ilike(f"%{company_name.strip()}%"))
    if target_role:
        q = q.filter(CompanyHistoricalData.target_role.ilike(f"%{target_role.strip()}%"))
    return q.all()


def get_historical_data(db: Session, item_id: int) -> CompanyHistoricalData:
    item = db.query(CompanyHistoricalData).filter(CompanyHistoricalData.id == item_id).first()
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Historical data item {item_id} not found.",
        )
    return item


def delete_historical_data(db: Session, item_id: int) -> None:
    item = get_historical_data(db, item_id)
    if item.file_path and os.path.exists(item.file_path):
        try:
            os.remove(item.file_path)
        except OSError as e:
            logger.warning(f"Could not delete file {item.file_path}: {e}")
    db.delete(item)
    db.commit()


# ── Pattern Extraction & Aggregation ──────────────────────────────────

def _historical_source_compatible(source: CompanyHistoricalData, target_role: str) -> bool:
    """Reject legacy pre-seeded rows whose benchmark belongs to another role."""
    if source.source_type != "pre_seeded":
        return True  # The source was explicitly filed under this exact company/role key.
    data = source.raw_data or {}
    provenance = data.get("source_provenance") or {}
    if provenance.get("explicit_fallback_requested"):
        return True
    reference = data.get("benchmark_reference", "")
    if not reference:
        return False
    benchmark_name = reference.rsplit(" - ", 1)[0].strip()
    benchmark = next((item for item in EDI5_BENCHMARKS if item["company_name"].lower() == benchmark_name.lower()), None)
    return bool(benchmark and benchmark_role_compatible(target_role, benchmark))


def _apply_round_configuration(
    pattern_data: Dict[str, Any],
    round_configuration: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Persist explicit TPO round configuration into the pattern's round_patterns.

    Only rounds present in the aggregated evidence (``assessment_rounds``) may be
    configured; explicit TPO values take precedence over evidence averages.
    Supplied ``focus_areas`` must be topics from the aggregated evidence whose
    ``typical_round`` is exactly this round, OR topics already documented for
    this round (contextually enriched from the same document) — no aliases, no
    random cross-round topics.
    A round is fully configured once question count, duration and difficulty are
    all provided AND evidence-backed round topics exist (evidence-derived or
    TPO-selected); otherwise it stays flagged ``requires_tpo_configuration`` so
    blueprint generation rejects it instead of silently injecting defaults.
    """
    VALID_ROUNDS = {"aptitude", "coding", "technical_interview", "hr_interview"}
    assessment_rounds = [
        str(r).lower().strip().replace(" ", "_")
        for r in pattern_data.get("assessment_rounds", [])
    ]
    round_patterns = pattern_data.setdefault("round_patterns", {})
    for cfg in round_configuration:
        rtype = str(cfg.get("round_type", "")).strip().lower()
        if rtype not in VALID_ROUNDS:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Round type '{cfg.get('round_type')}' is not a supported assessment round.",
            )
        if rtype not in assessment_rounds:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"Round '{rtype}' is not present in this pattern's historical "
                    "evidence; only evidence-supported rounds can be configured."
                ),
            )
        rp = round_patterns.setdefault(rtype, {})
        missing = [
            field
            for field in ("question_count", "duration_minutes", "difficulty_distribution")
            if cfg.get(field) is None
        ]
        if missing:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"Round configuration for '{rtype}' is incomplete; missing "
                    f"{', '.join(missing)}. Question count, duration and difficulty "
                    "distribution are all required before saving."
                ),
            )
        rp["question_count"] = int(cfg["question_count"])
        rp["duration_minutes"] = int(cfg["duration_minutes"])
        rp["difficulty_distribution"] = dict(cfg["difficulty_distribution"])

        # TPO-selected topics: only topics present in the aggregated evidence
        # are accepted. A topic is valid for this round when its taxonomy
        # typical_round is EXACTLY this round, OR when it is already part of
        # this round's document-derived focus (e.g. Software Engineering &
        # Design Patterns contextually enriched into Coding from the same
        # document). Brand-new cross-round topics that the document never
        # attached to this round are still rejected — no aliases, no random
        # borrowing. Supplying an empty list (or omitting the field) leaves any
        # evidence-derived focus_areas untouched.
        supplied_focus = cfg.get("focus_areas")
        if supplied_focus:
            topic_frequency = pattern_data.get("topic_frequency", []) or []
            by_name = {
                str(item.get("topic", "")).casefold(): item
                for item in topic_frequency
                if isinstance(item, dict) and str(item.get("topic", "")).strip()
            }
            current_focus = {str(f).casefold() for f in (rp.get("focus_areas") or [])}
            selected: List[str] = []
            invalid: List[str] = []
            for topic in supplied_focus:
                item = by_name.get(str(topic).casefold())
                if not item or (
                    item.get("typical_round") != rtype
                    and str(topic).casefold() not in current_focus
                ):
                    invalid.append(str(topic).strip())
                    continue
                selected.append(item["topic"])
            if invalid:
                quoted = ", ".join(f"'{t}'" for t in sorted(set(invalid)))
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=(
                        f"Topics {quoted} cannot be selected for round "
                        f"'{rtype}': they are not evidence-backed topics for this round. Only topics "
                        "whose typical_round is exactly this round are selectable."
                    ),
                )
            rp["focus_areas"] = list(dict.fromkeys(selected))

        has_topics = bool(rp.get("focus_areas"))
        has_config = (
            "question_count" in rp
            and "duration_minutes" in rp
            and "difficulty_distribution" in rp
        )
        # A TPO-added round carries no historical topic evidence to select from;
        # once numerics are set it is complete (blueprint uses canonical default
        # topics). Evidence rounds still require an explicit topic selection.
        if has_config and (has_topics or rp.get("round_origin") == "tpo_added"):
            rp.pop("requires_tpo_configuration", None)
        else:
            rp["requires_tpo_configuration"] = True
    return pattern_data


def _apply_added_rounds(
    pattern_data: Dict[str, Any],
    added_rounds: List[str],
) -> Dict[str, Any]:
    """Explicitly add a round the TPO chose that was NOT present in the evidence.

    Historical extraction never invents rounds, so an assessment round a TPO
    wants but that has no historical evidence can only enter the pattern
    through this explicit ``added_rounds`` action. Added rounds are appended
    to ``assessment_rounds`` in the order given and tagged
    ``round_origin: "tpo_added"`` (evidence-derived rounds stay
    ``round_origin: "evidence"``). The round stays flagged
    ``requires_tpo_configuration`` until a full configuration (question count,
    duration, difficulty AND at least one topic) is persisted — exactly like an
    evidence round with missing data. Supplying an already-present round is a
    no-op and never downgrades an evidence round.
    """
    VALID_ROUNDS = {"aptitude", "coding", "technical_interview", "hr_interview"}
    assessment_rounds = [
        str(r).lower().strip().replace(" ", "_")
        for r in pattern_data.get("assessment_rounds", [])
    ]
    round_patterns = pattern_data.setdefault("round_patterns", {})
    for raw_round in added_rounds:
        rtype = str(raw_round).lower().strip().replace(" ", "_")
        if rtype not in VALID_ROUNDS:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Round type '{raw_round}' is not a supported assessment round.",
            )
        if rtype in assessment_rounds:
            continue
        assessment_rounds.append(rtype)
        rp = round_patterns.setdefault(rtype, {})
        if rp.get("round_origin") != "evidence":
            rp["round_origin"] = "tpo_added"
        rp["requires_tpo_configuration"] = True
        rp["sources_count"] = 0
    pattern_data["assessment_rounds"] = assessment_rounds
    return pattern_data


def _normalize_round_key(value: Any) -> str:
    return str(value).strip().lower().replace(" ", "_")


def _round_is_fully_configured(round_pattern: Dict[str, Any]) -> bool:
    has_config = (
        "question_count" in round_pattern
        and "duration_minutes" in round_pattern
        and "difficulty_distribution" in round_pattern
    )
    if not has_config:
        return False
    # An evidence round can only be completed by TPO-selected evidence topics.
    # A TPO-added round has no historical topic evidence to select from, so once
    # its numeric settings are complete it is valid: the blueprint derives the
    # canonical default topics for that round type (marked as defaults).
    return bool(round_pattern.get("focus_areas")) or round_pattern.get("round_origin") == "tpo_added"


def _refresh_round_config_flag(round_pattern: Dict[str, Any]) -> None:
    if _round_is_fully_configured(round_pattern):
        round_pattern.pop("requires_tpo_configuration", None)
    else:
        round_pattern["requires_tpo_configuration"] = True


def _apply_deselected_rounds(
    pattern_data: Dict[str, Any],
    deselected_rounds: List[str],
) -> Dict[str, Any]:
    """Remove explicitly deselected rounds from the effective pattern view.

    Deselection only affects the derived ``assessment_rounds`` / ``round_patterns``
    view; the underlying ``CompanyHistoricalData`` sources and the recorded
    ``evidence_rounds`` are never deleted. A round that is merely unspecified
    (absent from the TPO configuration) is left untouched and keeps its evidence
    default, so absence is never confused with an explicit deselection.
    """
    deselected = {_normalize_round_key(r) for r in (deselected_rounds or [])}
    if not deselected:
        return pattern_data
    assessment_rounds = [
        _normalize_round_key(r) for r in pattern_data.get("assessment_rounds", []) or []
    ]
    pattern_data["assessment_rounds"] = [r for r in assessment_rounds if r not in deselected]
    round_patterns = pattern_data.get("round_patterns", {}) or {}
    for rtype in deselected:
        round_patterns.pop(rtype, None)
    return pattern_data


def _restore_tpo_configuration(
    pattern_data: Dict[str, Any],
    prior_configuration: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """Re-apply a previously persisted TPO configuration to freshly extracted evidence.

    Recalculation rebuilds the pattern from the raw historical sources, which
    would otherwise erase any TPO-added rounds and TPO-edited round values. This
    restores the durable ``tpo_configuration`` block so repeated recalculation is
    stable (no dropped rounds, no dropped overrides).
    """
    if not isinstance(prior_configuration, dict):
        return pattern_data
    prior_rounds = prior_configuration.get("rounds")
    if not isinstance(prior_rounds, list) or not prior_rounds:
        return pattern_data

    round_patterns = pattern_data.setdefault("round_patterns", {})

    added = [
        _normalize_round_key(entry.get("round_type"))
        for entry in prior_rounds
        if entry.get("enabled") and entry.get("round_origin") == "tpo_added"
    ]
    added = [rtype for rtype in added if rtype]
    if added:
        pattern_data = _apply_added_rounds(pattern_data, added)
        round_patterns = pattern_data.setdefault("round_patterns", {})

    for entry in prior_rounds:
        if not entry.get("enabled"):
            continue
        rtype = _normalize_round_key(entry.get("round_type"))
        round_pattern = round_patterns.get(rtype)
        if round_pattern is None:
            continue
        for field in ("question_count", "duration_minutes", "difficulty_distribution"):
            if entry.get(field) is not None:
                round_pattern[field] = entry[field]
        focus_areas = entry.get("focus_areas")
        if focus_areas:
            round_pattern["focus_areas"] = list(dict.fromkeys(str(t) for t in focus_areas))
        _refresh_round_config_flag(round_pattern)
    return pattern_data


def _resolve_tpo_configuration(
    prior_configuration: Optional[Dict[str, Any]],
    pattern_data: Dict[str, Any],
    round_configuration: Optional[List[Dict[str, Any]]],
    added_rounds: Optional[List[str]],
    deselected_rounds: List[str],
) -> Dict[str, Any]:
    """Build the durable TPO configuration block persisted inside ``pattern_data``.

    Each entry records an explicit TPO decision: ``enabled: true`` (explicitly
    selected/added), ``enabled: false`` (explicitly deselected) or no entry at
    all (unspecified -> evidence default). Entries are keyed by round type so the
    merge never depends on array position, display labels or UI-only state, and
    repeated recalculation never duplicates rounds.
    """
    entries: Dict[str, Dict[str, Any]] = {}
    round_patterns = pattern_data.get("round_patterns", {}) or {}
    evidence_set = {
        _normalize_round_key(r) for r in pattern_data.get("evidence_rounds", []) or []
    }

    def capture(rtype: str, enabled: bool, origin: Optional[str] = None) -> None:
        round_pattern = round_patterns.get(rtype, {}) or {}
        entry = entries.get(rtype) or {"round_type": rtype}
        entry["enabled"] = enabled
        if origin:
            entry["round_origin"] = origin
        elif not entry.get("round_origin"):
            entry["round_origin"] = (
                "tpo_added" if round_pattern.get("round_origin") == "tpo_added" else "evidence"
            )
        for field in (
            "question_count",
            "duration_minutes",
            "difficulty_distribution",
            "focus_areas",
        ):
            value = round_pattern.get(field)
            if value is not None:
                entry[field] = value
        entries[rtype] = entry

    prior_rounds = (prior_configuration or {}).get("rounds") or []
    for entry in prior_rounds:
        rtype = _normalize_round_key(entry.get("round_type"))
        if rtype and entry.get("enabled") and entry.get("round_origin") == "tpo_added":
            capture(rtype, True, "tpo_added")
    for entry in prior_rounds:
        rtype = _normalize_round_key(entry.get("round_type"))
        if rtype and entry.get("enabled") and entry.get("round_origin") != "tpo_added":
            capture(rtype, True, entry.get("round_origin") or "evidence")
    for raw in added_rounds or []:
        rtype = _normalize_round_key(raw)
        if rtype:
            capture(rtype, True, "tpo_added")
    for cfg in round_configuration or []:
        rtype = _normalize_round_key(cfg.get("round_type"))
        if rtype:
            capture(rtype, True, "tpo_added" if rtype not in evidence_set else "evidence")
    for raw in deselected_rounds or []:
        rtype = _normalize_round_key(raw)
        if not rtype:
            continue
        entry = entries.get(rtype) or {"round_type": rtype}
        round_pattern = round_patterns.get(rtype, {}) or {}
        for field in (
            "question_count",
            "duration_minutes",
            "difficulty_distribution",
            "focus_areas",
        ):
            if field not in entry and round_pattern.get(field) is not None:
                entry[field] = round_pattern[field]
        entry["enabled"] = False
        if not entry.get("round_origin"):
            entry["round_origin"] = (
                "tpo_added" if round_pattern.get("round_origin") == "tpo_added" else "evidence"
            )
        entries[rtype] = entry

    return {
        "version": 1,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "rounds": list(entries.values()),
    }


def generate_pattern(
    db: Session,
    company_name: str,
    target_role: str,
    created_by_id: int,
    use_fallback: bool = False,
    round_configuration: Optional[List[Dict[str, Any]]] = None,
    added_rounds: Optional[List[str]] = None,
    deselected_rounds: Optional[List[str]] = None,
) -> CompanyPattern:
    """Aggregate all historical sources for company+role into a verified structured pattern.

    - Combines multi-source evidence.
    - Normalizes equivalent topics.
    - Computes evidence count and confidence level.
    - Supports EDI5 pre-seeded benchmark fallback when requested and sources are empty.
    """
    company, role = _normalize_key(company_name, target_role)

    existing = (
        db.query(CompanyPattern)
        .filter(
            func.lower(CompanyPattern.company_name) == company.lower(),
            func.lower(CompanyPattern.target_role) == role.lower(),
        )
        .first()
    )
    prior_configuration = (existing.pattern_data or {}).get("tpo_configuration") if existing else None

    sources = (
        db.query(CompanyHistoricalData)
        .filter(
            func.lower(CompanyHistoricalData.company_name) == company.lower(),
            func.lower(CompanyHistoricalData.target_role) == role.lower(),
        )
        .all()
    )

    # Legacy pre-seeded rows may have been created by the old role-blind lookup.
    # Keep their records intact, but exclude them from a pattern unless their
    # benchmark role is compatible or the fallback was explicitly requested.
    compatible_sources = [src for src in sources if _historical_source_compatible(src, role)]
    incompatible_count = len(sources) - len(compatible_sources)
    sources = compatible_sources
    is_fallback = False
    if not sources:
        if use_fallback:
            # Seed fallback benchmark data and reload sources
            logger.info(f"Using EDI5 benchmark fallback for {company} - {role}")
            fallback_source = seed_edi5_fallback_data(db, company, role, created_by_id)
            sources = [fallback_source]
            is_fallback = True
        else:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "INSUFFICIENT_ROLE_SPECIFIC_EVIDENCE",
                    "message": "No role-specific historical evidence is available for this company/role.",
                    "selection_status": "no_compatible_evidence_found",
                    "company_name": company,
                    "target_role": role,
                    "excluded_incompatible_sources": incompatible_count,
                },
            )

    pattern_data = _extract_pattern_from_sources(sources)
    # Record the pure evidence rounds (pre TPO add/deselect) so consumers can
    # always tell historical evidence apart from explicit TPO choices.
    pattern_data["evidence_rounds"] = [
        str(r).strip().lower().replace(" ", "_")
        for r in pattern_data.get("assessment_rounds", []) or []
    ]

    # Re-apply any durable TPO configuration (rounds the TPO added, values the
    # TPO edited, rounds the TPO deselected) so recalculation never erases it.
    pattern_data = _restore_tpo_configuration(pattern_data, prior_configuration)

    if added_rounds:
        pattern_data = _apply_added_rounds(pattern_data, added_rounds)
    if round_configuration:
        pattern_data = _apply_round_configuration(pattern_data, round_configuration)

    # Effective deselection set: a round the TPO explicitly deselected stays
    # deselected across recalculation unless the current request explicitly
    # (re)selects it; a request deselection always wins.
    request_selected = {
        _normalize_round_key(r) for r in (added_rounds or [])
    } | {
        _normalize_round_key(cfg.get("round_type")) for cfg in (round_configuration or [])
    }
    effective_deselected: List[str] = []
    for entry in (prior_configuration or {}).get("rounds", []) or []:
        rtype = _normalize_round_key(entry.get("round_type"))
        if rtype and not entry.get("enabled") and rtype not in request_selected:
            effective_deselected.append(rtype)
    for raw in deselected_rounds or []:
        rtype = _normalize_round_key(raw)
        if rtype and rtype not in effective_deselected:
            effective_deselected.append(rtype)

    # Persist the durable TPO configuration before removing deselected rounds
    # from the effective view (so a deselected round keeps its last known values).
    pattern_data["tpo_configuration"] = _resolve_tpo_configuration(
        prior_configuration,
        pattern_data,
        round_configuration,
        added_rounds,
        effective_deselected,
    )
    if effective_deselected:
        pattern_data = _apply_deselected_rounds(pattern_data, effective_deselected)

    empirical_sources = [src for src in sources if src.source_type != "pre_seeded"]
    preseeded_sources = [src for src in sources if src.source_type == "pre_seeded"]
    source_classification = (
        "company_specific_historical_evidence" if empirical_sources
        else ("generic_fallback" if any((src.raw_data or {}).get("source_provenance", {}).get("classification") == "generic_fallback" for src in preseeded_sources)
              else "pre_seeded_benchmark")
    )
    pattern_data["is_fallback"] = bool(preseeded_sources) and not empirical_sources
    pattern_data["source_provenance"] = {
        "classification": source_classification,
        "selection_status": "generic_fallback_found" if source_classification == "generic_fallback" else "role_compatible_evidence_found",
        "explicit_fallback_requested": any((src.raw_data or {}).get("source_provenance", {}).get("explicit_fallback_requested", False) for src in preseeded_sources),
        "empirical_source_count": len(empirical_sources),
        "pre_seeded_source_count": len(preseeded_sources),
        "excluded_incompatible_source_count": incompatible_count,
    }
    if preseeded_sources:
        pattern_data["source_provenance"]["benchmark_references"] = [
            (src.raw_data or {}).get("benchmark_reference") for src in preseeded_sources
        ]
    if not empirical_sources:
        pattern_data["confidence_level"] = "low (EDI5 benchmark fallback)"
        pattern_data["confidence_score"] = 0.40
        pattern_data["confidence_reasons"] = "Generated from explicitly selected pre-seeded benchmark data; this is not company-specific historical evidence."
    elif preseeded_sources:
        empirical_pattern = _extract_pattern_from_sources(empirical_sources)
        pattern_data["confidence_level"] = empirical_pattern["confidence_level"]
        pattern_data["confidence_score"] = empirical_pattern["confidence_score"]
        pattern_data["confidence_reasons"] = empirical_pattern["confidence_reasons"] + " Pre-seeded benchmark also contributed to the pattern."

    # Upsert: update existing or create new (``existing`` fetched up front so the
    # prior durable TPO configuration could be restored before aggregation).
    if existing:
        # Preserve review status if already approved and not fallback
        prev_data = existing.pattern_data or {}
        if prev_data.get("review_status") == "approved" and not is_fallback:
            pattern_data["review_status"] = "approved"
            pattern_data["reviewed_by"] = prev_data.get("reviewed_by")
            pattern_data["reviewed_at"] = prev_data.get("reviewed_at")

        existing.pattern_data = pattern_data
        existing.source_count = len(sources)
        existing.created_by_id = created_by_id
        db.commit()
        db.refresh(existing)
        return existing

    pattern = CompanyPattern(
        company_name=company,
        target_role=role,
        pattern_data=pattern_data,
        source_count=len(sources),
        created_by_id=created_by_id,
    )
    db.add(pattern)
    db.commit()
    db.refresh(pattern)
    return pattern


def _extract_pattern_from_sources(sources: List[CompanyHistoricalData]) -> Dict[str, Any]:
    """Aggregate multiple raw historical sources into a unified evidence-backed pattern."""
    total_sources = len(sources)
    all_rounds_seen: List[str] = []
    round_sources_map: Dict[str, Set[int]] = defaultdict(set)
    topic_sources_map: Dict[str, Set[int]] = defaultdict(set)
    topic_total_mentions: Dict[str, int] = defaultdict(int)
    qtype_sources_map: Dict[str, Set[int]] = defaultdict(set)
    difficulties_observed: List[str] = []
    round_difficulties: Dict[str, List[str]] = defaultdict(list)
    round_difficulty_distributions: Dict[str, List[Dict[str, float]]] = defaultdict(list)
    years_observed: List[int] = []
    round_durations: Dict[str, List[int]] = defaultdict(list)
    round_question_counts: Dict[str, List[int]] = defaultdict(list)
    round_focus_areas: Dict[str, Set[str]] = defaultdict(set)
    sources_summary: List[Dict[str, Any]] = []

    VALID_ROUNDS = {"aptitude", "coding", "technical_interview", "hr_interview"}
    VALID_DIFFICULTIES = {"easy", "medium", "hard"}

    total_evidence_points = 0

    for src in sources:
        data = src.raw_data or {}
        src_rounds_found = []
        src_topics_count = 0

        # ── 1. Rounds ─────────────────────────────────────────────────
        raw_rounds = data.get("rounds", [])
        if isinstance(raw_rounds, list):
            for r in raw_rounds:
                r_norm = str(r).lower().strip().replace(" ", "_")
                if r_norm in VALID_ROUNDS:
                    matched_round = r_norm
                elif "aptitude" in r_norm or "written" in r_norm or "screening" in r_norm:
                    matched_round = "aptitude"
                elif "coding" in r_norm or "code" in r_norm or "programming" in r_norm:
                    matched_round = "coding"
                elif "technical" in r_norm or "tech" in r_norm:
                    matched_round = "technical_interview"
                elif "hr" in r_norm or "behav" in r_norm:
                    matched_round = "hr_interview"
                else:
                    matched_round = None

                if matched_round:
                    all_rounds_seen.append(matched_round)
                    round_sources_map[matched_round].add(src.id)
                    src_rounds_found.append(matched_round)
                    total_evidence_points += 1

        # ── 2. Topics ─────────────────────────────────────────────────
        raw_topics = data.get("topics", [])
        if isinstance(raw_topics, list):
            for t in raw_topics:
                canon = normalize_topic(str(t))
                if canon:
                    topic_sources_map[canon].add(src.id)
                    topic_total_mentions[canon] += 1
                    src_topics_count += 1
                    total_evidence_points += 1

        # ── 3. Question types ─────────────────────────────────────────
        raw_qtypes = data.get("question_types", [])
        if isinstance(raw_qtypes, list):
            for qt in raw_qtypes:
                qt_str = str(qt).strip()
                if qt_str:
                    qtype_sources_map[qt_str].add(src.id)
                    total_evidence_points += 1

        # ── 4. Difficulty ─────────────────────────────────────────────
        raw_diff = str(data.get("difficulty", "")).lower().strip()
        if raw_diff in VALID_DIFFICULTIES:
            difficulties_observed.append(raw_diff)
            total_evidence_points += 1
            # Attribute the source-level difficulty to every round this
            # source actually evidences so per-round difficulty is explicit.
            for rnd in src_rounds_found:
                round_difficulties[rnd].append(raw_diff)

        # ── 5. Year ───────────────────────────────────────────────────
        year = data.get("year")
        if isinstance(year, int) and 2015 <= year <= 2030:
            years_observed.append(year)

        # ── 6. Round Patterns (Durations, Questions, Focus) ───────────
        round_data = data.get("round_patterns", {})
        if isinstance(round_data, dict):
            for rnd, rnd_info in round_data.items():
                if not isinstance(rnd_info, dict):
                    continue
                rnd_norm = str(rnd).lower().strip().replace(" ", "_")
                dur = rnd_info.get("duration_minutes") or rnd_info.get("duration")
                if isinstance(dur, (int, float)) and dur > 0:
                    round_durations[rnd_norm].append(int(dur))
                    total_evidence_points += 1
                cnt = rnd_info.get("question_count") or rnd_info.get("problem_count") or rnd_info.get("questions")
                if isinstance(cnt, (int, float)) and cnt > 0:
                    round_question_counts[rnd_norm].append(int(cnt))
                    total_evidence_points += 1
                focus = rnd_info.get("focus_areas") or rnd_info.get("topics")
                if isinstance(focus, list):
                    for f in focus:
                        canon_f = normalize_topic(str(f))
                        if canon_f:
                            round_focus_areas[rnd_norm].add(canon_f)
                rnd_diff = str(rnd_info.get("difficulty") or rnd_info.get("difficulty_level") or "").lower().strip()
                if rnd_diff in VALID_DIFFICULTIES:
                    round_difficulties[rnd_norm].append(rnd_diff)
                rnd_diff_dist = rnd_info.get("difficulty_distribution")
                if isinstance(rnd_diff_dist, dict) and set(rnd_diff_dist) == {"easy", "medium", "hard"}:
                    round_difficulty_distributions[rnd_norm].append(rnd_diff_dist)

        # A document-wide explicit duration/count is evidence for every round
        # the document listed when that round itself carried no per-round
        # number (e.g. "60 minutes / 25 questions" written once for the whole
        # process). This is explicit evidence, never an invented default.
        if src_rounds_found:
            doc_dur = data.get("duration_minutes")
            doc_qc = data.get("question_count")
            if isinstance(doc_dur, (int, float)) and doc_dur > 0:
                for rnd_ in src_rounds_found:
                    if not round_durations[rnd_]:
                        round_durations[rnd_].append(int(doc_dur))
            if isinstance(doc_qc, (int, float)) and doc_qc > 0:
                for rnd_ in src_rounds_found:
                    if not round_question_counts[rnd_]:
                        round_question_counts[rnd_].append(int(doc_qc))

        # Record source summary
        sources_summary.append({
            "id": src.id,
            "label": src.label,
            "source_type": src.source_type,
            "file_name": src.file_name,
            "year": data.get("year"),
            "rounds_found": list(dict.fromkeys(src_rounds_found)),
            "topics_count": src_topics_count,
        })

    # ── Aggregation & Sequence ────────────────────────────────────────
    round_order = ["aptitude", "coding", "technical_interview", "hr_interview"]
    # Include ONLY rounds explicitly seen in the historical evidence. A round
    # that was never detected (e.g. no keyword, no named heading) must not be
    # invented: no aptitude/coding/technical defaults are injected here.
    ordered_rounds = [r for r in round_order if len(round_sources_map[r]) > 0]

    # Topics ranked by source frequency first, then mention count
    sorted_topics = sorted(
        topic_sources_map.keys(),
        key=lambda t: (len(topic_sources_map[t]), topic_total_mentions[t]),
        reverse=True,
    )
    top_topics_dict = {t: topic_total_mentions[t] for t in sorted_topics[:25]}

    topic_frequency = [
        {
            "topic": t,
            "count": topic_total_mentions[t],
            "sources_count": len(topic_sources_map[t]),
            "frequency_pct": round((len(topic_sources_map[t]) / max(total_sources, 1)) * 100, 1),
            "category": get_topic_category(t),
            "typical_round": _taxonomy_round_for_topic(t),
        }
        for t in sorted_topics[:25]
    ]

    # Question types
    question_types = {
        qt: len(sources_set) for qt, sources_set in qtype_sources_map.items()
    }
    if not question_types:
        question_types = {"MCQ": 1, "Coding": 1}

    # Difficulty distribution
    diff_counts = Counter(difficulties_observed)
    total_diff_obs = max(sum(diff_counts.values()), 1)
    difficulty_dist = {
        d: round(diff_counts.get(d, 0) / total_diff_obs, 2)
        for d in ("easy", "medium", "hard")
    }
    avg_difficulty = diff_counts.most_common(1)[0][0] if diff_counts else "medium"

    round_patterns: Dict[str, Any] = {}
    for rnd in ordered_rounds:
        rp: Dict[str, Any] = {}
        requires_config = False

        # Duration: evidence average only; never silently default-filled.
        if rnd in round_durations and round_durations[rnd]:
            rp["avg_duration_minutes"] = round(sum(round_durations[rnd]) / len(round_durations[rnd]))
        else:
            requires_config = True

        # Question count: evidence average only; never silently default-filled.
        if rnd in round_question_counts and round_question_counts[rnd]:
            rp["avg_question_count"] = round(sum(round_question_counts[rnd]) / len(round_question_counts[rnd]))
        else:
            requires_config = True

        # Round-specific topics from DOCUMENT CONTEXT, in priority order:
        #   1. Round-scoped focus filtered to topics this round's taxonomy
        #      attributes to the round (topics explicitly written under the
        #      round heading).
        #   2. Taxonomy attribution of the document's global normalized topics.
        #   3. Contextual enrichment: orphaned topics from the SAME document
        #      (e.g. Software Engineering & Design Patterns / SQL & Querying
        #      whose taxonomy round was not detected) that fit this round's
        #      assessment context. Never defaults, never invented, never
        #      unrelated leakage. See ``_contextual_round_topics``.
        observed_f = [
            t for t in round_focus_areas[rnd] if _taxonomy_round_for_topic(t) == rnd
        ]
        if not observed_f:
            observed_f = [t for t in sorted_topics if _taxonomy_round_for_topic(t) == rnd][:4]
        observed_f = _contextual_round_topics(observed_f, rnd, ordered_rounds, sorted_topics)
        if observed_f:
            rp["focus_areas"] = observed_f[:5]
        else:
            requires_config = True

        # Per-round difficulty distribution from explicit observations only.
        rnd_diff_dist = None
        if round_difficulty_distributions[rnd]:
            dists = round_difficulty_distributions[rnd]
            rnd_diff_dist = {
                d: round(sum(dist.get(d, 0) for dist in dists) / len(dists), 2)
                for d in ("easy", "medium", "hard")
            }
        elif round_difficulties[rnd]:
            rnd_diff_counts = Counter(round_difficulties[rnd])
            rnd_total_obs = max(sum(rnd_diff_counts.values()), 1)
            rnd_diff_dist = {
                d: round(rnd_diff_counts.get(d, 0) / rnd_total_obs, 2)
                for d in ("easy", "medium", "hard")
            }
        if rnd_diff_dist:
            rp["difficulty_distribution"] = rnd_diff_dist
        else:
            requires_config = True

        if requires_config:
            rp["requires_tpo_configuration"] = True
        rp["round_origin"] = "evidence"
        rp["sources_count"] = len(round_sources_map[rnd])

        round_patterns[rnd] = rp

    # ── Confidence Level Calculation ──────────────────────────────────
    if total_sources >= 3 and total_evidence_points >= 8:
        confidence_level = "high"
        confidence_score = round(min(0.75 + (total_sources * 0.05) + (total_evidence_points * 0.01), 0.98), 2)
        confidence_reasons = (
            f"Strong evidence synthesized from {total_sources} verified sources "
            f"({total_evidence_points} total evidence data points observed)."
        )
    elif total_sources >= 2 or (total_sources == 1 and total_evidence_points >= 6):
        confidence_level = "medium"
        confidence_score = round(min(0.55 + (total_sources * 0.08) + (total_evidence_points * 0.01), 0.80), 2)
        confidence_reasons = (
            f"Moderate evidence synthesized from {total_sources} source(s) "
            f"({total_evidence_points} verified assessment attributes)."
        )
    else:
        confidence_level = "low"
        confidence_score = round(max(0.30, total_evidence_points * 0.08), 2)
        confidence_reasons = (
            f"Limited evidence ({total_sources} source, {total_evidence_points} datapoints). "
            f"Logging additional past drives or uploading format documents will enhance pattern reliability."
        )

    return {
        "assessment_rounds": ordered_rounds,
        "topics": top_topics_dict,
        "topic_frequency": topic_frequency,
        "question_types": question_types,
        "difficulty_distribution": difficulty_dist,
        "avg_difficulty": avg_difficulty,
        "round_patterns": round_patterns,
        "year_range": [min(years_observed), max(years_observed)] if years_observed else [],
        "source_count": total_sources,
        "evidence_count": total_evidence_points,
        "confidence_level": confidence_level,
        "confidence_score": confidence_score,
        "confidence_reasons": confidence_reasons,
        "sources_summary": sources_summary,
        "review_status": "pending_review",
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


# ── Pattern CRUD & Review ─────────────────────────────────────────────

def get_pattern(
    db: Session,
    company_name: str,
    target_role: str,
) -> CompanyPattern:
    company, role = _normalize_key(company_name, target_role)
    pattern = (
        db.query(CompanyPattern)
        .filter(
            func.lower(CompanyPattern.company_name) == company.lower(),
            func.lower(CompanyPattern.target_role) == role.lower(),
        )
        .first()
    )
    if not pattern:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"No pattern found for company='{company}', role='{role}'. "
                "Generate a pattern first via POST /tpo/company-data/pattern/generate."
            ),
        )
    return pattern


def list_patterns(db: Session) -> List[CompanyPattern]:
    return db.query(CompanyPattern).order_by(CompanyPattern.updated_at.desc()).all()


def review_pattern(
    db: Session,
    company_name: str,
    target_role: str,
    review_status: str,
    notes: Optional[str],
    reviewer_email: str,
) -> CompanyPattern:
    """TPO review and approval of the extracted structured pattern."""
    pattern = get_pattern(db, company_name, target_role)
    pdata = dict(pattern.pattern_data or {})
    pdata["review_status"] = review_status
    pdata["reviewed_by"] = reviewer_email
    pdata["reviewed_at"] = datetime.now(timezone.utc).isoformat()
    if notes:
        pdata["review_notes"] = notes.strip()

    pattern.pattern_data = pdata
    db.commit()
    db.refresh(pattern)
    return pattern
