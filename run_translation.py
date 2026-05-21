import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

from src import (
    DEFAULT_DICTIONARIES_DIR,
    DictionaryMatcher,
    build_terms_translation_from_description,
    configure_logging,
    google_translate_text,
    save_translation_result,
    split_description_and_terms,
    translate_cultural_description_with_gemini,
    translate_cultural_description_with_gpt,
)


DEFAULT_MODELS = {
    "gemini": "gemini-3.5-flash",
    "openai": "gpt-5-mini",
}


def build_parser():
    parser = argparse.ArgumentParser(
        description="Translate Greek cultural heritage descriptions and save outputs/logs."
    )
    parser.add_argument(
        "input",
        nargs="?",
        help="JSONL input file. Each line should contain a JSON object with id/text fields.",
    )
    parser.add_argument("--provider", choices=["gemini", "openai"], default="gemini")
    parser.add_argument("--model", help="Model name. Defaults depend on provider.")
    parser.add_argument("--api-key", help="API key. Prefer GEMINI_API_KEY or OPENAI_API_KEY in the environment.")
    parser.add_argument("--no-hints", action="store_true", help="Ignore term hints while translating.")
    parser.add_argument(
        "--dictionaries-dir",
        default=DEFAULT_DICTIONARIES_DIR,
        help="Folder with .rdf dictionaries used to build term hints.",
    )
    parser.add_argument(
        "--hint-threshold",
        type=float,
        default=0.84,
        help="Minimum RDF term matching score.",
    )
    parser.add_argument(
        "--max-hints",
        type=int,
        default=20,
        help="Maximum number of RDF term hints to include.",
    )
    parser.add_argument(
        "--print-hints-only",
        action="store_true",
        help="Build/print RDF term hints and exit without calling a model.",
    )
    parser.add_argument(
        "--baselines-only",
        action="store_true",
        help="Save description, RDF hints, prompt, and Google Translate without calling a model.",
    )
    parser.add_argument(
        "--single-translation",
        action="store_true",
        help="Call the provider once instead of producing both with-hints and no-hints translations.",
    )
    parser.add_argument(
        "--no-google-translate",
        action="store_true",
        help="Skip the Google Translate baseline.",
    )
    parser.add_argument("--google-source", default="el", help="Source language for Google Translate.")
    parser.add_argument("--google-target", default="en", help="Target language for Google Translate.")
    parser.add_argument(
        "--thinking-level",
        default="low",
        help="Gemini thinking level. Use 'none' to omit thinking config.",
    )
    parser.add_argument("--outputs-dir", default=Path(__file__).resolve().parent / "outputs")
    parser.add_argument("--logs-dir", default=Path(__file__).resolve().parent / "logs")
    parser.add_argument("--id-field", default="id", help="JSONL field containing the record id.")
    parser.add_argument("--text-field", default="text", help="JSONL field containing the source text.")
    parser.add_argument("--limit", type=int, help="Translate at most this many JSONL records.")
    parser.add_argument("--start", type=int, default=0, help="Skip this many JSONL records before processing.")
    parser.add_argument(
        "--greek-only",
        action="store_true",
        help="Process only records whose extracted description has Greek characters and no English letters.",
    )
    parser.add_argument(
        "--min-greek-chars",
        type=int,
        default=1,
        help="Minimum Greek character count required when --greek-only is enabled.",
    )
    parser.add_argument(
        "--stop-on-error",
        action="store_true",
        help="Stop batch processing when one JSONL record fails.",
    )
    return parser


def read_input(input_path):
    if input_path:
        path = Path(input_path)
        return path.read_text(encoding="utf-8"), path

    if not sys.stdin.isatty():
        return sys.stdin.read(), None

    raise ValueError("Give an input file, or pipe text through stdin.")


def parse_input(raw_text):
    try:
        description, terms_translation = split_description_and_terms(raw_text)
        return (description, terms_translation), not bool(terms_translation.strip())
    except ValueError:
        text = (raw_text or "").strip()
        description_marker = "Description:"
        if text.lower().startswith(description_marker.lower()):
            text = text[len(description_marker) :].strip()
        if not text:
            raise
        return (text, ""), True


def extract_description_from_text(text):
    text = (text or "").strip()
    markdown_match = re.search(
        r"\*\*Description:\*\*\s*(.*?)(?:\n\s*\*\*[^*\n]+:\*\*|\Z)",
        text,
        flags=re.DOTALL | re.IGNORECASE,
    )
    if markdown_match:
        return markdown_match.group(1).strip()

    plain_match = re.search(
        r"Description:\s*(.*?)(?:\n\s*[A-Za-z &]+:\s*|\Z)",
        text,
        flags=re.DOTALL | re.IGNORECASE,
    )
    if plain_match:
        return plain_match.group(1).strip()

    return text


def parse_jsonl_record(record, args):
    text = record.get(args.text_field)
    if not isinstance(text, str) or not text.strip():
        raise ValueError(f"Missing non-empty text field: {args.text_field}")

    description = extract_description_from_text(text)
    if not description:
        raise ValueError("Could not extract a non-empty description.")

    terms_translation = record.get("terms_translation") or record.get("terms") or ""
    return description, terms_translation


def count_greek_chars(text):
    return len(re.findall(r"[Α-ΩΆ-Ώα-ωά-ώϊϋΐΰς]", text or ""))


def contains_english(text):
    return bool(re.search(r"[A-Za-z]", text or ""))


def passes_greek_filter(description, args):
    greek_char_count = count_greek_chars(description)
    has_english = contains_english(description)
    if not args.greek_only:
        return True, greek_char_count, has_english
    return greek_char_count >= args.min_greek_chars and not has_english, greek_char_count, has_english


def translate(description, terms_translation, args):
    model = args.model or DEFAULT_MODELS[args.provider]
    use_hints = not args.no_hints

    if args.provider == "gemini":
        thinking_level = None if args.thinking_level.lower() == "none" else args.thinking_level
        return (
            translate_cultural_description_with_gemini(
                description=description,
                terms_translation=terms_translation,
                api_key=args.api_key,
                model=model,
                use_hints=use_hints,
                thinking_level=thinking_level,
            ),
            model,
        )

    return (
        translate_cultural_description_with_gpt(
            description=description,
            terms_translation=terms_translation,
            api_key=args.api_key,
            model=model,
            use_hints=use_hints,
        ),
        model,
    )


def build_prompt_block(description, terms_translation):
    return f"Description:\n{description}\n\nTerms Translation\n{terms_translation}"


def maybe_google_translate(description, args, logger, line_number=None, record_id=None):
    if args.no_google_translate:
        return "", None

    try:
        return google_translate_text(
            description,
            source=args.google_source,
            target=args.google_target,
        ), None
    except Exception as exc:
        logger.exception("Google Translate failed line=%s id=%s", line_number, record_id)
        if args.stop_on_error:
            raise
        return "", str(exc)


def build_batch_output_path(outputs_dir, source_path, provider):
    output_dir = Path(outputs_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    suffix = "baselines" if provider == "baselines" else f"{provider}_translations"
    return output_dir / f"{source_path.stem}_{suffix}_{timestamp}.jsonl"


def iter_jsonl_records(path, start=0, limit=None):
    processed = 0
    seen = 0
    with Path(path).open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue

            if seen < start:
                seen += 1
                continue

            if limit is not None and processed >= limit:
                break

            seen += 1
            processed += 1
            yield line_number, json.loads(line)


def run_jsonl_batch(args, source_path, logger, log_file):
    model = args.model or DEFAULT_MODELS[args.provider]
    output_provider = "baselines" if args.baselines_only else args.provider
    output_path = None if args.print_hints_only else build_batch_output_path(
        args.outputs_dir,
        source_path,
        output_provider,
    )
    matcher = None

    if not args.no_hints:
        logger.info("Loading RDF dictionaries once from dir=%s", args.dictionaries_dir)
        matcher = DictionaryMatcher(dictionaries_dir=args.dictionaries_dir)
        logger.info("Loaded %s RDF terms", len(matcher.terms))

    counts = {"processed": 0, "eligible": 0, "skipped_greek_filter": 0, "translated": 0, "failed": 0}
    output_handle = output_path.open("w", encoding="utf-8") if output_path else None

    try:
        for line_number, record in iter_jsonl_records(source_path, start=args.start, limit=args.limit):
            counts["processed"] += 1
            record_id = record.get(args.id_field)

            try:
                description, terms_translation = parse_jsonl_record(record, args)
                should_process, greek_char_count, has_english = passes_greek_filter(description, args)
                if not should_process:
                    counts["skipped_greek_filter"] += 1
                    logger.info(
                        "Skipping line=%s id=%s greek_chars=%s has_english=%s",
                        line_number,
                        record_id,
                        greek_char_count,
                        has_english,
                    )
                    continue

                counts["eligible"] += 1
                hint_matches = []

                if not args.no_hints and not terms_translation.strip():
                    terms_translation, hint_matches = matcher.build_terms_translation(
                        description=description,
                        threshold=args.hint_threshold,
                        max_results=args.max_hints,
                    )

                prompt = build_prompt_block(description, terms_translation)
                google_translation, google_translation_error = "", None

                if args.print_hints_only:
                    print(
                        json.dumps(
                            {
                                "id": record_id,
                                "line_number": line_number,
                                "description": description,
                                "prompt": prompt,
                                "terms_translation": terms_translation,
                                "hint_matches": hint_matches,
                            },
                            ensure_ascii=False,
                        )
                    )
                    continue

                google_translation, google_translation_error = maybe_google_translate(
                    description=description,
                    args=args,
                    logger=logger,
                    line_number=line_number,
                    record_id=record_id,
                )

                output_record = dict(record)
                output_record.update(
                    {
                        "description": description,
                        "description_for_translation": description,
                        "prompt": prompt,
                        "terms_translation": terms_translation,
                        "hint_matches": hint_matches,
                        "google_translation": google_translation,
                        "google_translation_error": google_translation_error,
                        "source_line_number": line_number,
                    }
                )

                if args.baselines_only:
                    output_handle.write(json.dumps(output_record, ensure_ascii=False) + "\n")
                    output_handle.flush()
                    continue

                if args.single_translation:
                    logger.info("Translating line=%s id=%s provider=%s", line_number, record_id, args.provider)
                    translation, model = translate(description, terms_translation, args)
                    counts["translated"] += 1

                    output_record.update(
                        {
                            "translation": translation,
                            "provider": args.provider,
                            "model": model,
                        }
                    )
                    output_handle.write(json.dumps(output_record, ensure_ascii=False) + "\n")
                    output_handle.flush()
                    continue

                logger.info(
                    "Translating line=%s id=%s provider=%s hints=yes",
                    line_number,
                    record_id,
                    args.provider,
                )
                translation_with_hints, model = translate(description, terms_translation, args)

                # no_hints_args = argparse.Namespace(**vars(args))
                # no_hints_args.no_hints = True
                # logger.info(
                #     "Translating line=%s id=%s provider=%s hints=no",
                #     line_number,
                #     record_id,
                #     args.provider,
                # )
                # translation_no_hints, model = translate(description, terms_translation, no_hints_args)
                counts["translated"] += 1

                output_record.update(
                    {
                        "translation_with_hints": translation_with_hints,
                        # "translation_no_hints": translation_no_hints,
                        "provider": args.provider,
                        "model": model,
                    }
                )
                output_handle.write(json.dumps(output_record, ensure_ascii=False) + "\n")
                output_handle.flush()
            except Exception as exc:
                counts["failed"] += 1
                logger.exception("Failed line=%s id=%s", line_number, record_id)
                error_record = {
                    "id": record_id,
                    "source_line_number": line_number,
                    "error": str(exc),
                    "provider": args.provider,
                    "model": model,
                }
                if output_handle:
                    output_handle.write(json.dumps(error_record, ensure_ascii=False) + "\n")
                    output_handle.flush()
                if args.stop_on_error:
                    raise
    finally:
        if output_handle:
            output_handle.close()

    logger.info(
        "Batch done processed=%s eligible=%s skipped_greek_filter=%s translated=%s failed=%s",
        counts["processed"],
        counts["eligible"],
        counts["skipped_greek_filter"],
        counts["translated"],
        counts["failed"],
    )
    if args.greek_only:
        print(
            "Greek filter: "
            f"processed={counts['processed']} "
            f"eligible={counts['eligible']} "
            f"skipped={counts['skipped_greek_filter']} "
            f"min_greek_chars={args.min_greek_chars} "
            "rule=has_greek_and_no_english"
        )
    if output_path:
        print(f"Saved jsonl: {output_path}")
    print(f"Log file: {log_file}")


def main():
    parser = build_parser()
    args = parser.parse_args()
    logger, log_file = configure_logging(log_dir=args.logs_dir)

    try:
        source_path = Path(args.input) if args.input else None
        if source_path and source_path.suffix.lower() == ".jsonl":
            run_jsonl_batch(args, source_path, logger, log_file)
            return

        raw_text, source_path = read_input(args.input)
        (description, terms_translation), generated_hints = parse_input(raw_text)
        hint_matches = []

        if not args.no_hints and generated_hints:
            logger.info("Building term hints from RDF dictionaries dir=%s", args.dictionaries_dir)
            terms_translation, hint_matches = build_terms_translation_from_description(
                description=description,
                dictionaries_dir=args.dictionaries_dir,
                threshold=args.hint_threshold,
                max_results=args.max_hints,
            )
            logger.info("Built %s term hints from RDF dictionaries", len(hint_matches))

        if args.print_hints_only:
            logger.info("Printing hints only; skipping model call")
            print(terms_translation)
            print(f"\nLog file: {log_file}")
            return

        logger.info("Starting translation provider=%s source=%s", args.provider, source_path or "stdin")
        translation, model = translate(description, terms_translation, args)

        paths = save_translation_result(
            translation=translation,
            description=description,
            terms_translation=terms_translation,
            provider=args.provider,
            model=model,
            output_dir=args.outputs_dir,
            source_path=source_path,
            metadata={
                "use_hints": not args.no_hints,
                "generated_hints_from_rdf": generated_hints and not args.no_hints,
                "dictionaries_dir": str(args.dictionaries_dir),
                "hint_threshold": args.hint_threshold,
                "max_hints": args.max_hints,
                "hint_matches": hint_matches,
            },
        )

        logger.info("Translation saved text=%s json=%s", paths["text"], paths["json"])
        print(translation)
        print(f"\nSaved text: {paths['text']}")
        print(f"Saved json: {paths['json']}")
        print(f"Log file: {log_file}")
    except Exception:
        logger.exception("Translation failed")
        raise


if __name__ == "__main__":
    main()
