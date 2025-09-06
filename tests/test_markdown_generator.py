"""
Obsidian形式Markdown生成機能のテスト
Task 8の実装確認用
"""

import pytest
import sys
import os
from pathlib import Path
from datetime import datetime

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app import MarkdownGenerator, Bookmark


class TestMarkdownGenerator:
    """Obsidian形式Markdown生成機能のテストクラス"""
    
    @pytest.fixture
    def generator(self):
        """MarkdownGeneratorインスタンスを提供するフィクスチャ"""
        return MarkdownGenerator()
    
    @pytest.fixture
    def sample_bookmark(self):
        """サンプルブックマークを提供するフィクスチャ"""
        return Bookmark(
            title="テスト記事のタイトル",
            url="https://example.com/test-article",
            folder_path=["技術", "Python"],
            add_date=datetime(2024, 1, 1, 12, 0, 0)
        )
    
    @pytest.fixture
    def sample_page_data(self):
        """サンプルページデータを提供するフィクスチャ"""
        return {
            'title': 'テスト記事のタイトル',
            'content': 'これはテスト記事の本文です。\n\n複数の段落があります。\n\n最後の段落です。',
            'tags': ['Python', 'テスト', 'プログラミング'],
            'metadata': {
                'description': 'テスト記事の説明',
                'author': 'テスト作者',
                'keywords': 'Python,テスト'
            },
            'quality_score': 0.85,
            'extraction_method': 'semantic_tags'
        }
    
    def test_markdown_generator_initialization(self, generator):
        """MarkdownGenerator初期化テスト"""
        assert hasattr(generator, 'yaml_template')
        assert hasattr(generator, 'generate_obsidian_markdown')
        assert hasattr(generator, 'generate_file_path')
        assert generator.yaml_template['source'] == 'bookmark-to-obsidian'
    
    def test_yaml_frontmatter_creation(self, generator, sample_page_data, sample_bookmark):
        """YAML front matter生成テスト"""
        yaml_frontmatter = generator._create_yaml_frontmatter(sample_page_data, sample_bookmark)
        
        # YAML構造の確認
        assert yaml_frontmatter.startswith('---\n')
        assert yaml_frontmatter.endswith('---\n')
        
        # 必要な情報が含まれていることを確認
        assert 'title: "テスト記事のタイトル"' in yaml_frontmatter
        assert 'url: "https://example.com/test-article"' in yaml_frontmatter
        assert 'source: "bookmark-to-obsidian"' in yaml_frontmatter
        assert 'description: "テスト記事の説明"' in yaml_frontmatter
        assert 'author: "テスト作者"' in yaml_frontmatter
        assert 'quality_score: 0.85' in yaml_frontmatter
        
        # タグが正しく含まれていることを確認
        assert 'tags:' in yaml_frontmatter
        assert '- "Python"' in yaml_frontmatter
        assert '- "テスト"' in yaml_frontmatter
    
    def test_yaml_string_escaping(self, generator):
        """YAML文字列エスケープテスト"""
        # 特殊文字を含む文字列
        test_string = 'テスト"引用符\n改行\tタブ'
        escaped = generator._escape_yaml_string(test_string)
        
        assert '\\"' in escaped  # 引用符がエスケープされている
        assert '\\n' in escaped  # 改行がエスケープされている
        assert '\\t' in escaped  # タブがエスケープされている
    
    def test_content_formatting_for_obsidian(self, generator):
        """Obsidian用コンテンツフォーマットテスト"""
        test_content = "これはテスト記事です。\n\nhttps://example.com のリンクがあります。\n\n最後の段落です。"
        
        formatted = generator._format_content_for_obsidian(test_content)
        
        # URLが自動リンク化されていることを確認
        assert '[https://example.com](https://example.com)' in formatted
        
        # 段落構造が保持されていることを確認
        assert 'これはテスト記事です。' in formatted
        assert '最後の段落です。' in formatted
    
    def test_tags_formatting_for_obsidian(self, generator):
        """Obsidianタグフォーマットテスト"""
        test_tags = ['Python', 'Web Scraping', 'テスト記事', 'AI/ML']
        
        formatted_tags = generator._format_tags_for_obsidian(test_tags)
        
        # タグセクションが生成されていることを確認
        assert '## タグ' in formatted_tags
        
        # Obsidian形式のタグが生成されていることを確認
        assert '#Python' in formatted_tags
        assert '#Web-Scraping' in formatted_tags  # スペースがハイフンに変換
        assert '#テスト記事' in formatted_tags
        assert '#AI-ML' in formatted_tags  # スラッシュがハイフンに変換
    
    def test_tag_cleaning_for_obsidian(self, generator):
        """Obsidianタグクリーニングテスト"""
        # 様々な特殊文字を含むタグ
        test_cases = [
            ('Python 3.9', 'Python-3-9'),
            ('Web/API', 'Web-API'),
            ('C++', 'C'),
            ('データ分析', 'データ分析'),
            ('  spaced  ', 'spaced'),
            ('', ''),
            ('very-long-tag-name-that-exceeds-fifty-characters-limit', 'very-long-tag-name-that-exceeds-fifty-characters-l')
        ]
        
        for input_tag, expected in test_cases:
            result = generator._clean_tag_for_obsidian(input_tag)
            assert result == expected, f"Input: '{input_tag}' -> Expected: '{expected}', Got: '{result}'"
    
    def test_sentence_splitting(self, generator):
        """文分割機能テスト"""
        long_text = "これは長い文章です。複数の文が含まれています！最後の文もあります？"
        
        sentences = generator._split_into_sentences(long_text)
        
        # 適切に分割されていることを確認
        assert len(sentences) >= 2
        assert any('長い文章です。' in s for s in sentences)
        assert any('含まれています！' in s for s in sentences)
        assert any('あります？' in s for s in sentences)
    
    def test_complete_markdown_generation(self, generator, sample_page_data, sample_bookmark):
        """完全なMarkdown生成テスト"""
        markdown = generator.generate_obsidian_markdown(sample_page_data, sample_bookmark)
        
        # YAML front matterが含まれていることを確認
        assert markdown.startswith('---\n')
        
        # タイトルが含まれていることを確認
        assert '# テスト記事のタイトル' in markdown
        
        # 元URL情報が含まれていることを確認
        assert '**元URL:**' in markdown
        assert 'https://example.com/test-article' in markdown
        
        # ブックマーク日時が含まれていることを確認
        assert '**ブックマーク日時:**' in markdown
        assert '2024-01-01' in markdown
        
        # フォルダ情報が含まれていることを確認
        assert '**フォルダ:**' in markdown
        assert '技術 > Python' in markdown
        
        # 記事内容が含まれていることを確認
        assert '## 記事内容' in markdown
        assert 'これはテスト記事の本文です。' in markdown
        
        # タグが含まれていることを確認
        assert '## タグ' in markdown
        assert '#Python' in markdown
        
        # メタデータが含まれていることを確認
        assert '## メタデータ' in markdown
        assert '**説明:**' in markdown
        assert '**著者:**' in markdown
        assert '**品質スコア:**' in markdown
    
    def test_fallback_markdown_generation(self, generator, sample_bookmark):
        """フォールバックMarkdown生成テスト"""
        fallback_markdown = generator._generate_fallback_markdown(sample_bookmark)
        
        # 基本構造が含まれていることを確認
        assert fallback_markdown.startswith('---\n')
        assert '# テスト記事のタイトル' in fallback_markdown
        assert '**元URL:**' in fallback_markdown
        assert 'status: "extraction_failed"' in fallback_markdown
        
        # 注意メッセージが含まれていることを確認
        assert '## 注意' in fallback_markdown
        assert '自動抽出できませんでした' in fallback_markdown
    
    def test_file_path_generation(self, generator, sample_bookmark):
        """ファイルパス生成テスト"""
        base_path = Path("/test/base")
        
        file_path = generator.generate_file_path(sample_bookmark, base_path)
        
        # 正しいパス構造が生成されていることを確認
        expected_path = base_path / "技術" / "Python" / "テスト記事のタイトル.md"
        assert file_path == expected_path
    
    def test_file_path_generation_no_folder(self, generator):
        """フォルダなしブックマークのファイルパス生成テスト"""
        bookmark = Bookmark(
            title="ルート記事",
            url="https://example.com/root",
            folder_path=[]
        )
        base_path = Path("/test/base")
        
        file_path = generator.generate_file_path(bookmark, base_path)
        
        # ルートディレクトリに配置されることを確認
        expected_path = base_path / "ルート記事.md"
        assert file_path == expected_path
    
    def test_path_component_sanitization(self, generator):
        """パス要素サニタイズテスト"""
        test_cases = [
            ('正常なファイル名', '正常なファイル名'),
            ('危険な<>:"/\\|?*文字', '危険な_文字'),
            ('  前後スペース  ', '前後スペース'),
            ('連続___アンダースコア', '連続_アンダースコア'),
            ('', ''),
            ('CON', '_CON'),  # Windows予約語
        ]
        
        for input_name, expected in test_cases:
            result = generator._sanitize_path_component(input_name)
            assert result == expected, f"Input: '{input_name}' -> Expected: '{expected}', Got: '{result}'"
        
        # 長いファイル名のテスト（別途）
        long_name = 'very-long-filename-that-exceeds-one-hundred-characters-and-should-be-truncated-automatically'
        result = generator._sanitize_path_component(long_name)
        assert len(result) <= 100, f"Result length {len(result)} should be <= 100"
        assert result.startswith('very-long-filename'), "Should start with expected prefix"
    
    def test_statistics(self, generator):
        """統計情報取得テスト"""
        stats = generator.get_statistics()
        
        # 統計情報の構造確認
        assert 'yaml_template_keys' in stats
        assert 'supported_formats' in stats
        
        # 値の確認
        assert stats['yaml_template_keys'] > 0
        assert 'obsidian' in stats['supported_formats']
        assert 'yaml' in stats['supported_formats']
        assert 'markdown' in stats['supported_formats']
    
    def test_empty_content_handling(self, generator, sample_bookmark):
        """空コンテンツの処理テスト"""
        empty_page_data = {
            'title': 'タイトルのみ',
            'content': '',
            'tags': [],
            'metadata': {}
        }
        
        markdown = generator.generate_obsidian_markdown(empty_page_data, sample_bookmark)
        
        # 基本構造は生成されることを確認
        assert '# タイトルのみ' in markdown
        assert '**元URL:**' in markdown
        
        # 空のセクションは含まれないことを確認
        assert '## 記事内容' not in markdown or markdown.count('## 記事内容') == 0
        assert '## タグ' not in markdown
    
    def test_special_characters_in_content(self, generator, sample_bookmark):
        """コンテンツ内特殊文字の処理テスト"""
        special_page_data = {
            'title': 'Special Characters Test',
            'content': 'Content with **bold**, *italic*, `code`, and [links](https://example.com)',
            'tags': ['markdown', 'formatting'],
            'metadata': {}
        }
        
        markdown = generator.generate_obsidian_markdown(special_page_data, sample_bookmark)
        
        # Markdown記法が保持されていることを確認
        assert '**bold**' in markdown
        assert '*italic*' in markdown
        assert '`code`' in markdown
        # 既存のリンクが保持されていることを確認（自動リンク化で壊されていない）
        assert 'links](https://example.com)' in markdown