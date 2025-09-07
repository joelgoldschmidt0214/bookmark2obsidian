#!/usr/bin/env python3
"""
テストケースの重複問題を詳しく調査
"""

import sys
from bs4 import BeautifulSoup

# app.pyから必要なクラスをインポート
sys.path.append(".")
from app import BookmarkParser


def debug_test_case():
    """テストケースの重複問題を調査"""

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

    print("🔍 テストケースの詳細分析:")
    print("=" * 60)

    # BeautifulSoupで解析
    soup = BeautifulSoup(test_html, "html.parser")

    # 構造を表示
    print("HTML構造:")
    print(soup.prettify())

    # DL構造を分析
    root_dl = soup.find("dl")
    all_dt_in_dl = root_dl.find_all("dt")

    print("\n📊 構造分析:")
    print(f"  - 全DTエレメント数: {len(all_dt_in_dl)}")

    for i, dt in enumerate(all_dt_in_dl):
        print(f"\n  DT {i + 1}:")
        print(f"    テキスト: {dt.get_text(strip=True)}")

        # 子要素を確認
        children = list(dt.children)
        child_tags = [
            child.name for child in children if hasattr(child, "name") and child.name
        ]
        print(f"    子要素: {child_tags}")

        # H3とAタグの確認
        h3 = dt.find("h3")
        a_tag = dt.find("a")
        internal_dl = dt.find("dl")

        if h3:
            print(f"    H3: {h3.get_text(strip=True)}")
        if a_tag:
            print(f"    A: {a_tag.get_text(strip=True)} → {a_tag.get('href')}")
        if internal_dl:
            print("    内部DL: あり")

        # 次の兄弟要素
        next_sibling = dt.find_next_sibling()
        if next_sibling:
            print(f"    次の兄弟: {next_sibling.name}")
        else:
            print("    次の兄弟: なし")

    # ネストしたDLの分析
    nested_dls = root_dl.find_all("dl")[1:]
    print(f"\n📂 ネストしたDL数: {len(nested_dls)}")

    for i, nested_dl in enumerate(nested_dls):
        nested_dts = nested_dl.find_all("dt")
        print(f"  ネストDL {i + 1}: {len(nested_dts)}個のDT")
        for j, nested_dt in enumerate(nested_dts):
            a_tag = nested_dt.find("a")
            if a_tag:
                print(f"    DT {j + 1}: {a_tag.get_text(strip=True)}")

    # BookmarkParserで解析
    print("\n📚 BookmarkParser解析結果:")
    parser = BookmarkParser()
    bookmarks = parser.parse_bookmarks(test_html)

    print(f"  解析されたブックマーク数: {len(bookmarks)}")
    for i, bookmark in enumerate(bookmarks):
        folder_path = (
            "/".join(bookmark.folder_path) if bookmark.folder_path else "(ルート)"
        )
        print(
            f"    {i + 1}. {bookmark.title} (フォルダ: {folder_path}) → {bookmark.url}"
        )


if __name__ == "__main__":
    debug_test_case()
