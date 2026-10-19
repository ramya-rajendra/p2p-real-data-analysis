"""
Converts the BPI Challenge 2019 event log (.xes) into a CSV file.

Reads the XES file piece by piece, so it works on a normal laptop
(the file is ~730 MB and has 1.6 million events).

Usage (from the project root):
    python src/convert_xes.py
Input:  data/BPI_Challenge_2019.xes
Output: data/events.csv
"""

import csv
import time
import xml.etree.ElementTree as ET
from pathlib import Path

SRC = Path("data/BPI_Challenge_2019.xes")
OUT = Path("data/events.csv")

# case attributes we keep (XES key -> CSV column)
CASE_KEYS = {
    "concept:name": "case_id",
    "Purchasing Document": "purchasing_document",
    "Item Category": "item_category",
    "Item Type": "item_type",
    "Document Type": "document_type",
    "Vendor": "vendor",
    "Company": "company",
    "Spend area text": "spend_area",
    "GR-Based Inv. Verif.": "gr_based_inv_verif",
    "Goods Receipt": "goods_receipt",
}
# event attributes we keep
EVENT_KEYS = {
    "concept:name": "activity",
    "time:timestamp": "timestamp",
    "org:resource": "resource",
    "Cumulative net worth (EUR)": "net_worth_eur",
}
COLUMNS = list(CASE_KEYS.values()) + list(EVENT_KEYS.values())


def tag(el):
    return el.tag.split("}")[-1]


def main():
    if not SRC.exists():
        raise SystemExit(f"{SRC} not found. Download it first (see README).")

    start = time.time()
    n_events = n_cases = 0
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(COLUMNS)

        for _, el in ET.iterparse(SRC, events=("end",)):
            if tag(el) != "trace":
                continue
            case, events = {}, []
            for child in el:
                if tag(child) == "event":
                    ev = {EVENT_KEYS[a.get("key")]: a.get("value")
                          for a in child if a.get("key") in EVENT_KEYS}
                    events.append(ev)
                elif child.get("key") in CASE_KEYS:
                    case[CASE_KEYS[child.get("key")]] = child.get("value")
            for ev in events:
                row = {**case, **ev}
                writer.writerow([row.get(c, "") for c in COLUMNS])
            n_events += len(events)
            n_cases += 1
            el.clear()  # free memory as we go
            if n_cases % 50000 == 0:
                print(f"  {n_cases:,} cases, {n_events:,} events ...")

    print(f"Done in {time.time() - start:.0f}s: {n_cases:,} cases, {n_events:,} events -> {OUT}")


if __name__ == "__main__":
    main()
