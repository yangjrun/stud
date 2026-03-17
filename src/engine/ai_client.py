"""AI API 客户端: 封装 OpenAI 调用 + 结构化输出 + 校验层。"""

import json
import logging
import os

import httpx
from pydantic import BaseModel, ValidationError, field_validator

from openai import OpenAI

from src.config.settings import Settings

logger = logging.getLogger(__name__)

# ─── 合法值集合 ───

VALID_PHASES = frozenset({"冰点", "修复", "发酵", "高潮", "分歧", "退潮", "震荡"})
VALID_STRATEGIES = frozenset({"进攻型", "试探型", "防守型", "观望型", "空仓"})
VALID_TIERS = frozenset({"A", "B", "C"})
VALID_SEVERITIES = frozenset({"URGENT", "WARN"})
VALID_GATE_RESULTS = frozenset({"PASS", "FAIL", "CAUTION"})
VALID_INTENSITIES = frozenset({"strong", "normal", "weak"})
VALID_ROLES = frozenset({"龙头", "二龙", "三龙", "跟风"})
VALID_FORECAST_TYPES = frozenset({"promotion", "continuation", "new_leader"})

_OUTPUT_SCHEMA_INSTRUCTIONS = """
返回一个 JSON 对象，必须且只能包含这些顶层字段：
- predicted_phase: 冰点/修复/发酵/高潮/分歧/退潮/震荡
- predicted_score: 0-100 整数
- predicted_gate_result: PASS/FAIL/CAUTION
- phase_transition: 例如 "修复->发酵"
- gate_confidence: 0-100 整数
- gate_rationale: 字符串
- strategy_name: 进攻型/试探型/防守型/观望型/空仓
- strategy_intensity: strong/normal/weak
- strategy_summary: 字符串
- allow_roles: ["龙头","二龙","三龙","跟风"] 的子集
- buy_candidates: 数组，元素字段必须为
  code,name,ai_score,tier,market_role,forecast_type,predicted_board,rationale,theme_name
- sell_forecasts: 数组，元素字段必须为
  code,name,severity,reason,confidence
- market_summary: 字符串
- risk_warnings: 字符串数组

不要输出 markdown，不要输出代码块，不要添加 date、predicted_market、strategy 或其他包装层。
""".strip()


# ─── Pydantic 响应模型 ───


class AIBuyCandidate(BaseModel):
    """AI 对单只候选股的评估。"""

    code: str
    name: str
    ai_score: int
    tier: str
    market_role: str
    forecast_type: str
    predicted_board: str
    rationale: str
    theme_name: str

    @field_validator("ai_score")
    @classmethod
    def score_range(cls, v: int) -> int:
        if not 0 <= v <= 100:
            raise ValueError(f"ai_score must be 0-100, got {v}")
        return v

    @field_validator("tier")
    @classmethod
    def tier_valid(cls, v: str) -> str:
        if v not in VALID_TIERS:
            raise ValueError(f"tier must be one of {VALID_TIERS}, got {v}")
        return v

    @field_validator("market_role")
    @classmethod
    def role_valid(cls, v: str) -> str:
        if v not in VALID_ROLES:
            raise ValueError(f"market_role must be one of {VALID_ROLES}, got {v}")
        return v

    @field_validator("forecast_type")
    @classmethod
    def forecast_type_valid(cls, v: str) -> str:
        if v not in VALID_FORECAST_TYPES:
            raise ValueError(f"forecast_type must be one of {VALID_FORECAST_TYPES}, got {v}")
        return v


class AISellForecast(BaseModel):
    """AI 卖出预警。"""

    code: str
    name: str
    severity: str
    reason: str
    confidence: int

    @field_validator("severity")
    @classmethod
    def severity_valid(cls, v: str) -> str:
        if v not in VALID_SEVERITIES:
            raise ValueError(f"severity must be one of {VALID_SEVERITIES}, got {v}")
        return v

    @field_validator("confidence")
    @classmethod
    def confidence_range(cls, v: int) -> int:
        if not 0 <= v <= 100:
            raise ValueError(f"confidence must be 0-100, got {v}")
        return v


class AIForecastResponse(BaseModel):
    """AI 必须返回的完整结构。"""

    # 门控预测
    predicted_phase: str
    predicted_score: int
    predicted_gate_result: str
    phase_transition: str
    gate_confidence: int
    gate_rationale: str

    # 策略建议
    strategy_name: str
    strategy_intensity: str
    strategy_summary: str
    allow_roles: list[str]

    # 候选评估
    buy_candidates: list[AIBuyCandidate]
    sell_forecasts: list[AISellForecast]

    # 整体评估
    market_summary: str
    risk_warnings: list[str]

    @field_validator("predicted_phase")
    @classmethod
    def phase_valid(cls, v: str) -> str:
        if v not in VALID_PHASES:
            raise ValueError(f"predicted_phase must be one of {VALID_PHASES}, got {v}")
        return v

    @field_validator("predicted_score")
    @classmethod
    def score_range(cls, v: int) -> int:
        if not 0 <= v <= 100:
            raise ValueError(f"predicted_score must be 0-100, got {v}")
        return v

    @field_validator("predicted_gate_result")
    @classmethod
    def gate_result_valid(cls, v: str) -> str:
        if v not in VALID_GATE_RESULTS:
            raise ValueError(
                f"predicted_gate_result must be one of {VALID_GATE_RESULTS}, got {v}"
            )
        return v

    @field_validator("gate_confidence")
    @classmethod
    def gate_confidence_range(cls, v: int) -> int:
        if not 0 <= v <= 100:
            raise ValueError(f"gate_confidence must be 0-100, got {v}")
        return v

    @field_validator("strategy_name")
    @classmethod
    def strategy_valid(cls, v: str) -> str:
        if v not in VALID_STRATEGIES:
            raise ValueError(f"strategy_name must be one of {VALID_STRATEGIES}, got {v}")
        return v

    @field_validator("strategy_intensity")
    @classmethod
    def intensity_valid(cls, v: str) -> str:
        if v not in VALID_INTENSITIES:
            raise ValueError(f"strategy_intensity must be one of {VALID_INTENSITIES}, got {v}")
        return v

    @field_validator("allow_roles")
    @classmethod
    def roles_valid(cls, v: list[str]) -> list[str]:
        for r in v:
            if r not in VALID_ROLES:
                raise ValueError(f"allow_roles contains invalid role: {r}")
        return v


# ─── 一致性校验 ───


def _validate_consistency(resp: AIForecastResponse, valid_codes: set[str] | None) -> list[str]:
    """业务一致性校验，返回错误列表。"""
    errors: list[str] = []

    if resp.predicted_gate_result == "FAIL":
        if resp.strategy_name != "空仓":
            errors.append(
                f"gate_result=FAIL but strategy_name={resp.strategy_name}, expected 空仓"
            )
        if resp.buy_candidates:
            errors.append(
                f"gate_result=FAIL but {len(resp.buy_candidates)} buy candidates present"
            )

    phase_score_ranges: dict[str, tuple[int, int]] = {
        "冰点": (0, 35),
        "修复": (15, 50),
        "发酵": (30, 70),
        "高潮": (50, 100),
        "分歧": (25, 60),
        "退潮": (5, 40),
        "震荡": (20, 55),
    }
    lo, hi = phase_score_ranges.get(resp.predicted_phase, (0, 100))
    if not lo <= resp.predicted_score <= hi:
        errors.append(
            f"predicted_score={resp.predicted_score} out of range"
            f" [{lo},{hi}] for phase={resp.predicted_phase}"
        )

    if valid_codes is not None:
        for cand in resp.buy_candidates:
            if cand.code not in valid_codes:
                errors.append(f"buy candidate {cand.code} not in today's limit-up list")

    return errors


# ─── 保守默认值 ───


def _default_response() -> AIForecastResponse:
    """全部失败时的保守默认值。"""
    return AIForecastResponse(
        predicted_phase="震荡",
        predicted_score=30,
        predicted_gate_result="CAUTION",
        phase_transition="震荡->震荡",
        gate_confidence=20,
        gate_rationale="AI 预测失败，使用保守默认值",
        strategy_name="观望型",
        strategy_intensity="weak",
        strategy_summary="AI 分析暂不可用，建议观望",
        allow_roles=["龙头"],
        buy_candidates=[],
        sell_forecasts=[],
        market_summary="AI 预测服务异常，无法给出市场判断。建议保持观望，等待信号恢复。",
        risk_warnings=["AI 预测服务异常，本次结果为保守默认值"],
    )


def _default_allow_roles(strategy_name: str) -> list[str]:
    mapping = {
        "进攻型": ["龙头", "二龙", "三龙", "跟风"],
        "试探型": ["龙头", "二龙"],
        "防守型": ["龙头"],
        "观望型": ["龙头"],
        "空仓": [],
    }
    return mapping.get(strategy_name, ["龙头"])


def _strip_json_fence(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return text


def _normalize_buy_candidate(item: dict) -> dict:
    normalized = dict(item)
    normalized["ai_score"] = normalized.get("ai_score", normalized.get("score", normalized.get("confidence", 60)))
    normalized["tier"] = normalized.get("tier", normalized.get("rating", "C"))
    normalized["market_role"] = normalized.get("market_role", normalized.get("role", "龙头"))
    normalized["forecast_type"] = normalized.get(
        "forecast_type",
        normalized.get("type", "continuation"),
    )
    normalized["predicted_board"] = normalized.get(
        "predicted_board",
        normalized.get("board_prediction", normalized.get("next_board", "")),
    )
    normalized["rationale"] = normalized.get("rationale", normalized.get("reason", ""))
    normalized["theme_name"] = normalized.get(
        "theme_name",
        normalized.get("theme", normalized.get("concept_name", "")),
    )
    if normalized["predicted_board"] is None:
        normalized["predicted_board"] = ""
    elif not isinstance(normalized["predicted_board"], str):
        normalized["predicted_board"] = str(normalized["predicted_board"])
    return normalized


def _normalize_sell_forecast(item: dict) -> dict:
    normalized = dict(item)
    normalized["severity"] = normalized.get("severity", "WARN")
    normalized["reason"] = normalized.get("reason", normalized.get("rationale", ""))
    normalized["confidence"] = normalized.get(
        "confidence",
        normalized.get("score", 60),
    )
    return normalized


def _normalize_sell_forecast_item(item: object) -> dict | None:
    if isinstance(item, dict):
        return _normalize_sell_forecast(item)
    if isinstance(item, str):
        return {
            "code": "",
            "name": "",
            "severity": "WARN",
            "reason": item,
            "confidence": 50,
        }
    return None


def _normalize_forecast_payload(payload: dict) -> dict:
    data = dict(payload)

    gate_raw = data.get("predicted_market") or data.get("gate") or data.get("market_prediction") or {}
    strategy_raw = data.get("strategy") or data.get("strategy_advice") or data.get("strategy_recommendation") or {}
    gate = gate_raw if isinstance(gate_raw, dict) else {}
    strategy = strategy_raw if isinstance(strategy_raw, dict) else {}
    gate_text = gate_raw if isinstance(gate_raw, str) else ""
    strategy_text = strategy_raw if isinstance(strategy_raw, str) else ""

    predicted_phase = data.get("predicted_phase", gate.get("predicted_phase", gate.get("phase", "震荡")))
    predicted_score = data.get("predicted_score", gate.get("predicted_score", gate.get("score", 30)))
    predicted_gate_result = data.get(
        "predicted_gate_result",
        gate.get("predicted_gate_result", gate.get("gate_result", gate.get("result", "CAUTION"))),
    )

    strategy_name = data.get(
        "strategy_name",
        strategy.get("strategy_name", strategy.get("name", strategy.get("type", "观望型"))),
    )
    strategy_intensity = data.get(
        "strategy_intensity",
        strategy.get("strategy_intensity", strategy.get("intensity", "normal")),
    )

    normalized = {
        "predicted_phase": predicted_phase,
        "predicted_score": predicted_score,
        "predicted_gate_result": predicted_gate_result,
        "phase_transition": data.get(
            "phase_transition",
            gate.get("phase_transition", gate.get("transition", f"{predicted_phase}->{predicted_phase}")),
        ),
        "gate_confidence": data.get(
            "gate_confidence",
            gate.get("gate_confidence", gate.get("confidence", 60)),
        ),
        "gate_rationale": data.get(
            "gate_rationale",
            gate.get(
                "gate_rationale",
                gate.get("rationale", gate_text or data.get("market_summary", "模型未提供门控理由")),
            ),
        ),
        "strategy_name": strategy_name,
        "strategy_intensity": strategy_intensity,
        "strategy_summary": data.get(
            "strategy_summary",
            strategy.get(
                "strategy_summary",
                strategy.get("summary", strategy.get("description", strategy_text)),
            ),
        ),
        "allow_roles": data.get(
            "allow_roles",
            strategy.get("allow_roles", strategy.get("roles", _default_allow_roles(strategy_name))),
        ),
        "buy_candidates": data.get(
            "buy_candidates",
            data.get("candidates", data.get("buy_list", data.get("stocks_to_buy", []))),
        ),
        "sell_forecasts": data.get(
            "sell_forecasts",
            data.get("sell_warnings", data.get("sell_candidates", [])),
        ),
        "market_summary": data.get(
            "market_summary",
            data.get("summary", data.get("market_analysis", data.get("overall_assessment", ""))),
        ),
        "risk_warnings": data.get(
            "risk_warnings",
            data.get("risks", data.get("risk_alerts", [])),
        ),
    }

    if not isinstance(normalized["allow_roles"], list):
        normalized["allow_roles"] = _default_allow_roles(strategy_name)

    normalized["buy_candidates"] = [
        _normalize_buy_candidate(item)
        for item in normalized["buy_candidates"]
        if isinstance(item, dict)
    ]
    normalized["sell_forecasts"] = [
        normalized_item
        for item in normalized["sell_forecasts"]
        for normalized_item in [_normalize_sell_forecast_item(item)]
        if normalized_item is not None
    ]
    if isinstance(normalized["risk_warnings"], str):
        normalized["risk_warnings"] = [normalized["risk_warnings"]]

    return normalized


# ─── 客户端 ───


class AIForecastClient:
    """封装 OpenAI 调用，通过结构化输出返回预测结果。"""

    def __init__(self, settings: Settings) -> None:
        base_url = (settings.ai_api_base_url or "").rstrip("/") or None
        default_headers: dict[str, str] | None = None

        # Some OpenAI-compatible gateways apply WAF rules to Python SDK defaults.
        # For custom base URLs, using a curl-like UA avoids false positives.
        if base_url:
            default_headers = {
                "User-Agent": settings.ai_user_agent,
                "Accept": "*/*",
            }

        # Configure proxy only when explicitly enabled for AI traffic.
        if settings.ai_use_env_proxy and settings.http_proxy:
            os.environ["HTTP_PROXY"] = settings.http_proxy
            logger.info("HTTP_PROXY configured: %s", settings.http_proxy)
        if settings.ai_use_env_proxy and settings.https_proxy:
            os.environ["HTTPS_PROXY"] = settings.https_proxy
            logger.info("HTTPS_PROXY configured: %s", settings.https_proxy)

        logger.info(
            "Initializing AIForecastClient with base_url=%s, model=%s, timeout=%d, max_retries=%d",
            base_url,
            settings.ai_model,
            settings.ai_timeout,
            settings.ai_max_retries,
        )
        if not settings.ai_api_key:
            raise ValueError("Missing AI API key. Set OPENAI_API_KEY or ASHORT_AI_API_KEY.")

        http_client = httpx.Client(
            timeout=settings.ai_timeout,
            trust_env=settings.ai_use_env_proxy,
            headers=default_headers,
        )

        self._client = OpenAI(
            api_key=settings.ai_api_key,
            base_url=base_url,
            timeout=settings.ai_timeout,
            default_headers=default_headers,
            http_client=http_client,
        )
        self._model = settings.ai_model
        self._temperature = settings.ai_temperature
        self._reasoning_effort = settings.ai_reasoning_effort or None
        self._max_retries = settings.ai_max_retries
        logger.info("AIForecastClient initialized successfully")

    def forecast(
        self,
        system_prompt: str,
        user_prompt: str,
        valid_codes: set[str] | None = None,
    ) -> AIForecastResponse:
        """调用 AI 生成预测，返回校验过的结构化结果。

        Args:
            system_prompt: 系统提示词
            user_prompt: 用户提示词（含市场数据）
            valid_codes: 今日涨停板代码集合，用于校验候选股

        Returns:
            校验通过的 AIForecastResponse，全部失败则返回保守默认值
        """
        logger.info(
            "Starting forecast with model=%s, reasoning_effort=%s, max_retries=%d",
            self._model,
            self._reasoning_effort,
            self._max_retries,
        )
        messages = [
            {"role": "system", "content": f"{system_prompt}\n\n{_OUTPUT_SCHEMA_INSTRUCTIONS}"},
            {"role": "user", "content": user_prompt},
        ]

        last_error = ""
        for attempt in range(1, self._max_retries + 1):
            try:
                if last_error:
                    retry_messages = [
                        *messages,
                        {
                            "role": "system",
                            "content": (
                                "你必须严格按照给定的 JSON Schema 返回。"
                                " 修正上次输出中的问题后重新生成完整结果。"
                                f"\n上次输出的问题:\n{last_error}"
                            ),
                        },
                    ]
                else:
                    retry_messages = messages

                resp = self._client.chat.completions.create(
                    model=self._model,
                    messages=retry_messages,
                    max_completion_tokens=8192,
                    reasoning_effort=self._reasoning_effort,
                    temperature=self._temperature,
                    response_format={"type": "json_object"},
                )
                message = resp.choices[0].message
                if getattr(message, "refusal", None):
                    last_error = f"Model refusal: {message.refusal}"
                    logger.warning("Attempt %d: %s", attempt, last_error)
                    continue

                raw_content = message.content or ""
                raw_content = _strip_json_fence(raw_content)
                if not raw_content:
                    last_error = "AI response content is empty"
                    logger.warning("Attempt %d: %s", attempt, last_error)
                    continue
                data = json.loads(raw_content)
                normalized = _normalize_forecast_payload(data)
                result = AIForecastResponse.model_validate(normalized)

                consistency_errors = _validate_consistency(result, valid_codes)
                if consistency_errors:
                    last_error = "\n".join(consistency_errors)
                    logger.warning(
                        "Attempt %d: consistency check failed: %s",
                        attempt,
                        last_error,
                    )
                    continue

                logger.info("AI forecast succeeded on attempt %d", attempt)
                return result

            except (json.JSONDecodeError, ValidationError) as e:
                last_error = f"Schema validation error: {e}"
                logger.warning("Attempt %d: %s", attempt, last_error)
            except Exception as e:
                last_error = f"Error: {e}"
                logger.warning("Attempt %d: %s", attempt, last_error)

        logger.error(
            "AI forecast failed after %d attempts, using default. Last error: %s",
            self._max_retries,
            last_error,
        )
        return _default_response()
