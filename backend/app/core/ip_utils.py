"""
Утилиты для работы с IP-адресами и заголовком X-Forwarded-For (S34-003).

Алгоритм (защита от подделки X-Forwarded-For):
1. Прямой TCP-peer — `request.client.host`.
2. Если `TRUSTED_PROXIES` пусто — X-Forwarded-For игнорируется, возвращается peer.
3. Если peer не входит в `TRUSTED_PROXIES` — заголовок подделан (или прокси не наш),
   возвращается peer. Так атакующий снаружи не может подменить свой IP.
4. Если peer доверенный — X-Forwarded-For разбирается **справа налево**: ближайшие
   к нам доверенные прокси пропускаются, первый недоверенный IP — реальный клиент.
   Левую часть заголовка контролирует клиент, поэтому она отбрасывается.
"""

import ipaddress

from fastapi import Request

from app.config import settings


def _is_trusted_proxy(ip_str: str) -> bool:
    """Проверяет, входит ли IP в `TRUSTED_PROXIES` (поддерживает CIDR)."""
    if not settings.trusted_proxies:
        return False

    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError:
        return False

    for trusted in settings.trusted_proxies:
        try:
            if "/" in trusted:
                if ip in ipaddress.ip_network(trusted, strict=False):
                    return True
            elif ip == ipaddress.ip_address(trusted):
                return True
        except ValueError:
            continue

    return False


def client_ip(request: Request) -> str:
    """Реальный IP клиента с учётом доверенных прокси (S34-003).

    Args:
        request: FastAPI request объект.

    Returns:
        IP-адрес клиента как строка.
    """
    peer = request.client.host if request.client else "unknown"
    forwarded = request.headers.get("x-forwarded-for")

    # Нет заголовка или прокси не настроены — доверяем только TCP-peer'у.
    if not forwarded or not settings.trusted_proxies:
        return peer

    # X-Forwarded-For учитывается, только если к нам пришёл запрос от
    # доверенного прокси. Иначе это попытка подделки — отбрасываем заголовок.
    if not _is_trusted_proxy(peer):
        return peer

    # Справа налево: пропускаем доверенные прокси, первый недоверенный — клиент.
    for raw in reversed(forwarded.split(",")):
        candidate = raw.strip()
        if not candidate:
            continue
        if _is_trusted_proxy(candidate):
            continue
        return candidate

    # Все хопы доверенные — берём самый левый (исходный клиент).
    hops = [item.strip() for item in forwarded.split(",") if item.strip()]
    return hops[0] if hops else peer
