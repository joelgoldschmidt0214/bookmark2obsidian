#!/usr/bin/env python3
"""
ブックマーク解析のデバッグスクリプト
4747件のAタグが122件しか解析対象にならない理由を調査
"""

import os
import sys
from bs4 import BeautifulSoup
from urllib.parse import urlparse

# app.pyから必要なクラスをインポート
sys.path.append(".")
from app import BookmarkParser, Bookmark


def analyze_bookmark_file(html_file_path):
    """ブックマークファイルの詳細解析"""

    print(f"📁 ファイル解析開始: {html_file_path}")

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

    print("\n" + "=" * 60)
    print("詳細解析")
    print("=" * 60)

    # 各Aタグを詳しく調べる
    valid_bookmarks = 0
    excluded_by_structure = 0
    excluded_by_filter = 0

    # ルートDLを取得
    root_dl = soup.find("dl")
    if not root_dl:
        print("❌ ルートDLエレメントが見つかりません")
        return

    print("✅ ルートDLエレメント発見")

    # 構造解析
    print("\n📂 ブックマーク構造解析:")
    analyze_structure(root_dl, parser, level=0)

    print("\n📊 解析結果サマリー:")
    print(f"  - 全Aタグ数: {len(all_a_tags)}")
    print(f"  - 解析されたブックマーク数: {len(bookmarks)}")
    print(
        f"  - 除外率: {((len(all_a_tags) - len(bookmarks)) / len(all_a_tags) * 100):.1f}%"
    )


def analyze_structure(dl_element, parser, level=0):
    """DL構造を再帰的に解析"""
    indent = "  " * level

    # このDLレベルのDTエレメントを取得
    all_dt_in_dl = dl_element.find_all("dt")

    # ネストしたDL内のDTエレメントを除外
    nested_dls = dl_element.find_all("dl")[1:]  # 最初のDLは自分自身なので除外
    nested_dt_elements = set()
    for nested_dl in nested_dls:
        nested_dt_elements.update(nested_dl.find_all("dt"))

    # このDLレベルのDTエレメントのみを処理
    direct_dt_elements = [dt for dt in all_dt_in_dl if dt not in nested_dt_elements]

    print(f"{indent}📁 DLレベル {level}: {len(direct_dt_elements)}個のDTエレメント")

    folder_count = 0
    bookmark_count = 0
    excluded_count = 0

    for i, dt in enumerate(direct_dt_elements):
        next_sibling = dt.find_next_sibling()

        if next_sibling and next_sibling.name == "dd":
            # フォルダ
            h3 = dt.find("h3")
            if h3:
                folder_name = h3.get_text(strip=True)
                folder_count += 1
                print(f"{indent}  📂 フォルダ {folder_count}: {folder_name}")

                # 再帰的に処理
                nested_dl = next_sibling.find("dl")
                if nested_dl:
                    analyze_structure(nested_dl, parser, level + 1)
        else:
            # ブックマーク候補
            a_tag = dt.find("a")
            if a_tag:
                url = a_tag.get("href", "").strip()
                title = a_tag.get_text(strip=True)

                # 除外チェック
                if url and title:
                    # 仮のブックマークオブジェクトを作成
                    temp_bookmark = Bookmark(title=title, url=url, folder_path=[])

                    if parser._should_exclude_bookmark(temp_bookmark):
                        excluded_count += 1
                        reason = get_exclusion_reason(parser, temp_bookmark)
                        if (
                            level == 0 and excluded_count <= 5
                        ):  # ルートレベルの最初の5個だけ表示
                            print(
                                f"{indent}  ❌ 除外 {excluded_count}: {title[:50]}... ({reason})"
                            )
                    else:
                        bookmark_count += 1
                        if (
                            level == 0 and bookmark_count <= 5
                        ):  # ルートレベルの最初の5個だけ表示
                            print(
                                f"{indent}  ✅ 有効 {bookmark_count}: {title[:50]}..."
                            )

    print(
        f"{indent}📊 レベル {level} 集計: フォルダ={folder_count}, 有効ブックマーク={bookmark_count}, 除外={excluded_count}"
    )


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


def sample_a_tags(html_file_path, sample_size=20):
    """Aタグのサンプルを表示"""
    print(f"\n🔍 Aタグサンプル解析 (最初の{sample_size}個)")
    print("=" * 60)

    with open(html_file_path, "r", encoding="utf-8") as f:
        content = f.read()

    soup = BeautifulSoup(content, "html.parser")
    all_a_tags = soup.find_all("a")

    parser = BookmarkParser()

    for i, a_tag in enumerate(all_a_tags[:sample_size]):
        url = a_tag.get("href", "").strip()
        title = a_tag.get_text(strip=True)

        print(f"\n{i + 1:2d}. タイトル: {title[:60]}...")
        print(f"    URL: {url[:80]}...")

        if url and title:
            temp_bookmark = Bookmark(title=title, url=url, folder_path=[])
            if parser._should_exclude_bookmark(temp_bookmark):
                reason = get_exclusion_reason(parser, temp_bookmark)
                print(f"    ❌ 除外理由: {reason}")
            else:
                print("    ✅ 有効")
        else:
            print("    ❌ URLまたはタイトルが空")


if __name__ == "__main__":
    html_file = "bookmarks_2025_09_06.html"

    if not os.path.exists(html_file):
        print(f"❌ ファイルが見つかりません: {html_file}")
        sys.exit(1)

    analyze_bookmark_file(html_file)
    sample_a_tags(html_file)
