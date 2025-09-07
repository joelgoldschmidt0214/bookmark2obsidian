"""
UI Components Module
Streamlit用のUIコンポーネント関数群
"""

import streamlit as st
from pathlib import Path
import os
import logging
import time
from typing import List, Dict, Any, Tuple
from urllib.parse import urlparse
from datetime import datetime

# 作成したモジュールからのインポート
from utils.models import Bookmark
from core.file_manager import LocalDirectoryManager
from core.scraper import WebScraper
from core.generator import MarkdownGenerator

# ロガーの取得
logger = logging.getLogger(__name__)


# ===== ファイル・ディレクトリ検証関数 =====


def validate_bookmarks_file(uploaded_file) -> Tuple[bool, str]:
    """
    アップロードされたファイルがbookmarks.htmlとして有効かを検証する

    Streamlitのfile_uploaderでアップロードされたファイルが
    ブラウザのブックマークファイルとして適切な形式かを確認します。

    Args:
        uploaded_file: Streamlitのアップロードファイルオブジェクト

    Returns:
        Tuple[bool, str]: (検証結果, メッセージ)
    """
    if uploaded_file is None:
        return False, "ファイルが選択されていません。"

    # ファイル名の確認
    if not uploaded_file.name.lower().endswith(".html"):
        return False, "HTMLファイル（.html）を選択してください。"

    # ファイルサイズの確認
    if uploaded_file.size == 0:
        return False, "ファイルが空です。"

    if uploaded_file.size > 50 * 1024 * 1024:  # 50MB制限
        return False, "ファイルサイズが大きすぎます（50MB以下にしてください）。"

    return True, "有効なブックマークファイルです。"


def validate_directory_path(directory_path: str) -> Tuple[bool, str]:
    """
    指定されたディレクトリパスが有効かを検証する

    出力先ディレクトリとして指定されたパスの妥当性を確認し、
    必要に応じてディレクトリの作成可能性もチェックします。

    Args:
        directory_path: 検証対象のディレクトリパス

    Returns:
        Tuple[bool, str]: (検証結果, メッセージ)
    """
    if not directory_path or not directory_path.strip():
        return False, "ディレクトリパスが入力されていません。"

    try:
        path = Path(directory_path.strip())

        # パスの妥当性確認
        if not path.is_absolute():
            return False, "絶対パスを指定してください。"

        # 既存ディレクトリの確認
        if path.exists():
            if not path.is_dir():
                return False, "指定されたパスはディレクトリではありません。"

            # 書き込み権限の確認
            if not os.access(path, os.W_OK):
                return False, "指定されたディレクトリに書き込み権限がありません。"

            return True, "有効なディレクトリです。"

        else:
            # 親ディレクトリの存在と権限確認
            parent = path.parent
            if not parent.exists():
                return False, f"親ディレクトリが存在しません: {parent}"

            if not os.access(parent, os.W_OK):
                return False, "親ディレクトリに書き込み権限がありません。"

            return True, "ディレクトリを作成できます。"

    except Exception as e:
        return False, f"パス検証中にエラーが発生しました: {str(e)}"


# ===== エッジケース処理関数 =====


def handle_edge_cases_and_errors(bookmarks: List[Bookmark]) -> Dict[str, Any]:
    """
    特殊ケースとエラーの包括的な処理

    ブックマークリストを分析し、問題のあるURL、タイトル、
    その他の特殊ケースを特定して分類します。

    Args:
        bookmarks: 分析対象のブックマークリスト

    Returns:
        Dict[str, Any]: エッジケース分析結果
    """
    result = {
        "total_bookmarks": len(bookmarks),
        "problematic_urls": [],
        "problematic_titles": [],
        "domain_root_urls": [],
        "statistics": {
            "invalid_urls": 0,
            "domain_roots": 0,
            "problematic_titles": 0,
            "valid_bookmarks": 0,
        },
    }

    logger.info(f"🔍 エッジケース分析開始: {len(bookmarks)}個のブックマーク")

    for bookmark in bookmarks:
        # ブックマークの型チェック
        if not hasattr(bookmark, "title"):
            logger.error(
                f"統計計算で無効なブックマークオブジェクト: {type(bookmark)} - {bookmark}"
            )
            continue

        # URL形式の検証
        if not _is_valid_url_format(bookmark.url):
            result["problematic_urls"].append(
                {
                    "title": bookmark.title,
                    "url": bookmark.url,
                    "reason": "無効なURL形式",
                }
            )
            result["statistics"]["invalid_urls"] += 1
            continue

        # ドメインルートURLの検出
        if _is_domain_root_url(bookmark.url):
            result["domain_root_urls"].append(
                {
                    "title": bookmark.title,
                    "url": bookmark.url,
                    "folder_path": bookmark.folder_path,
                }
            )
            result["statistics"]["domain_roots"] += 1

        # タイトルの問題文字チェック
        if _has_problematic_characters(bookmark.title):
            result["problematic_titles"].append(
                {
                    "title": bookmark.title,
                    "url": bookmark.url,
                    "folder_path": bookmark.folder_path,
                }
            )
            result["statistics"]["problematic_titles"] += 1

        # 有効なブックマークとしてカウント
        if _is_valid_url_format(bookmark.url) and not _is_domain_root_url(bookmark.url):
            result["statistics"]["valid_bookmarks"] += 1

    logger.info(f"✅ エッジケース分析完了: {result['statistics']}")
    return result


def _is_valid_url_format(url: str) -> bool:
    """URLの形式が有効かチェック"""
    try:
        parsed = urlparse(url)
        return bool(parsed.scheme and parsed.netloc)
    except Exception:
        return False


def _is_domain_root_url(url: str) -> bool:
    """URLがドメインルートかチェック"""
    try:
        parsed = urlparse(url)
        path = parsed.path.strip("/")
        return len(path) == 0 and not parsed.query and not parsed.fragment
    except Exception:
        return False


def _has_problematic_characters(title: str) -> bool:
    """タイトルに問題のある文字が含まれているかチェック"""
    problematic_chars = ["<", ">", ":", '"', "/", "\\", "|", "?", "*"]
    return any(char in title for char in problematic_chars)


# ===== 情報表示関数 =====


def display_edge_case_summary(edge_case_result: Dict[str, Any]):
    """特殊ケースの要約表示"""
    st.subheader("📊 ブックマーク分析結果")

    # 統計情報の表示
    stats = edge_case_result["statistics"]

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("総ブックマーク数", edge_case_result["total_bookmarks"])

    with col2:
        st.metric("有効なブックマーク", stats["valid_bookmarks"])

    with col3:
        st.metric("ドメインルートURL", stats["domain_roots"])

    with col4:
        st.metric("問題のあるURL", stats["invalid_urls"])


def display_user_friendly_messages():
    """ユーザビリティ向上のためのメッセージ表示"""
    st.sidebar.markdown("---")
    st.sidebar.subheader("💡 使用方法")

    with st.sidebar.expander("📖 基本的な使い方"):
        st.markdown("""
        1. **ブックマークファイルをアップロード**
           - ブラウザからエクスポートしたbookmarks.htmlを選択
        
        2. **出力ディレクトリを指定**
           - Obsidianのvaultディレクトリを指定
        
        3. **ブックマークを選択**
           - 変換したいブックマークを選択
        
        4. **Markdownファイルを生成**
           - 選択したブックマークをObsidian形式で保存
        """)


def show_application_info():
    """アプリケーション情報の表示"""
    st.title("🔖 Bookmark to Obsidian Converter")

    st.markdown("""
    このアプリケーションは、ブラウザのブックマークをObsidian用のMarkdownファイルに変換します。
    
    ### 🌟 主な機能
    
    - **📁 ブックマーク階層の保持**: フォルダ構造をそのまま再現
    - **🌐 Webページ内容の自動取得**: 記事本文を自動抽出
    - **📝 Obsidian形式のMarkdown生成**: YAML front matterとタグ対応
    - **🔍 重複チェック**: 既存ファイルとの重複を自動検出
    - **⚡ 高速処理**: 並列処理とキャッシュ機能
    - **🛡️ エラーハンドリング**: 堅牢なエラー処理とリトライ機能
    """)


# ===== ブックマーク表示・プレビュー関数 =====


def display_page_list_and_preview(
    bookmarks: List[Bookmark], duplicates: Dict, output_directory: Path
):
    """
    改善されたページ一覧表示とプレビュー機能

    要件:
    - エラーハンドリング付きの結果表示機能
    - セッション状態管理の改善
    - 表示エラー時の適切なメッセージ表示
    """
    try:
        st.subheader("📋 ブックマーク一覧とプレビュー")

        # 入力データの検証
        if not _validate_display_inputs(bookmarks, duplicates, output_directory):
            return

        # セッション状態の初期化と管理
        _initialize_session_state()

        # 統計情報の表示
        _display_bookmark_statistics(bookmarks, duplicates)

        # フォルダ別に整理（エラーハンドリング付き）
        try:
            folder_groups = organize_bookmarks_by_folder(bookmarks)
        except Exception as e:
            st.error(f"❌ フォルダ整理中にエラーが発生しました: {str(e)}")
            logger.error(f"フォルダ整理エラー: {e}")
            return

        # 表示モード選択
        display_mode = st.radio(
            "表示モード",
            ["📁 フォルダ別表示", "📄 一覧表示"],
            horizontal=True,
            key="display_mode_selection",
        )

        # 表示モードに応じた処理（エラーハンドリング付き）
        try:
            if display_mode == "📁 フォルダ別表示":
                display_bookmark_tree(bookmarks, folder_groups, duplicates)
            else:
                display_bookmark_list_only(bookmarks, duplicates)
        except Exception as e:
            st.error(f"❌ ブックマーク表示中にエラーが発生しました: {str(e)}")
            logger.error(f"ブックマーク表示エラー: {e}")

            # フォールバック表示
            _display_fallback_bookmark_list(bookmarks)

        # 選択状態の表示と管理
        _display_selection_summary()

    except Exception as e:
        st.error(f"❌ 予期しないエラーが発生しました: {str(e)}")
        logger.error(f"display_page_list_and_preview エラー: {e}")

        # 緊急時のフォールバック
        _display_emergency_fallback()


def _validate_display_inputs(
    bookmarks: List[Bookmark], duplicates: Dict, output_directory: Path
) -> bool:
    """表示機能の入力データを検証"""
    try:
        # ブックマークリストの検証
        if not bookmarks:
            st.warning("📝 表示するブックマークがありません。")
            st.info("💡 ブックマークファイルをアップロードして解析を実行してください。")
            return False

        if not isinstance(bookmarks, list):
            st.error("❌ ブックマークデータの形式が正しくありません。")
            logger.error(f"無効なブックマークデータ型: {type(bookmarks)}")
            return False

        # 重複データの検証
        if duplicates is None:
            st.warning("⚠️ 重複チェックデータがありません。")
            duplicates = {"files": [], "urls": []}

        # 出力ディレクトリの検証
        if not output_directory or not isinstance(output_directory, Path):
            st.error("❌ 出力ディレクトリが正しく設定されていません。")
            return False

        return True

    except Exception as e:
        st.error(f"❌ 入力データ検証中にエラーが発生しました: {str(e)}")
        logger.error(f"入力データ検証エラー: {e}")
        return False


def _initialize_session_state():
    """セッション状態の初期化と管理を改善"""
    try:
        # 選択されたブックマークの初期化
        if "selected_bookmarks" not in st.session_state:
            st.session_state.selected_bookmarks = []

        # 表示設定の初期化
        if "display_settings" not in st.session_state:
            st.session_state.display_settings = {
                "show_duplicates": True,
                "show_statistics": True,
                "items_per_page": 20,
                "sort_order": "folder",
            }

        # エラー状態の初期化
        if "display_errors" not in st.session_state:
            st.session_state.display_errors = []

        # 最後の更新時刻を記録
        st.session_state.last_display_update = datetime.now()

    except Exception as e:
        logger.error(f"セッション状態初期化エラー: {e}")


def _display_bookmark_statistics(bookmarks: List[Bookmark], duplicates: Dict):
    """ブックマーク統計情報の表示"""
    try:
        if not st.session_state.display_settings.get("show_statistics", True):
            return

        st.markdown("#### 📊 ブックマーク統計")

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("総ブックマーク数", len(bookmarks))

        with col2:
            duplicate_files = (
                duplicates.get("files", []) if isinstance(duplicates, dict) else []
            )
            duplicate_count = len(duplicate_files)
            st.metric("重複ファイル", duplicate_count)

        with col3:
            selected_count = len(st.session_state.get("selected_bookmarks", []))
            st.metric("選択中", selected_count)

        with col4:
            # フォルダ数の計算
            folders = set()
            for bookmark in bookmarks:
                # ブックマークの型チェック
                if not hasattr(bookmark, "title"):
                    continue

                if bookmark.folder_path:
                    folders.add(tuple(bookmark.folder_path))
            st.metric("フォルダ数", len(folders))

    except Exception as e:
        st.warning(f"⚠️ 統計情報の表示中にエラーが発生しました: {str(e)}")
        logger.error(f"統計情報表示エラー: {e}")


def _display_selection_summary():
    """選択状態のサマリー表示"""
    try:
        selected_bookmarks = st.session_state.get("selected_bookmarks", [])

        if selected_bookmarks:
            st.markdown("---")
            st.markdown("### 📋 選択サマリー")

            col1, col2 = st.columns(2)

            with col1:
                st.info(
                    f"✅ {len(selected_bookmarks)}個のブックマークが選択されています"
                )

            with col2:
                if st.button("🗑️ 選択をクリア", key="clear_selection"):
                    st.session_state.selected_bookmarks = []
                    st.rerun()

    except Exception as e:
        logger.error(f"選択サマリー表示エラー: {e}")


def _display_fallback_bookmark_list(bookmarks: List[Bookmark]):
    """フォールバック用のシンプルなブックマーク一覧表示"""
    try:
        st.markdown("### 📄 シンプル表示モード")
        st.info(
            "⚠️ 通常の表示でエラーが発生したため、シンプル表示モードに切り替えました。"
        )

        # ページネーション
        items_per_page = 10
        total_pages = (len(bookmarks) + items_per_page - 1) // items_per_page

        if total_pages > 1:
            page = st.selectbox(
                "ページ", range(1, total_pages + 1), key="fallback_page"
            )
            start_idx = (page - 1) * items_per_page
            end_idx = min(start_idx + items_per_page, len(bookmarks))
            page_bookmarks = bookmarks[start_idx:end_idx]
        else:
            page_bookmarks = bookmarks

        # シンプルなリスト表示
        for i, bookmark in enumerate(page_bookmarks):
            with st.expander(f"📄 {bookmark.title[:50]}..."):
                st.markdown(f"**URL:** [{bookmark.url}]({bookmark.url})")
                if bookmark.folder_path:
                    st.markdown(f"**フォルダ:** {' > '.join(bookmark.folder_path)}")

    except Exception as e:
        st.error(f"❌ フォールバック表示でもエラーが発生しました: {str(e)}")
        logger.error(f"フォールバック表示エラー: {e}")


def _display_emergency_fallback():
    """緊急時のフォールバック表示"""
    st.error("❌ 重大なエラーが発生しました")
    st.markdown("""
    ### 🚨 緊急時の対処方法
    
    1. **ページを再読み込み**してください
    2. **ブラウザのキャッシュをクリア**してください
    3. **ブックマークファイルを再アップロード**してください
    4. 問題が続く場合は、**より小さなブックマークファイル**で試してください
    
    ### 📞 サポート情報
    - エラーの詳細はブラウザの開発者ツールで確認できます
    - ログファイルも確認してください
    """)

    # セッション状態のリセットオプション
    if st.button("🔄 セッション状態をリセット", key="emergency_reset"):
        for key in list(st.session_state.keys()):
            if key.startswith(("selected_", "display_")):
                del st.session_state[key]
        st.success(
            "✅ セッション状態をリセットしました。ページを再読み込みしてください。"
        )
        st.rerun()


def organize_bookmarks_by_folder(
    bookmarks: List[Bookmark],
) -> Dict[tuple, List[Bookmark]]:
    """ブックマークをフォルダ別に整理"""
    folder_groups = {}

    for bookmark in bookmarks:
        # ブックマークの型チェック
        if not hasattr(bookmark, "title"):
            logger.error(
                f"無効なブックマークオブジェクト: {type(bookmark)} - {bookmark}"
            )
            continue

        # フォルダパスをタプルに変換（辞書のキーとして使用）
        folder_key = tuple(bookmark.folder_path) if bookmark.folder_path else tuple()

        if folder_key not in folder_groups:
            folder_groups[folder_key] = []

        folder_groups[folder_key].append(bookmark)

    # フォルダパスでソート（ルートフォルダを最初に）
    sorted_groups = dict(sorted(folder_groups.items(), key=lambda x: (len(x[0]), x[0])))

    return sorted_groups


def display_bookmark_tree(
    bookmarks: List[Bookmark],
    folder_groups: Dict[tuple, List[Bookmark]],
    duplicates: Dict,
):
    """改善されたツリー表示機能"""
    st.write("### 📁 フォルダ別ブックマーク表示")

    # セッション状態の初期化
    if "selected_bookmarks" not in st.session_state:
        st.session_state.selected_bookmarks = []

    # 全選択/全解除ボタン
    col1, col2 = st.columns(2)

    with col1:
        if st.button("✅ 全選択", key="select_all_tree"):
            st.session_state.selected_bookmarks = bookmarks.copy()
            st.rerun()

    with col2:
        if st.button("❌ 全解除", key="deselect_all_tree"):
            st.session_state.selected_bookmarks = []
            st.rerun()


def display_bookmark_list_only(bookmarks: List[Bookmark], duplicates: Dict):
    """
    改善されたブックマーク一覧表示機能

    要件:
    - 表示ロジックの修正
    - プレビュー機能の連携改善
    - 表示エラー時の適切なメッセージ表示
    """
    try:
        st.write("### 📄 ブックマーク一覧")

        # 入力データの検証
        if not bookmarks:
            st.warning("📝 表示するブックマークがありません。")
            return

        if not isinstance(bookmarks, list):
            st.error("❌ ブックマークデータの形式が正しくありません。")
            return

        # セッション状態の初期化（エラーハンドリング付き）
        _initialize_bookmark_list_session_state()

        # 表示設定コントロール
        _display_list_controls(bookmarks)

        # フィルタリングとソート
        try:
            filtered_bookmarks = _apply_bookmark_filters(bookmarks, duplicates)
            sorted_bookmarks = _apply_bookmark_sorting(filtered_bookmarks)
        except Exception as e:
            st.error(f"❌ ブックマークの処理中にエラーが発生しました: {str(e)}")
            logger.error(f"ブックマーク処理エラー: {e}")
            sorted_bookmarks = bookmarks  # フォールバック

        # ページネーション
        try:
            paginated_bookmarks = _apply_pagination(sorted_bookmarks)
        except Exception as e:
            st.warning(f"⚠️ ページネーション処理でエラーが発生しました: {str(e)}")
            paginated_bookmarks = sorted_bookmarks[:20]  # 最初の20件のみ表示

        # ブックマーク一覧の表示
        _display_bookmark_items(paginated_bookmarks, duplicates)

        # プレビュー機能の統合
        _display_integrated_preview()

    except Exception as e:
        st.error(f"❌ ブックマーク一覧表示中にエラーが発生しました: {str(e)}")
        logger.error(f"display_bookmark_list_only エラー: {e}")

        # フォールバック表示
        _display_simple_bookmark_fallback(bookmarks)


def _initialize_bookmark_list_session_state():
    """ブックマーク一覧用のセッション状態を初期化"""
    try:
        if "selected_bookmarks" not in st.session_state:
            st.session_state.selected_bookmarks = []

        if "bookmark_filters" not in st.session_state:
            st.session_state.bookmark_filters = {
                "show_duplicates": True,
                "search_term": "",
                "folder_filter": "all",
            }

        if "bookmark_sort" not in st.session_state:
            st.session_state.bookmark_sort = {"field": "title", "order": "asc"}

        if "pagination" not in st.session_state:
            st.session_state.pagination = {"current_page": 1, "items_per_page": 20}

        if "preview_bookmark" not in st.session_state:
            st.session_state.preview_bookmark = None

    except Exception as e:
        logger.error(f"セッション状態初期化エラー: {e}")


def _display_list_controls(bookmarks: List[Bookmark]):
    """一覧表示のコントロールを表示"""
    try:
        # 全選択/全解除ボタン
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            if st.button("✅ 全選択", key="select_all_list"):
                st.session_state.selected_bookmarks = bookmarks.copy()
                st.rerun()

        with col2:
            if st.button("❌ 全解除", key="deselect_all_list"):
                st.session_state.selected_bookmarks = []
                st.rerun()

        with col3:
            # 検索機能
            search_term = st.text_input(
                "🔍 検索",
                value=st.session_state.bookmark_filters.get("search_term", ""),
                key="bookmark_search",
                placeholder="タイトルまたはURLで検索",
            )
            st.session_state.bookmark_filters["search_term"] = search_term

        with col4:
            # ソート設定
            sort_options = ["title", "url", "folder", "date"]
            sort_field = st.selectbox(
                "📊 ソート",
                sort_options,
                index=sort_options.index(
                    st.session_state.bookmark_sort.get("field", "title")
                ),
                key="bookmark_sort_field",
            )
            st.session_state.bookmark_sort["field"] = sort_field

        # フィルター設定
        col5, col6 = st.columns(2)

        with col5:
            show_duplicates = st.checkbox(
                "🔄 重複も表示",
                value=st.session_state.bookmark_filters.get("show_duplicates", True),
                key="show_duplicates_filter",
            )
            st.session_state.bookmark_filters["show_duplicates"] = show_duplicates

        with col6:
            items_per_page = st.selectbox(
                "📄 表示件数",
                [10, 20, 50, 100],
                index=[10, 20, 50, 100].index(
                    st.session_state.pagination.get("items_per_page", 20)
                ),
                key="items_per_page_select",
            )
            st.session_state.pagination["items_per_page"] = items_per_page

    except Exception as e:
        st.warning(f"⚠️ コントロール表示でエラーが発生しました: {str(e)}")
        logger.error(f"コントロール表示エラー: {e}")


def _apply_bookmark_filters(
    bookmarks: List[Bookmark], duplicates: Dict
) -> List[Bookmark]:
    """ブックマークにフィルターを適用"""
    try:
        filtered_bookmarks = bookmarks.copy()
        filters = st.session_state.bookmark_filters

        # 検索フィルター
        search_term = filters.get("search_term", "").lower().strip()
        if search_term:
            filtered_bookmarks = [
                bookmark
                for bookmark in filtered_bookmarks
                if search_term in bookmark.title.lower()
                or search_term in bookmark.url.lower()
            ]

        # 重複フィルター
        if not filters.get("show_duplicates", True):
            duplicate_files = (
                duplicates.get("files", []) if isinstance(duplicates, dict) else []
            )
            duplicate_paths = set(duplicate_files)
            filtered_bookmarks = [
                bookmark
                for bookmark in filtered_bookmarks
                if not _is_bookmark_duplicate(bookmark, duplicate_paths)
            ]

        return filtered_bookmarks

    except Exception as e:
        logger.error(f"フィルター適用エラー: {e}")
        return bookmarks


def _apply_bookmark_sorting(bookmarks: List[Bookmark]) -> List[Bookmark]:
    """ブックマークにソートを適用"""
    try:
        sort_config = st.session_state.bookmark_sort
        field = sort_config.get("field", "title")
        reverse = sort_config.get("order", "asc") == "desc"

        if field == "title":
            return sorted(bookmarks, key=lambda b: b.title.lower(), reverse=reverse)
        elif field == "url":
            return sorted(bookmarks, key=lambda b: b.url.lower(), reverse=reverse)
        elif field == "folder":
            return sorted(
                bookmarks,
                key=lambda b: " > ".join(b.folder_path) if b.folder_path else "",
                reverse=reverse,
            )
        elif field == "date":
            return sorted(
                bookmarks, key=lambda b: b.add_date or datetime.min, reverse=reverse
            )
        else:
            return bookmarks

    except Exception as e:
        logger.error(f"ソート適用エラー: {e}")
        return bookmarks


def _apply_pagination(bookmarks: List[Bookmark]) -> List[Bookmark]:
    """ページネーションを適用"""
    try:
        pagination = st.session_state.pagination
        items_per_page = pagination.get("items_per_page", 20)
        current_page = pagination.get("current_page", 1)

        total_items = len(bookmarks)
        total_pages = (total_items + items_per_page - 1) // items_per_page

        if total_pages > 1:
            # ページ選択
            col1, col2, col3 = st.columns([1, 2, 1])

            with col2:
                page = st.selectbox(
                    f"ページ ({total_items}件中)",
                    range(1, total_pages + 1),
                    index=current_page - 1,
                    key="pagination_page_select",
                )
                st.session_state.pagination["current_page"] = page

            start_idx = (page - 1) * items_per_page
            end_idx = min(start_idx + items_per_page, total_items)

            return bookmarks[start_idx:end_idx]
        else:
            return bookmarks

    except Exception as e:
        logger.error(f"ページネーション適用エラー: {e}")
        return bookmarks[:20]  # フォールバック


def _is_bookmark_duplicate(bookmark: Bookmark, duplicate_paths: set) -> bool:
    """ブックマークが重複しているかチェック"""
    folder_path = "/".join(bookmark.folder_path) if bookmark.folder_path else ""
    filename = _sanitize_filename_for_check(bookmark.title, folder_path)
    file_path = f"{folder_path}/{filename}" if folder_path else filename
    return file_path in duplicate_paths


def _sanitize_filename_for_check(title: str, folder_path: str = "") -> str:
    """ファイル名のサニタイズ（file_managerと同じロジック）"""
    import re

    # 危険な文字を除去・置換
    filename = re.sub(r'[<>:"/\\|?*]', "_", title)
    filename = re.sub(r"_+", "_", filename)
    filename = filename.strip(" _")

    if not filename:
        filename = "untitled"

    # 長さ制限
    if len(filename) > 100:
        filename = filename[:97] + "..."

    return filename


def _display_bookmark_items(bookmarks: List[Bookmark], duplicates: Dict):
    """ブックマークアイテムを表示"""
    try:
        # duplicatesの構造を確認してから処理
        duplicate_files = (
            duplicates.get("files", []) if isinstance(duplicates, dict) else []
        )
        # duplicate_filesは文字列のリストなので、URLではなくファイルパスとして扱う
        duplicate_paths = set(duplicate_files)
        selected_bookmarks = st.session_state.get("selected_bookmarks", [])

        for i, bookmark in enumerate(bookmarks):
            # デバッグ: ブックマークの型をチェック
            if not hasattr(bookmark, "title"):
                st.error(
                    f"❌ 無効なブックマークオブジェクト: {type(bookmark)} - {bookmark}"
                )
                logger.error(
                    f"無効なブックマークオブジェクト: {type(bookmark)} - {bookmark}"
                )
                continue
            # 重複チェック（ファイルパスベース）
            folder_path = "/".join(bookmark.folder_path) if bookmark.folder_path else ""
            # ファイル名を生成（file_managerと同じロジック）
            filename = _sanitize_filename_for_check(bookmark.title, folder_path)
            file_path = f"{folder_path}/{filename}" if folder_path else filename
            is_duplicate = file_path in duplicate_paths

            # 選択状態チェック
            is_selected = any(b.url == bookmark.url for b in selected_bookmarks)

            # アイテム表示
            with st.container():
                col1, col2, col3 = st.columns([0.5, 8, 1.5])

                with col1:
                    # 選択チェックボックス
                    selected = st.checkbox(
                        "選択",
                        value=is_selected,
                        key=f"bookmark_select_{i}_{bookmark.url[:20]}",
                        label_visibility="collapsed",
                    )

                    # 選択状態の更新
                    if selected and not is_selected:
                        st.session_state.selected_bookmarks.append(bookmark)
                    elif not selected and is_selected:
                        st.session_state.selected_bookmarks = [
                            b for b in selected_bookmarks if b.url != bookmark.url
                        ]

                with col2:
                    # ブックマーク情報表示
                    title_display = (
                        bookmark.title[:60] + "..."
                        if len(bookmark.title) > 60
                        else bookmark.title
                    )

                    if is_duplicate:
                        st.markdown(f"🔄 **{title_display}** *(重複)*")
                    else:
                        st.markdown(f"📄 **{title_display}**")

                    st.markdown(f"🔗 [{bookmark.url[:80]}...]({bookmark.url})")

                    if bookmark.folder_path:
                        st.markdown(f"📁 {' > '.join(bookmark.folder_path)}")

                with col3:
                    # プレビューボタン
                    if st.button(
                        "👁️ プレビュー", key=f"preview_{i}_{bookmark.url[:20]}"
                    ):
                        st.session_state.preview_bookmark = bookmark
                        st.rerun()

                st.markdown("---")

    except Exception as e:
        st.error(f"❌ ブックマークアイテム表示でエラーが発生しました: {str(e)}")
        logger.error(f"ブックマークアイテム表示エラー: {e}")


def _display_integrated_preview():
    """統合されたプレビュー機能を表示"""
    try:
        preview_bookmark = st.session_state.get("preview_bookmark")

        if preview_bookmark:
            st.markdown("### 👁️ プレビュー")

            with st.expander(f"📄 {preview_bookmark.title}", expanded=True):
                col1, col2 = st.columns([3, 1])

                with col1:
                    st.markdown(
                        f"**📎 URL:** [{preview_bookmark.url}]({preview_bookmark.url})"
                    )

                    if preview_bookmark.folder_path:
                        st.markdown(
                            f"**📁 フォルダ:** {' > '.join(preview_bookmark.folder_path)}"
                        )

                    if preview_bookmark.add_date:
                        st.markdown(
                            f"**📅 追加日時:** {preview_bookmark.add_date.strftime('%Y-%m-%d %H:%M:%S')}"
                        )

                with col2:
                    if st.button("❌ プレビューを閉じる", key="close_preview"):
                        st.session_state.preview_bookmark = None
                        st.rerun()

    except Exception as e:
        logger.error(f"プレビュー表示エラー: {e}")


def _display_simple_bookmark_fallback(bookmarks: List[Bookmark]):
    """シンプルなフォールバック表示"""
    try:
        st.markdown("### 📄 シンプル表示モード")
        st.info(
            "⚠️ 通常の表示でエラーが発生したため、シンプル表示モードに切り替えました。"
        )

        for i, bookmark in enumerate(bookmarks[:10]):  # 最初の10件のみ
            st.markdown(f"**{i + 1}.** [{bookmark.title}]({bookmark.url})")

    except Exception as e:
        st.error(f"❌ フォールバック表示でもエラーが発生しました: {str(e)}")
        logger.error(f"フォールバック表示エラー: {e}")


def display_bookmark_structure_tree(
    directory_structure: Dict[str, List[str]], duplicates: Dict, directory_manager
) -> Tuple[int, int]:
    """ブックマーク構造をツリー形式で表示"""
    st.subheader("🌳 ディレクトリ構造")

    if not directory_structure:
        st.info("ディレクトリ構造が空です。")
        return 0, 0

    # 統計情報の計算
    total_files = sum(len(files) for files in directory_structure.values())
    duplicate_files_list = (
        duplicates.get("files", []) if isinstance(duplicates, dict) else []
    )
    duplicate_files = len(duplicate_files_list)

    # 統計表示
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("📁 総フォルダ数", len(directory_structure))
    with col2:
        st.metric("📄 総ファイル数", total_files)
    with col3:
        st.metric("🔄 重複ファイル数", duplicate_files)

    return total_files, duplicate_files


def show_page_preview(bookmark: Bookmark, index: int):
    """ブックマーク情報のプレビュー表示機能"""
    st.subheader(f"🔍 プレビュー: {bookmark.title}")

    # 基本情報の表示
    # ブックマークの型チェック
    if not hasattr(bookmark, "title"):
        st.error(f"❌ 無効なブックマークオブジェクト: {type(bookmark)}")
        return

    col1, col2 = st.columns([2, 1])

    with col1:
        st.markdown(f"**📎 URL:** [{bookmark.url}]({bookmark.url})")

        if bookmark.folder_path:
            st.markdown(f"**📁 フォルダ:** {' > '.join(bookmark.folder_path)}")

        if bookmark.add_date:
            st.markdown(
                f"**📅 追加日時:** {bookmark.add_date.strftime('%Y-%m-%d %H:%M:%S')}"
            )


# ===== ファイル保存関数 =====


def save_selected_pages_enhanced(
    selected_bookmarks: List[Bookmark], output_directory: Path
):
    """強化されたファイル保存機能"""
    if not selected_bookmarks:
        st.warning("保存するブックマークが選択されていません。")
        return

    st.subheader(f"💾 ファイル保存処理 ({len(selected_bookmarks)}件)")

    # 保存開始ボタン
    if st.button("🚀 保存開始", type="primary", use_container_width=True):
        # 初期化
        scraper = WebScraper()
        generator = MarkdownGenerator()
        # directory_manager = LocalDirectoryManager(output_directory)  # 未使用のため削除

        # 進捗表示の準備
        progress_bar = st.progress(0)
        status_text = st.empty()

        # 統計情報の初期化
        stats = {
            "total": len(selected_bookmarks),
            "completed": 0,
            "success": 0,
            "failed": 0,
            "skipped": 0,
        }

        # 処理開始時刻
        start_time = time.time()

        status_text.text(f"🌐 {len(selected_bookmarks)}件のブックマークを処理中...")

        # 各ブックマークを処理
        for i, bookmark in enumerate(selected_bookmarks):
            try:
                # 進捗更新
                progress = (i + 1) / stats["total"]
                progress_bar.progress(progress)
                status_text.text(
                    f"📄 処理中: {bookmark.title[:50]}... ({i + 1}/{stats['total']})"
                )

                # Webページの取得
                html_content = scraper.fetch_page_content(bookmark.url)

                if html_content:
                    # 記事内容の抽出
                    article_data = scraper.extract_article_content(
                        html_content, bookmark.url
                    )

                    if article_data:
                        # Markdownの生成
                        markdown_content = generator.generate_obsidian_markdown(
                            article_data, bookmark
                        )

                        # ファイルパスの生成
                        file_path = generator.generate_file_path(
                            bookmark, output_directory
                        )

                        # ディレクトリの作成
                        file_path.parent.mkdir(parents=True, exist_ok=True)

                        # ファイルの保存
                        with open(file_path, "w", encoding="utf-8") as f:
                            f.write(markdown_content)

                        stats["success"] += 1
                        logger.info(f"✅ 保存成功: {file_path}")
                    else:
                        stats["failed"] += 1
                        logger.error(f"❌ 記事抽出失敗: {bookmark.title}")
                else:
                    stats["failed"] += 1
                    logger.error(f"❌ ページ取得失敗: {bookmark.title}")

            except Exception as e:
                stats["failed"] += 1
                logger.error(f"💥 処理エラー: {bookmark.title} - {str(e)}")

            finally:
                stats["completed"] += 1

        # 処理完了
        progress_bar.progress(1.0)
        status_text.text("🎉 すべての処理が完了しました！")

        # 最終結果の表示
        st.success(f"✅ 処理完了: {stats['success']}件成功, {stats['failed']}件失敗")

        # 処理時間の表示
        total_time = time.time() - start_time
        st.info(f"⏱️ 総処理時間: {total_time / 60:.1f}分")


def save_selected_pages(selected_bookmarks: List[Bookmark], output_directory: Path):
    """進捗表示とエラーハンドリング機能を強化した保存機能"""
    if not selected_bookmarks:
        st.warning("保存するページが選択されていません")
        return

    st.subheader("📊 処理進捗")

    # 進捗バー
    progress_bar = st.progress(0)
    status_text = st.empty()

    # 統計情報
    col1, col2, col3 = st.columns(3)
    with col1:
        success_metric = st.metric("✅ 成功", 0)
    with col2:
        error_metric = st.metric("❌ エラー", 0)
    with col3:
        remaining_metric = st.metric("⏳ 残り", len(selected_bookmarks))

    scraper = WebScraper()
    generator = MarkdownGenerator()

    saved_count = 0
    error_count = 0

    # メイン処理ループ
    for i, bookmark in enumerate(selected_bookmarks):
        progress_value = (i + 1) / len(selected_bookmarks)
        progress_bar.progress(progress_value)

        status_text.text(f"📋 処理中: {i + 1}/{len(selected_bookmarks)} ページ")

        try:
            # ページ内容取得
            html_content = scraper.fetch_page_content(bookmark.url)

            if html_content:
                # コンテンツ抽出
                article_data = scraper.extract_article_content(
                    html_content, bookmark.url
                )

                if article_data:
                    # Markdown生成
                    markdown_content = generator.generate_obsidian_markdown(
                        article_data, bookmark
                    )

                    # ファイル保存
                    file_path = generator.generate_file_path(bookmark, output_directory)
                    file_path.parent.mkdir(parents=True, exist_ok=True)

                    with open(file_path, "w", encoding="utf-8") as f:
                        f.write(markdown_content)

                    saved_count += 1
                    logger.info(f"✅ ファイル保存成功: {file_path}")
                else:
                    error_count += 1
            else:
                error_count += 1

        except Exception as e:
            error_count += 1
            logger.error(f"💥 処理エラー: {bookmark.title} - {str(e)}")

        # メトリクス更新
        with col1:
            success_metric.metric("✅ 成功", saved_count)
        with col2:
            error_metric.metric("❌ エラー", error_count)
        with col3:
            remaining_metric.metric("⏳ 残り", len(selected_bookmarks) - i - 1)

    # 完了処理
    progress_bar.progress(1.0)
    status_text.text("🎉 処理完了！")

    # 結果サマリー
    st.markdown("---")
    st.subheader("📊 処理結果サマリー")

    if saved_count > 0:
        st.success(f"✅ {saved_count}個のファイルを正常に保存しました")

    if error_count > 0:
        st.error(f"❌ {error_count}個のファイルでエラーが発生しました")

    # 保存先情報
    st.info(f"📁 保存先: {output_directory}")

    # 処理完了ログ
    logger.info(f"🎉 処理完了: 成功={saved_count}, エラー={error_count}")
