#!/usr/bin/env python3
"""
ブックマーク除外の詳細分析
なぜ97.4%ものAタグが除外されているかを調査
"""

import os
import sys
from bs4 import BeautifulSoup
from urllib.parse import urlparse
from collections import Counter

# app.pyから必要なクラスをインポート
sys.path.append(".")
from app import BookmarkParser, Bookmark


def detailed_exclusion_analysis(html_file_path):
    """除外理由の詳細分析"""

    print(f"📁 除外理由詳細分析: {html_file_path}")

    # ファイル読み込み
    with open(html_file_path, "r", encoding="utf-8") as f:
        content = f.read()

    # BeautifulSoupで解析
    soup = BeautifulSoup(content, "html.parser")

    # 全Aタグを取得
    all_a_tags = soup.find_all("a")
    print(f"🔍 全Aタグ数: {len(all_a_tags)}")

    # 除外理由の統計
    exclusion_reasons = Counter()
    valid_count = 0

    parser = BookmarkParser()

    print("\n📊 除外理由分析:")
    print("=" * 60)

    for i, a_tag in enumerate(all_a_tags):
        url = a_tag.get("href", "").strip()
        title = a_tag.get_text(strip=True)

        if not url:
            exclusion_reasons["URLなし"] += 1
            continue

        if not title:
            exclusion_reasons["タイトルなし"] += 1
            continue

        # 仮のブックマークオブジェクトを作成
        temp_bookmark = Bookmark(title=title, url=url, folder_path=[])

        # 除外チェック
        if parser._is_domain_root_url(temp_bookmark.url):
            exclusion_reasons["ドメインルート"] += 1
        elif not parser._is_valid_url(temp_bookmark.url):
            exclusion_reasons["無効URL"] += 1
        elif temp_bookmark.url in parser.excluded_urls:
            exclusion_reasons["除外URL"] += 1
        else:
            try:
                parsed_url = urlparse(temp_bookmark.url)
                domain = parsed_url.netloc.lower()
                if domain in parser.excluded_domains:
                    exclusion_reasons["除外ドメイン"] += 1
                else:
                    valid_count += 1
            except:
                exclusion_reasons["URL解析エラー"] += 1

    # 結果表示
    print(f"✅ 有効なブックマーク: {valid_count}")
    print(f"❌ 除外されたブックマーク: {len(all_a_tags) - valid_count}")
    print(
        f"📊 除外率: {((len(all_a_tags) - valid_count) / len(all_a_tags) * 100):.1f}%"
    )

    print("\n📋 除外理由別統計:")
    for reason, count in exclusion_reasons.most_common():
        percentage = (count / len(all_a_tags)) * 100
        print(f"  {reason}: {count:,}件 ({percentage:.1f}%)")

    # ドメインルート除外の詳細分析
    print("\n🔍 ドメインルート除外の詳細分析:")
    print("=" * 60)

    domain_root_samples = []
    for a_tag in all_a_tags:
        url = a_tag.get("href", "").strip()
        title = a_tag.get_text(strip=True)

        if url and title:
            temp_bookmark = Bookmark(title=title, url=url, folder_path=[])
            if parser._is_domain_root_url(temp_bookmark.url):
                domain_root_samples.append((title, url))
                if len(domain_root_samples) >= 20:
                    break

    print("ドメインルートとして除外されたサンプル (最初の20件):")
    for i, (title, url) in enumerate(domain_root_samples, 1):
        print(f"  {i:2d}. {title[:40]}... → {url[:60]}...")

    # 無効URLの詳細分析
    print("\n🔍 無効URL除外の詳細分析:")
    print("=" * 60)

    invalid_url_samples = []
    for a_tag in all_a_tags:
        url = a_tag.get("href", "").strip()
        title = a_tag.get_text(strip=True)

        if url and title:
            temp_bookmark = Bookmark(title=title, url=url, folder_path=[])
            if not parser._is_valid_url(temp_bookmark.url):
                invalid_url_samples.append((title, url))
                if len(invalid_url_samples) >= 10:
                    break

    print("無効URLとして除外されたサンプル (最初の10件):")
    for i, (title, url) in enumerate(invalid_url_samples, 1):
        print(f"  {i:2d}. {title[:40]}... → {url[:60]}...")


def analyze_domain_root_logic():
    """ドメインルート判定ロジックの分析"""
    print("\n🔧 ドメインルート判定ロジックの分析:")
    print("=" * 60)

    parser = BookmarkParser()

    # テストケース
    test_urls = [
        "https://www.google.com/",
        "https://www.google.com",
        "https://www.google.com/search?q=test",
        "https://github.com/",
        "https://github.com",
        "https://github.com/user/repo",
        "https://example.com/page.html",
        "https://example.com/?param=value",
        "https://example.com/#section",
        "https://book.dmm.com/",
        "https://book.dmm.com",
        "https://book.dmm.com/detail/b123456789",
    ]

    print("テストURL判定結果:")
    for url in test_urls:
        is_root = parser._is_domain_root_url(url)
        parsed = urlparse(url)
        path = parsed.path.strip("/")
        print(f"  {'✅' if not is_root else '❌'} {url}")
        print(
            f"      パス: '{path}', クエリ: '{parsed.query}', フラグメント: '{parsed.fragment}'"
        )
        print(f"      ドメインルート判定: {is_root}")


if __name__ == "__main__":
    html_file = "bookmarks_2025_09_06.html"

    if not os.path.exists(html_file):
        print(f"❌ ファイルが見つかりません: {html_file}")
        sys.exit(1)

    detailed_exclusion_analysis(html_file)
    analyze_domain_root_logic()
