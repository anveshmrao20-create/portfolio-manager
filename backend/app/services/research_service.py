import json
import re
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from backend.app.database.models import (
    HoldingRecord,
    ResearchChunkRecord,
    ResearchDocumentRecord,
    ResearchIngestJobRecord,
)
from backend.app.models.research import (
    ResearchDocumentItem,
    ResearchIngestRequest,
    ResearchIngestResult,
    ResearchSearchHit,
    ResearchSearchRequest,
    ResearchSearchResponse,
)

try:
    from pypdf import PdfReader  # type: ignore
except Exception:
    PdfReader = None


def ingest_research_documents(payload: ResearchIngestRequest, db: Session) -> ResearchIngestResult:
    folder = Path(payload.source_folder)
    if not folder.exists() or not folder.is_dir():
        raise ValueError(f"Invalid folder path: {folder}")

    patterns = ("*.pdf", "*.txt")
    files = []
    for pat in patterns:
        files.extend(folder.rglob(pat))
    files = sorted(files)

    errors: list[str] = []
    job = ResearchIngestJobRecord(
        source_folder=str(folder),
        source_type="telegram",
        total_files=len(files),
        imported_documents=0,
        skipped_files=0,
        errors_json="[]",
    )
    db.add(job)
    db.flush()

    if payload.clear_existing:
        db.execute(delete(ResearchChunkRecord))
        db.execute(delete(ResearchDocumentRecord))

    holding_symbols = {
        h.symbol.upper().strip()
        for h in db.execute(select(HoldingRecord).where(HoldingRecord.is_cash_reserve == False)).scalars().all()  # noqa: E712
    }

    imported = 0
    skipped = 0
    attempted_new_files = 0
    for file_path in files:
        try:
            existing = db.execute(
                select(ResearchDocumentRecord).where(ResearchDocumentRecord.file_path == str(file_path))
            ).scalar_one_or_none()
            if existing is not None:
                continue
            if attempted_new_files >= payload.max_files:
                break
            attempted_new_files += 1
            content = _extract_text(file_path, payload.max_pdf_pages)
            if not content or len(content.strip()) < 40:
                skipped += 1
                continue
            symbols = _extract_symbols(content, holding_symbols)
            doc = ResearchDocumentRecord(
                source_type="telegram",
                channel_name=payload.channel_name or file_path.parent.name,
                source_message_id=None,
                file_name=file_path.name,
                file_path=str(file_path),
                file_type=file_path.suffix.lower().lstrip("."),
                content_text=content,
                symbols_csv=",".join(symbols),
                ingest_job_id=job.id,
            )
            db.add(doc)
            db.flush()

            for idx, chunk in enumerate(_chunk_text(content, 1200, 250)):
                chunk_symbols = _extract_symbols(chunk, holding_symbols)
                db.add(
                    ResearchChunkRecord(
                        document_id=doc.id,
                        chunk_index=idx,
                        chunk_text=chunk,
                        symbols_csv=",".join(chunk_symbols),
                    )
                )
            imported += 1
        except Exception as exc:
            skipped += 1
            errors.append(f"{file_path.name}: {exc}")

    job.imported_documents = imported
    job.skipped_files = skipped
    job.errors_json = json.dumps(errors[:200])
    db.add(job)
    db.commit()
    db.refresh(job)

    return ResearchIngestResult(
        ingest_job_id=job.id,
        total_files=job.total_files,
        imported_documents=job.imported_documents,
        skipped_files=job.skipped_files,
        errors=errors[:50],
        created_at=job.created_at,
    )


def search_research(payload: ResearchSearchRequest, db: Session) -> ResearchSearchResponse:
    query = payload.query.strip().lower()
    symbol_filter = payload.symbol.strip().upper() if payload.symbol else None
    rows = db.execute(select(ResearchChunkRecord).order_by(ResearchChunkRecord.created_at.desc())).scalars().all()

    hits: list[ResearchSearchHit] = []
    for row in rows:
        text = row.chunk_text or ""
        lower = text.lower()
        if query not in lower:
            continue
        symbols = [s for s in (row.symbols_csv or "").split(",") if s]
        if symbol_filter and symbol_filter not in symbols:
            continue
        doc = db.get(ResearchDocumentRecord, row.document_id)
        if doc is None:
            continue
        score = float(lower.count(query))
        snippet = _snippet(text, query, 240)
        hits.append(
            ResearchSearchHit(
                document_id=doc.id,
                file_name=doc.file_name,
                channel_name=doc.channel_name,
                symbols=symbols,
                snippet=snippet,
                score=score,
            )
        )

    hits.sort(key=lambda h: h.score, reverse=True)
    limited = hits[: payload.limit]
    return ResearchSearchResponse(total_hits=len(hits), hits=limited)


def list_research_documents(db: Session, limit: int = 200) -> list[ResearchDocumentItem]:
    docs = (
        db.execute(select(ResearchDocumentRecord).order_by(ResearchDocumentRecord.created_at.desc()))
        .scalars()
        .all()[:limit]
    )
    return [
        ResearchDocumentItem(
            document_id=d.id,
            channel_name=d.channel_name,
            file_name=d.file_name,
            file_type=d.file_type,
            symbols=[s for s in (d.symbols_csv or "").split(",") if s],
            created_at=d.created_at,
        )
        for d in docs
    ]


def _extract_text(file_path: Path, max_pdf_pages: int) -> str:
    suffix = file_path.suffix.lower()
    if suffix == ".txt":
        return file_path.read_text(encoding="utf-8", errors="ignore")
    if suffix == ".pdf":
        if PdfReader is None:
            raise RuntimeError("pypdf not installed for PDF extraction")
        reader = PdfReader(str(file_path))
        texts = []
        for index, page in enumerate(reader.pages):
            if index >= max_pdf_pages:
                break
            texts.append(page.extract_text() or "")
        return "\n".join(texts)
    return ""


def _extract_symbols(text: str, holding_symbols: set[str]) -> list[str]:
    tokens = set(re.findall(r"\b[A-Z]{2,15}\b", text.upper()))
    matched = sorted(token for token in tokens if token in holding_symbols)
    return matched


def _chunk_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    clean = " ".join(text.split())
    if len(clean) <= chunk_size:
        return [clean]
    chunks: list[str] = []
    start = 0
    while start < len(clean):
        end = start + chunk_size
        chunks.append(clean[start:end])
        if end >= len(clean):
            break
        start = max(0, end - overlap)
    return chunks


def _snippet(text: str, query: str, width: int) -> str:
    lower = text.lower()
    idx = lower.find(query.lower())
    if idx < 0:
        return text[:width]
    left = max(0, idx - width // 3)
    right = min(len(text), left + width)
    return text[left:right]
