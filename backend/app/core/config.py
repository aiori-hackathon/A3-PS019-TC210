import yaml
from pathlib import Path
from typing import Dict, Any, List

# All paths are absolute so the app works regardless of the current working directory.
BASE_DIR = Path(__file__).resolve().parent.parent.parent
CONFIG_DIR = BASE_DIR / "config"
DATA_DIR = BASE_DIR / "data"
UPLOAD_DIR = DATA_DIR / "uploads"

DATA_CLASSES_FILE = CONFIG_DIR / "data_classes.yaml"
RULES_FILE = CONFIG_DIR / "rules.yaml"
CHECKLIST_FILE = CONFIG_DIR / "evidence_checklist.yaml"
REGISTRY_FILE = CONFIG_DIR / "metadata_registry.yaml"

# Evaluation answer key: dataset,column,true_class. Every dataset it names is a CSV in DATA_DIR
# (currently large_test_set.csv and the two synthetic_kyc_payment_test_data files).
COLUMN_GROUND_TRUTH = DATA_DIR / "ground_truth.csv"
SAMPLE_DB = DATA_DIR / "sample.db"

STORE_STATE_FILE = DATA_DIR / "store_state.json"
RULES_STATE_FILE = DATA_DIR / "rules_state.json"
DECLARED_METADATA_FILE = DATA_DIR / "declared_metadata.json"

MAX_UPLOAD_BYTES = 50 * 1024 * 1024  # 50 MB

NON_PII = "Non-PII"


def load_yaml(filepath: Path) -> Dict[str, Any]:
    if not filepath.exists():
        raise FileNotFoundError(f"Missing config file at {filepath}")
    with open(filepath, "r", encoding="utf-8") as file:
        return yaml.safe_load(file) or {}


DATA_CLASSES_CONFIG = load_yaml(DATA_CLASSES_FILE)
RULES_CONFIG = load_yaml(RULES_FILE)
EVIDENCE_CHECKLIST_CONFIG = load_yaml(CHECKLIST_FILE)
REGISTRY_CONFIG = load_yaml(REGISTRY_FILE)

# The 5 predefined data classes, in display order.
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
