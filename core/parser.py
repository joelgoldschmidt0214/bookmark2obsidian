"""
ブックマーク解析モジュール

このモジュールは、ブラウザのbookmarks.htmlファイルを解析して
ブックマーク情報を抽出する機能を提供します。
"""

from bs4 import BeautifulSoup
import re
import datetime
from typing import Optional, List, Dict
from urllib.parse import urlparse

from ..utils.models import Bookmark

clas
s BookmarkParser:
    """
    bookmarks.htmlファイルを解析してブックマーク情報を抽出するクラス
    
    ブラウザのエクスポートしたbookmarks.htmlファイルを解析し、
    ブックマーク情報を構造化されたデータとして抽出します。
    フォルダ階層の解析、除外ルールの適用、統計情報の生成などの機能を提供します。
    """
    
    def __init__(self):
        """
        BookmarkParserを初期化
        
        除外ドメインと除外URLのセットを初期化します。
        """
        self.excluded_domains = set()
        self.excluded_urls = set()
    
    def parse_bookmarks(self, html_content: str) -> List[Bookmark]:
        """
        HTMLコンテンツからブックマーク一覧を抽出する
        
        bookmarks.htmlファイルの内容を解析し、ブックマーク情報を
        Bookmarkオブジェクトのリストとして返します。
        
        Args:
            html_content: bookmarks.htmlの内容
            
        Returns:
            List[Bookmark]: 抽出されたブックマーク一覧
            
        Raises:
            ValueError: ブックマーク解析に失敗した場合
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
    
    def extract_directory_structure(self, bookmarks: List[Bookmark]) -> Dict[str, List[str]]:
        """
        ブックマークからディレクトリ構造を抽出
        
        ブックマークのフォルダ階層情報を基に、ディレクトリ構造を生成します。
        各ディレクトリに含まれるファイル名のリストを返します。
        
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
        """
        除外ドメインを追加
        
        Args:
            domain: 除外するドメイン名
        """
        self.excluded_domains.add(domain.lower())
    
    def add_excluded_url(self, url: str) -> None:
        """
        除外URLを追加
        
        Args:
            url: 除外するURL
        """
        self.excluded_urls.add(url)
    
    def get_statistics(self, bookmarks: List[Bookmark]) -> Dict[str, int]:
        """
        ブックマーク統計情報を取得
        
        Args:
            bookmarks: ブックマーク一覧
            
        Returns:
            Dict[str, int]: 統計情報
                - total_bookmarks: 総ブックマーク数
                - unique_domains: ユニークドメイン数
                - folder_count: フォルダ数
        """
        total_bookmarks = len(bookmarks)
        unique_domains = len(set(urlparse(b.url).netloc for b in bookmarks))
        folder_count = len(set('/'.join(b.folder_path) for b in bookmarks if b.folder_path))
        
        return {
            'total_bookmarks': total_bookmarks,
            'unique_domains': unique_domains,
            'folder_count': folder_count
        }