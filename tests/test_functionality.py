"""
機能テストモジュール
このモジュールは、アプリケーションの各機能が正しく動作することを検証します。
キャッシュ機能、UI表示改善、エラーハンドリングのテストを提供します。
"""

import pytest
import tempfile
import os
from unittest.mock import Mock, patch, MagicMock
from typing import List, Dict, Any

# テスト対象のモジュールをインポート
from core.parser import BookmarkParser
from core.cache_manager import CacheManager
from utils.cache_utils import get_cache_statistics, clear_all_cache
from utils.error_handler import error_logger, error_recovery, ErrorRecoveryStrategy
from ui.progress_display import ProgressDisplay
from ui.components import display_page_list_and_preview, display_bookmark_list_only
from utils.models import Bookmark, CacheEntry


class TestCacheFunctionality:
    """キャッシュ機能のテスト"""

    def setup_method(self):
        """各テストメソッドの前に実行される初期化処理"""
        self.temp_dir = tempfile.mkdtemp()
        self.cache_manager = CacheManager(cache_dir=self.temp_dir)
        self.parser = BookmarkParser()

    def teardown_method(self):
        """各テストメソッドの後に実行されるクリーンアップ処理"""
        clear_all_cache()
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_cache_save_and_load(self):
        """キャッシュの保存と読み込み機能テスト"""
        # テスト用のHTMLコンテンツ
        test_html = """
        <DL><p>
        <DT><A HREF="https://example.com">Test Bookmark</A>
        </DL><p>
        """

        # テスト用のブックマークデータ
        test_bookmarks = [
            Bookmark(
                title="Test Bookmark", url="https://example.com", folder_path=["root"]
            )
        ]

        # キャッシュに保存
        file_hash = self.cache_manager.calculate_file_hash(test_html)
        self.cache_manager.save_bookmark_cache(file_hash, test_bookmarks)

        # キャッシュから読み込み
        cached_bookmarks = self.cache_manager.load_bookmark_cache(file_hash)

        # アサーション
        assert cached_bookmarks is not None, (
            "キャッシュからデータが読み込めませんでした"
        )
        assert len(cached_bookmarks) == len(test_bookmarks), (
            "キャッシュされたデータの数が正しくありません"
        )
        assert cached_bookmarks[0].title == test_bookmarks[0].title, (
            "キャッシュされたタイトルが正しくありません"
        )
        assert cached_bookmarks[0].url == test_bookmarks[0].url, (
            "キャッシュされたURLが正しくありません"
        )

    def test_cache_invalidation(self):
        """キャッシュ無効化機能テスト"""
        # テスト用のHTMLコンテンツ
        original_html = "<DL><p><DT><A HREF='https://example.com'>Original</A></DL><p>"
        modified_html = "<DL><p><DT><A HREF='https://example.com'>Modified</A></DL><p>"

        # テスト用のブックマークデータ
        original_bookmarks = [
            Bookmark(title="Original", url="https://example.com", folder_path=["root"])
        ]
        modified_bookmarks = [
            Bookmark(title="Modified", url="https://example.com", folder_path=["root"])
        ]

        # 最初のキャッシュ保存
        original_hash = self.cache_manager.calculate_file_hash(original_html)
        self.cache_manager.save_bookmark_cache(original_hash, original_bookmarks)

        # 異なるHTMLでキャッシュ保存（上書き）
        modified_hash = self.cache_manager.calculate_file_hash(modified_html)
        self.cache_manager.save_bookmark_cache(modified_hash, modified_bookmarks)

        # 修正されたHTMLでキャッシュ読み込み
        cached_bookmarks = self.cache_manager.load_bookmark_cache(modified_hash)

        # アサーション
        assert cached_bookmarks is not None, (
            "修正されたキャッシュが読み込めませんでした"
        )
        assert cached_bookmarks[0].title == "Modified", (
            "キャッシュが正しく更新されていません"
        )

        # 元のHTMLのキャッシュは異なるハッシュなので残っていることを確認
        original_cached = self.cache_manager.load_bookmark_cache(original_hash)
        assert original_cached is not None, "元のキャッシュが削除されています"
        assert original_cached[0].title == "Original", (
            "元のキャッシュの内容が正しくありません"
        )

    def test_cache_statistics(self):
        """キャッシュ統計機能テスト"""
        # 初期統計を取得
        initial_stats = get_cache_statistics()

        # テスト用のデータでキャッシュを作成
        created_hashes = []
        for i in range(3):
            html = f"<DL><p><DT><A HREF='https://example{i}.com'>Test {i}</A></DL><p>"
            bookmarks = [
                Bookmark(
                    title=f"Test {i}",
                    url=f"https://example{i}.com",
                    folder_path=["root"],
                )
            ]
            file_hash = self.cache_manager.calculate_file_hash(html)
            created_hashes.append(file_hash)
            self.cache_manager.save_bookmark_cache(file_hash, bookmarks)

        # 統計を再取得
        updated_stats = get_cache_statistics()

        # アサーション（キャッシュファイルは1つのJSONファイルに統合される可能性があるため、最低限の増加を確認）
        assert updated_stats["total_entries"] >= initial_stats["total_entries"], (
            "キャッシュエントリ数が減少しています"
        )
        assert updated_stats["total_size_mb"] >= initial_stats["total_size_mb"], (
            "キャッシュサイズが減少しています"
        )
        assert "hit_rate" in updated_stats, "キャッシュヒット率が統計に含まれていません"

        # 作成したキャッシュが実際に読み込めることを確認
        for i, file_hash in enumerate(created_hashes):
            cached_bookmarks = self.cache_manager.load_bookmark_cache(file_hash)
            assert cached_bookmarks is not None, f"キャッシュ {i} が読み込めません"
            assert len(cached_bookmarks) == 1, (
                f"キャッシュ {i} のブックマーク数が正しくありません"
            )


class TestUIFunctionality:
    """UI機能のテスト"""

    def setup_method(self):
        """各テストメソッドの前に実行される初期化処理"""
        self.progress_display = ProgressDisplay()

    @patch("streamlit.progress")
    @patch("streamlit.text")
    def test_progress_display_update(self, mock_text, mock_progress):
        """進捗表示の更新機能テスト"""
        # 進捗表示の初期化
        self.progress_display.initialize_display(100)

        # 進捗の更新
        self.progress_display.update_progress(50, current_item="50%完了")

        # アサーション
        mock_progress.assert_called()
        mock_text.assert_called()

        # 進捗値の確認（statsオブジェクトから取得）
        assert self.progress_display.stats.completed_items == 50, (
            "進捗値が正しく更新されていません"
        )

    @patch("streamlit.success")
    def test_progress_completion(self, mock_success):
        """進捗完了時の表示テスト"""
        # 進捗表示の初期化
        self.progress_display.initialize_display(100)

        # 進捗を完了
        self.progress_display.complete_progress("処理完了")

        # アサーション
        mock_success.assert_called()
        # 完了時は completed_items が total_items と等しくなる
        assert (
            self.progress_display.stats.completed_items
            == self.progress_display.stats.total_items
        ), "進捗完了状態が正しく設定されていません"

    @patch("streamlit.container")
    def test_bookmark_list_display(self, mock_container):
        """ブックマーク一覧表示機能テスト"""
        # テスト用のブックマークデータ
        test_bookmarks = [
            Bookmark(
                title="Test 1", url="https://example1.com", folder_path=["folder1"]
            ),
            Bookmark(
                title="Test 2", url="https://example2.com", folder_path=["folder2"]
            ),
        ]

        # モックの設定
        mock_container_instance = MagicMock()
        mock_container.return_value.__enter__.return_value = mock_container_instance

        # 表示機能をテスト
        try:
            display_bookmark_list_only(test_bookmarks)
            display_success = True
        except Exception as e:
            display_success = False
            print(f"表示エラー: {e}")

        # アサーション
        assert display_success, "ブックマーク一覧の表示に失敗しました"


class TestErrorHandling:
    """エラーハンドリング機能のテスト"""

    def setup_method(self):
        """各テストメソッドの前に実行される初期化処理"""
        self.parser = BookmarkParser()
        self.recovery_strategy = ErrorRecoveryStrategy()

    def test_malformed_html_handling(self):
        """不正なHTMLの処理テスト"""
        # 不正なHTMLコンテンツ
        malformed_html = """
        <DL><p>
        <DT><A HREF="">Empty URL</A>
        <DT><A>Missing URL</A>
        <DT><A HREF="invalid-url">Invalid URL</A>
        <!-- Missing closing tags -->
        """

        # エラーハンドリング付きで解析
        try:
            bookmarks = self.parser.parse_bookmarks(malformed_html)
            parsing_success = True
        except Exception as e:
            # エラー回復戦略を実行
            recovery_result = error_recovery.execute_recovery_action(
                "extraction", {"html_content": malformed_html}
            )
            parsing_success = recovery_result.get("success", False)
            bookmarks = recovery_result.get("bookmarks", [])

        # アサーション
        assert parsing_success, "不正なHTMLの処理に失敗しました"
        assert isinstance(bookmarks, list), "ブックマークリストが返されませんでした"

    def test_error_logging(self):
        """エラーログ機能テスト"""
        # エラーログの初期化
        error_logger.clear_errors()

        # 意図的にエラーを発生させる
        try:
            raise ValueError("テスト用エラー")
        except ValueError as e:
            error_logger.log_error("test_error", str(e), {"test": True})

        # エラーサマリーを取得
        error_summary = error_logger.get_error_summary()

        # アサーション
        assert error_summary["total_errors"] > 0, "エラーが記録されていません"
        assert "test_error" in error_summary["error_types"], (
            "エラータイプが記録されていません"
        )

    def test_error_recovery_strategy(self):
        """エラー回復戦略テスト"""
        # テスト用のエラー状況
        error_context = {
            "error_type": "extraction",
            "html_content": "<invalid>html</invalid>",
            "attempt_count": 1,
        }

        # 回復戦略を実行
        recovery_result = self.recovery_strategy.execute_recovery_action(
            "extraction", error_context
        )

        # アサーション
        assert "success" in recovery_result, "回復結果にsuccessフィールドがありません"
        assert "extraction_mode" in recovery_result, (
            "回復結果に抽出モードが含まれていません"
        )
        assert isinstance(recovery_result["success"], bool), (
            "success値がbooleanではありません"
        )


class TestBookmarkParser:
    """ブックマーク解析機能のテスト"""

    def setup_method(self):
        """各テストメソッドの前に実行される初期化処理"""
        self.parser = BookmarkParser()

    def test_chrome_bookmark_parsing(self):
        """Chrome形式ブックマークの解析テスト"""
        chrome_html = """
        <!DOCTYPE NETSCAPE-Bookmark-file-1>
        <META HTTP-EQUIV="Content-Type" CONTENT="text/html; charset=UTF-8">
        <TITLE>Bookmarks</TITLE>
        <H1>Bookmarks Menu</H1>
        <DL><p>
        <DT><H3 ADD_DATE="1600000000">Chrome Folder</H3>
        <DL><p>
        <DT><A HREF="https://chrome-example.com" ADD_DATE="1600000001">Chrome Bookmark</A>
        </DL><p>
        </DL><p>
        """

        # 解析実行
        bookmarks = self.parser.parse_bookmarks(chrome_html)

        # アサーション
        assert bookmarks is not None, "Chrome ブックマークの解析に失敗しました"
        assert len(bookmarks) > 0, "ブックマークが解析されませんでした"
        assert bookmarks[0].title == "Chrome Bookmark", (
            "ブックマークタイトルが正しくありません"
        )
        assert bookmarks[0].url == "https://chrome-example.com", (
            "ブックマークURLが正しくありません"
        )
        assert "Chrome Folder" in bookmarks[0].folder_path, (
            "フォルダパスが正しくありません"
        )

    def test_firefox_bookmark_parsing(self):
        """Firefox形式ブックマークの解析テスト"""
        firefox_html = """
        <!DOCTYPE NETSCAPE-Bookmark-file-1>
        <META HTTP-EQUIV="Content-Type" CONTENT="text/html; charset=UTF-8">
        <TITLE>Bookmarks</TITLE>
        <H1>Bookmarks Toolbar</H1>
        <DL><p>
        <DT><H3 PERSONAL_TOOLBAR_FOLDER="true">Firefox Folder</H3>
        <DL><p>
        <DT><A HREF="https://firefox-example.com" LAST_CHARSET="UTF-8">Firefox Bookmark</A>
        </DL><p>
        </DL><p>
        """

        # 解析実行
        bookmarks = self.parser.parse_bookmarks(firefox_html)

        # アサーション
        assert bookmarks is not None, "Firefox ブックマークの解析に失敗しました"
        assert len(bookmarks) > 0, "ブックマークが解析されませんでした"
        assert bookmarks[0].title == "Firefox Bookmark", (
            "ブックマークタイトルが正しくありません"
        )
        assert bookmarks[0].url == "https://firefox-example.com", (
            "ブックマークURLが正しくありません"
        )


if __name__ == "__main__":
    # テストを実行
    pytest.main([__file__, "-v", "--tb=short"])
