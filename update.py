#!/usr/bin/env python3
"""Daily update for kcommandbanned.szymonrichert.pl.

  update.py prices   fetch today's Scryfall prices, upsert into site/prices.json,
                     refresh card fields in site/data.json
  update.py check    validate site/data.json and site/prices.json
  update.py deploy   apply k8s/manifests.yaml, rebuild the site ConfigMap,
                     restart nginx, verify the live page serves the local data
  update.py all      prices + check + deploy

Only touches namespace kcommandbanned. Stdlib only.
"""

import datetime as dt
import json
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent
SITE = ROOT / "site"
DATA = SITE / "data.json"
PRICES = SITE / "prices.json"
MANIFESTS = ROOT / "k8s" / "manifests.yaml"
NS = "kcommandbanned"
URL = "https://kcommandbanned.szymonrichert.pl"
SCRYFALL_ID = "92585587-cfdc-406a-9114-4f6dd8802c37"
UA = {"User-Agent": "kcommandbanned/1.0", "Accept": "application/json"}


def get_json(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def num(v):
    return float(v) if v not in (None, "") else None


def today():
    return dt.datetime.now(ZoneInfo("Europe/Warsaw")).date().isoformat()


def prices():
    card = get_json(f"https://api.scryfall.com/cards/{SCRYFALL_ID}")
    p = card["prices"]
    row = {
        "date": today(),
        "usd": num(p.get("usd")),
        "eur": num(p.get("eur")),
        "tix": num(p.get("tix")),
        "source": "scryfall",
    }
    hist = json.loads(PRICES.read_text())
    rows = [r for r in hist["history"] if r["date"] != row["date"]]
    rows.append(row)
    rows.sort(key=lambda r: r["date"])
    hist["history"] = rows
    PRICES.write_text(json.dumps(hist, indent=1) + "\n")

    data = json.loads(DATA.read_text())
    data["card"].update(
        {
            "image": card["image_uris"]["normal"],
            "scryfall_uri": card["scryfall_uri"].split("?")[0],
            "prices": {k: row[k] for k in ("usd", "eur", "tix")},
            "legalities": {
                k: v for k, v in card["legalities"].items() if v != "not_legal"
            },
            "game_changer": card.get("game_changer"),
        }
    )
    DATA.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n")
    print(f"prices: {row}")


def check():
    data = json.loads(DATA.read_text())
    hist = json.loads(PRICES.read_text())["history"]
    errs = []
    for k in ("updated", "announcement", "estimates", "summary", "sources", "card"):
        if k not in data:
            errs.append(f"data.json missing '{k}'")
    a = data.get("announcement", {})
    if not a.get("date") or not a.get("source_url"):
        errs.append("announcement needs date and source_url")
    for e in data.get("estimates", []):
        if not (0 <= e.get("percent", -1) <= 100) or not e.get("format"):
            errs.append(f"bad estimate {e}")
    for s in data.get("sources", []):
        miss = [
            k for k in ("title", "source", "url", "date", "takeaway") if not s.get(k)
        ]
        if miss:
            errs.append(f"source {s.get('url')} missing {miss}")
    if not 6 <= len(data.get("sources", [])) <= 10:
        errs.append("sources must have 6-10 entries")
    text = json.dumps({k: data.get(k) for k in ("estimates", "summary", "sources")})
    if "\\u" in text:
        errs.append("estimates/summary/sources must be plain ASCII")
    dates = [r["date"] for r in hist]
    if dates != sorted(set(dates)):
        errs.append("prices.json history not sorted/unique by date")
    if errs:
        sys.exit("check failed:\n  " + "\n  ".join(errs))
    print(
        f"check: ok ({len(data['sources'])} sources, {len(hist)} price rows, last {dates[-1]})"
    )


def kubectl(*args, stdin=None):
    return subprocess.run(
        ["kubectl", *args], input=stdin, check=True, capture_output=True, text=True
    ).stdout


def deploy():
    check()
    data = json.loads(DATA.read_text())
    data["deployed_at"] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    DATA.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n")
    print(kubectl("apply", "-f", str(MANIFESTS)).strip())
    cm = kubectl(
        "-n",
        NS,
        "create",
        "configmap",
        "site",
        f"--from-file={SITE}",
        "--dry-run=client",
        "-o",
        "yaml",
    )
    print(kubectl("apply", "-f", "-", stdin=cm).strip())
    kubectl("-n", NS, "rollout", "restart", "deployment/web")
    kubectl("-n", NS, "rollout", "status", "deployment/web", "--timeout=180s")
    local = data["deployed_at"]
    for _ in range(12):
        try:
            req = urllib.request.Request(f"{URL}/data.json?t={time.time()}", headers=UA)
            with urllib.request.urlopen(req, timeout=15) as r:
                live = json.load(r).get("deployed_at")
            if live == local:
                print(f"verify: {URL} serves deployed_at={live}")
                return
            print(f"verify: live deployed_at={live}, want {local}, retrying")
        except Exception as e:  # cert issuance or ingress not ready yet
            print(f"verify: {e}, retrying")
        time.sleep(10)
    sys.exit("verify failed: live page does not serve local data.json")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "all"
    if cmd in ("prices", "all"):
        prices()
    if cmd == "check":
        check()
    if cmd in ("deploy", "all"):
        deploy()
