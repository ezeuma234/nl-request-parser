KEYWORDS = {
    "shopping": ["buy", "market", "groceries", "purchase"],
    "delivery": ["pick up", "pickup", "drop", "deliver", "parcel", "package"],
    "cleaning": ["clean", "sweep", "mop", "dirty", "compound"],
    "laundry": ["laundry", "iron", "clothes"],
    "repair": ["leak", "plumber", "electrician", "repair", "fix", "wiring",
               "overflow", "phase"],
}


def classify_task(text):
    text = text.lower()
    scores = {}
    for task_type, words in KEYWORDS.items():
        scores[task_type] = sum(1 for word in words if word in text)

    best = max(scores, key=scores.get)
    if scores[best] == 0:
        return "other"
    return best