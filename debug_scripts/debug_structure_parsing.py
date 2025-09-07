#!/usr/bin/env python3
"""
ブックマーク構造解析の詳細デバッグ
なぜ4747個のAタグから122個しか抽出されないかを調査
"""

import os
import sys
from bs4 import BeautifulSoup
from urllib.parse import urlparse

# app.pyから必要なクラスをインポート
sys.path.append(".")
from app import BookmarkParser, Bookmark


def analyze_bookmark_structure(html_file_path):
    """ブックマーク構造解析の詳細分析"""

    print(f"📁 ブックマーク構造解析の詳細分析: {html_file_path}")

    # ファイル読み込み
    with open(html_file_path, "r", encoding="utf-8") as f:
        content = f.read()

    # BeautifulSoupで解析
    soup = BeautifulSoup(content, "html.parser")

    # 全Aタグを取得
    all_a_tags = soup.find_all("a")
    print(f"🔍 全Aタグ数: {len(all_a_tags)}")

    # ルートDLを取得
    root_dl = soup.find("dl")
    if not root_dl:
        print("❌ ルートDLエレメントが見つかりません")
        return

    print("✅ ルートDLエレメント発見")

    # BookmarkParserで解析
    parser = BookmarkParser()
    bookmarks = parser.parse_bookmarks(content)
    print(f"📚 BookmarkParserで解析されたブックマーク数: {len(bookmarks)}")

    print("\n" + "=" * 80)
    print("構造解析の詳細")
    print("=" * 80)

    # DL構造を詳しく分析
    analyze_dl_structure_detailed(root_dl, parser)

    # 実際に処理されるAタグと処理されないAタグを比較
    print("\n" + "=" * 80)
    print("処理されるAタグ vs 処理されないAタグの比較")
    print("=" * 80)

    compare_processed_vs_unprocessed(soup, parser)


def analyze_dl_structure_detailed(dl_element, parser, level=0, max_level=3):
    """DL構造の詳細分析（制限付き）"""
    if level > max_level:
        return

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

    print(f"{indent}📁 DLレベル {level}:")
    print(f"{indent}  - 全DTエレメント数: {len(all_dt_in_dl)}")
    print(f"{indent}  - ネストしたDL数: {len(nested_dls)}")
    print(f"{indent}  - ネストしたDTエレメント数: {len(nested_dt_elements)}")
    print(f"{indent}  - 直接のDTエレメント数: {len(direct_dt_elements)}")

    folder_count = 0
    bookmark_count = 0
    excluded_count = 0

    for i, dt in enumerate(direct_dt_elements):
        if i >= 10 and level == 0:  # ルートレベルでは最初の10個だけ詳細表示
            print(f"{indent}  ... (残り{len(direct_dt_elements) - i}個のDTエレメント)")
            break

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
                    analyze_dl_structure_detailed(
                        nested_dl, parser, level + 1, max_level
                    )
        else:
            # ブックマーク候補
            a_tag = dt.find("a")
            if a_tag:
                url = a_tag.get("href", "").strip()
                title = a_tag.get_text(strip=True)

                if url and title:
                    temp_bookmark = Bookmark(title=title, url=url, folder_path=[])

                    if parser._should_exclude_bookmark(temp_bookmark):
                        excluded_count += 1
                        if excluded_count <= 3:  # 最初の3個だけ表示
                            reason = get_exclusion_reason(parser, temp_bookmark)
                            print(
                                f"{indent}  ❌ 除外 {excluded_count}: {title[:30]}... ({reason})"
                            )
                    else:
                        bookmark_count += 1
                        if bookmark_count <= 3:  # 最初の3個だけ表示
                            print(
                                f"{indent}  ✅ 有効 {bookmark_count}: {title[:30]}..."
                            )

    print(
        f"{indent}📊 レベル {level} 集計: フォルダ={folder_count}, 有効ブックマーク={bookmark_count}, 除外={excluded_count}"
    )


def compare_processed_vs_unprocessed(soup, parser):
    """処理されるAタグと処理されないAタグの比較"""

    # BookmarkParserで実際に処理されるAタグを特定
    processed_a_tags = set()

    # ルートDLから開始して、実際に処理されるAタグを追跡
    root_dl = soup.find("dl")
    if root_dl:
        track_processed_a_tags(root_dl, processed_a_tags)

    # 全Aタグを取得
    all_a_tags = soup.find_all("a")

    print("📊 Aタグ処理状況:")
    print(f"  - 全Aタグ数: {len(all_a_tags)}")
    print(f"  - 構造解析で処理されるAタグ数: {len(processed_a_tags)}")
    print(
        f"  - 構造解析で処理されないAタグ数: {len(all_a_tags) - len(processed_a_tags)}"
    )

    # 処理されないAタグのサンプルを表示
    unprocessed_a_tags = [a for a in all_a_tags if a not in processed_a_tags]

    print("\n🔍 構造解析で処理されないAタグのサンプル (最初の20個):")
    for i, a_tag in enumerate(unprocessed_a_tags[:20]):
        url = a_tag.get("href", "").strip()
        title = a_tag.get_text(strip=True)

        # 親要素の情報を取得
        parent_info = get_parent_info(a_tag)

        print(f"  {i + 1:2d}. {title[:40]}...")
        print(f"      URL: {url[:60]}...")
        print(f"      親要素: {parent_info}")

    # 処理されるAタグのサンプルも表示
    print("\n✅ 構造解析で処理されるAタグのサンプル (最初の10個):")
    for i, a_tag in enumerate(list(processed_a_tags)[:10]):
        url = a_tag.get("href", "").strip()
        title = a_tag.get_text(strip=True)

        print(f"  {i + 1:2d}. {title[:40]}...")
        print(f"      URL: {url[:60]}...")


def track_processed_a_tags(dl_element, processed_a_tags):
    """DL構造で実際に処理されるAタグを追跡"""

    # このDLレベルのDTエレメントを取得
    all_dt_in_dl = dl_element.find_all("dt")

    # ネストしたDL内のDTエレメントを除外
    nested_dls = dl_element.find_all("dl")[1:]  # 最初のDLは自分自身なので除外
    nested_dt_elements = set()
    for nested_dl in nested_dls:
        nested_dt_elements.update(nested_dl.find_all("dt"))

    # このDLレベルのDTエレメントのみを処理
    direct_dt_elements = [dt for dt in all_dt_in_dl if dt not in nested_dt_elements]

    for dt in direct_dt_elements:
        next_sibling = dt.find_next_sibling()

        if next_sibling and next_sibling.name == "dd":
            # フォルダ - 再帰的に処理
            nested_dl = next_sibling.find("dl")
            if nested_dl:
                track_processed_a_tags(nested_dl, processed_a_tags)
        else:
            # ブックマーク
            a_tag = dt.find("a")
            if a_tag:
                processed_a_tags.add(a_tag)


def get_parent_info(a_tag):
    """Aタグの親要素情報を取得"""
    parent = a_tag.parent
    if parent:
        parent_name = parent.name
        parent_class = parent.get("class", [])
        return f"{parent_name}" + (f".{'.'.join(parent_class)}" if parent_class else "")
    return "不明"


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


if __name__ == "__main__":
    html_file = "bookmarks_2025_09_06.html"

    if not os.path.exists(html_file):
        print(f"❌ ファイルが見つかりません: {html_file}")
        sys.exit(1)

    analyze_bookmark_structure(html_file)
