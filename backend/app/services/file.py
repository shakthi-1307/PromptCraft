import fitz  # pymupdf

# In-memory store: { filename: extracted_text }
uploaded_files: dict[str, str] = {}


def extract_text(filename: str, content: bytes) -> str:
    if filename.endswith(".txt"):
        return content.decode("utf-8", errors="ignore").strip()
    elif filename.endswith(".pdf"):
        text = ""
        with fitz.open(stream=content, filetype="pdf") as doc:
            for page in doc:
                text += page.get_text()
        return text.strip()
    return ""


def build_file_context(filenames: list[str]) -> str:
    parts = []
    for name in filenames:
        text = uploaded_files.get(name, "")
        if text:
            snippet = text[:2000] + ("..." if len(text) > 2000 else "")
            parts.append(f"[File: {name}]\n{snippet}")
    return "\n\n".join(parts)