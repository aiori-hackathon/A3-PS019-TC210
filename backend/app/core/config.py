import os
import tempfile
import yaml
from pathlib import Path
from typing import Dict, Any, List


BASE_DIR = Path(__file__).resolve().parent.parent.parent
CONFIG_DIR = BASE_DIR / "config"
DATA_DIR = BASE_DIR / "data"


def _writable_upload_dir() -> Path:

    candidates = [os.getenv("PRIVISTA_UPLOAD_DIR"), str(DATA_DIR / "uploads"),
                  os.path.join(tempfile.gettempdir(), "privista_uploads")]
    for c in filter(None, candidates):
        p = Path(c)
        try:
            p.mkdir(parents=True, exist_ok=True)
            probe = p / ".write_test"
            probe.write_bytes(b"")
            probe.unlink()
            return p
        except OSError:
            continue
    return Path(candidates[-1])


UPLOAD_DIR = _writable_upload_dir()

DATA_CLASSES_FILE = CONFIG_DIR / "data_classes.yaml"
RULES_FILE = CONFIG_DIR / "rules.yaml"
CHECKLIST_FILE = CONFIG_DIR / "evidence_checklist.yaml"
REGISTRY_FILE = CONFIG_DIR / "metadata_registry.yaml"


COLUMN_GROUND_TRUTH = DATA_DIR / "ground_truth.csv"
SAMPLE_DB = DATA_DIR / "sample.db"

STORE_STATE_FILE = DATA_DIR / "store_state.json"
RULES_STATE_FILE = DATA_DIR / "rules_state.json"
DECLARED_METADATA_FILE = DATA_DIR / "declared_metadata.json"

MAX_UPLOAD_BYTES = 50 * 1024 * 1024  # 50 MB


NON_PII = "Not personal data"


def load_yaml(filepath: Path) -> Dict[str, Any]:
    if not filepath.exists():
        raise FileNotFoundError(f"Missing config file at {filepath}")
    with open(filepath, "r", encoding="utf-8") as file:
        return yaml.safe_load(file) or {}


DATA_CLASSES_CONFIG = load_yaml(DATA_CLASSES_FILE)
RULES_CONFIG = load_yaml(RULES_FILE)
EVIDENCE_CHECKLIST_CONFIG = load_yaml(CHECKLIST_FILE)
REGISTRY_CONFIG = load_yaml(REGISTRY_FILE)

DATA_CLASSES: List[str] = list(DATA_CLASSES_CONFIG["data_classes"].keys())

CHECKLIST_ATTRIBUTES: List[Dict[str, Any]] = EVIDENCE_CHECKLIST_CONFIG.get("attributes", [])
CHECKLIST_KEYS: List[str] = [a["key"] for a in CHECKLIST_ATTRIBUTES]
DEFAULT_REQUIRED_ATTRS: List[str] = [a["key"] for a in CHECKLIST_ATTRIBUTES if a.get("required")]

DETECTION_SETTINGS: Dict[str, Any] = {
    "sample_size": 30,
    "min_match_ratio": 0.3,
    "column_name_hints": True,
    **(RULES_CONFIG.get("settings") or {}),
}


def class_sensitivity(data_class: str) -> str:
    info = DATA_CLASSES_CONFIG["data_classes"].get(data_class) or {}
    return info.get("sensitivity", "Medium")
