"""
Markdown生成モジュール

このモジュールは、Obsidian形式のMarkdownファイル生成機能を提供します。
ブックマーク情報とWebコンテンツを基に、適切なメタデータを含む
Markdownファイルを生成します。
"""

import logging
import datetime
import re
from pathlib import Path
from typing import Dict, List, Any

from ..utils.models import Bookmark#
 ロガーの取得
logger = logging.getLogger(__name__)


class MarkdownGenerator:
    """
    Obsidian形式のMarkdown生成クラス
    
    ブックマーク情報とWebコンテンツを基に、Obsidian用のMarkdownファイルを生成します。
    YAML front matter、適切なメタデータ、タグ情報を含む高品質なMarkdownを出力します。
    """
    
    def __init__(self):
        """
        MarkdownGeneratorを初期化
        
        YAML front matterのテンプレートを設定し、Markdown生成の準備を行います。
        """
        self.yaml_template = {
            'title': '',
            'url': '',
            'created': '',
            'tags': [],
            'description': '',
            'author': '',
            'source': 'bookmark-to-obsidian'
        }
        
        logger.info("📝 MarkdownGenerator初期化完了")
    
    def generate_obsidian_markdown(self, page_data: Dict, bookmark: Bookmark) -> str:
        """
        ページデータからObsidian形式のMarkdownを生成
        
        WebScraperから抽出された記事データとブックマーク情報を基に、
        Obsidian用の完全なMarkdownドキュメントを生成します。
        
        Args:
            page_data: WebScraperから抽出された記事データ
            bookmark: ブックマーク情報
            
        Returns:
            str: Obsidian形式のMarkdownコンテンツ
        """
        try:
            # YAML front matterを生成
            yaml_frontmatter = self._create_yaml_frontmatter(page_data, bookmark)
            
            # 記事本文をMarkdown形式に変換
            markdown_content = self._format_content_for_obsidian(page_data.get('content', ''))
            
            # タグをObsidian形式に変換
            obsidian_tags = self._format_tags_for_obsidian(page_data.get('tags', []))
            
            # 完全なMarkdownを構築
            full_markdown = self._build_complete_markdown(
                yaml_frontmatter, 
                markdown_content, 
                obsidian_tags,
                page_data,
                bookmark
            )
            
            logger.debug(f"📝 Markdown生成成功: {bookmark.title} (文字数: {len(full_markdown)})")
            return full_markdown
            
        except Exception as e:
            logger.error(f"❌ Markdown生成エラー: {bookmark.title} - {str(e)}")
            return self._generate_fallback_markdown(bookmark)
    
    def generate_file_path(self, bookmark: Bookmark, base_path: Path, avoid_duplicates: bool = True) -> Path:
        """
        重複回避機能を強化したファイルパス生成
        
        ブックマークのフォルダ階層とタイトルを基に、適切なファイルパスを生成します。
        重複回避機能により、既存ファイルとの衝突を防ぎます。
        
        Args:
            bookmark: ブックマーク情報
            base_path: 基準パス
            avoid_duplicates: 重複回避を行うかどうか（デフォルト: True）
            
        Returns:
            Path: 生成されたファイルパス（重複回避済み）
        """
        try:
            # フォルダ階層を構築
            folder_parts = []
            if bookmark.folder_path:
                for folder in bookmark.folder_path:
                    # フォルダ名をファイルシステム用にサニタイズ
                    clean_folder = self._sanitize_path_component(folder)
                    if clean_folder:
                        folder_parts.append(clean_folder)
            
            # ファイル名を生成
            base_filename = self._sanitize_path_component(bookmark.title)
            if not base_filename:
                base_filename = "untitled"
            
            # ディレクトリパスを構築
            if folder_parts:
                directory_path = base_path / Path(*folder_parts)
            else:
                directory_path = base_path
            
            # 重複回避機能
            if avoid_duplicates:
                final_filename = self._generate_unique_filename(directory_path, base_filename, ".md")
            else:
                final_filename = base_filename + ".md"
            
            # 完全なパスを構築
            full_path = directory_path / final_filename
            
            logger.debug(f"📁 ファイルパス生成: {full_path}")
            return full_path
            
        except Exception as e:
            logger.error(f"❌ ファイルパス生成エラー: {bookmark.title} - {str(e)}")
            # フォールバック: ルートディレクトリに保存
            safe_filename = f"bookmark_{hash(bookmark.url) % 10000}.md"
            return base_path / safe_filename
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        MarkdownGenerator統計情報を取得
        
        Returns:
            Dict[str, Any]: 統計情報
                - yaml_template_keys: YAMLテンプレートのキー数
                - supported_formats: サポートする形式一覧
        """
        return {
            'yaml_template_keys': len(self.yaml_template),
            'supported_formats': ['obsidian', 'yaml', 'markdown']
        }
    
    # プライベートメソッド群
    
    def _create_yaml_frontmatter(self, page_data: Dict, bookmark: Bookmark) -> str:
        """
        YAML front matterを生成
        
        Args:
            page_data: 記事データ
            bookmark: ブックマーク情報
            
        Returns:
            str: YAML front matter文字列
        """
        # メタデータを準備
        yaml_data = self.yaml_template.copy()
        
        # 基本情報
        yaml_data['title'] = page_data.get('title', bookmark.title)
        yaml_data['url'] = bookmark.url
        yaml_data['created'] = datetime.datetime.now().isoformat()
        
        # タグ情報
        tags = page_data.get('tags', [])
        if tags:
            yaml_data['tags'] = tags
        
        # メタデータから追加情報を抽出
        metadata = page_data.get('metadata', {})
        if metadata.get('description'):
            yaml_data['description'] = metadata['description']
        if metadata.get('author'):
            yaml_data['author'] = metadata['author']
        
        # ブックマーク情報
        if bookmark.add_date:
            yaml_data['bookmarked'] = bookmark.add_date.isoformat()
        
        if bookmark.folder_path:
            yaml_data['folder'] = '/'.join(bookmark.folder_path)
        
        # 品質情報
        if 'quality_score' in page_data:
            yaml_data['quality_score'] = page_data['quality_score']
        if 'extraction_method' in page_data:
            yaml_data['extraction_method'] = page_data['extraction_method']
        
        # シンプルなYAML生成（yamlライブラリを使わない）
        return self._create_simple_yaml_frontmatter_dict(yaml_data)
    
    def _create_simple_yaml_frontmatter_dict(self, yaml_data: Dict) -> str:
        """
        辞書からシンプルなYAML front matterを生成
        
        Args:
            yaml_data: YAML用データ辞書
            
        Returns:
            str: YAML front matter文字列
        """
        lines = ["---"]
        
        for key, value in yaml_data.items():
            if value:  # 空でない値のみ
                if isinstance(value, list):
                    if value:  # 空でないリストのみ
                        lines.append(f"{key}:")
                        for item in value:
                            lines.append(f"  - \"{self._escape_yaml_string(str(item))}\"")
                elif isinstance(value, (int, float)):
                    lines.append(f"{key}: {value}")
                else:
                    lines.append(f"{key}: \"{self._escape_yaml_string(str(value))}\"")
        
        lines.append("---")
        return '\n'.join(lines) + '\n'
    
    def _escape_yaml_string(self, text: str) -> str:
        """
        YAML文字列をエスケープ
        
        Args:
            text: エスケープ対象の文字列
            
        Returns:
            str: エスケープされた文字列
        """
        if not text:
            return ""
        
        # 危険な文字をエスケープ
        text = text.replace('"', '\\"')
        text = text.replace('\n', '\\n')
        text = text.replace('\r', '\\r')
        text = text.replace('\t', '\\t')
        
        return text
    
    def _format_content_for_obsidian(self, content: str) -> str:
        """
        記事本文をObsidian用のMarkdown形式に変換
        
        Args:
            content: 元の記事本文
            
        Returns:
            str: Obsidian形式のMarkdown
        """
        if not content:
            return ""
        
        # 基本的なMarkdown変換
        formatted_content = content
        
        # 段落の整理
        paragraphs = [p.strip() for p in formatted_content.split('\n\n') if p.strip()]
        
        # Obsidian特有の処理
        processed_paragraphs = []
        for paragraph in paragraphs:
            # 長い段落を適切に分割
            if len(paragraph) > 500:
                sentences = self._split_into_sentences(paragraph)
                processed_paragraphs.extend(sentences)
            else:
                processed_paragraphs.append(paragraph)
        
        # 最終的なMarkdownを構築
        markdown_content = '\n\n'.join(processed_paragraphs)
        
        # Obsidian特有の記法を適用
        markdown_content = self._apply_obsidian_formatting(markdown_content)
        
        return markdown_content
    
    def _split_into_sentences(self, text: str) -> List[str]:
        """
        長いテキストを文単位で分割
        
        Args:
            text: 分割対象のテキスト
            
        Returns:
            List[str]: 分割された文のリスト
        """
        # 日本語と英語の文区切りパターン
        sentence_patterns = [
            r'[。！？]',  # 日本語の文末
            r'[.!?](?:\s|$)',  # 英語の文末
        ]
        
        sentences = []
        current_sentence = ""
        
        for char in text:
            current_sentence += char
            
            # 文末パターンをチェック
            for pattern in sentence_patterns:
                if re.search(pattern, current_sentence[-2:]):
                    if len(current_sentence.strip()) > 10:  # 最小文字数
                        sentences.append(current_sentence.strip())
                        current_sentence = ""
                    break
        
        # 残りのテキストを追加
        if current_sentence.strip():
            sentences.append(current_sentence.strip())
        
        return sentences
    
    def _apply_obsidian_formatting(self, content: str) -> str:
        """
        Obsidian特有のフォーマットを適用
        
        Args:
            content: 元のコンテンツ
            
        Returns:
            str: Obsidian形式のコンテンツ
        """
        # URLを自動リンク化（既存のMarkdownリンクは除外）
        # 既存のMarkdownリンクを保護するため、まず既存のリンクを検出
        existing_links = re.findall(r'\[([^\]]+)\]\(([^)]+)\)', content)
        
        # 既存のリンク以外のHTTPSリンクを検出してObsidian形式に変換
        # ただし、既にMarkdownリンク内にあるURLは変換しない
        def replace_url(match):
            url = match.group()
            # 既存のリンク内のURLかチェック
            for link_text, link_url in existing_links:
                if url in link_url:
                    return url  # 既存のリンク内なので変換しない
            return f"[{url}]({url})"
        
        # 単独のURLのみを変換（Markdownリンク内でないもの）
        url_pattern = r'(?<!\]\()https?://[^\s<>"\']+[^\s<>"\'.,;:!?](?!\))'
        content = re.sub(url_pattern, replace_url, content)
        
        return content
    
    def _format_tags_for_obsidian(self, tags: List[str]) -> str:
        """
        タグをObsidian形式（#タグ名）に変換
        
        Args:
            tags: タグのリスト
            
        Returns:
            str: Obsidian形式のタグ文字列
        """
        if not tags:
            return ""
        
        obsidian_tags = []
        
        for tag in tags:
            # タグのクリーニング
            clean_tag = self._clean_tag_for_obsidian(tag)
            if clean_tag:
                obsidian_tags.append(f"#{clean_tag}")
        
        if obsidian_tags:
            return "\n\n## タグ\n\n" + " ".join(obsidian_tags)
        
        return ""
    
    def _clean_tag_for_obsidian(self, tag: str) -> str:
        """
        タグをObsidian用にクリーニング
        
        Args:
            tag: 元のタグ
            
        Returns:
            str: クリーニングされたタグ
        """
        if not tag:
            return ""
        
        clean_tag = tag.strip()
        
        # スペースをハイフンに変換
        clean_tag = re.sub(r'\s+', '-', clean_tag)
        
        # 特殊文字をハイフンに変換（スラッシュ、ドットなど）
        clean_tag = re.sub(r'[/\\.+]', '-', clean_tag)
        
        # 許可されない文字を除去（英数字、日本語、ハイフン、アンダースコアのみ）
        clean_tag = re.sub(r'[^\w\-ぁ-んァ-ヶ一-龯]', '', clean_tag)
        
        # 先頭と末尾のハイフンを除去
        clean_tag = clean_tag.strip('-_')
        
        # 長すぎる場合は切り詰め
        if len(clean_tag) > 50:
            clean_tag = clean_tag[:50]
        
        return clean_tag
    
    def _build_complete_markdown(self, yaml_frontmatter: str, content: str, tags: str, page_data: Dict, bookmark: Bookmark) -> str:
        """
        完全なMarkdownドキュメントを構築
        
        Args:
            yaml_frontmatter: YAML front matter
            content: 記事本文
            tags: Obsidianタグ
            page_data: 記事データ
            bookmark: ブックマーク情報
            
        Returns:
            str: 完全なMarkdownドキュメント
        """
        sections = [yaml_frontmatter]
        
        # タイトル
        title = page_data.get('title', bookmark.title)
        sections.append(f"# {title}\n")
        
        # 元URL情報
        sections.append(f"**元URL:** [{bookmark.url}]({bookmark.url})\n")
        
        # ブックマーク日時
        if bookmark.add_date:
            sections.append(f"**ブックマーク日時:** {bookmark.add_date.strftime('%Y-%m-%d %H:%M:%S')}\n")
        
        # フォルダ情報
        if bookmark.folder_path:
            folder_path = ' > '.join(bookmark.folder_path)
            sections.append(f"**フォルダ:** {folder_path}\n")
        
        # 記事本文
        if content:
            sections.append("## 記事内容\n")
            sections.append(content)
        
        # タグセクション
        if tags:
            sections.append(tags)
        
        # メタデータセクション
        metadata = page_data.get('metadata', {})
        if metadata:
            sections.append("\n## メタデータ\n")
            
            if metadata.get('description'):
                sections.append(f"**説明:** {metadata['description']}\n")
            
            if metadata.get('author'):
                sections.append(f"**著者:** {metadata['author']}\n")
            
            # 品質情報
            if 'quality_score' in page_data:
                sections.append(f"**品質スコア:** {page_data['quality_score']:.2f}\n")
            
            if 'extraction_method' in page_data:
                sections.append(f"**抽出方法:** {page_data['extraction_method']}\n")
        
        # セクションを結合
        return '\n'.join(sections)
    
    def _generate_fallback_markdown(self, bookmark: Bookmark) -> str:
        """
        フォールバック用のシンプルなMarkdownを生成
        
        Args:
            bookmark: ブックマーク情報
            
        Returns:
            str: フォールバック用Markdown
        """
        lines = [
            "---",
            f"title: \"{self._escape_yaml_string(bookmark.title)}\"",
            f"url: \"{bookmark.url}\"",
            f"created: \"{datetime.datetime.now().isoformat()}\"",
            "source: \"bookmark-to-obsidian\"",
            "status: \"extraction_failed\"",
            "---",
            "",
            f"# {bookmark.title}",
            "",
            f"**元URL:** [{bookmark.url}]({bookmark.url})",
            "",
            "## 注意",
            "",
            "このページの内容を自動抽出できませんでした。",
            "元のURLにアクセスして内容を確認してください。",
            ""
        ]
        
        if bookmark.add_date:
            lines.insert(-3, f"**ブックマーク日時:** {bookmark.add_date.strftime('%Y-%m-%d %H:%M:%S')}")
        
        if bookmark.folder_path:
            folder_path = ' > '.join(bookmark.folder_path)
            lines.insert(-3, f"**フォルダ:** {folder_path}")
        
        return '\n'.join(lines)
    
    def _generate_unique_filename(self, directory: Path, base_name: str, extension: str) -> str:
        """
        重複を回避したユニークなファイル名を生成
        
        Args:
            directory: 保存先ディレクトリ
            base_name: 基本ファイル名
            extension: 拡張子
            
        Returns:
            str: ユニークなファイル名
        """
        # 基本ファイル名をチェック
        original_filename = base_name + extension
        full_path = directory / original_filename
        
        if not full_path.exists():
            return original_filename
        
        # 重複がある場合、番号を付けて回避
        counter = 1
        while True:
            numbered_filename = f"{base_name}_{counter:03d}{extension}"
            full_path = directory / numbered_filename
            
            if not full_path.exists():
                logger.info(f"🔄 重複回避: {original_filename} → {numbered_filename}")
                return numbered_filename
            
            counter += 1
            
            # 安全のため、1000回を超えたら強制終了
            if counter > 1000:
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                fallback_filename = f"{base_name}_{timestamp}{extension}"
                logger.warning(f"⚠️ 重複回避上限到達、タイムスタンプ使用: {fallback_filename}")
                return fallback_filename
    
    def _sanitize_path_component(self, name: str) -> str:
        """
        パス要素をファイルシステム用にサニタイズ
        
        Args:
            name: 元の名前
            
        Returns:
            str: サニタイズされた名前
        """
        if not name:
            return ""
        
        # 危険な文字を除去・置換
        sanitized = re.sub(r'[<>:"/\\|?*]', '_', name)
        
        # 連続するアンダースコアを単一に
        sanitized = re.sub(r'_+', '_', sanitized)
        
        # 前後の空白とアンダースコアを除去
        sanitized = sanitized.strip(' _.')
        
        # 長すぎる場合は切り詰め
        if len(sanitized) > 100:
            sanitized = sanitized[:100]
        
        # 予約語をチェック（Windows）
        reserved_names = ['CON', 'PRN', 'AUX', 'NUL', 'COM1', 'COM2', 'COM3', 'COM4', 'COM5', 'COM6', 'COM7', 'COM8', 'COM9', 'LPT1', 'LPT2', 'LPT3', 'LPT4', 'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9']
        if sanitized.upper() in reserved_names:
            sanitized = f"_{sanitized}"
        
        return sanitized