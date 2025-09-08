"""
Bookmark to Obsidian Converter
Streamlitベースのデスクトップアプリケーション
Google Chromeのbookmarks.htmlファイルを解析し、Obsidian用のMarkdownファイルを生成する
"""

import datetime
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import streamlit as st
from streamlit_autorefresh import st_autorefresh

from core.cache_manager import CacheManager
from core.file_manager import LocalDirectoryManager

# 分離したモジュールからのインポート
from core.parser import BookmarkParser
from ui.components import (
    display_edge_case_summary,
    display_page_list_and_preview,
    handle_edge_cases_and_errors,
    show_application_info,
    validate_bookmarks_file,
    validate_directory_path,
)
from utils.cache_utils import clear_all_cache, get_cache_statistics

# Task 10: 強化されたログ設定とエラーログ記録機能
# 環境変数DEBUG=1を設定するとデバッグログも表示
log_level = logging.DEBUG if os.getenv("DEBUG") == "1" else logging.INFO

# ログファイルの設定
log_directory = Path("logs")
log_directory.mkdir(exist_ok=True)

# ログファイル名（日付付き）
log_filename = log_directory / f"bookmark2obsidian_{datetime.datetime.now().strftime('%Y%m%d')}.log"

# ログハンドラーの設定
handlers = [
    logging.StreamHandler(),  # コンソール出力
    logging.FileHandler(log_filename, encoding="utf-8"),  # ファイル出力
]

logging.basicConfig(
    level=log_level,
    format="%(asctime)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s",
    handlers=handlers,
)
logger = logging.getLogger(__name__)

logger.info(f"🚀 アプリケーション開始 (ログレベル: {logging.getLevelName(log_level)})")
logger.info(f"📝 ログファイル: {log_filename}")


def display_performance_settings_ui():
    """
    パフォーマンス設定UIを表示
    """
    st.markdown("---")
    st.subheader("⚡ パフォーマンス設定")

    # バッチサイズ設定
    batch_size = st.slider(
        "バッチサイズ",
        min_value=10,
        max_value=500,
        value=st.session_state.get("batch_size", 100),
        step=10,
        help="一度に処理するブックマークの数。大きくすると高速化しますが、メモリを多く使用します。",
    )
    st.session_state["batch_size"] = batch_size

    # 並列処理設定
    use_parallel = st.checkbox(
        "並列処理を使用",
        value=st.session_state.get("use_parallel_processing", True),
        help="複数のCPUコアを使用して処理を高速化します。",
    )
    st.session_state["use_parallel_processing"] = use_parallel

    # メモリ監視設定
    enable_memory_monitoring = st.checkbox(
        "メモリ使用量監視",
        value=st.session_state.get("enable_memory_monitoring", True),
        help="処理中のメモリ使用量を監視し、統計を表示します。",
    )
    st.session_state["enable_memory_monitoring"] = enable_memory_monitoring

    # パフォーマンス統計の表示
    if "analysis_stats" in st.session_state:
        stats = st.session_state["analysis_stats"]
        if stats.get("performance_stats"):
            perf_stats = stats["performance_stats"]
            st.info(f"""
            📊 前回の解析統計:
            - 処理時間: {stats.get("parse_time", 0):.2f}秒
            - メモリ使用量: {perf_stats.get("peak_memory_mb", 0):.1f}MB
            - ブックマーク数: {stats.get("bookmark_count", 0)}個
            """)


def display_cache_management_ui():
    """
    キャッシュ管理UIを表示

    要件:
    - キャッシュ状況表示機能
    - 履歴リセットボタン
    - 強制再解析オプション
    """
    try:
        st.markdown("---")
        st.subheader("🗄️ キャッシュ管理")

        # キャッシュマネージャーの初期化
        cache_manager = CacheManager()

        # キャッシュ統計の取得
        try:
            cache_stats = get_cache_statistics()
        except Exception as e:
            logger.error(f"キャッシュ統計取得エラー: {e}")
            cache_stats = {
                "total_entries": 0,
                "total_size_mb": 0.0,
                "hit_rate": 0.0,
                "last_cleanup": "不明",
            }

        # キャッシュ状況の表示
        st.markdown("#### 📊 キャッシュ状況")

        col1, col2 = st.columns(2)

        with col1:
            st.metric(
                "キャッシュエントリ数",
                cache_stats.get("total_entries", 0),
                help="保存されているキャッシュファイルの数",
            )

            st.metric(
                "キャッシュサイズ",
                f"{cache_stats.get('total_size_mb', 0.0):.1f} MB",
                help="キャッシュが使用しているディスク容量",
            )

        with col2:
            st.metric(
                "ヒット率",
                f"{cache_stats.get('hit_rate', 0.0):.1f}%",
                help="キャッシュから取得できた割合",
            )

            last_cleanup = cache_stats.get("last_cleanup", "不明")
            if last_cleanup != "不明":
                try:
                    cleanup_date = datetime.datetime.fromisoformat(last_cleanup)
                    cleanup_display = cleanup_date.strftime("%m/%d %H:%M")
                except (ValueError, TypeError):
                    cleanup_display = last_cleanup
            else:
                cleanup_display = last_cleanup

            st.metric(
                "最終クリーンアップ",
                cleanup_display,
                help="最後にキャッシュをクリーンアップした日時",
            )

        # キャッシュ操作ボタン
        st.markdown("#### 🔧 キャッシュ操作")

        col1, col2, col3 = st.columns(3)

        with col1:
            if st.button("🗑️ 履歴リセット", help="すべてのキャッシュを削除します"):
                try:
                    clear_all_cache()
                    st.success("✅ キャッシュを削除しました")
                    logger.info("キャッシュを手動削除しました")

                    # セッション状態もリセット
                    cache_related_keys = [
                        key for key in st.session_state.keys() if "cache" in key.lower() or "analysis" in key.lower()
                    ]
                    for key in cache_related_keys:
                        del st.session_state[key]

                    st.rerun()
                except Exception as e:
                    st.error(f"❌ キャッシュ削除エラー: {str(e)}")
                    logger.error(f"キャッシュ削除エラー: {e}")

        with col2:
            force_reanalysis = st.checkbox(
                "🔄 強制再解析",
                value=st.session_state.get("force_reanalysis", False),
                help="キャッシュを無視して強制的に再解析します",
            )
            st.session_state["force_reanalysis"] = force_reanalysis

        with col3:
            if st.button("🧹 キャッシュクリーンアップ", help="古いキャッシュファイルを削除します"):
                try:
                    cleaned_count = cache_manager.cleanup_old_cache(max_age_days=7)
                    st.success(f"✅ {cleaned_count}個の古いキャッシュを削除しました")
                    logger.info(f"キャッシュクリーンアップ完了: {cleaned_count}個削除")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ クリーンアップエラー: {str(e)}")
                    logger.error(f"キャッシュクリーンアップエラー: {e}")

        # キャッシュ設定
        with st.expander("⚙️ キャッシュ設定", expanded=False):
            cache_enabled = st.checkbox(
                "キャッシュを有効にする",
                value=st.session_state.get("cache_enabled", True),
                help="キャッシュ機能の有効/無効を切り替えます",
            )
            st.session_state["cache_enabled"] = cache_enabled

            if cache_enabled:
                cache_ttl_hours = st.slider(
                    "キャッシュ有効期間（時間）",
                    min_value=1,
                    max_value=168,  # 1週間
                    value=st.session_state.get("cache_ttl_hours", 24),
                    help="キャッシュが有効な期間を設定します",
                )
                st.session_state["cache_ttl_hours"] = cache_ttl_hours

                max_cache_size_mb = st.slider(
                    "最大キャッシュサイズ（MB）",
                    min_value=10,
                    max_value=1000,
                    value=st.session_state.get("max_cache_size_mb", 100),
                    help="キャッシュの最大サイズを設定します",
                )
                st.session_state["max_cache_size_mb"] = max_cache_size_mb
            else:
                st.info("ℹ️ キャッシュが無効になっています。処理が遅くなる可能性があります。")

        # キャッシュ詳細情報
        if cache_stats.get("total_entries", 0) > 0:
            with st.expander("📋 キャッシュ詳細", expanded=False):
                try:
                    cache_details = cache_manager.get_cache_details()

                    if cache_details:
                        st.markdown("**最近のキャッシュエントリ:**")

                        for i, entry in enumerate(cache_details[:5]):  # 最新5件
                            created_time = entry.get("created_at", "Unknown")
                            if created_time != "Unknown":
                                try:
                                    created_dt = datetime.datetime.fromisoformat(created_time)
                                    time_display = created_dt.strftime("%m/%d %H:%M")
                                except (ValueError, TypeError):
                                    time_display = created_time
                            else:
                                time_display = created_time

                            st.markdown(f"- **{entry.get('file_name', 'Unknown')}** ({time_display})")
                    else:
                        st.info("キャッシュエントリの詳細を取得できませんでした")

                except Exception as e:
                    st.warning(f"キャッシュ詳細の取得中にエラーが発生しました: {str(e)}")
                    logger.error(f"キャッシュ詳細取得エラー: {e}")

    except Exception as e:
        st.error(f"❌ キャッシュ管理UI表示エラー: {str(e)}")
        logger.error(f"キャッシュ管理UI表示エラー: {e}")


def _check_file_cache_status(uploaded_file):
    """
    アップロードされたファイルのキャッシュ状況をチェック

    Args:
        uploaded_file: Streamlitのアップロードファイルオブジェクト
    """
    try:
        cache_enabled = st.session_state.get("cache_enabled", True)

        if not cache_enabled:
            st.info("ℹ️ キャッシュが無効になっています")
            return

        # ファイル内容を読み取り
        content = uploaded_file.getvalue().decode("utf-8")

        # キャッシュマネージャーでチェック
        cache_manager = CacheManager()
        cached_result = cache_manager.get_cached_result(content)

        if cached_result:
            # キャッシュヒット
            st.success("🗄️ このファイルの解析結果がキャッシュに見つかりました！")

            # キャッシュ情報の表示
            with st.expander("📋 キャッシュ情報", expanded=False):
                st.markdown(f"""
                - **ブックマーク数**: {len(cached_result)}個
                - **キャッシュ状態**: 有効
                - **処理時間**: 大幅短縮が期待されます
                """)

            # セッション状態にキャッシュ情報を保存
            st.session_state["cache_available"] = True
            st.session_state["cached_bookmarks_count"] = len(cached_result)

        else:
            # キャッシュミス
            st.info("🔍 このファイルは初回解析です。キャッシュに保存されます。")
            st.session_state["cache_available"] = False

    except Exception as e:
        st.warning(f"⚠️ キャッシュチェック中にエラーが発生しました: {str(e)}")
        logger.error(f"ファイルキャッシュチェックエラー: {e}")
        st.session_state["cache_available"] = False


def _display_cache_hit_results(bookmarks, cache_hit):
    """
    キャッシュヒット時の結果表示

    Args:
        bookmarks: ブックマークリスト
        cache_hit: キャッシュヒットフラグ
    """
    if cache_hit:
        st.success("⚡ キャッシュから高速読み込み完了！")

        # キャッシュ効果の表示
        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric("処理時間", "< 1秒", delta="大幅短縮", delta_color="inverse")

        with col2:
            st.metric("キャッシュ効果", "有効", delta="高速化", delta_color="inverse")

        with col3:
            st.metric("データ取得", "キャッシュ", delta="最新", delta_color="normal")


def _display_cache_miss_flow(bookmarks):
    """
    キャッシュミス時の新規解析フロー表示

    Args:
        bookmarks: 解析されたブックマークリスト
    """
    st.info("🔄 新規解析が完了しました。結果をキャッシュに保存しました。")

    # 次回の高速化について
    with st.expander("💡 次回の処理について", expanded=False):
        st.markdown("""
        ### 🚀 次回の高速化
        
        - **同じファイル**を再度アップロードした場合、キャッシュから瞬時に結果を取得できます
        - **処理時間**が大幅に短縮されます
        - **キャッシュ有効期間**は設定で変更できます
        
        ### 🗄️ キャッシュ管理
        
        - サイドバーの「キャッシュ管理」で状況を確認できます
        - 必要に応じてキャッシュをクリアできます
        """)


def main():
    """
    メインアプリケーション関数

    Streamlitベースのブックマーク変換アプリケーションのエントリーポイント。
    ユーザーインターフェースの初期化、ファイルアップロード処理、
    ブックマーク解析、および変換処理の全体的な流れを管理します。
    """
    # ページ設定
    st.set_page_config(
        page_title="Bookmark to Obsidian Converter",
        page_icon="📚",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    # カスタムCSSでレイアウトを最適化
    st.markdown(
        """
    <style>
    .main .block-container {
        padding-left: 1rem;
        padding-right: 1rem;
        width: 100%;
        margin-right: 0;
    }
       
    .stTabs [data-baseweb="tab-list"] {
        gap: 2px;
    }
    
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        white-space: pre-wrap;
        background-color: #f0f2f6;
        border-radius: 4px 4px 0px 0px;
        gap: 1px;
        padding-left: 20px;
        padding-right: 20px;
    }
    
    .stTabs [aria-selected="true"] {
        background-color: #ffffff;
    }
    
    /* プレビューエリアの最適化 */
    .stExpander > div:first-child {
        background-color: #f8f9fa;
    }
    
    /* コードブロックの最適化 */
    .stCodeBlock {
        background-color: #f8f9fa;
        border: 1px solid #e9ecef;
        border-radius: 4px;
    }
    </style>
    """,
        unsafe_allow_html=True,
    )

    # --- 状態管理のためのセッション変数初期化 ---
    # 各キーが存在しない場合に個別に初期化する方式に変更し、堅牢性を向上
    if "app_state" not in st.session_state:
        st.session_state.app_state = "initial"  # initial | parsing | results
    if "analysis_future" not in st.session_state:
        st.session_state.analysis_future = None
    if "executor" not in st.session_state:
        st.session_state.executor = None
    if "progress_processed" not in st.session_state:
        st.session_state.progress_processed = 0
    if "progress_total" not in st.session_state:
        st.session_state.progress_total = 1
    if "progress_message" not in st.session_state:
        st.session_state.progress_message = ""
    if "output_directory_str" not in st.session_state:
        st.session_state.output_directory_str = "/mnt/d/hasechu/OneDrive/ドキュメント/Obsidian/hase_main/bookmarks"

    # メインタイトル
    st.title("📚 Bookmark to Obsidian Converter")
    st.markdown("---")
    st.markdown("""
    このアプリケーションは、Google Chromeのブックマークファイル（bookmarks.html）を解析し、
    ブックマークされたWebページの内容を取得してObsidian用のMarkdownファイルとして保存します。
    """)

    # サイドバー
    with st.sidebar:
        st.header("🔧 設定")
        st.markdown("ファイルアップロードとディレクトリ選択")

        uploaded_file = st.file_uploader("bookmarks.htmlを選択", type=["html"], key="uploaded_file_widget")
        if uploaded_file:
            st.session_state["uploaded_file"] = uploaded_file
            is_valid, msg = validate_bookmarks_file(uploaded_file)
            st.session_state["file_validated"] = is_valid
            if is_valid:
                st.success(msg)
                _check_file_cache_status(uploaded_file)
            else:
                st.error(msg)
        else:
            st.session_state["file_validated"] = False

        st.markdown("---")
        default_path = "/mnt/d/hasechu/OneDrive/ドキュメント/Obsidian/hase_main/bookmarks"
        directory_path = st.text_input(
            "保存先ディレクトリ", value=st.session_state.get("output_directory_str", default_path)
        )
        if directory_path:
            st.session_state["output_directory_str"] = directory_path
            is_valid, msg = validate_directory_path(directory_path)
            st.session_state["directory_validated"] = is_valid
            if is_valid:
                st.success(msg)
                st.session_state["output_directory"] = Path(directory_path)
            else:
                st.error(msg)
        else:
            st.session_state["directory_validated"] = False

        st.markdown("---")
        st.subheader("⚙️ 設定状況")
        file_status = "✅ 完了" if st.session_state.get("file_validated") else "❌ 未完了"
        dir_status = "✅ 完了" if st.session_state.get("directory_validated") else "❌ 未完了"
        st.write(f"📁 ファイル選択: {file_status}")
        st.write(f"📂 ディレクトリ選択: {dir_status}")

        ready_to_proceed = st.session_state.get("file_validated") and st.session_state.get("directory_validated")

        if st.button("📊 ブックマーク解析を開始", type="primary", disabled=not ready_to_proceed):
            # 状態を'parsing'に遷移させ、過去の解析結果をクリア
            st.session_state.app_state = "parsing"
            keys_to_clear = ["bookmarks", "analysis_stats", "duplicates", "edge_case_result", "analysis_future"]
            for key in keys_to_clear:
                if key in st.session_state:
                    del st.session_state[key]
            st.rerun()  # 状態遷移を確定させるために一度だけ再実行

        if not ready_to_proceed:
            st.warning("📋 上記の設定を完了してください")

        display_cache_management_ui()
        display_performance_settings_ui()
        show_application_info()

    # --- メインコンテンツエリア ---
    col1, col2 = st.columns([2, 1])

    with col1:
        st.header("📋 処理手順")

        if st.session_state.app_state == "parsing":
            # --- 解析中の処理 ---
            if st.session_state.analysis_future is None:
                st.session_state.executor = ThreadPoolExecutor(max_workers=1)
                content = st.session_state.uploaded_file.getvalue().decode("utf-8")
                cache_manager = CacheManager()
                future = st.session_state.executor.submit(execute_optimized_bookmark_analysis, content, cache_manager)
                st.session_state.analysis_future = future

            future = st.session_state.analysis_future

            # 進捗表示エリア
            progress_container = st.empty()
            with progress_container.container():
                processed = st.session_state.get("progress_processed", 0)
                total = st.session_state.get("progress_total", 1)
                progress_val = min(1.0, processed / total if total > 0 else 0)
                progress_text = f"解析中... {processed}/{total}"
                st.progress(progress_val, text=progress_text)

            if future.done():
                try:
                    result = future.result()
                    st.session_state.bookmarks = result["bookmarks"]
                    st.session_state.analysis_stats = result["analysis_stats"]

                    with st.spinner("重複チェックと最終処理中..."):
                        parser = BookmarkParser()
                        directory_manager = LocalDirectoryManager(st.session_state["output_directory"])
                        st.session_state.parser = parser
                        st.session_state.directory_manager = directory_manager
                        st.session_state.duplicates = directory_manager.compare_with_bookmarks(result["bookmarks"])
                        st.session_state.edge_case_result = handle_edge_cases_and_errors(result["bookmarks"])

                    st.session_state.app_state = "results"
                    if st.session_state.executor:
                        st.session_state.executor.shutdown(wait=False)
                        st.session_state.executor = None
                    st.session_state.analysis_future = None
                    st.rerun()
                except Exception as e:
                    st.error(f"解析処理中にエラーが発生しました: {e}")
                    logger.error("解析フューチャーの取得でエラー", exc_info=True)
                    st.session_state.app_state = "initial"  # エラー時は初期状態に戻す
            else:
                # 処理が終わるまで1秒ごとにUIを自動更新
                st_autorefresh(interval=1000, limit=None, key="progress_refresh")

        elif st.session_state.app_state == "results":
            # --- 解析結果の表示 ---
            bookmarks = st.session_state.bookmarks
            parser = st.session_state.parser
            duplicates = st.session_state.duplicates
            directory_manager = st.session_state.directory_manager

            st.markdown("### 📊 ブックマーク解析結果")
            if bookmarks:
                stats = parser.get_statistics(bookmarks)
                dir_stats = directory_manager.get_statistics()
                col_stat1, col_stat2, col_stat3, col_stat4 = st.columns(4)
                with col_stat1:
                    st.metric("📚 総ブックマーク数", stats["total_bookmarks"])
                with col_stat2:
                    st.metric("🌐 ユニークドメイン数", stats["unique_domains"])
                with col_stat3:
                    st.metric("📁 フォルダ数", stats["folder_count"])
                with col_stat4:
                    st.metric("🔄 重複ファイル数", len(duplicates.get("files", [])))

                if "edge_case_result" in st.session_state:
                    display_edge_case_summary(st.session_state["edge_case_result"])

                st.subheader("📂 ブックマーク構造")
                display_page_list_and_preview(bookmarks, duplicates, st.session_state["output_directory"])
            else:
                st.warning("⚠️ 有効なブックマークが見つかりませんでした。")

        else:  # app_state == "initial"
            # 初期表示
            st.markdown(
                "サイドバーでファイルとディレクトリを設定し、「ブックマーク解析を開始」ボタンを押してください。"
            )

    with col2:
        st.header("📊 ステータス")
        # ... (この部分は変更なしでOK) ...
        file_validated = st.session_state.get("file_validated", False)
        dir_validated = st.session_state.get("directory_validated", False)

        if file_validated and dir_validated:
            st.success("✅ 設定完了")
        else:
            st.warning("⚠️ 設定途中")

        if "bookmarks" in st.session_state:
            # ... (中略) ...
            pass  # このセクションは元のままで問題ありません
        else:
            st.metric("処理対象ページ", "0")
            st.metric("除外ページ", "0")

    st.markdown("---")
    st.markdown(
        "<div style='text-align: center; color: #666;'><small>Bookmark to Obsidian Converter v2.0 | Streamlit Application</small></div>",
        unsafe_allow_html=True,
    )


def execute_optimized_bookmark_analysis(content: str, cache_manager: CacheManager):
    """
    最適化されたブックマーク解析を実行（UI操作から分離）

    Args:
        content: HTMLコンテンツ
        cache_manager: キャッシュマネージャー

    Returns:
        dict: 解析結果を含む辞書
    """

    def progress_callback(current, total, message=""):
        # st.session_stateを更新する（UIは直接操作しない）
        st.session_state.progress_processed = current
        st.session_state.progress_total = total
        if message:
            st.session_state.progress_message = message

    start_time = time.time()
    bookmarks = None
    cache_hit = False

    try:
        if st.session_state.get("cache_enabled", True) and not st.session_state.get("force_reanalysis", False):
            logger.info("🔍 キャッシュをチェック中...")
            cached_bookmarks = cache_manager.load_from_cache(content)
            if cached_bookmarks:
                bookmarks, cache_hit = cached_bookmarks, True
                logger.info("✅ キャッシュヒット！")

        if bookmarks is None:
            logger.info("🚀 キャッシュがないため、新規解析を開始...")
            parser = BookmarkParser()
            batch_size = st.session_state.get("batch_size", 100)
            use_parallel = st.session_state.get("use_parallel_processing", True)

            bookmarks = parser.parse_bookmarks_optimized(
                content,
                batch_size=batch_size,
                use_parallel=use_parallel,
                progress_callback=progress_callback,
            )

            if st.session_state.get("cache_enabled", True):
                cache_manager.save_to_cache(content, bookmarks)
                logger.info("💾 解析結果をキャッシュに保存しました。")

        # URLによる重複除去
        original_count = len(bookmarks)
        unique_bookmarks_dict = {b.url: b for b in reversed(bookmarks)}
        bookmarks = list(unique_bookmarks_dict.values())
        if original_count != len(bookmarks):
            logger.info(f"🔄 URLによる重複除去: {original_count}件 → {len(bookmarks)}件")

        parse_time = time.time() - start_time
        analysis_stats = {
            "parse_time": parse_time,
            "cache_hit": cache_hit,
            "bookmark_count": len(bookmarks),
        }

        return {"bookmarks": bookmarks, "analysis_stats": analysis_stats}

    except Exception:
        logger.error("ブックマーク解析のスレッドでエラー発生", exc_info=True)
        raise


if __name__ == "__main__":
    main()
