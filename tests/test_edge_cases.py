"""
エッジケースと複雑なシナリオのテスト
"""

import tempfile
import os
from pathlib import Path
from app import validate_bookmarks_file, validate_directory_path
from tests.test_file_validation import MockUploadedFile


class TestComplexBookmarkStructures:
    """複雑なブックマーク構造のテスト"""
    
    def test_deeply_nested_bookmarks(self):
        """深くネストされたブックマーク構造のテスト"""
        content = '''<!DOCTYPE NETSCAPE-Bookmark-file-1>
<HTML><HEAD><TITLE>Bookmarks</TITLE></HEAD>
<BODY><H1>Bookmarks</H1>
<DL><p>
    <DT><H3>Level1</H3>
    <DL><p>
        <DT><H3>Level2</H3>
        <DL><p>
            <DT><H3>Level3</H3>
            <DL><p>
                <DT><A HREF="https://example.com/deep">Deep Link</A>
            </DL><p>
        </DL><p>
    </DL><p>
</DL></BODY></HTML>'''
        
        mock_file = MockUploadedFile("deep_bookmarks.html", content)
        is_valid, message = validate_bookmarks_file(mock_file)
        
        assert is_valid is True
        assert "1個のブックマーク" in message
        assert "3個のフォルダ" in message
    
    def test_bookmarks_with_special_characters(self):
        """特殊文字を含むブックマークのテスト"""
        content = '''<!DOCTYPE NETSCAPE-Bookmark-file-1>
<HTML><HEAD><TITLE>Bookmarks</TITLE></HEAD>
<BODY><H1>Bookmarks</H1>
<DL><p>
    <DT><A HREF="https://example.com/特殊文字">日本語タイトル & 特殊文字 < > " '</A>
    <DT><A HREF="https://example.com/emoji">🚀 Emoji Title 📚</A>
</DL></BODY></HTML>'''
        
        mock_file = MockUploadedFile("special_chars.html", content)
        is_valid, message = validate_bookmarks_file(mock_file)
        
        assert is_valid is True
        assert "2個のブックマーク" in message
    
    def test_bookmarks_with_malformed_html(self):
        """不正なHTMLを含むブックマークのテスト"""
        content = '''<!DOCTYPE NETSCAPE-Bookmark-file-1>
<HTML><HEAD><TITLE>Bookmarks</TITLE></HEAD>
<BODY><H1>Bookmarks</H1>
<DL><p>
    <DT><A HREF="https://example.com/unclosed">Unclosed Link
    <DT><A HREF="https://example.com/normal">Normal Link</A>
</DL></BODY></HTML>'''
        
        mock_file = MockUploadedFile("malformed.html", content)
        is_valid, message = validate_bookmarks_file(mock_file)
        
        # BeautifulSoupは不正なHTMLでも解析できるはず
        assert is_valid is True
        assert "ブックマーク" in message
    
    def test_empty_folders_only(self):
        """空のフォルダのみのブックマークファイル"""
        content = '''<!DOCTYPE NETSCAPE-Bookmark-file-1>
<HTML><HEAD><TITLE>Bookmarks</TITLE></HEAD>
<BODY><H1>Bookmarks</H1>
<DL><p>
    <DT><H3>Empty Folder 1</H3>
    <DL><p></DL><p>
    <DT><H3>Empty Folder 2</H3>
    <DL><p></DL><p>
</DL></BODY></HTML>'''
        
        mock_file = MockUploadedFile("empty_folders.html", content)
        is_valid, message = validate_bookmarks_file(mock_file)
        
        assert is_valid is False
        assert "ブックマークが見つかりません" in message


class TestDirectoryPermissions:
    """ディレクトリ権限のテスト"""
    
    def test_readonly_directory(self):
        """読み取り専用ディレクトリのテスト"""
        with tempfile.TemporaryDirectory() as temp_dir:
            # ディレクトリを読み取り専用に設定
            os.chmod(temp_dir, 0o444)
            
            try:
                is_valid, message = validate_directory_path(temp_dir)
                
                assert is_valid is False
                assert "書き込み権限がありません" in message
            finally:
                # 権限を戻してクリーンアップできるようにする
                os.chmod(temp_dir, 0o755)
    
    def test_home_directory_expansion(self):
        """ホームディレクトリ展開のテスト"""
        # ~ を含むパスのテスト
        home_path = str(Path.home())
        is_valid, message = validate_directory_path(home_path)
        
        assert is_valid is True
        assert "有効なディレクトリです" in message


class TestFileEncodingVariations:
    """ファイルエンコーディングのバリエーションテスト"""
    
    def test_utf8_with_bom(self):
        """UTF-8 BOM付きファイルのテスト"""
        content = '''<!DOCTYPE NETSCAPE-Bookmark-file-1>
<HTML><HEAD><TITLE>Bookmarks</TITLE></HEAD>
<BODY><H1>Bookmarks</H1>
<DL><p>
    <DT><A HREF="https://example.com/">Test Link</A>
</DL></BODY></HTML>'''
        
        # UTF-8 BOMを追加
        content_with_bom = '\ufeff' + content
        
        mock_file = MockUploadedFile("bom_file.html", content_with_bom)
        is_valid, message = validate_bookmarks_file(mock_file)
        
        assert is_valid is True
        assert "1個のブックマーク" in message
    
    def test_large_bookmark_file(self):
        """大きなブックマークファイルのテスト"""
        # 1000個のブックマークを生成
        links = []
        for i in range(1000):
            links.append(f'    <DT><A HREF="https://example{i}.com/">Link {i}</A>')
        
        content = f'''<!DOCTYPE NETSCAPE-Bookmark-file-1>
<HTML><HEAD><TITLE>Bookmarks</TITLE></HEAD>
<BODY><H1>Bookmarks</H1>
<DL><p>
{chr(10).join(links)}
</DL></BODY></HTML>'''
        
        mock_file = MockUploadedFile("large_bookmarks.html", content)
        is_valid, message = validate_bookmarks_file(mock_file)
        
        assert is_valid is True
        assert "1000個のブックマーク" in message


def test_integration_both_validations():
    """ファイルとディレクトリ両方の検証の統合テスト"""
    # 有効なブックマークファイル
    content = '''<!DOCTYPE NETSCAPE-Bookmark-file-1>
<HTML><HEAD><TITLE>Bookmarks</TITLE></HEAD>
<BODY><H1>Bookmarks</H1>
<DL><p>
    <DT><A HREF="https://example.com/">Test Link</A>
</DL></BODY></HTML>'''
    
    mock_file = MockUploadedFile("integration_test.html", content)
    
    # 有効なディレクトリ
    with tempfile.TemporaryDirectory() as temp_dir:
        # 両方の検証を実行
        file_valid, file_msg = validate_bookmarks_file(mock_file)
        dir_valid, dir_msg = validate_directory_path(temp_dir)
        
        # 両方とも成功するはず
        assert file_valid is True
        assert dir_valid is True
        assert "有効なブックマークファイルです" in file_msg
        assert "有効なディレクトリです" in dir_msg