import re


SYSTEM_INSTRUCTION = (
    "Translate faithfully from Greek to English for cultural heritage documentation. "
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


def build_cultural_translation_prompt(description, terms_translation):
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

Output rules:
- Return only the final English translation.
- Do not add a title.
- Do not use bullet points.
- Do not add comments, explanations, notes, or warnings.
- Do not mention the hints.

Description:
{description}

Term hints:
{terms_translation}
"""


def build_cultural_translation_prompt_no_hints(description):
    return f"""You are an expert translator of cultural heritage documentation from Greek into English.

Task:
- Translate the description below into English.
- Prioritize precise, natural, museum-grade and documentation-appropriate terminology.
- Be especially careful with Byzantine art terminology, iconography, portable icons, inscriptions, garments, materials, condition issues, and conservation language.
- Preserve proper names, inscriptions, and specialized terms in the most appropriate scholarly or curatorial English form.
- Produce a fluent, accurate English translation of the full description.

Output rules:
- Return only the final English translation.
- Do not add a title.
- Do not use bullet points.
- Do not add comments, explanations, notes, or warnings.

Description:
{description}
"""
