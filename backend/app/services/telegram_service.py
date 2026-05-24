import asyncio
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError

from backend.app.models.research import TelegramGroupItem


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = PROJECT_ROOT / "data"
TELEGRAM_DIR = DATA_DIR / "telegram"
SESSION_FILE = TELEGRAM_DIR / "user.session"
DOWNLOAD_DIR = TELEGRAM_DIR / "downloads"

TELEGRAM_DIR.mkdir(parents=True, exist_ok=True)
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)


_pending_auth: dict[str, object] = {}
PENDING_AUTH_FILE = TELEGRAM_DIR / "pending_auth.json"


def _save_pending_auth(state: dict[str, object]) -> None:
    PENDING_AUTH_FILE.write_text(__import__("json").dumps(state), encoding="utf-8")


def _load_pending_auth() -> dict[str, object]:
    if not PENDING_AUTH_FILE.exists():
        return {}
    try:
        return __import__("json").loads(PENDING_AUTH_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _clear_pending_auth() -> None:
    if PENDING_AUTH_FILE.exists():
        PENDING_AUTH_FILE.unlink(missing_ok=True)


def start_login(api_id: int, api_hash: str, phone_number: str) -> str:
    async def _run() -> str:
        client = TelegramClient(str(SESSION_FILE), api_id, api_hash)
        await client.connect()
        if await client.is_user_authorized():
            await client.disconnect()
            return "already_authorized"
        sent = await client.send_code_request(phone_number)
        _pending_auth["api_id"] = api_id
        _pending_auth["api_hash"] = api_hash
        _pending_auth["phone_number"] = phone_number
        _pending_auth["phone_code_hash"] = sent.phone_code_hash
        _save_pending_auth(_pending_auth)
        await client.disconnect()
        return "code_sent"

    return asyncio.run(_run())


def verify_login(code: str, password: str | None = None) -> str:
    state = _load_pending_auth()
    if not state:
        return "auth_not_started"

    async def _run() -> str:
        client = TelegramClient(str(SESSION_FILE), int(state["api_id"]), str(state["api_hash"]))
        await client.connect()
        try:
            await client.sign_in(
                phone=str(state["phone_number"]),
                code=code,
                phone_code_hash=str(state["phone_code_hash"]),
            )
        except SessionPasswordNeededError:
            if not password:
                await client.disconnect()
                return "password_required"
            await client.sign_in(password=password)
        await client.disconnect()
        _pending_auth.clear()
        _clear_pending_auth()
        return "authorized"

    return asyncio.run(_run())


def list_joined_groups(api_id: int, api_hash: str) -> list[TelegramGroupItem]:
    async def _run() -> list[TelegramGroupItem]:
        client = TelegramClient(str(SESSION_FILE), api_id, api_hash)
        await client.connect()
        if not await client.is_user_authorized():
            await client.disconnect()
            raise PermissionError("Telegram session not authorized")
        dialogs = await client.get_dialogs()
        groups: list[TelegramGroupItem] = []
        for d in dialogs:
            if d.is_group or d.is_channel:
                entity = d.entity
                groups.append(
                    TelegramGroupItem(
                        id=int(entity.id),
                        title=str(getattr(entity, "title", "unknown")),
                        username=getattr(entity, "username", None),
                    )
                )
        await client.disconnect()
        return sorted(groups, key=lambda g: g.title.lower())

    return asyncio.run(_run())


def fetch_documents(
    api_id: int,
    api_hash: str,
    group_ids: list[int],
    group_usernames: list[str],
    days_back: int,
    max_docs_per_group: int,
) -> list[str]:
    async def _run() -> list[str]:
        client = TelegramClient(str(SESSION_FILE), api_id, api_hash)
        await client.connect()
        if not await client.is_user_authorized():
            await client.disconnect()
            raise PermissionError("Telegram session not authorized")

        targets: list[object] = []
        targets.extend(group_ids)
        targets.extend(group_usernames)
        cutoff = datetime.now(timezone.utc) - timedelta(days=days_back)
        downloaded_paths: list[str] = []

        for target in targets:
            count = 0
            async for message in client.iter_messages(target, limit=2000):
                if message.date and message.date < cutoff:
                    continue
                if not message.document:
                    continue
                file_name = _safe_file_name(message.file.name or f"{message.id}.bin")
                ext = Path(file_name).suffix.lower()
                if ext not in {".pdf", ".txt", ".docx"}:
                    continue
                channel_slug = str(target).replace("@", "").replace("/", "_")
                out_dir = DOWNLOAD_DIR / channel_slug
                out_dir.mkdir(parents=True, exist_ok=True)
                out_path = out_dir / f"{message.id}_{file_name}"
                if out_path.exists():
                    continue
                await client.download_media(message, file=str(out_path))
                downloaded_paths.append(str(out_path))
                count += 1
                if count >= max_docs_per_group:
                    break

        await client.disconnect()
        return downloaded_paths

    return asyncio.run(_run())


def fetch_text_messages(
    api_id: int,
    api_hash: str,
    group_ids: list[int],
    group_usernames: list[str],
    days_back: int,
    max_messages_per_group: int,
) -> list[str]:
    async def _run() -> list[str]:
        client = TelegramClient(str(SESSION_FILE), api_id, api_hash)
        await client.connect()
        if not await client.is_user_authorized():
            await client.disconnect()
            raise PermissionError("Telegram session not authorized")

        targets: list[object] = []
        targets.extend(group_ids)
        targets.extend(group_usernames)
        cutoff = datetime.now(timezone.utc) - timedelta(days=days_back)
        saved_paths: list[str] = []

        for target in targets:
            count = 0
            async for message in client.iter_messages(target, limit=2000):
                if message.date and message.date < cutoff:
                    continue
                text = (message.message or "").strip()
                if len(text) < 40:
                    continue
                channel_slug = str(target).replace("@", "").replace("/", "_")
                out_dir = DOWNLOAD_DIR / channel_slug
                out_dir.mkdir(parents=True, exist_ok=True)
                out_path = out_dir / f"{message.id}_message.txt"
                if out_path.exists():
                    continue
                payload = (
                    f"Telegram message id: {message.id}\n"
                    f"Date: {message.date.isoformat() if message.date else ''}\n\n"
                    f"{text}\n"
                )
                out_path.write_text(payload, encoding="utf-8")
                saved_paths.append(str(out_path))
                count += 1
                if count >= max_messages_per_group:
                    break

        await client.disconnect()
        return saved_paths

    return asyncio.run(_run())


def _safe_file_name(value: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", value).strip()
    return cleaned[:180] or "telegram_document.bin"
