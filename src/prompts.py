import re


SYSTEM_INSTRUCTION = (
    "Translate faithfully from Greek to English for cultural heritage documentation. "
    "Use any attached image only as auxiliary context for disambiguation. "
    "Do not enrich the source text with details seen only in the image. "
    "Output only the final translation."
)


def split_description_and_terms(raw_text):
    text = (raw_text or "").strip()
    pattern = r"Description:\s*(.*?)\s*Terms\s*Translation\s*(.*)"
    match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
    if not match:
        raise ValueError("Could not find valid 'Description:' and 'Terms Translation' sections.")

    description = match.group(1).strip()
    terms_translation = match.group(2).strip()
    return description, terms_translation


def _visual_context_block(has_image_context):
    if not has_image_context:
        return ""

    return """Visual context:
- A thumbnail image is attached as optional supporting context.
- Use the image only when it helps disambiguate an object, material, iconographic element, inscription, color, shape, damage, or other term already present in the Greek text.
- Do not add information that appears only in the image.
- Do not broaden, decorate, or enrich the translation because of the image.

"""


def build_cultural_translation_prompt(description, terms_translation, has_image_context=False):
    visual_context = _visual_context_block(has_image_context)
    return f"""You are an expert translator of cultural heritage documentation from Greek into English.

Task:
- Translate the description below into English.
- Use the provided term mappings as strong contextual hints for this specific cultural heritage domain.
- Prioritize precise, natural, museum-grade and documentation-appropriate terminology.
- Be especially careful with Byzantine art terminology, iconography, portable icons, inscriptions, garments, materials, condition issues, and conservation language.
- Do not translate mechanically from the hints if a hint does not fit the actual meaning.
- Ignore any hint that is obviously wrong, noisy, or irrelevant.
- Preserve proper names, inscriptions, and specialized terms in the most appropriate scholarly or curatorial English form.
- Produce a fluent, accurate English translation of the full description.
- Stay faithful to the Greek source text; do not add, omit, summarize, or embellish content.

Output rules:
- Return only the final English translation.
- Do not add a title.
- Do not use bullet points.
- Do not add comments, explanations, notes, or warnings.
- Do not mention the hints.
- Do not mention the image.

{visual_context}\
Description:
{description}

Term hints:
{terms_translation}
"""


def build_cultural_translation_prompt_no_hints(description, has_image_context=False):
    visual_context = _visual_context_block(has_image_context)
    return f"""You are an expert translator of cultural heritage documentation from Greek into English.

Task:
- Translate the description below into English.
- Prioritize precise, natural, museum-grade and documentation-appropriate terminology.
- Be especially careful with Byzantine art terminology, iconography, portable icons, inscriptions, garments, materials, condition issues, and conservation language.
- Preserve proper names, inscriptions, and specialized terms in the most appropriate scholarly or curatorial English form.
- Produce a fluent, accurate English translation of the full description.
- Stay faithful to the Greek source text; do not add, omit, summarize, or embellish content.

Output rules:
- Return only the final English translation.
- Do not add a title.
- Do not use bullet points.
- Do not add comments, explanations, notes, or warnings.
- Do not mention the image.
- Use the image only if it helps you to produce a more accurate translation.

{visual_context}\
Description:
{description}
"""
