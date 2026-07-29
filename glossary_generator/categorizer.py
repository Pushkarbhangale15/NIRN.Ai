"""
categorizer.py — Automatic category classification for extracted terms.

Uses keyword matching against known category vocabularies.
No LLM — purely deterministic, reproducible.
"""

import re
from typing import Dict, List, Tuple

# ─────────────────────────────────────────────────────────────────────────────
# Category keyword vocabularies
# Each key is a category name; value is (English keywords, Marathi keywords)
# ─────────────────────────────────────────────────────────────────────────────

CATEGORY_VOCAB: Dict[str, Tuple[List[str], List[str]]] = {
    "Finance": (
        [
            "financial", "sanction", "grant", "fund", "expenditure", "budget",
            "treasury", "accountant", "accounts", "fiscal", "allocation",
            "reimbursement", "subsidy", "disbursement", "payment", "remittance",
            "appropriation", "deposit", "loan", "advance", "consolidated fund",
            "contingency fund", "salary", "wage", "honorarium", "stipend",
        ],
        [
            "वित्तीय", "मंजुरी", "अनुदान", "निधी", "खर्च", "अर्थसंकल्प",
            "कोषागार", "महालेखापाल", "वित्त", "आर्थिक", "वाटप", "परतावा",
            "अनुदान", "वितरण", "देयक", "प्रेषण", "विनियोग", "ठेव",
            "कर्ज", "अग्रिम", "एकत्रित निधी", "आकस्मिक निधी",
        ],
    ),
    "Budget": (
        [
            "budget head", "budget estimate", "revised estimate", "demand",
            "plan expenditure", "non-plan", "annual plan", "appropriation",
            "head of account", "major head", "minor head", "sub-head",
        ],
        [
            "अर्थसंकल्पीय शीर्ष", "अर्थसंकल्पात", "सुधारित अंदाज", "मागणी",
            "नियोजन खर्च", "बिगर नियोजन", "वार्षिक योजना", "लेखाशीर्ष",
            "प्रमुख शीर्ष", "किरकोळ शीर्ष",
        ],
    ),
    "Personnel": (
        [
            "employee", "officer", "staff", "cadre", "post", "appointment",
            "promotion", "transfer", "leave", "salary", "pay", "pension",
            "allowance", "seniority", "probation", "departmental inquiry",
            "service", "recruitment", "vacancy", "deputation", "lien",
            "dismissal", "suspension", "retirement", "gratuity",
        ],
        [
            "कर्मचारी", "अधिकारी", "कर्मचारी वर्ग", "संवर्ग", "पद", "नियुक्ती",
            "पदोन्नती", "बदली", "रजा", "वेतन", "निवृत्तिवेतन",
            "भत्ता", "ज्येष्ठता", "परिविक्षाधीन", "विभागीय चौकशी",
            "सेवा", "भरती", "रिक्त पद", "प्रतिनियुक्ती", "निलंबन",
            "निवृत्ती", "उपदान",
        ],
    ),
    "Education": (
        [
            "school", "college", "university", "education", "student",
            "teacher", "faculty", "course", "syllabus", "examination",
            "academic", "scholarship", "hostel", "affiliation", "admission",
            "intake", "enrollment", "enrolment", "degree", "diploma",
            "naac", "aicte", "ncte", "ugc",
        ],
        [
            "शाळा", "महाविद्यालय", "विद्यापीठ", "शिक्षण", "विद्यार्थी",
            "शिक्षक", "विद्याशाखा", "अभ्यासक्रम", "परीक्षा",
            "शैक्षणिक", "शिष्यवृत्ती", "वसतिगृह", "संलग्नीकरण", "प्रवेश",
            "पटसंख्या", "नोंदणी", "पदवी", "डिप्लोमा",
        ],
    ),
    "Agriculture": (
        [
            "agriculture", "farm", "crop", "irrigation", "soil", "water",
            "farmer", "drought", "fertilizer", "seed", "cultivation",
            "horticulture", "dairy", "animal husbandry", "fisheries",
            "forest", "watershed",
        ],
        [
            "कृषी", "शेती", "पीक", "सिंचन", "माती", "पाणी",
            "शेतकरी", "दुष्काळ", "खत", "बियाणे", "लागवड",
            "फलोत्पादन", "दुग्धव्यवसाय", "पशुसंवर्धन", "मत्स्यव्यवसाय",
            "वन", "पाणलोट",
        ],
    ),
    "Revenue": (
        [
            "revenue", "land", "record", "mutation", "tenancy", "survey",
            "cadastral", "settlement", "taluka", "tehsil", "collector",
            "taxation", "tax", "stamp duty", "registration",
        ],
        [
            "महसूल", "जमीन", "अभिलेख", "फेरफार", "कूळ", "सर्वेक्षण",
            "भूमापन", "तालुका", "तहसील", "जिल्हाधिकारी",
            "कर", "मुद्रांक शुल्क", "नोंदणी",
        ],
    ),
    "Infrastructure": (
        [
            "road", "bridge", "building", "construction", "project",
            "tender", "contractor", "works", "public works", "pwl",
            "housing", "water supply", "sanitation", "electricity",
            "irrigation", "dam", "canal",
        ],
        [
            "रस्ता", "पूल", "इमारत", "बांधकाम", "प्रकल्प",
            "निविदा", "कंत्राटदार", "बांधकाम", "सार्वजनिक बांधकाम",
            "गृहनिर्माण", "पाणीपुरवठा", "स्वच्छता", "विद्युत",
            "सिंचन", "धरण", "कालवा",
        ],
    ),
    "Legal": (
        [
            "act", "rule", "regulation", "ordinance", "court", "judge",
            "law", "judicial", "section", "clause", "provision",
            "jurisdiction", "appeal", "petition", "tribunal", "gazette",
            "notification", "amendment", "repeal", "supersession",
        ],
        [
            "अधिनियम", "नियम", "विनियम", "अध्यादेश", "न्यायालय", "न्यायाधीश",
            "कायदा", "न्यायिक", "कलम", "खंड", "तरतूद",
            "अधिकार क्षेत्र", "अपील", "याचिका", "न्यायाधिकरण", "राजपत्र",
            "अधिसूचना", "दुरुस्ती", "रद्द", "अधिक्रमण",
        ],
    ),
    "Healthcare": (
        [
            "hospital", "health", "medicine", "doctor", "nurse", "patient",
            "medical", "drug", "pharmacy", "clinical", "disease", "vaccination",
            "public health", "primary health centre", "ayurveda",
        ],
        [
            "रुग्णालय", "आरोग्य", "औषध", "डॉक्टर", "परिचारिका", "रुग्ण",
            "वैद्यकीय", "औषधी", "फार्मसी", "रोग", "लसीकरण",
            "सार्वजनिक आरोग्य", "प्राथमिक आरोग्य केंद्र",
        ],
    ),
    "Rural Development": (
        [
            "rural", "village", "panchayat", "gram", "gram sabha",
            "zilla parishad", "block", "mandal", "mahatma gandhi",
            "mgnrega", "watershed", "self help group", "microfinance",
        ],
        [
            "ग्रामीण", "गाव", "पंचायत", "ग्राम", "ग्रामसभा",
            "जिल्हा परिषद", "पंचायत समिती", "मनरेगा",
            "स्वयंसहायता गट", "सूक्ष्म वित्त",
        ],
    ),
    "Urban Development": (
        [
            "urban", "city", "municipal", "corporation", "metro",
            "slum", "housing", "town", "development plan", "nagar",
        ],
        [
            "नागरी", "शहर", "महापालिका", "महानगरपालिका", "मेट्रो",
            "झोपडपट्टी", "गृहनिर्माण", "नगर", "विकास योजना",
        ],
    ),
    "Office Procedure": (
        [
            "circular", "order", "directive", "resolution", "memorandum",
            "office procedure", "manual", "noting", "draft", "despatch",
            "correspondence", "file", "record", "minutes", "agenda",
            "copy to", "preamble", "reference", "implementation",
        ],
        [
            "परिपत्रक", "आदेश", "निर्देश", "ठराव", "ज्ञापन",
            "कार्यालयीन कार्यपद्धती", "नियमपुस्तिका", "नोंद", "मसुदा",
            "प्रेषण", "पत्रव्यवहार", "फाईल", "अभिलेख", "इतिवृत्त",
            "कार्यसूची", "प्रत", "प्रस्तावना", "संदर्भ", "अंमलबजावणी",
        ],
    ),
    "Administration": (
        [
            "department", "secretary", "director", "commissioner",
            "government", "administration", "policy", "scheme",
            "committee", "board", "authority", "council", "delegation",
            "ministry", "state government", "central government",
        ],
        [
            "विभाग", "सचिव", "संचालक", "आयुक्त",
            "शासन", "प्रशासन", "धोरण", "योजना",
            "समिती", "मंडळ", "प्राधिकरण", "परिषद",
            "राज्य शासन", "केंद्र शासन",
        ],
    ),
}

# Priority order for tie-breaking (more specific categories win)
CATEGORY_PRIORITY = [
    "Budget", "Finance", "Education", "Agriculture", "Revenue",
    "Healthcare", "Rural Development", "Urban Development", "Infrastructure",
    "Judiciary", "Legal", "Personnel", "Office Procedure", "Administration",
    "General Government",
]


def classify(text: str, language: str = "en", hint: str = "") -> str:
    """
    Classify a phrase into a category.

    Args:
        text: The phrase to classify.
        language: "en" or "mr"
        hint: Optional initial category hint from the extractor.

    Returns:
        Best matching category string.
    """
    text_lower = text.lower()
    scores: Dict[str, int] = {cat: 0 for cat in CATEGORY_VOCAB}

    for category, (en_kws, mr_kws) in CATEGORY_VOCAB.items():
        if language == "en":
            keywords = en_kws
        else:
            keywords = mr_kws
        for kw in keywords:
            if kw.lower() in text_lower:
                scores[category] += 1

    # Find category with highest score
    max_score = max(scores.values())
    if max_score == 0:
        # No keyword match — use hint or default
        return hint if hint in CATEGORY_VOCAB else "General Government"

    # Among tied categories, use priority order
    candidates = [cat for cat, score in scores.items() if score == max_score]
    for cat in CATEGORY_PRIORITY:
        if cat in candidates:
            return cat

    return candidates[0]


def classify_budget_head(code: str, department: str) -> str:
    """
    Classify a budget head code using the first two digits (Major Head).

    Standard Government of India Major Head ranges:
        0xxx - Revenue receipts
        1xxx - Revenue receipts (continued)
        2xxx - Revenue expenditure (social / general services)
        3xxx - Revenue expenditure (economic services)
        4xxx - Capital outlay
        5xxx - Loans and advances given
        6xxx - Loans and advances received
        7xxx - Debt / remittance heads
        8xxx - Contingency and other funds
    """
    if not code or not re.match(r'^\d{4}', code):
        return "Budget"

    major = int(code[:4])
    if 2000 <= major < 2300:
        return "Administration"
    elif 2200 <= major < 2300:
        return "Education"
    elif 2210 <= major < 2220:
        return "Healthcare"
    elif 2400 <= major < 2500:
        return "Agriculture"
    elif 2200 <= major < 2400:
        return "Finance"
    elif 4000 <= major < 5000:
        return "Infrastructure"
    elif 3000 <= major < 4000:
        return "Agriculture"
    return "Budget"
