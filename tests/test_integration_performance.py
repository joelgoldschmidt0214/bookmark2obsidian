"""
統合パフォーマンステストモジュール
このモジュールは、アプリケーション全体の統合パフォーマンスを検証します。
実際の使用シナリオに基づいたテストを提供します。
"""

import pytest
import time
import tempfile
import os
from typing import List, Dict, Any
from unittest.mock import Mock, patch

# テスト対象のモジュールをインポート
from core.parser import BookmarkParser
from core.cache_manager import CacheManager
from utils.performance_utils import PerformanceOptimizer
from utils.error_handler import error_logger, error_recovery
from ui.progress_display import ProgressDisplay
from utils.models import Bookmark


class TestRealWorldScenarios:
    """実世界のシナリオに基づくパフォーマンステスト"""

    def setup_method(self):
        """各テストメソッドの前に実行される初期化処理"""
        self.temp_dir = tempfile.mkdtemp()
        self.cache_manager = CacheManager(cache_dir=self.temp_dir)
        self.parser = BookmarkParser()
        self.optimizer = PerformanceOptimizer()
        self.progress_display = ProgressDisplay()

    def teardown_method(self):
        """各テストメソッドの後に実行されるクリーンアップ処理"""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_chrome_bookmark_export_performance(self):
        """Chrome ブックマークエクスポートファイルのパフォーマンステスト"""
        # Chrome形式のブックマークHTMLを生成
        chrome_html = self._generate_chrome_bookmark_html(2000)

        # 解析パフォーマンスを測定
        start_time = time.time()
        bookmarks = self.parser.parse_bookmarks(chrome_html)
        parse_time = time.time() - start_time

        # アサーション
        assert bookmarks is not None, "Chrome ブックマークの解析に失敗しました"
        assert len(bookmarks) > 1500, (
            f"期待されるブックマーク数が不足: {len(bookmarks)}"
        )

        # パフォーマンス要件（2000個のブックマークを15秒以内で解析）
        assert parse_time < 15.0, (
            f"Chrome ブックマーク解析が遅すぎます: {parse_time:.3f}s"
        )

        # 解析効率の確認
        bookmarks_per_second = len(bookmarks) / parse_time
        assert bookmarks_per_second > 100, (
            f"解析効率が低すぎます: {bookmarks_per_second:.1f} bookmarks/sec"
        )

        print(
            f"Chrome ブックマーク解析: {len(bookmarks)} bookmarks in {parse_time:.3f}s ({bookmarks_per_second:.1f} bookmarks/sec)"
        )

    def test_large_bookmark_file_with_cache(self):
        """大きなブックマークファイルでのキャッシュ効果テスト"""
        # 大きなブックマークファイルを生成
        large_html = self._generate_chrome_bookmark_html(5000)

        # 初回実行（キャッシュなし）
        start_time = time.time()
        bookmarks_first = self.parser.parse_bookmarks(large_html)
        file_hash = self.cache_manager.calculate_file_hash(large_html)
        self.cache_manager.save_bookmark_cache(file_hash, bookmarks_first)
        first_run_time = time.time() - start_time

        # 2回目実行（キャッシュあり）
        start_time = time.time()
        bookmarks_cached = self.cache_manager.load_bookmark_cache(file_hash)
        second_run_time = time.time() - start_time

        # アサーション
        assert bookmarks_cached is not None, "キャッシュからの読み込みに失敗しました"
        assert len(bookmarks_cached) == len(bookmarks_first), (
            "キャッシュされたデータの数が正しくありません"
        )

        # キャッシュ効果の確認（10倍以上の高速化）
        cache_speedup = (
            first_run_time / second_run_time if second_run_time > 0 else float("inf")
        )
        assert cache_speedup >= 10.0, (
            f"キャッシュ効果が不十分です: {cache_speedup:.2f}x speedup"
        )

        print(
            f"大きなファイルのキャッシュ効果: {cache_speedup:.2f}x faster ({first_run_time:.3f}s -> {second_run_time:.3f}s)"
        )

    def test_concurrent_processing_performance(self):
        """並行処理のパフォーマンステスト"""
        # 複数の中サイズブックマークファイルを生成
        bookmark_files = [self._generate_chrome_bookmark_html(500) for _ in range(4)]

        # シーケンシャル処理の時間を測定
        start_time = time.time()
        sequential_results = []
        for html in bookmark_files:
            bookmarks = self.parser.parse_bookmarks(html)
            sequential_results.append(bookmarks)
        sequential_time = time.time() - start_time

        # 並列処理の時間を測定
        start_time = time.time()
        parallel_results = self.optimizer.process_in_parallel(
            bookmark_files, self.parser.parse_bookmarks, max_workers=4
        )
        parallel_time = time.time() - start_time

        # 結果の正確性を確認
        assert len(parallel_results) == len(sequential_results), (
            "並列処理の結果数が正しくありません"
        )
        for i, (seq_result, par_result) in enumerate(
            zip(sequential_results, parallel_results)
        ):
            assert len(seq_result) == len(par_result), (
                f"ファイル{i}の並列処理結果が正しくありません"
            )

        # 並列処理の効果を確認（少なくとも1.5倍高速）
        speedup = sequential_time / parallel_time if parallel_time > 0 else float("inf")
        assert speedup >= 1.5, f"並列処理の効果が不十分です: {speedup:.2f}x speedup"

        print(
            f"並列処理効果: {speedup:.2f}x faster ({sequential_time:.3f}s -> {parallel_time:.3f}s)"
        )

    def _generate_chrome_bookmark_html(self, bookmark_count: int) -> str:
        """Chrome形式のブックマークHTMLを生成"""
        html_parts = [
            "<!DOCTYPE NETSCAPE-Bookmark-file-1>",
            '<META HTTP-EQUIV="Content-Type" CONTENT="text/html; charset=UTF-8">',
            "<TITLE>Bookmarks</TITLE>",
            "<H1>Bookmarks Menu</H1>",
            "<DL><p>",
        ]

        # Chrome特有の属性を含むブックマークを生成
        for i in range(bookmark_count):
            folder_name = f"Chrome Folder {i // 50}"
            bookmark_title = f"Chrome Bookmark {i}"
            bookmark_url = f"https://chrome-example{i}.com"
            add_date = str(1600000000 + i)  # Chrome形式のタイムスタンプ

            if i % 50 == 0:  # 新しいフォルダを開始
                html_parts.append(
                    f'<DT><H3 ADD_DATE="{add_date}" LAST_MODIFIED="{add_date}">{folder_name}</H3>'
                )
                html_parts.append("<DL><p>")

            html_parts.append(
                f'<DT><A HREF="{bookmark_url}" ADD_DATE="{add_date}">{bookmark_title}</A>'
            )

            if (i + 1) % 50 == 0:  # フォルダを閉じる
                html_parts.append("</DL><p>")

        html_parts.append("</DL><p>")
        return "\n".join(html_parts)


if __name__ == "__main__":
    # テストを実行
    pytest.main([__file__, "-v", "--tb=short"])
