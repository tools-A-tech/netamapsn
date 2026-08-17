#!/usr/bin/env python3
"""
サブスク棚 - データ更新スクリプト
JustWatch (GraphQL) を中心にデータを取得し、data/titles.json を更新する。
ブラウザなしで動作することを優先。必要に応じて後で Playwright を追加可能。
"""

import json
import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

try:
    import requests
except ImportError:
    print("requests が必要です: pip install requests")
    sys.exit(1)

# ========== 設定 ==========
OUTPUT_PATH = Path(__file__).parent.parent / "data" / "titles.json"
JUSTWATCH_GRAPHQL = "https://apis.justwatch.com/graphql"
COUNTRY = "JP"
LANGUAGE = "ja"

# JustWatch の provider コード（日本）
PROVIDERS = {
    "netflix": "nfx",
    "prime": "prv",   # Amazon Prime Video
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Content-Type": "application/json",
    "Accept": "application/json",
    "Origin": "https://www.justwatch.com",
    "Referer": "https://www.justwatch.com/",
}

JST = timezone(timedelta(hours=9))


def now_jst():
    return datetime.now(JST)


def fetch_justwatch_popular(provider_code: str, count: int = 30):
    """
    JustWatch の popularTitles 相当を取得する簡易版。
    実際のクエリは変更される可能性があるため、失敗時は空リストを返す。
    """
    # 注意: JustWatch の GraphQL スキーマは非公式で変更されやすい
    # ここでは骨格のみ。本番では実際に動くクエリに調整が必要。
    query = """
    query GetPopularTitles($country: Country!, $language: Language!, $first: Int!, $popularTitlesFilter: TitleFilter) {
      popularTitles(country: $country, filter: $popularTitlesFilter, first: $first, sortBy: POPULAR) {
        edges {
          node {
            id
            objectType
            objectId
            content(country: $country, language: $language) {
              title
              originalTitle
              fullPath
              scoring {
                imdbScore
              }
              posterUrl
              externalIds {
                imdbId
                tmdbId
              }
            }
          }
        }
      }
    }
    """

    variables = {
        "country": COUNTRY,
        "language": LANGUAGE,
        "first": count,
        "popularTitlesFilter": {
            "packages": [provider_code]
        }
    }

    try:
        resp = requests.post(
            JUSTWATCH_GRAPHQL,
            headers=HEADERS,
            json={"query": query, "variables": variables},
            timeout=30
        )
        if resp.status_code != 200:
            print(f"[JustWatch] HTTP {resp.status_code} for {provider_code}")
            return []

        data = resp.json()
        if "errors" in data:
            print(f"[JustWatch] GraphQL errors: {data['errors']}")
            return []

        edges = data.get("data", {}).get("popularTitles", {}).get("edges", [])
        results = []
        for edge in edges:
            node = edge.get("node", {})
            content = node.get("content") or {}
            results.append({
                "id": f"{provider_code}_{node.get('objectId')}",
                "title": content.get("title") or "不明",
                "original_title": content.get("originalTitle") or "",
                "type": "series" if node.get("objectType") == "SHOW" else "movie",
                "genres": [],  # 後で詳細取得で補完可能
                "year": None,
                "release_date": None,
                "added_date": now_jst().strftime("%Y-%m-%d"),
                "leaving_date": None,
                "poster": content.get("posterUrl"),
                "overview": "",
                "link": f"https://www.justwatch.com{content.get('fullPath', '')}" if content.get("fullPath") else "",
            })
        return results
    except Exception as e:
        print(f"[JustWatch] 取得失敗 ({provider_code}): {e}")
        return []


def create_fallback_data():
    """JustWatchが失敗した場合のフォールバック（既存JSONを維持しつつ更新日時だけ変える）"""
    if OUTPUT_PATH.exists():
        with open(OUTPUT_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        data["updated_at"] = now_jst().isoformat()
        data["note"] = "JustWatch取得に失敗したため前回データを維持"
        return data

    # 最低限の空データ
    return {
        "updated_at": now_jst().isoformat(),
        "note": "初期データ（取得失敗）",
        "services": {
            "netflix": {"name": "Netflix", "genres": [], "titles": []},
            "prime": {"name": "Amazonプライム", "genres": [], "titles": []},
            "psplus": {"name": "PS Plus", "genres": [], "titles": []}
        }
    }


def build_json(netflix_titles, prime_titles):
    """取得結果をサイト用JSONに整形"""
    def collect_genres(titles):
        gset = set()
        for t in titles:
            for g in t.get("genres") or []:
                gset.add(g)
        return sorted(gset)

    # PS Plus は別途実装が必要なので一旦プレースホルダ
    psplus = {
        "name": "PS Plus",
        "genres": ["アクション", "RPG"],
        "titles": []
    }

    data = {
        "updated_at": now_jst().isoformat(),
        "source": "justwatch",
        "services": {
            "netflix": {
                "name": "Netflix",
                "genres": collect_genres(netflix_titles),
                "titles": netflix_titles
            },
            "prime": {
                "name": "Amazonプライム",
                "genres": collect_genres(prime_titles),
                "titles": prime_titles
            },
            "psplus": psplus
        }
    }
    return data


def main():
    print(f"=== サブスク棚 データ更新開始 {now_jst().isoformat()} ===")

    netflix = fetch_justwatch_popular(PROVIDERS["netflix"], count=40)
    print(f"Netflix: {len(netflix)} 件取得")

    prime = fetch_justwatch_popular(PROVIDERS["prime"], count=40)
    print(f"Prime  : {len(prime)} 件取得")

    if not netflix and not prime:
        print("両方失敗したためフォールバックデータを使用")
        data = create_fallback_data()
    else:
        data = build_json(netflix, prime)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"書き出し完了: {OUTPUT_PATH}")
    print("=== 更新終了 ===")


if __name__ == "__main__":
    main()
