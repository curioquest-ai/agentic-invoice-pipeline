"""Synthetic Indian GST invoice records -- zero external dependencies.

Named faker_in.py because it plays the role Faker's Indian locale would, but
a hand-rolled generator is deterministic (seeded), dependency-free, and --
critically -- produces GSTINs with VALID checksums, so that our validators
only flag the errors the chaos engine deliberately injects. If your clean
data fails its own validators, your eval is meaningless before you start.

Every record produced here is internally consistent (math adds up, GSTIN
checks out, date is ISO). Mess is added later, by chaos.py, ON PURPOSE and
WITH A LOG. That separation is the day's rule: truth first, chaos second.
"""
from __future__ import annotations

import random
import string

GSTIN_CHARS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
STATE_CODES = ["29", "27", "07", "33", "06", "24", "36", "19"]  # KA MH DL TN HR GJ TS WB

COMPANIES = [
    ("Sri Venkateshwara Traders", "Bengaluru"), ("Mahalakshmi Enterprises", "Chennai"),
    ("Patel Industrial Supplies", "Ahmedabad"), ("Verma Electricals Pvt Ltd", "New Delhi"),
    ("Deccan Hardware Mart", "Hyderabad"), ("Kohinoor Packaging Co", "Mumbai"),
    ("Ganga Steel & Alloys", "Kolkata"), ("Nandi Agro Solutions", "Mysuru"),
    ("Bharat Office Systems", "Pune"), ("Shree Balaji Polymers", "Coimbatore"),
    ("Arihant Paper Products", "Jaipur"), ("Kaveri Tech Distributors", "Bengaluru"),
]

ITEMS = [
    ("HDMI Cable 2m", "8544"), ("Wireless Mouse", "8471"), ("A4 Copier Paper 500s", "4802"),
    ("Laptop Stand Aluminium", "8473"), ("USB-C Charger 65W", "8504"), ("LED Panel Light 18W", "9405"),
    ("Packing Tape 48mm", "3919"), ("Office Chair Mesh", "9401"), ("Extension Board 6A", "8536"),
    ("Whiteboard Marker Set", "9608"), ("Cloud Hosting - Monthly", "9983"), ("AMC Service Visit", "9987"),
]


def _gstin(rng: random.Random) -> str:
    pan = (
        "".join(rng.choices(string.ascii_uppercase, k=5))
        + "".join(rng.choices(string.digits, k=4))
        + rng.choice(string.ascii_uppercase)
    )
    body = rng.choice(STATE_CODES) + pan + rng.choice("123456789") + "Z"
    total = 0
    for i, ch in enumerate(body):
        v = GSTIN_CHARS.index(ch) * (1 if i % 2 == 0 else 2)
        total += v // 36 + v % 36
    return body + GSTIN_CHARS[(36 - total % 36) % 36]


def make_record(rng: random.Random, seq: int) -> dict:
    """One internally-consistent invoice record. Dates ISO; chaos comes later."""
    vendor, city = rng.choice(COMPANIES)
    n_items = rng.randint(1, 5)
    items = []
    for _ in range(n_items):
        desc, hsn = rng.choice(ITEMS)
        qty = float(rng.randint(1, 20))
        rate = round(rng.uniform(45, 9500), 2)
        items.append({
            "description": desc, "hsn": hsn, "qty": qty, "rate": rate,
            "amount": round(qty * rate, 2),
        })
    subtotal = round(sum(i["amount"] for i in items), 2)
    cgst = round(subtotal * 0.09, 2)   # intra-state 18% GST split equally
    sgst = round(subtotal * 0.09, 2)
    return {
        "vendor": vendor,
        "city": city,
        "gstin": _gstin(rng),
        "invoice_no": f"INV-{2026}-{seq:04d}",
        "date": f"2026-{rng.randint(4, 8):02d}-{rng.randint(1, 28):02d}",  # ISO, canonical
        "items": items,
        "cgst": cgst,
        "sgst": sgst,
        "total": round(subtotal + cgst + sgst, 2),
    }


if __name__ == "__main__":
    import json
    import sys
    sys.path.insert(0, "../03-parser")
    from validators import gstin_checksum_ok

    rng = random.Random(42)
    recs = [make_record(rng, i) for i in range(200)]
    assert all(gstin_checksum_ok(r["gstin"]) for r in recs)
    assert all(abs(sum(i["amount"] for i in r["items"]) + r["cgst"] + r["sgst"] - r["total"]) < 0.05 for r in recs)
    print("faker_in self-test OK -- 200 records, all GSTINs valid, all math consistent")
    print(json.dumps(recs[0], indent=2))
