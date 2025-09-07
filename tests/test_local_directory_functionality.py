#!/usr/bin/env python3
"""
LocalDirectoryManager機能の動作確認スクリプト
"""

import tempfile
from pathlib import Path
import sys

# app.pyから必要なクラスをインポート
from app import LocalDirectoryManager, Bookmark


def test_basic_functionality():
    """基本機能のテスト"""
    print("=== LocalDirectoryManager 基本機能テスト ===\n")

    # 一時ディレクトリを作成
    with tempfile.TemporaryDirectory() as temp_dir:
        print(f"テスト用ディレクトリ: {temp_dir}")

        # テスト用ファイル構造を作成
        test_files = [
            "existing_file1.md",
            "existing_file2.markdown",
            "folder1/nested_file.md",
            "folder1/subfolder/deep_file.md",
            "folder2/another_file.md",
            "ignore_this.txt",  # これは無視される
        ]

        print("\n1. テスト用ファイル構造を作成中...")
        for file_path in test_files:
            full_path = Path(temp_dir) / file_path
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(f"Content of {file_path}")
            print(f"  作成: {file_path}")

        # LocalDirectoryManagerを初期化
        manager = LocalDirectoryManager(temp_dir)

        # ディレクトリスキャンテスト
        print("\n2. ディレクトリスキャン実行中...")
        existing_structure = manager.scan_directory()

        print("検出された構造:")
        for path, files in existing_structure.items():
            path_display = path if path else "(ルート)"
            print(f"  📁 {path_display}: {files}")

        # テスト用ブックマークを作成
        print("\n3. テスト用ブックマークを作成...")
        bookmarks = [
            Bookmark(
                title="existing file1", url="https://example.com/1", folder_path=[]
            ),  # 重複
            Bookmark(
                title="new file", url="https://example.com/2", folder_path=[]
            ),  # 新規
            Bookmark(
                title="nested file",
                url="https://example.com/3",
                folder_path=["folder1"],
            ),  # 重複
            Bookmark(
                title="brand new", url="https://example.com/4", folder_path=["folder1"]
            ),  # 新規
            Bookmark(
                title="Test<>File", url="https://example.com/5", folder_path=["folder3"]
            ),  # サニタイズテスト
        ]

        for i, bookmark in enumerate(bookmarks):
            folder_display = (
                " > ".join(bookmark.folder_path) if bookmark.folder_path else "(ルート)"
            )
            print(f"  {i + 1}. {bookmark.title} [{folder_display}]")

        # 重複チェック実行
        print("\n4. 重複チェック実行中...")
        duplicates = manager.compare_with_bookmarks(bookmarks)

        print(f"重複ファイル数: {len(duplicates['files'])}")
        if duplicates["files"]:
            print("重複ファイル一覧:")
            for duplicate in duplicates["files"]:
                print(f"  🔄 {duplicate}")

        # 個別の重複判定テスト
        print("\n5. 個別重複判定テスト...")
        for i, bookmark in enumerate(bookmarks):
            is_dup = manager.is_duplicate(bookmark)
            status = "重複" if is_dup else "新規"
            print(f"  {i + 1}. {bookmark.title} → {status}")

        # ファイル名サニタイズテスト
        print("\n6. ファイル名サニタイズテスト...")
        test_titles = [
            "Normal Title",
            "Title<>With:Bad/Characters",
            "Very" + "Long" * 50 + "Title",
            "",
            "   Spaces   ",
        ]

        for title in test_titles:
            sanitized = manager._sanitize_filename(title)
            print(f"  '{title}' → '{sanitized}'")

        # 統計情報
        print("\n7. 統計情報...")
        stats = manager.get_statistics()
        print(f"  総ファイル数: {stats['total_files']}")
        print(f"  総ディレクトリ数: {stats['total_directories']}")
        print(f"  重複ファイル数: {stats['duplicate_files']}")

        print("\n✅ テスト完了!")


def test_file_operations():
    """ファイル操作のテスト"""
    print("\n=== ファイル操作テスト ===\n")

    with tempfile.TemporaryDirectory() as temp_dir:
        manager = LocalDirectoryManager(temp_dir)

        # ディレクトリ構造作成テスト
        print("1. ディレクトリ構造作成テスト...")
        structure = {
            "test_folder": ["file1", "file2"],
            "test_folder/subfolder": ["file3"],
            "another_folder": ["file4"],
        }

        manager.create_directory_structure(temp_dir, structure)

        for folder in structure.keys():
            if folder:
                folder_path = Path(temp_dir) / folder
                exists = folder_path.exists()
                print(f"  📁 {folder}: {'✅' if exists else '❌'}")

        # ファイル保存テスト
        print("\n2. Markdownファイル保存テスト...")
        test_content = """# テストファイル

これはテスト用のMarkdownファイルです。

## セクション1
- リスト項目1
- リスト項目2

## セクション2
**太字テキスト** と *斜体テキスト*
"""

        test_files = [
            "test_root.md",
            "test_folder/test_nested.md",
            "new_folder/deep/test_deep.md",
        ]

        for file_path in test_files:
            success = manager.save_markdown_file(file_path, test_content)
            full_path = Path(temp_dir) / file_path
            exists = full_path.exists()
            print(f"  📄 {file_path}: {'✅' if success and exists else '❌'}")

        print("\n✅ ファイル操作テスト完了!")


if __name__ == "__main__":
    try:
        test_basic_functionality()
        test_file_operations()
        print("\n🎉 全てのテストが正常に完了しました！")
    except Exception as e:
        print(f"\n❌ エラーが発生しました: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
