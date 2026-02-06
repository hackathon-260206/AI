import hashlib
import json
import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

try:
    import requests
except ImportError:  # pragma: no cover
    requests = None


_LOCKS: dict[str, threading.Lock] = {}
_GLOBAL_LOCK = threading.Lock()


def _get_lock(key: str) -> threading.Lock:
    with _GLOBAL_LOCK:
        lock = _LOCKS.get(key)
        if lock is None:
            lock = threading.Lock()
            _LOCKS[key] = lock
        return lock


def _strip_code_fence(text: str) -> str:
    value = (text or "").strip()
    if value.startswith("```"):
        lines = value.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        value = "\n".join(lines).strip()
    return value


def _extract_json_object(text: str) -> dict[str, Any]:
    cleaned = _strip_code_fence(text)
    try:
        obj = json.loads(cleaned)
    except Exception:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise ValueError("No JSON object found in model output.")
        obj = json.loads(cleaned[start : end + 1])
    if not isinstance(obj, dict):
        raise ValueError("Model output is not a JSON object.")
    return obj


def _extract_text_from_gemini_response(data: dict[str, Any]) -> str:
    candidates = data.get("candidates", [])
    if not isinstance(candidates, list) or not candidates:
        raise ValueError("Gemini response has no candidates.")
    first = candidates[0]
    if not isinstance(first, dict):
        raise ValueError("Gemini candidate shape is invalid.")
    content = first.get("content", {})
    if not isinstance(content, dict):
        raise ValueError("Gemini candidate content is invalid.")
    parts = content.get("parts", [])
    if not isinstance(parts, list) or not parts:
        raise ValueError("Gemini response has no text parts.")
    chunks: list[str] = []
    for part in parts:
        if isinstance(part, dict) and isinstance(part.get("text"), str):
            chunks.append(part["text"])
    text = "\n".join(chunks).strip()
    if not text:
        raise ValueError("Gemini response text is empty.")
    return text


def _call_gemini_http(prompt: str, model: str, timeout: int) -> str:
    if requests is None:
        raise RuntimeError("requests is required for gemini_http provider. Install with: pip install requests")
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY (or GOOGLE_API_KEY) is not set. --fill-cards cannot run.")

    payload = {
        "systemInstruction": {
            "parts": [
                {"text": "Return JSON object only. No markdown, no extra text."}
            ]
        },
        "contents": [
            {
                "role": "user",
                "parts": [{"text": prompt}],
            }
        ],
        "generationConfig": {
            "responseMimeType": "application/json",
        },
    }

    response = requests.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        headers={
            "Content-Type": "application/json",
        },
        params={"key": api_key},
        json=payload,
        timeout=timeout,
    )
    if response.status_code >= 400:
        raise RuntimeError(f"Gemini HTTP {response.status_code}: {response.text[:300]}")
    data = response.json()
    return _extract_text_from_gemini_response(data)


def _trim_one_line_reason(value: Any) -> str:
    text = str(value or "").replace("\r", " ").replace("\n", " ").strip()
    if len(text) > 35:
        text = text[:35].strip()
    return text


def _fallback_card(validator: dict[str, Any]) -> dict[str, Any]:
    mentor_id = validator["mentor_id"]
    overlap_topics = list(validator.get("overlap", {}).get("topics", []))
    overlap_stacks = list(validator.get("overlap", {}).get("stacks", []))
    overlap_tags = (overlap_topics + overlap_stacks)[:6]
    u_topics = set(validator.get("U_topics", []))
    m_topics = set(validator.get("M_topics", []))
    missing = sorted(u_topics - m_topics)[:3]
    caution_points = [f"\ubcf4\uc644: {tag}" for tag in missing]
    return {
        "mentor_id": mentor_id,
        "one_line_reason": "\uacb9\uce58\ub294 \ud0dc\uadf8 \uae30\ubc18 \ucd94\ucc9c",
        "overlap_tags": overlap_tags,
        "caution_points": caution_points,
    }


def _validate_card(card: dict[str, Any], validator: dict[str, Any]) -> dict[str, Any]:
    required = {"mentor_id", "one_line_reason", "overlap_tags", "caution_points"}
    if not isinstance(card, dict):
        raise ValueError("Card must be a dict JSON.")
    if not required.issubset(card.keys()):
        missing = sorted(required - set(card.keys()))
        raise ValueError(f"Missing required keys: {missing}")

    req_mentor_id = validator["mentor_id"]
    if str(card["mentor_id"]) != str(req_mentor_id):
        raise ValueError("mentor_id mismatch.")

    reason = _trim_one_line_reason(card["one_line_reason"])
    if not reason:
        reason = "\uacb9\uce58\ub294 \ud0dc\uadf8 \uae30\ubc18 \ucd94\ucc9c"

    overlap_topics = validator.get("overlap", {}).get("topics", [])
    overlap_stacks = validator.get("overlap", {}).get("stacks", [])
    allowed_tags = set(overlap_topics + overlap_stacks)
    provided_overlap = card.get("overlap_tags", [])
    if not isinstance(provided_overlap, list):
        raise ValueError("overlap_tags must be a list.")
    overlap_tags = []
    for tag in provided_overlap:
        if isinstance(tag, str) and tag in allowed_tags:
            overlap_tags.append(tag)
    overlap_tags = overlap_tags[:6]

    caution_points = card.get("caution_points", [])
    if not isinstance(caution_points, list):
        raise ValueError("caution_points must be a list.")
    cautions = [str(x).strip() for x in caution_points if isinstance(x, str) and str(x).strip()]

    return {
        "mentor_id": req_mentor_id,
        "one_line_reason": reason,
        "overlap_tags": overlap_tags,
        "caution_points": cautions,
    }


def _load_cached_card(cache_file: str, validator: dict[str, Any]) -> dict[str, Any] | None:
    if not os.path.exists(cache_file):
        return None
    try:
        with open(cache_file, "r", encoding="utf-8") as f:
            cached = json.load(f)
        return _validate_card(cached, validator)
    except Exception:
        return None


def _save_cache(cache_file: str, card: dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(cache_file), exist_ok=True)
    with open(cache_file, "w", encoding="utf-8") as f:
        json.dump(card, f, ensure_ascii=False, indent=2)


def _fill_one(
    prompt_item: dict[str, Any],
    validator: dict[str, Any],
    provider: str,
    model: str,
    timeout: int,
    cache_dir: str,
    retry: int,
) -> dict[str, Any]:
    mentor_id = prompt_item["mentor_id"]
    prompt = str(prompt_item["prompt_for_llm"])
    key = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    cache_file = os.path.join(cache_dir, f"{key}.json")
    lock = _get_lock(key)

    with lock:
        cached = _load_cached_card(cache_file, validator)
        if cached is not None:
            return cached

    attempts = 1 + max(0, int(retry))
    last_exc: Exception | None = None
    for _ in range(attempts):
        try:
            if provider != "gemini_http":
                raise RuntimeError(f"Unsupported llm provider: {provider}")
            raw_text = _call_gemini_http(prompt, model=model, timeout=timeout)
            parsed = _extract_json_object(raw_text)
            valid = _validate_card(parsed, validator)
            with lock:
                _save_cache(cache_file, valid)
            return valid
        except Exception as exc:
            last_exc = exc

    fallback = _fallback_card(validator)
    with lock:
        _save_cache(cache_file, fallback)
    if last_exc:
        fallback["error"] = str(last_exc)
    fallback["mentor_id"] = mentor_id
    return fallback


def fill_cards(
    top5_card_prompts: list[dict[str, Any]],
    validator_payloads: list[dict[str, Any]],
    provider: str = "gemini_http",
    model: str = "gemini-2.0-flash",
    timeout: int = 10,
    max_concurrency: int = 3,
    cache_dir: str = "./cache/cards",
    retry: int = 1,
) -> list[dict[str, Any]]:
    if provider == "gemini_http" and not (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")):
        raise RuntimeError("GEMINI_API_KEY (or GOOGLE_API_KEY) is not set. --fill-cards cannot run.")

    if len(top5_card_prompts) != len(validator_payloads):
        raise ValueError("top5_card_prompts and validator_payloads length mismatch.")

    validators_by_id = {str(v["mentor_id"]): v for v in validator_payloads}
    ordered_ids = [str(item["mentor_id"]) for item in top5_card_prompts]

    jobs: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for item in top5_card_prompts:
        key = str(item["mentor_id"])
        validator = validators_by_id.get(key)
        if validator is None:
            raise ValueError(f"validator payload missing for mentor_id={key}")
        jobs.append((item, validator))

    cards_by_id: dict[str, dict[str, Any]] = {}
    pool_size = max(1, int(max_concurrency))
    with ThreadPoolExecutor(max_workers=pool_size) as executor:
        future_to_id = {
            executor.submit(
                _fill_one,
                prompt_item,
                validator,
                provider,
                model,
                int(timeout),
                cache_dir,
                int(retry),
            ): str(prompt_item["mentor_id"])
            for prompt_item, validator in jobs
        }
        for future in as_completed(future_to_id):
            mentor_id = future_to_id[future]
            try:
                cards_by_id[mentor_id] = future.result()
            except Exception:
                cards_by_id[mentor_id] = _fallback_card(validators_by_id[mentor_id])

    return [cards_by_id[mid] for mid in ordered_ids]
