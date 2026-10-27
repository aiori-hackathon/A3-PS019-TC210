
import csv
import random
import sqlite3
import string
import sys
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Callable, Dict, List, Optional

import yaml
from faker import Faker

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))
from app.services.validators import INDIAN_STATE_CODES, verhoeff_check_digit  # noqa: E402

SEED = 42
ROWS = 60

DATA_DIR = BACKEND / "data"
CSV_DIR = DATA_DIR / "synthetic"
DB_FILE = DATA_DIR / "sample.db"
DUMP_FILE = DATA_DIR / "sample_dump.sql"
GROUND_TRUTH = DATA_DIR / "ground_truth.csv"
REGISTRY = BACKEND / "config" / "metadata_registry.yaml"

PI, CI, GOV, FIN, LOC = (
    "Personal identity", "Contact information", "Government identifiers",
    "Financial information", "Location / address",
)
NEG = "Not personal data"
CLASSES = [PI, CI, GOV, FIN, LOC]

rng = random.Random(SEED)
fake = Faker("en_IN")
fake.seed_instance(SEED)

Gen = Callable[[int], object]   # row index -> value


# ─── Value generators: personal data ──────────────────────────────────────────

def digits(n: int) -> str:
    return "".join(rng.choices(string.digits, k=n))


def letters(n: int) -> str:
    return "".join(rng.choices(string.ascii_uppercase, k=n))


def name(i: int) -> str:
    return fake.name()


def dob(fmt: str) -> Gen:
    start, end = date(1950, 1, 1), date(2006, 12, 31)

    def g(i: int) -> str:
        d = start + timedelta(days=rng.randint(0, (end - start).days))
        return d.strftime(fmt)
    return g


def gender_word(i: int) -> str:
    return rng.choice(["Male", "Female", "Male", "Female", "Male", "Female", "Transgender", "Other"])


def gender_short(i: int) -> str:
    return rng.choice(["M", "F", "M", "F", "M", "F", "O"])


def age(i: int) -> str:
    return str(rng.randint(18, 85))


def email(i: int) -> str:
    return fake.safe_email()  

def _mobile() -> str:
    return rng.choice("6789") + digits(9)


def phone(style: str = "mixed") -> Gen:
    formats = {
        "plain": lambda d: d,
        "plus91": lambda d: f"+91{d}",
        "plus91_space": lambda d: f"+91 {d[:5]} {d[5:]}",
        "plus91_dash": lambda d: f"+91-{d[:5]}-{d[5:]}",
        "zero": lambda d: f"0{d}",
        "3_3_4": lambda d: f"{d[:3]}-{d[3:6]}-{d[6:]}",
    }

    def g(i: int) -> str:
        key = rng.choice(list(formats)) if style == "mixed" else style
        return formats[key](_mobile())
    return g


def aadhaar(grouped: bool = True) -> Gen:
    def g(i: int) -> str:
        body = rng.choice("23456789") + digits(10)
        full = body + str(verhoeff_check_digit(body))
        return f"{full[:4]} {full[4:8]} {full[8:]}" if grouped else full
    return g


def pan(i: int) -> str:
    # 4th letter = holder type; P (individual) for personal records.
    return letters(3) + "P" + letters(1) + digits(4) + letters(1)


def passport(i: int) -> str:
    return rng.choice("ABCDEFGHJKLMNPRSTUVWY") + str(rng.randint(1, 9)) + digits(5) + str(rng.randint(1, 9))


def voter_id(i: int) -> str:
    return letters(3) + digits(7)


_STATES = sorted(INDIAN_STATE_CODES - {"OR", "UA", "CT", "TS"})


def driving_licence(i: int) -> str:
    sc, rto, yr, num = rng.choice(_STATES), f"{rng.randint(1, 50):02d}", rng.randint(1990, 2024), digits(7)
    return rng.choice([f"{sc}{rto} {yr}{num}", f"{sc}{rto}{yr}{num}", f"{sc}-{rto}{yr}{num}"])


def _luhn_complete(prefix: str, length: int = 16) -> str:
    body = prefix + digits(length - len(prefix) - 1)
    total = 0
    for idx, ch in enumerate(reversed(body)):
        d = int(ch)
        if idx % 2 == 0:  
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return body + str((10 - total % 10) % 10)


def _group4(n: str) -> str:
    return " ".join(n[k:k + 4] for k in range(0, len(n), 4))


def card(i: int) -> str:
    n = _luhn_complete(rng.choice(["4", "4", "51", "52", "53", "54", "55"]))
    return _group4(n) if rng.random() < 0.4 else n


def rupay_card(i: int) -> str:
    n = _luhn_complete(rng.choice(["6070", "6521", "6522", "5085", "6080"]))
    return _group4(n) if rng.random() < 0.5 else n


def masked_card(i: int) -> str:
    last4 = digits(4)
    return rng.choice([f"XXXX-XXXX-XXXX-{last4}", f"**** **** **** {last4}", f"xxxx xxxx xxxx {last4}"])


def bank_account(i: int) -> str:
    return rng.choice("123456789") + digits(rng.randint(8, 17))


_BANK_CODES = ["SBIN", "HDFC", "ICIC", "UTIB", "PUNB", "KKBK", "BARB", "CNRB", "IDIB", "YESB", "UBIN", "IOBA"]


def ifsc(i: int) -> str:
    return rng.choice(_BANK_CODES) + "0" + digits(6)


_UPI_KNOWN = ["okaxis", "okicici", "oksbi", "okhdfcbank", "ybl", "ibl", "axl", "paytm", "apl", "upi"]
_UPI_OTHER = ["payzapp", "mbk", "axisgo"]   # syntactically valid handles not in the rule's list


def upi(i: int) -> str:
    local = rng.choice([fake.user_name().lower().replace("_", "."), _mobile()])
    handle = rng.choice(_UPI_KNOWN) if rng.random() < 0.85 else rng.choice(_UPI_OTHER)
    return f"{local}@{handle}"


def pin_code(spaced: bool = False) -> Gen:
    def g(i: int) -> str:
        p = str(rng.randint(1, 8)) + digits(5)
        return f"{p[:3]} {p[3:]}" if spaced and rng.random() < 0.5 else p
    return g


def _pin() -> str:
    return str(rng.randint(1, 8)) + digits(5)


def address(with_pin: bool = True) -> Gen:
    def g(i: int) -> str:
        city, state = fake.city(), fake.state()
        pin = f" {_pin()}" if with_pin else ""
        templates = [
            f"Flat {rng.randint(101, 1204)}, {fake.last_name()} Apartments, {fake.street_name()}, {city}{pin}",
            f"H.No. {rng.randint(1, 999)}, Sector {rng.randint(1, 80)}, {city}, {state}{pin}",
            f"Plot {rng.randint(1, 400)}, {fake.last_name()} Nagar, {city}{pin}",
            f"{rng.randint(1, 300)}/{rng.randint(1, 99)}, {fake.street_name()}, {city}{pin}",
        ]
        if with_pin and rng.random() < 0.4:
            return fake.address().replace("\n", ", ")   
        return rng.choice(templates)
    return g


def _coord(lo: float, hi: float) -> float:
    s = f"{rng.uniform(lo, hi):.6f}"
    if s.endswith("0"):
        s = s[:-1] + str(rng.randint(1, 9))
    return float(s)


def lat_lon_pair(i: int) -> str:
    lat, lon = _coord(8.0, 35.0), _coord(68.0, 97.0)
    return f"{lat:.6f}, {lon:.6f}" if rng.random() < 0.7 else f"{lat:.6f},{lon:.6f}"


def latitude(i: int) -> float:
    return _coord(8.0, 35.0)


def longitude(i: int) -> float:
    return _coord(68.0, 97.0)




def seq(prefix: str = "", width: int = 0) -> Gen:
    return lambda i: f"{prefix}{i + 1:0{width}d}" if (prefix or width) else i + 1


def choice(options: List[str]) -> Gen:
    return lambda i: rng.choice(options)


def timestamp(i: int) -> str:
    start = datetime(2023, 1, 1)
    return (start + timedelta(seconds=rng.randint(0, 3 * 365 * 86400))).strftime("%Y-%m-%d %H:%M:%S")


def recent_date(fmt: str = "%Y-%m-%d") -> Gen:
    start = date(2023, 1, 1)
    return lambda i: (start + timedelta(days=rng.randint(0, 3 * 365))).strftime(fmt)


def amount(lo: float = 100, hi: float = 99999) -> Gen:
    return lambda i: round(rng.uniform(lo, hi), 2)


def integer(lo: int, hi: int) -> Gen:
    return lambda i: rng.randint(lo, hi)


def decimal4(lo: float, hi: float) -> Gen:
    return lambda i: f"{rng.uniform(lo, hi):.4f}"


def phone_like_number(i: int) -> str:      # 10 digits starting 6-9, like a mobile number
    return _mobile()


def aadhaar_like_number(i: int) -> str:    # 4-4-4 grouping like Aadhaar
    return f"{rng.choice('23456789')}{digits(3)} {digits(4)} {digits(4)}"


def card_like_number(i: int) -> str:       # Luhn-valid 16 digits, like a card
    return _luhn_complete(rng.choice(["4", "5", "6"]))


def ifsc_like_code(i: int) -> str:
    return letters(4) + "0" + "".join(rng.choices(string.ascii_uppercase + string.digits, k=6))


def build_tag(i: int) -> str:              # name@word without a dot, like a UPI ID
    return f"{rng.choice(['release', 'build', 'deploy', 'hotfix'])}@{rng.choice(['stable', 'canary', 'beta', 'nightly'])}"


def uuid4(i: int) -> str:
    h = "".join(rng.choices("0123456789abcdef", k=32))
    return f"{h[:8]}-{h[8:12]}-4{h[13:16]}-{h[16:20]}-{h[20:]}"


def version(i: int) -> str:
    return f"v{rng.randint(0, 9)}.{rng.randint(0, 20)}.{rng.randint(0, 50)}"


def hex_colour(i: int) -> str:
    return "#" + "".join(rng.choices("0123456789abcdef", k=6))


def gstin(i: int) -> str:                  # business tax ID; contains a PAN-shaped part
    return f"{rng.randint(1, 37):02d}{letters(3)}C{letters(1)}{digits(4)}{letters(1)}{rng.randint(1, 9)}Z{rng.choice(string.ascii_uppercase + string.digits)}"


def ip_address(i: int) -> str:
    return f"10.{rng.randint(0, 255)}.{rng.randint(0, 255)}.{rng.randint(1, 254)}"


def mac_address(i: int) -> str:
    return ":".join("".join(rng.choices("0123456789ABCDEF", k=2)) for _ in range(6))


def vehicle_reg(i: int) -> str:
    return f"{rng.choice(_STATES)}{rng.randint(1, 50):02d}{letters(2)}{digits(4)}"


def isbn(i: int) -> str:
    return f"978-81-{digits(4)}-{digits(3)}-{rng.randint(0, 9)}"


_WORDS = ["river", "window", "orbit", "maple", "copper", "lantern", "harbor", "pixel", "meadow", "quartz",
          "summit", "canvas", "ember", "velvet", "glacier", "tunnel", "saffron", "marble", "falcon", "cobalt"]
_CITIES = ["Mumbai", "Pune", "Kochi", "Indore", "Lucknow", "Jaipur", "Nagpur", "Mysuru", "Surat", "Patna"]
_STATE_NAMES = ["Kerala", "Gujarat", "Punjab", "Odisha", "Assam", "Bihar", "Goa", "Tripura", "Haryana"]
_PRODUCTS = ["Steel Water Bottle", "Cotton Kurta", "LED Desk Lamp", "Basmati Rice 5kg", "Wireless Mouse",
             "Masala Chai 250g", "Yoga Mat", "Ceramic Mug", "Notebook A5", "Phone Charger"]


# ─── Dataset specification ────────────────────────────────────────────────────

@dataclass
class Col:
    name: str
    gen: Gen
    true_class: str
    sub_type: str
    meta: str = "full"        # full | no_purpose | no_retention | undeclared  (personal-data columns only)
    sql_type: str = "TEXT"
    notes: str = ""


@dataclass
class Table:
    name: str                 # CSV file name or SQL table name
    kind: str                 # csv | sql
    purpose: str = ""
    retention: str = ""
    owner: Optional[str] = None
    rows: int = ROWS
    cols: List[Col] = field(default_factory=list)


def P(name_: str, gen: Gen, cls: str, sub: str, meta: str = "full", sql_type: str = "TEXT", notes: str = "") -> Col:
    return Col(name_, gen, cls, sub, meta, sql_type, notes)


def N(name_: str, gen: Gen, sub: str, sql_type: str = "TEXT", notes: str = "") -> Col:
    return Col(name_, gen, NEG, sub, "n/a", sql_type, notes)


HARD = "hard case: no column-name context, value alone is ambiguous"

TABLES: List[Table] = [
    # ── CSV files ─────────────────────────────────────────────────────────────
    Table("customers_kyc.csv", "csv", "Identity verification (KYC)", "8 years after account closure", "Compliance & Risk", cols=[
        N("customer_id", seq("CUST", 5), "Record ID"),
        P("full_name", name, PI, "Name"),
        P("date_of_birth", dob("%d/%m/%Y"), PI, "Date of birth"),
        P("gender", gender_word, PI, "Gender"),
        P("age", age, PI, "Age"),
        P("email", email, CI, "Email address"),
        P("alternate_email", email, CI, "Email address"),
        P("mobile", phone("plus91"), CI, "Phone number"),
        P("aadhaar_number", aadhaar(), GOV, "Aadhaar"),
        P("pan_number", pan, GOV, "PAN"),
        P("passport_no", passport, GOV, "Passport", meta="undeclared"),
        P("voter_id", voter_id, GOV, "Voter ID"),
        P("driving_licence", driving_licence, GOV, "Driving licence", meta="no_retention"),
        P("residential_address", address(), LOC, "Postal address"),
        P("permanent_address", address(), LOC, "Postal address", meta="no_purpose"),
        P("pincode", pin_code(), LOC, "PIN code"),
        N("kyc_status", choice(["Verified", "Pending", "Rejected", "Re-KYC due"]), "Status"),
        N("created_at", timestamp, "Timestamp", notes="look-alike: date (date of birth)"),
        N("branch_city", choice(_CITIES), "City", notes="city alone is not a postal address"),
        N("customer_segment", choice(["Retail", "Premium", "SME", "NRI"]), "Category"),
    ]),
    Table("payments.csv", "csv", "Payment processing and settlement", "10 years", "Finance", cols=[
        N("txn_id", seq("TXN", 7), "Record ID"),
        P("payer_name", name, PI, "Name"),
        P("payer_email", email, CI, "Email address"),
        P("payer_phone", phone("mixed"), CI, "Phone number"),
        P("payer_pan", pan, GOV, "PAN"),
        P("card_number", card, FIN, "Card number"),
        P("rupay_card", rupay_card, FIN, "Card number"),
        P("masked_card", masked_card, FIN, "Card number"),
        P("bank_account_no", bank_account, FIN, "Bank account number"),
        P("ifsc_code", ifsc, FIN, "IFSC"),
        P("beneficiary_account", bank_account, FIN, "Bank account number"),
        P("beneficiary_ifsc", ifsc, FIN, "IFSC"),
        P("upi_id", upi, FIN, "UPI ID", meta="no_retention"),
        P("refund_upi", upi, FIN, "UPI ID", meta="undeclared"),
        N("amount", amount(), "Amount"),
        N("order_id", phone_like_number, "Order ID", notes="look-alike: 10-digit mobile number"),
        N("invoice_no", aadhaar_like_number, "Invoice number", notes="look-alike: Aadhaar 4-4-4"),
        N("txn_date", recent_date("%d/%m/%Y"), "Date", notes="look-alike: date of birth"),
        N("payment_status", choice(["SUCCESS", "FAILED", "PENDING", "REFUNDED"]), "Status"),
        N("currency", choice(["INR"]), "Currency code"),
    ]),
    Table("delivery_orders.csv", "csv", "Order delivery", "2 years", "Logistics", cols=[
        N("order_ref", seq("ORD-2025-", 6), "Record ID"),
        P("recipient", name, PI, "Name"),
        P("recipient_email", email, CI, "Email address"),
        P("contact_no", phone("plain"), CI, "Phone number"),
        P("alt_contact", phone("plus91_dash"), CI, "Phone number", meta="no_purpose"),
        P("shipping_address", address(), LOC, "Postal address"),
        P("pickup_address", address(), LOC, "Postal address"),
        P("delivery_pincode", pin_code(spaced=True), LOC, "PIN code"),
        P("drop_location", lat_lon_pair, LOC, "Geo-coordinates", meta="undeclared"),
        P("pickup_lat_long", lat_lon_pair, LOC, "Geo-coordinates", meta="no_retention"),
        P("cod_upi", upi, FIN, "UPI ID"),
        N("warehouse_code", ifsc_like_code, "Warehouse code", notes="look-alike: IFSC"),
        N("sku", pan, "SKU", notes="look-alike: PAN"),
        N("package_weight", decimal4(0.1, 40), "Weight", notes="look-alike: single coordinate"),
        N("otp", lambda i: _pin(), "One-time password", notes="look-alike: 6-digit PIN code"),
        N("delivery_date", recent_date(), "Date", notes="look-alike: date of birth"),
        N("delivery_slot", choice(["Morning", "Afternoon", "Evening"]), "Category"),
    ]),
    Table("hr_employees.csv", "csv", "Employment and payroll", "7 years after exit", "Human Resources", cols=[
        N("emp_id", seq("EMP", 5), "Record ID"),
        P("employee_name", name, PI, "Name"),
        P("birth_date", dob("%Y-%m-%d"), PI, "Date of birth", meta="no_retention"),
        P("sex", gender_short, PI, "Gender"),
        P("age_years", age, PI, "Age"),
        P("work_email", email, CI, "Email address"),
        P("personal_phone", phone("zero"), CI, "Phone number"),
        P("emergency_contact_phone", phone("3_3_4"), CI, "Phone number"),
        P("pan", pan, GOV, "PAN"),
        P("aadhaar", aadhaar(grouped=False), GOV, "Aadhaar"),
        P("passport", passport, GOV, "Passport"),
        P("driving_licence_no", driving_licence, GOV, "Driving licence"),
        P("voter_card", voter_id, GOV, "Voter ID"),
        P("salary_account", bank_account, FIN, "Bank account number"),
        P("salary_ifsc", ifsc, FIN, "IFSC"),
        P("reimbursement_upi", upi, FIN, "UPI ID", meta="undeclared"),
        P("home_address", address(), LOC, "Postal address"),
        P("home_pin", pin_code(), LOC, "PIN code", meta="no_purpose"),
        N("joining_date", recent_date("%d-%m-%Y"), "Date", notes="look-alike: date of birth"),
        N("department", choice(["Finance", "Engineering", "Sales", "Operations", "Legal"]), "Category"),
        N("grade", choice(["L1", "L2", "L3", "L4", "L5"]), "Category"),
        N("rating", integer(1, 5), "Score", notes="look-alike: age"),
        N("shift", choice(["Day", "Night", "Rotational"]), "Category"),
    ]),
    Table("patients.csv", "csv", "Patient registration", "5 years after last visit", "Hospital Administration", cols=[
        N("patient_id", seq("PT", 6), "Record ID"),
        P("patient_name", name, PI, "Name"),
        P("patient_dob", dob("%d %b %Y"), PI, "Date of birth"),
        P("patient_gender", gender_word, PI, "Gender"),
        P("patient_age", age, PI, "Age"),
        P("guardian_name", name, PI, "Name", meta="undeclared"),
        P("contact_email", email, CI, "Email address"),
        P("contact_phone", phone("plus91_space"), CI, "Phone number"),
        P("guardian_phone", phone("mixed"), CI, "Phone number"),
        P("patient_aadhaar", aadhaar(), GOV, "Aadhaar"),
        P("address_line", address(), LOC, "Postal address"),
        P("pin_code", pin_code(), LOC, "PIN code"),
        P("gps_location", lat_lon_pair, LOC, "Geo-coordinates", meta="no_retention"),
        N("ward", lambda i: f"Ward {rng.randint(1, 20)}", "Ward"),
        N("bed_no", lambda i: f"B-{rng.randint(1, 60)}", "Bed number"),
        N("admission_date", recent_date(), "Date", notes="look-alike: date of birth"),
        N("discharge_date", recent_date(), "Date", notes="look-alike: date of birth"),
        N("blood_group", choice(["A+", "A-", "B+", "B-", "O+", "O-", "AB+", "AB-"]), "Health attribute",
          notes="sensitive but outside the five classes"),
        N("department", choice(["Cardiology", "Orthopaedics", "Paediatrics", "General Medicine"]), "Category"),
    ]),
    Table("vague_columns.csv", "csv", cols=[   # no declarations at all: an undocumented export
        P("col_a", name, PI, "Name", meta="undeclared"),
        P("col_b", email, CI, "Email address", meta="undeclared"),
        P("col_c", phone("plus91"), CI, "Phone number", meta="undeclared"),
        P("col_d", aadhaar(), GOV, "Aadhaar", meta="undeclared"),
        P("col_e", pan, GOV, "PAN", meta="undeclared"),
        P("col_f", voter_id, GOV, "Voter ID", meta="undeclared"),
        P("col_g", driving_licence, GOV, "Driving licence", meta="undeclared"),
        P("col_h", card, FIN, "Card number", meta="undeclared"),
        P("col_i", ifsc, FIN, "IFSC", meta="undeclared"),
        P("col_j", upi, FIN, "UPI ID", meta="undeclared"),
        P("col_k", address(), LOC, "Postal address", meta="undeclared"),
        P("col_l", lat_lon_pair, LOC, "Geo-coordinates", meta="undeclared"),
        P("col_m", gender_word, PI, "Gender", meta="undeclared"),
        P("col_u", phone("plus91_space"), CI, "Phone number", meta="undeclared"),
        P("col_w", address(with_pin=False), LOC, "Postal address", meta="undeclared"),
        P("col_s", dob("%d/%m/%Y"), PI, "Date of birth", meta="undeclared", notes=HARD),
        P("col_t", bank_account, FIN, "Bank account number", meta="undeclared", notes=HARD),
        N("col_n", choice(_WORDS), "Random words"),
        N("col_o", lambda i: f"{rng.choice('ABCDE')}{rng.randint(1, 9)}", "Code"),
        N("col_p", uuid4, "UUID"),
        N("col_q", version, "Version string"),
        N("col_r", hex_colour, "Colour code"),
    ]),
    Table("lookalikes.csv", "csv", cols=[      # only negatives: values shaped like personal data
        N("order_number", phone_like_number, "Order number", notes="look-alike: mobile number"),
        N("invoice_number", aadhaar_like_number, "Invoice number", notes="look-alike: Aadhaar"),
        N("product_sku", pan, "SKU", notes="look-alike: PAN"),
        N("tracking_id", card_like_number, "Tracking number", notes="look-alike: Luhn-valid card number"),
        N("coupon_code", voter_id, "Coupon code", notes="look-alike: voter ID"),
        N("batch_no", passport, "Batch number", notes="look-alike: passport"),
        N("ticket_ref", driving_licence, "Ticket reference", notes="look-alike: driving licence"),
        N("build_tag", build_tag, "Build tag", notes="look-alike: UPI ID"),
        N("product_code", lambda i: _pin(), "Product code", notes="look-alike: PIN code"),
        N("unit_price", decimal4(10, 95), "Price", notes="look-alike: single coordinate"),
        N("temperature_c", decimal4(20, 45), "Temperature", notes="look-alike: single coordinate"),
        N("test_score", integer(0, 100), "Score", notes="look-alike: age"),
        N("quantity", integer(1, 90), "Quantity", notes="look-alike: age"),
        N("event_date", recent_date("%d/%m/%Y"), "Date", notes="look-alike: date of birth"),
        N("size", choice(["S", "M", "L", "XL", "XXL"]), "Size", notes="look-alike: gender M/F"),
        N("city", choice(_CITIES), "City", notes="city alone is not a postal address"),
        N("state", choice(_STATE_NAMES), "State"),
        N("country", choice(["India"]), "Country"),
        N("plan_name", choice(["Gold", "Silver", "Basic", "Student", "Business"]), "Plan name"),
        N("colour", choice(["Blue", "Red", "Green", "Black", "White"]), "Colour"),
        N("gstin", gstin, "GSTIN (business tax ID)", notes="look-alike: contains a PAN-shaped part"),
        N("ip_address", ip_address, "IP address", notes="look-alike: 'address' column name"),
        N("mac_address", mac_address, "MAC address", notes="look-alike: 'address' column name"),
        N("vehicle_reg", vehicle_reg, "Vehicle registration", notes="look-alike: driving licence state code"),
        N("isbn", isbn, "ISBN", notes="look-alike: phone number"),
        N("pnr", lambda i: rng.choice("2345678") + digits(9), "PNR", notes="look-alike: 10-digit number"),
        N("hsn_code", lambda i: digits(8), "HSN code"),
        N("employee_count", integer(5, 110), "Count", notes="look-alike: age"),
    ]),

    # ── SQLite tables (data/sample.db) ────────────────────────────────────────
    Table("customers", "sql", "Identity verification (KYC)", "8 years after account closure", "Compliance & Risk", cols=[
        N("customer_id", seq(), "Record ID", sql_type="INTEGER PRIMARY KEY"),
        P("full_name", name, PI, "Name"),
        P("dob", dob("%Y-%m-%d"), PI, "Date of birth"),
        P("gender", gender_word, PI, "Gender"),
        P("email", email, CI, "Email address"),
        P("phone", phone("plus91"), CI, "Phone number"),
        P("aadhaar", aadhaar(), GOV, "Aadhaar"),
        P("pan", pan, GOV, "PAN", meta="no_retention"),
        P("passport_no", passport, GOV, "Passport", meta="undeclared"),
        P("address", address(), LOC, "Postal address", meta="undeclared"),
        P("pincode", pin_code(), LOC, "PIN code"),
        N("city", choice(_CITIES), "City", notes="city alone is not a postal address"),
        N("segment", choice(["Retail", "Premium", "SME"]), "Category"),
        N("created_at", timestamp, "Timestamp", notes="look-alike: date (date of birth)"),
    ]),
    Table("accounts", "sql", "Account servicing", "10 years after account closure", "Finance", cols=[
        N("account_id", seq(), "Record ID", sql_type="INTEGER PRIMARY KEY", notes="look-alike: 'account' column name"),
        N("customer_id", integer(1, ROWS), "Foreign key", sql_type="INTEGER"),
        P("account_number", bank_account, FIN, "Bank account number", meta="undeclared"),
        P("ifsc", ifsc, FIN, "IFSC"),
        P("upi_handle", upi, FIN, "UPI ID"),
        P("debit_card", rupay_card, FIN, "Card number"),
        P("credit_card", card, FIN, "Card number"),
        N("balance", amount(0, 500000), "Amount", sql_type="REAL"),
        N("opened_on", recent_date(), "Date", notes="look-alike: date of birth"),
        N("account_type", choice(["Savings", "Current", "Salary"]), "Category", notes="look-alike: 'account' column name"),
    ]),
    Table("kyc_documents", "sql", "Identity verification (KYC)", "8 years after account closure", "Compliance & Risk", cols=[
        N("doc_id", seq(), "Record ID", sql_type="INTEGER PRIMARY KEY"),
        N("customer_id", integer(1, ROWS), "Foreign key", sql_type="INTEGER"),
        P("passport_number", passport, GOV, "Passport"),
        P("voter_epic", voter_id, GOV, "Voter ID"),
        P("dl_no", driving_licence, GOV, "Driving licence", meta="no_retention"),
        N("verification_status", choice(["VERIFIED", "PENDING", "EXPIRED"]), "Status"),
        N("uploaded_at", timestamp, "Timestamp"),
    ]),
    Table("branch_visits", "sql", "Branch footfall analytics", "1 year", None, cols=[
        N("visit_id", seq(), "Record ID", sql_type="INTEGER PRIMARY KEY"),
        N("customer_id", integer(1, ROWS), "Foreign key", sql_type="INTEGER"),
        P("latitude", latitude, LOC, "Geo-coordinates", meta="undeclared", sql_type="REAL"),
        P("longitude", longitude, LOC, "Geo-coordinates", meta="undeclared", sql_type="REAL"),
        P("visit_pin", pin_code(), LOC, "PIN code"),
        N("device_id", lambda i: f"DEV-{digits(4)}", "Device ID"),
        N("visited_at", timestamp, "Timestamp"),
        N("duration_min", integer(5, 120), "Duration", sql_type="INTEGER", notes="look-alike: age"),
    ]),
    Table("support_tickets", "sql", "Customer support", "3 years", "Customer Success", cols=[
        N("ticket_id", seq(), "Record ID", sql_type="INTEGER PRIMARY KEY"),
        P("raised_by_email", email, CI, "Email address"),
        P("callback_number", phone("mixed"), CI, "Phone number", meta="no_purpose"),
        N("subject", choice(["Card not working", "Update KYC", "Statement request", "Net banking locked"]), "Free text"),
        N("priority", choice(["Low", "Medium", "High"]), "Category"),
        N("created_at", timestamp, "Timestamp"),
    ]),
    Table("products", "sql", rows=40, cols=[
        N("product_id", seq(), "Record ID", sql_type="INTEGER PRIMARY KEY"),
        N("product_name", choice(_PRODUCTS), "Product name", notes="look-alike: 'name' column name"),
        N("product_code", pan, "Product code", notes="look-alike: PAN"),
        N("price", amount(50, 5000), "Price", sql_type="REAL"),
        N("stock", integer(0, 99), "Quantity", sql_type="INTEGER", notes="look-alike: age"),
        N("category", choice(["Home", "Apparel", "Grocery", "Electronics"]), "Category"),
    ]),
    Table("system_logs", "sql", cols=[
        N("log_id", seq(), "Record ID", sql_type="INTEGER PRIMARY KEY"),
        N("event_type", choice(["LOGIN", "LOGOUT", "AUDIT", "SCAN", "REPORT"]), "Category"),
        N("message", choice(["User logged in", "User logged out", "Evidence audit completed",
                             "Schema discovery initiated", "Inventory report generated"]), "Free text"),
        N("created_at", timestamp, "Timestamp"),
    ]),
]


# ─── Writers ──────────────────────────────────────────────────────────────────

def build_rows(t: Table) -> List[List[object]]:
    return [[c.gen(i) for c in t.cols] for i in range(t.rows)]


def write_csv(t: Table, rows: List[List[object]]) -> None:
    CSV_DIR.mkdir(parents=True, exist_ok=True)
    with open(CSV_DIR / t.name, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow([c.name for c in t.cols])
        w.writerows(rows)


def write_sql(conn: sqlite3.Connection, t: Table, rows: List[List[object]]) -> None:
    cols_sql = ", ".join(f'"{c.name}" {c.sql_type}' for c in t.cols)
    conn.execute(f'CREATE TABLE "{t.name}" ({cols_sql})')
    placeholders = ", ".join("?" for _ in t.cols)
    conn.executemany(f'INSERT INTO "{t.name}" VALUES ({placeholders})', rows)


def dataset_name(t: Table) -> str:
    return f"synthetic/{t.name}" if t.kind == "csv" else f"{DB_FILE.name}:{t.name}"


def registry_source(t: Table) -> str:
    # Must match the scanner: CSV source = file name, SQL source = <db file stem>.<table>
    return t.name if t.kind == "csv" else f"{DB_FILE.stem}.{t.name}"


def write_ground_truth() -> None:
    with open(GROUND_TRUTH, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["dataset", "column", "true_class", "sub_type", "source_type", "notes"])
        for t in TABLES:
            for c in t.cols:
                w.writerow([dataset_name(t), c.name, c.true_class, c.sub_type, t.kind, c.notes])


REGISTRY_HEADER = """\
# Declared purpose / retention / owner metadata, matched to scanned fields by exact (source, field).
# GENERATED by scripts/generate_datasets.py - edit the TABLES spec there, then re-run the script.
#
# Format (YAML):
#   declarations:
#     - source:    CSV file name (e.g. customers_kyc.csv) or <sqlite file stem>.<table> (e.g. sample.customers)
#       field:     column name
#       purpose:   declared business purpose            (omitted = missing -> evidence gap)
#       retention: declared retention schedule          (omitted = missing -> evidence gap)
#       owner:     accountable team                     (optional checklist attribute)
#
# Some personal-data fields are deliberately left undeclared or incomplete so the evidence-gap
# report can be demonstrated; they are listed in deliberate_gaps below (informational only).
"""


def write_registry() -> List[Dict[str, str]]:
    declarations, gaps = [], []
    for t in TABLES:
        for c in t.cols:
            if c.true_class == NEG:
                continue
            src = registry_source(t)
            if c.meta == "undeclared" or not t.purpose:
                gaps.append({"source": src, "field": c.name, "missing": "purpose, retention (no declaration)"})
                continue
            d: Dict[str, str] = {"source": src, "field": c.name}
            if c.meta != "no_purpose":
                d["purpose"] = t.purpose
            if c.meta != "no_retention":
                d["retention"] = t.retention
            if t.owner:
                d["owner"] = t.owner
            declarations.append(d)
            if c.meta in ("no_purpose", "no_retention"):
                gaps.append({"source": src, "field": c.name, "missing": c.meta.replace("no_", "")})
    with open(REGISTRY, "w", encoding="utf-8") as f:
        f.write(REGISTRY_HEADER + "\n")
        yaml.safe_dump({"declarations": declarations, "deliberate_gaps": gaps}, f,
                       sort_keys=False, allow_unicode=True, width=120)
    return gaps


def main() -> None:
    if DB_FILE.exists():
        DB_FILE.unlink()
    conn = sqlite3.connect(DB_FILE)
    for t in TABLES:
        rows = build_rows(t)
        if t.kind == "csv":
            write_csv(t, rows)
        else:
            write_sql(conn, t, rows)
    conn.commit()
    with open(DUMP_FILE, "w", encoding="utf-8") as f:
        for line in conn.iterdump():
            f.write(line + "\n")
    conn.close()

    write_ground_truth()
    gaps = write_registry()

    counts = {k: 0 for k in CLASSES + [NEG]}
    for t in TABLES:
        for c in t.cols:
            counts[c.true_class] += 1
    n_csv = sum(1 for t in TABLES if t.kind == "csv")
    n_sql = sum(1 for t in TABLES if t.kind == "sql")
    print(f"Seed {SEED}: {n_csv} CSV files in {CSV_DIR.relative_to(BACKEND)}, "
          f"{n_sql} tables in {DB_FILE.relative_to(BACKEND)}")
    print(f"Labelled fields: {sum(counts.values())}")
    for k, v in counts.items():
        print(f"  {k:24} {v}")
    print(f"Deliberate metadata gaps: {len(gaps)} (see {REGISTRY.relative_to(BACKEND)})")


if __name__ == "__main__":
    main()
