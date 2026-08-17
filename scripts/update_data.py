#!/usr/bin/env python3
"""
サブスク棚 - データ更新スクリプト
Netflix / Amazonプライム を JustWatch から取得（最大約1800件）
PS Plus は構造を用意（データは今後拡充）
"""

import json
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

try:
    import requests
except ImportError:
    print("requests が必要です: pip install requests")
    sys.exit(1)

OUTPUT_PATH = Path(__file__).parent.parent / "data" / "titles.json"
JUSTWATCH_GRAPHQL = "https://apis.justwatch.com/graphql"
COUNTRY = "JP"
LANGUAGE = "ja"

PROVIDERS = {
    "netflix": "nfx",
    "prime": "prv",
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Content-Type": "application/json",
    "Accept": "application/json",
    "Origin": "https://www.justwatch.com",
    "Referer": "https://www.justwatch.com/",
}

JST = timezone(timedelta(hours=9))
MAX_TITLES = 1800
PAGE_SIZE = 100


def now_jst():
    return datetime.now(JST)


def fetch_page(provider_code, after_cursor=None):
    query = """
    query GetPopularTitles($country: Country!, $language: Language!, $first: Int!, $after: String, $filter: TitleFilter) {
      popularTitles(country: $country, filter: $filter, first: $first, after: $after, sortBy: POPULAR) {
        edges {
          node {
            id
            objectType
            objectId
            content(country: $country, language: $language) {
              title
              originalTitle
              fullPath
              posterUrl
              scoring { imdbScore }
              externalIds { tmdbId imdbId }
              genres { shortName translation(language: $language) }
            }
          }
          cursor
        }
        pageInfo {
          hasNextPage
          endCursor
        }
      }
    }
    """
    variables = {
        "country": COUNTRY,
        "language": LANGUAGE,
        "first": PAGE_SIZE,
        "filter": {"packages": [provider_code]},
    }
    if after_cursor:
        variables["after"] = after_cursor

    try:
        resp = requests.post(JUSTWATCH_GRAPHQL, headers=HEADERS,
                             json={"query": query, "variables": variables}, timeout=45)
        if resp.status_code != 200:
            print(f"  HTTP {resp.status_code}")
            return [], None, False
        data = resp.json()
        if "errors" in data:
            print(f"  GraphQL errors: {str(data['errors'])[:200]}")
            return [], None, False

        conn = data.get("data", {}).get("popularTitles") or {}
        edges = conn.get("edges") or []
        page_info = conn.get("pageInfo") or {}
        has_next = page_info.get("hasNextPage", False)
        end_cursor = page_info.get("endCursor")

        results = []
        for edge in edges:
            node = edge.get("node") or {}
            content = node.get("content") or {}
            genres = []
            for g in (content.get("genres") or []):
                name = g.get("translation") or g.get("shortName")
                if name:
                    genres.append(name)

            poster = content.get("posterUrl") or ""
            if poster.startswith("/"):
                poster = "https://images.justwatch.com" + poster

            results.append({
                "id": f"{provider_code}_{node.get('objectId')}",
                "title": content.get("title") or "不明",
                "original_title": content.get("originalTitle") or "",
                "type": "series" if node.get("objectType") == "SHOW" else "movie",
                "genres": genres,
                "platforms": [],
                "year": None,
                "release_date": None,
                "added_date": now_jst().strftime("%Y-%m-%d"),
                "leaving_date": None,
                "poster": poster,
                "overview": "",
                "link": ("https://www.justwatch.com" + content["fullPath"]) if content.get("fullPath") else "",
            })
        return results, end_cursor, has_next
    except Exception as e:
        print(f"  Exception: {e}")
        return [], None, False


def fetch_provider(provider_code, max_count=MAX_TITLES):
    print(f"[{provider_code}] 取得開始 (最大 {max_count})")
    all_titles = []
    cursor = None
    page = 0
    while len(all_titles) < max_count:
        page += 1
        titles, next_cursor, has_next = fetch_page(provider_code, cursor)
        if not titles:
            print(f"  page {page}: 0件 or failed")
            break
        all_titles.extend(titles)
        print(f"  page {page}: +{len(titles)} (total {len(all_titles)})")
        if not has_next or not next_cursor:
            break
        cursor = next_cursor
        time.sleep(0.35)
    # unique
    seen = set()
    unique = []
    for t in all_titles:
        if t["id"] not in seen:
            seen.add(t["id"])
            unique.append(t)
    print(f"[{provider_code}] 完了 {len(unique)} 件")
    return unique[:max_count]


def collect_genres(titles):
    g = set()
    for t in titles:
        for x in t.get("genres") or []:
            g.add(x)
    return sorted(g)


def main():
    print(f"=== 更新開始 {now_jst().isoformat()} ===")
    netflix = fetch_provider(PROVIDERS["netflix"])
    prime = fetch_provider(PROVIDERS["prime"])

    # PS Plus プレースホルダ（今後本格実装）
    # platforms と genres の両方を持てる構造にしておく
    psplus_titles = [
        # サンプル構造
        # {
        #   "id": "ps_sample1",
        #   "title": "サンプルゲーム",
        #   "type": "game",
        #   "genres": ["アクション"],
        #   "platforms": ["PS5"],
        #   "poster": null,
        #   "link": "https://store.playstation.com/",
        #   "tier": "Extra",
        #   "added_date": "2026-08-17"
        # }
    ]

    data = {
        "updated_at": now_jst().isoformat(),
        "source": "justwatch",
        "services": {
            "netflix": {
                "name": "Netflix",
                "genres": collect_genres(netflix),
                "titles": netflix
            },
            "prime": {
                "name": "Amazonプライム",
                "genres": collect_genres(prime),
                "titles": prime
            },
            "psplus": {
                "name": "PS Plus",
                "genres": [],
                "platforms": ["PS4", "PS5"],
                "titles": psplus_titles
            }
        }
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"書き出し完了 Netflix:{len(netflix)} Prime:{len(prime)} PS:{len(psplus_titles)}")
    print("=== 終了 ===")


if __name__ == "__main__":
    main()
