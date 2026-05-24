import json
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.database.models import HoldingRecord, ImportJobRecord
from backend.app.ingestion.holdings.normalizer import is_cash_reserve
from backend.app.ingestion.holdings.parser_groww import parse_groww_excel
from backend.app.ingestion.holdings.parser_zerodha import parse_zerodha_csv
from backend.app.schemas.holdings_import import (
    HoldingsImportRequest,
    HoldingsImportResult,
    HoldingsSnapshotResponse,
    ImportErrorRow,
    ImportedHolding,
)


def import_holdings(payload: HoldingsImportRequest, db: Session) -> HoldingsImportResult:
    source_path = Path(payload.file_path)
    if not source_path.exists():
        raise FileNotFoundError(f"File not found: {source_path}")
    if not source_path.is_file():
        raise ValueError(f"Path is not a file: {source_path}")

    records, parse_errors = _parse_input(payload, str(source_path))
    errors: list[ImportErrorRow] = [ImportErrorRow(row_number=row, message=msg) for row, msg in parse_errors]

    job = ImportJobRecord(
        source_path=str(source_path),
        source_format=source_path.suffix.lower().lstrip("."),
        broker=payload.broker,
        asset_type=payload.asset_type,
        replace_existing=payload.replace_existing,
        total_rows=len(records) + len(errors),
        imported_rows=0,
        skipped_rows=len(errors),
        errors_json="[]",
    )
    db.add(job)
    db.flush()

    if payload.replace_existing:
        existing_rows = db.execute(
            select(HoldingRecord).where(
                HoldingRecord.broker == payload.broker,
                HoldingRecord.asset_type == payload.asset_type,
            )
        ).scalars()
        for row in existing_rows:
            db.delete(row)

    imported_count = 0
    for row in records:
        cash_reserve = is_cash_reserve(row.symbol, row.name)
        db.add(
            HoldingRecord(
                symbol=row.symbol,
                name=row.name,
                isin=row.isin,
                broker=payload.broker,
                asset_type=payload.asset_type,
                quantity=row.quantity,
                average_price=row.average_price,
                buy_value=row.buy_value,
                closing_price=row.closing_price,
                closing_value=row.closing_value,
                unrealised_pnl=row.unrealised_pnl,
                is_cash_reserve=cash_reserve,
                reserve_for=payload.asset_type if cash_reserve else None,
                import_job_id=job.id,
            )
        )
        imported_count += 1

    job.imported_rows = imported_count
    job.skipped_rows = len(errors)
    job.errors_json = json.dumps([error.model_dump() for error in errors])
    db.add(job)
    db.commit()
    db.refresh(job)

    return HoldingsImportResult(
        import_job_id=job.id,
        source_path=job.source_path,
        broker=job.broker,  # type: ignore[arg-type]
        asset_type=job.asset_type,  # type: ignore[arg-type]
        total_rows=job.total_rows,
        imported_rows=job.imported_rows,
        skipped_rows=job.skipped_rows,
        errors=errors,
        created_at=job.created_at,
    )


def get_holdings_snapshot(db: Session) -> HoldingsSnapshotResponse:
    rows = db.execute(select(HoldingRecord).order_by(HoldingRecord.created_at.desc())).scalars().all()
    holdings = [
        ImportedHolding(
            symbol=row.symbol,
            name=row.name,
            isin=row.isin,
            broker=row.broker,
            asset_type=row.asset_type,
            quantity=row.quantity,
            average_price=row.average_price,
            buy_value=row.buy_value,
            closing_price=row.closing_price,
            closing_value=row.closing_value,
            unrealised_pnl=row.unrealised_pnl,
            is_cash_reserve=row.is_cash_reserve,
            reserve_for=row.reserve_for,
        )
        for row in rows
    ]
    return HoldingsSnapshotResponse(holdings=holdings)


def _parse_input(payload: HoldingsImportRequest, file_path: str):
    if payload.broker == "zerodha":
        return parse_zerodha_csv(file_path)
    return parse_groww_excel(file_path)
