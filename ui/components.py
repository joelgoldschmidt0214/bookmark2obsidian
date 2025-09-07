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

# 作成したモジュールからのインポート
from utils.models import Bookmark, Page, PageStatus
from utils.error_handler import error_logger
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
    """ページ一覧表示とプレビュー機能"""
    st.subheader("📋 ブックマーク一覧とプレビュー")

    if not bookmarks:
        st.warning("表示するブックマークがありません。")
        return

    # フォルダ別に整理
    folder_groups = organize_bookmarks_by_folder(bookmarks)

    # 表示モード選択
    display_mode = st.radio(
        "表示モード", ["📁 フォルダ別表示", "📄 一覧表示"], horizontal=True
    )

    if display_mode == "📁 フォルダ別表示":
        display_bookmark_tree(bookmarks, folder_groups, duplicates)
    else:
        display_bookmark_list_only(bookmarks, duplicates)


def organize_bookmarks_by_folder(
    bookmarks: List[Bookmark],
) -> Dict[tuple, List[Bookmark]]:
    """ブックマークをフォルダ別に整理"""
    folder_groups = {}

    for bookmark in bookmarks:
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
    """ブックマーク一覧のみを表示"""
    st.write("### 📄 ブックマーク一覧")

    # セッション状態の初期化
    if "selected_bookmarks" not in st.session_state:
        st.session_state.selected_bookmarks = []

    # 全選択/全解除ボタン
    col1, col2 = st.columns(2)

    with col1:
        if st.button("✅ 全選択", key="select_all_list"):
            st.session_state.selected_bookmarks = bookmarks.copy()
            st.rerun()

    with col2:
        if st.button("❌ 全解除", key="deselect_all_list"):
            st.session_state.selected_bookmarks = []
            st.rerun()


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
    duplicate_files = len(duplicates.get("files", []))

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
        directory_manager = LocalDirectoryManager(output_directory)

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
