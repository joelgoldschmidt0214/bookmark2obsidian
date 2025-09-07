#!/usr/bin/env python3
"""
重複チェック問題のデバッグスクリプト
実際のディレクトリ構造を使って問題を特定する
"""

import os
from pathlib import Path
from app import LocalDirectoryManager, Bookmark


def debug_real_directory():
    """実際のディレクトリ構造での重複チェックをデバッグ"""
    print("=== 実際のディレクトリでの重複チェックデバッグ ===\n")

    # 実際のObsidianディレクトリパス（ログから取得）
    obsidian_path = "/mnt/d/hasechu/OneDrive/ドキュメント/Obsidian/hase_main"

    if not Path(obsidian_path).exists():
        print(f"❌ ディレクトリが存在しません: {obsidian_path}")
        return

    print(f"📂 対象ディレクトリ: {obsidian_path}")

    # LocalDirectoryManagerを初期化
    manager = LocalDirectoryManager(obsidian_path)

    # ディレクトリスキャン
    print("\n1. ディレクトリスキャン実行...")
    existing_structure = manager.scan_directory()

    print(f"検出されたディレクトリ数: {len(existing_structure)}")
    print("検出された構造（最初の10個）:")
    for i, (path, files) in enumerate(existing_structure.items()):
        if i >= 10:
            print(f"  ... 他 {len(existing_structure) - 10}個のディレクトリ")
            break
        path_display = path if path else "(ルート)"
        print(f"  📁 {path_display}: {len(files)}個のファイル")
        if files and len(files) <= 3:
            for file in files:
                print(f"    - {file}")
        elif files:
            print(f"    - {files[0]}")
            print(f"    - {files[1]}")
            print(f"    ... 他 {len(files) - 2}個")

    # テスト用ブックマークを作成（実際に存在するファイル名を使用）
    print("\n2. テスト用ブックマークを作成...")
    test_bookmarks = []

    # 既存ファイルから数個をテスト用ブックマークとして使用
    for path, files in existing_structure.items():
        if len(test_bookmarks) >= 5:
            break
        for file in files[:2]:  # 各ディレクトリから最大2個
            if len(test_bookmarks) >= 5:
                break
            folder_path = path.split("/") if path else []
            bookmark = Bookmark(
                title=file,  # ファイル名をそのままタイトルとして使用
                url=f"https://example.com/{file}",
                folder_path=folder_path,
            )
            test_bookmarks.append(bookmark)
            print(f"  作成: '{file}' (パス: {folder_path})")

    if not test_bookmarks:
        print("❌ テスト用ブックマークを作成できませんでした")
        return

    # 重複チェック実行
    print(f"\n3. 重複チェック実行 ({len(test_bookmarks)}個のブックマーク)...")
    duplicates = manager.compare_with_bookmarks(test_bookmarks)

    print("\n結果:")
    print(f"  重複ファイル数: {len(duplicates['files'])}")
    print(f"  重複ファイル一覧: {duplicates['files']}")

    # 個別チェック
    print("\n4. 個別重複判定:")
    for i, bookmark in enumerate(test_bookmarks):
        is_dup = manager.is_duplicate(bookmark)
        status = "重複" if is_dup else "新規"
        print(f"  {i + 1}. '{bookmark.title}' → {status}")

        # 詳細チェック
        folder_path = "/".join(bookmark.folder_path) if bookmark.folder_path else ""
        filename = manager._sanitize_filename(bookmark.title)
        file_exists = manager.check_file_exists(folder_path, filename)
        print(
            f"      パス: '{folder_path}', ファイル名: '{filename}', 存在: {file_exists}"
        )


def debug_sanitize_filename():
    """ファイル名サニタイズのテスト"""
    print("\n=== ファイル名サニタイズテスト ===")

    manager = LocalDirectoryManager("/tmp")

    test_cases = [
        "EXサービス運賃ナビ",
        "Python Documentation",
        "Stack Overflow",
        "Test File",
        "Test<>File",
        "Test/File\\Name",
    ]

    for title in test_cases:
        sanitized = manager._sanitize_filename(title)
        print(f"  '{title}' → '{sanitized}'")


if __name__ == "__main__":
    # デバッグログを有効にする
    os.environ["DEBUG"] = "1"

    debug_sanitize_filename()
    debug_real_directory()
