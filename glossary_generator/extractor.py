"""
extractor.py — Phrase extraction from GR documents.

Deterministic extraction using regex patterns, keyword anchors, and
n-gram frequency analysis. No LLM involved.

Extracts:
  1. Legal terminology (multi-word administrative phrases)
  2. Department names
  3. Office designations
  4. Standard GR phrases
  5. Budget head codes
  6. Named acts and schemes
"""

import re
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

from cleaner import (
    clean_text,
    is_valid_phrase,
    normalize_phrase,
    split_sentences,
)

# ─────────────────────────────────────────────────────────────────────────────
# Data containers
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class ExtractedPhrase:
    """A raw extracted phrase before alignment or classification."""
    text: str
    language: str          # "en" or "mr"
    category_hint: str     # initial hint from the extraction pattern
    source_gr: str         # GR document ID
    department: str
    context: str           # surrounding sentence for validation


# ─────────────────────────────────────────────────────────────────────────────
# English pattern definitions
# ─────────────────────────────────────────────────────────────────────────────

# Formal Government Resolution phrases
_EN_GR_PHRASES = [
    re.compile(r'Government (?:Resolution|Order|Circular|Notification)\b', re.I),
    re.compile(r'Manual of Office Procedure\b', re.I),
    re.compile(r'Financial Sanction\b', re.I),
    re.compile(r'Administrative Approval\b', re.I),
    re.compile(r'Competent Authority\b', re.I),
    re.compile(r'Expenditure Sanction\b', re.I),
    re.compile(r'Technical Sanction\b', re.I),
    re.compile(r'Revised Estimate\b', re.I),
    re.compile(r'Budget Estimate\b', re.I),
    re.compile(r'Grant[- ]in[- ]Aid\b', re.I),
    re.compile(r'Plan Expenditure\b', re.I),
    re.compile(r'Non[- ]Plan Expenditure\b', re.I),
    re.compile(r'Sanctioned Post\b', re.I),
    re.compile(r'Sanctioned Intake\b', re.I),
    re.compile(r'Probation Period\b', re.I),
    re.compile(r'Departmental (?:Inquiry|Examination|Promotion)\b', re.I),
    re.compile(r'Public Accounts Committee\b', re.I),
    re.compile(r'Chief Minister(?:\'s)? Relief Fund\b', re.I),
    re.compile(r'State Government Employees?\b', re.I),
    re.compile(r'Pay (?:Band|Commission|Scale|Fixation|Revision)\b', re.I),
    re.compile(r'Dearness Allowance\b', re.I),
    re.compile(r'House Rent Allowance\b', re.I),
    re.compile(r'Travel(?:ling)? Allowance\b', re.I),
    re.compile(r'Medical Reimbursement\b', re.I),
    re.compile(r'Transfer Policy\b', re.I),
    re.compile(r'General Transfer\b', re.I),
    re.compile(r'Maternity Leave\b', re.I),
    re.compile(r'Casual Leave\b', re.I),
    re.compile(r'Earned Leave\b', re.I),
    re.compile(r'Leave Without Pay\b', re.I),
    re.compile(r'State Cabinet\b', re.I),
    re.compile(r'Governor of Maharashtra\b', re.I),
    re.compile(r'Government of Maharashtra\b', re.I),
    re.compile(r'Mantralaya(?:,\s*Mumbai)?\b', re.I),
    re.compile(r'With (?:immediate|retrospective) effect\b', re.I),
    re.compile(r'Subject to the provisions\b', re.I),
    re.compile(r'By order and in the name of the Governor\b', re.I),
    re.compile(r'Under Secretary to (?:Government|Govt)\b', re.I),
    re.compile(r'Principal Secretary to (?:Government|Govt)\b', re.I),
    re.compile(r'Additional Chief Secretary\b', re.I),
    re.compile(r'Joint Secretary\b', re.I),
    re.compile(r'Deputy Secretary\b', re.I),
    re.compile(r'Section Officer\b', re.I),
    re.compile(r'Finance Department\b', re.I),
    re.compile(r'Planning Department\b', re.I),
    re.compile(r'General Administration Department\b', re.I),
    re.compile(r'Director(?:ate)? of\s+[A-Z][a-z\s]+\b'),
    re.compile(r'Commissioner(?:\s+of\s+[A-Z][a-z\s]+)?\b'),
    re.compile(r'Municipal Corpor(?:ation|ations?)\b', re.I),
    re.compile(r'Local Self[- ]Government(?:\s+Body)?\b', re.I),
    re.compile(r'Backward Class\b', re.I),
    re.compile(r'Scheduled (?:Caste|Tribe)s?\b', re.I),
    re.compile(r'Other Backward Class(?:es)?\b', re.I),
    re.compile(r'Economically Weaker Section\b', re.I),
    re.compile(r'Annual (?:Confidential|Performance) Report\b', re.I),
    re.compile(r'Detailed Project Report\b', re.I),
    re.compile(r'Public Interest\b', re.I),
    re.compile(r'E[- ]Tendering\b', re.I),
    re.compile(r'Work Order\b', re.I),
    re.compile(r'Contractor\b', re.I),
    re.compile(r'Gross Enrolment Ratio\b', re.I),
    re.compile(r'Academic (?:Year|Session|Calendar)\b', re.I),
    re.compile(r'Affiliated (?:College|Institution|University)\b', re.I),
    re.compile(r'Accreditation\b', re.I),
]

# English: Anchor-based patterns for multi-word phrases
_EN_ANCHOR_PATTERNS = [
    # "X Department"
    re.compile(r'\b([A-Z][a-z]+(?:\s+(?:and|of|for|the)\s+[A-Z][a-z]+)*\s+Department)\b'),
    # "X Act, YYYY"
    re.compile(r'\b([A-Z][a-z]+(?:\s+[A-Za-z]+){0,6}\s+Act,?\s*\d{4})\b'),
    # "X Scheme"
    re.compile(r'\b([A-Z][a-z]+(?:\s+[A-Za-z]+){0,5}\s+Scheme)\b'),
    # "X Fund"
    re.compile(r'\b([A-Z][a-z]+(?:\s+[A-Za-z]+){0,4}\s+Fund)\b'),
    # "X Policy"
    re.compile(r'\b([A-Z][a-z]+(?:\s+[A-Za-z]+){0,4}\s+Policy)\b'),
    # "X Committee"
    re.compile(r'\b([A-Z][a-z]+(?:\s+[A-Za-z]+){0,5}\s+Committee)\b'),
    # "X Board"
    re.compile(r'\b([A-Z][a-z]+(?:\s+[A-Za-z]+){0,4}\s+Board)\b'),
    # "the X of Y" - 'the Secretary of State' style
    re.compile(r'\bthe\s+([A-Z][a-z]+(?:\s+[A-Za-z]+){1,5})\b'),
]

# Budget head format: e.g. "2053-00-101-01" or "2202-01-102-00"
_BUDGET_HEAD_EN = re.compile(
    r'\b(\d{4}[-–]\d{2}[-–]\d{3}[-–]\d{2})\b'
)

# GR reference: "GR No. XYZ-2020/CR-45/TE-1"
_GR_REF_EN = re.compile(
    r'(?:G\.?R\.?\s*No\.?|Government\s+Resolution\s+No\.?)\s*:?\s*'
    r'([A-Z]{2,10}[-–]\d{4}/[A-Za-z0-9./-]{3,30})',
    re.IGNORECASE
)

# Standard phrase triggers (beginning of standard phrases)
_EN_STANDARD_PHRASES = [
    ("It is hereby directed", "Office Procedure"),
    ("The Government is pleased to", "Office Procedure"),
    ("With immediate effect", "Office Procedure"),
    ("With effect from", "Office Procedure"),
    ("Accordingly, the Government", "Office Procedure"),
    ("Subject to the terms and conditions", "Office Procedure"),
    ("By order and in the name of the Governor", "Office Procedure"),
    ("The following orders are issued", "Office Procedure"),
    ("This issues with the concurrence", "Office Procedure"),
    ("As per the provisions of", "Legal"),
    ("In supersession of", "Administration"),
    ("In modification of", "Administration"),
    ("In continuation of", "Administration"),
    ("No objection is raised", "Administration"),
    ("The expenditure is to be met from", "Finance"),
    ("The amount is to be debited to", "Finance"),
    ("Provision has been made", "Finance"),
    ("Administrative approval is hereby accorded", "Finance"),
    ("Financial sanction is hereby accorded", "Finance"),
]


# ─────────────────────────────────────────────────────────────────────────────
# Marathi pattern definitions
# ─────────────────────────────────────────────────────────────────────────────

# Fixed Marathi legal/admin terms (known phrases from GR corpus)
_MR_FIXED_TERMS = [
    ("शासन निर्णय", "Office Procedure"),
    ("शासन परिपत्रक", "Office Procedure"),
    ("शासन अधिसूचना", "Office Procedure"),
    ("शासन आदेश", "Office Procedure"),
    ("महाराष्ट्र शासन", "Administration"),
    ("प्रशासकीय मान्यता", "Administration"),
    ("वित्तीय मान्यता", "Finance"),
    ("वित्तीय मंजुरी", "Finance"),
    ("तांत्रिक मान्यता", "Finance"),
    ("सक्षम प्राधिकारी", "Legal"),
    ("अनुदान सहाय्य", "Finance"),
    ("अनुदान मंजूर", "Finance"),
    ("अर्थसंकल्पीय तरतूद", "Budget"),
    ("अर्थसंकल्पात तरतूद", "Budget"),
    ("सुधारित अंदाज", "Budget"),
    ("वार्षिक अंदाजपत्रक", "Budget"),
    ("मंजूर प्रवेश क्षमता", "Education"),
    ("परिविक्षाधीन कालावधी", "Personnel"),
    ("विभागीय चौकशी", "Personnel"),
    ("वेतन आयोग", "Personnel"),
    ("महागाई भत्ता", "Personnel"),
    ("घरभाडे भत्ता", "Personnel"),
    ("प्रवास भत्ता", "Personnel"),
    ("रजा रोखीकरण", "Personnel"),
    ("अर्जित रजा", "Personnel"),
    ("राज्य शासनाचे कर्मचारी", "Personnel"),
    ("राज्यपालांच्या नावे व आदेशाने", "Office Procedure"),
    ("राजपत्र अधिसूचना", "Legal"),
    ("सार्वजनिक हित", "Administration"),
    ("लोकहित", "Administration"),
    ("मंत्रालय, मुंबई", "Administration"),
    ("अवर सचिव", "Administration"),
    ("प्रधान सचिव", "Administration"),
    ("उप सचिव", "Administration"),
    ("संयुक्त सचिव", "Administration"),
    ("अतिरिक्त मुख्य सचिव", "Administration"),
    ("मुख्य सचिव", "Administration"),
    ("आयुक्त", "Administration"),
    ("विभागीय आयुक्त", "Administration"),
    ("जिल्हाधिकारी", "Administration"),
    ("तहसीलदार", "Administration"),
    ("ग्रामपंचायत", "Rural Development"),
    ("जिल्हा परिषद", "Administration"),
    ("महानगरपालिका", "Urban Development"),
    ("नगरपालिका", "Urban Development"),
    ("अनुसूचित जाती", "Administration"),
    ("अनुसूचित जमाती", "Administration"),
    ("इतर मागासवर्ग", "Administration"),
    ("आर्थिकदृष्ट्या दुर्बल घटक", "Administration"),
    ("वार्षिक गोपनीय अहवाल", "Personnel"),
    ("पदोन्नती", "Personnel"),
    ("नियुक्ती", "Personnel"),
    ("बदली धोरण", "Personnel"),
    ("सामान्य बदली", "Personnel"),
    ("प्रसूती रजा", "Personnel"),
    ("आकस्मिक रजा", "Personnel"),
    ("शैक्षणिक वर्ष", "Education"),
    ("संलग्नित महाविद्यालय", "Education"),
    ("सकल नोंदणी प्रमाण", "Education"),
    ("राज्य मंत्रिमंडळ", "Administration"),
    ("मंत्रिपरिषद", "Administration"),
    ("विधानसभा", "Legal"),
    ("विधानपरिषद", "Legal"),
    ("राज्य विधिमंडळ", "Legal"),
    ("कार्यालयीन कार्यपद्धती नियमावली", "Office Procedure"),
    ("e-निविदा", "Administration"),
    ("कार्यादेश", "Administration"),
    ("तात्काळ प्रभावाने", "Office Procedure"),
    ("या निर्णयास वित्त विभागाने मान्यता दिली आहे", "Finance"),
    ("वाचा", "Office Procedure"),
    ("संदर्भ", "Office Procedure"),
    ("प्रस्तावना", "Office Procedure"),
]

# Marathi anchor patterns for department names
_MR_DEPT_PATTERN = re.compile(
    r'([^\s,।]+(?:\s+[^\s,।]+){0,6}\s+विभाग)\b',
    re.UNICODE
)

# Marathi scheme/act patterns
_MR_ACT_PATTERN = re.compile(
    r'([^\s,।]+(?:\s+[^\s,।]+){0,8}\s+(?:अधिनियम|कायदा|योजना|नियमावली)(?:\s*,?\s*\d{4})?)\b',
    re.UNICODE
)

# Marathi budget head (same numeric format, sometimes in Devanagari)
_BUDGET_HEAD_MR = re.compile(
    r'\b(\d{4}[-–]\d{2}[-–]\d{3}[-–]\d{2})\b'
)


# ─────────────────────────────────────────────────────────────────────────────
# Standard phrases for output (always included)
# ─────────────────────────────────────────────────────────────────────────────

STANDARD_EN_PHRASES = [
    "It is hereby directed that",
    "The Government is pleased to sanction",
    "With immediate effect",
    "With effect from the date of issue",
    "Accordingly, the Government hereby orders",
    "Subject to the terms and conditions",
    "By order and in the name of the Governor of Maharashtra",
    "The following orders are issued",
    "This issues with the concurrence of the Finance Department",
    "As per the provisions of the Act",
    "In supersession of all previous orders",
    "In modification of Government Resolution",
    "No objection is raised to the above proposal",
    "The expenditure is to be met from the Consolidated Fund",
    "Administrative approval is hereby accorded",
    "Financial sanction is hereby accorded",
    "The amount is to be debited to",
    "Provision has been made in the Budget",
    "The matter was under consideration of the Government",
    "The Government has decided as follows",
]

STANDARD_MR_PHRASES = [
    "याद्वारे आदेश देण्यात येतो की",
    "शासन खालीलप्रमाणे मंजुरी देण्यास प्रसन्न आहे",
    "तात्काळ प्रभावाने",
    "आदेश निर्गमित तारखेपासून अंमलात येईल",
    "त्यानुसार शासन आदेश देत आहे",
    "अटी व शर्तींच्या अधीन",
    "राज्यपालांच्या नावे व आदेशाने",
    "खालील आदेश निर्गमित केले जात आहेत",
    "हे वित्त विभागाच्या सहमतीने निर्गमित होत आहे",
    "अधिनियमातील तरतुदींनुसार",
    "मागील सर्व आदेशांच्या अधिक्रमणाने",
    "शासन निर्णयात बदल करुन",
    "वरील प्रस्तावास आक्षेप नाही",
    "एकत्रित निधीतून खर्च भागविण्यात यावा",
    "प्रशासकीय मान्यता प्रदान करण्यात येत आहे",
    "वित्तीय मंजुरी प्रदान करण्यात येत आहे",
    "रक्कम खात्यावर नावे टाकण्यात यावी",
    "अर्थसंकल्पात तरतूद करण्यात आलेली आहे",
    "बाब शासनाच्या विचाराधीन होती",
    "शासनाने खालीलप्रमाणे निर्णय घेतला आहे",
]


# ─────────────────────────────────────────────────────────────────────────────
# Extractor class
# ─────────────────────────────────────────────────────────────────────────────

class PhraseExtractor:
    """
    Extracts multi-word administrative and legal phrases from GR text.

    Usage:
        extractor = PhraseExtractor()
        phrases = extractor.extract(text, language, gr_id, department)
    """

    def __init__(self, min_phrase_chars: int = 5, max_phrase_tokens: int = 8):
        self.min_chars = min_phrase_chars
        self.max_tokens = max_phrase_tokens

    def extract(
        self,
        text: str,
        language: str,
        gr_id: str,
        department: str,
    ) -> List[ExtractedPhrase]:
        """
        Extract all known phrases from a document.

        Args:
            text: Cleaned document text.
            language: "en" or "mr"
            gr_id: Document identifier.
            department: Source department name.

        Returns:
            List of ExtractedPhrase objects.
        """
        if language == "en":
            return self._extract_english(text, gr_id, department)
        else:
            return self._extract_marathi(text, gr_id, department)

    def _make_phrase(self, text: str, lang: str, cat: str, gr: str, dept: str, ctx: str = "") -> Optional[ExtractedPhrase]:
        text = normalize_phrase(text)
        if not is_valid_phrase(text, self.min_chars, self.max_tokens):
            return None
        return ExtractedPhrase(
            text=text,
            language=lang,
            category_hint=cat,
            source_gr=gr,
            department=dept,
            context=ctx[:200],
        )

    def _extract_english(self, text: str, gr_id: str, dept: str) -> List[ExtractedPhrase]:
        results = []
        sentences = split_sentences(text)

        # 1. Fixed pattern matches
        for pattern in _EN_GR_PHRASES:
            for match in pattern.finditer(text):
                phrase = match.group(0)
                p = self._make_phrase(phrase, "en", "Administration", gr_id, dept, text[max(0, match.start()-50):match.end()+50])
                if p:
                    results.append(p)

        # 2. Standard phrase anchors
        for phrase_start, category in _EN_STANDARD_PHRASES:
            if phrase_start.lower() in text.lower():
                idx = text.lower().find(phrase_start.lower())
                # Grab up to 20 words starting at this anchor
                snippet = text[idx:idx+120]
                first_sentence_end = re.search(r'[.!?।]', snippet)
                if first_sentence_end:
                    snippet = snippet[:first_sentence_end.start()]
                p = self._make_phrase(snippet.strip(), "en", category, gr_id, dept, text[max(0,idx-30):idx+120])
                if p:
                    results.append(p)

        # 3. Anchor-based named-entity patterns
        for pattern in _EN_ANCHOR_PATTERNS:
            for match in pattern.finditer(text):
                phrase = match.group(1) if match.lastindex else match.group(0)
                p = self._make_phrase(phrase, "en", "Administration", gr_id, dept)
                if p:
                    results.append(p)

        # 4. Budget heads
        for match in _BUDGET_HEAD_EN.finditer(text):
            p = ExtractedPhrase(
                text=match.group(1),
                language="en",
                category_hint="Budget",
                source_gr=gr_id,
                department=dept,
                context=text[max(0, match.start()-40):match.end()+40],
            )
            results.append(p)

        return results

    def _extract_marathi(self, text: str, gr_id: str, dept: str) -> List[ExtractedPhrase]:
        results = []

        # 1. Fixed known Marathi terms
        for term, category in _MR_FIXED_TERMS:
            if term in text:
                idx = text.find(term)
                p = ExtractedPhrase(
                    text=term,
                    language="mr",
                    category_hint=category,
                    source_gr=gr_id,
                    department=dept,
                    context=text[max(0, idx-50):idx+len(term)+50],
                )
                results.append(p)

        # 2. Department name pattern
        for match in _MR_DEPT_PATTERN.finditer(text):
            phrase = match.group(1)
            p = self._make_phrase(phrase, "mr", "Administration", gr_id, dept)
            if p:
                results.append(p)

        # 3. Act/scheme patterns
        for match in _MR_ACT_PATTERN.finditer(text):
            phrase = match.group(1)
            p = self._make_phrase(phrase, "mr", "Legal", gr_id, dept)
            if p:
                results.append(p)

        # 4. Budget heads (same numeric format appears in Marathi docs)
        for match in _BUDGET_HEAD_MR.finditer(text):
            p = ExtractedPhrase(
                text=match.group(1),
                language="mr",
                category_hint="Budget",
                source_gr=gr_id,
                department=dept,
                context=text[max(0, match.start()-40):match.end()+40],
            )
            results.append(p)

        return results

    def extract_standard_phrases(self) -> Tuple[List[str], List[str]]:
        """Return the built-in lists of standard EN and MR phrases."""
        return STANDARD_EN_PHRASES, STANDARD_MR_PHRASES
