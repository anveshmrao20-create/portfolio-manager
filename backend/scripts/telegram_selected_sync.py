import argparse
import os
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv

from backend.app.database import SessionLocal, init_database
from backend.app.models.research import ResearchIngestRequest
from backend.app.services.research_service import ingest_research_documents
from backend.app.services.telegram_service import DOWNLOAD_DIR, fetch_documents, fetch_text_messages


SELECTED_GROUPS = {
    2088923066: "STOCK AAJ OR KAL [ STOCK MARKET INFO ]",
    1487114286: "Beat The Street News| Latest Share Market News",
    1820276185: "Beat The Street Equity Research Reports | Books",
}


def main() -> None:
    load_dotenv(PROJECT_ROOT / ".env")
    parser = argparse.ArgumentParser(description="Fetch and index selected Telegram research groups.")
    parser.add_argument("--api-id", type=int, default=int(os.getenv("TELEGRAM_API_ID", "0")))
    parser.add_argument("--api-hash", default=os.getenv("TELEGRAM_API_HASH", ""))
    parser.add_argument("--days-back", type=int, default=120)
    parser.add_argument("--max-docs-per-group", type=int, default=80)
    parser.add_argument("--max-texts-per-group", type=int, default=40)
    parser.add_argument("--ingest-batch-size", type=int, default=25)
    parser.add_argument("--max-pdf-pages", type=int, default=30)
    args = parser.parse_args()

    if not args.api_id or not args.api_hash:
        raise SystemExit("Set TELEGRAM_API_ID/TELEGRAM_API_HASH or pass --api-id/--api-hash.")

    init_database()
    db = SessionLocal()
    try:
        total_downloaded = 0
        total_ingested = 0
        total_skipped = 0
        for group_id, group_name in SELECTED_GROUPS.items():
            paths = fetch_documents(
                api_id=args.api_id,
                api_hash=args.api_hash,
                group_ids=[group_id],
                group_usernames=[],
                days_back=args.days_back,
                max_docs_per_group=args.max_docs_per_group,
            )
            total_downloaded += len(paths)
            text_paths = fetch_text_messages(
                api_id=args.api_id,
                api_hash=args.api_hash,
                group_ids=[group_id],
                group_usernames=[],
                days_back=args.days_back,
                max_messages_per_group=args.max_texts_per_group,
            )
            total_downloaded += len(text_paths)
            folder = DOWNLOAD_DIR / str(group_id)
            folder.mkdir(parents=True, exist_ok=True)
            result = ingest_research_documents(
                ResearchIngestRequest(
                    source_folder=str(folder),
                    channel_name=group_name,
                    clear_existing=False,
                    max_files=args.ingest_batch_size,
                    max_pdf_pages=args.max_pdf_pages,
                ),
                db,
            )
            total_ingested += result.imported_documents
            total_skipped += result.skipped_files
            print(
                f"{group_id} | docs={len(paths)} | texts={len(text_paths)} | "
                f"ingested={result.imported_documents} | skipped={result.skipped_files}"
            )

        print(
            {
                "total_downloaded": total_downloaded,
                "total_ingested": total_ingested,
                "total_skipped": total_skipped,
            }
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()
