import json
import logging
from datetime import datetime
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = PROJECT_DIR / "outputs"
DEFAULT_LOG_DIR = PROJECT_DIR / "logs"


def ensure_runtime_dirs(output_dir=None, log_dir=None):
    output_path = Path(output_dir) if output_dir else DEFAULT_OUTPUT_DIR
    log_path = Path(log_dir) if log_dir else DEFAULT_LOG_DIR
    output_path.mkdir(parents=True, exist_ok=True)
    log_path.mkdir(parents=True, exist_ok=True)
    return output_path, log_path


def configure_logging(log_dir=None, level=logging.INFO):
    _, log_path = ensure_runtime_dirs(log_dir=log_dir)
    log_file = log_path / f"generation_{datetime.now().strftime('%Y%m%d')}.log"

    logger = logging.getLogger("culturalmt_generation")
    logger.setLevel(level)
    logger.handlers.clear()

    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(formatter)
    file_handler.setLevel(level)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(level)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    return logger, log_file


def save_translation_result(
    translation,
    description,
    terms_translation,
    provider,
    model,
    output_dir=None,
    source_path=None,
    metadata=None,
):
    output_path, _ = ensure_runtime_dirs(output_dir=output_dir)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_name = f"translation_{timestamp}_{provider}"
    text_path = output_path / f"{base_name}.txt"
    json_path = output_path / f"{base_name}.json"

    text_path.write_text(translation.strip() + "\n", encoding="utf-8")

    payload = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "provider": provider,
        "model": model,
        "source_path": str(source_path) if source_path else None,
        "description": description,
        "terms_translation": terms_translation,
        "translation": translation,
        "metadata": metadata or {},
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    return {"text": text_path, "json": json_path}
