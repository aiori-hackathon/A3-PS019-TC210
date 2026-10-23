import os
import random
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path


def generate_luhn_16():
    prefix = random.choice([4, 5])
    digits = [prefix] + [random.randint(0, 9) for _ in range(14)]
    total = 0
    for i, d in enumerate(reversed(digits)):
        if i % 2 == 0:
            val = d * 2
            if val > 9:
                val -= 9
            total += val
        else:
            total += d
    check_digit = (10 - (total % 10)) % 10
    digits.append(check_digit)
    return "".join(map(str, digits))


def verhoeff_check_digit(digits: str) -> int:
    d = [[0,1,2,3,4,5,6,7,8,9],[1,2,3,4,0,6,7,8,9,5],[2,3,4,0,1,7,8,9,5,6],[3,4,0,1,2,8,9,5,6,7],
         [4,0,1,2,3,9,5,6,7,8],[5,9,8,7,6,0,4,3,2,1],[6,5,9,8,7,1,0,4,3,2],[7,6,5,9,8,2,1,0,4,3],
         [8,7,6,5,9,3,2,1,0,4],[9,8,7,6,5,4,3,2,1,0]]
    p = [[0,1,2,3,4,5,6,7,8,9],[1,5,7,6,2,8,3,0,9,4],[5,8,0,3,7,9,6,1,4,2],[8,9,1,6,0,4,3,5,2,7],
         [9,4,5,3,1,2,6,8,7,0],[4,2,8,6,5,7,3,9,0,1],[2,7,9,3,8,0,6,4,1,5],[7,0,4,6,9,1,3,2,5,8]]
    inv = [0,4,3,2,1,5,6,7,8,9]
    c = 0
    for i, ch in enumerate(reversed(digits)):
        c = d[c][p[(i + 1) % 8][int(ch)]]
    return inv[c]


def generate_aadhaar():
    """12-digit Aadhaar (4-4-4) with a valid Verhoeff check digit."""
    body = str(random.randint(2, 9)) + "".join(str(random.randint(0, 9)) for _ in range(10))
    full = body + str(verhoeff_check_digit(body))
    return f"{full[:4]} {full[4:8]} {full[8:]}"


def generate_bank_account():
    length = random.choice([11, 12, 13, 14])
    first_digit = random.randint(1, 9)
    remaining = [random.randint(0, 9) for _ in range(length - 1)]
    return str(first_digit) + "".join(map(str, remaining))


def main():
    random.seed(42)

    base_dir = Path(__file__).resolve().parent.parent
    data_dir = base_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    db_file = data_dir / "sample.db"

    os.makedirs("data", exist_ok=True)

    if db_file.exists():
        db_file.unlink()

    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE customers (
            customer_id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT,
            email TEXT,
            phone TEXT,
            aadhaar TEXT,
            pan TEXT,
            address TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE payments (
            payment_id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER,
            credit_card TEXT,
            account_number TEXT,
            amount REAL,
            FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
        )
    """)

    cursor.execute("""
        CREATE TABLE system_logs (
            log_id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT,
            message TEXT,
            created_at TEXT
        )
    """)

    first_names = [
        "Rohan", "Priya", "Aarav", "Ananya", "Vikram",
        "Neha", "Aditya", "Kavita", "Siddharth", "Pooja",
        "Rahul", "Sneha", "Amit", "Deepika", "Karan",
        "Sunita", "Rajesh", "Meera", "Manoj", "Shweta"
    ]
    last_names = [
        "Sharma", "Patel", "Verma", "Iyer", "Malhotra",
        "Gupta", "Mukherjee", "Reddy", "Nair", "Kulkarni",
        "Singh", "Joshi", "Chopra", "Deshmukh", "Mehta",
        "Bose", "Rao", "Das", "Bhat", "Kapoor"
    ]
    cities = [
        "Bengaluru, Karnataka", "Mumbai, Maharashtra", "Delhi, NCR",
        "Hyderabad, Telangana", "Chennai, Tamil Nadu", "Pune, Maharashtra",
        "Kolkata, West Bengal", "Jaipur, Rajasthan", "Ahmedabad, Gujarat",
        "Chandigarh, Punjab"
    ]

    customers_data = []
    for i in range(20):
        first = first_names[i]
        last = last_names[i]
        full_name = f"{first} {last}"
        email = f"{first.lower()}.{last.lower()}@example.com"
        phone = f"+91{random.choice(['6', '7', '8', '9'])}{''.join(str(random.randint(0, 9)) for _ in range(9))}"
        aadhaar = generate_aadhaar()
        pan_letters = "".join(random.choices("ABCDEFGHIJKLMNOPQRSTUVWXYZ", k=5))
        pan_digits = "".join(random.choices("0123456789", k=4))
        pan_last = random.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
        pan = f"{pan_letters}{pan_digits}{pan_last}"
        address = f"Flat {random.randint(101, 909)}, {cities[i % len(cities)]}"
        customers_data.append((full_name, email, phone, aadhaar, pan, address))

    cursor.executemany("""
        INSERT INTO customers (full_name, email, phone, aadhaar, pan, address)
        VALUES (?, ?, ?, ?, ?, ?)
    """, customers_data)

    payments_data = []
    for _ in range(15):
        cust_id = random.randint(1, 20)
        card = generate_luhn_16()
        acct = generate_bank_account()
        amt = round(random.uniform(250.0, 75000.0), 2)
        payments_data.append((cust_id, card, acct, amt))

    cursor.executemany("""
        INSERT INTO payments (customer_id, credit_card, account_number, amount)
        VALUES (?, ?, ?, ?)
    """, payments_data)

    log_events = [
        ("LOGIN", "User logged in"),
        ("LOGOUT", "User logged out"),
        ("AUDIT", "Automated evidence audit completed"),
        ("SCAN", "SQL schema discovery initiated"),
        ("REPORT", "Compliance inventory report generated")
    ]
    logs_data = []
    base_time = datetime(2026, 10, 18, 9, 0, 0)
    for i in range(25):
        evt, msg = log_events[i % len(log_events)]
        timestamp = (base_time + timedelta(minutes=i * 12)).isoformat() + "Z"
        logs_data.append((evt, msg, timestamp))

    cursor.executemany("""
        INSERT INTO system_logs (event_type, message, created_at)
        VALUES (?, ?, ?)
    """, logs_data)

    conn.commit()
    conn.close()

    print(f"Seeded data/sample.db with {len(customers_data)} customers, {len(payments_data)} payments, {len(logs_data)} log rows")


if __name__ == "__main__":
    main()
