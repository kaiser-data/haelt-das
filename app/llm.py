"""Single gateway for every Nebius Token Factory call. Every call is logged so the UI can show it."""
import contextvars
import json
import os
import re
import time

import httpx

BASE = "https://api.tokenfactory.nebius.com/v1"

MODEL_FAST = "Qwen/Qwen3-30B-A3B-Instruct-2507"
MODEL_VISION = "google/gemma-3-27b-it"
MODEL_VISION_STRONG = "moonshotai/Kimi-K3"
MODEL_EMBED = "Qwen/Qwen3-Embedding-8B"
MODEL_DECIDE = "deepseek-ai/DeepSeek-V4-Pro-0813"
MODEL_DECIDE_FALLBACK = "deepseek-ai/DeepSeek-V4.1-Flash-1017"

call_log: contextvars.ContextVar = contextvars.ContextVar("call_log", default=None)
CONNECT_TIMEOUT = 5  # a dead host shows up in seconds; only reading the answer may take long
_client = httpx.AsyncClient(timeout=httpx.Timeout(120, connect=CONNECT_TIMEOUT))


def _headers():
    return {"Authorization": f"Bearer {os.environ['NEBIUS_API_KEY']}"}


def _log(entry):
    log = call_log.get()
    if log is not None:
        log.append(entry)


async def _post(path, payload, purpose):
    t = time.time()
    resp = await _client.post(BASE + path, json=payload, headers=_headers())
    ms = int((time.time() - t) * 1000)
    data = resp.json() if resp.status_code == 200 else {"error": resp.text[:300]}
    usage = data.get("usage") or {}
    _log({
        "purpose": purpose,
        "model": payload.get("model"),
        "status": resp.status_code,
        "ms": ms,
        "prompt_tokens": usage.get("prompt_tokens"),
        "completion_tokens": usage.get("completion_tokens"),
        "ts": int(t),
    })
    if resp.status_code != 200:
        raise RuntimeError(f"Nebius {payload.get('model')} HTTP {resp.status_code}: {resp.text[:200]}")
    return data


def _parse_json(text):
    text = re.sub(r"<think>.*?</think>", "", text or "", flags=re.S).strip()
    m = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if m:
        text = m.group(1)
    start = min([i for i in (text.find("{"), text.find("[")) if i != -1], default=-1)
    if start == -1:
        raise ValueError(f"no JSON in model output: {text[:200]}")
    end = max(text.rfind("}"), text.rfind("]"))
    return json.loads(text[start:end + 1])


async def chat_json(prompt, *, system=None, model=MODEL_FAST, purpose="", max_tokens=1500, images=None):
    content = prompt
    if images:
        content = [{"type": "text", "text": prompt}] + [
            {"type": "image_url", "image_url": {"url": u}} for u in images
        ]
    messages = ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": content}]
    data = await _post("/chat/completions", {
        "model": model, "messages": messages, "max_tokens": max_tokens, "temperature": 0.1,
    }, purpose)
    msg = data["choices"][0]["message"]
    out = _parse_json(msg.get("content") or "")
    log = call_log.get()
    if log:
        log[-1]["output_preview"] = json.dumps(out, ensure_ascii=False)[:400]
    return out


async def decide(prompt, *, system, purpose="final verdict"):
    try:
        return await chat_json(prompt, system=system, model=MODEL_DECIDE, purpose=purpose, max_tokens=4000)
    except Exception:
        return await chat_json(prompt, system=system, model=MODEL_DECIDE_FALLBACK, purpose=purpose + " (fallback)", max_tokens=4000)


async def embed(texts, purpose="embed"):
    data = await _post("/embeddings", {"model": MODEL_EMBED, "input": texts}, purpose)
    return [d["embedding"] for d in data["data"]]
