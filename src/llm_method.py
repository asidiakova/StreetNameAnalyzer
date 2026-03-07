#!/usr/bin/env python3
"""
LLM-based street name normalization.

Uses large language models' world knowledge to identify the person, place,
or concept a street is named after. Supports multiple providers (OpenAI,
Anthropic, Google Gemini) through a single factory function — each call
creates an independent normalizer with its own state and disk cache.

See docs/llm.md for detailed description, examples, and known limitations.
"""

import json
import os
import re
import time

from anthropic import Anthropic
from google import genai
from google.genai.types import GenerateContentConfig
from openai import OpenAI

from text_utils import ascii_norm

SYSTEM_PROMPT = (
    "You analyze Slovak street names. Given a street name, identify what person, "
    "place, or concept it is named after and return the canonical form.\n\n"
    "Rules:\n"
    "- If named after a person, return their full name in Slovak nominative case\n"
    "- If the name is descriptive (e.g., Hlavná, Lipová, Krátka), return it unchanged\n"
    "- If named after a place, return the place name\n"
    "- Return ONLY the canonical name, no explanation or extra punctuation"
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
        "base_url": None,
        "api_key_env": "OPENAI_API_KEY",
        "type": "openai",
    },
    "anthropic": {
        "base_url": None,
        "api_key_env": "ANTHROPIC_API_KEY",
        "type": "anthropic",
    },
    "gemini": {
        "base_url": None,
        "api_key_env": "GEMINI_API_KEY",
        "type": "gemini",
    },
}

LLM_REQUEST_DELAY = 0.05


def _sanitize_for_filename(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]", "_", name)


def create_llm_normalizer(provider: str, model: str, cache_dir: str = "."):
    """
    Factory that returns a normalize function for a given LLM provider/model.

    The API client is created lazily on the first call. Results are cached
    to a JSON file on disk so repeated runs incur zero API cost.

    Args:
        provider: One of "openai", "anthropic", "gemini"
        model: Model identifier (e.g., "gpt-4o-mini", "claude-haiku-4-5-20251001", "gemini-2.0-flash")
        cache_dir: Directory for the per-model cache file
    """
    if provider not in PROVIDERS:
        raise ValueError(f"Unknown provider '{provider}'. Available: {list(PROVIDERS.keys())}")

    config = PROVIDERS[provider]
    cache_file = os.path.join(cache_dir, f"llm_cache_{_sanitize_for_filename(model)}.json")

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
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(_state["cache"], f, ensure_ascii=False, indent=2)

    def _init_client():
        api_key = os.environ.get(config["api_key_env"])
        if not api_key:
            raise RuntimeError(
                f"Set {config['api_key_env']} environment variable for provider '{provider}'"
            )

        if config["type"] == "openai":
            kwargs = {"api_key": api_key}
            if config["base_url"]:
                kwargs["base_url"] = config["base_url"]
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

    def normalize(name: str) -> str:
        if _state["cache"] is None:
            _state["cache"] = _load_cache()

        if name in _state["cache"]:
            return _state["cache"][name]

        if _state["client"] is None:
            _state["client"] = _init_client()

        if _state["call_count"] > 0:
            time.sleep(LLM_REQUEST_DELAY)

        try:
            raw = _call_api(name)
            canonical = raw.strip().strip('"\'').split("\n")[0].strip()
            if not canonical:
                canonical = name
            group_id = ascii_norm(canonical)
        except Exception as e:
            print(f"  LLM error for '{name}': {e}")
            group_id = ascii_norm(name)

        _state["call_count"] += 1
        _state["cache"][name] = group_id
        _save_cache()

        return group_id

    return normalize
