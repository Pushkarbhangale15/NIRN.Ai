"""
build_embeddings.py — Clause-aware FAISS index builder for NIRN.Ai.

Replaces the old RecursiveCharacterTextSplitter with a structural parser
that extracts individual clauses from each GR and stores rich metadata
alongside each embedding.

Usage:
    python build_embeddings.py
"""

import os
import re
import sys
import json
import pickle
import argparse
import random
import numpy as np
import faiss
from pathlib import Path
from sentence_transformers import SentenceTransformer

# ---------------------------------------------------------------------------
# GR Structural Parser (mirrors the parser in backend/llm.py)
# ---------------------------------------------------------------------------

_HEADER_MARKERS_MR = [
    "महाराष्ट्र शासन", "शासन निर्णय क्रमांक", "मंत्रालय", "बांधकाम भवन",
    "दिनांक", "# Page 1", "Government of Maharashtra",
]
_HEADER_MARKERS_EN = [
    "Government of Maharashtra", "Government Resolution", "Mantralaya",
    "# Page 1", "Date:", "Hutatma Rajguru Chowk",
]
_READ_MARKERS = ["वाचा", "Read:-", "Read :-", "Reference:-", "संदर्भ"]
_BACKGROUND_MARKERS = ["प्रस्तावना", "Preamble", "Introduction:", "Background:"]
_FOOTER_MARKERS = [
    "प्रत", "Copy to", "By order", "सही/-", "(Signed)", "e-mail",
    "या शासन निर्णयाची सत्यप्रत", "This Government Resolution",
]

# Financial keywords for flagging
_FINANCIAL_TERMS = [
    "rs.", "rs ", "रु.", "रुपये", "budget", "grant", "अनुदान", "निधी",
    "crore", "lakh", "कोटी", "लक्ष", "funding", "expenditure",
]

# Authority keywords
_AUTHORITY_TERMS = [
    "collector", "commissioner", "secretary", "minister", "director",
    "जिल्हाधिकारी", "कलेक्टर", "आयुक्त", "सचिव", "मंत्री",
]

# Timeline keywords
_TIMELINE_TERMS = [
    "deadline", "days", "months", "financial year", "दिवस", "महिना",
    "मुदत", "quarterly", "monthly", "annual",
]


def _classify_section(text: str) -> str:
    """Classify a text section as header/read/background/operative/footer."""
    text_lower = text.lower()
    first_100 = text[:100]

    for m in _FOOTER_MARKERS:
        if m.lower() in text_lower:
            if len(text) < 200 or m.lower() in text_lower[:150]:
                return "footer"
    for m in _HEADER_MARKERS_MR + _HEADER_MARKERS_EN:
        if m in first_100:
            return "header"
    for m in _READ_MARKERS:
        if m in first_100:
            return "read"
    for m in _BACKGROUND_MARKERS:
        if m in first_100:
            return "background"
    return "operative"


def _extract_subject(text: str) -> str:
    """Try to extract the subject line from a GR."""
    # Marathi subject: "विषय :" or "विषय:-"
    match = re.search(r'विषय\s*[:\-]+\s*(.+?)(?:\n|$)', text)
    if match:
        return match.group(1).strip()[:200]
    # English subject: "Subject:" or "Sub:"
    match = re.search(r'(?:Subject|Sub)\s*[:\-]+\s*(.+?)(?:\n|$)', text, re.IGNORECASE)
    if match:
        return match.group(1).strip()[:200]
    return ""


def _extract_year(gr_id: str) -> int:
    """Extract year from GR ID (first 4 digits)."""
    match = re.match(r'(\d{4})', gr_id)
    if match:
        return int(match.group(1))
    return 0


def _extract_keywords(text: str) -> list:
    """Extract important keywords from clause text."""
    keywords = []
    text_lower = text.lower()
    keyword_patterns = [
        "approval", "sanction", "withdraw", "cancel", "amend", "supersede",
        "prohibit", "permit", "establish", "transfer", "appoint",
        "मान्यता", "मंजूर", "रद्द", "सुधारणा", "स्थापना", "नियुक्ती",
    ]
    for kw in keyword_patterns:
        if kw in text_lower:
            keywords.append(kw)
    return keywords[:10]


def _has_flag(text: str, terms: list) -> bool:
    """Check if text contains any of the given terms."""
    text_lower = text.lower()
    return any(t in text_lower for t in terms)


def parse_gr_into_clauses(text: str, gr_id: str, department: str, language: str) -> list:
    """
    Parse a single GR text into individual clause records with rich metadata.

    Only embeds operative clauses and background sections.
    Headers, read sections, footers, and signatures are stripped.
    """
    subject = _extract_subject(text)
    year = _extract_year(gr_id)

    # Split on numbered clauses
    raw_parts = re.split(
        r"\n\s*(?=(?:\d+|[\u0966-\u096F]+)[.)]\s)",
        text,
    )

    clauses = []
    clause_counter = 0

    for part in raw_parts:
        stripped = part.strip()
        if len(stripped) < 30:
            continue

        section_type = _classify_section(stripped)

        # Only embed operative clauses and background
        if section_type not in ("operative", "background"):
            continue

        # Extract clause number
        num_match = re.match(r'^(?:(\d+)|([\u0966-\u096F]+))[.)]\s', stripped)
        if num_match:
            clause_counter += 1
            if num_match.group(1):
                clause_num = int(num_match.group(1))
            else:
                dev_str = num_match.group(2)
                clause_num = int(''.join(str(ord(c) - 0x0966) for c in dev_str))
        else:
            clause_counter += 1
            clause_num = clause_counter

        clauses.append({
            "gr_id": gr_id,
            "department": department,
            "language": language,
            "chunk_id": clause_counter,
            "clause_number": clause_num,
            "clause_type": section_type,
            "subject": subject,
            "year": year,
            "financial_flag": _has_flag(stripped, _FINANCIAL_TERMS),
            "authority_flag": _has_flag(stripped, _AUTHORITY_TERMS),
            "timeline_flag": _has_flag(stripped, _TIMELINE_TERMS),
            "keywords": _extract_keywords(stripped),
            "text": stripped,
        })

    # If no clauses found, treat entire text as one clause (minus headers)
    if not clauses:
        # Try to strip obvious header/footer before using as fallback
        lines = text.split('\n')
        body_lines = []
        for line in lines:
            line_stripped = line.strip()
            if len(line_stripped) < 10:
                continue
            cls = _classify_section(line_stripped)
            if cls in ("operative", "background"):
                body_lines.append(line_stripped)

        fallback_text = '\n'.join(body_lines) if body_lines else text.strip()
        if len(fallback_text) > 30:
            clauses.append({
                "gr_id": gr_id,
                "department": department,
                "language": language,
                "chunk_id": 1,
                "clause_number": 1,
                "clause_type": "operative",
                "subject": subject,
                "year": year,
                "financial_flag": _has_flag(fallback_text, _FINANCIAL_TERMS),
                "authority_flag": _has_flag(fallback_text, _AUTHORITY_TERMS),
                "timeline_flag": _has_flag(fallback_text, _TIMELINE_TERMS),
                "keywords": _extract_keywords(fallback_text),
                "text": fallback_text[:1000],
            })

    return clauses


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample", type=int, default=None, help="Process only a sample of N documents")
    args = parser.parse_args()

    workspace_root = os.path.dirname(os.path.abspath(__file__))
    dataset_root = Path(workspace_root) / "mahGRs-main" / "GRs"
    if not dataset_root.exists():
        dataset_root = Path(workspace_root) / "mahGRs"
    data_dir = os.path.join(workspace_root, "backend", "data")
    os.makedirs(data_dir, exist_ok=True)

    if not dataset_root.exists():
        print(f"Error: Local dataset not found at {dataset_root}")
        sys.exit(1)

    print("✓ Parsing GRs with clause-aware structural parser...")
    all_files = list(dataset_root.rglob("*.txt"))
    
    if args.sample and args.sample < len(all_files):
        print(f"Sampling {args.sample} files from total {len(all_files)}...")
        random.seed(42)  # For reproducible samples
        all_files = random.sample(all_files, args.sample)

    chunks_data = []
    metadata = []
    skipped = 0

    for i, file in enumerate(all_files):
        filename = file.name
        gr_id = filename.split(".")[0]
        department = file.parent.name
        language = "mr" if ".mr." in filename else "en"

        metadata.append({
            "gr_id": gr_id,
            "department": department,
            "language": language,
            "filename": filename,
            "path": str(file)
        })

        try:
            with open(file, "r", encoding="utf-8") as f:
                text = f.read()
            clauses = parse_gr_into_clauses(text, gr_id, department, language)
            chunks_data.extend(clauses)
        except Exception as e:
            print(f"Skipping {filename}: {e}")
            skipped += 1

        if (i + 1) % 500 == 0:
            print(f"  Processed {i + 1}/{len(all_files)} files, {len(chunks_data)} clauses so far...")

    print(f"Created {len(chunks_data)} clause-level chunks from {len(all_files)} files (skipped {skipped}).")

    # Statistics
    types = {}
    for c in chunks_data:
        t = c.get("clause_type", "unknown")
        types[t] = types.get(t, 0) + 1
    print(f"Clause types: {types}")

    # Save metadata.json
    metadata_path = os.path.join(data_dir, "metadata.json")
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)
    print(f"Saved metadata to {metadata_path}")

    print("✓ Generating embeddings (this may take some time)...")
    import torch
    texts = ["passage: " + chunk["text"] for chunk in chunks_data]
    
    if torch.cuda.is_available():
        gpu_count = torch.cuda.device_count()
        print(f"Using device: CUDA ({gpu_count} GPUs detected)")
        if gpu_count > 1:
            print("Starting multi-process pool for multi-GPU execution...")
            model = SentenceTransformer("intfloat/multilingual-e5-base")
            pool = model.start_multi_process_pool()
            embeddings = model.encode_multi_process(texts, pool, batch_size=256)
            model.stop_multi_process_pool(pool)
            
            # encode_multi_process returns a numpy array directly by default in newer versions, 
            # but let's ensure it's a numpy array just in case
            import numpy as np
            embeddings = np.array(embeddings)
        else:
            model = SentenceTransformer("intfloat/multilingual-e5-base", device="cuda")
            embeddings = model.encode(texts, batch_size=256, show_progress_bar=True, convert_to_numpy=True)
    else:
        device = "mps" if torch.backends.mps.is_available() else "cpu"
        print(f"Using device: {device.upper()}")
        model = SentenceTransformer("intfloat/multilingual-e5-base", device=device)
        embeddings = model.encode(texts, batch_size=32, show_progress_bar=True, convert_to_numpy=True)

    print("✓ Building FAISS index...")
    faiss.normalize_L2(embeddings)
    dimension = embeddings.shape[1]
    index = faiss.IndexFlatIP(dimension)
    index.add(embeddings)

    # Save index.faiss and chunks.pkl to backend/data/
    index_out = os.path.join(data_dir, "index.faiss")
    chunks_pkl_out = os.path.join(data_dir, "chunks.pkl")

    faiss.write_index(index, index_out)
    with open(chunks_pkl_out, "wb") as f:
        pickle.dump(chunks_data, f)

    print(f"✓ Embedding regeneration complete.")
    print(f"  Total clauses indexed: {len(chunks_data)}")
    print(f"  FAISS dimension: {dimension}")
    print(f"  Index saved to: {index_out}")
    print(f"  Chunks saved to: {chunks_pkl_out}")
    print(f"  Backend ready.")


if __name__ == "__main__":
    main()
