"""
텔레그램 발송 스텁.

실제 토큰/채팅방 ID를 설정하기 전까지는 안전하게 스킵한다.
나중에 아래 환경변수만 채우면 실제 발송으로 전환할 수 있다.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

from loguru import logger


def is_configured() -> bool:
    return bool(os.getenv("TELEGRAM_BOT_TOKEN") and os.getenv("TELEGRAM_CHAT_ID"))


def get_config_help() -> str:
    return (
        "TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID 환경변수를 설정하면 "
        "일간 브리핑 자동 발송을 활성화할 수 있습니다."
    )


def send_message(text: str) -> bool:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        logger.info("[텔레그램] 설정 없음 → 발송 스킵")
        return False

    payload = json.dumps(
        {
            "chat_id": chat_id,
            "text": text,
            "disable_web_page_preview": True,
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            status_code = getattr(response, "status", 200)
            if 200 <= status_code < 300:
                logger.info("[텔레그램] 발송 성공")
                return True
            logger.warning("[텔레그램] 비정상 응답: {}", status_code)
            return False
    except urllib.error.URLError as exc:
        logger.error("[텔레그램] 발송 실패: {}", exc)
        return False
