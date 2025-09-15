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
from ui.progress_display import ProgressDisplay
from utils.cache_utils import clear_all_cache, get_cache_statistics
from utils.performance_utils import MemoryMonitor

# --- ログ設定 (変更なし) ---
log_level = logging.DEBUG if os.getenv("DEBUG") == "1" else logging.INFO
log_directory = Path("logs")
log_directory.mkdir(exist_ok=True)
log_filename = log_directory / f"bookmark2obsidian_{datetime.datetime.now().strftime('%Y%m%d')}.log"
handlers = [
    logging.StreamHandler(),
    logging.FileHandler(log_filename, encoding="utf-8"),
]
logging.basicConfig(
    level=log_level,
    format="%(asctime)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s",
    handlers=handlers,
)
logger = logging.getLogger(__name__)
logger.info(f"🚀 アプリケーション開始 (ログレベル: {logging.getLevelName(log_level)})")


# --- UIコンポーネント関数 (変更なし) ---
def display_performance_settings_ui():
    """パフォーマンス設定UIを表示"""
    st.markdown("---")
    st.subheader("⚡ パフォーマンス設定")
    batch_size = st.slider(
        "バッチサイズ",
        min_value=10,
        max_value=500,
        value=st.session_state.get("batch_size", 100),
        step=10,
        help="一度に処理するブックマークの数。大きくすると高速化しますが、メモリを多く使用します。",
    )
    st.session_state["batch_size"] = batch_size
    use_parallel = st.checkbox(
        "並列処理を使用",
        value=st.session_state.get("use_parallel_processing", True),
        help="複数のCPUコアを使用して処理を高速化します。",
    )
    st.session_state["use_parallel_processing"] = use_parallel


def display_cache_management_ui():
    """キャッシュ管理UIを表示"""
    try:
        st.markdown("---")
        st.subheader("🗄️ キャッシュ管理")
        cache_stats = get_cache_statistics()
        col1, col2 = st.columns(2)
        with col1:
            st.metric("キャッシュエントリ数", cache_stats.get("total_entries", 0))
            st.metric("キャッシュサイズ", f"{cache_stats.get('total_size_mb', 0.0):.1f} MB")
        with col2:
            st.metric("ヒット率", f"{cache_stats.get('hit_rate', 0.0):.1f}%")
            last_cleanup = cache_stats.get("last_cleanup", "不明")
            st.metric(
                "最終クリーンアップ",
                last_cleanup if isinstance(last_cleanup, str) else last_cleanup.strftime("%m/%d %H:%M"),
            )

        if st.button("🗑️ キャッシュをクリア", help="すべてのキャッシュを削除します"):
            clear_all_cache()
            st.success("✅ キャッシュを削除しました")
            st.rerun()

        force_reanalysis = st.checkbox(
            "🔄 強制再解析",
            value=st.session_state.get("force_reanalysis", False),
            help="キャッシュを無視して強制的に再解析します",
        )
        st.session_state["force_reanalysis"] = force_reanalysis
    except Exception as e:
        st.error(f"❌ キャッシュ管理UI表示エラー: {str(e)}")


def _check_file_cache_status(uploaded_file):
    """アップロードされたファイルのキャッシュ状況をチェック"""
    try:
        bytes_content = uploaded_file.getvalue()
        html_content_str = bytes_content.decode("utf-8")
        cache_manager = CacheManager()
        if cache_manager.load_from_cache(html_content_str):
            st.success("🗄️ このファイルの解析結果がキャッシュに見つかりました！")
            st.session_state["cache_available"] = True
        else:
            st.info("🔍 このファイルは初回解析です。結果はキャッシュに保存されます。")
            st.session_state["cache_available"] = False
    except Exception as e:
        st.warning(f"⚠️ キャッシュチェック中にエラー: {str(e)}")


def main():
    """メインアプリケーション関数"""
    st.set_page_config(page_title="Bookmark to Obsidian Converter", page_icon="📚", layout="wide")

    # --- セッション状態の初期化 ---
    if "app_state" not in st.session_state:
        st.session_state.app_state = "initial"
    if "analysis_future" not in st.session_state:
        st.session_state.analysis_future = None
    if "progress_info" not in st.session_state:
        st.session_state.progress_info = {}
    if "performance_stats" not in st.session_state:
        st.session_state.performance_stats = {}

    # --- サイドバー ---
    with st.sidebar:
        st.header("🔧 設定")
        uploaded_file = st.file_uploader("bookmarks.htmlを選択", type=["html"])
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

        default_path = st.session_state.get(
            "output_directory_str", "/mnt/d/hasechu/OneDrive/ドキュメント/Obsidian/hase_main/bookmarks"
        )  # os.path.expanduser("~"))
        directory_path = st.text_input("保存先ディレクトリ", value=default_path)
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
        st.markdown(f"📁 ファイル選択: {file_status}\n\n📂 ディレクトリ選択: {dir_status}")

        ready_to_proceed = st.session_state.get("file_validated") and st.session_state.get("directory_validated")
        if st.button("📊 ブックマーク解析を開始", type="primary", disabled=not ready_to_proceed):
            st.session_state.app_state = "parsing"
            keys_to_clear = [
                "bookmarks",
                "analysis_stats",
                "duplicates",
                "edge_case_result",
                "analysis_future",
                "progress_info",
            ]
            for key in keys_to_clear:
                st.session_state.pop(key, None)
            st.rerun()

        display_cache_management_ui()
        display_performance_settings_ui()
        with st.expander("ℹ️ アプリケーション情報"):
            show_application_info()

    # --- メインコンテンツエリア ---
    st.title("📚 Bookmark to Obsidian Converter")
    st.markdown("Chromeのブックマークファイルを解析し、Obsidian用のMarkdownファイルを生成します。")

    if st.session_state.app_state == "initial":
        st.info("サイドバーでファイルとディレクトリを設定し、「ブックマーク解析を開始」ボタンを押してください。")

    elif st.session_state.app_state == "parsing":
        handle_parsing_state()

    elif st.session_state.app_state == "results":
        handle_results_state()


def handle_parsing_state():
    """解析中の状態を処理する"""
    if st.session_state.analysis_future is None:
        with ThreadPoolExecutor(max_workers=1) as executor:
            st.session_state.executor = executor
            bytes_content = st.session_state.uploaded_file.getvalue()
            html_content_str = bytes_content.decode("utf-8")
            cache_manager = CacheManager()
            future = executor.submit(execute_optimized_bookmark_analysis, html_content_str, cache_manager)
            st.session_state.analysis_future = future

    future = st.session_state.analysis_future

    if "progress_display" not in st.session_state:
        st.session_state.progress_display = ProgressDisplay(title="ブックマーク解析進捗")

    progress_display = st.session_state.progress_display
    total_items = st.session_state.progress_info.get("total", 1)
    progress_display.initialize_display(total_items)

    if future.done():
        try:
            result = future.result()
            st.session_state.performance_stats = result["analysis_stats"]
            st.session_state.bookmarks = result["bookmarks"]
            st.session_state.analysis_stats = result["analysis_stats"]
            with st.spinner("重複チェックと最終処理中..."):
                directory_manager = LocalDirectoryManager(st.session_state["output_directory"])
                directory_manager.scan_directory()
                st.session_state.directory_manager = directory_manager
                st.session_state.duplicates = directory_manager.compare_with_bookmarks(result["bookmarks"])
                st.session_state.edge_case_result = handle_edge_cases_and_errors(result["bookmarks"])

            st.session_state.app_state = "results"
            st.session_state.analysis_future = None
            st.rerun()
        except Exception as e:
            st.error(f"解析処理中にエラーが発生しました: {e}")
            logger.error("解析フューチャーの取得でエラー", exc_info=True)
            st.session_state.app_state = "initial"
    else:
        # st.session_stateから進捗を読み取りUIを更新
        progress_info = st.session_state.get("progress_info", {})
        processed = progress_info.get("current", 0)
        total = progress_info.get("total", 1)

        # パフォーマンス情報を更新
        mem_monitor = st.session_state.get("mem_monitor")
        memory_usage = mem_monitor.get_memory_usage_mb() if mem_monitor else 0

        progress_display.update_progress(
            completed=processed, current_item=f"{processed}/{total} 件処理中", memory_usage_mb=memory_usage
        )
        st_autorefresh(interval=1000, limit=None, key="progress_refresh")


def handle_results_state():
    """解析結果の表示状態を処理する"""
    bookmarks = st.session_state.bookmarks
    duplicates = st.session_state.duplicates
    directory_manager = st.session_state.directory_manager

    if not bookmarks:
        st.warning("⚠️ 有効なブックマークが見つかりませんでした。")
        return

    stats = st.session_state.analysis_stats
    st.success(
        f"解析完了！ {stats['bookmark_count']}件のブックマークを{stats['parse_time']:.2f}秒で処理しました。",
        f" (キャッシュヒット: {stats['cache_hit']})",
    )

    # --- ✨修正点: st.tabsを使用してUIを整理 ---
    tab1, tab2, tab3 = st.tabs(["📊 概要", "📂 ブックマーク一覧", "⚠️ 特殊ケース"])

    with tab1:
        st.subheader("解析結果サマリー")
        dir_stats = directory_manager.get_statistics()
        parser = BookmarkParser()
        bookmark_stats = parser.get_statistics(bookmarks)

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("📚 総ブックマーク数", bookmark_stats["total_bookmarks"])
        with col2:
            st.metric("🌐 ユニークドメイン数", bookmark_stats["unique_domains"])
        with col3:
            st.metric("📁 フォルダ数", bookmark_stats["folder_count"])
        with col4:
            st.metric("🔄 重複ファイル数", dir_stats["duplicate_files"])

        st.subheader("⚡ パフォーマンス統計")
        perf_stats = st.session_state.performance_stats
        p_col1, p_col2, p_col3 = st.columns(3)
        with p_col1:
            st.metric("⏱️ 処理時間", f"{perf_stats.get('parse_time', 0):.2f} 秒")
        with p_col2:
            st.metric("🧠 ピークメモリ", f"{perf_stats.get('peak_memory_mb', 0):.1f} MB")
        with p_col3:
            st.metric("⚡ キャッシュヒット", "✅ Yes" if perf_stats.get("cache_hit") else "❌ No")

    with tab2:
        display_page_list_and_preview(bookmarks, duplicates, st.session_state["output_directory"])

    with tab3:
        if "edge_case_result" in st.session_state:
            display_edge_case_summary(st.session_state["edge_case_result"], show_details=True)


def execute_optimized_bookmark_analysis(html_content_str: str, cache_manager: CacheManager):
    """最適化されたブックマーク解析を実行（UI操作から分離）"""
    start_time = time.time()
    mem_monitor = MemoryMonitor()
    st.session_state["mem_monitor"] = mem_monitor

    # --- ✨修正点: 進捗コールバックをより詳細な情報を渡すように修正 ---
    def progress_callback(current, total, message=""):
        st.session_state.progress_info = {"current": current, "total": total, "message": message}

    try:
        bookmarks, cache_hit = None, False

        if not st.session_state.get("force_reanalysis", False):
            cached_bookmarks = cache_manager.load_from_cache(html_content_str)
            if cached_bookmarks:
                bookmarks, cache_hit = cached_bookmarks, True
                progress_callback(1, 1, "キャッシュから読み込み完了")  # 進捗を100%に

        if bookmarks is None:
            parser = BookmarkParser()  # rules.ymlのパスは必要に応じて指定
            bookmarks = parser.parse(html_content_str)
            cache_manager.save_to_cache(html_content_str, bookmarks)
            # parseの結果をフィルタリングする必要があればここで行う
            # filtered_bookmarks = [b for b in bookmarks if not parser._should_exclude_bookmark(b)]
            # bookmarks = filtered_bookmarks

        unique_bookmarks_dict = {b.url: b for b in reversed(bookmarks)}
        bookmarks = list(unique_bookmarks_dict.values())

        parse_time = time.time() - start_time
        peak_memory = mem_monitor.get_memory_delta()

        analysis_stats = {
            "parse_time": parse_time,
            "cache_hit": cache_hit,
            "bookmark_count": len(bookmarks),
            "peak_memory_mb": peak_memory,
        }
        return {"bookmarks": bookmarks, "analysis_stats": analysis_stats}
    except Exception:
        logger.error("ブックマーク解析のスレッドでエラー発生", exc_info=True)
        raise


if __name__ == "__main__":
    main()
