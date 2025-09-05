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
        
        # プレースホルダーセクション（今後の実装用）
        st.info("📁 ファイルアップロード機能は次のタスクで実装予定")
        st.info("📂 ディレクトリ選択機能は次のタスクで実装予定")
    
    # メインコンテンツエリア
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.header("📋 処理手順")
        st.markdown("""
        1. **ファイルアップロード**: bookmarks.htmlファイルをアップロード
        2. **ディレクトリ選択**: Obsidianファイルの保存先を指定
        3. **ブックマーク解析**: ファイル構造とURLを解析
        4. **重複チェック**: 既存ファイルとの重複を確認
        5. **コンテンツ取得**: Webページの内容を取得
        6. **プレビュー**: 処理対象ページを確認・選択
        7. **保存**: Markdownファイルとして保存
        """)
    
    with col2:
        st.header("📊 ステータス")
        st.info("アプリケーション準備完了")
        st.success("✅ 基本構造実装済み")
        
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