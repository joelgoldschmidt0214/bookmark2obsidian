import logging
from pathlib import Path

from core.parser import BookmarkParser

# --- 設定 ---
# poetry や uv の管理下にいれば、この設定は不要な場合があります
# import sys
# sys.path.append(str(Path(__file__).parent))

# ★★★ あなたのbookmarks.htmlファイルのパスを指定してください ★★★
# BOOKMARKS_FILE = Path("./test_data/bookmarks_2025_09_06.html")
BOOKMARKS_FILE = Path("./test_data/test_bookmarks.html")

# ログ設定（コンソールにデバッグメッセージを表示するため）
logging.basicConfig(level=logging.DEBUG, format="%(levelname)s:%(name)s:%(message)s")
logger = logging.getLogger(__name__)


def run_debug():
    """パーサーを直接実行してデバッグ情報を出力する"""
    print("--- 簡便デバッグスクリプト実行 ---")

    if not BOOKMARKS_FILE.exists():
        print(f"❌エラー: ブックマークファイルが見つかりません。パスを確認してください: {BOOKMARKS_FILE}")
        return

    print(f"解析対象ファイル: {BOOKMARKS_FILE.resolve()}")

    try:
        # パーサーをインスタンス化
        parser = BookmarkParser()

        # HTMLファイルを読み込む
        html_content = BOOKMARKS_FILE.read_text(encoding="utf-8")

        # ★★★ 新しいパーサーは内部的にフィルタリングまで行う ★★★
        bookmarks = parser.parse(html_content)

        print("\n--- 解析結果 ---")
        # フィルタリング後のブックマーク数を表示
        print(f"✔️ 最終的なブックマーク数: {len(bookmarks)}")

        # 統計情報を表示
        print("\n--- 統計情報 ---")
        stats = parser.get_statistics(bookmarks)
        print(f"  - 総ブックマーク数: {stats['total_bookmarks']}")
        print(f"  - ユニークドメイン数: {stats['unique_domains']}")
        print(f"  - フォルダ数: {stats['folder_count']}")

        if bookmarks:
            print("\n--- 抽出サンプル (最初の20件) ---")
            for i, b in enumerate(bookmarks[:20]):
                folder_path_str = "/".join(b.folder_path)
                print(f"{i + 1:02d}: [{folder_path_str}] > {b.title}")
        else:
            print("\n⚠️ ブックマークが1件も抽出されませんでした。パーサーのロジックを確認してください。")

    except Exception as e:
        logger.error(f"デバッグ中にエラーが発生しました: {e}", exc_info=True)


if __name__ == "__main__":
    run_debug()
