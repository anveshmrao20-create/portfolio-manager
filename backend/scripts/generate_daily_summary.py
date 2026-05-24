import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.database import SessionLocal, init_database
from backend.app.services.assistant_service import generate_daily_summary


def main() -> None:
    init_database()
    db = SessionLocal()
    try:
        summary = generate_daily_summary(db)
        print(
            {
                "summary_date": summary.summary_date,
                "headline": summary.headline,
                "points": len(summary.points),
            }
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()
