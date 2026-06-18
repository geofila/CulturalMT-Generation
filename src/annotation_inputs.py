import json
from pathlib import Path


ANNOTATION_FILE_SUFFIXES = {".json", ".jsonl"}


def _iter_annotation_objects(path):
    path = Path(path)

    if path.suffix.lower() == ".jsonl":
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if line:
                    yield json.loads(line)
        return

    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        yield from data
    elif isinstance(data, dict):
        tasks = data.get("tasks") or data.get("items") or data.get("results")
        if isinstance(tasks, list):
            yield from tasks
        else:
            yield data


def _extract_record_id(annotation_object):
    if not isinstance(annotation_object, dict):
        return None

    data = annotation_object.get("data")
    if isinstance(data, dict):
        for field in ("url", "record_url", "source_url", "id"):
            value = data.get(field)
            if isinstance(value, str) and value.strip():
                return value.strip()

    for field in ("url", "record_url", "source_url"):
        value = annotation_object.get(field)
        if isinstance(value, str) and value.strip():
            return value.strip()

    return None


def load_annotation_record_ids(input_dir):
    input_path = Path(input_dir)
    if not input_path.exists():
        raise FileNotFoundError(f"Annotation input folder does not exist: {input_path}")
    if not input_path.is_dir():
        raise ValueError(f"Annotation input path is not a folder: {input_path}")

    files = sorted(
        path
        for path in input_path.iterdir()
        if path.is_file() and path.suffix.lower() in ANNOTATION_FILE_SUFFIXES
    )
    if not files:
        raise ValueError(f"No annotation .json/.jsonl files found in: {input_path}")

    record_ids = set()
    for path in files:
        for annotation_object in _iter_annotation_objects(path):
            record_id = _extract_record_id(annotation_object)
            if record_id:
                record_ids.add(record_id)

    if not record_ids:
        raise ValueError(f"No record IDs found in annotation files under: {input_path}")

    return record_ids
