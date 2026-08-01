"""Clean, user-facing error types for the upload pipeline.

Every one of these is caught in routes.py and turned into a JSON error
response — never a raw stack trace, since this runs live in front of a
demo audience.
"""


class ExtractionError(Exception):
    """Base class for anything that goes wrong while extracting text
    from an uploaded file. The message is safe to show the user."""


class UnsupportedFileTypeError(ExtractionError):
    pass


class FileTooLargeError(ExtractionError):
    pass


class OcrUnavailableError(ExtractionError):
    """Tesseract itself, or the Marathi language pack, isn't installed
    on this machine. Raised lazily — only when OCR is actually needed —
    so docx/digital-PDF/txt uploads keep working even without Tesseract."""
