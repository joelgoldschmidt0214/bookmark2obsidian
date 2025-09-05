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
from urllib.parse import urlparse
from bs4 import BeautifulSoup


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
        
        # DLの直接の子要素のDTを順番に処理
        for dt in dl_element.find_all('dt', recursive=False):
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
        # 危険な文字を除去・置換
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
            is_valid_file, file_message = validate_bookmarks_file(uploaded_file)
            if is_valid_file:
                st.success(file_message)
                # セッション状態にファイルを保存
                st.session_state['uploaded_file'] = uploaded_file
                st.session_state['file_validated'] = True
            else:
                st.error(file_message)
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
            is_valid_dir, dir_message = validate_directory_path(directory_path)
            if is_valid_dir:
                st.success(dir_message)
                # セッション状態にディレクトリパスを保存
                st.session_state['output_directory'] = Path(directory_path)
                st.session_state['directory_validated'] = True
            else:
                st.error(dir_message)
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
                        parser = BookmarkParser()
                        bookmarks = parser.parse_bookmarks(content)
                        
                        # セッション状態に保存
                        st.session_state['bookmarks'] = bookmarks
                        st.session_state['parser'] = parser
                    
                    # 解析結果の表示
                    if bookmarks:
                        stats = parser.get_statistics(bookmarks)
                        
                        # 統計情報の表示
                        col_stat1, col_stat2, col_stat3 = st.columns(3)
                        with col_stat1:
                            st.metric("📚 総ブックマーク数", stats['total_bookmarks'])
                        with col_stat2:
                            st.metric("🌐 ユニークドメイン数", stats['unique_domains'])
                        with col_stat3:
                            st.metric("📁 フォルダ数", stats['folder_count'])
                        
                        # ディレクトリ構造の表示
                        st.subheader("📂 ディレクトリ構造")
                        directory_structure = parser.extract_directory_structure(bookmarks)
                        
                        for folder_path, filenames in directory_structure.items():
                            if folder_path:
                                st.write(f"**📁 {folder_path}** ({len(filenames)}個のファイル)")
                                with st.expander(f"ファイル一覧を表示"):
                                    for filename in filenames[:10]:  # 最初の10個のみ表示
                                        st.write(f"  - {filename}")
                                    if len(filenames) > 10:
                                        st.write(f"  ... 他 {len(filenames) - 10}個")
                            else:
                                st.write(f"**📄 ルートディレクトリ** ({len(filenames)}個のファイル)")
                        
                        # サンプルブックマークの表示
                        st.subheader("📋 ブックマークサンプル")
                        sample_bookmarks = bookmarks[:5]  # 最初の5個を表示
                        
                        for i, bookmark in enumerate(sample_bookmarks):
                            with st.expander(f"{i+1}. {bookmark.title}"):
                                st.write(f"**URL:** {bookmark.url}")
                                st.write(f"**フォルダパス:** {' > '.join(bookmark.folder_path) if bookmark.folder_path else 'ルート'}")
                                if bookmark.add_date:
                                    st.write(f"**追加日:** {bookmark.add_date.strftime('%Y-%m-%d %H:%M:%S')}")
                        
                        st.success(f"✅ ブックマーク解析が完了しました！{len(bookmarks)}個のブックマークが見つかりました。")
                        
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
        if 'bookmarks' in st.session_state:
            bookmarks = st.session_state['bookmarks']
            st.metric("処理対象ページ", len(bookmarks))
            st.metric("除外ページ", "0")  # 今後の実装で更新
            st.metric("完了ページ", "0")  # 今後の実装で更新
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