import os

from .prompts import (
    SYSTEM_INSTRUCTION,
    build_cultural_translation_prompt,
    build_cultural_translation_prompt_no_hints,
    split_description_and_terms,
)


def _build_prompt(description, terms_translation, use_hints):
    if use_hints:
        return build_cultural_translation_prompt(description, terms_translation)
    return build_cultural_translation_prompt_no_hints(description)


def translate_cultural_description_with_gpt(
    description,
    terms_translation,
    api_key=None,
    model="gpt-5-mini",
    use_hints=True,
):
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise ImportError("The 'openai' package was not found. Install it with: pip install -U openai") from exc

    client = OpenAI(api_key=api_key or os.getenv("OPENAI_API_KEY"))
    prompt = _build_prompt(description, terms_translation, use_hints)

    response = client.responses.create(
        model=model,
        reasoning={"effort": "low"},
        text={"verbosity": "low"},
        input=[
            {
                "role": "system",
                "content": [{"type": "input_text", "text": SYSTEM_INSTRUCTION}],
            },
            {
                "role": "user",
                "content": [{"type": "input_text", "text": prompt}],
            },
        ],
    )

    translation = response.output_text.strip()
    if not translation:
        raise RuntimeError("OpenAI returned an empty translation.")
    return translation


def translate_cultural_description_with_gemini(
    description,
    terms_translation,
    api_key=None,
    model="gemini-3.5-flash",
    use_hints=True,
    thinking_level="low",
    retry_attempts=8,
    retry_max_delay=120.0,
):
    try:
        from google import genai
        from google.genai import types
    except ImportError as exc:
        raise ImportError(
            "The 'google-genai' package was not found. Install it with: pip install -U google-genai"
        ) from exc

    resolved_api_key = api_key or os.getenv("GEMINI_API_KEY")
    # Gemini returns transient 503 UNAVAILABLE ("high demand") under load.
    # The SDK default is only ~5 retries over ~60s, which sustained overload
    # outlasts, so we extend the retry budget here (408/429/5xx are retried
    # by default).
    http_options = types.HttpOptions(
        retry_options=types.HttpRetryOptions(
            attempts=retry_attempts,
            initial_delay=2.0,
            max_delay=retry_max_delay,
            exp_base=2.0,
            jitter=1.0,
        )
    )
    client = (
        genai.Client(api_key=resolved_api_key, http_options=http_options)
        if resolved_api_key
        else genai.Client(http_options=http_options)
    )
    prompt = _build_prompt(description, terms_translation, use_hints)

    config_kwargs = {"system_instruction": SYSTEM_INSTRUCTION}
    if thinking_level is not None:
        config_kwargs["thinking_config"] = types.ThinkingConfig(thinking_level=thinking_level)

    response = client.models.generate_content(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(**config_kwargs),
    )

    translation = (response.text or "").strip()
    if not translation:
        raise RuntimeError("Gemini returned an empty translation.")
    return translation


def google_translate_text(text, source="el", target="en"):
    if not text or not text.strip():
        return ""

    try:
        from deep_translator import GoogleTranslator
    except ImportError as exc:
        raise ImportError(
            "The 'deep-translator' package was not found. Install it with: pip install -U deep-translator"
        ) from exc

    return GoogleTranslator(source=source, target=target).translate(text.strip())


def translate_cultural_block_with_gpt(raw_text, api_key=None, model="gpt-5-mini", use_hints=True):
    description, terms_translation = split_description_and_terms(raw_text)
    return translate_cultural_description_with_gpt(
        description=description,
        terms_translation=terms_translation,
        api_key=api_key,
        model=model,
        use_hints=use_hints,
    )


def translate_cultural_block_with_gemini(
    raw_text,
    api_key=None,
    model="gemini-3.5-flash",
    use_hints=True,
    thinking_level="low",
):
    description, terms_translation = split_description_and_terms(raw_text)
    return translate_cultural_description_with_gemini(
        description=description,
        terms_translation=terms_translation,
        api_key=api_key,
        model=model,
        use_hints=use_hints,
        thinking_level=thinking_level,
    )
