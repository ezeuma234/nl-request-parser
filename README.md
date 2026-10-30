# Request Parser

Turns messy customer requests, including Nigerian Pidgin, typos and shorthand, into structured JSON for an errand and service marketplace.

**Live demo:** https://nl-request-parser.onrender.com
The demo runs on a free plan, so the first load after a quiet period can take up to a minute.

## Example

Input: `abeg buy some tomatoes and pepper for me tomorrow`

```json
{
  "task_type": "shopping",
  "items": [
    {"name": "tomatoes", "quantity": null, "unit": null},
    {"name": "pepper", "quantity": null, "unit": null}
  ],
  "pickup_location": null,
  "dropoff_location": null,
  "delivery_required": true,
  "deadline": "tomorrow",
  "confidence": 0.75,
  "missing": ["pickup_location"]
}
```

## API

| Endpoint | What it does |
|---|---|
| `POST /parse` | Takes `{"text": "..."}` and returns the JSON above |
| `GET /health` | Returns `{"status": "ok"}` |
| `GET /docs` | Interactive API page |
| `GET /` | Simple web front end |

```bash
curl -X POST https://nl-request-parser.onrender.com/parse \
  -H "Content-Type: application/json" \
  -d '{"text": "buy 3 bags of rice from Mile 3 before 5pm"}'
```

### Output fields

| Field | Meaning |
|---|---|
| `task_type` | `shopping`, `delivery`, `cleaning`, `laundry`, `repair` or `other` |
| `items` | List of `name`, `quantity` and `unit` |
| `pickup_location`, `dropoff_location` | Named places only |
| `delivery_required` | Whether something has to be brought to the customer |
| `deadline` | The time phrase found in the message |
| `missing` | Required details the message did not give |
| `confidence` | 1.0 minus 0.25 for each missing field |

## How it works (v1)

A rules-based parser, with no machine learning:

- **Task type:** weighted keyword scoring, where strong keywords count double.
- **Items:** patterns for "3 bags of rice", "two crates of eggs", "a dozen eggs" and "a parcel".
- **Places:** patterns such as "from X", "pick up ... at X" and "drop it at X".
- **Deadline:** patterns for day names, "tomorrow morning", "before 5pm", "by evening" and similar.
- **Missing and confidence:** calculated from the rules below.

### Labeling rules

These rules define what counts as a correct answer for both the dev set and the holdout set.

1. A deadline is always required.
2. A named place ("Mile 3", "Rumuola") is captured. A generic place ("the market", "my house") is not, and the field is flagged as missing.
3. Shopping needs a pickup location. Delivery needs both pickup and dropoff.
4. A shopping request with no items named is missing `items`.
5. A message too vague to classify is missing `task_type`.
6. "a parcel" means quantity 1. "a dozen" means 12.
7. If a message holds more than one job, `task_type` is the first one mentioned.

## Results

| Field | Dev set (21) | Holdout set (18) |
|---|---|---|
| task_type | 100% | 67% |
| items | 100% | 100% |
| pickup_location | 100% | 100% |
| dropoff_location | 100% | 94% |
| delivery_required | 100% | 100% |
| deadline | 100% | 100% |
| missing | 100% | 94% |
| **All fields correct** | **100%** | **67%** |

How to read these numbers:

- The rules were built while looking at the dev set, so 100% there is expected. The holdout is the real measure.
- The holdout file is frozen with a checksum (`holdout.sha256`), and the evaluation script refuses to run if it changes. It also refuses to print holdout failures, so the rules can't be tuned against it.
- The first holdout run used labels that disagreed with the dev set's rules. They were corrected before any tuning, and the scores above are from the corrected file.
- Both sets are small, so one wrong answer moves a score by several percent. The holdout was written alongside the rules, so the strong fields are best-case figures. Task type is the genuine weak spot.

## Known limitations

- Task type depends on a fixed keyword list, so words that aren't in it are missed.
- Sentences containing a quantity pattern lean towards shopping, even when the job is a pickup.
- Item names are a single word, so "palm oil" becomes "palm".
- Pidgin directions such as "from X go Y" are not understood.
- When a message holds two jobs, only the first is reported.
- "my house" and "my office" are deliberately not treated as addresses.

## Run locally

From the project folder:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload
```

Then open http://127.0.0.1:8000/ for the front end, or http://127.0.0.1:8000/docs for the API page.

## Tests and evaluation

```bash
python3 -m pytest -q
python3 evaluation.py samples.json --parser request_parser:parse_request --show-failures
python3 evaluation.py holdout.json --parser request_parser:parse_request
```

## Environment variables

None required.

## Project layout

| File | Purpose |
|---|---|
| `request_parser.py` | The parser |
| `main.py` | FastAPI app |
| `index.html` | Front end |
| `evaluation.py` | Scores a parser against a labeled JSON file |
| `samples.json` | Dev set |
| `holdout.json`, `holdout.sha256` | Frozen holdout set and its checksum |
| `results/` | Saved scores |
| `tests/` | Unit tests |

## Roadmap

- **v1.1:** improve keyword coverage using the dev set, measured on a fresh holdout.
- **v2:** an LLM-based parser that returns the same JSON, scored by the same script.
- **v3:** compare accuracy, speed and cost between v1 and v2.
