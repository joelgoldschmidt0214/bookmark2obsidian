"""
Bookmark to Obsidian Converter
Streamlitベースのデスクトップアプリケーション
Google Chromeのbookmarks.htmlファイルを解析し、Obsidian用のMarkdownファイルを生成する
"""

import streamlit as st
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from enum import Enum
import datetime
import os
import re
import logging
import time
import requests
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser
from bs4 import BeautifulSoup

# Task 10: 強化されたログ設定とエラーログ記録機能
# 環境変数DEBUG=1を設定するとデバッグログも表示
log_level = logging.DEBUG if os.getenv('DEBUG') == '1' else logging.INFO

# ログファイルの設定
log_directory = Path("logs")
log_directory.mkdir(exist_ok=True)

# ログファイル名（日付付き）
log_filename = log_directory / f"bookmark2obsidian_{datetime.datetime.now().strftime('%Y%m%d')}.log"

# ログハンドラーの設定
handlers = [
    logging.StreamHandler(),  # コンソール出力
    logging.FileHandler(log_filename, encoding='utf-8')  # ファイル出力
]

logging.basicConfig(
    level=log_level,
    format='%(asctime)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s',
    handlers=handlers
)
logger = logging.getLogger(__name__)

logger.info(f"🚀 アプリケーション開始 (ログレベル: {logging.getLevelName(log_level)})")
logger.info(f"📝 ログファイル: {log_filename}")


class ErrorLogger:
    """Task 10: エラーログ記録と管理クラス"""
    
    def __init__(self):
        self.errors = []
        self.error_counts = {
            'network': 0,
            'timeout': 0,
            'fetch': 0,
            'extraction': 0,
            'markdown': 0,
            'permission': 0,
            'filesystem': 0,
            'save': 0,
            'unexpected': 0
        }
    
    def log_error(self, bookmark: 'Bookmark', error_msg: str, error_type: str, retryable: bool = False):
        """
        エラーを記録
        
        Args:
            bookmark: エラーが発生したブックマーク
            error_msg: エラーメッセージ
            error_type: エラータイプ
            retryable: リトライ可能かどうか
        """
        error_entry = {
            'timestamp': datetime.datetime.now(),
            'bookmark': bookmark,
            'error': error_msg,
            'type': error_type,
            'retryable': retryable,
            'url': bookmark.url,
            'title': bookmark.title
        }
        
        self.errors.append(error_entry)
        
        if error_type in self.error_counts:
            self.error_counts[error_type] += 1
        
        # ログファイルにも記録
        logger.error(f"[{error_type.upper()}] {bookmark.title} - {error_msg}")
    
    def get_error_summary(self) -> Dict[str, Any]:
        """エラーサマリーを取得"""
        return {
            'total_errors': len(self.errors),
            'error_counts': self.error_counts.copy(),
            'retryable_count': sum(1 for error in self.errors if error['retryable']),
            'recent_errors': self.errors[-10:] if self.errors else []
        }
    
    def get_retryable_errors(self) -> List[Dict]:
        """リトライ可能なエラーを取得"""
        return [error for error in self.errors if error['retryable']]
    
    def clear_errors(self):
        """エラーログをクリア"""
        self.errors.clear()
        self.error_counts = {key: 0 for key in self.error_counts}


# グローバルエラーログインスタンス
error_logger = ErrorLogger()


# データモデル定義
class PageStatus(Enum):
    PENDING = "pending"
    FETCHING = "fetching"
    SUCCESS = "success"
    EXCLUDED = "excluded"
    ERROR = "error"


@dataclass
class Bookmark:
    title: str
    url: str
    folder_path: List[str]
    add_date: Optional[datetime.datetime] = None
    icon: Optional[str] = None


@dataclass
class Page:
    bookmark: Bookmark
    content: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    metadata: Dict = field(default_factory=dict)
    is_selected: bool = True
    status: PageStatus = PageStatus.PENDING


class LocalDirectoryManager:
    """
    ローカルディレクトリの構造を解析し、重複チェックを行うクラス
    """
    
    def __init__(self, base_path: Path):
        """
        LocalDirectoryManagerを初期化
        
        Args:
            base_path: 基準となるディレクトリパス
        """
        self.base_path = Path(base_path)
        self.existing_structure = {}
        self.duplicate_files = set()
    
    def scan_directory(self, path: Optional[str] = None) -> Dict[str, List[str]]:
        """
        指定されたディレクトリの既存ファイル構造を読み取る
        
        Args:
            path: スキャン対象のパス（Noneの場合はbase_pathを使用）
            
        Returns:
            Dict[str, List[str]]: ディレクトリパスをキーとしたファイル名一覧
        """
        scan_path = Path(path) if path else self.base_path
        
        if not scan_path.exists() or not scan_path.is_dir():
            return {}
        
        structure = {}
        
        try:
            # ディレクトリを再帰的にスキャン
            for root, dirs, files in os.walk(scan_path):
                # 相対パスを計算
                relative_root = Path(root).relative_to(scan_path)
                relative_path = str(relative_root) if str(relative_root) != '.' else ''
                
                # Markdownファイルのみを対象とする
                markdown_files = [
                    Path(f).stem for f in files 
                    if f.lower().endswith(('.md', '.markdown'))
                ]
                
                if markdown_files:
                    structure[relative_path] = markdown_files
            
            self.existing_structure = structure
            return structure
            
        except Exception as e:
            raise RuntimeError(f"ディレクトリスキャンエラー: {str(e)}")
    
    def check_file_exists(self, path: str, filename: str) -> bool:
        """
        指定されたパスにファイルが存在するかチェック
        
        Args:
            path: ディレクトリパス
            filename: ファイル名（拡張子なし）
            
        Returns:
            bool: ファイルが存在する場合True
        """
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            # パスを正規化
            normalized_path = path.replace('\\', '/') if path else ''
            
            logger.debug(f"    ファイル存在チェック: パス='{normalized_path}', ファイル名='{filename}'")
            logger.debug(f"    既存構造: {self.existing_structure}")
            
            # 既存構造から確認
            if normalized_path in self.existing_structure:
                exists_in_structure = filename in self.existing_structure[normalized_path]
                logger.debug(f"    構造内チェック結果: {exists_in_structure}")
                if exists_in_structure:
                    return True
            
            # 実際のファイルシステムからも確認
            full_path = self.base_path / path if path else self.base_path
            if full_path.exists():
                md_file = full_path / f"{filename}.md"
                markdown_file = full_path / f"{filename}.markdown"
                file_exists = md_file.exists() or markdown_file.exists()
                logger.debug(f"    ファイルシステムチェック: {md_file} → {md_file.exists()}")
                logger.debug(f"    ファイルシステムチェック: {markdown_file} → {markdown_file.exists()}")
                return file_exists
            
            logger.debug(f"    結果: ファイル存在しない")
            return False
            
        except Exception as e:
            logger.error(f"    ファイル存在チェックエラー: {e}")
            return False
    
    def compare_with_bookmarks(self, bookmarks: List[Bookmark]) -> Dict[str, List[str]]:
        """
        ブックマーク階層と既存ディレクトリ構造を比較し、重複ファイルを特定
        
        Args:
            bookmarks: ブックマーク一覧
            
        Returns:
            Dict[str, List[str]]: 重複ファイルの情報
        """
        import logging
        logger = logging.getLogger(__name__)
        
        duplicates = {
            'files': [],  # 重複ファイル一覧
            'paths': []   # 重複パス一覧
        }
        
        self.duplicate_files.clear()
        
        logger.info(f"重複チェック対象: {len(bookmarks)}個のブックマーク")
        
        for i, bookmark in enumerate(bookmarks):
            # フォルダパスを文字列に変換
            folder_path = '/'.join(bookmark.folder_path) if bookmark.folder_path else ''
            
            # ファイル名を生成（BookmarkParserと同じロジック）
            filename = self._sanitize_filename(bookmark.title)
            
            logger.debug(f"  {i+1}. チェック中: '{bookmark.title}' → '{filename}' (パス: '{folder_path}')")
            
            # 重複チェック
            file_exists = self.check_file_exists(folder_path, filename)
            logger.debug(f"     ファイル存在チェック結果: {file_exists}")
            
            if file_exists:
                duplicate_info = f"{folder_path}/{filename}" if folder_path else filename
                duplicates['files'].append(duplicate_info)
                duplicates['paths'].append(folder_path)
                
                # 重複ファイルセットに追加
                self.duplicate_files.add((folder_path, filename))
                logger.info(f"  🔄 重複検出: {duplicate_info}")
        
        logger.info(f"重複チェック完了: {len(duplicates['files'])}個の重複を検出")
        return duplicates
    
    def is_duplicate(self, bookmark: Bookmark) -> bool:
        """
        指定されたブックマークが重複ファイルかどうかを判定
        
        Args:
            bookmark: 判定対象のブックマーク
            
        Returns:
            bool: 重複ファイルの場合True
        """
        folder_path = '/'.join(bookmark.folder_path) if bookmark.folder_path else ''
        filename = self._sanitize_filename(bookmark.title)
        
        return (folder_path, filename) in self.duplicate_files
    
    def get_duplicate_count(self) -> int:
        """
        重複ファイル数を取得
        
        Returns:
            int: 重複ファイル数
        """
        return len(self.duplicate_files)
    
    def create_directory_structure(self, base_path: str, structure: Dict) -> None:
        """
        ディレクトリ構造を自動作成
        
        Args:
            base_path: 基準パス
            structure: 作成するディレクトリ構造
        """
        try:
            base = Path(base_path)
            
            for folder_path in structure.keys():
                if folder_path:  # 空文字列でない場合
                    full_path = base / folder_path
                    full_path.mkdir(parents=True, exist_ok=True)
                    
        except Exception as e:
            raise RuntimeError(f"ディレクトリ作成エラー: {str(e)}")
    
    def save_markdown_file(self, path: str, content: str) -> bool:
        """
        Markdownファイルをローカルディレクトリに保存
        
        Args:
            path: 保存先パス（base_pathからの相対パス）
            content: ファイル内容
            
        Returns:
            bool: 保存成功の場合True
        """
        try:
            full_path = self.base_path / path
            
            # ディレクトリが存在しない場合は作成
            full_path.parent.mkdir(parents=True, exist_ok=True)
            
            # ファイルを保存
            with open(full_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            return True
            
        except Exception as e:
            raise RuntimeError(f"ファイル保存エラー: {str(e)}")
    
    def _sanitize_filename(self, title: str) -> str:
        """
        タイトルから安全なファイル名を生成（BookmarkParserと同じロジック）
        
        Args:
            title: 元のタイトル
            
        Returns:
            str: 安全なファイル名
        """
        # 危険な文字を除去・置換（スペースは保持）
        filename = re.sub(r'[<>:"/\\|?*]', '_', title)
        
        # 連続するアンダースコアを単一に
        filename = re.sub(r'_+', '_', filename)
        
        # 前後の空白とアンダースコアを除去
        filename = filename.strip(' _')
        
        # 空の場合はデフォルト名を使用
        if not filename:
            filename = 'untitled'
        
        # 長すぎる場合は切り詰め（拡張子を考慮して200文字以内）
        if len(filename) > 200:
            filename = filename[:200]
        
        return filename
    
    def get_statistics(self) -> Dict[str, int]:
        """
        ディレクトリ統計情報を取得
        
        Returns:
            Dict[str, int]: 統計情報
        """
        total_files = sum(len(files) for files in self.existing_structure.values())
        total_directories = len(self.existing_structure)
        
        return {
            'total_files': total_files,
            'total_directories': total_directories,
            'duplicate_files': len(self.duplicate_files)
        }


class BookmarkParser:
    """
    bookmarks.htmlファイルを解析してブックマーク情報を抽出するクラス
    """
    
    def __init__(self):
        self.excluded_domains = set()
        self.excluded_urls = set()
    
    def parse_bookmarks(self, html_content: str) -> List[Bookmark]:
        """
        HTMLコンテンツからブックマーク一覧を抽出する
        
        Args:
            html_content: bookmarks.htmlの内容
            
        Returns:
            List[Bookmark]: 抽出されたブックマーク一覧
        """
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            bookmarks = []
            
            # ルートDLエレメントから開始
            root_dl = soup.find('dl')
            if root_dl:
                bookmarks = self._parse_dl_element(root_dl, [])
            
            return bookmarks
            
        except Exception as e:
            raise ValueError(f"ブックマーク解析エラー: {str(e)}")
    
    def _parse_dl_element(self, dl_element, current_path: List[str], processed_dls=None) -> List[Bookmark]:
        """
        DLエレメントを愚直に解析してブックマークを抽出
        
        Args:
            dl_element: BeautifulSoupのDLエレメント
            current_path: 現在のフォルダパス
            processed_dls: 処理済みのDLエレメントのセット
            
        Returns:
            List[Bookmark]: 抽出されたブックマーク一覧
        """
        if processed_dls is None:
            processed_dls = set()
        
        # 既に処理済みの場合はスキップ
        if id(dl_element) in processed_dls:
            return []
        
        # 処理済みとしてマーク
        processed_dls.add(id(dl_element))
        
        bookmarks = []
        
        # DLエレメント内のDTを処理（Pタグ内にある場合も考慮）
        # まず、このDLレベルのDTエレメントを取得
        all_dt_in_dl = dl_element.find_all('dt')
        
        # このDLの直接の子DTエレメントのみを取得（pタグ内も含む）
        direct_dt_elements = []
        for child in dl_element.children:
            if hasattr(child, 'name'):
                if child.name == 'dt':
                    direct_dt_elements.append(child)
                elif child.name == 'p':
                    # P要素内のすべてのDTエレメントを取得（ネストしたDL内のものは除く）
                    all_p_dts = child.find_all('dt')
                    
                    # ネストしたDL内のDTを除外
                    nested_dls_in_p = child.find_all('dl')
                    nested_dt_in_p = set()
                    for nested_dl in nested_dls_in_p:
                        nested_dt_in_p.update(nested_dl.find_all('dt'))
                    
                    p_dt_elements = [dt for dt in all_p_dts if dt not in nested_dt_in_p]
                    direct_dt_elements.extend(p_dt_elements)
        
        for dt in direct_dt_elements:
            # DTの次の兄弟要素がDDかどうかをチェック
            next_sibling = dt.find_next_sibling()
            
            if next_sibling and next_sibling.name == 'dd':
                # DTの後にDDがある場合 → フォルダ構造
                h3 = dt.find('h3')
                if h3:
                    folder_name = h3.get_text(strip=True)
                    new_path = current_path + [folder_name]
                    
                    # DD内のDLを再帰的に処理
                    nested_dl = next_sibling.find('dl')
                    if nested_dl:
                        nested_bookmarks = self._parse_dl_element(nested_dl, new_path, processed_dls)
                        bookmarks.extend(nested_bookmarks)
            else:
                # DTの後にDDがない場合の処理
                # H3タグがあり、内部にDLがある場合はフォルダとして処理
                h3 = dt.find('h3')
                internal_dl = dt.find('dl')
                
                if h3 and internal_dl:
                    # DTの内部にフォルダ構造がある場合（ブックマークバーなど）
                    folder_name = h3.get_text(strip=True)
                    new_path = current_path + [folder_name]
                    nested_bookmarks = self._parse_dl_element(internal_dl, new_path, processed_dls)
                    bookmarks.extend(nested_bookmarks)
                else:
                    # 通常のブックマーク
                    a_tag = dt.find('a')
                    if a_tag:
                        bookmark = self._extract_bookmark_from_a_tag(a_tag, current_path)
                        if bookmark and not self._should_exclude_bookmark(bookmark):
                            bookmarks.append(bookmark)
        
        return bookmarks
    

    
    def _extract_bookmark_from_a_tag(self, a_tag, folder_path: List[str]) -> Optional[Bookmark]:
        """
        Aタグからブックマーク情報を抽出
        
        Args:
            a_tag: BeautifulSoupのAエレメント
            folder_path: フォルダパス
            
        Returns:
            Optional[Bookmark]: 抽出されたブックマーク（除外対象の場合はNone）
        """
        try:
            url = a_tag.get('href', '').strip()
            title = a_tag.get_text(strip=True)
            
            if not url or not title:
                return None
            
            # 日付の解析（ADD_DATE属性）
            add_date = None
            add_date_str = a_tag.get('add_date')
            if add_date_str:
                try:
                    # Unix timestampから変換
                    add_date = datetime.datetime.fromtimestamp(int(add_date_str))
                except (ValueError, TypeError):
                    pass
            
            # アイコン情報の取得
            icon = a_tag.get('icon')
            
            return Bookmark(
                title=title,
                url=url,
                folder_path=folder_path,
                add_date=add_date,
                icon=icon
            )
            
        except Exception as e:
            # 個別のブックマーク解析エラーは警告レベルで処理
            return None
    
    def _should_exclude_bookmark(self, bookmark: Bookmark) -> bool:
        """
        ブックマークを除外すべきかどうかを判定
        
        Args:
            bookmark: 判定対象のブックマーク
            
        Returns:
            bool: 除外すべき場合True
        """
        # ドメインルートURLの除外
        if self._is_domain_root_url(bookmark.url):
            return True
        
        # 無効なURLの除外
        if not self._is_valid_url(bookmark.url):
            return True
        
        # 除外リストに含まれるURLの除外
        if bookmark.url in self.excluded_urls:
            return True
        
        # 除外ドメインの確認
        try:
            parsed_url = urlparse(bookmark.url)
            domain = parsed_url.netloc.lower()
            if domain in self.excluded_domains:
                return True
        except Exception:
            return True
        
        return False
    
    def _is_domain_root_url(self, url: str) -> bool:
        """
        URLがドメインのルートかどうかを判定
        
        Args:
            url: 判定対象のURL
            
        Returns:
            bool: ドメインルートの場合True
        """
        try:
            parsed = urlparse(url)
            # パスが空、または「/」のみの場合はルートと判定
            path = parsed.path.strip('/')
            is_root = len(path) == 0 and not parsed.query and not parsed.fragment
            return is_root
        except Exception:
            return False
    
    def _is_valid_url(self, url: str) -> bool:
        """
        URLが有効かどうかを判定
        
        Args:
            url: 判定対象のURL
            
        Returns:
            bool: 有効なURLの場合True
        """
        try:
            parsed = urlparse(url)
            # スキームとネットロケーションが存在することを確認
            return bool(parsed.scheme and parsed.netloc)
        except Exception:
            return False
    
    def extract_directory_structure(self, bookmarks: List[Bookmark]) -> Dict[str, List[str]]:
        """
        ブックマークからディレクトリ構造を抽出
        
        Args:
            bookmarks: ブックマーク一覧
            
        Returns:
            Dict[str, List[str]]: ディレクトリパスをキーとしたファイル名一覧
        """
        structure = {}
        
        for bookmark in bookmarks:
            # フォルダパスを文字列に変換
            folder_path = '/'.join(bookmark.folder_path) if bookmark.folder_path else ''
            
            # ファイル名を生成（タイトルから安全なファイル名を作成）
            filename = self._sanitize_filename(bookmark.title)
            
            if folder_path not in structure:
                structure[folder_path] = []
            
            structure[folder_path].append(filename)
        
        return structure
    
    def _sanitize_filename(self, title: str) -> str:
        """
        タイトルから安全なファイル名を生成
        
        Args:
            title: 元のタイトル
            
        Returns:
            str: 安全なファイル名
        """
        # 危険な文字を除去・置換（スペースは保持）
        filename = re.sub(r'[<>:"/\\|?*]', '_', title)
        
        # 連続するアンダースコアを単一に
        filename = re.sub(r'_+', '_', filename)
        
        # 前後の空白とアンダースコアを除去
        filename = filename.strip(' _')
        
        # 空の場合はデフォルト名を使用
        if not filename:
            filename = 'untitled'
        
        # 長すぎる場合は切り詰め（拡張子を考慮して200文字以内）
        if len(filename) > 200:
            filename = filename[:200]
        
        return filename
    
    def add_excluded_domain(self, domain: str) -> None:
        """除外ドメインを追加"""
        self.excluded_domains.add(domain.lower())
    
    def add_excluded_url(self, url: str) -> None:
        """除外URLを追加"""
        self.excluded_urls.add(url)
    
    def get_statistics(self, bookmarks: List[Bookmark]) -> Dict[str, int]:
        """
        ブックマーク統計情報を取得
        
        Args:
            bookmarks: ブックマーク一覧
            
        Returns:
            Dict[str, int]: 統計情報
        """
        total_bookmarks = len(bookmarks)
        unique_domains = len(set(urlparse(b.url).netloc for b in bookmarks))
        folder_count = len(set('/'.join(b.folder_path) for b in bookmarks if b.folder_path))
        
        return {
            'total_bookmarks': total_bookmarks,
            'unique_domains': unique_domains,
            'folder_count': folder_count
        }


class WebScraper:
    """
    Webページ取得・解析クラス
    robots.txt確認、レート制限、記事本文抽出機能を提供
    """
    
    def __init__(self):
        """WebScraperを初期化"""
        self.domain_last_access = {}  # ドメインごとの最終アクセス時刻
        self.rate_limit_delay = 3  # デフォルトの待ち時間（秒）
        self.timeout = 10  # リクエストタイムアウト（秒）
        self.user_agent = "Mozilla/5.0 (compatible; BookmarkToObsidian/1.0; +https://github.com/user/bookmark-to-obsidian)"
        
        # セッション設定
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': self.user_agent,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'ja,en-US;q=0.7,en;q=0.3',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })
        
        logger.info(f"🌐 WebScraper初期化完了 (User-Agent: {self.user_agent})")
    
    def check_robots_txt(self, domain: str) -> bool:
        """
        指定されたドメインのrobots.txtを確認し、スクレイピングが許可されているかチェック
        
        Args:
            domain: 確認対象のドメイン
            
        Returns:
            bool: スクレイピングが許可されている場合True
        """
        try:
            robots_url = f"https://{domain}/robots.txt"
            logger.debug(f"🤖 robots.txt確認: {robots_url}")
            
            # RobotFileParserを使用してrobots.txtを解析
            rp = RobotFileParser()
            rp.set_url(robots_url)
            
            # robots.txtを読み込み（タイムアウト付き）
            try:
                rp.read()
                
                # User-Agentに対してアクセス許可をチェック
                # 一般的なクローラー名とカスタムUser-Agentの両方をチェック
                user_agents_to_check = [
                    self.user_agent,
                    "*",  # 全てのUser-Agent
                    "Mozilla/5.0",  # 一般的なブラウザ
                ]
                
                for ua in user_agents_to_check:
                    if rp.can_fetch(ua, "/"):
                        logger.debug(f"✅ robots.txt許可: {domain} (User-Agent: {ua})")
                        return True
                
                logger.info(f"🚫 robots.txt拒否: {domain}")
                return False
                
            except Exception as e:
                # robots.txtが存在しない、またはアクセスできない場合は許可とみなす
                logger.debug(f"⚠️ robots.txt読み込みエラー（許可として処理）: {domain} - {str(e)}")
                return True
                
        except Exception as e:
            # エラーが発生した場合は安全側に倒して許可とみなす
            logger.debug(f"⚠️ robots.txtチェックエラー（許可として処理）: {domain} - {str(e)}")
            return True
    
    def fetch_page_content(self, url: str) -> Optional[str]:
        """
        Task 10: エラーハンドリングを強化したページ取得機能
        
        Args:
            url: 取得対象のURL
            
        Returns:
            Optional[str]: 取得されたHTMLコンテンツ（失敗時はNone）
            
        Raises:
            requests.exceptions.ConnectionError: ネットワーク接続エラー
            requests.exceptions.Timeout: タイムアウトエラー
            requests.exceptions.HTTPError: HTTPエラー
            requests.exceptions.SSLError: SSL証明書エラー
        """
        try:
            # URLの解析
            parsed_url = urlparse(url)
            domain = parsed_url.netloc.lower()
            
            logger.debug(f"🌐 ページ取得開始: {url}")
            
            # robots.txtチェック
            if not self.check_robots_txt(domain):
                logger.info(f"🚫 robots.txt拒否によりスキップ: {url}")
                return None
            
            # レート制限の適用
            self.apply_rate_limiting(domain)
            
            # HTTPリクエストの実行（エラーハンドリング強化）
            try:
                response = self.session.get(
                    url,
                    timeout=self.timeout,
                    allow_redirects=True,
                    verify=True  # SSL証明書検証を有効化
                )
                
                # ステータスコードの確認
                response.raise_for_status()
                
            except requests.exceptions.Timeout as e:
                logger.warning(f"⏰ タイムアウト: {url} (timeout={self.timeout}s)")
                raise requests.exceptions.Timeout(f"ページ取得がタイムアウトしました: {url}")
                
            except requests.exceptions.SSLError as e:
                logger.warning(f"🔒 SSL証明書エラー: {url}")
                raise requests.exceptions.SSLError(f"SSL証明書の検証に失敗しました: {url}")
                
            except requests.exceptions.ConnectionError as e:
                logger.warning(f"🔌 接続エラー: {url}")
                raise requests.exceptions.ConnectionError(f"ネットワーク接続に失敗しました: {url}")
                
            except requests.exceptions.HTTPError as e:
                status_code = e.response.status_code if e.response else "不明"
                logger.warning(f"🚫 HTTPエラー: {url} - ステータスコード: {status_code}")
                
                # 特定のHTTPエラーに対する詳細メッセージ
                if status_code == 403:
                    raise requests.exceptions.HTTPError(f"アクセスが拒否されました (403): {url}")
                elif status_code == 404:
                    raise requests.exceptions.HTTPError(f"ページが見つかりません (404): {url}")
                elif status_code == 429:
                    raise requests.exceptions.HTTPError(f"リクエスト制限に達しました (429): {url}")
                elif status_code >= 500:
                    raise requests.exceptions.HTTPError(f"サーバーエラー ({status_code}): {url}")
                else:
                    raise requests.exceptions.HTTPError(f"HTTPエラー ({status_code}): {url}")
            
            # 文字エンコーディングの自動検出
            if response.encoding is None:
                response.encoding = response.apparent_encoding
            
            # HTMLコンテンツを取得
            html_content = response.text
            
            # コンテンツサイズの検証
            if len(html_content) < 100:
                logger.warning(f"⚠️ コンテンツサイズが小さすぎます: {url} (サイズ: {len(html_content)} 文字)")
                return None
            
            logger.debug(f"✅ ページ取得成功: {url} (サイズ: {len(html_content):,} 文字)")
            
            # 最終アクセス時刻を更新
            self.domain_last_access[domain] = time.time()
            
            return html_content
            
        except (requests.exceptions.Timeout, 
                requests.exceptions.ConnectionError, 
                requests.exceptions.HTTPError, 
                requests.exceptions.SSLError):
            # 既知のネットワークエラーは再発生させる
            raise
            
        except Exception as e:
            logger.error(f"❌ 予期しないページ取得エラー: {url} - {str(e)}")
            raise Exception(f"予期しないエラーが発生しました: {str(e)}")
    
    def extract_article_content(self, html: str, url: str = "") -> Optional[Dict]:
        """
        HTMLから記事本文とメタデータを抽出（高度な抽出アルゴリズム）
        
        Args:
            html: HTMLコンテンツ
            url: 元のURL（ログ用）
            
        Returns:
            Optional[Dict]: 抽出された記事データ（失敗時はNone）
        """
        try:
            soup = BeautifulSoup(html, 'html.parser')
            
            # 記事データの初期化
            article_data = {
                'title': '',
                'content': '',
                'tags': [],
                'metadata': {},
                'quality_score': 0.0,
                'extraction_method': ''
            }
            
            # 不要な要素を事前に除去
            self._remove_unwanted_elements(soup)
            
            # タイトルの抽出（複数の方法を試行）
            article_data['title'] = self._extract_title(soup, url)
            
            # メタデータの抽出
            article_data['metadata'] = self._extract_metadata(soup)
            
            # タグ情報の抽出
            article_data['tags'] = self._extract_tags(soup, article_data['metadata'])
            
            # 記事本文の抽出（複数のアルゴリズムを試行）
            content_result = self._extract_main_content(soup, url)
            
            if content_result:
                article_data['content'] = content_result['content']
                article_data['quality_score'] = content_result['quality_score']
                article_data['extraction_method'] = content_result['method']
                
                # コンテンツ品質の検証
                if self._validate_content_quality(article_data, url):
                    logger.debug(f"✅ 記事本文抽出成功: {url} (文字数: {len(article_data['content'])}, 品質スコア: {article_data['quality_score']:.2f}, 方法: {article_data['extraction_method']})")
                    return article_data
                else:
                    logger.warning(f"⚠️ コンテンツ品質が基準を満たしません: {url}")
                    return None
            else:
                logger.warning(f"⚠️ 記事本文が見つかりません: {url}")
                return None
                
        except Exception as e:
            logger.error(f"❌ 記事本文抽出エラー: {url} - {str(e)}")
            return None
    
    def _remove_unwanted_elements(self, soup: BeautifulSoup) -> None:
        """
        不要な要素を除去（広告、ナビゲーション、スクリプトなど）
        
        Args:
            soup: BeautifulSoupオブジェクト
        """
        # 除去対象のセレクタ
        unwanted_selectors = [
            # スクリプトとスタイル
            'script', 'style', 'noscript',
            
            # ナビゲーション要素
            'nav', 'header', 'footer', 'aside',
            '.navigation', '.navbar', '.nav-menu', '.menu',
            '.breadcrumb', '.breadcrumbs',
            
            # 広告関連
            '.advertisement', '.ads', '.ad', '.advert',
            '.google-ads', '.adsense', '.ad-container',
            '[id*="ad"]', '[class*="ad-"]', '[class*="ads-"]',
            
            # ソーシャル・共有ボタン
            '.share-buttons', '.social-share', '.social-buttons',
            '.share', '.sharing', '.social-media',
            
            # コメント・関連記事
            '.comments', '.comment-section', '.disqus',
            '.related-posts', '.related-articles', '.recommendations',
            
            # サイドバー・ウィジェット
            '.sidebar', '.widget', '.widgets',
            
            # その他の不要要素
            '.popup', '.modal', '.overlay',
            '.newsletter', '.subscription',
            '.cookie-notice', '.cookie-banner',
            '.back-to-top', '.scroll-to-top'
        ]
        
        for selector in unwanted_selectors:
            for element in soup.select(selector):
                element.decompose()
    
    def _extract_title(self, soup: BeautifulSoup, url: str) -> str:
        """
        ページタイトルを抽出（複数の方法を試行）
        
        Args:
            soup: BeautifulSoupオブジェクト
            url: 元のURL
            
        Returns:
            str: 抽出されたタイトル
        """
        # タイトル抽出の優先順位
        title_selectors = [
            'h1',  # メインタイトル
            'title',  # HTMLタイトル
            '[property="og:title"]',  # Open Graphタイトル
            '.title', '.post-title', '.article-title',
            '.entry-title', '.page-title'
        ]
        
        for selector in title_selectors:
            elements = soup.select(selector)
            for element in elements:
                if selector == '[property="og:title"]':
                    title = element.get('content', '').strip()
                else:
                    title = element.get_text(strip=True)
                
                if title and len(title) > 5:  # 最小文字数チェック
                    # タイトルのクリーニング
                    title = re.sub(r'\s+', ' ', title)  # 連続する空白を単一に
                    title = title.replace('\n', ' ').replace('\t', ' ')
                    return title[:200]  # 最大200文字に制限
        
        # タイトルが見つからない場合はURLから生成
        from urllib.parse import urlparse
        parsed_url = urlparse(url)
        return f"記事 - {parsed_url.netloc}"
    
    def _extract_metadata(self, soup: BeautifulSoup) -> Dict[str, str]:
        """
        メタデータを抽出
        
        Args:
            soup: BeautifulSoupオブジェクト
            
        Returns:
            Dict[str, str]: 抽出されたメタデータ
        """
        metadata = {}
        
        # メタタグから情報を抽出
        meta_tags = soup.find_all('meta')
        for meta in meta_tags:
            name = meta.get('name', '').lower()
            property_attr = meta.get('property', '').lower()
            content = meta.get('content', '').strip()
            
            if content:
                # 標準的なメタタグ
                if name in ['description', 'keywords', 'author', 'robots', 'viewport']:
                    metadata[name] = content
                
                # Open Graphタグ
                elif property_attr.startswith('og:'):
                    metadata[property_attr] = content
                
                # Articleタグ
                elif property_attr.startswith('article:'):
                    metadata[property_attr] = content
                
                # Twitterカード
                elif name.startswith('twitter:'):
                    metadata[name] = content
        
        # 構造化データ（JSON-LD）の抽出
        json_ld_scripts = soup.find_all('script', type='application/ld+json')
        for script in json_ld_scripts:
            try:
                import json
                data = json.loads(script.string)
                if isinstance(data, dict):
                    if data.get('@type') in ['Article', 'BlogPosting', 'NewsArticle']:
                        if 'author' in data:
                            metadata['structured_author'] = str(data['author'])
                        if 'datePublished' in data:
                            metadata['structured_date'] = data['datePublished']
                        if 'description' in data:
                            metadata['structured_description'] = data['description']
            except (json.JSONDecodeError, AttributeError):
                continue
        
        return metadata
    
    def _extract_tags(self, soup: BeautifulSoup, metadata: Dict[str, str]) -> List[str]:
        """
        タグ情報を抽出
        
        Args:
            soup: BeautifulSoupオブジェクト
            metadata: メタデータ
            
        Returns:
            List[str]: 抽出されたタグ一覧
        """
        tags = set()
        
        # メタデータのキーワードから抽出
        keywords = metadata.get('keywords', '')
        if keywords:
            # カンマ区切りのキーワードを分割
            keyword_list = [kw.strip() for kw in keywords.split(',') if kw.strip()]
            tags.update(keyword_list)
        
        # HTMLからタグ要素を抽出
        tag_selectors = [
            '.tags a', '.tag a', '.categories a', '.category a',
            '.labels a', '.label a', '.topics a', '.topic a',
            '[rel="tag"]', '.post-tags a', '.entry-tags a'
        ]
        
        for selector in tag_selectors:
            elements = soup.select(selector)
            for element in elements:
                tag_text = element.get_text(strip=True)
                if tag_text and len(tag_text) <= 50:  # 最大50文字のタグのみ
                    # タグのクリーニング
                    tag_text = re.sub(r'[^\w\s\-_]', '', tag_text)  # 特殊文字を除去
                    tag_text = re.sub(r'\s+', '-', tag_text.strip())  # スペースをハイフンに
                    if tag_text:
                        tags.add(tag_text)
        
        # タグ数を制限（最大20個）
        return list(tags)[:20]
    
    def _extract_main_content(self, soup: BeautifulSoup, url: str) -> Optional[Dict]:
        """
        メインコンテンツを抽出（複数のアルゴリズムを試行）
        
        Args:
            soup: BeautifulSoupオブジェクト
            url: 元のURL
            
        Returns:
            Optional[Dict]: 抽出結果（content, quality_score, method）
        """
        extraction_methods = [
            ('semantic_tags', self._extract_by_semantic_tags),
            ('content_density', self._extract_by_content_density),
            ('common_selectors', self._extract_by_common_selectors),
            ('body_fallback', self._extract_by_body_fallback)
        ]
        
        best_result = None
        best_score = 0.0
        
        for method_name, method_func in extraction_methods:
            try:
                result = method_func(soup)
                if result and result['quality_score'] > best_score:
                    best_result = result
                    best_score = result['quality_score']
                    best_result['method'] = method_name
                    
                    # 十分に高品質なコンテンツが見つかった場合は早期終了
                    if best_score >= 0.8:
                        break
                        
            except Exception as e:
                logger.debug(f"抽出方法 {method_name} でエラー: {str(e)}")
                continue
        
        return best_result
    
    def _extract_by_semantic_tags(self, soup: BeautifulSoup) -> Optional[Dict]:
        """
        セマンティックタグを使用した抽出
        """
        semantic_selectors = ['article', 'main', '[role="main"]']
        
        for selector in semantic_selectors:
            elements = soup.select(selector)
            if elements:
                # 最も長いコンテンツを選択
                best_element = max(elements, key=lambda x: len(x.get_text()))
                content = self._clean_content(best_element.get_text())
                
                if len(content) > 50:  # 閾値を下げる
                    return {
                        'content': content,
                        'quality_score': 0.9,  # セマンティックタグは高品質
                        'method': 'semantic_tags'
                    }
        
        return None
    
    def _extract_by_content_density(self, soup: BeautifulSoup) -> Optional[Dict]:
        """
        コンテンツ密度による抽出
        """
        # 各要素のコンテンツ密度を計算
        candidates = []
        
        for element in soup.find_all(['div', 'section', 'article']):
            text = element.get_text(strip=True)
            if len(text) < 50:  # 閾値を下げる
                continue
            
            # リンク密度を計算（リンクテキスト / 全テキスト）
            link_text = ''.join([a.get_text() for a in element.find_all('a')])
            link_density = len(link_text) / len(text) if text else 1.0
            
            # 段落数を計算
            paragraphs = len(element.find_all('p'))
            
            # 品質スコアを計算
            quality_score = (
                min(len(text) / 500, 1.0) * 0.4 +  # 文字数（最大500文字で1.0）
                (1.0 - link_density) * 0.4 +  # リンク密度が低いほど高スコア
                min(paragraphs / 3, 1.0) * 0.2  # 段落数（最大3段落で1.0）
            )
            
            candidates.append({
                'element': element,
                'text': text,
                'quality_score': quality_score
            })
        
        if candidates:
            # 最高スコアの要素を選択
            best_candidate = max(candidates, key=lambda x: x['quality_score'])
            content = self._clean_content(best_candidate['text'])
            
            return {
                'content': content,
                'quality_score': best_candidate['quality_score'],
                'method': 'content_density'
            }
        
        return None
    
    def _extract_by_common_selectors(self, soup: BeautifulSoup) -> Optional[Dict]:
        """
        一般的なセレクタによる抽出
        """
        common_selectors = [
            '.content', '.post-content', '.entry-content',
            '.article-content', '#content', '#main-content',
            '.main-content', '.post-body', '.entry-body',
            '.article-body', '.content-body'
        ]
        
        for selector in common_selectors:
            elements = soup.select(selector)
            if elements:
                best_element = max(elements, key=lambda x: len(x.get_text()))
                content = self._clean_content(best_element.get_text())
                
                if len(content) > 100:
                    return {
                        'content': content,
                        'quality_score': 0.7,  # 中程度の品質
                        'method': 'common_selectors'
                    }
        
        return None
    
    def _extract_by_body_fallback(self, soup: BeautifulSoup) -> Optional[Dict]:
        """
        bodyタグからのフォールバック抽出
        """
        body = soup.find('body')
        if body:
            content = self._clean_content(body.get_text())
            
            if len(content) > 200:
                return {
                    'content': content,
                    'quality_score': 0.3,  # 低品質（フォールバック）
                    'method': 'body_fallback'
                }
        
        return None
    
    def _clean_content(self, text: str) -> str:
        """
        テキストコンテンツをクリーニング
        
        Args:
            text: 元のテキスト
            
        Returns:
            str: クリーニング済みテキスト
        """
        if not text:
            return ""
        
        # 連続する空白を単一のスペースに
        text = re.sub(r'[ \t]+', ' ', text)
        
        # 行ごとに処理
        lines = []
        for line in text.split('\n'):
            line = line.strip()
            if line and len(line) > 3:  # 短すぎる行は除外
                lines.append(line)
        
        # 段落として結合
        content = '\n\n'.join(lines)
        
        # 最大文字数制限（10,000文字）
        if len(content) > 10000:
            content = content[:10000] + "..."
        
        return content
    
    def _validate_content_quality(self, article_data: Dict, url: str) -> bool:
        """
        コンテンツ品質を検証
        
        Args:
            article_data: 記事データ
            url: 元のURL
            
        Returns:
            bool: 品質基準を満たす場合True
        """
        content = article_data.get('content', '')
        quality_score = article_data.get('quality_score', 0.0)
        
        # 基本的な品質チェック
        checks = {
            'min_length': len(content) >= 100,  # 最小100文字
            'max_length': len(content) <= 50000,  # 最大50,000文字
            'quality_score': quality_score >= 0.3,  # 最小品質スコア
            'has_title': bool(article_data.get('title', '').strip()),  # タイトル存在
            'reasonable_structure': content.count('\n') >= 2  # 最低限の構造
        }
        
        # すべてのチェックをパス
        passed_checks = sum(checks.values())
        total_checks = len(checks)
        
        success_rate = passed_checks / total_checks
        
        if success_rate < 0.8:  # 80%以上のチェックをパスする必要
            logger.debug(f"品質チェック失敗: {url} - {checks}")
            return False
        
        # 特定のパターンをチェック（エラーページなど）
        error_patterns = [
            r'404.*not found',
            r'page not found',
            r'access denied',
            r'forbidden',
            r'error occurred'
        ]
        
        content_lower = content.lower()
        for pattern in error_patterns:
            if re.search(pattern, content_lower):
                logger.debug(f"エラーページパターン検出: {url} - {pattern}")
                return False
        
        return True
    
    def group_urls_by_domain(self, urls: List[str]) -> Dict[str, List[str]]:
        """
        URLリストをドメインごとにグループ化
        
        Args:
            urls: URL一覧
            
        Returns:
            Dict[str, List[str]]: ドメインをキーとしたURL一覧
        """
        domain_groups = {}
        
        for url in urls:
            try:
                parsed_url = urlparse(url)
                domain = parsed_url.netloc.lower()
                
                if domain not in domain_groups:
                    domain_groups[domain] = []
                
                domain_groups[domain].append(url)
                
            except Exception as e:
                logger.warning(f"⚠️ URL解析エラー: {url} - {str(e)}")
                continue
        
        logger.info(f"🌐 ドメイングループ化完了: {len(domain_groups)}個のドメイン")
        for domain, domain_urls in domain_groups.items():
            logger.debug(f"  📍 {domain}: {len(domain_urls)}個のURL")
        
        return domain_groups
    
    def apply_rate_limiting(self, domain: str) -> None:
        """
        指定されたドメインに対してレート制限を適用
        
        Args:
            domain: 対象ドメイン
        """
        current_time = time.time()
        
        if domain in self.domain_last_access:
            time_since_last_access = current_time - self.domain_last_access[domain]
            
            if time_since_last_access < self.rate_limit_delay:
                sleep_time = self.rate_limit_delay - time_since_last_access
                logger.debug(f"⏳ レート制限待機: {domain} ({sleep_time:.1f}秒)")
                time.sleep(sleep_time)
        
        # 最終アクセス時刻を更新
        self.domain_last_access[domain] = time.time()
    
    def set_rate_limit_delay(self, delay: float) -> None:
        """
        レート制限の待ち時間を設定
        
        Args:
            delay: 待ち時間（秒）
        """
        self.rate_limit_delay = max(1.0, delay)  # 最小1秒
        logger.info(f"⏳ レート制限設定: {self.rate_limit_delay}秒")
    
    def set_timeout(self, timeout: int) -> None:
        """
        リクエストタイムアウトを設定
        
        Args:
            timeout: タイムアウト時間（秒）
        """
        self.timeout = max(5, timeout)  # 最小5秒
        logger.info(f"⏰ タイムアウト設定: {self.timeout}秒")
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        WebScraper統計情報を取得
        
        Returns:
            Dict[str, Any]: 統計情報
        """
        return {
            'domains_accessed': len(self.domain_last_access),
            'rate_limit_delay': self.rate_limit_delay,
            'timeout': self.timeout,
            'user_agent': self.user_agent
        }


class MarkdownGenerator:
    """
    Obsidian形式のMarkdown生成クラス
    記事データからObsidian用のMarkdownファイルを生成する
    """
    
    def __init__(self):
        """MarkdownGeneratorを初期化"""
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
    
    def generate_obsidian_markdown(self, page_data: Dict, bookmark: 'Bookmark') -> str:
        """
        ページデータからObsidian形式のMarkdownを生成
        
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
    
    def _create_yaml_frontmatter(self, page_data: Dict, bookmark: 'Bookmark') -> str:
        """
        YAML front matterを生成
        
        Args:
            page_data: 記事データ
            bookmark: ブックマーク情報
            
        Returns:
            str: YAML front matter文字列
        """
        import datetime
        
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
        import re
        
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
        import re
        
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
        import re
        
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
    
    def _build_complete_markdown(self, yaml_frontmatter: str, content: str, tags: str, page_data: Dict, bookmark: 'Bookmark') -> str:
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
    
    def _generate_fallback_markdown(self, bookmark: 'Bookmark') -> str:
        """
        フォールバック用のシンプルなMarkdownを生成
        
        Args:
            bookmark: ブックマーク情報
            
        Returns:
            str: フォールバック用Markdown
        """
        import datetime
        
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
    
    def generate_file_path(self, bookmark: 'Bookmark', base_path: Path) -> Path:
        """
        ブックマーク階層構造を維持したファイルパスを生成
        
        Args:
            bookmark: ブックマーク情報
            base_path: 基準パス
            
        Returns:
            Path: 生成されたファイルパス
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
            filename = self._sanitize_path_component(bookmark.title)
            if not filename:
                filename = "untitled"
            
            # 拡張子を追加
            filename += ".md"
            
            # 完全なパスを構築
            if folder_parts:
                full_path = base_path / Path(*folder_parts) / filename
            else:
                full_path = base_path / filename
            
            logger.debug(f"📁 ファイルパス生成: {full_path}")
            return full_path
            
        except Exception as e:
            logger.error(f"❌ ファイルパス生成エラー: {bookmark.title} - {str(e)}")
            # フォールバック: ルートディレクトリに保存
            safe_filename = f"bookmark_{hash(bookmark.url) % 10000}.md"
            return base_path / safe_filename
    
    def _sanitize_path_component(self, name: str) -> str:
        """
        パス要素をファイルシステム用にサニタイズ
        
        Args:
            name: 元の名前
            
        Returns:
            str: サニタイズされた名前
        """
        import re
        
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
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        MarkdownGenerator統計情報を取得
        
        Returns:
            Dict[str, Any]: 統計情報
        """
        return {
            'yaml_template_keys': len(self.yaml_template),
            'supported_formats': ['obsidian', 'yaml', 'markdown']
        }


def validate_bookmarks_file(uploaded_file) -> tuple[bool, str]:
    """
    アップロードされたファイルがbookmarks.htmlとして有効かを検証する
    
    Returns:
        tuple[bool, str]: (検証結果, エラーメッセージまたは成功メッセージ)
    """
    if uploaded_file is None:
        return False, "ファイルが選択されていません"
    
    # ファイル名の確認
    if not uploaded_file.name.lower().endswith('.html'):
        return False, "HTMLファイルを選択してください"
    
    try:
        # ファイル内容を読み取り
        content = uploaded_file.read().decode('utf-8')
        uploaded_file.seek(0)  # ファイルポインタをリセット
        
        # BeautifulSoupでHTMLを解析
        soup = BeautifulSoup(content, 'html.parser')
        
        # ブックマーク構造の基本的な確認
        # Chromeのブックマークファイルには通常<DT><A>タグが含まれる
        bookmark_links = soup.find_all('a')
        if len(bookmark_links) == 0:
            return False, "ブックマークが見つかりません。正しいbookmarks.htmlファイルを選択してください"
        
        # ブックマークフォルダ構造の確認（<DT><H3>タグ）
        folder_headers = soup.find_all('h3')
        
        return True, f"✅ 有効なブックマークファイルです（{len(bookmark_links)}個のブックマーク、{len(folder_headers)}個のフォルダを検出）"
        
    except UnicodeDecodeError:
        return False, "ファイルの文字エンコーディングが正しくありません"
    except Exception as e:
        return False, f"ファイル解析エラー: {str(e)}"


def validate_directory_path(directory_path: str) -> tuple[bool, str]:
    """
    指定されたディレクトリパスが有効かを検証する
    
    Returns:
        tuple[bool, str]: (検証結果, エラーメッセージまたは成功メッセージ)
    """
    if not directory_path.strip():
        return False, "ディレクトリパスを入力してください"
    
    try:
        path = Path(directory_path)
        
        # パスの存在確認
        if not path.exists():
            return False, f"指定されたパスが存在しません: {directory_path}"
        
        # ディレクトリかどうかの確認
        if not path.is_dir():
            return False, f"指定されたパスはディレクトリではありません: {directory_path}"
        
        # 書き込み権限の確認
        if not os.access(path, os.W_OK):
            return False, f"指定されたディレクトリに書き込み権限がありません: {directory_path}"
        
        # 読み取り権限の確認
        if not os.access(path, os.R_OK):
            return False, f"指定されたディレクトリに読み取り権限がありません: {directory_path}"
        
        return True, f"✅ 有効なディレクトリです: {path.absolute()}"
        
    except Exception as e:
        return False, f"ディレクトリ検証エラー: {str(e)}"


def display_page_list_and_preview(bookmarks: List[Bookmark], duplicates: Dict, output_directory: Path):
    """
    Task 9: ページ一覧表示とプレビュー機能
    
    Args:
        bookmarks: ブックマーク一覧
        duplicates: 重複ファイル情報
        output_directory: 出力ディレクトリ
    """
    st.header("📋 ページ一覧とプレビュー")
    st.markdown("処理対象のページを確認し、必要に応じてプレビューを表示できます。")
    
    # セッション状態の初期化
    if 'selected_pages' not in st.session_state:
        # デフォルトで全てチェック済み（重複除外）
        st.session_state.selected_pages = {}
        for i, bookmark in enumerate(bookmarks):
            # 重複ファイルでない場合はデフォルトでチェック
            is_duplicate = any(bookmark.title in dup_file for dup_file in duplicates.get('files', []))
            st.session_state.selected_pages[i] = not is_duplicate
    
    if 'preview_cache' not in st.session_state:
        st.session_state.preview_cache = {}
    
    # 全選択/全解除ボタン
    col1, col2, col3 = st.columns([1, 1, 4])
    
    with col1:
        if st.button("✅ 全選択"):
            for i in range(len(bookmarks)):
                st.session_state.selected_pages[i] = True
            st.rerun()
    
    with col2:
        if st.button("❌ 全解除"):
            for i in range(len(bookmarks)):
                st.session_state.selected_pages[i] = False
            st.rerun()
    
    with col3:
        selected_count = sum(1 for selected in st.session_state.selected_pages.values() if selected)
        st.write(f"**選択中:** {selected_count}/{len(bookmarks)} ページ")
    
    # フォルダ別にブックマークを整理
    folder_groups = organize_bookmarks_by_folder(bookmarks)
    
    # 展開可能なディレクトリツリー形式で表示
    for folder_path, folder_bookmarks in folder_groups.items():
        folder_name = ' > '.join(folder_path) if folder_path else "📁 ルートフォルダ"
        
        # フォルダ内の選択状況を計算
        folder_indices = [bookmarks.index(bookmark) for bookmark in folder_bookmarks]
        folder_selected = sum(1 for idx in folder_indices if st.session_state.selected_pages.get(idx, False))
        
        with st.expander(f"📂 {folder_name} ({folder_selected}/{len(folder_bookmarks)} 選択)", expanded=True):
            for bookmark in folder_bookmarks:
                original_index = bookmarks.index(bookmark)
                
                # 重複チェック
                is_duplicate = any(bookmark.title in dup_file for dup_file in duplicates.get('files', []))
                
                # チェックボックスとページ情報を表示
                col1, col2, col3 = st.columns([1, 4, 1])
                
                with col1:
                    if is_duplicate:
                        st.checkbox(
                            "重複",
                            value=False,
                            disabled=True,
                            key=f"checkbox_dup_{original_index}",
                            help="このページは既存ファイルと重複しています"
                        )
                        st.session_state.selected_pages[original_index] = False
                    else:
                        selected = st.checkbox(
                            "選択",
                            value=st.session_state.selected_pages.get(original_index, True),
                            key=f"checkbox_{original_index}"
                        )
                        st.session_state.selected_pages[original_index] = selected
                
                with col2:
                    # ページ情報表示
                    if is_duplicate:
                        st.markdown(f"~~**{bookmark.title}**~~ *(重複)*")
                    else:
                        st.markdown(f"**{bookmark.title}**")
                    
                    st.markdown(f"🔗 [{bookmark.url}]({bookmark.url})")
                    
                    if bookmark.add_date:
                        st.caption(f"📅 {bookmark.add_date.strftime('%Y-%m-%d %H:%M:%S')}")
                
                with col3:
                    # プレビューボタン
                    if not is_duplicate:
                        if st.button("👁️ プレビュー", key=f"preview_{original_index}"):
                            show_page_preview(bookmark, original_index)
                    else:
                        st.caption("重複により除外")
                
                st.divider()
    
    # 保存ボタンセクション
    st.markdown("---")
    st.subheader("💾 ファイル保存")
    
    selected_bookmarks = [
        bookmark for i, bookmark in enumerate(bookmarks) 
        if st.session_state.selected_pages.get(i, False)
    ]
    
    if selected_bookmarks:
        col1, col2 = st.columns([1, 3])
        
        with col1:
            if st.button("💾 選択したページを保存", type="primary"):
                save_selected_pages(selected_bookmarks, output_directory)
        
        with col2:
            st.info(f"💡 {len(selected_bookmarks)}個のページがMarkdownファイルとして保存されます")
            st.caption(f"保存先: {output_directory}")
    else:
        st.warning("⚠️ 保存するページが選択されていません")


def organize_bookmarks_by_folder(bookmarks: List[Bookmark]) -> Dict[tuple, List[Bookmark]]:
    """
    ブックマークをフォルダ別に整理
    
    Args:
        bookmarks: ブックマーク一覧
        
    Returns:
        Dict[tuple, List[Bookmark]]: フォルダパスをキーとしたブックマーク辞書
    """
    folder_groups = {}
    
    for bookmark in bookmarks:
        folder_key = tuple(bookmark.folder_path) if bookmark.folder_path else ()
        
        if folder_key not in folder_groups:
            folder_groups[folder_key] = []
        
        folder_groups[folder_key].append(bookmark)
    
    # フォルダパスでソート
    return dict(sorted(folder_groups.items()))


def show_page_preview(bookmark: Bookmark, index: int):
    """
    Task 10: 進捗表示とエラーハンドリングを強化したプレビュー機能
    
    Args:
        bookmark: ブックマーク情報
        index: ページインデックス
    """
    # プレビューデータがキャッシュされているかチェック
    if index not in st.session_state.preview_cache:
        
        # 進捗表示コンテナ
        progress_container = st.container()
        
        with progress_container:
            st.info(f"🔍 プレビュー取得中: {bookmark.title}")
            
            # 詳細進捗表示
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            try:
                # ステップ1: ページ取得
                status_text.text("🌐 ページ内容を取得中...")
                progress_bar.progress(0.2)
                
                scraper = WebScraper()
                html_content = None
                
                try:
                    html_content = scraper.fetch_page_content(bookmark.url)
                except requests.exceptions.ConnectionError:
                    st.session_state.preview_cache[index] = {
                        'success': False,
                        'error': 'ネットワーク接続エラー',
                        'error_type': 'network',
                        'retryable': True
                    }
                    error_logger.log_error(bookmark, 'ネットワーク接続エラー', 'network', True)
                    return
                except requests.exceptions.Timeout:
                    st.session_state.preview_cache[index] = {
                        'success': False,
                        'error': 'タイムアウトエラー',
                        'error_type': 'timeout',
                        'retryable': True
                    }
                    error_logger.log_error(bookmark, 'タイムアウトエラー', 'timeout', True)
                    return
                except Exception as e:
                    st.session_state.preview_cache[index] = {
                        'success': False,
                        'error': f'ページ取得エラー: {str(e)}',
                        'error_type': 'fetch',
                        'retryable': False
                    }
                    error_logger.log_error(bookmark, f'ページ取得エラー: {str(e)}', 'fetch', False)
                    return
                
                # ステップ2: コンテンツ抽出
                status_text.text("📄 記事内容を抽出中...")
                progress_bar.progress(0.6)
                
                article_data = None
                if html_content:
                    try:
                        article_data = scraper.extract_article_content(html_content, bookmark.url)
                    except Exception as e:
                        logger.warning(f"⚠️ コンテンツ抽出エラー: {str(e)} - フォールバックを使用")
                        error_logger.log_error(bookmark, f'コンテンツ抽出エラー: {str(e)}', 'extraction', False)
                
                # ステップ3: Markdown生成
                status_text.text("📝 Markdownを生成中...")
                progress_bar.progress(0.8)
                
                try:
                    generator = MarkdownGenerator()
                    if article_data:
                        markdown_content = generator.generate_obsidian_markdown(article_data, bookmark)
                    else:
                        markdown_content = generator._generate_fallback_markdown(bookmark)
                        article_data = {
                            'title': bookmark.title,
                            'content': 'コンテンツの抽出に失敗しました',
                            'quality_score': 0.0,
                            'extraction_method': 'fallback',
                            'tags': []
                        }
                except Exception as e:
                    st.session_state.preview_cache[index] = {
                        'success': False,
                        'error': f'Markdown生成エラー: {str(e)}',
                        'error_type': 'markdown',
                        'retryable': False
                    }
                    error_logger.log_error(bookmark, f'Markdown生成エラー: {str(e)}', 'markdown', False)
                    return
                
                # ステップ4: 完了
                status_text.text("✅ プレビュー準備完了")
                progress_bar.progress(1.0)
                
                # キャッシュに保存
                st.session_state.preview_cache[index] = {
                    'success': True,
                    'article_data': article_data,
                    'markdown': markdown_content,
                    'fetch_time': datetime.datetime.now()
                }
                
                # 進捗表示をクリア
                progress_container.empty()
                
            except Exception as e:
                st.session_state.preview_cache[index] = {
                    'success': False,
                    'error': f'予期しないエラー: {str(e)}',
                    'error_type': 'unexpected',
                    'retryable': False
                }
                error_logger.log_error(bookmark, f'予期しないエラー: {str(e)}', 'unexpected', False)
                progress_container.empty()
                return
    
    # プレビューデータを表示
    preview_data = st.session_state.preview_cache[index]
    
    if preview_data['success']:
        article_data = preview_data['article_data']
        
        # プレビュー情報を表示
        st.subheader(f"📄 {bookmark.title} - プレビュー")
        
        # キャッシュ情報
        if 'fetch_time' in preview_data:
            fetch_time = preview_data['fetch_time']
            st.caption(f"🕒 取得時刻: {fetch_time.strftime('%Y-%m-%d %H:%M:%S')}")
        
        # 基本情報
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown(f"**URL:** {bookmark.url}")
            quality_score = article_data.get('quality_score', 'N/A')
            if isinstance(quality_score, (int, float)):
                quality_color = "🟢" if quality_score > 0.7 else "🟡" if quality_score > 0.4 else "🔴"
                st.markdown(f"**品質スコア:** {quality_color} {quality_score}")
            else:
                st.markdown(f"**品質スコア:** {quality_score}")
        
        with col2:
            extraction_method = article_data.get('extraction_method', 'N/A')
            method_icon = "✅" if extraction_method != 'fallback' else "⚠️"
            st.markdown(f"**抽出方法:** {method_icon} {extraction_method}")
            
            content_length = len(article_data.get('content', ''))
            st.markdown(f"**文字数:** {content_length:,}文字")
        
        # タグ表示
        if article_data.get('tags'):
            st.markdown("**タグ:** " + ", ".join([f"`{tag}`" for tag in article_data['tags']]))
        
        # 記事内容のプレビュー（最初の500文字）
        content = article_data.get('content', '')
        if content:
            st.markdown("**記事内容プレビュー:**")
            preview_content = content[:500] + "..." if len(content) > 500 else content
            st.text_area("内容", preview_content, height=200, disabled=True)
        
        # 生成されるMarkdownのプレビュー
        with st.expander("📝 生成されるMarkdownファイル"):
            st.code(preview_data['markdown'], language='markdown')
        
        # プレビューアクション
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔄 プレビューを更新", key=f"refresh_preview_{index}"):
                # キャッシュをクリアして再取得
                if index in st.session_state.preview_cache:
                    del st.session_state.preview_cache[index]
                st.rerun()
        
        with col2:
            if st.button("📋 URLをコピー", key=f"copy_url_{index}"):
                st.code(bookmark.url)
                st.success("URLを表示しました")
    
    else:
        error_type = preview_data.get('error_type', 'unknown')
        retryable = preview_data.get('retryable', False)
        
        # エラータイプに応じたアイコンとメッセージ
        error_icons = {
            'network': '🔌',
            'timeout': '⏰',
            'fetch': '🌐',
            'extraction': '📄',
            'markdown': '📝',
            'unexpected': '💥'
        }
        
        error_icon = error_icons.get(error_type, '❌')
        st.error(f"{error_icon} プレビューエラー: {preview_data['error']}")
        
        if retryable:
            st.info("🔄 このエラーはリトライ可能です")
            if st.button("🔄 リトライ", key=f"retry_preview_{index}"):
                # キャッシュをクリアして再取得
                if index in st.session_state.preview_cache:
                    del st.session_state.preview_cache[index]
                st.rerun()
        else:
            st.info("💡 このページは手動で確認が必要です")
        
        # エラー詳細情報
        with st.expander("🔍 エラー詳細"):
            st.write(f"**エラータイプ:** {error_type}")
            st.write(f"**リトライ可能:** {'はい' if retryable else 'いいえ'}")
            st.write(f"**URL:** {bookmark.url}")
            st.write(f"**タイトル:** {bookmark.title}")


def save_selected_pages(selected_bookmarks: List[Bookmark], output_directory: Path):
    """
    Task 10: 進捗表示とエラーハンドリング機能を強化した保存機能
    
    Args:
        selected_bookmarks: 選択されたブックマーク一覧
        output_directory: 出力ディレクトリ
    """
    if not selected_bookmarks:
        st.warning("保存するページが選択されていません")
        return
    
    # 進捗表示とエラーハンドリングの初期化
    progress_container = st.container()
    error_container = st.container()
    
    with progress_container:
        st.subheader("📊 処理進捗")
        
        # 複数の進捗バー
        overall_progress = st.progress(0)
        current_progress = st.progress(0)
        
        # ステータス表示
        status_text = st.empty()
        current_task = st.empty()
        
        # 統計情報
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            success_metric = st.metric("✅ 成功", 0)
        with col2:
            error_metric = st.metric("❌ エラー", 0)
        with col3:
            skip_metric = st.metric("⏭️ スキップ", 0)
        with col4:
            remaining_metric = st.metric("⏳ 残り", len(selected_bookmarks))
    
    # エラーログとリトライ機能
    error_log = []
    retry_queue = []
    
    scraper = WebScraper()
    generator = MarkdownGenerator()
    
    saved_count = 0
    error_count = 0
    skip_count = 0
    
    # メイン処理ループ
    for i, bookmark in enumerate(selected_bookmarks):
        overall_progress_value = (i + 1) / len(selected_bookmarks)
        overall_progress.progress(overall_progress_value)
        
        status_text.text(f"📋 処理中: {i+1}/{len(selected_bookmarks)} ページ")
        current_task.text(f"🔍 現在の処理: {bookmark.title}")
        
        try:
            # ステップ1: ページ内容取得
            current_progress.progress(0.2)
            current_task.text(f"🌐 ページ取得中: {bookmark.title}")
            
            html_content = None
            article_data = None
            
            # ネットワークエラーハンドリング
            try:
                html_content = scraper.fetch_page_content(bookmark.url)
            except requests.exceptions.ConnectionError:
                error_msg = f"ネットワーク接続エラー: {bookmark.url}"
                error_log.append({
                    'bookmark': bookmark,
                    'error': error_msg,
                    'type': 'network',
                    'retryable': True
                })
                logger.error(f"🔌 {error_msg}")
                skip_count += 1
                continue
            except requests.exceptions.Timeout:
                error_msg = f"タイムアウトエラー: {bookmark.url}"
                error_log.append({
                    'bookmark': bookmark,
                    'error': error_msg,
                    'type': 'timeout',
                    'retryable': True
                })
                logger.error(f"⏰ {error_msg}")
                skip_count += 1
                continue
            except Exception as e:
                error_msg = f"ページ取得エラー: {str(e)}"
                error_log.append({
                    'bookmark': bookmark,
                    'error': error_msg,
                    'type': 'fetch',
                    'retryable': False
                })
                logger.error(f"❌ {error_msg}")
                error_count += 1
                continue
            
            # ステップ2: コンテンツ抽出
            current_progress.progress(0.5)
            current_task.text(f"📄 コンテンツ抽出中: {bookmark.title}")
            
            if html_content:
                try:
                    article_data = scraper.extract_article_content(html_content, bookmark.url)
                except Exception as e:
                    error_msg = f"コンテンツ抽出エラー: {str(e)}"
                    error_log.append({
                        'bookmark': bookmark,
                        'error': error_msg,
                        'type': 'extraction',
                        'retryable': False
                    })
                    logger.warning(f"⚠️ {error_msg} - フォールバックを使用")
            
            # ステップ3: Markdown生成
            current_progress.progress(0.7)
            current_task.text(f"📝 Markdown生成中: {bookmark.title}")
            
            try:
                if article_data:
                    markdown_content = generator.generate_obsidian_markdown(article_data, bookmark)
                else:
                    # フォールバック用Markdown
                    markdown_content = generator._generate_fallback_markdown(bookmark)
            except Exception as e:
                error_msg = f"Markdown生成エラー: {str(e)}"
                error_log.append({
                    'bookmark': bookmark,
                    'error': error_msg,
                    'type': 'markdown',
                    'retryable': False
                })
                logger.error(f"❌ {error_msg}")
                error_count += 1
                continue
            
            # ステップ4: ファイル保存
            current_progress.progress(0.9)
            current_task.text(f"💾 ファイル保存中: {bookmark.title}")
            
            try:
                # ファイルパスを生成
                file_path = generator.generate_file_path(bookmark, output_directory)
                
                # ディレクトリを作成
                file_path.parent.mkdir(parents=True, exist_ok=True)
                
                # ファイルを保存
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(markdown_content)
                
                saved_count += 1
                logger.info(f"✅ ファイル保存成功: {file_path}")
                
            except PermissionError:
                error_msg = f"ファイル保存権限エラー: {file_path}"
                error_log.append({
                    'bookmark': bookmark,
                    'error': error_msg,
                    'type': 'permission',
                    'retryable': False
                })
                logger.error(f"🔒 {error_msg}")
                error_count += 1
                continue
            except OSError as e:
                error_msg = f"ファイルシステムエラー: {str(e)}"
                error_log.append({
                    'bookmark': bookmark,
                    'error': error_msg,
                    'type': 'filesystem',
                    'retryable': False
                })
                logger.error(f"💾 {error_msg}")
                error_count += 1
                continue
            except Exception as e:
                error_msg = f"ファイル保存エラー: {str(e)}"
                error_log.append({
                    'bookmark': bookmark,
                    'error': error_msg,
                    'type': 'save',
                    'retryable': False
                })
                logger.error(f"❌ {error_msg}")
                error_count += 1
                continue
            
            # ステップ5: 完了
            current_progress.progress(1.0)
            
        except Exception as e:
            # 予期しないエラー
            error_msg = f"予期しないエラー: {str(e)}"
            error_log.append({
                'bookmark': bookmark,
                'error': error_msg,
                'type': 'unexpected',
                'retryable': False
            })
            logger.error(f"💥 {error_msg}")
            error_count += 1
        
        # メトリクス更新
        with col1:
            success_metric.metric("✅ 成功", saved_count)
        with col2:
            error_metric.metric("❌ エラー", error_count)
        with col3:
            skip_metric.metric("⏭️ スキップ", skip_count)
        with col4:
            remaining_metric.metric("⏳ 残り", len(selected_bookmarks) - i - 1)
    
    # 完了処理
    overall_progress.progress(1.0)
    current_progress.progress(1.0)
    status_text.text("🎉 処理完了！")
    current_task.text("✅ すべての処理が完了しました")
    
    # 結果サマリー
    st.markdown("---")
    st.subheader("📊 処理結果サマリー")
    
    total_processed = saved_count + error_count + skip_count
    
    if saved_count > 0:
        st.success(f"✅ {saved_count}個のファイルを正常に保存しました")
    
    if error_count > 0:
        st.error(f"❌ {error_count}個のファイルでエラーが発生しました")
    
    if skip_count > 0:
        st.warning(f"⏭️ {skip_count}個のファイルをスキップしました")
    
    # エラーログの表示
    if error_log:
        with error_container:
            st.subheader("🚨 エラーログ")
            
            # エラータイプ別の集計
            error_types = {}
            retryable_errors = []
            
            for error in error_log:
                error_type = error['type']
                if error_type not in error_types:
                    error_types[error_type] = 0
                error_types[error_type] += 1
                
                if error['retryable']:
                    retryable_errors.append(error)
            
            # エラータイプ別表示
            st.markdown("**エラータイプ別集計:**")
            for error_type, count in error_types.items():
                error_type_names = {
                    'network': '🔌 ネットワークエラー',
                    'timeout': '⏰ タイムアウトエラー',
                    'fetch': '🌐 ページ取得エラー',
                    'extraction': '📄 コンテンツ抽出エラー',
                    'markdown': '📝 Markdown生成エラー',
                    'permission': '🔒 権限エラー',
                    'filesystem': '💾 ファイルシステムエラー',
                    'save': '💾 保存エラー',
                    'unexpected': '💥 予期しないエラー'
                }
                st.write(f"- {error_type_names.get(error_type, error_type)}: {count}件")
            
            # 詳細エラーログ
            with st.expander("📋 詳細エラーログ"):
                for i, error in enumerate(error_log):
                    st.write(f"**{i+1}. {error['bookmark'].title}**")
                    st.write(f"   URL: {error['bookmark'].url}")
                    st.write(f"   エラー: {error['error']}")
                    st.write(f"   タイプ: {error['type']}")
                    if error['retryable']:
                        st.write("   🔄 リトライ可能")
                    st.write("---")
            
            # リトライ機能
            if retryable_errors:
                st.subheader("🔄 リトライ機能")
                st.info(f"{len(retryable_errors)}個のエラーはリトライ可能です")
                
                if st.button("🔄 エラーページをリトライ"):
                    retry_bookmarks = [error['bookmark'] for error in retryable_errors]
                    st.info("リトライを開始します...")
                    save_selected_pages(retry_bookmarks, output_directory)
    
    # 保存先情報
    st.info(f"📁 保存先: {output_directory}")
    
    # 処理完了ログ
    logger.info(f"🎉 処理完了: 成功={saved_count}, エラー={error_count}, スキップ={skip_count}")


def main():
    """メインアプリケーション関数"""
    # ページ設定
    st.set_page_config(
        page_title="Bookmark to Obsidian Converter",
        page_icon="📚",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # メインタイトル
    st.title("📚 Bookmark to Obsidian Converter")
    st.markdown("---")
    
    # アプリケーション説明
    st.markdown("""
    このアプリケーションは、Google Chromeのブックマークファイル（bookmarks.html）を解析し、
    ブックマークされたWebページの内容を取得してObsidian用のMarkdownファイルとして保存します。
    """)
    
    # サイドバー
    with st.sidebar:
        st.header("🔧 設定")
        st.markdown("ファイルアップロードとディレクトリ選択")
        
        # ファイルアップロード機能
        st.subheader("📁 ブックマークファイル")
        uploaded_file = st.file_uploader(
            "bookmarks.htmlファイルを選択してください",
            type=['html'],
            help="Google Chromeのブックマークエクスポートファイル（bookmarks.html）を選択してください"
        )
        
        # ファイル検証結果の表示
        if uploaded_file is not None:
            logger.info(f"📁 ファイルアップロード: {uploaded_file.name} (サイズ: {uploaded_file.size} bytes)")
            is_valid_file, file_message = validate_bookmarks_file(uploaded_file)
            if is_valid_file:
                st.success(file_message)
                logger.info(f"✅ ファイル検証成功: {file_message}")
                # セッション状態にファイルを保存
                st.session_state['uploaded_file'] = uploaded_file
                st.session_state['file_validated'] = True
            else:
                st.error(file_message)
                logger.error(f"❌ ファイル検証失敗: {file_message}")
                st.session_state['file_validated'] = False
        else:
            st.session_state['file_validated'] = False
        
        st.markdown("---")
        
        # ディレクトリ選択機能
        st.subheader("📂 保存先ディレクトリ")
        
        # デフォルトパスの提案
        default_path = str(Path.home() / "Documents" / "Obsidian")
        
        directory_path = st.text_input(
            "Obsidianファイルの保存先パスを入力してください",
            value=default_path,
            help="Markdownファイルを保存するディレクトリのフルパスを入力してください"
        )
        
        # ディレクトリ検証結果の表示
        if directory_path:
            logger.info(f"📂 ディレクトリ指定: {directory_path}")
            is_valid_dir, dir_message = validate_directory_path(directory_path)
            if is_valid_dir:
                st.success(dir_message)
                logger.info(f"✅ ディレクトリ検証成功: {directory_path}")
                # セッション状態にディレクトリパスを保存
                st.session_state['output_directory'] = Path(directory_path)
                st.session_state['directory_validated'] = True
            else:
                st.error(dir_message)
                logger.error(f"❌ ディレクトリ検証失敗: {dir_message}")
                st.session_state['directory_validated'] = False
        else:
            st.session_state['directory_validated'] = False
        
        st.markdown("---")
        
        # 設定状況の表示
        st.subheader("⚙️ 設定状況")
        file_status = "✅ 完了" if st.session_state.get('file_validated', False) else "❌ 未完了"
        dir_status = "✅ 完了" if st.session_state.get('directory_validated', False) else "❌ 未完了"
        
        st.write(f"📁 ファイル選択: {file_status}")
        st.write(f"📂 ディレクトリ選択: {dir_status}")
        
        # 次のステップへの準備状況
        ready_to_proceed = (
            st.session_state.get('file_validated', False) and 
            st.session_state.get('directory_validated', False)
        )
        
        if ready_to_proceed:
            st.success("🚀 解析を開始する準備が整いました！")
            
            # ブックマーク解析ボタン
            if st.button("📊 ブックマーク解析を開始", type="primary"):
                st.session_state['start_analysis'] = True
        else:
            st.info("📋 上記の設定を完了してください")
    
    # メインコンテンツエリア
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.header("📋 処理手順")
        
        # 設定状況に応じた手順表示
        ready_to_proceed = (
            st.session_state.get('file_validated', False) and 
            st.session_state.get('directory_validated', False)
        )
        
        if ready_to_proceed:
            # ブックマーク解析の実行
            if st.session_state.get('start_analysis', False):
                st.markdown("### 📊 ブックマーク解析結果")
                
                try:
                    # ファイル内容を読み取り
                    uploaded_file = st.session_state['uploaded_file']
                    content = uploaded_file.read().decode('utf-8')
                    uploaded_file.seek(0)  # ファイルポインタをリセット
                    
                    # ブックマーク解析の実行
                    with st.spinner("ブックマークを解析中..."):
                        logger.info("📊 ブックマーク解析を開始...")
                        parser = BookmarkParser()
                        bookmarks = parser.parse_bookmarks(content)
                        logger.info(f"📚 ブックマーク解析完了: {len(bookmarks)}個のブックマークを検出")
                        
                        # セッション状態に保存
                        st.session_state['bookmarks'] = bookmarks
                        st.session_state['parser'] = parser
                        
                        # ローカルディレクトリ管理の初期化と重複チェック
                        output_directory = st.session_state['output_directory']
                        logger.info(f"📂 ディレクトリスキャン開始: {output_directory}")
                        directory_manager = LocalDirectoryManager(output_directory)
                        
                        # 既存ディレクトリ構造をスキャン
                        existing_structure = directory_manager.scan_directory()
                        logger.info(f"📁 既存ファイル検出: {sum(len(files) for files in existing_structure.values())}個のMarkdownファイル")
                        
                        # 既存構造の詳細をログ出力
                        for path, files in existing_structure.items():
                            path_display = path if path else "(ルート)"
                            logger.info(f"  📁 {path_display}: {files}")
                        
                        # ブックマークとの重複チェック
                        logger.info("🔄 重複チェック開始...")
                        duplicates = directory_manager.compare_with_bookmarks(bookmarks)
                        logger.info(f"🔄 重複チェック完了: {len(duplicates['files'])}個の重複ファイルを検出")
                        
                        # 重複ファイルの詳細をログ出力
                        if duplicates['files']:
                            logger.info("重複ファイル一覧:")
                            for duplicate in duplicates['files']:
                                logger.info(f"  🔄 {duplicate}")
                        
                        # セッション状態に保存
                        st.session_state['directory_manager'] = directory_manager
                        st.session_state['existing_structure'] = existing_structure
                        st.session_state['duplicates'] = duplicates
                    
                    # 解析結果の表示
                    if bookmarks:
                        stats = parser.get_statistics(bookmarks)
                        
                        # 統計情報の表示
                        directory_manager = st.session_state['directory_manager']
                        dir_stats = directory_manager.get_statistics()
                        duplicates = st.session_state['duplicates']
                        
                        logger.info("📊 統計情報:")
                        logger.info(f"  📚 総ブックマーク数: {stats['total_bookmarks']}")
                        logger.info(f"  🌐 ユニークドメイン数: {stats['unique_domains']}")
                        logger.info(f"  📁 フォルダ数: {stats['folder_count']}")
                        logger.info(f"  🔄 重複ファイル数: {len(duplicates['files'])}")
                        
                        col_stat1, col_stat2, col_stat3, col_stat4 = st.columns(4)
                        with col_stat1:
                            st.metric("📚 総ブックマーク数", stats['total_bookmarks'])
                        with col_stat2:
                            st.metric("🌐 ユニークドメイン数", stats['unique_domains'])
                        with col_stat3:
                            st.metric("📁 フォルダ数", stats['folder_count'])
                        with col_stat4:
                            st.metric("🔄 重複ファイル数", len(duplicates['files']))
                        
                        # 重複チェック結果の表示
                        st.subheader("🔄 重複チェック結果")
                        existing_structure = st.session_state['existing_structure']
                        
                        if existing_structure:
                            st.info(f"📂 既存ディレクトリから {dir_stats['total_files']} 個のMarkdownファイルを検出しました")
                            
                            if duplicates['files']:
                                st.warning(f"⚠️ {len(duplicates['files'])} 個の重複ファイルが見つかりました")
                                
                                with st.expander("重複ファイル一覧を表示"):
                                    for duplicate_file in duplicates['files'][:20]:  # 最初の20個を表示
                                        st.write(f"  - 🔄 {duplicate_file}")
                                    if len(duplicates['files']) > 20:
                                        st.write(f"  ... 他 {len(duplicates['files']) - 20}個")
                                
                                st.info("💡 重複ファイルは自動的に処理対象から除外されます")
                            else:
                                st.success("✅ 重複ファイルは見つかりませんでした")
                        else:
                            st.info("📂 保存先ディレクトリは空です（新規作成）")
                        
                        # ディレクトリ構造の表示
                        st.subheader("📂 ブックマーク構造")
                        directory_structure = parser.extract_directory_structure(bookmarks)
                        
                        # 処理対象と除外対象を分けて表示
                        total_to_process = 0
                        total_excluded = 0
                        
                        for folder_path, filenames in directory_structure.items():
                            # このフォルダ内の重複ファイル数を計算
                            if folder_path:
                                folder_duplicates = [f for f in duplicates['files'] 
                                                   if f.startswith(folder_path + '/')]
                            else:
                                folder_duplicates = [f for f in duplicates['files'] 
                                                   if '/' not in f]
                            
                            excluded_count = len([f for f in filenames 
                                                if directory_manager.check_file_exists(folder_path, f)])
                            process_count = len(filenames) - excluded_count
                            
                            total_to_process += process_count
                            total_excluded += excluded_count
                            
                            if folder_path:
                                status_text = f"📁 {folder_path}"
                                if excluded_count > 0:
                                    status_text += f" ({process_count}個処理予定, {excluded_count}個除外)"
                                else:
                                    status_text += f" ({process_count}個処理予定)"
                                st.write(f"**{status_text}**")
                            else:
                                status_text = f"📄 ルートディレクトリ"
                                if excluded_count > 0:
                                    status_text += f" ({process_count}個処理予定, {excluded_count}個除外)"
                                else:
                                    status_text += f" ({process_count}個処理予定)"
                                st.write(f"**{status_text}**")
                        
                        # 処理予定の統計を表示
                        st.markdown("---")
                        col_process1, col_process2 = st.columns(2)
                        with col_process1:
                            st.metric("✅ 処理予定ファイル", total_to_process)
                        with col_process2:
                            st.metric("🔄 除外ファイル", total_excluded)
                        
                        # サンプルブックマークの表示
                        st.subheader("📋 ブックマークサンプル")
                        sample_bookmarks = bookmarks[:5]  # 最初の5個を表示
                        
                        for i, bookmark in enumerate(sample_bookmarks):
                            with st.expander(f"{i+1}. {bookmark.title}"):
                                st.write(f"**URL:** {bookmark.url}")
                                st.write(f"**フォルダパス:** {' > '.join(bookmark.folder_path) if bookmark.folder_path else 'ルート'}")
                                if bookmark.add_date:
                                    st.write(f"**追加日:** {bookmark.add_date.strftime('%Y-%m-%d %H:%M:%S')}")
                        
                        st.success(f"✅ ブックマーク解析と重複チェックが完了しました！")
                        st.info(f"📊 {len(bookmarks)}個のブックマークが見つかり、{total_to_process}個が処理対象、{total_excluded}個が重複により除外されました。")
                        
                        # Task 9: ページ一覧表示とプレビュー機能
                        if total_to_process > 0:
                            st.markdown("---")
                            display_page_list_and_preview(bookmarks, duplicates, st.session_state['output_directory'])
                        
                        # デバッグ情報の表示
                        if len(duplicates['files']) == 0 and len(existing_structure) > 0:
                            st.warning("⚠️ 既存ファイルがあるのに重複が検出されませんでした。デバッグ情報を確認してください。")
                            
                            with st.expander("🔍 デバッグ情報"):
                                st.write("**既存ファイル例（最初の5個）:**")
                                file_count = 0
                                for path, files in existing_structure.items():
                                    for file in files:
                                        if file_count >= 5:
                                            break
                                        path_display = path if path else "(ルート)"
                                        st.write(f"- {path_display}/{file}")
                                        file_count += 1
                                    if file_count >= 5:
                                        break
                                
                                st.write("**ブックマークタイトル例（最初の5個）:**")
                                for i, bookmark in enumerate(bookmarks[:5]):
                                    folder_display = " > ".join(bookmark.folder_path) if bookmark.folder_path else "(ルート)"
                                    st.write(f"- {folder_display}/{bookmark.title}")
                                
                                st.write("**サニタイズ後のファイル名例:**")
                                for i, bookmark in enumerate(bookmarks[:5]):
                                    sanitized = parser._sanitize_filename(bookmark.title)
                                    st.write(f"- '{bookmark.title}' → '{sanitized}'")
                        
                    else:
                        st.warning("⚠️ 有効なブックマークが見つかりませんでした。")
                        
                except Exception as e:
                    st.error(f"❌ ブックマーク解析中にエラーが発生しました: {str(e)}")
                    st.session_state['start_analysis'] = False
            
            else:
                st.markdown("""
                ✅ **ファイルアップロード**: 完了  
                ✅ **ディレクトリ選択**: 完了  
                
                **次のステップ:**
                3. **ブックマーク解析**: ファイル構造とURLを解析 ← 👈 サイドバーのボタンをクリック
                4. **重複チェック**: 既存ファイルとの重複を確認
                5. **コンテンツ取得**: Webページの内容を取得
                6. **プレビュー**: 処理対象ページを確認・選択
                7. **保存**: Markdownファイルとして保存
                """)
                
                # ファイル情報の表示
                if 'uploaded_file' in st.session_state:
                    uploaded_file = st.session_state['uploaded_file']
                    st.info(f"📁 選択されたファイル: {uploaded_file.name}")
                
                if 'output_directory' in st.session_state:
                    output_dir = st.session_state['output_directory']
                    st.info(f"📂 保存先ディレクトリ: {output_dir}")
                
        else:
            st.markdown("""
            **設定が必要な項目:**
            1. **ファイルアップロード**: bookmarks.htmlファイルをアップロード
            2. **ディレクトリ選択**: Obsidianファイルの保存先を指定
            
            **今後の処理手順:**
            3. **ブックマーク解析**: ファイル構造とURLを解析
            4. **重複チェック**: 既存ファイルとの重複を確認
            5. **コンテンツ取得**: Webページの内容を取得
            6. **プレビュー**: 処理対象ページを確認・選択
            7. **保存**: Markdownファイルとして保存
            """)
            
            st.warning("👈 左側のサイドバーで設定を完了してください")
    
    with col2:
        st.header("📊 ステータス")
        
        # 設定状況の表示
        file_validated = st.session_state.get('file_validated', False)
        dir_validated = st.session_state.get('directory_validated', False)
        
        if file_validated and dir_validated:
            st.success("✅ 設定完了")
            st.info("🚀 解析準備完了")
        elif file_validated or dir_validated:
            st.warning("⚠️ 設定途中")
            st.info("📋 設定を完了してください")
        else:
            st.info("📋 設定待ち")
            st.info("👈 サイドバーで設定してください")
        
        # 統計情報の表示
        if 'bookmarks' in st.session_state and 'directory_manager' in st.session_state:
            bookmarks = st.session_state['bookmarks']
            directory_manager = st.session_state['directory_manager']
            
            # 処理対象と除外対象を計算
            total_bookmarks = len(bookmarks)
            excluded_count = sum(1 for bookmark in bookmarks if directory_manager.is_duplicate(bookmark))
            process_count = total_bookmarks - excluded_count
            
            st.metric("処理対象ページ", process_count)
            st.metric("除外ページ", excluded_count)
            st.metric("完了ページ", "0")  # 今後の実装で更新
        elif 'bookmarks' in st.session_state:
            bookmarks = st.session_state['bookmarks']
            st.metric("処理対象ページ", len(bookmarks))
            st.metric("除外ページ", "0")
            st.metric("完了ページ", "0")
        else:
            st.metric("処理対象ページ", "0")
            st.metric("除外ページ", "0")
            st.metric("完了ページ", "0")
    
    # フッター
    st.markdown("---")
    st.markdown("""
    <div style='text-align: center; color: #666;'>
        <small>Bookmark to Obsidian Converter v1.0 | Streamlit Application</small>
    </div>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()