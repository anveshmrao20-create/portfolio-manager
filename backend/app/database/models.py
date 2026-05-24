from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.database.base import Base


class HoldingRecord(Base):
    __tablename__ = "holdings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    name: Mapped[str | None] = mapped_column(String(256))
    isin: Mapped[str | None] = mapped_column(String(32), index=True)
    broker: Mapped[str] = mapped_column(String(32), index=True)
    asset_type: Mapped[str] = mapped_column(String(16), index=True)
    quantity: Mapped[float] = mapped_column(Float)
    average_price: Mapped[float] = mapped_column(Float)
    buy_value: Mapped[float] = mapped_column(Float)
    closing_price: Mapped[float | None] = mapped_column(Float)
    closing_value: Mapped[float | None] = mapped_column(Float)
    unrealised_pnl: Mapped[float | None] = mapped_column(Float)
    is_cash_reserve: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    reserve_for: Mapped[str | None] = mapped_column(String(16))
    import_job_id: Mapped[int] = mapped_column(Integer, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )


class ImportJobRecord(Base):
    __tablename__ = "import_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_path: Mapped[str] = mapped_column(Text)
    source_format: Mapped[str] = mapped_column(String(16))
    broker: Mapped[str] = mapped_column(String(32))
    asset_type: Mapped[str] = mapped_column(String(16))
    replace_existing: Mapped[bool] = mapped_column(Boolean, default=True)
    total_rows: Mapped[int] = mapped_column(Integer, default=0)
    imported_rows: Mapped[int] = mapped_column(Integer, default=0)
    skipped_rows: Mapped[int] = mapped_column(Integer, default=0)
    errors_json: Mapped[str] = mapped_column(Text, default="[]")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )


class ResearchDocumentRecord(Base):
    __tablename__ = "research_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_type: Mapped[str] = mapped_column(String(32), index=True, default="telegram")
    channel_name: Mapped[str | None] = mapped_column(String(256), index=True)
    source_message_id: Mapped[str | None] = mapped_column(String(64), index=True)
    file_name: Mapped[str] = mapped_column(String(512), index=True)
    file_path: Mapped[str] = mapped_column(Text)
    file_type: Mapped[str] = mapped_column(String(16), index=True)
    content_text: Mapped[str] = mapped_column(Text)
    symbols_csv: Mapped[str] = mapped_column(Text, default="")
    ingest_job_id: Mapped[int] = mapped_column(Integer, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )


class ResearchChunkRecord(Base):
    __tablename__ = "research_chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(Integer, index=True)
    chunk_index: Mapped[int] = mapped_column(Integer)
    chunk_text: Mapped[str] = mapped_column(Text)
    symbols_csv: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )


class ResearchIngestJobRecord(Base):
    __tablename__ = "research_ingest_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_folder: Mapped[str] = mapped_column(Text)
    source_type: Mapped[str] = mapped_column(String(32), index=True, default="telegram")
    total_files: Mapped[int] = mapped_column(Integer, default=0)
    imported_documents: Mapped[int] = mapped_column(Integer, default=0)
    skipped_files: Mapped[int] = mapped_column(Integer, default=0)
    errors_json: Mapped[str] = mapped_column(Text, default="[]")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
