"""Bureau of Reclamation 24-Month Study connector.

Downloads the monthly 24-Month Study PDF and parses the Lake Mead (Hoover Dam) end-of-month elevation and storage
table. The study projects conditions; it does not by itself set shortage policy. Policy stays a scenario input.
"""

from __future__ import annotations

import datetime as dt
import io
import re
from dataclasses import dataclass

import pandas as pd
from pypdf import PdfReader

from aquaos.data.cache import DataCache
from aquaos.data.provenance import Provenance

CURRENT_URL = "https://www.usbr.gov/lc/region/g4000/24mo.pdf"
ARCHIVE_URL = "https://www.usbr.gov/lc/region/g4000/24mo/{year}/{mon}{yy}.pdf"
LICENSE = "U.S. Government work (Bureau of Reclamation); public domain in the U.S."

_ROW = re.compile(r"^(?P<mon>[A-Z][a-z]{2}) (?P<year>\d{4})((?: -?[\d.]+)+)\s*$")
_TITLE = re.compile(r"(?P<month>January|February|March|April|May|June|July|August|September|October|November|"
                    r"December) (?P<year>\d{4}) (?P<run>Most Probable|Min Probable|Max Probable) 24-Month Study")


@dataclass
class LakeMeadProjection:
    study: str
    data: pd.DataFrame  # index: month start; columns: elevation_ft, storage_kaf
    provenance: Provenance


def archive_url(year: int, month: int) -> str:
    mon = dt.date(year, month, 1).strftime("%b").upper()
    return ARCHIVE_URL.format(year=year, mon=mon, yy=str(year)[2:])


def pdf_text(pdf_bytes: bytes) -> str:
    return "\n".join(page.extract_text() for page in PdfReader(io.BytesIO(pdf_bytes)).pages)


def parse_lake_mead(text: str) -> tuple[str, pd.DataFrame]:
    """Return (study title, table) for the Hoover Dam – Lake Mead section of a 24-Month Study."""
    title_m = _TITLE.search(text)
    study = title_m.group(0) if title_m else "unknown 24-Month Study"
    start = text.find("Hoover Dam – Lake Mead")
    if start < 0:
        start = text.find("Hoover Dam - Lake Mead")
    if start < 0:
        raise ValueError("Lake Mead table not found in 24-Month Study text")
    end = text.find("Model Run ID", start)
    rows = []
    for line in text[start:end].splitlines():
        m = _ROW.match(line.strip())
        if not m:
            continue
        nums = [float(x) for x in line.split()[2:]]
        if len(nums) < 2:
            continue
        month = pd.Timestamp(f"{m.group('mon')} 1 {m.group('year')}")
        rows.append((month, nums[-2], nums[-1]))
    if not rows:
        raise ValueError("no Lake Mead rows parsed")
    df = pd.DataFrame(rows, columns=["month", "elevation_ft", "storage_kaf"]).set_index("month")
    return study, df


def fetch_lake_mead(url: str = CURRENT_URL, cache: DataCache | None = None,
                    refresh: bool = False) -> LakeMeadProjection:
    cache = cache or DataCache()
    name = "usbr/" + url.rsplit("/", 1)[-1]
    template = Provenance(
        title="Reclamation 24-Month Study (Lake Mead end-of-month projection)", kind="primary",
        source_url=url, retrieved=dt.date.today(), license=LICENSE,
        units={"elevation_ft": "ft above mean sea level", "storage_kaf": "thousand acre-feet"},
    )
    hit = cache.fetch(name, url, template, refresh=refresh)
    study, df = parse_lake_mead(pdf_text(hit.path.read_bytes()))
    prov = hit.provenance.model_copy(update={"source_document": study})
    return LakeMeadProjection(study, df, prov)
