"""
BeautifulSoupがHTMLをどのように解釈し、
木構造を構築したかを確認するためのデバッグスクリプト
"""

from pathlib import Path

from bs4 import BeautifulSoup

# --- 設定 ---
BOOKMARKS_FILE = Path("./test_data/test_bookmarks.html")


def inspect_tree():
    """HTMLファイルを読み込み、BeautifulSoupが構築したツリーを表示する"""
    print("--- BeautifulSoupツリー構造 確認スクリプト ---")

    if not BOOKMARKS_FILE.exists():
        print(f"❌エラー: ブックマークファイルが見つかりません: {BOOKMARKS_FILE}")
        return

    print(f"解析対象ファイル: {BOOKMARKS_FILE.resolve()}\n")

    html_content = BOOKMARKS_FILE.read_text(encoding="utf-8")

    # lxmlパーサーでHTMLを解析
    soup = BeautifulSoup(html_content, "lxml")

    # prettify()を使って、BeautifulSoupが認識しているツリー構造を出力
    print("--- BeautifulSoupが構築した木構造 (`soup.prettify()`) ---")
    print(soup.prettify())
    print("---------------------------------------------------------")


if __name__ == "__main__":
    inspect_tree()
