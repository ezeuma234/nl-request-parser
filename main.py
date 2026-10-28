"""FastAPI wrapper around the request parser.

Run locally:   uvicorn main:app --reload
Docs page:     http://127.0.0.1:8000/docs
"""
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from request_parser import parse_request

app = FastAPI(title="NL Request Parser", version="1.0.0")

# Open CORS so a separate front end can call the API. Restrict allow_origins
# to your real front-end URL once it is hosted.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ParseIn(BaseModel):
    text: str = Field(..., max_length=2000, examples=["I need 3 bags of rice from Mile 3 by evening"])


class Item(BaseModel):
    name: str
    quantity: Optional[int] = None
    unit: Optional[str] = None


class ParseOut(BaseModel):
    task_type: str
    items: List[Item]
    pickup_location: Optional[str] = None
    dropoff_location: Optional[str] = None
    delivery_required: bool
    deadline: Optional[str] = None
    confidence: float
    missing: List[str]


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/parse", response_model=ParseOut)
def parse(body: ParseIn):
    if not body.text.strip():
        raise HTTPException(status_code=422, detail="text must not be empty")
    return parse_request(body.text)


from pathlib import Path  # noqa: E402

from fastapi.responses import FileResponse  # noqa: E402


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(Path(__file__).parent / "index.html")
