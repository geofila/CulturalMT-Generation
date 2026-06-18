import os
from pathlib import Path

from .prompts import (
    SYSTEM_INSTRUCTION,
    build_cultural_translation_prompt,
    build_cultural_translation_prompt_no_hints,
    split_description_and_terms,
)


def _build_prompt(description, terms_translation, use_hints, has_image_context=False):
    if use_hints:
        return build_cultural_translation_prompt(
            description,
            terms_translation,
            has_image_context=has_image_context,
        )
    return build_cultural_translation_prompt_no_hints(
        description,
        has_image_context=has_image_context,
    )


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
    image_path=None,
    image_mime_type=None,
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
    # A per-request timeout is essential: without it a connection that the
    # server accepts but never replies on (seen under the same overload that
    # produces 503s) leaves the client blocked on recv() indefinitely. The
    # retry options above only fire on error responses or connection failures,
    # not on a silently stalled-but-open socket, so the timeout is what lets a
    # hung request fail and be retried. Value is in milliseconds.
    http_options = types.HttpOptions(
        timeout=120_000,
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
    has_image_context = bool(image_path)
    prompt = _build_prompt(
        description,
        terms_translation,
        use_hints,
        has_image_context=has_image_context,
    )

    config_kwargs = {
        "system_instruction": SYSTEM_INSTRUCTION,
        # Museum/archaeological catalogue text legitimately describes nudity,
        # erotic scenes, etc. The default safety filters return an empty
        # response on those, so disable them for this translation task.
        "safety_settings": [
            types.SafetySetting(category=c, threshold=types.HarmBlockThreshold.OFF)
            for c in (
                types.HarmCategory.HARM_CATEGORY_HARASSMENT,
                types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
                types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
                types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
            )
        ],
    }
    if thinking_level is not None:
        config_kwargs["thinking_config"] = types.ThinkingConfig(thinking_level=thinking_level)

    contents = prompt
    if image_path:
        image_bytes = Path(image_path).read_bytes()
        contents = [
            prompt,
            types.Part.from_bytes(
                data=image_bytes,
                mime_type=image_mime_type or "image/jpeg",
            ),
        ]

    response = client.models.generate_content(
        model=model,
        contents=contents,
        config=types.GenerateContentConfig(**config_kwargs),
    )

    translation = (response.text or "").strip()
    if not translation:
        # Surface the real cause instead of a generic message, so a safety
        # block is distinguishable from recitation / token-budget exhaustion.
        reason = ""
        try:
            cand = (response.candidates or [None])[0]
            finish_reason = getattr(cand, "finish_reason", None)
            block_reason = getattr(
                getattr(response, "prompt_feedback", None), "block_reason", None
            )
            reason = f" (finish_reason={finish_reason}, block_reason={block_reason})"
        except Exception:
            pass
        raise RuntimeError(f"Gemini returned an empty translation.{reason}")
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
    image_path=None,
    image_mime_type=None,
):
    description, terms_translation = split_description_and_terms(raw_text)
    return translate_cultural_description_with_gemini(
        description=description,
        terms_translation=terms_translation,
        api_key=api_key,
        model=model,
        use_hints=use_hints,
        thinking_level=thinking_level,
        image_path=image_path,
        image_mime_type=image_mime_type,
    )
