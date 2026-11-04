import io
import os
import re


def _txt(data: bytes) -> str:
    for enc in ("utf-8-sig", "utf-16", "latin-1"):
        try:
            return data.decode(enc)
        except (UnicodeDecodeError, UnicodeError):
            continue
    return data.decode("utf-8", errors="replace")


def _pdf(data: bytes) -> str:
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(data))
    pages = []
    for page in reader.pages:
        t = page.extract_text() or ""
        # PDFs hard-wrap lines inside a sentence: join lines that don't end a sentence
        t = re.sub(r"(?<![.!?:])\n(?!\n)", " ", t)
        pages.append(t)
    return "\n\n".join(pages)


def _docx(data: bytes) -> str:
    import docx
    document = docx.Document(io.BytesIO(data))
    parts = [p.text for p in document.paragraphs]
    for table in document.tables:
        for row in table.rows:
            for cell in row.cells:
                parts.append(cell.text)
    return "\n".join(parts)


def extract_text(filename: str, data: bytes) -> str:
    ext = os.path.splitext(filename)[1].lower()
    if ext == ".txt":
        return _txt(data)
    if ext == ".pdf":
        return _pdf(data)
    if ext == ".docx":
        return _docx(data)
    raise ValueError(f"Unsupported file type: {ext}")
