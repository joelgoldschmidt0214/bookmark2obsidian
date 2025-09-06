"""
LocalDirectoryManagerクラスのテスト
"""

import pytest
import tempfile
import os
from pathlib import Path
from unittest.mock import patch, MagicMock

# テスト対象のクラスをインポート
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import LocalDirectoryManager, Bookmark


class TestLocalDirectoryManager:
    """LocalDirectoryManagerクラスのテストクラス"""
    
    def setup_method(self):
        """各テストメソッドの前に実行される初期化処理"""
        # 一時ディレクトリを作成
        self.temp_dir = tempfile.mkdtemp()
        self.manager = LocalDirectoryManager(self.temp_dir)
    
    def teardown_method(self):
        """各テストメソッドの後に実行されるクリーンアップ処理"""
        # 一時ディレクトリを削除
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_init(self):
        """初期化のテスト"""
        assert self.manager.base_path == Path(self.temp_dir)
        assert self.manager.existing_structure == {}
        assert len(self.manager.duplicate_files) == 0
    
    def test_scan_empty_directory(self):
        """空のディレクトリのスキャンテスト"""
        result = self.manager.scan_directory()
        assert result == {}
        assert self.manager.existing_structure == {}
    
    def test_scan_directory_with_markdown_files(self):
        """Markdownファイルがあるディレクトリのスキャンテスト"""
        # テスト用ファイルを作成
        test_files = [
            "test1.md",
            "test2.markdown", 
            "test3.txt",  # これは除外される
            "subfolder/nested.md"
        ]
        
        for file_path in test_files:
            full_path = Path(self.temp_dir) / file_path
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text("test content")
        
        result = self.manager.scan_directory()
        
        # Markdownファイルのみが検出されることを確認
        assert '' in result  # ルートディレクトリ
        assert 'test1' in result['']
        assert 'test2' in result['']
        assert 'test3' not in result['']  # .txtファイルは除外
        
        assert 'subfolder' in result
        assert 'nested' in result['subfolder']
    
    def test_check_file_exists(self):
        """ファイル存在チェックのテスト"""
        # テスト用ファイルを作成
        test_file = Path(self.temp_dir) / "existing_file.md"
        test_file.write_text("test content")
        
        # ディレクトリをスキャン
        self.manager.scan_directory()
        
        # 存在するファイルのテスト
        assert self.manager.check_file_exists('', 'existing_file') == True
        
        # 存在しないファイルのテスト
        assert self.manager.check_file_exists('', 'non_existing_file') == False
    
    def test_compare_with_bookmarks_no_duplicates(self):
        """重複なしのブックマーク比較テスト"""
        # テスト用ブックマークを作成
        bookmarks = [
            Bookmark(title="Test Page 1", url="https://example.com/1", folder_path=[]),
            Bookmark(title="Test Page 2", url="https://example.com/2", folder_path=["folder1"])
        ]
        
        # 重複チェック実行
        duplicates = self.manager.compare_with_bookmarks(bookmarks)
        
        assert len(duplicates['files']) == 0
        assert len(duplicates['paths']) == 0
        assert self.manager.get_duplicate_count() == 0
    
    def test_compare_with_bookmarks_with_duplicates(self):
        """重複ありのブックマーク比較テスト"""
        # サニタイズされたファイル名で既存ファイルを作成
        # "Test Page 1" -> "Test_Page_1"
        existing_file = Path(self.temp_dir) / "Test_Page_1.md"
        existing_file.write_text("existing content")
        
        subfolder = Path(self.temp_dir) / "folder1"
        subfolder.mkdir()
        existing_file2 = subfolder / "Test_Page_2.md"
        existing_file2.write_text("existing content")
        
        # ディレクトリをスキャン
        self.manager.scan_directory()
        
        # テスト用ブックマークを作成（既存ファイルと同名になるタイトル）
        bookmarks = [
            Bookmark(title="Test Page 1", url="https://example.com/1", folder_path=[]),
            Bookmark(title="Test Page 2", url="https://example.com/2", folder_path=["folder1"]),
            Bookmark(title="New Page", url="https://example.com/3", folder_path=[])
        ]
        
        # 重複チェック実行
        duplicates = self.manager.compare_with_bookmarks(bookmarks)
        
        assert len(duplicates['files']) == 2  # 2つの重複
        assert 'Test_Page_1' in duplicates['files']
        assert 'folder1/Test_Page_2' in duplicates['files']
        assert self.manager.get_duplicate_count() == 2
    
    def test_is_duplicate(self):
        """重複判定のテスト"""
        # 既存ファイルを作成
        existing_file = Path(self.temp_dir) / "existing.md"
        existing_file.write_text("content")
        
        # ディレクトリをスキャンして重複チェック実行
        self.manager.scan_directory()
        
        bookmarks = [
            Bookmark(title="existing", url="https://example.com/1", folder_path=[]),
            Bookmark(title="new file", url="https://example.com/2", folder_path=[])
        ]
        
        self.manager.compare_with_bookmarks(bookmarks)
        
        # 重複判定テスト
        assert self.manager.is_duplicate(bookmarks[0]) == True  # existing
        assert self.manager.is_duplicate(bookmarks[1]) == False  # new file
    
    def test_sanitize_filename(self):
        """ファイル名サニタイズのテスト"""
        # 危険な文字を含むタイトル
        dangerous_title = 'Test<>:"/\\|?*File'
        sanitized = self.manager._sanitize_filename(dangerous_title)
        
        # 危険な文字がアンダースコアに置換されることを確認
        assert '<' not in sanitized
        assert '>' not in sanitized
        assert ':' not in sanitized
        assert '"' not in sanitized
        assert '/' not in sanitized
        assert '\\' not in sanitized
        assert '|' not in sanitized
        assert '?' not in sanitized
        assert '*' not in sanitized
        
        # 長すぎるタイトルの切り詰めテスト
        long_title = 'a' * 300
        sanitized_long = self.manager._sanitize_filename(long_title)
        assert len(sanitized_long) <= 200
    
    def test_create_directory_structure(self):
        """ディレクトリ構造作成のテスト"""
        structure = {
            'folder1': ['file1', 'file2'],
            'folder1/subfolder': ['file3'],
            'folder2': ['file4']
        }
        
        self.manager.create_directory_structure(self.temp_dir, structure)
        
        # ディレクトリが作成されたことを確認
        assert (Path(self.temp_dir) / 'folder1').exists()
        assert (Path(self.temp_dir) / 'folder1' / 'subfolder').exists()
        assert (Path(self.temp_dir) / 'folder2').exists()
    
    def test_save_markdown_file(self):
        """Markdownファイル保存のテスト"""
        content = "# Test Content\n\nThis is a test markdown file."
        file_path = "test_folder/test_file.md"
        
        result = self.manager.save_markdown_file(file_path, content)
        
        assert result == True
        
        # ファイルが実際に保存されたことを確認
        saved_file = Path(self.temp_dir) / file_path
        assert saved_file.exists()
        assert saved_file.read_text(encoding='utf-8') == content
    
    def test_get_statistics(self):
        """統計情報取得のテスト"""
        # テスト用ファイルを作成
        test_files = [
            "file1.md",
            "folder1/file2.md",
            "folder1/file3.md",
            "folder2/file4.md"
        ]
        
        for file_path in test_files:
            full_path = Path(self.temp_dir) / file_path
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text("content")
        
        # ディレクトリをスキャン
        self.manager.scan_directory()
        
        # 重複ファイルを設定
        self.manager.duplicate_files.add(('', 'file1'))
        self.manager.duplicate_files.add(('folder1', 'file2'))
        
        stats = self.manager.get_statistics()
        
        assert stats['total_files'] == 4
        assert stats['total_directories'] == 3  # '', 'folder1', 'folder2'
        assert stats['duplicate_files'] == 2


if __name__ == "__main__":
    pytest.main([__file__])