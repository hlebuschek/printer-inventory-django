"""
Сервисный слой для исходящих действий в Okdesk: отправка комментариев,
ленивая (точечная) синхронизация комментариев одной заявки.

Использует личный токен пользователя (`access.UserOkdeskToken`) для
аутентификации в Okdesk API — комментарий пишется от имени этого
пользователя.
"""
import logging

import requests
from django.conf import settings
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from .models import OkdeskComment

logger = logging.getLogger(__name__)


class OkdeskSendError(Exception):
    """Бизнес-ошибка при отправке/синхронизации — текст уходит в UI."""

    def __init__(self, message: str, status_code: int = 500):
        super().__init__(message)
        self.status_code = status_code


def _user_token(user):
    from access.models import UserOkdeskToken

    try:
        return UserOkdeskToken.objects.get(user=user).get_token()
    except UserOkdeskToken.DoesNotExist:
        raise OkdeskSendError(
            "Личный API-токен Okdesk не настроен. Добавьте его в меню пользователя → Токен Okdesk.",
            status_code=403,
        )


def _api_url():
    return getattr(settings, "OKDESK_API_URL", "https://abikom.okdesk.ru/api/v1")


def _save_comment(issue_id: int, raw: dict) -> OkdeskComment:
    """Сохраняет/обновляет комментарий из ответа Okdesk API в локальной БД."""
    author = raw.get("author") or {}
    published_raw = raw.get("published_at") or raw.get("created_at")
    obj, _ = OkdeskComment.objects.update_or_create(
        comment_id=raw["id"],
        defaults={
            "issue_id": issue_id,
            "author_name": author.get("name", "") or "",
            "content": raw.get("content", "") or "",
            "is_public": bool(raw.get("public", True)),
            "created_at": parse_datetime(published_raw) if published_raw else None,
            "synced_at": timezone.now(),
        },
    )
    return obj


def post_comment_to_okdesk(user, issue_id: int, content: str, is_public: bool = True) -> dict:
    """Публикует комментарий в Okdesk от имени пользователя (по его личному токену).

    После успешного POST сохраняет комментарий локально из ответа API.
    Возвращает словарь как `services_okdesk_dashboard.get_issue_detail::comments[]`.
    """
    if not (content or "").strip():
        raise OkdeskSendError("Комментарий не может быть пустым.", status_code=400)
    token = _user_token(user)

    try:
        resp = requests.post(
            f"{_api_url()}/issues/{int(issue_id)}/comments",
            params={"api_token": token},
            json={"comment": {"content": content, "public": bool(is_public)}},
            verify=getattr(settings, "OKDESK_VERIFY_SSL", True),
            timeout=15,
        )
    except requests.Timeout:
        raise OkdeskSendError(
            "Сервер Okdesk не отвечает. Попробуйте повторить через несколько минут.",
            status_code=504,
        )
    except requests.ConnectionError:
        raise OkdeskSendError(
            "Нет соединения с Okdesk. Проверьте сеть и попробуйте позже.",
            status_code=502,
        )

    if resp.status_code == 401:
        raise OkdeskSendError(
            "Неверный API-токен Okdesk. Обновите токен в меню пользователя.",
            status_code=403,
        )
    if resp.status_code == 404:
        raise OkdeskSendError(f"Заявка #{issue_id} не найдена в Okdesk.", status_code=404)
    if not resp.ok:
        try:
            err_body = resp.json()
        except Exception:
            err_body = resp.text[:200]
        raise OkdeskSendError(f"Okdesk API ответил HTTP {resp.status_code}: {err_body}", status_code=502)

    data = resp.json() or {}
    obj = _save_comment(int(issue_id), data)
    return {
        "id": obj.comment_id,
        "author": obj.author_name,
        "content": obj.content,
        "is_public": obj.is_public,
        "created_at": obj.created_at.isoformat() if obj.created_at else None,
    }


def refresh_issue_comments(issue_id: int) -> dict:
    """Точечная синхронизация комментариев одной заявки. Использует
    общий API-токен (settings.OKDESK_API_TOKEN), потому что чтение
    публичных комментариев допустимо для любого пользователя — индивидуальный
    токен не требуется."""
    api_token = getattr(settings, "OKDESK_API_TOKEN", "")
    if not api_token:
        raise OkdeskSendError("OKDESK_API_TOKEN не настроен на сервере.", status_code=503)

    try:
        resp = requests.get(
            f"{_api_url()}/issues/{int(issue_id)}/comments",
            params={"api_token": api_token},
            verify=getattr(settings, "OKDESK_VERIFY_SSL", True),
            timeout=15,
        )
    except requests.RequestException as exc:
        raise OkdeskSendError(f"Ошибка при обращении к Okdesk: {exc}", status_code=502)

    if resp.status_code == 404:
        return {"updated": 0, "comments": []}
    if not resp.ok:
        raise OkdeskSendError(f"Okdesk API ответил HTTP {resp.status_code}", status_code=502)

    items = resp.json() or []
    out = []
    for item in items:
        if not item.get("id"):
            continue
        obj = _save_comment(int(issue_id), item)
        out.append(
            {
                "id": obj.comment_id,
                "author": obj.author_name,
                "content": obj.content,
                "is_public": obj.is_public,
                "created_at": obj.created_at.isoformat() if obj.created_at else None,
            }
        )
    out.sort(key=lambda c: c["created_at"] or "")
    return {"updated": len(out), "comments": out}
