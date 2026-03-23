#!/usr/bin/env python3
"""
LLM-based street name normalization.

Uses large language models to identify the person, place, or concept a street is named after.
"""

import json
import os
import re
import time
from datetime import date

from anthropic import Anthropic
from google import genai
from google.genai.types import GenerateContentConfig
from openai import OpenAI

from src.config import LLM_FALLBACK_ON_ERROR
from src.text_utils import ascii_norm

_MODULE_DIR = os.path.dirname(os.path.abspath(__file__))

SYSTEM_PROMPT = (
    "You analyze Slovak street names. Given a street name, identify what person, "
    "place, or concept it is named after and return the canonical form.\n\n"
    "Rules:\n"
    "- If named after a person, return their full name in Slovak nominative case\n"
    "- If the name is descriptive (e.g., Hlavná, Lipová, Krátka), return it unchanged\n"
    "- If named after a place, return the place name\n"
    "- Return ONLY the canonical name, no explanation or extra punctuation"
)

BATCH_SYSTEM_PROMPT = (
    SYSTEM_PROMPT +
    "\n\nYou will receive multiple street names at once. "
    "Return a JSON object mapping each input street name (exactly as given) "
    "to its canonical form. Return ONLY valid JSON, no markdown or code blocks."
)

FEW_SHOT = (
    'Examples:\n'
    '"Štefánikova" → Milan Rastislav Štefánik\n'
    '"M. R. Štefánika" → Milan Rastislav Štefánik\n'
    '"Námestie gen. Štefánika" → Milan Rastislav Štefánik\n'
    '"Komenského" → Jan Amos Komenský\n'
    '"Hviezdoslavova" → Pavol Országh Hviezdoslav\n'
    '"Lipová" → Lipová\n'
    '"Hlavná" → Hlavná\n'
)

PROVIDERS = {
    "openai": {
        "api_key_env": "OPENAI_API_KEY",
        "type": "openai",
    },
    "anthropic": {
        "api_key_env": "ANTHROPIC_API_KEY",
        "type": "anthropic",
    },
    "gemini": {
        "api_key_env": "GEMINI_API_KEY",
        "type": "gemini",
    },
}

LLM_REQUEST_DELAY = 0.05
BATCH_SIZE = 40


def create_llm_normalizer(provider: str, model: str, cache_dir: str = _MODULE_DIR):
    """
    Factory that returns a normalize function for a given LLM provider/model.

    The API client is created on the first call. Results are cached to a JSON file.

    Uses LLM_FALLBACK_ON_ERROR from config: when False, failures are cached as ""
    and normalize returns "" (no ascii_norm(name) substitute).
    """
    use_fallback = LLM_FALLBACK_ON_ERROR
    config = PROVIDERS[provider]
    filename = re.sub(r"[^a-zA-Z0-9_-]", "_", model)
    cache_file = os.path.join(cache_dir, f"llm_cache_{filename}.json")

    _state = {
        "client": None,
        "cache": None,
        "call_count": 0,
    }

    def _load_cache() -> dict:
        if os.path.exists(cache_file):
            with open(cache_file, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    def _save_cache():
        _state["cache"]["_last_updated"] = str(date.today())
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(_state["cache"], f, ensure_ascii=False, indent=2)

    def _init_client():
        api_key = os.environ.get(config["api_key_env"])

        if config["type"] == "openai":
            kwargs = {"api_key": api_key}
            return OpenAI(**kwargs)
        elif config["type"] == "anthropic":
            return Anthropic(api_key=api_key)
        else:
            return genai.Client(api_key=api_key)

    def _call_api(name: str) -> str:
        user_msg = f'{FEW_SHOT}\nStreet name: "{name}"'

        if config["type"] == "openai":
            response = _state["client"].chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_msg},
                ],
                max_tokens=100,
                temperature=0,
            )
            return response.choices[0].message.content.strip()
        elif config["type"] == "anthropic":
            response = _state["client"].messages.create(
                model=model,
                max_tokens=100,
                temperature=0,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_msg}],
            )
            return response.content[0].text.strip()
        else:
            response = _state["client"].models.generate_content(
                model=model,
                contents=user_msg,
                config=GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    max_output_tokens=100,
                    temperature=0,
                ),
            )
            return response.text.strip()

    def _call_batch_api(names: list[str]) -> dict[str, str]:
        names_list = "\n".join(f'"{n}"' for n in names)
        user_msg = f'{FEW_SHOT}\nProcess these street names:\n{names_list}'

        if config["type"] == "openai":
            response = _state["client"].chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": BATCH_SYSTEM_PROMPT},
                    {"role": "user", "content": user_msg},
                ],
                max_tokens=4096,
                temperature=0,
            )
            raw = response.choices[0].message.content.strip()
        elif config["type"] == "anthropic":
            response = _state["client"].messages.create(
                model=model,
                max_tokens=4096,
                temperature=0,
                system=BATCH_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_msg}],
            )
            raw = response.content[0].text.strip()
        else:
            response = _state["client"].models.generate_content(
                model=model,
                contents=user_msg,
                config=GenerateContentConfig(
                    system_instruction=BATCH_SYSTEM_PROMPT,
                    max_output_tokens=4096,
                    temperature=0,
                ),
            )
            raw = response.text.strip()

        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()

        return json.loads(raw)

    def batch_warm(names: list[str]):
        if _state["cache"] is None:
            _state["cache"] = _load_cache()

        uncached = [n for n in names if n not in _state["cache"]]

        if _state["client"] is None:
            _state["client"] = _init_client()

        total_batches = (len(uncached) + BATCH_SIZE - 1) // BATCH_SIZE
        print(f"    Batch warming {len(uncached)} uncached names "
              f"({total_batches} batches of up to {BATCH_SIZE})...")

        for i in range(0, len(uncached), BATCH_SIZE):
            batch = uncached[i:i + BATCH_SIZE]
            batch_num = i // BATCH_SIZE + 1

            if _state["call_count"] > 0:
                time.sleep(LLM_REQUEST_DELAY)

            try:
                results = _call_batch_api(batch)
                for name in batch:
                    raw = results.get(name)
                    if raw is None:
                        if use_fallback:
                            _state["cache"][name] = ascii_norm(name)
                        else:
                            _state["cache"][name] = ""
                        continue
                    canonical = str(raw).strip().strip('"\'').split("\n")[0].strip()
                    if not canonical:
                        if use_fallback:
                            _state["cache"][name] = ascii_norm(name)
                        else:
                            _state["cache"][name] = ""
                        continue
                    _state["cache"][name] = ascii_norm(canonical)
            except Exception as e:
                print(f"    Batch {batch_num}/{total_batches} failed: {e}")
                for name in batch:
                    if name not in _state["cache"]:
                        _state["cache"][name] = ascii_norm(name) if use_fallback else ""

            _state["call_count"] += 1
            _save_cache()

            if batch_num % 10 == 0 or batch_num == total_batches:
                print(f"    {batch_num}/{total_batches} batches done")

    def normalize(name: str) -> str:
        if _state["cache"] is None:
            _state["cache"] = _load_cache()

        if name in _state["cache"]:
            return _state["cache"][name]  # may be "" (cached failure)

        if _state["client"] is None:
            _state["client"] = _init_client()

        if _state["call_count"] > 0:
            time.sleep(LLM_REQUEST_DELAY)

        try:
            raw = _call_api(name)
            canonical = raw.strip().strip('"\'').split("\n")[0].strip()
            if not canonical:
                group_id = ascii_norm(name) if use_fallback else ""
            else:
                group_id = ascii_norm(canonical)
        except Exception as e:
            print(f"  LLM error for '{name}': {e}")
            group_id = ascii_norm(name) if use_fallback else ""

        _state["call_count"] += 1
        _state["cache"][name] = group_id
        _save_cache()

        return group_id

    def cache_date() -> str | None:
        if _state["cache"] is None:
            _state["cache"] = _load_cache()
        return _state["cache"].get("_last_updated")

    normalize.batch_warm = batch_warm
    normalize.cache_date = cache_date
    return normalize
