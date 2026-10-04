"""Generates labelled narrations in the formats Indian banks actually print, to bootstrap the classifier.

Users' own corrections are added on top of this at training time (see categorizer.py).
"""
import random

from .merchants import MERCHANTS

DEBIT_TEMPLATES = [
    "UPI/{ref}/{m}/{vpa}@okaxis/Payment",
    "UPI-{m}-{vpa}@ybl-{ref}-UPI",
    "UPI/DR/{ref}/{m}/HDFC/{vpa}@hdfcbank",
    "POS {card} {m} {city}",
    "POS/{m}/{city}/{ref}",
    "ACH D- {m}-{ref}",
    "NACH/{m}/{ref}",
    "{m} {city} IN",
    "ONL {m} {ref}",
    "VPS/{m}/{ref}",
    "IMPS/P2A/{ref}/{m}",
    "BIL/ONL/{ref}/{m}/",
    "{m}",
    "{m_lower} payment",
]
CREDIT_TEMPLATES = [
    "NEFT CR-{ref}-{m}",
    "NEFT/{ref}/{m}/ACME TECHNOLOGIES",
    "IMPS/{ref}/{m}",
    "UPI/CR/{ref}/{m}/{vpa}@oksbi",
    "{m} CREDITED",
    "BY TRANSFER-{m}-{ref}",
]
CITIES = ["MUMBAI", "BANGALORE", "PUNE", "DELHI", "HYDERABAD", "GURGAON", "CHENNAI"]
CREDIT_CATEGORIES = {"Salary", "Other Income"}

# Local shops rarely appear in any list, but their names usually say what they sell
# ("SAI PETROL PUMP", "SHARMA MEDICAL STORES"). Generated names teach the model those keywords.
NAME_PREFIXES = ["SHREE", "SAI", "NEW", "OM", "RAJ", "KRISHNA", "GANESH", "SHARMA", "PATEL", "ROYAL",
                 "CITY", "STAR", "GOLDEN", "MAHALAXMI", "JAI", "BALAJI", "VINAYAK", "NAVRANG"]
PERSON_NAMES = ["RAHUL", "PRIYA", "AMIT", "SNEHA", "ROHAN", "NEHA", "KARAN", "ANJALI", "VIKRAM", "POOJA"]
CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "Food & Dining": ["RESTAURANT", "CAFE", "DHABA", "BIRYANI HOUSE", "SWEETS", "BAKERY", "KITCHEN",
                      "PIZZERIA", "CHAI POINT", "FAST FOOD", "BAR AND GRILL", "VADA PAV CENTRE"],
    "Groceries": ["KIRANA STORE", "SUPERMARKET", "GENERAL STORES", "PROVISION STORE", "DAIRY", "VEGETABLES",
                  "FRUIT MART", "GROCERY", "HYPERMARKET", "FRESH MART"],
    "Shopping": ["FASHION", "GARMENTS", "ELECTRONICS", "FOOTWEAR", "MOBILE STORE", "COLLECTION", "TEXTILES",
                 "JEWELLERS", "BOUTIQUE", "GIFT SHOP", "OPTICALS"],
    "Transport": ["TAXI SERVICE", "AUTO RICKSHAW", "CAB SERVICE", "PARKING", "TOLL PLAZA", "METRO CARD",
                  "BIKE TAXI"],
    "Fuel": ["PETROL PUMP", "FUEL STATION", "SERVICE STATION", "FILLING STATION", "PETROLEUM", "CNG STATION"],
    "Bills & Utilities": ["ELECTRICITY BILL", "BROADBAND", "MOBILE RECHARGE", "GAS BILL", "WATER BILL",
                          "DTH RECHARGE", "POSTPAID BILL", "INTERNET SERVICES", "POWER DISTRIBUTION"],
    "Rent": ["RENT", "HOUSE RENT", "FLAT RENT", "PG RENT", "SOCIETY MAINTENANCE", "HOSTEL RENT"],
    "Entertainment": ["CINEMAS", "GAMING ZONE", "MULTIPLEX", "BOWLING", "AMUSEMENT PARK", "CONCERT TICKETS",
                      "EVENTS", "MOVIE TICKETS"],
    "Subscriptions": ["MONTHLY SUBSCRIPTION", "PREMIUM PLAN", "MEMBERSHIP", "ANNUAL PLAN", "STREAMING",
                      "PRO SUBSCRIPTION", "MUSIC PREMIUM"],
    "Health": ["PHARMACY", "MEDICAL STORES", "HOSPITAL", "CLINIC", "DIAGNOSTICS", "CHEMIST", "DENTAL CARE",
               "PATHLAB", "FITNESS GYM", "NURSING HOME"],
    "Education": ["ACADEMY", "COACHING CLASSES", "TUITION", "COLLEGE FEES", "BOOK DEPOT", "INSTITUTE",
                  "SCHOOL FEES", "EXAM FEES", "STATIONERY"],
    "Travel": ["TOURS AND TRAVELS", "HOTEL", "RESORT", "AIRLINES", "LODGE", "HOLIDAYS", "FLIGHT BOOKING",
               "BUS TICKETS", "TRAIN TICKET"],
    "Investments": ["MUTUAL FUND SIP", "SECURITIES", "STOCK BROKING", "CAPITAL MARKETS", "WEALTH",
                    "FIXED DEPOSIT", "RECURRING DEPOSIT", "DEMAT"],
    "EMI & Loans": ["LOAN EMI", "FINANCE EMI", "CREDIT CARD BILL", "CARD PAYMENT", "FINSERV EMI",
                    "PERSONAL LOAN", "BNPL REPAYMENT"],
    "Cash Withdrawal": ["ATM", "CASH WDL", "ATM WITHDRAWAL", "CASH AT ATM"],
    "Salary": ["TECHNOLOGIES SALARY", "SOLUTIONS PAYROLL", "INFOTECH SALARY", "CONSULTING STIPEND",
               "INDUSTRIES SALARY", "SYSTEMS PAYROLL"],
    "Transfers": ["TRANSFER", "SENT TO", "FUND TRANSFER", "SELF TRANSFER", "RECEIVED FROM"],
    "Other Income": ["INTEREST", "CASHBACK", "REFUND", "DIVIDEND", "REVERSAL", "BONUS REWARD"],
}


def generic_merchants(seed: int = 11) -> dict[str, list[str]]:
    rng = random.Random(seed)
    out: dict[str, list[str]] = {}
    for category, keywords in CATEGORY_KEYWORDS.items():
        names = []
        for kw in keywords:
            for _ in range(2):
                if category == "Transfers":
                    names.append(f"{kw} {rng.choice(PERSON_NAMES)}")
                else:
                    names.append(f"{rng.choice(NAME_PREFIXES)} {kw}")
        out[category] = sorted(set(names))
    return out


def narration(merchant: str, category: str, rng: random.Random) -> str:
    templates = CREDIT_TEMPLATES if category in CREDIT_CATEGORIES else DEBIT_TEMPLATES
    vpa = merchant.lower().replace(" ", "")[:12]
    return rng.choice(templates).format(
        m=merchant, m_lower=merchant.lower(), vpa=vpa, city=rng.choice(CITIES),
        ref=rng.randint(10**9, 10**12 - 1), card=f"XXXX{rng.randint(1000, 9999)}",
    )


def build_dataset(per_merchant: int = 12, seed: int = 7) -> tuple[list[str], list[str], list[str]]:
    """Returns (texts, labels, merchants) so evaluation can hold out whole merchants."""
    rng = random.Random(seed)
    texts, labels, merchants = [], [], []
    generic = generic_merchants()
    for category in MERCHANTS:
        for merchant in MERCHANTS[category] + generic.get(category, []):
            for _ in range(per_merchant):
                texts.append(narration(merchant, category, rng))
                labels.append(category)
                merchants.append(merchant)
    return texts, labels, merchants
