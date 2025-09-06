#!/usr/bin/env python3
"""
ブックマークファイルから抽出されるタイトルと既存ファイル名の比較
"""

import os
from app import BookmarkParser, LocalDirectoryManager

def debug_bookmark_titles():
    """ブックマークタイトルと既存ファイル名の比較"""
    print("=== ブックマークタイトルと既存ファイル名の比較 ===\n")
    
    # 実際のObsidianディレクトリパス
    obsidian_path = "/mnt/d/hasechu/OneDrive/ドキュメント/Obsidian/hase_main"
    
    # LocalDirectoryManagerでディレクトリスキャン
    print("1. 既存ファイルをスキャン...")
    manager = LocalDirectoryManager(obsidian_path)
    existing_structure = manager.scan_directory()
    
    # 既存ファイル名を収集
    existing_files = set()
    for path, files in existing_structure.items():
        for file in files:
            existing_files.add(file)
    
    print(f"既存ファイル数: {len(existing_files)}")
    print("既存ファイル例（最初の10個）:")
    for i, file in enumerate(list(existing_files)[:10]):
        print(f"  - {file}")
    
    # ブックマークファイルが存在するかチェック
    # 通常、Streamlitアプリでアップロードされたファイルは一時的なので、
    # ここでは仮想的なブックマークを作成してテスト
    print(f"\n2. 既存ファイル名をブックマークタイトルとして使用してテスト...")
    
    # 既存ファイル名の一部をブックマークとして作成
    from app import Bookmark
    test_bookmarks = []
    
    sample_files = list(existing_files)[:20]  # 最初の20個をテスト
    for file in sample_files:
        # ファイル名からフォルダパスを推測（実際のパスを使用）
        folder_path = []
        for path, files in existing_structure.items():
            if file in files:
                folder_path = path.split('/') if path else []
                break
        
        bookmark = Bookmark(
            title=file,  # 既存ファイル名をそのままタイトルとして使用
            url=f"https://example.com/{file}",
            folder_path=folder_path
        )
        test_bookmarks.append(bookmark)
    
    print(f"テスト用ブックマーク数: {len(test_bookmarks)}")
    
    # 重複チェック実行
    print("\n3. 重複チェック実行...")
    duplicates = manager.compare_with_bookmarks(test_bookmarks)
    
    print(f"重複検出数: {len(duplicates['files'])}")
    print(f"期待値: {len(test_bookmarks)} (全て重複のはず)")
    
    if len(duplicates['files']) != len(test_bookmarks):
        print("\n❌ 重複チェックに問題があります！")
        print("\n重複として検出されなかったファイル:")
        detected_files = set(duplicates['files'])
        for bookmark in test_bookmarks:
            folder_path = '/'.join(bookmark.folder_path) if bookmark.folder_path else ''
            expected_path = f"{folder_path}/{bookmark.title}" if folder_path else bookmark.title
            if expected_path not in detected_files:
                print(f"  - {expected_path}")
                # 詳細チェック
                filename = manager._sanitize_filename(bookmark.title)
                file_exists = manager.check_file_exists(folder_path, filename)
                print(f"    サニタイズ後: '{filename}', 存在チェック: {file_exists}")
    else:
        print("✅ 重複チェックは正常に動作しています！")

if __name__ == "__main__":
    # デバッグログを有効にする
    os.environ['DEBUG'] = '1'
    
    debug_bookmark_titles()