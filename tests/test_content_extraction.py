"""
記事本文抽出とコンテンツ検証機能のテスト
Task 7の実装確認用
"""

import pytest
import sys
import os
from pathlib import Path
from bs4 import BeautifulSoup

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app import WebScraper


class TestContentExtraction:
    """記事本文抽出とコンテンツ検証機能のテストクラス"""
    
    @pytest.fixture
    def scraper(self):
        """WebScraperインスタンスを提供するフィクスチャ"""
        return WebScraper()
    
    def test_content_extraction_initialization(self, scraper):
        """記事本文抽出機能の初期化テスト"""
        # 新しいメソッドが存在することを確認
        assert hasattr(scraper, '_remove_unwanted_elements')
        assert hasattr(scraper, '_extract_title')
        assert hasattr(scraper, '_extract_metadata')
        assert hasattr(scraper, '_extract_tags')
        assert hasattr(scraper, '_extract_main_content')
        assert hasattr(scraper, '_validate_content_quality')
    
    def test_title_extraction(self, scraper):
        """タイトル抽出機能テスト"""
        # テスト用HTML
        test_html = """
        <html>
        <head>
            <title>テストページのタイトル</title>
            <meta property="og:title" content="OGタイトル">
        </head>
        <body>
            <h1>メインタイトル</h1>
            <div class="content">
                <p>記事の内容です。</p>
            </div>
        </body>
        </html>
        """
        
        soup = BeautifulSoup(test_html, 'html.parser')
        title = scraper._extract_title(soup, "https://example.com/test")
        
        # h1タグが優先されることを確認
        assert title == "メインタイトル"
    
    def test_title_extraction_fallback(self, scraper):
        """タイトル抽出のフォールバック機能テスト"""
        # h1タグがない場合のテスト
        test_html = """
        <html>
        <head>
            <title>HTMLタイトル</title>
        </head>
        <body>
            <div>コンテンツ</div>
        </body>
        </html>
        """
        
        soup = BeautifulSoup(test_html, 'html.parser')
        title = scraper._extract_title(soup, "https://example.com/test")
        
        # titleタグが使用されることを確認
        assert title == "HTMLタイトル"
    
    def test_metadata_extraction(self, scraper):
        """メタデータ抽出機能テスト"""
        # テスト用HTML
        test_html = """
        <html>
        <head>
            <meta name="description" content="テストページの説明">
            <meta name="keywords" content="テスト,記事,抽出">
            <meta name="author" content="テスト作者">
            <meta property="og:title" content="OGタイトル">
            <meta property="og:description" content="OG説明">
            <meta name="twitter:card" content="summary">
        </head>
        <body>
            <div>コンテンツ</div>
        </body>
        </html>
        """
        
        soup = BeautifulSoup(test_html, 'html.parser')
        metadata = scraper._extract_metadata(soup)
        
        # メタデータが正しく抽出されることを確認
        assert metadata['description'] == "テストページの説明"
        assert metadata['keywords'] == "テスト,記事,抽出"
        assert metadata['author'] == "テスト作者"
        assert metadata['og:title'] == "OGタイトル"
        assert metadata['og:description'] == "OG説明"
        assert metadata['twitter:card'] == "summary"
    
    def test_tags_extraction_from_html(self, scraper):
        """HTMLからのタグ抽出機能テスト"""
        # テスト用HTML
        test_html = """
        <html>
        <body>
            <div class="tags">
                <a href="/tag/python">Python</a>
                <a href="/tag/web-scraping">Web Scraping</a>
                <a href="/tag/ai">AI</a>
            </div>
        </body>
        </html>
        """
        
        soup = BeautifulSoup(test_html, 'html.parser')
        metadata = {}
        
        tags = scraper._extract_tags(soup, metadata)
        
        # タグが正しく抽出されることを確認
        assert 'Python' in tags
        assert any('Web' in tag and 'Scraping' in tag for tag in tags)
        assert 'AI' in tags
    
    def test_tags_extraction_from_keywords(self, scraper):
        """キーワードからのタグ抽出機能テスト"""
        soup = BeautifulSoup("<html><body></body></html>", 'html.parser')
        
        # メタデータにキーワードを含める
        metadata = {'keywords': 'プログラミング,開発,技術'}
        
        tags = scraper._extract_tags(soup, metadata)
        
        # キーワードからタグが抽出されることを確認
        assert 'プログラミング' in tags
        assert '開発' in tags
        assert '技術' in tags
    
    def test_content_cleaning(self, scraper):
        """コンテンツクリーニング機能テスト"""
        # テスト用テキスト（不要な空白や改行を含む）
        test_text = """これは    テスト    記事です。
        
        複数の段落が    あります。
        
        最後の段落です。"""
        
        cleaned = scraper._clean_content(test_text)
        
        # クリーニングが正しく行われることを確認
        assert "これは テスト 記事です。" in cleaned
        assert "複数の段落が あります。" in cleaned
        assert "最後の段落です。" in cleaned
        
        # 段落が正しく分離されることを確認
        lines = [line for line in cleaned.split('\n\n') if line.strip()]
        assert len(lines) == 3  # 3つの段落
    
    def test_content_quality_validation_good(self, scraper):
        """高品質コンテンツの品質検証テスト"""
        # 高品質なコンテンツ
        good_article = {
            'title': '良い記事のタイトル',
            'content': 'これは十分な長さの記事内容です。' * 10,  # 十分な長さ
            'quality_score': 0.8,
            'tags': ['tag1', 'tag2'],
            'metadata': {'description': '記事の説明'}
        }
        
        # 品質検証テスト
        assert scraper._validate_content_quality(good_article, "https://example.com/good") == True
    
    def test_content_quality_validation_bad(self, scraper):
        """低品質コンテンツの品質検証テスト"""
        # 低品質なコンテンツ
        bad_article = {
            'title': '',  # タイトルなし
            'content': '短い',  # 短すぎる
            'quality_score': 0.1,  # 低スコア
            'tags': [],
            'metadata': {}
        }
        
        # 品質検証テスト
        assert scraper._validate_content_quality(bad_article, "https://example.com/bad") == False
    
    def test_unwanted_elements_removal(self, scraper):
        """不要要素除去機能テスト"""
        # テスト用HTML（不要要素を含む）
        test_html = """
        <html>
        <body>
            <nav>ナビゲーション</nav>
            <script>console.log('script');</script>
            <style>.test { color: red; }</style>
            <div class="ads">広告</div>
            <article>
                <h1>記事タイトル</h1>
                <p>記事の内容</p>
            </article>
            <footer>フッター</footer>
        </body>
        </html>
        """
        
        soup = BeautifulSoup(test_html, 'html.parser')
        
        # 除去前の要素数を確認
        assert soup.find('nav') is not None
        assert soup.find('script') is not None
        assert soup.find('style') is not None
        assert soup.find(class_='ads') is not None
        
        # 不要要素を除去
        scraper._remove_unwanted_elements(soup)
        
        # 除去後の確認
        assert soup.find('nav') is None
        assert soup.find('script') is None
        assert soup.find('style') is None
        assert soup.find(class_='ads') is None
        
        # 記事要素は残っていることを確認
        assert soup.find('article') is not None
    
    def test_semantic_extraction(self, scraper):
        """セマンティック抽出機能テスト"""
        # テスト用HTML（articleタグを含む）
        test_html = """
        <html>
        <body>
            <article>
                <h1>記事タイトル</h1>
                <p>これは記事の本文です。十分な長さの内容を含んでいます。</p>
                <p>複数の段落があり、意味のあるコンテンツです。</p>
                <p>記事として適切な構造を持っています。</p>
            </article>
        </body>
        </html>
        """
        
        soup = BeautifulSoup(test_html, 'html.parser')
        
        # セマンティック抽出を実行
        result = scraper._extract_by_semantic_tags(soup)
        
        # 結果の確認
        assert result is not None
        assert result['quality_score'] == 0.9  # セマンティックタグは高品質
        assert '記事の本文です' in result['content']
    
    def test_content_density_extraction(self, scraper):
        """コンテンツ密度による抽出機能テスト"""
        # テスト用HTML
        test_html = """
        <html>
        <body>
            <div>
                <p>これは十分な長さの記事内容です。</p>
                <p>複数の段落があります。</p>
                <p>コンテンツ密度が高い記事です。</p>
                <p>リンクは少なく、テキストが多いです。</p>
                <a href="/link">少しのリンク</a>
            </div>
        </body>
        </html>
        """
        
        soup = BeautifulSoup(test_html, 'html.parser')
        
        # コンテンツ密度による抽出を実行
        result = scraper._extract_by_content_density(soup)
        
        # 結果の確認
        assert result is not None
        assert result['quality_score'] > 0.0
        assert 'これは十分な長さの記事内容です' in result['content']
    
    def test_full_extraction_pipeline(self, scraper):
        """完全な抽出パイプラインテスト"""
        # 実際のWebページ風のHTML
        test_html = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>テスト記事 - テストサイト</title>
            <meta name="description" content="これはテスト記事の説明です">
            <meta name="keywords" content="テスト,記事,Python">
            <meta property="og:title" content="テスト記事">
        </head>
        <body>
            <header>
                <nav>ナビゲーション</nav>
            </header>
            
            <main>
                <article>
                    <h1>テスト記事のタイトル</h1>
                    <div class="tags">
                        <a href="/tag/python">Python</a>
                        <a href="/tag/testing">Testing</a>
                    </div>
                    <div class="content">
                        <p>これはテスト記事の本文です。十分な長さと内容を持っています。</p>
                        <p>複数の段落があり、構造化されたコンテンツです。</p>
                        <p>記事として適切な品質を持っています。</p>
                        <p>抽出アルゴリズムのテストに使用されます。</p>
                    </div>
                </article>
            </main>
            
            <aside class="sidebar">
                <div class="ads">広告</div>
            </aside>
            
            <footer>フッター</footer>
        </body>
        </html>
        """
        
        # 完全な抽出を実行
        result = scraper.extract_article_content(test_html, "https://example.com/test-article")
        
        # 結果の確認
        assert result is not None
        assert result['title'] == "テスト記事のタイトル"
        assert 'テスト記事の本文です' in result['content']
        assert 'Python' in result['tags']
        assert 'Testing' in result['tags']
        assert result['metadata']['description'] == "これはテスト記事の説明です"
        assert result['quality_score'] > 0.5
        
        # 不要要素が除去されていることを確認
        assert 'ナビゲーション' not in result['content']
        assert '広告' not in result['content']
        assert 'フッター' not in result['content']
    
    def test_error_page_detection(self, scraper):
        """エラーページ検出テスト"""
        # エラーページのコンテンツ
        error_article = {
            'title': '404 Not Found',
            'content': 'Error 404: Page not found. The requested page does not exist.',
            'quality_score': 0.5,
            'tags': [],
            'metadata': {}
        }
        
        # エラーページは品質検証で除外されることを確認
        assert scraper._validate_content_quality(error_article, "https://example.com/404") == False
    
    def test_json_ld_metadata_extraction(self, scraper):
        """JSON-LD構造化データの抽出テスト"""
        # JSON-LDを含むHTML
        test_html = """
        <html>
        <head>
            <script type="application/ld+json">
            {
                "@type": "Article",
                "author": "テスト作者",
                "datePublished": "2024-01-01",
                "description": "構造化データの説明"
            }
            </script>
        </head>
        <body>
            <div>コンテンツ</div>
        </body>
        </html>
        """
        
        soup = BeautifulSoup(test_html, 'html.parser')
        metadata = scraper._extract_metadata(soup)
        
        # 構造化データが抽出されることを確認
        assert 'structured_author' in metadata
        assert 'structured_date' in metadata
        assert 'structured_description' in metadata
        assert metadata['structured_author'] == "テスト作者"
        assert metadata['structured_date'] == "2024-01-01"
        assert metadata['structured_description'] == "構造化データの説明"