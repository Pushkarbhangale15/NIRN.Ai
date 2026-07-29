"""
utils.py — Shared utilities: file discovery, checkpointing, logging setup.
"""

import json
import logging
import logging.handlers
import os
import sys
from pathlib import Path
from typing import Dict, Generator, List, Optional, Set, Tuple


# ─────────────────────────────────────────────────────────────────────────────
# Logging setup
# ─────────────────────────────────────────────────────────────────────────────

def setup_logging(log_dir: str, verbose: bool = False) -> logging.Logger:
    """
    Configure root logger with console + rotating file handlers.

    Returns the root logger.
    """
    os.makedirs(log_dir, exist_ok=True)
    level = logging.DEBUG if verbose else logging.INFO

    # Root logger
    root = logging.getLogger()
    root.setLevel(level)
    root.handlers.clear()

    # Console handler — INFO+ with colour prefixes
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(level)
    console.setFormatter(logging.Formatter(
        "%(asctime)s  %(levelname)-8s  %(message)s",
        datefmt="%H:%M:%S",
    ))
    root.addHandler(console)

    # Rotating file handler — DEBUG+
    log_file = os.path.join(log_dir, "generator.log")
    file_handler = logging.handlers.RotatingFileHandler(
        log_file, maxBytes=10 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(
        "%(asctime)s  %(levelname)-8s  %(name)s  %(message)s"
    ))
    root.addHandler(file_handler)

    # Error-only file
    error_file = os.path.join(log_dir, "errors.log")
    error_handler = logging.FileHandler(error_file, encoding="utf-8")
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(logging.Formatter(
        "%(asctime)s  %(levelname)s  %(name)s\n%(message)s\n"
    ))
    root.addHandler(error_handler)

    return root


# ─────────────────────────────────────────────────────────────────────────────
# File discovery
# ─────────────────────────────────────────────────────────────────────────────

_BINARY_SIGNATURES = [
    b'\x89PNG', b'\xff\xd8\xff', b'%PDF', b'PK\x03\x04',
    b'\xd0\xcf\x11\xe0',  # MS Office compound
]


def is_likely_binary(path: str) -> bool:
    """Check the first 16 bytes to detect binary files."""
    try:
        with open(path, "rb") as f:
            header = f.read(16)
        for sig in _BINARY_SIGNATURES:
            if header.startswith(sig):
                return True
        # Heuristic: >30% non-ASCII bytes → binary
        non_ascii = sum(1 for b in header if b > 127)
        return non_ascii / max(len(header), 1) > 0.30
    except Exception:
        return True


def discover_documents(
    root_path: str,
    supported_extensions: Set[str],
    logger: Optional[logging.Logger] = None,
) -> Generator[Tuple[str, str, str], None, None]:
    """
    Walk the GR corpus and yield tuples of (filepath, department, gr_id).

    Skips:
        - Binary files
        - Hidden files/directories (.DS_Store, .git, etc.)
        - Empty files

    Yields:
        (filepath, department, gr_id)
    """
    log = logger or logging.getLogger(__name__)
    root = Path(root_path)

    for dept_dir in sorted(root.iterdir()):
        if not dept_dir.is_dir() or dept_dir.name.startswith('.'):
            continue
        department = dept_dir.name

        for filepath in sorted(dept_dir.glob("**/*")):
            if filepath.is_dir():
                continue
            if filepath.name.startswith('.'):
                continue

            # Check extension
            suffix = filepath.suffix.lower()
            # Handle compound extensions like .pdf.en.txt → treat as .txt
            name_lower = filepath.name.lower()
            if name_lower.endswith('.en.txt') or name_lower.endswith('.mr.txt'):
                pass  # Always process
            elif suffix not in supported_extensions:
                continue

            # Skip empty
            try:
                if filepath.stat().st_size == 0:
                    log.debug("Skipping empty file: %s", filepath.name)
                    continue
            except OSError:
                continue

            # Skip binary
            if is_likely_binary(str(filepath)):
                log.debug("Skipping binary: %s", filepath.name)
                continue

            # Derive GR ID from filename stem (strip .pdf.en / .pdf.mr extensions)
            gr_id = filepath.name
            for suffix_to_strip in ['.en.txt', '.mr.txt', '.txt', '.md', '.html', '.json']:
                if gr_id.endswith(suffix_to_strip):
                    gr_id = gr_id[:-len(suffix_to_strip)]
            # Also strip .pdf if present
            if gr_id.endswith('.pdf'):
                gr_id = gr_id[:-4]

            yield str(filepath), department, gr_id


def read_file_safe(path: str, logger: Optional[logging.Logger] = None) -> Optional[str]:
    """
    Read a file with multiple encoding fallbacks.
    Returns the text content or None on failure.
    """
    log = logger or logging.getLogger(__name__)
    for encoding in ("utf-8", "utf-8-sig", "cp1252", "iso-8859-1"):
        try:
            with open(path, "r", encoding=encoding, errors="replace") as f:
                return f.read()
        except (UnicodeDecodeError, OSError):
            continue
    log.error("Failed to read file: %s", path)
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Checkpointing
# ─────────────────────────────────────────────────────────────────────────────

def load_checkpoint(checkpoint_file: str) -> Dict:
    """Load a previously saved checkpoint, or return empty state."""
    if os.path.exists(checkpoint_file):
        try:
            with open(checkpoint_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            logging.getLogger(__name__).info(
                "Resuming from checkpoint: %d GRs already processed",
                len(data.get("processed_grs", []))
            )
            return data
        except Exception as e:
            logging.getLogger(__name__).warning("Could not load checkpoint: %s", e)
    return {"processed_grs": [], "phrase_freq": {}, "aligned_pairs": []}


def save_checkpoint(checkpoint_file: str, state: Dict):
    """Save current processing state to checkpoint file."""
    try:
        with open(checkpoint_file, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False)
    except Exception as e:
        logging.getLogger(__name__).warning("Could not save checkpoint: %s", e)


def clear_checkpoint(checkpoint_file: str):
    """Remove checkpoint to start fresh."""
    if os.path.exists(checkpoint_file):
        os.remove(checkpoint_file)


# ─────────────────────────────────────────────────────────────────────────────
# Department metadata
# ─────────────────────────────────────────────────────────────────────────────

# Known Marathi names for the 33 departments in the corpus
def group_bilingual_pairs(dataset_path: str) -> List[Tuple]:
    """
    Walk the GR corpus root and group English + Marathi files by GR ID.

    Returns:
        List of (en_path, mr_path, gr_id, department) tuples.
        Either path may be None for monolingual documents.
    """
    import os
    pairs: dict = {}  # gr_id -> {"en": path, "mr": path, "dept": name}

    root = Path(dataset_path)
    for dept_dir in sorted(root.iterdir()):
        if not dept_dir.is_dir() or dept_dir.name.startswith('.'):
            continue
        department = dept_dir.name

        for filepath in sorted(dept_dir.iterdir()):
            if filepath.is_dir() or filepath.name.startswith('.'):
                continue

            fname = filepath.name.lower()
            if fname.endswith('.en.txt'):
                gr_id = filepath.name[:-7]
                if gr_id not in pairs:
                    pairs[gr_id] = {"dept": department}
                pairs[gr_id]["en"] = str(filepath)
            elif fname.endswith('.mr.txt'):
                gr_id = filepath.name[:-7]
                if gr_id not in pairs:
                    pairs[gr_id] = {"dept": department}
                pairs[gr_id]["mr"] = str(filepath)

    result = []
    for gr_id, info in pairs.items():
        result.append((
            info.get("en"),
            info.get("mr"),
            gr_id,
            info["dept"],
        ))
    return result


DEPARTMENT_MARATHI_NAMES: Dict[str, Dict] = {
    "Agriculture,_Dairy_Development,_Animal_Husbandry_and_Fisheries_Department": {
        "marathi": "कृषी, पशुसंवर्धन, दुग्धव्यवसाय विकास व मत्स्यव्यवसाय विभाग",
        "abbreviation": "ADAHF",
    },
    "Co-operation,_Textiles_and_Marketing_Department": {
        "marathi": "सहकार, वस्त्रोद्योग व बाजार विभाग",
        "abbreviation": "CTM",
    },
    "Environment_Department": {
        "marathi": "पर्यावरण विभाग",
        "abbreviation": "ENV",
    },
    "Finance_Department": {
        "marathi": "वित्त विभाग",
        "abbreviation": "FIN",
    },
    "Food,_Civil_Supplies_and_Consumer_Protection_Department": {
        "marathi": "अन्न, नागरी पुरवठा व ग्राहक संरक्षण विभाग",
        "abbreviation": "FCS",
    },
    "General_Administration_Department": {
        "marathi": "सामान्य प्रशासन विभाग",
        "abbreviation": "GAD",
    },
    "Higher_and_Technical_Education_Department": {
        "marathi": "उच्च व तंत्र शिक्षण विभाग",
        "abbreviation": "HTE",
    },
    "Home_Department": {
        "marathi": "गृह विभाग",
        "abbreviation": "HOME",
    },
    "Housing_Department": {
        "marathi": "गृहनिर्माण विभाग",
        "abbreviation": "HOUS",
    },
    "Industries,_Energy_and_Labour_Department": {
        "marathi": "उद्योग, ऊर्जा व कामगार विभाग",
        "abbreviation": "IEL",
    },
    "Information_Technology_Department": {
        "marathi": "माहिती तंत्रज्ञान विभाग",
        "abbreviation": "IT",
    },
    "Law_and_Judiciary_Department": {
        "marathi": "विधि व न्याय विभाग",
        "abbreviation": "LAW",
    },
    "Marathi_Language_Department": {
        "marathi": "मराठी भाषा विभाग",
        "abbreviation": "ML",
    },
    "Medical_Education_and_Drugs_Department": {
        "marathi": "वैद्यकीय शिक्षण व औषधी द्रव्ये विभाग",
        "abbreviation": "MED",
    },
    "Minorities_Development_Department": {
        "marathi": "अल्पसंख्याक विकास विभाग",
        "abbreviation": "MIN",
    },
    "Other_Backward_Bahujan_Welfare_Department": {
        "marathi": "इतर मागासवर्ग बहुजन कल्याण विभाग",
        "abbreviation": "OBC",
    },
    "Parliamentary_Affairs_Department": {
        "marathi": "संसदीय कार्य विभाग",
        "abbreviation": "PA",
    },
    "Persons_with_Disabilities_Welfare_Department": {
        "marathi": "दिव्यांग कल्याण विभाग",
        "abbreviation": "PWD",
    },
    "Planning_Department": {
        "marathi": "नियोजन विभाग",
        "abbreviation": "PLAN",
    },
    "Public_Health_Department": {
        "marathi": "सार्वजनिक आरोग्य विभाग",
        "abbreviation": "PHD",
    },
    "Public_Works_Department": {
        "marathi": "सार्वजनिक बांधकाम विभाग",
        "abbreviation": "PWD",
    },
    "Revenue_and_Forest_Department": {
        "marathi": "महसूल व वन विभाग",
        "abbreviation": "REV",
    },
    "Rural_Development_Department": {
        "marathi": "ग्रामविकास विभाग",
        "abbreviation": "RDD",
    },
    "School_Education_and_Sports_Department": {
        "marathi": "शालेय शिक्षण व क्रीडा विभाग",
        "abbreviation": "SES",
    },
    "Skill_Development_and_Entrepreneurship_Department": {
        "marathi": "कौशल्य विकास व उद्योजकता विभाग",
        "abbreviation": "SDE",
    },
    "Social_Justice_and_Special_Assistance_Department": {
        "marathi": "सामाजिक न्याय व विशेष सहाय्य विभाग",
        "abbreviation": "SJSA",
    },
    "Soil_and_Water_Conservation_Department": {
        "marathi": "मृद व जलसंधारण विभाग",
        "abbreviation": "SWC",
    },
    "Tourism_and_Cultural_Affairs_Department": {
        "marathi": "पर्यटन व सांस्कृतिक कार्य विभाग",
        "abbreviation": "TCA",
    },
    "Tribal_Development_Department": {
        "marathi": "आदिवासी विकास विभाग",
        "abbreviation": "TDD",
    },
    "Urban_Development_Department": {
        "marathi": "नगरविकास विभाग",
        "abbreviation": "UDD",
    },
    "Water_Resources_Department": {
        "marathi": "जलसंपदा विभाग",
        "abbreviation": "WRD",
    },
    "Water_Supply_and_Sanitation_Department": {
        "marathi": "पाणी पुरवठा व स्वच्छता विभाग",
        "abbreviation": "WSS",
    },
    "Women_and_Child_Development_Department": {
        "marathi": "महिला व बालविकास विभाग",
        "abbreviation": "WCD",
    },
}
