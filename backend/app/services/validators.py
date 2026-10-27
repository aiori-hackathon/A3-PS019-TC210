
import re
from datetime import date, datetime
from typing import Callable, Dict

# Verhoeff tables (dihedral group D5): multiplication, permutation.
_D = [
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
    [1, 2, 3, 4, 0, 6, 7, 8, 9, 5],
    [2, 3, 4, 0, 1, 7, 8, 9, 5, 6],
    [3, 4, 0, 1, 2, 8, 9, 5, 6, 7],
    [4, 0, 1, 2, 3, 9, 5, 6, 7, 8],
    [5, 9, 8, 7, 6, 0, 4, 3, 2, 1],
    [6, 5, 9, 8, 7, 1, 0, 4, 3, 2],
    [7, 6, 5, 9, 8, 2, 1, 0, 4, 3],
    [8, 7, 6, 5, 9, 3, 2, 1, 0, 4],
    [9, 8, 7, 6, 5, 4, 3, 2, 1, 0],
]
_P = [
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
    [1, 5, 7, 6, 2, 8, 3, 0, 9, 4],
    [5, 8, 0, 3, 7, 9, 6, 1, 4, 2],
    [8, 9, 1, 6, 0, 4, 3, 5, 2, 7],
    [9, 4, 5, 3, 1, 2, 6, 8, 7, 0],
    [4, 2, 8, 6, 5, 7, 3, 9, 0, 1],
    [2, 7, 9, 3, 8, 0, 6, 4, 1, 5],
    [7, 0, 4, 6, 9, 1, 3, 2, 5, 8],
]
_INV = [0, 4, 3, 2, 1, 5, 6, 7, 8, 9]


def _digits(text: str) -> str:
    return "".join(c for c in str(text) if c.isdigit())


def verhoeff_valid(text: str) -> bool:
    """True if the digits in `text` (check digit last) pass the Verhoeff checksum."""
    digits = _digits(text)
    if not digits:
        return False
    c = 0
    for i, ch in enumerate(reversed(digits)):
        c = _D[c][_P[i % 8][int(ch)]]
    return c == 0


def verhoeff_check_digit(text: str) -> int:
    """Check digit to append to the digits in `text` (used by test-data generators)."""
    c = 0
    for i, ch in enumerate(reversed(_digits(text))):
        c = _D[c][_P[(i + 1) % 8][int(ch)]]
    return _INV[c]


def aadhaar_valid(text: str) -> bool:
    """Aadhaar: 12 digits, first digit 2-9, Verhoeff check digit."""
    digits = _digits(text)
    return len(digits) == 12 and digits[0] not in "01" and verhoeff_valid(digits)


def luhn_valid(text: str) -> bool:
    """True if the digits in `text` pass the Luhn (mod 10) checksum used by payment cards."""
    digits = _digits(text)
    if len(digits) < 12:
        return False
    total = 0
    for i, ch in enumerate(reversed(digits)):
        d = int(ch)
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


def person_name_plausible(text: str) -> bool:
    """Reject NER 'names' that cannot be names: digits, or masks such as XXXX-XXXX."""
    t = str(text).strip()
    if not t or any(c.isdigit() for c in t):
        return False
    letters = [c for c in t if c.isalpha()]
    if not letters or all(c in "Xx" for c in letters):
        return False
    return True


# ─── Government identifiers ───────────────────────────────────────────────────

# 4th character of a PAN = holder type (P person, C company, H HUF, F firm, A AOP,
# T trust, B BOI, L local authority, J artificial juridical person, G government).
PAN_HOLDER_TYPES = set("PCHFATBLJG")


def pan_valid(text: str) -> bool:
    """PAN: AAAAA9999A with a valid holder-type letter in position 4."""
    t = re.sub(r"\s", "", str(text)).upper()
    return bool(re.fullmatch(r"[A-Z]{5}[0-9]{4}[A-Z]", t)) and t[3] in PAN_HOLDER_TYPES


# State / UT codes used as the prefix of Indian driving licences and vehicle registrations.
INDIAN_STATE_CODES = {
    "AN", "AP", "AR", "AS", "BR", "CH", "CG", "CT", "DD", "DL", "DN", "GA", "GJ", "HR", "HP",
    "JK", "JH", "KA", "KL", "LA", "LD", "MP", "MH", "MN", "ML", "MZ", "NL", "OD", "OR", "PB",
    "PY", "RJ", "SK", "TN", "TS", "TG", "TR", "UP", "UK", "UA", "WB",
}


def driving_licence_valid(text: str) -> bool:
    """Driving licence: SS RR YYYY NNNNNNN with a real state code and a plausible issue year."""
    t = re.sub(r"[\s-]", "", str(text)).upper()
    m = re.fullmatch(r"([A-Z]{2})([0-9]{2})((?:19|20)[0-9]{2})([0-9]{7})", t)
    if not m:
        return False
    return m.group(1) in INDIAN_STATE_CODES and 1950 <= int(m.group(3)) <= date.today().year


# ─── Personal identity ────────────────────────────────────────────────────────

_DATE_FORMATS = ("%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%Y-%m-%d", "%Y/%m/%d",
                 "%d %b %Y", "%d %B %Y", "%d-%b-%Y", "%d %b, %Y", "%d %B, %Y")


def date_of_birth_valid(text: str) -> bool:
    """A real calendar date between 1900-01-01 and today (no future birth dates)."""
    t = re.sub(r"\s+", " ", str(text).strip())
    for fmt in _DATE_FORMATS:
        try:
            d = datetime.strptime(t, fmt).date()
        except ValueError:
            continue
        return date(1900, 1, 1) <= d <= date.today()
    return False


def age_valid(text: str) -> bool:
    """Age in whole years, 0-120."""
    t = str(text).strip()
    return t.isdigit() and 0 <= int(t) <= 120


# ─── Location / address ───────────────────────────────────────────────────────

def coordinates_valid(text: str) -> bool:
    """'lat, lon' pair within range, or a single coordinate within -180..180."""
    parts = [p.strip() for p in str(text).split(",")]
    try:
        nums = [float(p) for p in parts]
    except ValueError:
        return False
    if len(nums) == 2:
        return -90 <= nums[0] <= 90 and -180 <= nums[1] <= 180
    return len(nums) == 1 and -180 <= nums[0] <= 180


def address_plausible(text: str) -> bool:
    """Postal address: at least 3 words, a house/plot number or PIN, and an address word."""
    t = str(text).strip()
    words = re.findall(r"[A-Za-z0-9]+", t)
    return len(words) >= 3 and any(c.isdigit() for c in t) and any(c.isalpha() for c in t)


VALIDATORS: Dict[str, Callable[[str], bool]] = {
    "verhoeff": verhoeff_valid,
    "aadhaar": aadhaar_valid,
    "luhn": luhn_valid,
    "person_name": person_name_plausible,
    "pan": pan_valid,
    "driving_licence": driving_licence_valid,
    "date_of_birth": date_of_birth_valid,
    "age": age_valid,
    "coordinates": coordinates_valid,
    "address": address_plausible,
}
