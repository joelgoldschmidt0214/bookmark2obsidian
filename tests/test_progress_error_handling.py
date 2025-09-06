"""
Task 10: 進捗表示とエラーハンドリング機能のテスト
"""

import pytest
import sys
import os
from pathlib import Path
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock
import requests

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app import ErrorLogger, Bookmark, WebScraper


class TestErrorLogger:
    """ErrorLoggerクラスのテスト"""
    
    @pytest.fixture
    def error_logger(self):
        """ErrorLoggerインスタンスを提供するフィクスチャ"""
        return ErrorLogger()
    
    @pytest.fixture
    def sample_bookmark(self):
        """サンプルブックマークを提供するフィクスチャ"""
        return Bookmark(
            title="テスト記事",
            url="https://example.com/test",
            folder_path=["テスト", "フォルダ"]
        )
    
    def test_error_logger_initialization(self, error_logger):
        """ErrorLoggerの初期化テスト"""
        assert len(error_logger.errors) == 0
        assert error_logger.error_counts['network'] == 0
        assert error_logger.error_counts['timeout'] == 0
        assert error_logger.error_counts['fetch'] == 0
        assert error_logger.error_counts['extraction'] == 0
        assert error_logger.error_counts['markdown'] == 0
        assert error_logger.error_counts['permission'] == 0
        assert error_logger.error_counts['filesystem'] == 0
        assert error_logger.error_counts['save'] == 0
        assert error_logger.error_counts['unexpected'] == 0
    
    def test_log_error_basic(self, error_logger, sample_bookmark):
        """基本的なエラーログ記録テスト"""
        error_msg = "テストエラーメッセージ"
        error_type = "network"
        
        error_logger.log_error(sample_bookmark, error_msg, error_type, retryable=True)
        
        assert len(error_logger.errors) == 1
        assert error_logger.error_counts['network'] == 1
        
        error_entry = error_logger.errors[0]
        assert error_entry['bookmark'] == sample_bookmark
        assert error_entry['error'] == error_msg
        assert error_entry['type'] == error_type
        assert error_entry['retryable'] == True
        assert error_entry['url'] == sample_bookmark.url
        assert error_entry['title'] == sample_bookmark.title
        assert isinstance(error_entry['timestamp'], datetime)
    
    def test_log_multiple_errors(self, error_logger, sample_bookmark):
        """複数エラーのログ記録テスト"""
        # 異なるタイプのエラーを記録
        error_logger.log_error(sample_bookmark, "ネットワークエラー", "network", True)
        error_logger.log_error(sample_bookmark, "タイムアウトエラー", "timeout", True)
        error_logger.log_error(sample_bookmark, "抽出エラー", "extraction", False)
        
        assert len(error_logger.errors) == 3
        assert error_logger.error_counts['network'] == 1
        assert error_logger.error_counts['timeout'] == 1
        assert error_logger.error_counts['extraction'] == 1
        assert error_logger.error_counts['fetch'] == 0
    
    def test_get_error_summary(self, error_logger, sample_bookmark):
        """エラーサマリー取得テスト"""
        # エラーを追加
        error_logger.log_error(sample_bookmark, "エラー1", "network", True)
        error_logger.log_error(sample_bookmark, "エラー2", "timeout", True)
        error_logger.log_error(sample_bookmark, "エラー3", "extraction", False)
        
        summary = error_logger.get_error_summary()
        
        assert summary['total_errors'] == 3
        assert summary['error_counts']['network'] == 1
        assert summary['error_counts']['timeout'] == 1
        assert summary['error_counts']['extraction'] == 1
        assert summary['retryable_count'] == 2
        assert len(summary['recent_errors']) == 3
    
    def test_get_retryable_errors(self, error_logger, sample_bookmark):
        """リトライ可能エラー取得テスト"""
        # リトライ可能・不可能なエラーを混在させる
        error_logger.log_error(sample_bookmark, "リトライ可能1", "network", True)
        error_logger.log_error(sample_bookmark, "リトライ不可1", "extraction", False)
        error_logger.log_error(sample_bookmark, "リトライ可能2", "timeout", True)
        error_logger.log_error(sample_bookmark, "リトライ不可2", "markdown", False)
        
        retryable_errors = error_logger.get_retryable_errors()
        
        assert len(retryable_errors) == 2
        assert all(error['retryable'] for error in retryable_errors)
        assert retryable_errors[0]['error'] == "リトライ可能1"
        assert retryable_errors[1]['error'] == "リトライ可能2"
    
    def test_clear_errors(self, error_logger, sample_bookmark):
        """エラーログクリアテスト"""
        # エラーを追加
        error_logger.log_error(sample_bookmark, "エラー1", "network", True)
        error_logger.log_error(sample_bookmark, "エラー2", "timeout", False)
        
        assert len(error_logger.errors) == 2
        assert error_logger.error_counts['network'] == 1
        assert error_logger.error_counts['timeout'] == 1
        
        # クリア実行
        error_logger.clear_errors()
        
        assert len(error_logger.errors) == 0
        assert error_logger.error_counts['network'] == 0
        assert error_logger.error_counts['timeout'] == 0
        assert all(count == 0 for count in error_logger.error_counts.values())
    
    def test_error_logger_with_large_number_of_errors(self, error_logger, sample_bookmark):
        """大量エラーでのパフォーマンステスト"""
        # 100個のエラーを記録
        for i in range(100):
            error_type = ['network', 'timeout', 'fetch', 'extraction'][i % 4]
            error_logger.log_error(
                sample_bookmark, 
                f"エラー{i}", 
                error_type, 
                retryable=(i % 2 == 0)
            )
        
        assert len(error_logger.errors) == 100
        assert error_logger.error_counts['network'] == 25
        assert error_logger.error_counts['timeout'] == 25
        assert error_logger.error_counts['fetch'] == 25
        assert error_logger.error_counts['extraction'] == 25
        
        summary = error_logger.get_error_summary()
        assert summary['total_errors'] == 100
        assert summary['retryable_count'] == 50
        assert len(summary['recent_errors']) == 10  # 最新10件のみ
    
    def test_error_logger_unknown_error_type(self, error_logger, sample_bookmark):
        """未知のエラータイプのテスト"""
        error_logger.log_error(sample_bookmark, "未知のエラー", "unknown_type", False)
        
        assert len(error_logger.errors) == 1
        # 未知のタイプはerror_countsに追加されない
        assert all(count == 0 for count in error_logger.error_counts.values())
        
        error_entry = error_logger.errors[0]
        assert error_entry['type'] == "unknown_type"


class TestWebScraperErrorHandling:
    """WebScraperのエラーハンドリングテスト"""
    
    @pytest.fixture
    def web_scraper(self):
        """WebScraperインスタンスを提供するフィクスチャ"""
        return WebScraper()
    
    def test_fetch_page_content_timeout_error(self, web_scraper):
        """タイムアウトエラーのテスト"""
        with patch.object(web_scraper.session, 'get') as mock_get:
            mock_get.side_effect = requests.exceptions.Timeout("タイムアウト")
            
            with pytest.raises(requests.exceptions.Timeout):
                web_scraper.fetch_page_content("https://example.com/timeout")
    
    def test_fetch_page_content_connection_error(self, web_scraper):
        """接続エラーのテスト"""
        with patch.object(web_scraper.session, 'get') as mock_get:
            mock_get.side_effect = requests.exceptions.ConnectionError("接続エラー")
            
            with pytest.raises(requests.exceptions.ConnectionError):
                web_scraper.fetch_page_content("https://example.com/connection-error")
    
    def test_fetch_page_content_http_error_403(self, web_scraper):
        """HTTP 403エラーのテスト"""
        with patch.object(web_scraper.session, 'get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 403
            mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(response=mock_response)
            mock_get.return_value = mock_response
            
            with pytest.raises(requests.exceptions.HTTPError) as exc_info:
                web_scraper.fetch_page_content("https://example.com/forbidden")
            
            assert "アクセスが拒否されました (403)" in str(exc_info.value)
    
    def test_fetch_page_content_http_error_404(self, web_scraper):
        """HTTP 404エラーのテスト"""
        with patch.object(web_scraper.session, 'get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 404
            mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(response=mock_response)
            mock_get.return_value = mock_response
            
            with pytest.raises(requests.exceptions.HTTPError) as exc_info:
                web_scraper.fetch_page_content("https://example.com/not-found")
            
            assert "ページが見つかりません (404)" in str(exc_info.value)
    
    def test_fetch_page_content_http_error_429(self, web_scraper):
        """HTTP 429エラーのテスト"""
        with patch.object(web_scraper.session, 'get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 429
            mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(response=mock_response)
            mock_get.return_value = mock_response
            
            with pytest.raises(requests.exceptions.HTTPError) as exc_info:
                web_scraper.fetch_page_content("https://example.com/rate-limited")
            
            assert "リクエスト制限に達しました (429)" in str(exc_info.value)
    
    def test_fetch_page_content_http_error_500(self, web_scraper):
        """HTTP 500エラーのテスト"""
        with patch.object(web_scraper.session, 'get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 500
            mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(response=mock_response)
            mock_get.return_value = mock_response
            
            with pytest.raises(requests.exceptions.HTTPError) as exc_info:
                web_scraper.fetch_page_content("https://example.com/server-error")
            
            assert "サーバーエラー (500)" in str(exc_info.value)
    
    def test_fetch_page_content_ssl_error(self, web_scraper):
        """SSL証明書エラーのテスト"""
        with patch.object(web_scraper.session, 'get') as mock_get:
            mock_get.side_effect = requests.exceptions.SSLError("SSL証明書エラー")
            
            with pytest.raises(requests.exceptions.SSLError):
                web_scraper.fetch_page_content("https://example.com/ssl-error")
    
    def test_fetch_page_content_small_content(self, web_scraper):
        """小さすぎるコンテンツのテスト"""
        with patch.object(web_scraper.session, 'get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.raise_for_status.return_value = None
            mock_response.encoding = 'utf-8'
            mock_response.text = "小さい"  # 100文字未満
            mock_get.return_value = mock_response
            
            with patch.object(web_scraper, 'check_robots_txt', return_value=True):
                with patch.object(web_scraper, 'apply_rate_limiting'):
                    result = web_scraper.fetch_page_content("https://example.com/small-content")
            
            assert result is None
    
    def test_fetch_page_content_success(self, web_scraper):
        """正常なページ取得のテスト"""
        with patch.object(web_scraper.session, 'get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.raise_for_status.return_value = None
            mock_response.encoding = 'utf-8'
            mock_response.text = "これは十分な長さのHTMLコンテンツです。" * 10  # 100文字以上
            mock_get.return_value = mock_response
            
            with patch.object(web_scraper, 'check_robots_txt', return_value=True):
                with patch.object(web_scraper, 'apply_rate_limiting'):
                    result = web_scraper.fetch_page_content("https://example.com/success")
            
            assert result is not None
            assert len(result) > 100
    
    def test_fetch_page_content_robots_txt_blocked(self, web_scraper):
        """robots.txtによるブロックのテスト"""
        with patch.object(web_scraper, 'check_robots_txt', return_value=False):
            result = web_scraper.fetch_page_content("https://example.com/blocked")
            
            assert result is None
    
    def test_fetch_page_content_unexpected_error(self, web_scraper):
        """予期しないエラーのテスト"""
        with patch.object(web_scraper.session, 'get') as mock_get:
            mock_get.side_effect = ValueError("予期しないエラー")
            
            with pytest.raises(Exception) as exc_info:
                web_scraper.fetch_page_content("https://example.com/unexpected")
            
            assert "予期しないエラーが発生しました" in str(exc_info.value)