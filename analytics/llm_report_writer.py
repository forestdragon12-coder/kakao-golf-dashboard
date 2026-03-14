"""
LLM 기반 리포트 작성기 스텁.

현재 단계에서는 OpenAI Responses API를 직접 호출한다.
실패 시 deterministic fallback으로 즉시 전환한다.
"""
from __future__ import annotations

import json
import os
import ssl
import urllib.error
import urllib.request
from pathlib import Path
import re

import certifi
from loguru import logger

from analytics.report_generator import (
    render_daily_text_report,
    render_monthly_text_report,
    render_weekly_text_report,
    render_yearly_text_report,
)

_ENV_LOADED = False
_REPORT_TERMINATOR = "[보고서 종료]"
_REPORT_SECTION_HEADERS = {
    "daily": [
        "1. 오늘의 한 줄 결론",
        "2. 오늘의 가격 변화",
        "3. 오늘의 판매 흐름 변화",
        "4. 베르힐CC 오늘 포인트",
        "5. 오늘의 핵심 액션",
        "6. 내일 확인 포인트",
    ],
    "weekly": [
        "1. 주간 총평",
        "2. 가격 변화 요약",
        "3. 판매 흐름 요약",
        "4. 베르힐CC 집중 분석",
        "5. 경쟁 골프장 비교",
        "6. 핵심 운영 액션",
        "7. 다음 주 확인 포인트",
    ],
    "monthly": [
        "0. 용어 해설",
        "1. 월간 총평",
        "2. 체급/할인 구조 요약",
        "3. 구조적 약세 및 방어 구간",
        "4. 정책 제안",
        "5. 판단 보류 / 추가 확인 과제",
    ],
    "yearly": [
        "0. 용어 해설",
        "1. 연간 결론",
        "2. 체급 구조와 할인 구조 해석",
        "3. 가격/공급 정책 회고",
        "4. 내년 실행 제안",
        "5. 판단 보류 / 추가 데이터 과제",
    ],
}
_REPORT_SECTION_BATCHES = {
    "daily": [
        ["1. 오늘의 한 줄 결론", "2. 오늘의 가격 변화"],
        ["3. 오늘의 판매 흐름 변화", "4. 베르힐CC 오늘 포인트"],
        ["5. 오늘의 핵심 액션", "6. 내일 확인 포인트"],
    ],
    "weekly": [
        ["1. 주간 총평", "2. 가격 변화 요약"],
        ["3. 판매 흐름 요약", "4. 베르힐CC 집중 분석"],
        ["5. 경쟁 골프장 비교", "6. 핵심 운영 액션"],
        ["7. 다음 주 확인 포인트"],
    ],
    "monthly": [
        ["1. 월간 총평", "2. 체급/할인 구조 요약"],
        ["3. 구조적 약세 및 방어 구간", "4. 정책 제안"],
        ["5. 판단 보류 / 추가 확인 과제"],
    ],
    "yearly": [
        ["1. 연간 결론", "2. 체급 구조와 할인 구조 해석"],
        ["3. 가격/공급 정책 회고", "4. 내년 실행 제안"],
        ["5. 판단 보류 / 추가 데이터 과제"],
    ],
}
_INTERNAL_TERMS = (
    "management_snapshot",
    "course_comparisons",
    "strategy_profiles",
    "promo_ratio",
    "discount_dependency",
    "discount_amplification",
    "response_grade",
    "signal_ratio",
    "open_slots",
    "weakness_signals",
    "defense_signals",
)


def _load_local_env() -> None:
    global _ENV_LOADED
    if _ENV_LOADED:
        return

    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            os.environ.setdefault(key, value)
    _ENV_LOADED = True


def is_llm_enabled() -> bool:
    _load_local_env()
    return os.getenv("REPORT_LLM_ENABLED", "false").lower() == "true"


def get_prompt_template(report_type: str) -> str:
    templates = {
        "daily": "daily_prompt_v4_focus_today",
        "weekly": "weekly_prompt_pro_v4_price_flow",
        "monthly": "monthly_prompt_pro_v3_sectioned",
        "yearly": "yearly_prompt_pro_v3_sectioned",
    }
    return templates.get(report_type, "unknown_prompt")


def get_model_for_report_type(report_type: str) -> str | None:
    _load_local_env()
    specific_key = f"REPORT_LLM_MODEL_{report_type.upper()}"
    return os.getenv(specific_key) or os.getenv("REPORT_LLM_MODEL")


def _get_llm_setting(report_type: str, key: str, default: str) -> str:
    _load_local_env()
    specific_key = f"{key}_{report_type.upper()}"
    return os.getenv(specific_key) or os.getenv(key, default)


def render_report(payload: dict, prefer_llm: bool = True) -> tuple[str, dict]:
    """
    Returns:
      (text, meta)

    meta example:
      {
        "used_llm": False,
        "report_type": "daily",
        "prompt_template": "daily_prompt_v1",
        "fallback_reason": "llm_disabled"
      }
    """
    report_type = payload.get("report_type", "daily")
    prompt_template = get_prompt_template(report_type)

    if not prefer_llm or not is_llm_enabled():
        return _finalize_rendered_report(_fallback_render(payload), payload), {
            "used_llm": False,
            "report_type": report_type,
            "prompt_template": prompt_template,
            "fallback_reason": "llm_disabled" if not is_llm_enabled() else "prefer_llm_false",
        }

    api_key = os.getenv("OPENAI_API_KEY")
    model = get_model_for_report_type(report_type)
    if not api_key:
        return _finalize_rendered_report(_fallback_render(payload), payload), {
            "used_llm": False,
            "report_type": report_type,
            "prompt_template": prompt_template,
            "fallback_reason": "missing_openai_api_key",
        }
    if not model:
        return _finalize_rendered_report(_fallback_render(payload), payload), {
            "used_llm": False,
            "report_type": report_type,
            "prompt_template": prompt_template,
            "fallback_reason": "missing_report_llm_model",
        }

    try:
        text = _generate_report_text(payload, model=model, api_key=api_key)
        invalid_reason = _validate_rendered_report(text, report_type)
        if invalid_reason:
            logger.warning("[LLM] 보고서 품질 검증 실패, fallback 사용: {}", invalid_reason)
            return _finalize_rendered_report(_fallback_render(payload), payload), {
                "used_llm": False,
                "report_type": report_type,
                "prompt_template": prompt_template,
                "fallback_reason": f"llm_invalid_output:{invalid_reason}",
                "model": model,
            }
        return _finalize_rendered_report(text, payload), {
            "used_llm": True,
            "report_type": report_type,
            "prompt_template": prompt_template,
            "fallback_reason": None,
            "model": model,
        }
    except Exception as exc:
        logger.error("[LLM] 보고서 생성 실패, fallback 사용: {}", exc)
        return _finalize_rendered_report(_fallback_render(payload), payload), {
            "used_llm": False,
            "report_type": report_type,
            "prompt_template": prompt_template,
            "fallback_reason": f"llm_error:{type(exc).__name__}",
            "model": model,
        }


def _fallback_render(payload: dict) -> str:
    report_type = payload.get("report_type", "daily")
    if report_type == "daily":
        return render_daily_text_report(payload)
    if report_type == "weekly":
        return render_weekly_text_report(payload)
    if report_type == "monthly":
        return render_monthly_text_report(payload)
    if report_type == "yearly":
        return render_yearly_text_report(payload)
    raise ValueError(f"unsupported report_type: {report_type}")


def _generate_report_text(payload: dict, *, model: str, api_key: str) -> str:
    report_type = payload.get("report_type", "daily")
    if _use_sectioned_rendering(report_type):
        try:
            return _render_report_in_sections(payload, model=model, api_key=api_key)
        except Exception as exc:
            logger.warning("[LLM] 섹션 분할 생성 실패, 단일 호출로 재시도: {}", exc)
    return _call_openai_responses_api(payload, model=model, api_key=api_key)


def _call_openai_responses_api(payload: dict, *, model: str, api_key: str) -> str:
    report_type = payload.get("report_type", "daily")
    base_url = os.getenv("REPORT_LLM_BASE_URL", "https://api.openai.com/v1/responses")
    timeout = float(_get_llm_setting(report_type, "REPORT_LLM_TIMEOUT_SEC", "20"))
    max_output_tokens = int(_get_llm_setting(report_type, "REPORT_LLM_MAX_TOKENS", "4000"))

    request_body = {
        "model": model,
        "instructions": _build_system_instructions(report_type, model),
        "input": _build_user_prompt(payload, model),
        "max_output_tokens": max_output_tokens,
    }

    return _call_openai_request(
        base_url=base_url,
        request_body=request_body,
        api_key=api_key,
        timeout=timeout,
    )


def _call_openai_request(*, base_url: str, request_body: dict, api_key: str, timeout: float) -> str:
    request = urllib.request.Request(
        base_url,
        data=json.dumps(request_body, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    ssl_context = ssl.create_default_context(cafile=certifi.where())

    with urllib.request.urlopen(request, timeout=timeout, context=ssl_context) as response:
        raw = response.read().decode("utf-8")
        data = json.loads(raw)
    _raise_if_response_incomplete(data)
    return _extract_response_text(data)


def _render_report_in_sections(payload: dict, *, model: str, api_key: str) -> str:
    report_type = payload.get("report_type", "daily")
    batches = _REPORT_SECTION_BATCHES.get(report_type)
    if not batches:
        raise ValueError(f"sectioned rendering not configured for {report_type}")

    base_url = os.getenv("REPORT_LLM_BASE_URL", "https://api.openai.com/v1/responses")
    timeout = float(_get_llm_setting(report_type, "REPORT_LLM_TIMEOUT_SEC", "20"))
    total_max_tokens = int(_get_llm_setting(report_type, "REPORT_LLM_MAX_TOKENS", "4000"))
    batch_max_tokens = _get_section_batch_max_tokens(report_type, model, total_max_tokens, len(batches))
    section_timeout = _get_section_timeout_sec(report_type, model, timeout)

    chunks: list[str] = []
    if report_type in {"monthly", "yearly"}:
        chunks.append(_render_glossary_section(payload))
    for index, headers in enumerate(batches):
        is_final = index == len(batches) - 1
        request_body = {
            "model": model,
            "instructions": _build_section_system_instructions(report_type, model, headers, is_final),
            "input": _build_section_user_prompt(payload, model, headers, is_final),
            "max_output_tokens": batch_max_tokens,
        }
        chunk = _call_openai_request_with_retry(
            base_url=base_url,
            request_body=request_body,
            api_key=api_key,
            timeout=section_timeout,
            retry_timeout=max(section_timeout * 1.5, section_timeout + 30),
        )
        invalid_reason = _validate_report_chunk(chunk, headers, is_final=is_final)
        if invalid_reason:
            raise ValueError(f"invalid_chunk:{invalid_reason}")
        chunks.append(chunk.strip())
    return "\n\n".join(part for part in chunks if part.strip())


def _build_system_instructions(report_type: str, model: str) -> str:
    report_goal = {
        "daily": "오늘 바로 실행할 운영 판단을 빠르게 정리한다.",
        "weekly": "이번 주 구조 변화와 다음 주 실행 우선순위를 정리한다.",
        "monthly": "월간 구조 변화와 정책 방향을 경영진 관점에서 정리한다.",
        "yearly": "연간 회고와 내년 운영 전략을 정책 수준에서 정리한다.",
    }.get(report_type, "운영 보고서를 정리한다.")
    reasoning_mode = (
        "긴 호흡의 구조 해석과 비교 정리를 수행하되, 중간 추론은 쓰지 말고 결론만 보고서 문장으로 남겨라."
        if model.endswith("-pro")
        else "판단 속도를 우선하되, 결론의 근거는 짧고 명확하게 남겨라."
    )
    return (
        "당신은 골프장 운영팀과 경영진이 함께 보는 운영 보고서를 작성한다.\n"
        f"이번 보고서 목표: {report_goal}\n"
        f"모델 운용 원칙: {reasoning_mode}\n"
        "출력은 보고서 본문만 작성하고, 서론/사족/변명/코드블록/JSON/표를 절대 쓰지 않는다.\n"
        "핵심 제약:\n"
        "1. payload의 숫자, 날짜, 액션, priority를 바꾸지 말 것.\n"
        "2. payload에 없는 사실을 추가하지 말 것.\n"
        "3. 내부 키 이름(signal_ratio, open_slots, promo_ratio, strategy_profiles 등)을 그대로 쓰지 말 것.\n"
        "4. 보고서 형식은 report_type별 섹션 규칙을 따를 것. 일간은 질문에 답하는 짧은 운영 문장으로 쓰고, 관측/해석/액션 같은 라벨을 반복하지 말 것.\n"
        "5. 변화값은 실제 비교값이 있는 수치에만 붙이고, 비교값이 없으면 '오늘 기준 확인 안 됨'처럼 짧게 처리할 것.\n"
        "6. 반복 액션은 날짜 구간으로 묶어 압축할 것.\n"
        "7. 데이터 부족은 별도 한계 문장으로 짧게 처리하고, 본문을 결측 설명으로 채우지 말 것.\n"
        "8. 문장은 짧고 단단하게, 불필요한 수식어 없이 쓸 것.\n"
        f"9. 마지막 줄은 반드시 '{_REPORT_TERMINATOR}' 하나만 쓸 것."
    )


def _build_user_prompt(payload: dict, model: str) -> str:
    report_type = payload.get("report_type", "daily")
    model_tier = "pro" if model.endswith("-pro") else "standard"
    detail_level = _get_report_detail_level(report_type)
    instructions = {
        "daily": (
            "아래 payload로 카카오골프 일간 운영 브리핑을 작성하라.\n"
            "목표: 오늘 관측된 가격 변화와 판매 흐름 변화를 짧고 명확하게 요약해 운영자가 바로 확인할 포인트를 제시하는 것이다.\n"
            "반드시 아래 질문에 답하라:\n"
            "1. 오늘 가격이 바뀐 골프장은 어디인가\n"
            "2. 오늘 새로 특가 또는 추가할인이 들어간 곳은 어디인가\n"
            "3. 오늘 가격 변화 후 판매 속도가 빨라진 구간은 어디인가\n"
            "4. 오늘 할인했는데도 반응이 약한 구간은 어디인가\n"
            "5. 오늘 할인 없이도 잘 팔리는 구간은 어디인가\n"
            "6. 베르힐CC의 오늘 상태는 어떠한가\n"
            "7. 내일 다시 확인해야 할 포인트는 무엇인가\n"
            "반드시 아래 헤더를 그대로 사용하라:\n"
            "1. 오늘의 한 줄 결론\n"
            "2. 오늘의 가격 변화\n"
            "3. 오늘의 판매 흐름 변화\n"
            "4. 베르힐CC 오늘 포인트\n"
            "5. 오늘의 핵심 액션\n"
            "6. 내일 확인 포인트\n"
            "길이 규칙:\n"
            "- 각 섹션은 2~4문장 이내.\n"
            "- 항목형이면 섹션당 최대 3개 항목.\n"
            "스타일 규칙:\n"
            "- 오늘 기준 변화에 집중하라.\n"
            "- 장기 결론보다 오늘의 변화와 즉시 확인 포인트를 우선하라.\n"
            "- 가격 변화와 판매 흐름을 반드시 연결하라.\n"
            "- 잔여 슬롯만 보고 해석하지 말고 payload에 있는 반응/방어 신호와 함께 해석하라.\n"
            "- 베르힐CC는 별도 섹션으로 작성하라.\n"
            "- 문장은 짧고 분명하게 써라.\n"
            "- 운영자가 바로 읽고 이해할 수 있게 작성하라.\n"
            "- 원인 단정 대신 관측 패턴으로 설명하라.\n"
            "- 내부 키 이름이나 영문 상태값을 그대로 쓰지 말라.\n"
            "- 근거가 없으면 추정하지 말고 '오늘 기준 확인 안 됨'이라고 써라.\n"
            "- N/A, null, 판단보류 같은 원시 표현은 운영 문장으로 바꿔 써라.\n"
            f"- 마지막 줄은 반드시 {_REPORT_TERMINATOR}"
        ),
        "weekly": (
            "너는 골프장 운영 전략 분석가다.\n"
            "카카오골프 수집 데이터를 바탕으로 골프장별 가격 변화 이력과 티타임 판매 흐름을 함께 읽어 "
            "운영자가 주간 단위로 가격 전략과 판매 패턴을 해석할 수 있는 카카오골프 주간 전략 보고서를 작성하라.\n"
            "이번 주간 보고서의 핵심은 단순 잔여 슬롯 요약이 아니다. 반드시 가격 변화와 판매 흐름을 연결해 읽어라.\n"
            "반드시 아래 흐름을 반영하라:\n"
            "- 이번 주에 어떤 골프장이 가격을 유지했는가\n"
            "- 어떤 골프장이 중간에 추가할인 또는 특가에 들어갔는가\n"
            "- 가격 인하 후 판매 속도가 실제로 빨라진 구간은 어디인가\n"
            "- 할인했는데도 반응이 약한 구간은 어디인가\n"
            "- 비할인 상태에서도 안정적으로 팔리는 구간은 어디인가\n"
            "- 경쟁 골프장 대비 어느 골프장이 가격 유지력이 높은가\n"
            "- 베르힐CC는 어느 구간에서 가격을 지켜도 되고, 어느 구간에서 할인 검토 또는 재점검이 필요한가\n"
            "반드시 아래 헤더를 그대로 사용하라:\n"
            "1. 주간 총평\n"
            "2. 가격 변화 요약\n"
            "3. 판매 흐름 요약\n"
            "4. 베르힐CC 집중 분석\n"
            "5. 경쟁 골프장 비교\n"
            "6. 핵심 운영 액션\n"
            "7. 다음 주 확인 포인트\n"
            "길이 규칙:\n"
            "- 각 섹션은 3~6문장 이내로 작성할 것.\n"
            "- 항목형은 섹션당 최대 5개까지 작성할 것.\n"
            "중요 원칙:\n"
            "- 가격 이벤트와 판매 반응을 반드시 함께 설명할 것.\n"
            "- 단순 잔여 슬롯 요약으로 끝내지 말 것.\n"
            "- '잔여 많음', '특가 비중 높음', '반복 약세 구간 존재' 같은 빈 문장은 금지한다.\n"
            "- 반드시 '가격 유지 상태에서도 소진 유지', '가격 인하 후 판매 가속 관측', '할인 반복에도 판매 반응 제한적', '경쟁사 할인 개시 후 상대 약세 가능성', '비할인 기본 판매력 양호 또는 약함' 중 하나 이상으로 해석할 것.\n"
            "- 원인 단정은 금지하고 관측 패턴으로만 설명할 것.\n"
            "- 베르힐CC는 반드시 가격 변화 추이, 1부 판매 흐름, 2부 판매 흐름, 경쟁 대비 위치, 운영 해석을 포함할 것.\n"
            "- 경쟁 비교는 입력 JSON 안의 코스 상대 비교만 사용하고 외부 시장 정보는 추가하지 말 것.\n"
            "- 내부 키 이름이나 영문 상태값을 그대로 쓰지 말 것.\n"
            "- 근거가 약하면 '이번 주 기준 추가 관찰 필요'라고 쓸 것.\n"
            "- 핵심 운영 액션은 반드시 '가격 유지 가능 구간 / 할인 검토 구간 / 할인 효과 재점검 구간' 3개 카테고리로 나눌 것.\n"
            "- 액션 항목은 반드시 '{골프장명} / {요일 또는 part} / {액션} / {근거}' 형식을 지킬 것.\n"
            f"- 마지막 줄은 반드시 {_REPORT_TERMINATOR}"
        ),
        "monthly": (
            "아래 payload로 월간 운영 인사이트 보고서를 작성하라.\n"
            "목표: 월간 숫자 요약이 아니라 체급 변화, 할인 구조, 정책 수정 포인트를 경영 판단으로 압축하는 것.\n"
            "운영 기준: 개별 이벤트보다 반복적으로 확인된 구조 신호를 우선 서술하라.\n"
            "반드시 아래 헤더를 그대로 사용하라:\n"
            "0. 용어 해설\n"
            "1. 월간 총평\n"
            "2. 체급/할인 구조 요약\n"
            "3. 구조적 약세 및 방어 구간\n"
            "4. 정책 제안\n"
            "5. 판단 보류 / 추가 확인 과제\n"
            "길이 규칙:\n"
            "- 0. 용어 해설은 보고서 해석에 필요한 핵심 용어를 먼저 설명할 것.\n"
            "- 총평은 3문장 이내.\n"
            "- 섹션별 최대 4개 항목.\n"
            "- 정책 제안은 실행 우선순위가 드러나게 쓸 것.\n"
            "- 약한 신호는 단정하지 말고 조건부 판단으로 정리할 것.\n"
            "- priority_score, severity 같은 내부 필드명은 쓰지 말 것.\n"
            f"- 마지막 줄은 반드시 {_REPORT_TERMINATOR}"
        ),
        "yearly": (
            "아래 payload로 연간 운영 전략 보고서를 작성하라.\n"
            "목표: 연간 구조 변화, 정책 성과, 다음 해 운영 원칙을 경영진 문서 수준으로 정리하는 것.\n"
            "운영 기준: 단기 등락보다 정책 회고와 재현 가능한 원칙을 우선 제시하라.\n"
            "반드시 아래 헤더를 그대로 사용하라:\n"
            "0. 용어 해설\n"
            "1. 연간 결론\n"
            "2. 체급 구조와 할인 구조 해석\n"
            "3. 가격/공급 정책 회고\n"
            "4. 내년 실행 제안\n"
            "5. 판단 보류 / 추가 데이터 과제\n"
            "길이 규칙:\n"
            "- 0. 용어 해설은 이후 정책 문장에서 반복될 용어를 먼저 설명할 것.\n"
            "- 연간 결론은 4문장 이내.\n"
            "- 섹션별 최대 5개 항목.\n"
            "- 실행 제안은 정책 수준으로 압축할 것.\n"
            "- 올해 관측과 내년 제안을 분리해서 쓸 것.\n"
            "- priority_score, severity 같은 내부 필드명은 쓰지 말 것.\n"
            f"- 마지막 줄은 반드시 {_REPORT_TERMINATOR}"
        ),
    }
    compact_payload = _build_llm_payload(payload)
    payload_json = json.dumps(compact_payload, ensure_ascii=False, indent=2)
    return (
        f"모델 티어: {model_tier}\n"
        f"상세 작성 수준: {detail_level}\n"
        f"{instructions.get(report_type, 'payload를 바탕으로 보고서를 작성하라.')}\n\n"
        f"{_build_detail_contract(report_type, detail_level)}\n\n"
        "작성 절차:\n"
        "1. 먼저 공통 추세를 정리한다.\n"
        "2. 그다음 코스별 차이를 묶어서 설명한다.\n"
        "3. 마지막으로 실행 항목과 판단 보류를 분리한다.\n"
        "4. 사고 과정은 쓰지 말고 결과 문장만 남긴다.\n\n"
        f"payload:\n{payload_json}"
    )


def _build_section_system_instructions(report_type: str, model: str, headers: list[str], is_final: bool) -> str:
    base = _build_system_instructions(report_type, model)
    header_lines = "\n".join(f"- {header}" for header in headers)
    tail_rule = (
        f"마지막 배치이므로 마지막 줄은 반드시 '{_REPORT_TERMINATOR}' 하나만 써라."
        if is_final
        else f"중간 배치이므로 '{_REPORT_TERMINATOR}'를 쓰지 마라."
    )
    return (
        f"{base}\n"
        "이번 호출은 보고서 일부만 작성한다.\n"
        "아래 헤더만 작성하고, 다른 헤더나 제목은 절대 추가하지 마라.\n"
        f"{header_lines}\n"
        f"{tail_rule}"
    )


def _build_section_user_prompt(payload: dict, model: str, headers: list[str], is_final: bool) -> str:
    report_type = payload.get("report_type", "daily")
    detail_level = _get_report_detail_level(report_type)
    compact_payload = _build_llm_payload(payload)
    compact_payload = _build_section_payload(compact_payload, headers)
    payload_json = json.dumps(compact_payload, ensure_ascii=False, indent=2)
    headers_text = "\n".join(headers)
    tail_rule = "마지막 줄에 [보고서 종료]를 붙인다." if is_final else "마지막 줄에 [보고서 종료]를 붙이지 않는다."
    if report_type == "daily":
        return (
            f"모델 티어: {'pro' if model.endswith('-pro') else 'standard'}\n"
            f"상세 작성 수준: {detail_level}\n"
            "이번 호출은 일간 보고서 일부만 작성한다.\n"
            "이번 배치에서 작성할 헤더는 아래뿐이다.\n"
            f"{headers_text}\n"
            "반드시 반영할 원칙:\n"
            "- 오늘 기준 변화만 쓴다.\n"
            "- 가격 변화와 판매 흐름을 연결한다.\n"
            "- 질문에 답하듯 짧고 분명하게 쓴다.\n"
            "- 섹션 안에서 관측:, 해석:, 액션:, 신뢰수준: 같은 라벨을 반복하지 않는다.\n"
            "- 내부 키 이름이나 영문 상태값을 그대로 쓰지 않는다.\n"
            "- 근거가 없으면 '오늘 기준 확인 안 됨'이라고 쓴다.\n"
            "- 비율은 raw decimal을 쓰지 말고 보고서용 백분율 또는 %p만 쓴다.\n"
            f"- {tail_rule}\n\n"
            f"payload:\n{payload_json}"
        )
    if report_type == "weekly":
        return (
            f"모델 티어: {'pro' if model.endswith('-pro') else 'standard'}\n"
            f"상세 작성 수준: {detail_level}\n"
            "이번 호출은 주간 보고서 일부만 작성한다.\n"
            "이번 배치에서 작성할 헤더는 아래뿐이다.\n"
            f"{headers_text}\n"
            "반드시 반영할 원칙:\n"
            "- 이번 주의 가격 변화와 판매 흐름을 연결해서 쓴다.\n"
            "- 단순 잔여 슬롯 요약으로 끝내지 않는다.\n"
            "- 가격 유지형, 할인 개입형, 할인 의존형, 할인 실효 낮음형 같은 운영 분류를 적극 활용한다.\n"
            "- 베르힐CC 섹션에서는 1부와 2부를 분리해 적고 경쟁 대비 위치를 함께 적는다.\n"
            "- '관측:', '해석:', '액션:' 같은 라벨을 반복하지 않는다.\n"
            "- 내부 키 이름이나 영문 상태값을 그대로 쓰지 않는다.\n"
            "- 근거가 약하면 '이번 주 기준 추가 관찰 필요'라고 쓴다.\n"
            "- 액션 항목은 '{골프장명} / {요일 또는 part} / {액션} / {근거}' 형식을 지킨다.\n"
            f"- {tail_rule}\n\n"
            f"payload:\n{payload_json}"
        )
    return (
        f"모델 티어: {'pro' if model.endswith('-pro') else 'standard'}\n"
        f"상세 작성 수준: {detail_level}\n"
        "이번 호출에서 작성할 헤더는 아래뿐이다.\n"
        f"{headers_text}\n"
        f"{_build_detail_contract(report_type, detail_level)}\n"
        "보고서 원칙:\n"
        "- 배정되지 않은 섹션은 쓰지 않는다.\n"
        "- 각 섹션 안에서는 관측 → 해석 → 액션 → 신뢰수준 순서를 유지한다.\n"
        "- 비중/비율 지표는 %p를 우선 쓰고, 슬롯 수 증감은 괄호로 보조 표기한다.\n"
        "- priority_score, severity, hold, strong, weak, none 같은 내부 표현은 쓰지 않는다.\n"
        f"- {tail_rule}\n\n"
        f"payload:\n{payload_json}"
    )


def _get_report_detail_level(report_type: str) -> str:
    level = _get_llm_setting(report_type, "REPORT_LLM_DETAIL_LEVEL", "detailed").strip().lower()
    if level not in {"brief", "standard", "detailed"}:
        return "detailed"
    return level


def _use_sectioned_rendering(report_type: str) -> bool:
    value = _get_llm_setting(report_type, "REPORT_LLM_SECTIONED", "true")
    return value.strip().lower() == "true"


def _get_section_timeout_sec(report_type: str, model: str, base_timeout: float) -> float:
    override = _get_llm_setting(report_type, "REPORT_LLM_SECTION_TIMEOUT_SEC", "")
    if override.strip():
        try:
            return float(override)
        except ValueError:
            pass

    if model.endswith("-pro"):
        if report_type in {"weekly", "monthly"}:
            return max(base_timeout, 180.0)
        if report_type == "yearly":
            return max(base_timeout, 240.0)
    if report_type == "daily":
        return max(base_timeout, 90.0)
    return max(base_timeout, 120.0)


def _get_section_batch_max_tokens(
    report_type: str,
    model: str,
    total_max_tokens: int,
    batch_count: int,
) -> int:
    override = _get_llm_setting(report_type, "REPORT_LLM_SECTION_MAX_TOKENS", "")
    if override.strip():
        try:
            return int(override)
        except ValueError:
            pass

    if model.endswith("-pro"):
        if report_type == "weekly":
            return max(5000, total_max_tokens // max(1, batch_count - 1))
        if report_type == "monthly":
            return max(5200, total_max_tokens // max(1, batch_count - 1))
        if report_type == "yearly":
            return max(6500, total_max_tokens // max(1, batch_count - 1))
        return max(3200, total_max_tokens // batch_count + 1200)

    return max(1800, total_max_tokens // batch_count + 700)


def _call_openai_request_with_retry(
    *,
    base_url: str,
    request_body: dict,
    api_key: str,
    timeout: float,
    retry_timeout: float,
) -> str:
    try:
        return _call_openai_request(
            base_url=base_url,
            request_body=request_body,
            api_key=api_key,
            timeout=timeout,
        )
    except TimeoutError:
        logger.warning("[LLM] 섹션 호출 timeout, 1회 재시도: {}초", retry_timeout)
        return _call_openai_request(
            base_url=base_url,
            request_body=request_body,
            api_key=api_key,
            timeout=retry_timeout,
        )


def _build_detail_contract(report_type: str, detail_level: str) -> str:
    detail_map = {
        "brief": "상세도 규칙: 핵심 판단만 남기고, 각 섹션은 대표 항목 위주로 최소 분량만 작성한다.",
        "standard": "상세도 규칙: 핵심 판단과 보조 근거를 함께 쓰되, 중복 설명은 줄인다.",
        "detailed": "상세도 규칙: 각 섹션에서 대표 사례와 수치 의미를 충분히 설명하되, 같은 메시지는 묶어서 정리한다.",
    }
    type_map = {
        "daily": "일간 보고서는 오늘 실행 여부가 갈리는 근거를 더 자세히 쓴다.",
        "weekly": "주간 보고서는 코스 묶음별 구조 차이와 다음 주 우선순위를 자세히 쓴다.",
        "monthly": "월간 보고서는 체급 변화, 할인 구조, 정책 수정 포인트를 자세히 쓴다.",
        "yearly": "연간 보고서는 정책 회고, 반복 패턴, 내년 운영 원칙을 자세히 쓴다.",
    }
    return f"{detail_map.get(detail_level, detail_map['detailed'])} {type_map.get(report_type, '')}".strip()


def _finalize_rendered_report(text: str, payload: dict) -> str:
    report_type = payload.get("report_type", "daily")
    report_date = payload.get("report_date") or ""
    finalized = text.strip()
    finalized = _ensure_report_title(finalized, report_type, report_date)
    finalized = _sanitize_report_labels(finalized)
    return finalized.strip()


def _render_glossary_section(payload: dict) -> str:
    glossary = ((payload.get("evidence") or {}).get("metric_glossary") or [])[:6]
    lines = ["0. 용어 해설"]
    if not glossary:
        lines.append("- 이번 보고서에서 새로 해설할 핵심 용어 없음")
        return "\n".join(lines)
    for item in glossary:
        lines.append(
            f"- {item.get('metric')}: {item.get('description')} {item.get('interpretation')}"
        )
    return "\n".join(lines)


def _ensure_report_title(text: str, report_type: str, report_date: str) -> str:
    stripped = text.lstrip()
    if stripped.startswith("[카카오골프 "):
        return text
    title_map = {
        "daily": "일간 브리핑",
        "weekly": "주간 전략 보고서",
        "monthly": "월간 운영 인사이트 보고서",
        "yearly": "연간 운영 전략 보고서",
    }
    header = f"[카카오골프 {title_map.get(report_type, '보고서')}] {report_date}".strip()
    return f"{header}\n\n{text}".strip()


def _sanitize_report_labels(text: str) -> str:
    sanitized = text
    severity_map = {
        "high": "높음",
        "medium": "중간",
        "low": "낮음",
    }

    def replace_priority(match: re.Match[str]) -> str:
        severity = severity_map.get(match.group(2).lower(), "중간")
        return f"(우선순위 {severity})"

    sanitized = re.sub(
        r"\(priority_score:\s*(\d+),\s*severity:\s*(high|medium|low)\)",
        replace_priority,
        sanitized,
        flags=re.IGNORECASE,
    )
    sanitized = re.sub(r"\bpriority_score\s*:\s*\d+\b", "", sanitized, flags=re.IGNORECASE)
    sanitized = re.sub(r"\bseverity\s*:\s*(high|medium|low)\b", "", sanitized, flags=re.IGNORECASE)
    sanitized = re.sub(r"\bhold\b", "판단보류", sanitized, flags=re.IGNORECASE)
    sanitized = re.sub(r"\bstrong\b", "강한 반응", sanitized, flags=re.IGNORECASE)
    sanitized = re.sub(r"\bweak\b", "약한 반응", sanitized, flags=re.IGNORECASE)
    sanitized = re.sub(r"\bnone\b", "반응 없음", sanitized, flags=re.IGNORECASE)
    sanitized = re.sub(r"[ ]{2,}", " ", sanitized)
    sanitized = re.sub(r"[ \t]+\n", "\n", sanitized)
    return sanitized


def _validate_report_chunk(text: str, headers: list[str], *, is_final: bool) -> str | None:
    stripped = text.strip()
    if not stripped:
        return "empty_chunk"
    lowered = stripped.lower()
    for term in _INTERNAL_TERMS:
        if term in lowered:
            return f"internal_term:{term}"
    for header in headers:
        if header not in stripped:
            return f"missing_header:{header}"

    if is_final:
        if _REPORT_TERMINATOR not in stripped:
            return "missing_terminator"
        body, _, tail = stripped.rpartition(_REPORT_TERMINATOR)
        if tail.strip():
            return "invalid_terminator_tail"
        check_text = body.strip()
    else:
        if _REPORT_TERMINATOR in stripped:
            return "unexpected_terminator"
        check_text = stripped

    lines = [line.strip() for line in check_text.splitlines() if line.strip()]
    if not lines:
        return "empty_lines"
    last_line = lines[-1]
    if not re.search(r"[.!?)]$|[다됨음요함]$", last_line):
        return "truncated_tail"
    return None


def _extract_response_text(data: dict) -> str:
    output_text = data.get("output_text")
    if isinstance(output_text, str) and output_text.strip():
        return output_text.strip()
    if isinstance(output_text, list):
        joined = "\n".join(part.strip() for part in output_text if isinstance(part, str) and part.strip()).strip()
        if joined:
            return joined

    outputs = data.get("output") or []
    text_parts: list[str] = []
    for item in outputs:
        content_list = item.get("content") or []
        for content in content_list:
            text_value = _coerce_text_value(content.get("text"))
            if content.get("type") in {"output_text", "text"} and text_value:
                text_parts.append(text_value)
            alt_value = _coerce_text_value(content.get("output_text"))
            if alt_value:
                text_parts.append(alt_value)

    text = "\n".join(part.strip() for part in text_parts if part.strip()).strip()
    if text:
        return text

    fallback_text = _find_text_recursively(data)
    if fallback_text:
        return fallback_text

    raise ValueError("response text not found in OpenAI response payload")


def _raise_if_response_incomplete(data: dict) -> None:
    if data.get("status") == "incomplete":
        details = data.get("incomplete_details") or {}
        reason = details.get("reason") or "unknown"
        raise ValueError(f"response_incomplete:{reason}")
    for item in data.get("output") or []:
        if item.get("status") == "incomplete":
            details = item.get("incomplete_details") or {}
            reason = details.get("reason") or "unknown"
            raise ValueError(f"response_output_incomplete:{reason}")


def _coerce_text_value(value) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    if isinstance(value, dict):
        for key in ("value", "text", "content"):
            nested = value.get(key)
            if isinstance(nested, str) and nested.strip():
                return nested.strip()
    return None


def _find_text_recursively(node) -> str | None:
    if isinstance(node, str) and node.strip():
        return node.strip()
    if isinstance(node, dict):
        for key in ("output_text", "text", "value", "content"):
            if key in node:
                found = _find_text_recursively(node[key])
                if found:
                    return found
        for value in node.values():
            found = _find_text_recursively(value)
            if found:
                return found
    if isinstance(node, list):
        parts = []
        for item in node:
            found = _find_text_recursively(item)
            if found:
                parts.append(found)
        if parts:
            return "\n".join(parts)
    return None


def _validate_rendered_report(text: str, report_type: str) -> str | None:
    stripped = text.strip()
    if not stripped:
        return "empty_text"

    if _REPORT_TERMINATOR not in stripped:
        return "missing_terminator"

    body, _, tail = stripped.rpartition(_REPORT_TERMINATOR)
    if tail.strip():
        return "invalid_terminator_tail"
    stripped = body.strip()
    if not stripped:
        return "empty_body"

    lowered = stripped.lower()
    for term in _INTERNAL_TERMS:
        if term in lowered:
            return f"internal_term:{term}"

    required_headers = _REPORT_SECTION_HEADERS.get(report_type) or []
    for header in required_headers:
        if header not in stripped:
            return f"missing_header:{header}"

    lines = [line.strip() for line in stripped.splitlines() if line.strip()]
    if len(lines) < 12:
        return "too_short"

    last_line = lines[-1]
    if not re.search(r"[.!?)]$|[다됨음요함]$", last_line):
        return "truncated_tail"

    return None


def _build_llm_payload(payload: dict) -> dict:
    report_type = payload.get("report_type", "daily")
    summary = payload.get("summary") or {}
    evidence = payload.get("evidence") or {}

    compact = {
        "report_type": report_type,
        "report_date": payload.get("report_date"),
        "summary": _compact_summary(summary),
        "actions": _compact_actions(payload.get("actions") or []),
        "risks": _compact_risks(payload.get("risks") or []),
        "recommendations": _compact_recommendations(payload.get("recommendations") or []),
        "course_focus": _compact_course_focus(payload.get("course_focus") or []),
        "evidence": _compact_evidence(report_type, evidence),
    }
    return compact


def _build_daily_section_payload(compact_payload: dict, headers: list[str]) -> dict:
    header_set = set(headers)
    payload = {
        "report_type": compact_payload.get("report_type"),
        "report_date": compact_payload.get("report_date"),
        "summary": compact_payload.get("summary"),
    }
    evidence = compact_payload.get("evidence") or {}

    if header_set & {"1. 오늘의 한 줄 결론", "2. 오늘의 가격 변화", "3. 오늘의 판매 흐름 변화"}:
        payload["course_focus"] = compact_payload.get("course_focus") or []
        payload["actions"] = compact_payload.get("actions") or []
        payload["evidence"] = {
            "course_comparisons": evidence.get("course_comparisons") or [],
            "price_change_watch": evidence.get("price_change_watch") or {},
            "discount_response": evidence.get("discount_response") or {},
            "defense_signals": evidence.get("defense_signals") or [],
            "repeat_discount_signals": evidence.get("repeat_discount_signals") or [],
        }

    if "4. 베르힐CC 오늘 포인트" in header_set:
        payload["actions"] = [
            item for item in (compact_payload.get("actions") or [])
            if item.get("course_name") == "베르힐"
        ]
        payload["course_focus"] = [
            item for item in (compact_payload.get("course_focus") or [])
            if item.get("course_name") == "베르힐"
        ]
        payload["evidence"] = {
            "course_comparisons": [
                item for item in (evidence.get("course_comparisons") or [])
                if item.get("course_name") == "베르힐"
            ],
            "defense_signals": [
                item for item in (evidence.get("defense_signals") or [])
                if item.get("course_name") == "베르힐"
            ],
            "repeat_discount_signals": [
                item for item in (evidence.get("repeat_discount_signals") or [])
                if item.get("course_name") == "베르힐"
            ],
        }

    if "5. 오늘의 핵심 액션" in header_set:
        payload["actions"] = compact_payload.get("actions") or []
        payload["recommendations"] = compact_payload.get("recommendations") or []
        payload["evidence"] = {
            "course_comparisons": evidence.get("course_comparisons") or [],
            "price_change_watch": evidence.get("price_change_watch") or {},
        }

    if "6. 내일 확인 포인트" in header_set:
        payload["risks"] = compact_payload.get("risks") or []
        payload["course_focus"] = compact_payload.get("course_focus") or []
        payload["evidence"] = {
            "discount_response": evidence.get("discount_response") or {},
            "price_change_watch": evidence.get("price_change_watch") or {},
            "repeat_discount_signals": evidence.get("repeat_discount_signals") or [],
        }

    return payload


def _build_period_section_payload(compact_payload: dict, headers: list[str]) -> dict:
    header_set = set(headers)
    payload = {
        "report_type": compact_payload.get("report_type"),
        "report_date": compact_payload.get("report_date"),
        "summary": compact_payload.get("summary"),
    }
    evidence = compact_payload.get("evidence") or {}
    report_type = compact_payload.get("report_type")

    if report_type == "weekly":
        if header_set & {"1. 주간 총평", "2. 가격 변화 요약", "3. 판매 흐름 요약"}:
            payload["course_focus"] = compact_payload.get("course_focus") or []
            payload["actions"] = compact_payload.get("actions") or []
            payload["evidence"] = {
                "indices": evidence.get("indices") or {},
                "repeated_weak_slots": evidence.get("repeated_weak_slots") or [],
                "discount_efficiency": evidence.get("discount_efficiency") or [],
                "competitive_position": evidence.get("competitive_position") or [],
                "member_supply_changes": evidence.get("member_supply_changes") or [],
            }

        if "4. 베르힐CC 집중 분석" in header_set:
            payload["actions"] = [
                item for item in (compact_payload.get("actions") or [])
                if item.get("course_name") == "베르힐"
            ]
            payload["course_focus"] = [
                item for item in (compact_payload.get("course_focus") or [])
                if item.get("course_name") == "베르힐"
            ]
            payload["evidence"] = {
                "indices": evidence.get("indices") or {},
                "repeated_weak_slots": [
                    item for item in (evidence.get("repeated_weak_slots") or [])
                    if item.get("course_name") == "베르힐"
                ],
                "competitive_position": [
                    item for item in (evidence.get("competitive_position") or [])
                    if item.get("course_name") == "베르힐"
                ],
            }

        if "5. 경쟁 골프장 비교" in header_set:
            payload["course_focus"] = compact_payload.get("course_focus") or []
            payload["evidence"] = {
                "indices": evidence.get("indices") or {},
                "competitive_position": evidence.get("competitive_position") or [],
                "discount_efficiency": evidence.get("discount_efficiency") or [],
                "strategy_profiles": evidence.get("strategy_profiles") or [],
            }

        if "6. 핵심 운영 액션" in header_set:
            payload["actions"] = compact_payload.get("actions") or []
            payload["evidence"] = {
                "indices": evidence.get("indices") or {},
                "repeated_weak_slots": evidence.get("repeated_weak_slots") or [],
                "discount_efficiency": evidence.get("discount_efficiency") or [],
            }

        if "7. 다음 주 확인 포인트" in header_set:
            payload["risks"] = compact_payload.get("risks") or []
            payload["course_focus"] = compact_payload.get("course_focus") or []
            payload["evidence"] = {
                "indices": evidence.get("indices") or {},
                "discount_efficiency": evidence.get("discount_efficiency") or [],
                "member_supply_changes": evidence.get("member_supply_changes") or [],
                "repeated_weak_slots": evidence.get("repeated_weak_slots") or [],
            }
        return payload

    if header_set & {
        "1. 주간 결론",
        "2. 이번 주 구조 변화",
        "1. 월간 총평",
        "2. 체급/할인 구조 요약",
        "1. 연간 결론",
        "2. 체급 구조와 할인 구조 해석",
    }:
        payload["course_focus"] = compact_payload.get("course_focus") or []
        payload["evidence"] = {
            "indices": evidence.get("indices") or {},
            "strategy_profiles": evidence.get("strategy_profiles") or [],
        }

    if header_set & {
        "3. 골프장별 전략 변화",
        "4. 다음 주 실행 제안",
        "3. 구조적 약세 및 방어 구간",
        "4. 정책 제안",
        "3. 가격/공급 정책 회고",
        "4. 내년 실행 제안",
    }:
        payload["actions"] = compact_payload.get("actions") or []
        payload["recommendations"] = compact_payload.get("recommendations") or []
        payload["course_focus"] = compact_payload.get("course_focus") or []
        section_evidence = payload.setdefault("evidence", {})
        section_evidence["indices"] = evidence.get("indices") or {}
        section_evidence["strategy_profiles"] = evidence.get("strategy_profiles") or []

    if header_set & {
        "5. 판단 보류 / 데이터 한계",
        "5. 판단 보류 / 추가 확인 과제",
        "5. 판단 보류 / 추가 데이터 과제",
    }:
        payload["risks"] = compact_payload.get("risks") or []
        section_evidence = payload.setdefault("evidence", {})
        section_evidence["indices"] = evidence.get("indices") or {}

    return payload


def _build_section_payload(compact_payload: dict, headers: list[str]) -> dict:
    report_type = compact_payload.get("report_type", "daily")
    if report_type == "daily":
        return _build_daily_section_payload(compact_payload, headers)
    return _build_period_section_payload(compact_payload, headers)


def _compact_summary(summary: dict) -> dict:
    compact = {}
    for key in (
        "total_rows",
        "total_courses",
        "total_slots",
        "promo_slots",
        "promo_ratio",
        "price_change_events",
        "price_response_events",
        "member_open_events",
        "observed_days",
        "courses_analyzed",
        "dominant_market_pattern",
    ):
        if key in summary:
            compact[key] = summary.get(key)
    if summary.get("top_signals"):
        compact["top_signals"] = summary.get("top_signals")[:5]
    if summary.get("management_snapshot"):
        compact["management_snapshot"] = summary.get("management_snapshot")
    return compact


def _compact_actions(actions: list[dict]) -> list[dict]:
    compact = []
    seen = set()
    for item in actions:
        key = (
            item.get("course_name"),
            item.get("play_date"),
            item.get("part_type"),
            item.get("action"),
        )
        if key in seen:
            continue
        seen.add(key)
        compact.append(
            {
                "course_name": item.get("course_name"),
                "play_date": item.get("play_date"),
                "part_type": item.get("part_type"),
                "severity": item.get("severity"),
                "action": item.get("action"),
                "reason": item.get("reason"),
                "priority_score": item.get("priority_score"),
            }
        )
        if len(compact) >= 8:
            break
    return compact


def _compact_risks(risks: list[dict]) -> list[dict]:
    compact = []
    for item in risks[:5]:
        compact.append(
            {
                "level": item.get("level"),
                "message": item.get("message"),
                "reason": item.get("reason"),
            }
        )
    return compact


def _compact_recommendations(recommendations: list[dict]) -> list[dict]:
    compact = []
    seen = set()
    for item in recommendations:
        key = (item.get("course_name"), item.get("recommendation"))
        if key in seen:
            continue
        seen.add(key)
        compact.append(
            {
                "course_name": item.get("course_name"),
                "recommendation": item.get("recommendation"),
            }
        )
        if len(compact) >= 5:
            break
    return compact


def _compact_course_focus(course_focus: list[dict]) -> list[dict]:
    compact = []
    for item in course_focus[:5]:
        compact.append(
            {
                "course_name": item.get("course_name"),
                "headline": item.get("headline"),
                "key_metrics": {
                    "total_slots": (item.get("key_metrics") or {}).get("total_slots"),
                    "promo_ratio": (item.get("key_metrics") or {}).get("promo_ratio"),
                    "min_price": (item.get("key_metrics") or {}).get("min_price"),
                },
            }
        )
    return compact


def _compact_evidence(report_type: str, evidence: dict) -> dict:
    compact = {}

    course_comparisons = evidence.get("course_comparisons") or []
    if course_comparisons:
        compact["course_comparisons"] = _compact_course_comparisons(course_comparisons)

    if evidence.get("composite_issues"):
        compact["composite_issues"] = (evidence.get("composite_issues") or [])[:5]
    if evidence.get("price_change_watch"):
        compact["price_change_watch"] = evidence.get("price_change_watch")
    if evidence.get("discount_response"):
        compact["discount_response"] = evidence.get("discount_response")
    if evidence.get("defense_signals"):
        compact["defense_signals"] = (evidence.get("defense_signals") or [])[:6]
    if evidence.get("repeat_discount_signals"):
        compact["repeat_discount_signals"] = (evidence.get("repeat_discount_signals") or [])[:6]
    if evidence.get("metric_glossary"):
        compact["metric_glossary"] = (evidence.get("metric_glossary") or [])[:5]

    strategy_profiles = evidence.get("strategy_profiles") or []
    if strategy_profiles:
        compact["strategy_profiles"] = _compact_strategy_profiles(strategy_profiles)

    if report_type != "daily" and evidence.get("indices"):
        compact["indices"] = evidence.get("indices")
    if report_type == "weekly":
        if evidence.get("repeated_weak_slots"):
            compact["repeated_weak_slots"] = (evidence.get("repeated_weak_slots") or [])[:10]
        if evidence.get("discount_efficiency"):
            compact["discount_efficiency"] = (evidence.get("discount_efficiency") or [])[:8]
        if evidence.get("competitive_position"):
            compact["competitive_position"] = (evidence.get("competitive_position") or [])[:12]
        if evidence.get("member_supply_changes"):
            compact["member_supply_changes"] = (evidence.get("member_supply_changes") or [])[:8]

    return compact


def _compact_course_comparisons(course_comparisons: list[dict]) -> list[dict]:
    selected = []
    counts = {"discount": 0, "defense": 0, "mixed": 0, "watch": 0, "supply": 0}
    for item in course_comparisons:
        status = (item.get("status") or {}).get("code") or "watch"
        if status in counts and counts[status] >= 2:
            continue
        counts[status] = counts.get(status, 0) + 1
        selected.append(
            {
                "course_name": item.get("course_name"),
                "status": item.get("status"),
                "avg_price_metric": item.get("avg_price_metric"),
                "min_price_metric": item.get("min_price_metric"),
                "promo_metric": item.get("promo_metric"),
                "discount_days_metric": item.get("discount_days_metric"),
                "defense_days_metric": item.get("defense_days_metric"),
                "interpretation": item.get("interpretation"),
                "today_action": item.get("today_action"),
                "confidence": item.get("confidence"),
            }
        )
        if len(selected) >= 8:
            break
    return selected


def _compact_strategy_profiles(profiles: list[dict]) -> list[dict]:
    compact = []
    for item in profiles[:5]:
        compact.append(
            {
                "course_name": item.get("course_name"),
                "base_tier": {
                    "grade": (item.get("base_tier") or {}).get("grade"),
                    "label": (item.get("base_tier") or {}).get("label"),
                },
                "discount_dependency": {
                    "label": (item.get("discount_dependency") or {}).get("label"),
                    "value": (item.get("discount_dependency") or {}).get("value"),
                },
                "discount_amplification": {
                    "label": (item.get("discount_amplification") or {}).get("label"),
                    "value": (item.get("discount_amplification") or {}).get("value"),
                },
            }
        )
    return compact
