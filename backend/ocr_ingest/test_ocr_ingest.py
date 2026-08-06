"""
Unit tests for ocr_ingest/clean.py and ocr_ingest/metadata.py, using
realistic OCR-shaped fixture text (garbled whitespace, mixed-script lines,
real GR header formats already seen elsewhere in this project) rather than
synthetic examples — mirrors the style of
backend/test_draft_27201ed3_regressions.py. Deliberately regex-only
inputs (no LLM fallback triggered), so these run fast and don't need
Ollama up.
"""
import unittest

from ocr_ingest.clean import clean_and_reassemble
from ocr_ingest.extract import OcrBlock
from ocr_ingest.metadata import (
    extract_date,
    extract_department,
    extract_gr_number,
    extract_metadata,
    extract_subject,
)


class TestCleanAndReassemble(unittest.TestCase):
    def test_joins_stray_mid_sentence_line_break(self):
        # A justified paragraph split mid-sentence by the scan -- no
        # sentence-final punctuation on the first line, so it should join
        # to the next rather than becoming its own paragraph.
        blocks = [
            OcrBlock(text="शासनाच्या विचाराधीन बाब होती की ग्रामीण भागातील", confidence=92.0, needs_review=False),
            OcrBlock(text="शाळांमध्ये पिण्याच्या पाण्याची सुविधा उभारावी.", confidence=90.0, needs_review=False),
        ]
        cleaned, low_conf = clean_and_reassemble(blocks)
        self.assertIn("शासनाच्या विचाराधीन बाब होती की ग्रामीण भागातील शाळांमध्ये पिण्याच्या पाण्याची सुविधा उभारावी.", cleaned)
        self.assertEqual(low_conf, [])

    def test_numbered_clause_starts_new_paragraph(self):
        blocks = [
            OcrBlock(text="शासन परिपत्रक:", confidence=95.0, needs_review=False),
            OcrBlock(text="०१. पहिला कार्यवाहक परिच्छेद आहे.", confidence=88.0, needs_review=False),
            OcrBlock(text="०२. दुसरा कार्यवाहक परिच्छेद आहे.", confidence=91.0, needs_review=False),
        ]
        cleaned, _ = clean_and_reassemble(blocks)
        paragraphs = [p for p in cleaned.split("\n\n") if p.strip()]
        self.assertEqual(len(paragraphs), 3)
        self.assertTrue(paragraphs[1].startswith("०१."))
        self.assertTrue(paragraphs[2].startswith("०२."))

    def test_low_confidence_blocks_are_collected(self):
        blocks = [
            OcrBlock(text="स्पष्ट मजकूर.", confidence=95.0, needs_review=False),
            OcrBlock(text="अस्पष्ट धूसर मजकूर भाग.", confidence=52.0, needs_review=True),
        ]
        _, low_conf = clean_and_reassemble(blocks)
        self.assertEqual(len(low_conf), 1)
        self.assertEqual(low_conf[0]["text"], "अस्पष्ट धूसर मजकूर भाग.")
        self.assertEqual(low_conf[0]["confidence"], 52.0)

    def test_empty_blocks_are_dropped(self):
        blocks = [
            OcrBlock(text="   ", confidence=0.0, needs_review=True),
            OcrBlock(text="वास्तविक मजकूर.", confidence=90.0, needs_review=False),
        ]
        cleaned, low_conf = clean_and_reassemble(blocks)
        self.assertEqual(cleaned, "वास्तविक मजकूर.")
        self.assertEqual(low_conf, [])

    def test_no_multiple_consecutive_blank_lines(self):
        blocks = [
            OcrBlock(text="पहिला परिच्छेद.", confidence=90.0, needs_review=False),
            OcrBlock(text="दुसरा परिच्छेद.", confidence=90.0, needs_review=False),
        ]
        cleaned, _ = clean_and_reassemble(blocks)
        self.assertNotIn("\n\n\n", cleaned)


class TestMetadataExtraction(unittest.TestCase):
    # Real header format confirmed elsewhere in this project (e.g. the
    # nutrition/health test draft from the retrieval-observability task).
    SAMPLE_HEADER = (
        "महाराष्ट्र शासन\n"
        "सामान्य प्रशासन विभाग\n"
        "शासन परिपत्रक क्रमांक: जीए-२०२६/प्र.क्र.०१/स्थाप-०१\n"
        "हुतात्मा राजगुरु चौक, मादाम कामा मार्ग, मंत्रालय मुंबई-३२\n"
        "दिनांक: ०६ ऑगस्ट, २०२६\n\n"
        "विषय: राज्यातील सौर ऊर्जेचा वापर वाढवण्यासाठी योजना\n\n"
        "वाचा:\n"
        "१. उद्योग, ऊर्जा व कामगार विभाग क्रमांक: सौरप्र-२०२३/प्र.क्र.९५/ऊर्जा-७\n"
    )

    SAMPLE_HEADER_EN = (
        "GOVERNMENT OF MAHARASHTRA\n"
        "General Administration Department\n"
        "Government Resolution No.: GA-2026/CR.01/EST-01\n"
        "Dated: 06 August, 2026\n\n"
        "Subject: Comprehensive scheme for solar energy adoption\n"
    )

    def test_extract_gr_number_marathi(self):
        result = extract_gr_number(self.SAMPLE_HEADER)
        self.assertIsNotNone(result)
        self.assertIn("जीए", result)

    def test_extract_gr_number_english(self):
        result = extract_gr_number(self.SAMPLE_HEADER_EN)
        self.assertIsNotNone(result)
        self.assertIn("GA", result)

    def test_extract_date_named_marathi(self):
        result = extract_date(self.SAMPLE_HEADER)
        self.assertEqual(result, "06.08.2026")

    def test_extract_date_named_english(self):
        result = extract_date(self.SAMPLE_HEADER_EN)
        self.assertEqual(result, "06.08.2026")

    def test_extract_date_numeric(self):
        text = "Dated: 15.03.2025\nSome other text."
        result = extract_date(text)
        self.assertEqual(result, "15.03.2025")

    def test_extract_date_absent_returns_none(self):
        result = extract_date("No date information anywhere in this text at all.")
        self.assertIsNone(result)

    def test_extract_department_marathi(self):
        result = extract_department(self.SAMPLE_HEADER)
        self.assertIsNotNone(result)
        self.assertIn("General", result)  # canonicalized to the English slug form

    def test_extract_subject_marathi(self):
        result = extract_subject(self.SAMPLE_HEADER)
        self.assertIsNotNone(result)
        self.assertIn("सौर ऊर्जेचा", result)

    def test_extract_subject_english(self):
        result = extract_subject(self.SAMPLE_HEADER_EN)
        self.assertIsNotNone(result)
        self.assertIn("solar energy", result)

    def test_extract_metadata_all_regex_no_llm_fallback(self):
        result = extract_metadata(self.SAMPLE_HEADER)
        self.assertEqual(result["extraction_method"], "regex")
        self.assertIsNotNone(result["gr_number"])
        self.assertIsNotNone(result["date"])
        self.assertIsNotNone(result["subject"])


if __name__ == "__main__":
    unittest.main()
