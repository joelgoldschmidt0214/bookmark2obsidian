"""
Task 9: ページ一覧表示とプレビュー機能のテスト
"""

import pytest
import sys
from pathlib import Path
from datetime import datetime

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app import organize_bookmarks_by_folder, Bookmark


class TestPagePreview:
    """ページ一覧表示とプレビュー機能のテストクラス"""

    @pytest.fixture
    def sample_bookmarks(self):
        """サンプルブックマークを提供するフィクスチャ"""
        return [
            Bookmark(
                title="Python記事1",
                url="https://example.com/python1",
                folder_path=["技術", "Python"],
                add_date=datetime(2024, 1, 1, 12, 0, 0),
            ),
            Bookmark(
                title="Python記事2",
                url="https://example.com/python2",
                folder_path=["技術", "Python"],
                add_date=datetime(2024, 1, 2, 12, 0, 0),
            ),
            Bookmark(
                title="JavaScript記事",
                url="https://example.com/js",
                folder_path=["技術", "JavaScript"],
                add_date=datetime(2024, 1, 3, 12, 0, 0),
            ),
            Bookmark(
                title="ルート記事",
                url="https://example.com/root",
                folder_path=[],
                add_date=datetime(2024, 1, 4, 12, 0, 0),
            ),
        ]

    def test_organize_bookmarks_by_folder(self, sample_bookmarks):
        """ブックマークのフォルダ別整理テスト"""
        folder_groups = organize_bookmarks_by_folder(sample_bookmarks)

        # フォルダ構造の確認
        assert len(folder_groups) == 3  # 3つのフォルダグループ

        # Pythonフォルダの確認
        python_key = ("技術", "Python")
        assert python_key in folder_groups
        assert len(folder_groups[python_key]) == 2

        # JavaScriptフォルダの確認
        js_key = ("技術", "JavaScript")
        assert js_key in folder_groups
        assert len(folder_groups[js_key]) == 1

        # ルートフォルダの確認
        root_key = ()
        assert root_key in folder_groups
        assert len(folder_groups[root_key]) == 1

    def test_organize_bookmarks_empty_list(self):
        """空のブックマークリストの整理テスト"""
        folder_groups = organize_bookmarks_by_folder([])

        assert len(folder_groups) == 0
        assert isinstance(folder_groups, dict)

    def test_organize_bookmarks_all_root(self):
        """全てルートフォルダのブックマーク整理テスト"""
        root_bookmarks = [
            Bookmark(
                title="ルート記事1", url="https://example.com/root1", folder_path=[]
            ),
            Bookmark(
                title="ルート記事2", url="https://example.com/root2", folder_path=[]
            ),
        ]

        folder_groups = organize_bookmarks_by_folder(root_bookmarks)

        assert len(folder_groups) == 1
        assert () in folder_groups
        assert len(folder_groups[()]) == 2

    def test_organize_bookmarks_deep_hierarchy(self):
        """深い階層のブックマーク整理テスト"""
        deep_bookmarks = [
            Bookmark(
                title="深い記事",
                url="https://example.com/deep",
                folder_path=["レベル1", "レベル2", "レベル3", "レベル4"],
            )
        ]

        folder_groups = organize_bookmarks_by_folder(deep_bookmarks)

        assert len(folder_groups) == 1
        deep_key = ("レベル1", "レベル2", "レベル3", "レベル4")
        assert deep_key in folder_groups
        assert len(folder_groups[deep_key]) == 1

    def test_organize_bookmarks_sorting(self, sample_bookmarks):
        """フォルダソート機能テスト"""
        folder_groups = organize_bookmarks_by_folder(sample_bookmarks)

        # フォルダキーがソートされていることを確認
        folder_keys = list(folder_groups.keys())
        expected_order = [
            (),  # ルートフォルダが最初
            ("技術", "JavaScript"),
            ("技術", "Python"),
        ]

        assert folder_keys == expected_order

    def test_organize_bookmarks_with_none_folder_path(self):
        """folder_pathがNoneのブックマーク整理テスト"""
        bookmarks_with_none = [
            Bookmark(title="None記事", url="https://example.com/none", folder_path=None)
        ]

        folder_groups = organize_bookmarks_by_folder(bookmarks_with_none)

        assert len(folder_groups) == 1
        assert () in folder_groups  # Noneは空のタプルとして扱われる
        assert len(folder_groups[()]) == 1

    def test_organize_bookmarks_mixed_folder_types(self):
        """様々なフォルダタイプの混在テスト"""
        mixed_bookmarks = [
            Bookmark(title="記事1", url="https://example.com/1", folder_path=["A"]),
            Bookmark(
                title="記事2", url="https://example.com/2", folder_path=["A", "B"]
            ),
            Bookmark(
                title="記事3", url="https://example.com/3", folder_path=["A", "B", "C"]
            ),
            Bookmark(title="記事4", url="https://example.com/4", folder_path=["B"]),
        ]

        folder_groups = organize_bookmarks_by_folder(mixed_bookmarks)

        # 4つの異なるフォルダグループ
        assert len(folder_groups) == 4

        # 各フォルダの確認
        assert ("A",) in folder_groups
        assert ("A", "B") in folder_groups
        assert ("A", "B", "C") in folder_groups
        assert ("B",) in folder_groups

        # 各フォルダのブックマーク数確認
        assert len(folder_groups[("A",)]) == 1
        assert len(folder_groups[("A", "B")]) == 1
        assert len(folder_groups[("A", "B", "C")]) == 1
        assert len(folder_groups[("B",)]) == 1

    def test_organize_bookmarks_duplicate_folders(self):
        """同じフォルダに複数のブックマークがある場合のテスト"""
        duplicate_folder_bookmarks = [
            Bookmark(
                title="記事1", url="https://example.com/1", folder_path=["共通フォルダ"]
            ),
            Bookmark(
                title="記事2", url="https://example.com/2", folder_path=["共通フォルダ"]
            ),
            Bookmark(
                title="記事3", url="https://example.com/3", folder_path=["共通フォルダ"]
            ),
        ]

        folder_groups = organize_bookmarks_by_folder(duplicate_folder_bookmarks)

        assert len(folder_groups) == 1
        assert ("共通フォルダ",) in folder_groups
        assert len(folder_groups[("共通フォルダ",)]) == 3

        # ブックマークの順序が保持されていることを確認
        bookmarks_in_folder = folder_groups[("共通フォルダ",)]
        assert bookmarks_in_folder[0].title == "記事1"
        assert bookmarks_in_folder[1].title == "記事2"
        assert bookmarks_in_folder[2].title == "記事3"

    def test_organize_bookmarks_special_characters_in_folder(self):
        """フォルダ名に特殊文字が含まれる場合のテスト"""
        special_char_bookmarks = [
            Bookmark(
                title="特殊記事",
                url="https://example.com/special",
                folder_path=["フォルダ/スラッシュ", "フォルダ:コロン", "フォルダ<>"],
            )
        ]

        folder_groups = organize_bookmarks_by_folder(special_char_bookmarks)

        assert len(folder_groups) == 1
        special_key = ("フォルダ/スラッシュ", "フォルダ:コロン", "フォルダ<>")
        assert special_key in folder_groups
        assert len(folder_groups[special_key]) == 1

    def test_organize_bookmarks_unicode_folder_names(self):
        """Unicode文字を含むフォルダ名のテスト"""
        unicode_bookmarks = [
            Bookmark(
                title="Unicode記事",
                url="https://example.com/unicode",
                folder_path=["📚 技術書", "🐍 Python", "🔥 高度な内容"],
            )
        ]

        folder_groups = organize_bookmarks_by_folder(unicode_bookmarks)

        assert len(folder_groups) == 1
        unicode_key = ("📚 技術書", "🐍 Python", "🔥 高度な内容")
        assert unicode_key in folder_groups
        assert len(folder_groups[unicode_key]) == 1

    def test_organize_bookmarks_performance_large_list(self):
        """大量のブックマークでのパフォーマンステスト"""
        import time

        # 1000個のブックマークを生成
        large_bookmarks = []
        for i in range(1000):
            folder_index = i % 10  # 10個のフォルダに分散
            large_bookmarks.append(
                Bookmark(
                    title=f"記事{i}",
                    url=f"https://example.com/{i}",
                    folder_path=[f"フォルダ{folder_index}"],
                )
            )

        start_time = time.time()
        folder_groups = organize_bookmarks_by_folder(large_bookmarks)
        end_time = time.time()

        # 処理時間が1秒以内であることを確認
        assert (end_time - start_time) < 1.0

        # 結果の確認
        assert len(folder_groups) == 10
        for i in range(10):
            folder_key = (f"フォルダ{i}",)
            assert folder_key in folder_groups
            assert len(folder_groups[folder_key]) == 100  # 各フォルダに100個
