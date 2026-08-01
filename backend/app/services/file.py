import fitz  # pymupdf
from app.logger import get_logger

log = get_logger(__name__)

# In-memory store: { filename: extracted_text }
uploaded_files: dict[str, str] = {}


def extract_text(filename: str, content: bytes) -> str:
    try:
        if filename.endswith(".txt"):
            text = content.decode("utf-8", errors="ignore").strip()
            log.info(f"Extracted {len(text)} chars from TXT: {filename}")
            return text
        elif filename.endswith(".pdf"):
            text = ""
            with fitz.open(stream=content, filetype="pdf") as doc:
                for page in doc:
                    text += page.get_text()
            text = text.strip()
            log.info(f"Extracted {len(text)} chars from PDF: {filename}")
            return text
    except Exception as e:
        log.error(f"Failed to extract text from {filename}: {e}")
        return ""
    return ""


def build_file_context(filenames: list[str]) -> str:
    parts = []
    for name in filenames:
        text = uploaded_files.get(name, "")
        if text:
            snippet = text[:2000] + ("..." if len(text) > 2000 else "")
            parts.append(f"[File: {name}]\n{snippet}")
        else:
            log.warning(f"File requested in context but not found in store: {name}")
    return "\n\n".join(parts)