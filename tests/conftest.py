"""
pytest設定ファイル
テスト実行時の共通設定とフィクスチャを定義します。
"""

import pytest
import tempfile
import shutil
from unittest.mock import Mock


@pytest.fixture
def temp_dir():
    """テスト用の一時ディレクトリを提供するフィクスチャ"""
    temp_path = tempfile.mkdtemp()
    yield temp_path
    shutil.rmtree(temp_path, ignore_errors=True)


@pytest.fixture
def sample_bookmark_html():
    """テスト用のサンプルブックマークHTMLを提供するフィクスチャ"""
    return """
    <!DOCTYPE NETSCAPE-Bookmark-file-1>
    <META HTTP-EQUIV="Content-Type" CONTENT="text/html; charset=UTF-8">
    <TITLE>Bookmarks</TITLE>
    <H1>Bookmarks</H1>
    <DL><p>
    <DT><H3>Test Folder</H3>
    <DL><p>
    <DT><A HREF="https://example1.com">Test Bookmark 1</A>
    <DT><A HREF="https://example2.com">Test Bookmark 2</A>
    </DL><p>
    <DT><A HREF="https://example3.com">Root Bookmark</A>
    </DL><p>
    """


@pytest.fixture
def mock_progress_callback():
    """テスト用の進捗コールバック関数を提供するフィクスチャ"""
    return Mock()


# テスト実行時の設定
def pytest_configure(config):
    """pytest実行時の設定"""
    # テスト実行時の警告を抑制
    import warnings

    warnings.filterwarnings("ignore", category=DeprecationWarning)
    warnings.filterwarnings("ignore", category=PendingDeprecationWarning)


# テストマーカーの定義
def pytest_collection_modifyitems(config, items):
    """テストアイテムの修正"""
    # パフォーマンステストにマーカーを追加
    for item in items:
        if "performance" in item.nodeid:
            item.add_marker(pytest.mark.performance)
        if "integration" in item.nodeid:
            item.add_marker(pytest.mark.integration)
