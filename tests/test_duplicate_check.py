#!/usr/bin/env python3
"""
重複チェック機能の詳細テスト
"""

import tempfile
import os
from pathlib import Path
from app import LocalDirectoryManager, Bookmark


def create_test_environment():
    """テスト環境を作成"""
    temp_dir = tempfile.mkdtemp()
    print(f"テスト用ディレクトリ: {temp_dir}")

    # 既存ファイルを作成
    existing_files = [
        "Google.md",  # "Google"というタイトルのブックマークと重複
        "GitHub.md",  # "GitHub"というタイトルのブックマークと重複
        "folder1/Python Documentation.md",  # フォルダ内の重複
        "folder2/Stack Overflow.md",
    ]

    print("\n既存ファイルを作成:")
    for file_path in existing_files:
        full_path = Path(temp_dir) / file_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(f"# {file_path}\n\nExisting content")
        print(f"  作成: {file_path}")

    return temp_dir


def create_test_bookmarks():
    """テスト用ブックマークを作成"""
    bookmarks = [
        Bookmark(title="Google", url="https://google.com", folder_path=[]),  # 重複
        Bookmark(title="GitHub", url="https://github.com", folder_path=[]),  # 重複
        Bookmark(title="New Site", url="https://newsite.com", folder_path=[]),  # 新規
        Bookmark(
            title="Python Documentation",
            url="https://docs.python.org",
            folder_path=["folder1"],
        ),  # 重複
        Bookmark(
            title="Stack Overflow",
            url="https://stackoverflow.com",
            folder_path=["folder2"],
        ),  # 重複
        Bookmark(
            title="Fresh Content", url="https://fresh.com", folder_path=["folder1"]
        ),  # 新規
    ]

    print("\nテスト用ブックマーク:")
    for i, bookmark in enumerate(bookmarks):
        folder_display = (
            " > ".join(bookmark.folder_path) if bookmark.folder_path else "(ルート)"
        )
        print(f"  {i + 1}. {bookmark.title} [{folder_display}]")

    return bookmarks


def test_duplicate_detection():
    """重複検出のテスト"""
    print("=== 重複検出テスト ===")

    # テスト環境を作成
    temp_dir = create_test_environment()
    bookmarks = create_test_bookmarks()

    try:
        # LocalDirectoryManagerを初期化
        manager = LocalDirectoryManager(temp_dir)

        # ディレクトリスキャン
        print("\nディレクトリスキャン実行...")
        existing_structure = manager.scan_directory()

        print("検出された既存構造:")
        for path, files in existing_structure.items():
            path_display = path if path else "(ルート)"
            print(f"  📁 {path_display}: {files}")

        # 重複チェック実行
        print("\n重複チェック実行...")
        duplicates = manager.compare_with_bookmarks(bookmarks)

        print("\n結果:")
        print(f"  重複ファイル数: {len(duplicates['files'])}")
        print(f"  重複ファイル一覧: {duplicates['files']}")

        # 期待される重複
        expected_duplicates = [
            "Google",
            "GitHub",
            "folder1/Python_Documentation",
            "folder2/Stack_Overflow",
        ]

        print(f"\n期待される重複: {expected_duplicates}")

        # 個別チェック
        print("\n個別重複判定:")
        for i, bookmark in enumerate(bookmarks):
            is_dup = manager.is_duplicate(bookmark)
            status = "重複" if is_dup else "新規"
            print(f"  {i + 1}. {bookmark.title} → {status}")

        # 統計情報
        stats = manager.get_statistics()
        print("\n統計情報:")
        print(f"  総ファイル数: {stats['total_files']}")
        print(f"  総ディレクトリ数: {stats['total_directories']}")
        print(f"  重複ファイル数: {stats['duplicate_files']}")

    finally:
        # クリーンアップ
        import shutil

        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    # デバッグログを有効にする
    os.environ["DEBUG"] = "1"

    test_duplicate_detection()
