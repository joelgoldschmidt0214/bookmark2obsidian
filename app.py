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
from urllib.parse import urlparse
from bs4 import BeautifulSoup

# ログ設定
# 環境変数DEBUG=1を設定するとデバッグログも表示
log_level = logging.DEBUG if os.getenv('DEBUG') == '1' else logging.INFO
logging.basicConfig(
    level=log_level,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),  # コンソール出力
    ]
)
logger = logging.getLogger(__name__)

logger.info(f"🚀 アプリケーション開始 (ログレベル: {logging.getLevelName(log_level)})")


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
    
    def _parse_dl_element(self, dl_element, current_path: List[str]) -> List[Bookmark]:
        """
        DLエレメントを愚直に解析してブックマークを抽出
        
        Args:
            dl_element: BeautifulSoupのDLエレメント
            current_path: 現在のフォルダパス
            
        Returns:
            List[Bookmark]: 抽出されたブックマーク一覧
        """
        bookmarks = []
        
        # DLエレメント内のDTを処理（Pタグ内にある場合も考慮）
        # まず、このDLレベルのDTエレメントを取得
        all_dt_in_dl = dl_element.find_all('dt')
        
        # ネストしたDL内のDTエレメントを除外
        nested_dls = dl_element.find_all('dl')[1:]  # 最初のDLは自分自身なので除外
        nested_dt_elements = set()
        for nested_dl in nested_dls:
            nested_dt_elements.update(nested_dl.find_all('dt'))
        
        # このDLレベルのDTエレメントのみを処理
        direct_dt_elements = [dt for dt in all_dt_in_dl if dt not in nested_dt_elements]
        
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
                        nested_bookmarks = self._parse_dl_element(nested_dl, new_path)
                        bookmarks.extend(nested_bookmarks)
            else:
                # DTの後にDDがない場合 → ブックマーク
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