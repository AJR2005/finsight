"""Merchant vocabulary and narration cleaning shared by the classifier, demo data and subscription detection."""
import re

# Category -> example merchants as they appear in Indian bank / UPI narrations.
MERCHANTS: dict[str, list[str]] = {
    "Food & Dining": ["ZOMATO", "SWIGGY", "DOMINOS PIZZA", "MCDONALDS", "STARBUCKS", "CHAAYOS", "HALDIRAMS",
                      "BURGER KING", "KFC", "BARBEQUE NATION", "THIRD WAVE COFFEE", "SUBWAY", "PIZZA HUT",
                      "BEHROUZ BIRYANI", "CAFE COFFEE DAY", "WOW MOMO", "FAASOS", "EATCLUB"],
    "Groceries": ["BIGBASKET", "BLINKIT", "ZEPTO", "DMART", "RELIANCE FRESH", "JIOMART", "NATURES BASKET",
                  "MORE SUPERMARKET", "SPENCERS", "STAR BAZAAR", "SWIGGY INSTAMART", "COUNTRY DELIGHT"],
    "Shopping": ["AMAZON", "FLIPKART", "MYNTRA", "AJIO", "NYKAA", "MEESHO", "DECATHLON", "CROMA",
                 "RELIANCE DIGITAL", "TATA CLIQ", "LIFESTYLE", "WESTSIDE", "IKEA", "H AND M", "ZARA", "UNIQLO"],
    "Transport": ["UBER", "OLA CABS", "RAPIDO", "MUMBAI METRO", "DMRC", "BEST BUS", "NAMMA YATRI", "BLUSMART",
                  "IRCTC UTS", "FASTAG"],
    "Fuel": ["INDIAN OIL", "HP PETROL PUMP", "BHARAT PETROLEUM", "SHELL", "HPCL", "IOCL FUEL", "NAYARA ENERGY"],
    "Bills & Utilities": ["AIRTEL", "JIO RECHARGE", "VI VODAFONE", "TATA POWER", "ADANI ELECTRICITY",
                          "BESCOM", "MAHANAGAR GAS", "ACT FIBERNET", "BSNL", "TORRENT POWER", "MSEDCL",
                          "TATA PLAY"],
    "Rent": ["RENT PAYMENT", "NOBROKER RENT", "HOUSE RENT", "CRED RENT", "MAGICBRICKS RENT", "PG RENT"],
    "Entertainment": ["BOOKMYSHOW", "PVR CINEMAS", "INOX", "STEAM GAMES", "PLAYSTATION", "DISTRICT",
                      "SMAAASH", "TIMEZONE", "PAYTM INSIDER"],
    "Subscriptions": ["NETFLIX", "SPOTIFY", "AMAZON PRIME", "HOTSTAR", "YOUTUBE PREMIUM", "APPLE MEDIA",
                      "GOOGLE ONE", "SONYLIV", "ZEE5", "LINKEDIN PREMIUM", "CHATGPT PLUS", "NOTION",
                      "CANVA PRO", "AUDIBLE", "CULTFIT"],
    "Health": ["APOLLO PHARMACY", "PHARMEASY", "1MG", "PRACTO", "MEDPLUS", "NETMEDS", "FORTIS HOSPITAL",
               "THYROCARE", "DR LAL PATHLABS", "CULT GYM", "GOLDS GYM"],
    "Education": ["UDEMY", "COURSERA", "BYJUS", "UNACADEMY", "NMIMS FEES", "UPGRAD", "SCALER", "CHEGG",
                  "KINDLE BOOKS", "CROSSWORD BOOKS"],
    "Travel": ["MAKEMYTRIP", "INDIGO", "AIR INDIA", "IRCTC", "GOIBIBO", "OYO ROOMS", "AIRBNB", "CLEARTRIP",
               "VISTARA", "REDBUS", "EASEMYTRIP", "TAJ HOTELS", "AKASA AIR"],
    "Investments": ["ZERODHA", "GROWW", "UPSTOX", "KUVERA", "SIP HDFC MF", "SIP ICICI PRU MF", "COIN BY ZERODHA",
                    "PPF DEPOSIT", "NPS CONTRIBUTION", "SBI MUTUAL FUND", "INDMONEY", "SMALLCASE"],
    "EMI & Loans": ["EMI BAJAJ FINSERV", "HDFC LOAN EMI", "HOME LOAN EMI", "CREDIT CARD PAYMENT",
                    "CRED CC BILL", "SBI CARD PAYMENT", "ICICI CC PAYMENT", "AXIS CARD BILL", "SIMPL PAY",
                    "LAZYPAY", "ZESTMONEY EMI"],
    "Cash Withdrawal": ["ATM WDL", "ATM CASH WITHDRAWAL", "CASH WITHDRAWAL", "NFS CASH WDL"],
    "Salary": ["SALARY", "SAL CREDIT", "PAYROLL", "STIPEND", "INTERN STIPEND"],
    "Transfers": ["SELF TRANSFER", "TRANSFER TO FRIEND", "SPLITWISE", "SENT TO MOM", "FUND TRANSFER",
                  "TRANSFER FROM DAD", "POCKET MONEY"],
    "Other Income": ["INTEREST CREDIT", "CASHBACK", "REFUND", "DIVIDEND", "REVERSAL", "REWARD POINTS"],
}

CATEGORIES = list(MERCHANTS) + ["Other"]
INCOME_CATEGORIES = {"Salary", "Other Income"}
# Money moved between your own accounts or into savings is not "spending".
NON_SPEND_CATEGORIES = INCOME_CATEGORIES | {"Transfers", "Investments"}

_PREFIXES = r"^(upi|pos|neft|imps|rtgs|ach|nach|ecs|atm|bil|onl|mmt|vps|ipay|inb|cms|ib|tpt|ft)\b"
_STOPWORDS = {
    "upi", "pos", "neft", "imps", "rtgs", "ach", "nach", "dr", "cr", "payment", "paid", "to", "from", "via",
    "pvt", "ltd", "private", "limited", "india", "in", "the", "txn", "ref", "no", "online", "www", "com",
    "mumbai", "bangalore", "bengaluru", "delhi", "pune", "hyderabad", "chennai", "gurgaon", "noida",
    "okaxis", "okhdfcbank", "oksbi", "okicici", "ybl", "paytm", "axl", "ibl", "upiintent", "collect", "request",
    "debit", "credit", "card", "visa", "mastercard", "rupay", "transaction", "pay", "bank", "hdfc", "icici",
    "sbi", "axis", "kotak", "yes", "mandate", "autopay", "recurring", "si",
    "bil", "onl", "mmt", "vps", "ipay", "inb", "cms", "ib", "tpt", "ft", "pa", "is", "by",
}


def clean_narration(text: str) -> str:
    """Lower-case, strip reference numbers, UPI handles and noise so the model sees the merchant."""
    t = text.lower()
    t = re.sub(r"[a-z0-9._]+@[a-z]+", " ", t)  # UPI VPAs like zomato@hdfcbank
    t = re.sub(r"\b[x*]{2,}\d*\b", " ", t)  # masked card numbers
    t = re.sub(r"[^a-z ]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def merchant_key(text: str) -> str:
    """Short stable key for a merchant, e.g. 'UPI/NETFLIX COM/9871/Pay' -> 'netflix'."""
    t = re.sub(_PREFIXES, " ", clean_narration(text))
    words = [w for w in t.split() if w not in _STOPWORDS and len(w) > 1]
    return " ".join(words[:2]) or "unknown"
