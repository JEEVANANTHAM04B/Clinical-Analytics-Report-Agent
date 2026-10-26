"""Validate final bytes before a report is marked completed."""
from io import BytesIO
from pypdf import PdfReader


def validate_pdf(data):
    if not isinstance(data, bytes) or not data.startswith(b"%PDF-"):
        raise ValueError("PDF output is missing or malformed")
    reader = PdfReader(BytesIO(data), strict=True)
    if reader.is_encrypted or not reader.pages:
        raise ValueError("PDF has no accessible pages")
    for page in reader.pages:
        if float(page.mediabox.width) <= 0 or float(page.mediabox.height) <= 0:
            raise ValueError("Invalid PDF page geometry")
    return data
