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
            st.markdown("""
            ✅ **ファイルアップロード**: 完了  
            ✅ **ディレクトリ選択**: 完了  
            
            **次のステップ:**
            3. **ブックマーク解析**: ファイル構造とURLを解析
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
        
        # 統計情報プレースホルダー
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