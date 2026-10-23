import random
import string
from pathlib import Path
import sys
import pandas as pd
from faker import Faker

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.services.validators import verhoeff_check_digit  # noqa: E402

fake = Faker()

def generate_pan() -> str:
    """Generates a synthetic Indian PAN (e.g., ABCDE1234F)."""
    letters1 = ''.join(random.choices(string.ascii_uppercase, k=5))
    digits = ''.join(random.choices(string.digits, k=4))
    letter2 = random.choice(string.ascii_uppercase)
    return f"{letters1}{digits}{letter2}"

def generate_aadhaar() -> str:
    """Generates a synthetic 12-digit Indian Aadhaar (4-4-4) with a valid Verhoeff check digit."""
    body = str(random.randint(2, 9)) + "".join(random.choices(string.digits, k=10))
    d = body + str(verhoeff_check_digit(body))
    return f"{d[:4]} {d[4:8]} {d[8:]}"

def generate_phone() -> str:
    """Generates a synthetic Indian phone number with +91 country code."""
    first_digit = random.choice([7, 8, 9])
    rest_digits = random.randint(100000000, 999999999)
    return f"+91{first_digit}{rest_digits}"

def generate_labelled_test_data(rows_per_class: int = 10, unknown_rows: int = 10):
    rows = []

 
    sample_names = [
        "Aarav Sharma", "Pooja Patel", "Rahul Verma", "Neha Singh", "Amit Kumar",
        "Priya Iyer", "Rajesh Gupta", "Vikram Malhotra", "Ananya Deshmukh", "Siddharth Joshi",
        "John Smith", "David Miller", "Sarah Connor", "Emily Clark"
    ]
    selected_names = sample_names[:rows_per_class] if rows_per_class <= len(sample_names) else [fake.name() for _ in range(rows_per_class)]
    for name in selected_names:
        rows.append({"text": name, "label": "Name"})

   
    for _ in range(rows_per_class):
        rows.append({"text": fake.email(), "label": "Email ID"})

    
    for _ in range(rows_per_class):
        rows.append({"text": generate_phone(), "label": "Phone Number"})

    # 4. Government ID: Synthetic Indian PAN and Aadhaar
    half = rows_per_class // 2
    for _ in range(half):
        rows.append({"text": generate_pan(), "label": "Government ID"})
    for _ in range(rows_per_class - half):
        rows.append({"text": generate_aadhaar(), "label": "Government ID"})

    # 5. Financial Data: Valid format Visa credit card numbers passing Luhn checks
    for _ in range(rows_per_class):
        rows.append({"text": fake.credit_card_number(card_type="visa"), "label": "Financial Data"})

    # 6. Unknown: Non-PII control values (colors, categories, numbers) to test false positives
    non_pii_samples = [
        "Ocean Blue", "Crimson Red", "Forest Green", "Amber Yellow",
        "Widget-SKU-4912", "Completed", "Pending Approval", "Low Priority",
        "42", "1024"
    ]
    for val in non_pii_samples[:unknown_rows]:
        rows.append({"text": val, "label": "Unknown"})

    # Shuffle rows
    random.seed(42)
    random.shuffle(rows)

    df = pd.DataFrame(rows, columns=["text", "label"])

    # Output file path: data/labelled_test_set.csv relative to backend root
    base_dir = Path(__file__).resolve().parent.parent
    data_dir = base_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    output_path = data_dir / "labelled_test_set.csv"

    df.to_csv(output_path, index=False)
    print(f"Successfully generated {len(df)} rows at {output_path}")
    print(f"Columns: {list(df.columns)}")
    print(df["label"].value_counts())
    return df

if __name__ == "__main__":
    generate_labelled_test_data()