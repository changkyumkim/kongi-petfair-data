#!/usr/bin/env python3
"""K-Pet + Megazoo 전시 일정 스크레이퍼.

소스: https://k-pet.co.kr/information/exhibition-scheduled-all/
결과: events.json (17건 근처)
"""

from __future__ import annotations

import json
import re
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Optional, Tuple, List

import requests
from bs4 import BeautifulSoup

SOURCE_URL = "https://k-pet.co.kr/information/exhibition-scheduled-all/"
KST = timezone(timedelta(hours=9))
ROOT = Path(__file__).parent
SNAPS = ROOT / "snapshots"
OUT = ROOT / "events.json"

TITLE_RE = re.compile(r"케이펫페어|메가주")
# 9.11(금) – 13(일) / 2.27(금) – 3.1(일) / hyphen · en-dash · em-dash 모두 허용
DATE_RE = re.compile(
    r"(\d{1,2})\.(\d{1,2})\s*\([^)]+\)\s*[-–—]\s*(?:(\d{1,2})\.)?(\d{1,2})\s*\("
)
YEAR_RE = re.compile(r"(20\d\d)\s*전시일정")


def fetch_and_snapshot() -> str:
    r = requests.get(SOURCE_URL, headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
    r.raise_for_status()
    SNAPS.mkdir(parents=True, exist_ok=True)
    today = datetime.now(KST).date().isoformat()
    (SNAPS / f"{today}.html").write_text(r.text, encoding="utf-8")
    (SNAPS / "latest.html").write_text(r.text, encoding="utf-8")
    return r.text


def parse_year(html: str) -> int:
    m = YEAR_RE.search(html)
    if not m:
        raise RuntimeError("페이지에서 'YYYY 전시일정' 표기를 못 찾음")
    return int(m.group(1))


def slug_from_url(url: Optional[str]) -> Optional[str]:
    if not url:
        return None
    url = url.strip().rstrip("/")
    return url.rsplit("/", 1)[-1] if "/" in url else url


def fallback_id(title: str, start_iso: str) -> str:
    if "메가주" in title:
        base = "megazoo"
    else:
        base = "kpet_" + re.sub(r"\s+", "", title)
    return f"{base}_{start_iso}"


def find_cards(html: str) -> List[Tuple[str, "BeautifulSoup"]]:
    """카드 경계 = 각 <strong> 을 감싸는 가장 가까운 .fusion-column-wrapper."""
    soup = BeautifulSoup(html, "html.parser")
    cards = []
    for strong in soup.find_all("strong"):
        title = strong.get_text(strip=True)
        if not TITLE_RE.search(title):
            continue
        node = strong
        wrapper = None
        while node is not None:
            cls = node.get("class") if hasattr(node, "get") else None
            if cls and "fusion-column-wrapper" in cls:
                wrapper = node
                break
            node = node.parent
        if wrapper is not None:
            cards.append((title, wrapper))
    return cards


def extract_date_venue(wrapper) -> Optional[Tuple[str, str]]:
    """카드 내부 첫 번째 (날짜, 장소) <p>. PC판·모바일판이 중복이라 첫 번째만."""
    for p in wrapper.find_all("p"):
        text = p.get_text("\n", strip=True)
        if not DATE_RE.search(text):
            continue
        lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
        if len(lines) >= 2:
            return lines[0], lines[1]
    return None


def compute_range(date_str: str, year: int) -> Tuple[str, str]:
    m = DATE_RE.search(date_str)
    if not m:
        raise ValueError(f"날짜 파싱 실패: {date_str!r}")
    sm, sd, em, ed = m.group(1), m.group(2), m.group(3), m.group(4)
    start_m, start_d = int(sm), int(sd)
    end_m = int(em) if em else start_m
    end_d = int(ed)
    # start 연도는 페이지에서 읽은 연도로 고정.
    # end 는 end_month < start_month 일 때만 +1년.
    end_year = year + 1 if end_m < start_m else year
    start = date(year, start_m, start_d)
    end = date(end_year, end_m, end_d)
    return start.isoformat(), end.isoformat()


def extract_detail_url(wrapper) -> Optional[str]:
    a = wrapper.select_one("a.fusion-no-lightbox[href]")
    return a["href"].strip() if a else None


def extract_pre_reg_url(wrapper) -> Optional[str]:
    for a in wrapper.find_all("a", href=True):
        href = a["href"].strip()
        if "/registration/#/pre-reg/" in href:
            return href
    return None


def deadline_for(start_iso: str) -> str:
    d = date.fromisoformat(start_iso) - timedelta(days=1)
    dt = datetime(d.year, d.month, d.day, 23, 59, 0, tzinfo=KST)
    return dt.isoformat()


def main() -> int:
    html = fetch_and_snapshot()
    year = parse_year(html)
    cards = find_cards(html)

    seen = set()
    events = []
    for title, wrapper in cards:
        dv = extract_date_venue(wrapper)
        if not dv:
            continue
        date_str, venue = dv
        try:
            start_iso, end_iso = compute_range(date_str, year)
        except ValueError as e:
            print(f"skip (date parse): {title} — {e}", file=sys.stderr)
            continue

        detail = extract_detail_url(wrapper)
        slug = slug_from_url(detail) or fallback_id(title, start_iso)
        if slug in seen:
            continue
        seen.add(slug)

        pre_reg = extract_pre_reg_url(wrapper)
        events.append({
            "id": slug,
            "title": title,
            "start": start_iso,
            "end": end_iso,
            "venue": venue,
            "detail_url": detail,
            "pre_reg_url": pre_reg,
            "pre_reg_deadline": deadline_for(start_iso) if pre_reg else None,
        })

    if len(events) < 10:
        print(f"수집 실패: {len(events)}건", file=sys.stderr)
        return 1

    out = {
        "updated_at": datetime.now(KST).replace(microsecond=0).isoformat(),
        "source": SOURCE_URL,
        "count": len(events),
        "events": events,
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"OK: {len(events)}건 → {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
