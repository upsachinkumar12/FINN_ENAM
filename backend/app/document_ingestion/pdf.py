"""Download, extract and chunk primary-source PDFs. Downloaded files are untrusted data:
their text is only ever passed to models as quoted document content, never as instructions."""
import hashlib
import re
from dataclasses import dataclass

import pymupdf

from app.config import settings
from app.utils.http import SourceError, get

MAX_PDF_BYTES = 60 * 1024 * 1024
CHUNK_CHARS = 1400
CHUNK_OVERLAP = 200
_WORD = re.compile(r"[A-Za-z]{3,}")
# Words OCR typically mangles in Indian results filings; seeing the mangled form marks a bad text layer.
_OCR_TELLS = re.compile(r"\b(Bonk|Bnnk|Tower\.|Corpornte|Operotinq|lndia|Limlted|Proflt)\b")


def _cache_path(url: str):
    return settings.docs_dir / (hashlib.sha1(url.encode()).hexdigest() + ".pdf")


def download(url: str) -> bytes:
    p = _cache_path(url)
    if p.exists():
        return p.read_bytes()
    r = get(url, headers={"Referer": "https://www.bseindia.com/", "Accept": "application/pdf,*/*"})
    data = r.content
    if not data.startswith(b"%PDF"):
        raise SourceError("The link did not return a PDF")
    if len(data) > MAX_PDF_BYTES:
        raise SourceError("PDF is larger than 60 MB; skipped")
    p.write_bytes(data)
    return data


@dataclass
class Page:
    number: int  # 1-indexed, as printed by PDF viewers
    text: str


def clean(text: str) -> str:
    text = text.replace(" ", " ").replace("�", "'")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_pages(data: bytes) -> list[Page]:
    with pymupdf.open(stream=data, filetype="pdf") as doc:
        return [Page(i + 1, clean(pg.get_text())) for i, pg in enumerate(doc)]


def text_quality(pages: list[Page]) -> str:
    """'good', 'ocr' (a scanned text layer: words exist but are unreliable) or 'none' (image only)."""
    chars = sum(len(p.text) for p in pages)
    if not pages or chars / len(pages) < 80:
        return "none"
    sample = " ".join(p.text for p in pages[:6])
    if len(_OCR_TELLS.findall(sample)) >= 2:
        return "ocr"
    return "good"


def page_as_pdf(data: bytes, page_number: int) -> bytes:
    """A single page cut out as its own PDF, for the model to read visually when text is unreliable."""
    with pymupdf.open(stream=data, filetype="pdf") as src, pymupdf.open() as out:
        out.insert_pdf(src, from_page=page_number - 1, to_page=page_number - 1)
        return out.tobytes()


def chunk_pages(pages: list[Page]) -> list[tuple[int, str]]:
    """Chunks never cross a page boundary, so every chunk has exactly one true page number."""
    out: list[tuple[int, str]] = []
    for p in pages:
        t = p.text
        if len(_WORD.findall(t)) < 8:
            continue
        start = 0
        while start < len(t):
            end = min(len(t), start + CHUNK_CHARS)
            if end < len(t):
                cut = t.rfind("\n", start + CHUNK_CHARS // 2, end)
                end = cut if cut > 0 else end
            out.append((p.number, t[start:end].strip()))
            if end >= len(t):
                break
            start = max(end - CHUNK_OVERLAP, start + 1)
    return out


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
