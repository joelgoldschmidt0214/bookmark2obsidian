#!/usr/bin/env python3
"""
新しいロジックでのブックマーク解析デバッグ
重複処理の確認と統計情報の取得
"""

import os
import sys
from bs4 import BeautifulSoup
from urllib.parse import urlparse
from collections import Counter

# app.pyから必要なクラスをインポート
sys.path.append(".")
from app import BookmarkParser, Bookmark


def analyze_new_logic(html_file_path):
    """新しいロジックでの解析結果を詳しく調べる"""

    print(f"📁 新しいロジックでの解析: {html_file_path}")

    # ファイル読み込み
    with open(html_file_path, "r", encoding="utf-8") as f:
        content = f.read()

    # BeautifulSoupで解析
    soup = BeautifulSoup(content, "html.parser")

    # 全Aタグを取得
    all_a_tags = soup.find_all("a")
    print(f"🔍 全Aタグ数: {len(all_a_tags)}")

    # BookmarkParserで解析
    parser = BookmarkParser()
    bookmarks = parser.parse_bookmarks(content)
    print(f"📚 解析されたブックマーク数: {len(bookmarks)}")

    # 重複チェック
    urls = [b.url for b in bookmarks]
    url_counts = Counter(urls)
    duplicates = {url: count for url, count in url_counts.items() if count > 1}

    print("\n📊 重複分析:")
    print(f"  - ユニークURL数: {len(url_counts)}")
    print(f"  - 重複URL数: {len(duplicates)}")
    print(
        f"  - 重複による余分なブックマーク数: {sum(duplicates.values()) - len(duplicates)}"
    )

    if duplicates:
        print("\n🔍 重複URLサンプル (上位10個):")
        for i, (url, count) in enumerate(
            sorted(duplicates.items(), key=lambda x: x[1], reverse=True)[:10]
        ):
            print(f"  {i + 1:2d}. {count}回: {url[:80]}...")

    # フォルダ別統計
    folder_stats = Counter()
    for bookmark in bookmarks:
        folder_path = (
            "/".join(bookmark.folder_path) if bookmark.folder_path else "(ルート)"
        )
        folder_stats[folder_path] += 1

    print("\n📂 フォルダ別統計 (上位20個):")
    for i, (folder, count) in enumerate(folder_stats.most_common(20)):
        print(f"  {i + 1:2d}. {count:4d}個: {folder}")

    # 除外統計
    excluded_count = 0
    exclusion_reasons = Counter()

    for a_tag in all_a_tags:
        url = a_tag.get("href", "").strip()
        title = a_tag.get_text(strip=True)

        if url and title:
            temp_bookmark = Bookmark(title=title, url=url, folder_path=[])
            if parser._should_exclude_bookmark(temp_bookmark):
                excluded_count += 1
                reason = get_exclusion_reason(parser, temp_bookmark)
                exclusion_reasons[reason] += 1

    print("\n❌ 除外統計:")
    print(f"  - 除外されたAタグ数: {excluded_count}")
    for reason, count in exclusion_reasons.most_common():
        print(f"  - {reason}: {count}個")

    # 処理効率の計算
    processed_rate = (len(bookmarks) / len(all_a_tags)) * 100 if all_a_tags else 0
    unique_rate = (len(url_counts) / len(all_a_tags)) * 100 if all_a_tags else 0

    print("\n📈 処理効率:")
    print(f"  - 処理率: {processed_rate:.1f}% ({len(bookmarks)}/{len(all_a_tags)})")
    print(f"  - ユニーク率: {unique_rate:.1f}% ({len(url_counts)}/{len(all_a_tags)})")


def get_exclusion_reason(parser, bookmark):
    """除外理由を特定"""
    if parser._is_domain_root_url(bookmark.url):
        return "ドメインルート"
    if not parser._is_valid_url(bookmark.url):
        return "無効URL"
    if bookmark.url in parser.excluded_urls:
        return "除外URL"

    try:
        parsed_url = urlparse(bookmark.url)
        domain = parsed_url.netloc.lower()
        if domain in parser.excluded_domains:
            return "除外ドメイン"
    except:
        return "URL解析エラー"

    return "不明"


def check_duplicate_processing():
    """重複処理の原因を調査"""
    print("\n🔍 重複処理の原因調査:")

    # 簡単なテストケースで確認
    test_html = """
    <dl>
        <dt><h3>フォルダ1</h3>
            <dl>
                <dt><a href="https://example.com/1">テスト1</a></dt>
                <dt><a href="https://example.com/2">テスト2</a></dt>
            </dl>
        </dt>
        <dt><a href="https://example.com/3">テスト3</a></dt>
    </dl>
    """

    parser = BookmarkParser()
    bookmarks = parser.parse_bookmarks(test_html)

    print("  テストケース結果:")
    print("  - 期待されるブックマーク数: 3")
    print(f"  - 実際のブックマーク数: {len(bookmarks)}")

    for i, bookmark in enumerate(bookmarks):
        folder_path = (
            "/".join(bookmark.folder_path) if bookmark.folder_path else "(ルート)"
        )
        print(f"    {i + 1}. {bookmark.title} (フォルダ: {folder_path})")


if __name__ == "__main__":
    html_file = "bookmarks_2025_09_06.html"

    if not os.path.exists(html_file):
        print(f"❌ ファイルが見つかりません: {html_file}")
        sys.exit(1)

    analyze_new_logic(html_file)
    check_duplicate_processing()
