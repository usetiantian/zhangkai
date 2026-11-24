"""
文件解析器 — 统一接口，按扩展名分发

支持格式:
  .txt .md .py .js .go .html .css .json .csv  → 直接读
  .pdf                                         → pdfplumber
  .docx                                        → python-docx
  .pptx                                        → python-pptx
  .xlsx .xls                                   → openpyxl
  .png .jpg .jpeg (OCR)                        → 待实现

设计原则（宪法 0.5）:
  - 每种格式独立 parser，挂了不影响其他
  - 缺依赖就装，装不上就报错。不偷偷降级
"""

import os, logging

logger = logging.getLogger("nexus_kb.parser")


def parse(filepath: str) -> dict:
    """
    解析文件为纯文本。
    返回: {"text": str, "metadata": {...}} 或 {"text": "", "error": "..."}
    """
    if not os.path.isfile(filepath):
        return {"text": "", "error": f"Not a file: {filepath}"}

    ext = os.path.splitext(filepath)[1].lower()
    metadata = {
        "filepath": filepath,
        "filename": os.path.basename(filepath),
        "ext": ext,
        "size": os.path.getsize(filepath),
    }

    parser = _PARSERS.get(ext)
    if parser is None:
        # 未知格式，尝试当纯文本读
        return _parse_txt(filepath, metadata)

    try:
        text = parser(filepath)
        return {"text": text, "metadata": metadata}
    except ImportError as e:
        logger.error(f"Missing dependency for {ext}: {e}")
        return {"text": "", "error": str(e), "metadata": metadata}
    except Exception as e:
        logger.warning(f"Parser {ext} failed for {filepath}: {e}, fallback to raw text")
        return _parse_txt(filepath, metadata)


# ========================================
# Parsers
# ========================================

def _parse_txt(path: str, meta: dict = None) -> dict:
    """纯文本：直接读。"""
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        text = f.read()
    return {"text": text, "metadata": meta or {}}


def _parse_pdf(path: str) -> str:
    """PDF：pdfplumber 提取文字。"""
    import pdfplumber
    text_parts = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            t = page.extract_text()
            if t:
                text_parts.append(t)
    return "\n".join(text_parts)


def _parse_docx(path: str) -> str:
    """Word：python-docx 提取段落文字。"""
    from docx import Document
    doc = Document(path)
    parts = []
    for p in doc.paragraphs:
        if p.text.strip():
            parts.append(p.text)
    return "\n".join(parts)


def _parse_pptx(path: str) -> str:
    """PPT：python-pptx 提取幻灯片文字。"""
    from pptx import Presentation
    prs = Presentation(path)
    parts = []
    for i, slide in enumerate(prs.slides, 1):
        parts.append(f"\n--- 幻灯片 {i} ---")
        for shape in slide.shapes:
            if shape.has_text_frame:
                for para in shape.text_frame.paragraphs:
                    t = para.text.strip()
                    if t:
                        parts.append(t)
    return "\n".join(parts)


def _parse_xlsx(path: str) -> str:
    """Excel：openpyxl 提取所有 sheet 内容。"""
    import openpyxl
    wb = openpyxl.load_workbook(path, data_only=True)
    parts = []
    for sheet_name in wb.sheetnames:
        ws = wb[sheet_name]
        parts.append(f"\n--- Sheet: {sheet_name} ---")
        for row in ws.iter_rows(values_only=True):
            row_text = "\t".join(str(c) if c is not None else "" for c in row)
            if row_text.strip():
                parts.append(row_text)
    wb.close()
    return "\n".join(parts)


def _parse_txt_wrapper(path: str) -> str:
    """适配器：让纯文本 parser 适配 {text, metadata} 返回格式。"""
    result = _parse_txt(path)
    return result["text"]


# ========================================
# Parser registry (must come AFTER all function definitions)
# ========================================

_PARSERS = {
    ".txt": _parse_txt_wrapper,
    ".md": _parse_txt_wrapper,
    ".py": _parse_txt_wrapper,
    ".js": _parse_txt_wrapper,
    ".go": _parse_txt_wrapper,
    ".ts": _parse_txt_wrapper,
    ".html": _parse_txt_wrapper,
    ".css": _parse_txt_wrapper,
    ".json": _parse_txt_wrapper,
    ".csv": _parse_txt_wrapper,
    ".yaml": _parse_txt_wrapper,
    ".yml": _parse_txt_wrapper,
    ".xml": _parse_txt_wrapper,
    ".pdf": _parse_pdf,
    ".docx": _parse_docx,
    ".pptx": _parse_pptx,
    ".xlsx": _parse_xlsx,
    ".xls": _parse_xlsx,
}
