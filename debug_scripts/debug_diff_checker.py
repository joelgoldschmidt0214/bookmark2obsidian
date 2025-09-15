"""
HTML内に存在する全リンクと、パーサーが抽出したリンクを比較し、
取りこぼしたリンク（差分）を特定するためのデバッグスクリプト。
"""

from pathlib import Path

from bs4 import BeautifulSoup

# 現在のパーサーをインポート
from core.parser import BookmarkParser

# --- 設定 ---
# poetry や uv の管理下にいれば、この設定は不要な場合があります
# import sys
# sys.path.append(str(Path(__file__).parent))

# ★★★ あなたのbookmarks.htmlファイルのパスを指定してください ★★★
BOOKMARKS_FILE = Path("./test_data/bookmarks_2025_09_06.html")


def get_all_links_from_html(html_content: str) -> set:
    """
    HTMLからhref属性を持つ全てのAタグのURLを単純に抽出する（あるべき姿）
    """
    print("--- HTML内の全リンクを抽出中... ---")
    soup = BeautifulSoup(html_content, "lxml")
    all_links = set()
    for a_tag in soup.find_all("a", href=True):
        if a_tag["href"]:
            all_links.add(a_tag["href"].strip())
    print(f"✔️ 全リンクの抽出完了: {len(all_links)}件")
    return all_links


def get_extracted_links_from_parser(html_content: str) -> set:
    """
    現在のパーサーを使って、抽出できたURLをすべて取得する（現実の姿）
    """
    print("\n--- パーサーによるブックマーク抽出を実行中... ---")
    # ★注意: この調査のため、事前にparser.pyのエラーチェックをコメントアウトしておくこと
    parser = BookmarkParser()
    bookmarks = parser.parse(html_content)
    extracted_links = {b.url.strip() for b in bookmarks}
    print(f"✔️ パーサーによる抽出完了: {len(extracted_links)}件")
    return extracted_links


def run_diff_check():
    """差分チェックを実行する"""
    print("--- 差分チェッカースクリプト実行 ---")

    if not BOOKMARKS_FILE.exists():
        print(f"❌エラー: ブックマークファイルが見つかりません: {BOOKMARKS_FILE}")
        return

    html_content = BOOKMARKS_FILE.read_text(encoding="utf-8")

    # 2つのリストを取得
    all_links_in_html = get_all_links_from_html(html_content)
    extracted_links = get_extracted_links_from_parser(html_content)

    # 差分を計算
    missing_links = all_links_in_html - extracted_links

    print("\n--- 差分チェック結果 ---")
    if not missing_links:
        print("✔️ 素晴らしい！すべてのリンクが抽出できています。")
    else:
        print(f"❌ {len(missing_links)}件のリンクが抽出されていませんでした。")
        print("--- 取りこぼされたURL一覧 ---")
        for i, url in enumerate(sorted(list(missing_links))):
            print(f"{i + 1:03d}: {url}")
        print("---------------------------------")
        print("\n上記のURLが、元のHTMLファイルのどのあたりにあるかを確認すると、")
        print("パーサーが見逃しているHTMLの構造パターンが特定できるはずです。")


if __name__ == "__main__":
    run_diff_check()
