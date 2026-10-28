"""Score a parser against a labeled JSON file.

Usage (run from your repo root):
    python evaluate.py data/dev.json --parser YOUR_MODULE:YOUR_FUNCTION
    python evaluate.py data/dev.json --parser app.parser:parse_request --show-failures
    python evaluate.py data/holdout.json --parser app.parser:parse_request --save results/v1_holdout.json

--parser is "module:function". The function takes the raw text (a string) and
returns a dict in your output contract (or a JSON string, or an object with
.model_dump()).

Scored fields: task_type, items, pickup_location, dropoff_location,
delivery_required, deadline, missing. Confidence is NOT scored.
"""
import argparse
import hashlib
import importlib
import json
import sys
from datetime import datetime
from pathlib import Path

FIELDS = [
    "task_type", "items", "pickup_location", "dropoff_location",
    "delivery_required", "deadline", "missing",
]


def norm(value):
    return value.strip().lower() if isinstance(value, str) else value


def same_text(a, b):
    return norm(a) == norm(b)


def same_location(a, b):
    """Loose match: both empty, or one contains the other (case-insensitive)."""
    a, b = norm(a), norm(b)
    if a is None or b is None:
        return a is b
    return a in b or b in a


def same_items(a, b):
    def key(items):
        return sorted(
            (norm(i.get("name")), i.get("quantity"), norm(i.get("unit")))
            for i in (items or [])
        )
    return key(a) == key(b)


def same_missing(a, b):
    return sorted(a or []) == sorted(b or [])


COMPARE = {
    "task_type": same_text,
    "deadline": same_text,
    "pickup_location": same_location,
    "dropoff_location": same_location,
    "delivery_required": lambda a, b: a == b,
    "items": same_items,
    "missing": same_missing,
}


def verify_checksum(path):
    """If a .sha256 file sits next to the data file, it must match."""
    checksum_file = path.with_suffix(".sha256")
    if not checksum_file.exists():
        print(f"note: no checksum file found at {checksum_file}, skipping integrity check")
        return
    expected = checksum_file.read_text().split()[0]
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if expected != actual:
        sys.exit(f"ERROR: {path} does not match {checksum_file}. The file changed since it was frozen.")
    print(f"checksum OK for {path.name}")


def load_parser(spec):
    module_name, _, func_name = spec.partition(":")
    if not func_name:
        sys.exit('--parser must look like "module:function", e.g. app.parser:parse_request')
    sys.path.insert(0, str(Path.cwd()))
    return getattr(importlib.import_module(module_name), func_name)


def to_dict(result):
    if hasattr(result, "model_dump"):
        return result.model_dump()
    if isinstance(result, str):
        return json.loads(result)
    return result


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("data_file")
    ap.add_argument("--parser", required=True)
    ap.add_argument("--show-failures", action="store_true")
    ap.add_argument("--save", help="write the scores to this JSON file")
    args = ap.parse_args()

    path = Path(args.data_file)
    if args.show_failures and "holdout" in path.name.lower():
        sys.exit("Refusing to show failures for the holdout set: reading them would let you tune against it. "
                 "Use the dev set for debugging.")

    verify_checksum(path)
    samples = json.loads(path.read_text(encoding="utf-8"))
    parse = load_parser(args.parser)

    correct = {f: 0 for f in FIELDS}
    all_correct = 0
    errors = 0
    failures = []

    for sample in samples:
        expected = sample["expected"]
        try:
            got = to_dict(parse(sample["text"]))
        except Exception as exc:  # a crash counts as every field wrong
            errors += 1
            failures.append((sample["text"], {"__error__": repr(exc)}))
            continue
        wrong = {}
        for field in FIELDS:
            if COMPARE[field](got.get(field), expected.get(field)):
                correct[field] += 1
            else:
                wrong[field] = {"expected": expected.get(field), "got": got.get(field)}
        if not wrong:
            all_correct += 1
        else:
            failures.append((sample["text"], wrong))

    n = len(samples)
    print(f"\n{path.name}: {n} samples, {errors} parser crash(es)\n")
    print(f"{'field':<20}{'correct':>8}{'accuracy':>10}")
    for field in FIELDS:
        print(f"{field:<20}{correct[field]:>8}{correct[field] / n:>10.0%}")
    print(f"{'ALL FIELDS':<20}{all_correct:>8}{all_correct / n:>10.0%}")

    if args.show_failures:
        print("\nFailures:")
        for text, wrong in failures:
            print(f"\n  {text}")
            for field, detail in wrong.items():
                print(f"    {field}: {detail}")

    if args.save:
        out = Path(args.save)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps({
            "file": str(path),
            "run_at": datetime.now().isoformat(timespec="seconds"),
            "samples": n,
            "crashes": errors,
            "accuracy": {f: correct[f] / n for f in FIELDS},
            "all_fields": all_correct / n,
        }, indent=2))
        print(f"\nsaved scores to {out}")


if __name__ == "__main__":
    main()