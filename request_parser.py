"""Rules-based natural-language request parser (v1).

parse_request(text) returns a dict in the project's output contract:
task_type, items, pickup_location, dropoff_location, delivery_required,
deadline, confidence, missing.
"""
import re

# ------------------------------------------------------------------ task type
# Strong keywords count double: they almost only appear in one kind of job.
# Weak keywords count once: they show up in several kinds of job.
KEYWORDS = {
    "shopping": {"strong": ["buy", "groceries", "purchase"], "weak": ["market"]},
    "delivery": {"strong": ["pick up", "pickup", "drop", "parcel", "package"],
                 "weak": ["deliver"]},
    "cleaning": {"strong": ["clean", "sweep", "mop"], "weak": ["dirty", "compound"]},
    "laundry": {"strong": ["laundry", "iron"], "weak": ["clothes"]},
    "repair": {"strong": ["plumber", "electrician", "repair", "wiring", "leak"],
               "weak": ["fix", "overflow", "phase"]},
}

NUMBER_WORDS = "one|two|three|four|five|six|seven|eight|nine|ten"
NUMBER_MAP = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
              "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
              "a dozen": 12}

# Matches things like "3 bags of rice" or "two crates of eggs".
ITEM_PATTERN = re.compile(rf"\b(\d+|{NUMBER_WORDS})\s+\w+\s+of\s+\w+")


def classify_task(text):
    text = text.lower()
    scores = {}
    for task_type, groups in KEYWORDS.items():
        score = 2 * sum(1 for w in groups["strong"] if w in text)
        score += sum(1 for w in groups["weak"] if w in text)
        scores[task_type] = score

    # "3 bags of rice" means goods are being bought
    if ITEM_PATTERN.search(text):
        scores["shopping"] += 2

    best = max(scores, key=scores.get)
    if scores[best] == 0:
        return "other"
    return best


# ---------------------------------------------------------------------- items
QUANTITY_ITEM = re.compile(rf"\b(\d+|{NUMBER_WORDS})\s+(\w+)\s+of\s+(\w+)")
PARCEL = re.compile(r"\b(?:a|an)\s+(parcel|package)\b")
LOOSE_QTY = re.compile(rf"\b(\d+|{NUMBER_WORDS}|a dozen)\s+(?!of\b)([a-z]+)")
BUY_LIST = re.compile(r"\b(?:buy|get|purchase)\s+(?:me\s+)?(.+)", re.I)

# A number right after one of these is an address or room number, not a quantity.
PLACE_WORDS = {"mile", "room", "flat", "phase", "block", "plot", "no", "number",
               "street", "st", "road", "rd", "avenue", "line", "floor"}
# A word after a number that is a time, a verb or a room type, not a thing.
NOT_ITEM = {"delivered", "deliver", "am", "pm", "hour", "hours", "minute",
            "minutes", "day", "days", "week", "weeks", "bedroom", "bedrooms",
            "people", "persons", "person"}
VAGUE_ITEM_WORDS = {"something", "anything", "stuff", "things", "thing", "it", "them"}

_STOP_ITEMS = re.compile(
    r"\s+(?:then|for|from|at|to|by|before|on|this|tomorrow|today|tonight|"
    r"urgently|asap|please|pls|so|but|because|delivered|deliver|i|we)\b|[.;!?]",
    re.I)


def _to_number(token):
    if token.isdigit():
        return int(token)
    return NUMBER_MAP[token]


def extract_items(text, task_type="other"):
    lowered = text.lower()
    items = []

    # 1. "3 bags of rice", "two crates of eggs"
    for qty, unit, name in QUANTITY_ITEM.findall(lowered):
        items.append({"name": name, "quantity": _to_number(qty), "unit": unit})
    masked = QUANTITY_ITEM.sub(" ", lowered)

    # 2. "a parcel", "a package" -> one item, no unit
    for name in PARCEL.findall(masked):
        items.append({"name": name, "quantity": 1, "unit": None})

    if task_type in ("shopping", "delivery") and not items:
        # 3. "5 shirts", "a dozen eggs"
        for m in LOOSE_QTY.finditer(masked):
            qty, name = m.groups()
            before = masked[:m.start()].split()
            if (before and before[-1] in PLACE_WORDS) or name in NOT_ITEM:
                continue
            items.append({"name": name, "quantity": _to_number(qty), "unit": None})

    if task_type == "shopping" and not items:
        # 4. "buy some tomatoes and pepper" -> names only, no quantity
        m = BUY_LIST.search(text)
        if m:
            tail = _STOP_ITEMS.split(m.group(1), maxsplit=1)[0]
            for part in re.split(r"\s*(?:,|\band\b|&)\s*", tail):
                name = re.sub(r"^(?:some|any|a|an|the|my|our)\s+", "",
                              part.strip(), flags=re.I).lower()
                if name and len(name.split()) <= 3 and name not in VAGUE_ITEM_WORDS:
                    items.append({"name": name, "quantity": None, "unit": None})
    return items


# ------------------------------------------------------------------ locations
# A named place ("Mile 3", "Rumuola") is captured. A generic one ("the market",
# "my house") is not, so the request is flagged as missing that location.
GENERIC_FIRST = {"the", "my", "your", "our", "a", "an", "this", "that", "me", "us",
                 "him", "her", "them", "it", "home", "house", "there", "here",
                 "market", "shop", "store", "park", "supermarket", "office"}

_STOP_PLACE = re.compile(
    r"\s+(?:and|then|go|for|by|before|on|this|tomorrow|today|tonight|urgently|"
    r"asap|please|pls|abeg|so|but|because|delivered|deliver|i|we|to)\b|[,.;!?]",
    re.I)

PICKUP_PATTERNS = [
    re.compile(r"\bfrom\s+(.+)", re.I),
    re.compile(r"\b(?:pick\s?up|collect)\b[^.]*?\b(?:at|around|near|in)\s+(.+)", re.I),
]
DROPOFF_PATTERNS = [
    re.compile(r"\bdrop\s*(?:it|them|that|this)?\s*(?:off\s+)?(?:at|in|to)\s+(.+)", re.I),
    re.compile(r"\bdeliver(?:ed)?(?:\s+(?:it|them|that|this))?\s+to\s+(.+)", re.I),
    re.compile(r"\b(?:take|bring|carry|send)\b[^.]*?\bto\s+(.+)", re.I),
]


def _clean_place(raw):
    place = _STOP_PLACE.split(raw, maxsplit=1)[0].strip(" -")
    if re.search(r"\sin\s", place, re.I):          # "my sister in Trans Amadi"
        place = re.split(r"\s+in\s+", place, flags=re.I)[-1]
    words = place.lower().split()
    if not words or words[0] in GENERIC_FIRST or len(words) > 5:
        return None
    return place.title() if place.islower() else place


def _find_place(patterns, text):
    for pattern in patterns:
        m = pattern.search(text)
        if m:
            place = _clean_place(m.group(1))
            if place:
                return place
    return None


# ------------------------------------------------------------------- deadline
DAYS_FULL = r"(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)"
DAYS_ABBR = r"(?:mon|tue|tues|wed|thu|thur|thurs|fri|sat|sun)"
DAY_ANY = rf"(?:{DAYS_FULL}|{DAYS_ABBR})"
PERIODS = r"(?:morning|mrng|afternoon|evening|night)"
CLOCK = r"\d{1,2}(?::\d{2})?\s?(?:am|pm)"

DEADLINE_PATTERNS = [
    re.compile(rf"\b(?:before|by)\s+{CLOCK}\b", re.I),                     # before 5pm
    re.compile(rf"\bbefore\s+(?:{DAYS_FULL}|tomorrow|{PERIODS})\b", re.I),  # before saturday
    re.compile(rf"\b(?:tomorrow|today|{DAY_ANY}|this|next)\s+{PERIODS}\b", re.I),
    re.compile(r"\b(?:next|this)\s+(?:week|month|weekend)\b", re.I),
    re.compile(rf"\b(?:by|in the|for)\s+({PERIODS})\b", re.I),             # by evening -> evening
    re.compile(rf"\b(?:today|tonight|tomorrow|urgently|asap|immediately|{DAYS_FULL})\b", re.I),
]


def _find_deadline(text):
    """Return (phrase, (start, end)) of the earliest, longest time phrase, or (None, None)."""
    best = None
    for pattern in DEADLINE_PATTERNS:
        m = pattern.search(text)
        if not m:
            continue
        if best is None or m.start() < best.start() or (
                m.start() == best.start() and len(m.group(0)) > len(best.group(0))):
            best = m
    if best is None:
        return None, None
    phrase = best.group(1) if best.lastindex else best.group(0)
    return re.sub(r"\s+", " ", phrase.lower()).strip(), best.span()


# ----------------------------------------------------------- delivery / vague
DELIVERY_VERBS = re.compile(r"\b(?:bring|deliver(?:ed)?|return)\b", re.I)

FILLER = {"i", "im", "i'm", "need", "needs", "want", "wants", "help", "with",
          "something", "anything", "someone", "somebody", "person", "people", "to",
          "me", "my", "please", "pls", "abeg", "a", "an", "the", "hello", "hi",
          "hey", "good", "morning", "afternoon", "evening", "night", "can", "could",
          "would", "you", "for", "us", "we", "is", "am", "are", "do", "some",
          "thing", "things", "kindly", "come", "go", "dey", "make", "get", "it",
          "this", "that", "of", "in", "on", "at", "and", "or", "urgent"}


def _is_vague(text, span):
    """True when nothing in the message says what job is wanted."""
    if span:
        text = text[:span[0]] + " " + text[span[1]:]
    words = re.findall(r"[a-z']+", text.lower())
    return not [w for w in words if w not in FILLER]


# ----------------------------------------------------------------- main entry
def parse_request(text):
    text = (text or "").strip()
    task_type = classify_task(text)
    deadline, span = _find_deadline(text)
    items = extract_items(text, task_type)

    needs_places = task_type in ("shopping", "delivery")
    pickup = _find_place(PICKUP_PATTERNS, text) if needs_places else None
    dropoff = _find_place(DROPOFF_PATTERNS, text) if needs_places else None
    delivery_required = needs_places or bool(DELIVERY_VERBS.search(text))

    # Required fields that the message did not give.
    missing = []
    if task_type == "other" and _is_vague(text, span):
        missing.append("task_type")
    if task_type == "shopping" and not items:
        missing.append("items")
    if needs_places and pickup is None:
        missing.append("pickup_location")
    if task_type == "delivery" and dropoff is None:
        missing.append("dropoff_location")
    if deadline is None:
        missing.append("deadline")

    return {
        "task_type": task_type,
        "items": items,
        "pickup_location": pickup,
        "dropoff_location": dropoff,
        "delivery_required": delivery_required,
        "deadline": deadline,
        "confidence": max(0.0, round(1 - 0.25 * len(missing), 2)),
        "missing": missing,
    }
