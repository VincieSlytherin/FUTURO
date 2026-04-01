from __future__ import annotations

from pathlib import Path

from dotenv import set_key
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.config import PROJECT_ROOT, settings
from app.deps import AuthDep
from app.notifications import EmailNotificationService, notifications_enabled

router = APIRouter(prefix="/api/notifications", tags=["notifications"])
ENV_PATH = PROJECT_ROOT / ".env"


class NotificationConfigRequest(BaseModel):
    notify_email: str = ""
    gmail_app_password: str = ""


class NotificationTestRequest(BaseModel):
    kind: str
    notify_email: str = ""
    gmail_app_password: str = ""


def _ensure_env_file() -> None:
    if not ENV_PATH.exists():
        Path(ENV_PATH).write_text("", encoding="utf-8")


def _set_env(key: str, value: str) -> None:
    _ensure_env_file()
    set_key(str(ENV_PATH), key, value, quote_mode="never")


def _payload() -> dict:
    return {
        "notify_email": settings.notify_email,
        "gmail_app_password_configured": bool(settings.gmail_app_password.strip()),
        "notifications_enabled": notifications_enabled(),
        "weekly_digest_schedule": "Every Monday at 8:00 AM (local time)",
    }


@router.get("")
async def get_notifications(_: AuthDep):
    return _payload()


@router.put("")
async def update_notifications(body: NotificationConfigRequest, _: AuthDep):
    email = body.notify_email.strip()
    password = "".join(body.gmail_app_password.split())

    _set_env("NOTIFY_EMAIL", email)
    settings.notify_email = email

    if password:
        _set_env("GMAIL_APP_PASSWORD", password)
        settings.gmail_app_password = password

    return {"saved": True, **_payload()}


@router.post("/test")
async def send_test_notification(body: NotificationTestRequest, _: AuthDep):
    kind = body.kind.strip().lower()
    email = body.notify_email.strip() or settings.notify_email
    password = "".join(body.gmail_app_password.split()) or settings.gmail_app_password

    if kind not in {"scout", "digest"}:
        raise HTTPException(400, "Notification kind must be 'scout' or 'digest'")

    if not notifications_enabled(email, password):
        raise HTTPException(400, "Set NOTIFY_EMAIL and a Gmail App Password first")

    service = EmailNotificationService()

    if kind == "scout":
        jobs = await service.build_test_scout_jobs()
        sent = await service.send_scout_run_summary(
            config_name="Scout test",
            search_term="Applied AI Engineer",
            location="Remote",
            min_score=70,
            jobs_found=max(3, len(jobs)),
            jobs_new=len(jobs),
            jobs_scored=len(jobs),
            jobs=jobs,
            recipient_email=email,
            gmail_password=password,
            test_mode=True,
        )
    else:
        sent = await service.send_weekly_digest(
            recipient_email=email,
            gmail_password=password,
            test_mode=True,
        )

    if not sent:
        raise HTTPException(400, "Notifications are not configured")

    return {
        "sent": True,
        "kind": kind,
        "notify_email": email,
        "message": f"Sent a test {kind} email to {email}.",
    }
