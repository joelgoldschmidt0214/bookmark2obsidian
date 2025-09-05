"""
ファイルアップロードとディレクトリ選択機能のテスト
"""

import tempfile
from pathlib import Path
from app import validate_bookmarks_file, validate_directory_path

# pytestは開発依存関係なので、手動テスト用の関数も提供
try:
    import pytest
    PYTEST_AVAILABLE = True
except ImportError:
    PYTEST_AVAILABLE = False


class MockUploadedFile:
    """Streamlitのアップロードファイルをモックするクラス"""
    
    def __init__(self, name: str, content: str):
        self.name = name
        self.content = content.encode('utf-8')
        self.pos = 0
    
    def read(self):
        return self.content
    
    def seek(self, pos: int):
        self.pos = pos


def create_test_bookmarks_html() -> str:
    """テスト用のブックマークHTMLコンテンツを生成"""
    return '''<!DOCTYPE NETSCAPE-Bookmark-file-1>
<!-- This is an automatically generated file.
     It will be read and overwritten.
     DO NOT EDIT! -->
<META HTTP-EQUIV="Content-Type" CONTENT="text/html; charset=UTF-8">
<TITLE>Bookmarks</TITLE>
<H1>Bookmarks</H1>
<DL><p>
    <DT><H3 ADD_DATE="1634790292" LAST_MODIFIED="1747662924">開発</H3>
    <DL><p>
        <DT><H3 ADD_DATE="1737884617" LAST_MODIFIED="1746704274">フロントエンド</H3>
        <DL><p>
            <DT><A HREF="https://reactjs.org/" ADD_DATE="1737884602">React – A JavaScript library for building user interfaces</A>
            <DT><A HREF="https://vuejs.org/" ADD_DATE="1739975310">Vue.js - The Progressive JavaScript Framework</A>
        </DL><p>
        <DT><H3 ADD_DATE="1704464941" LAST_MODIFIED="1746588642">バックエンド</H3>
        <DL><p>
            <DT><A HREF="https://fastapi.tiangolo.com/" ADD_DATE="1704464913">FastAPI</A>
            <DT><A HREF="https://flask.palletsprojects.com/" ADD_DATE="1715224341">Flask</A>
        </DL><p>
    </DL><p>
    <DT><H3 ADD_DATE="1634790292" LAST_MODIFIED="1747662924">ツール</H3>
    <DL><p>
        <DT><A HREF="https://github.com/" ADD_DATE="1737884602">GitHub</A>
        <DT><A HREF="https://stackoverflow.com/" ADD_DATE="1739975310">Stack Overflow</A>
    </DL><p>
</DL><p>'''


class TestValidateBookmarksFile:
    """ブックマークファイル検証のテスト"""
    
    def test_valid_bookmarks_file(self):
        """有効なブックマークファイルのテスト"""
        content = create_test_bookmarks_html()
        mock_file = MockUploadedFile("bookmarks.html", content)
        
        is_valid, message = validate_bookmarks_file(mock_file)
        
        assert is_valid is True
        assert "有効なブックマークファイルです" in message
        assert "6個のブックマーク" in message
        assert "4個のフォルダ" in message
    
    def test_none_file(self):
        """ファイルが選択されていない場合のテスト"""
        is_valid, message = validate_bookmarks_file(None)
        
        assert is_valid is False
        assert "ファイルが選択されていません" in message
    
    def test_non_html_file(self):
        """HTMLファイル以外のテスト"""
        mock_file = MockUploadedFile("test.txt", "some content")
        
        is_valid, message = validate_bookmarks_file(mock_file)
        
        assert is_valid is False
        assert "HTMLファイルを選択してください" in message
    
    def test_empty_bookmarks_file(self):
        """ブックマークが含まれていないHTMLファイルのテスト"""
        content = "<html><head><title>Empty</title></head><body></body></html>"
        mock_file = MockUploadedFile("empty.html", content)
        
        is_valid, message = validate_bookmarks_file(mock_file)
        
        assert is_valid is False
        assert "ブックマークが見つかりません" in message
    
    def test_invalid_encoding(self):
        """無効な文字エンコーディングのテスト"""
        # 無効なUTF-8バイト列を含むモックファイル
        class InvalidEncodingFile:
            def __init__(self):
                self.name = "invalid.html"
            
            def read(self):
                return b'\xff\xfe'  # 無効なUTF-8
            
            def seek(self, pos):
                pass
        
        mock_file = InvalidEncodingFile()
        is_valid, message = validate_bookmarks_file(mock_file)
        
        assert is_valid is False
        assert "文字エンコーディングが正しくありません" in message


class TestValidateDirectoryPath:
    """ディレクトリパス検証のテスト"""
    
    def test_valid_directory(self):
        """有効なディレクトリのテスト"""
        with tempfile.TemporaryDirectory() as temp_dir:
            is_valid, message = validate_directory_path(temp_dir)
            
            assert is_valid is True
            assert "有効なディレクトリです" in message
            assert temp_dir in message
    
    def test_empty_path(self):
        """空のパスのテスト"""
        is_valid, message = validate_directory_path("")
        
        assert is_valid is False
        assert "ディレクトリパスを入力してください" in message
    
    def test_whitespace_only_path(self):
        """空白のみのパスのテスト"""
        is_valid, message = validate_directory_path("   ")
        
        assert is_valid is False
        assert "ディレクトリパスを入力してください" in message
    
    def test_nonexistent_path(self):
        """存在しないパスのテスト"""
        nonexistent_path = "/path/that/does/not/exist/12345"
        is_valid, message = validate_directory_path(nonexistent_path)
        
        assert is_valid is False
        assert "指定されたパスが存在しません" in message
    
    def test_file_instead_of_directory(self):
        """ファイルパスを指定した場合のテスト"""
        with tempfile.NamedTemporaryFile() as temp_file:
            is_valid, message = validate_directory_path(temp_file.name)
            
            assert is_valid is False
            assert "指定されたパスはディレクトリではありません" in message


def run_manual_test():
    """手動テスト用の関数"""
    print("=== ファイルアップロードとディレクトリ選択機能のテスト ===")
    
    # 1. 有効なブックマークファイルのテスト
    print("\n1. 有効なブックマークファイルのテスト")
    content = create_test_bookmarks_html()
    mock_file = MockUploadedFile("bookmarks.html", content)
    is_valid, message = validate_bookmarks_file(mock_file)
    print(f"結果: {is_valid}")
    print(f"メッセージ: {message}")
    
    # 2. 無効なファイルのテスト
    print("\n2. 無効なファイル（非HTML）のテスト")
    mock_file = MockUploadedFile("test.txt", "not html content")
    is_valid, message = validate_bookmarks_file(mock_file)
    print(f"結果: {is_valid}")
    print(f"メッセージ: {message}")
    
    # 3. 有効なディレクトリのテスト
    print("\n3. 有効なディレクトリのテスト")
    temp_dir = tempfile.mkdtemp()
    is_valid, message = validate_directory_path(temp_dir)
    print(f"結果: {is_valid}")
    print(f"メッセージ: {message}")
    
    # 4. 無効なディレクトリのテスト
    print("\n4. 無効なディレクトリのテスト")
    is_valid, message = validate_directory_path("/nonexistent/path")
    print(f"結果: {is_valid}")
    print(f"メッセージ: {message}")
    
    print("\n=== テスト完了 ===")


if __name__ == "__main__":
    run_manual_test()