# CulturalMT Generation

Small translation runner for Greek cultural heritage descriptions.

This folder intentionally does not include any Label Studio code.

## Setup

```bash
pip install -r requirements.txt
```

## How to run the script

### Step 1: Define the API Key
For Gemini:

```bash
export GEMINI_API_KEY="your-gemini-api-key"
```

For OpenAI:

```bash
export OPENAI_API_KEY="your-openai-api-key"
```

### Step 2: Run the Generation Script

```bash
python run_translation.py puretext_chunks.jsonl \
  --provider gemini \
  --model gemini-3.5-flash \
  --greek-only \
  --start 1000 \
  --limit 10 \
  --hint-threshold 0.9 \
  --max-hints 1500 \
  --thinking-level low
```

## Input Format

The input is a JSONL file, one JSON object per line. The default fields are `id` and `text`, matching `puretext_chunks.jsonl`:

```json
{"id": "record-id", "text": "**Title:** ...\n\n**Description:**\nΤο ελληνικό κείμενο...\n\n**Subjects & Themes:** ..."}
```

## Run

```bash
python run_translation.py puretext_chunks.jsonl --provider gemini
```

This saves one JSONL output record per input record, including:

```text
description
prompt
terms_translation
hint_matches
google_translation
translation_with_hints
translation_no_hints
provider
model
```

The selected provider is called twice per record: once with RDF hints and once without hints. The `provider` field at the end says which provider was used, for example `gemini` or `openai`.

Test only the first 5 records:

```bash
python run_translation.py puretext_chunks.jsonl --provider gemini --limit 5
```

To process only records whose extracted description contains Greek and no English letters:

```bash
python run_translation.py puretext_chunks.jsonl --provider gemini --greek-only --limit 5
```

When `--greek-only` is enabled, the script prints how many records were processed, how many were eligible, and how many were skipped. The rule is: at least one Greek character by default and no English letters. Change the Greek minimum with `--min-greek-chars`.

For OpenAI, only change the provider. The output field names stay the same:

```bash
python run_translation.py puretext_chunks.jsonl --provider openai --model gpt-5-mini --limit 5
```

If you really want only one provider call per record, add:

```bash
python run_translation.py puretext_chunks.jsonl --provider openai --model gpt-5-mini --single-translation --limit 5
```

In `--single-translation` mode the output has one field named `translation` instead of the two comparison fields.

Skip records if you want to continue later:

```bash
python run_translation.py puretext_chunks.jsonl --provider gemini --start 100 --limit 50
```

Outputs are saved as JSONL in `outputs/`.
Logs are saved in `logs/`.

## Baselines Only

To save only the extracted description, RDF hints, prompt, and Google Translate output without calling Gemini/OpenAI:

```bash
python run_translation.py puretext_chunks.jsonl --baselines-only --limit 10
```

This is useful for creating a notebook-style comparison file before running model translations.

If you want hints and prompt only, without Google Translate:

```bash
python run_translation.py puretext_chunks.jsonl --baselines-only --no-google-translate --limit 10
```

## RDF Dictionaries

By default the runner reads RDF dictionaries from:

```text
dictionaries/
```

For each JSONL record, the runner extracts the text under `**Description:**` and automatically builds `Terms Translation` hints from the RDF files.

You can point to another RDF folder if needed:

```bash
python run_translation.py puretext_chunks.jsonl --dictionaries-dir dictionaries
```

To inspect RDF hints without calling Gemini/OpenAI:

```bash
python run_translation.py puretext_chunks.jsonl --print-hints-only --limit 5
```
