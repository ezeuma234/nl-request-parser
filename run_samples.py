import json
from request_parser import classify_task

samples = json.load(open("samples.json"))
wrong = 0

for s in samples:
    got = classify_task(s["text"])
    want = s["expected"]["task_type"]
    if got != want:
        wrong += 1
        print(f"WRONG: {s['text']}")
        print(f"  expected={want}  got={got}\n")

print(f"{len(samples) - wrong}/{len(samples)} correct")