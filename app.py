"""
Bookmark to Obsidian Converter
Streamlitベースのデスクトップアプリケーション
Google Chromeのbookmarks.htmlファイルを解析し、Obsidian用のMarkdownファイルを生成する
"""

import streamlit as st
from pathlib import Path
import datetime
import os
import logging
import time
from urllib.parse import urlparse

# 分離したモジュールからのインポート
from core.parser import BookmarkParser
from core.file_manager import LocalDirectoryManager
from core.cache_manager import CacheManager
from utils.cache_utils import get_cache_statistics, clear_all_cache
from ui.components import (
    validate_bookmarks_file,
    validate_directory_path,
    handle_edge_cases_and_errors,
    display_edge_case_summary,
    display_user_friendly_messages,
    show_application_info,
    display_page_list_and_preview,
    display_bookmark_structure_tree,
    display_bookmark_list_only,
    show_page_preview,
)

# Task 10: 強化されたログ設定とエラーログ記録機能
# 環境変数DEBUG=1を設定するとデバッグログも表示
log_level = logging.DEBUG if os.getenv("DEBUG") == "1" else logging.INFO

# ログファイルの設定
log_directory = Path("logs")
log_directory.mkdir(exist_ok=True)

# ログファイル名（日付付き）
log_filename = (
    log_directory
    / f"bookmark2obsidian_{datetime.datetime.now().strftime('%Y%m%d')}.log"
)

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
                except:
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
                        key
                        for key in st.session_state.keys()
                        if "cache" in key.lower() or "analysis" in key.lower()
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
            if st.button(
                "🧹 キャッシュクリーンアップ", help="古いキャッシュファイルを削除します"
            ):
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
                st.info(
                    "ℹ️ キャッシュが無効になっています。処理が遅くなる可能性があります。"
                )

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
                                    created_dt = datetime.datetime.fromisoformat(
                                        created_time
                                    )
                                    time_display = created_dt.strftime("%m/%d %H:%M")
                                except:
                                    time_display = created_time
                            else:
                                time_display = created_time

                            st.markdown(
                                f"- **{entry.get('file_name', 'Unknown')}** ({time_display})"
                            )
                    else:
                        st.info("キャッシュエントリの詳細を取得できませんでした")

                except Exception as e:
                    st.warning(
                        f"キャッシュ詳細の取得中にエラーが発生しました: {str(e)}"
                    )
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
            type=["html"],
            help="Google Chromeのブックマークエクスポートファイル（bookmarks.html）を選択してください",
        )

        # ファイル検証結果の表示
        if uploaded_file is not None:
            logger.info(
                f"📁 ファイルアップロード: {uploaded_file.name} (サイズ: {uploaded_file.size} bytes)"
            )
            is_valid_file, file_message = validate_bookmarks_file(uploaded_file)
            if is_valid_file:
                st.success(file_message)
                logger.info(f"✅ ファイル検証成功: {file_message}")

                # セッション状態にファイルを保存
                st.session_state["uploaded_file"] = uploaded_file
                st.session_state["file_validated"] = True

                # キャッシュ検出機能
                _check_file_cache_status(uploaded_file)
            else:
                st.error(file_message)
                logger.error(f"❌ ファイル検証失敗: {file_message}")
                st.session_state["file_validated"] = False
        else:
            st.session_state["file_validated"] = False

        st.markdown("---")

        # ディレクトリ選択機能
        st.subheader("📂 保存先ディレクトリ")

        # デフォルトパスの提案
        default_path = str(Path.home() / "Documents" / "Obsidian")

        directory_path = st.text_input(
            "Obsidianファイルの保存先パスを入力してください",
            value=default_path,
            help="Markdownファイルを保存するディレクトリのフルパスを入力してください",
        )

        # ディレクトリ検証結果の表示
        if directory_path:
            logger.info(f"📂 ディレクトリ指定: {directory_path}")
            is_valid_dir, dir_message = validate_directory_path(directory_path)
            if is_valid_dir:
                st.success(dir_message)
                logger.info(f"✅ ディレクトリ検証成功: {directory_path}")
                # セッション状態にディレクトリパスを保存
                st.session_state["output_directory"] = Path(directory_path)
                st.session_state["directory_validated"] = True
            else:
                st.error(dir_message)
                logger.error(f"❌ ディレクトリ検証失敗: {dir_message}")
                st.session_state["directory_validated"] = False
        else:
            st.session_state["directory_validated"] = False

        st.markdown("---")

        # 設定状況の表示
        st.subheader("⚙️ 設定状況")
        file_status = (
            "✅ 完了" if st.session_state.get("file_validated", False) else "❌ 未完了"
        )
        dir_status = (
            "✅ 完了"
            if st.session_state.get("directory_validated", False)
            else "❌ 未完了"
        )

        st.write(f"📁 ファイル選択: {file_status}")
        st.write(f"📂 ディレクトリ選択: {dir_status}")

        # 次のステップへの準備状況
        ready_to_proceed = st.session_state.get(
            "file_validated", False
        ) and st.session_state.get("directory_validated", False)

        if ready_to_proceed:
            st.success("🚀 解析を開始する準備が整いました！")

            # ブックマーク解析ボタン
            if st.button("📊 ブックマーク解析を開始", type="primary"):
                st.session_state["start_analysis"] = True
        else:
            st.info("📋 上記の設定を完了してください")

        # キャッシュ管理UI
        display_cache_management_ui()

        # Task 12: ユーザビリティ向上機能の追加
        display_user_friendly_messages()
        show_application_info()

    # メインコンテンツエリア
    col1, col2 = st.columns([2, 1])

    with col1:
        st.header("📋 処理手順")

        # 設定状況に応じた手順表示
        ready_to_proceed = st.session_state.get(
            "file_validated", False
        ) and st.session_state.get("directory_validated", False)

        if ready_to_proceed:
            # ブックマーク解析の実行
            if st.session_state.get("start_analysis", False):
                st.markdown("### 📊 ブックマーク解析結果")

                try:
                    # ファイル内容を読み取り
                    uploaded_file = st.session_state["uploaded_file"]
                    content = uploaded_file.read().decode("utf-8")
                    uploaded_file.seek(0)  # ファイルポインタをリセット

                    # ブックマーク解析の実行
                    # プログレスバーとログ表示の改善
                    progress_container = st.container()
                    log_container = st.container()

                    with progress_container:
                        st.subheader("📊 ブックマーク解析進捗")
                        progress_bar = st.progress(0)
                        status_text = st.empty()

                    with log_container:
                        log_placeholder = st.empty()
                        logs = []

                        def add_log(message):
                            logs.append(f"• {message}")
                            log_placeholder.text_area(
                                "📝 処理ログ", "\\n".join(logs[-10:]), height=200
                            )

                        # ステップ1: ブックマーク解析
                        status_text.text("📊 ブックマークファイルを解析中...")
                        progress_bar.progress(0.1)

                        start_time = time.time()
                        add_log("📊 ブックマーク解析を開始...")

                        # キャッシュ機能の統合
                        cache_manager = CacheManager()
                        force_reanalysis = st.session_state.get(
                            "force_reanalysis", False
                        )
                        cache_enabled = st.session_state.get("cache_enabled", True)

                        bookmarks = None
                        cache_hit = False

                        # キャッシュチェック（強制再解析でない場合）
                        if cache_enabled and not force_reanalysis:
                            try:
                                add_log("🗄️ キャッシュをチェック中...")
                                cached_result = cache_manager.get_cached_result(content)

                                if cached_result:
                                    bookmarks = cached_result
                                    cache_hit = True
                                    add_log(
                                        "✅ キャッシュヒット！既存の解析結果を使用します"
                                    )
                                else:
                                    add_log("❌ キャッシュミス。新規解析を実行します")
                            except Exception as e:
                                add_log(f"⚠️ キャッシュチェックエラー: {str(e)}")
                                logger.error(f"キャッシュチェックエラー: {e}")

                        # 新規解析（キャッシュヒットしなかった場合）
                        if bookmarks is None:
                            parser = BookmarkParser()
                            add_log("🔍 HTMLパーサーを初期化...")

                            # ブックマーク解析の詳細ログ
                            add_log("📄 HTMLコンテンツを解析中...")
                            add_log("🔍 HTMLパーサーでDOMツリーを構築中...")
                            add_log("📂 フォルダ構造を解析中...")
                            add_log("🔗 ブックマークリンクを抽出中...")

                            bookmarks = parser.parse_bookmarks(content)

                            # 解析結果をキャッシュに保存
                            if cache_enabled and bookmarks:
                                try:
                                    cache_manager.save_to_cache(content, bookmarks)
                                    add_log("💾 解析結果をキャッシュに保存しました")
                                except Exception as e:
                                    add_log(f"⚠️ キャッシュ保存エラー: {str(e)}")
                                    logger.error(f"キャッシュ保存エラー: {e}")

                        parse_time = time.time() - start_time

                        if cache_hit:
                            add_log(
                                f"📚 ブックマーク解析完了（キャッシュ使用）: {len(bookmarks)}個のブックマークを検出 ({parse_time:.2f}秒)"
                            )
                        else:
                            add_log(
                                f"📚 ブックマーク解析完了: {len(bookmarks)}個のブックマークを検出 ({parse_time:.2f}秒)"
                            )

                        # ブックマーク統計の詳細ログ
                        if bookmarks:
                            domains = set(urlparse(b.url).netloc for b in bookmarks)
                            folders = set(
                                "/".join(b.folder_path)
                                for b in bookmarks
                                if b.folder_path
                            )
                            add_log(
                                f"📊 統計: {len(domains)}個のドメイン, {len(folders)}個のフォルダ"
                            )

                        # キャッシュ結果の表示
                        if cache_hit:
                            _display_cache_hit_results(bookmarks, cache_hit)
                        else:
                            _display_cache_miss_flow(bookmarks)

                        # セッション状態に保存
                        st.session_state["bookmarks"] = bookmarks
                        st.session_state["parser"] = parser

                        # ステップ2: ディレクトリスキャン
                        status_text.text("📂 既存ファイルをスキャン中...")
                        progress_bar.progress(0.3)

                        scan_start = time.time()
                        output_directory = st.session_state["output_directory"]
                        add_log(f"📂 ディレクトリスキャン開始: {output_directory}")

                        directory_manager = LocalDirectoryManager(output_directory)
                        add_log("🔍 ディレクトリ構造を解析中...")
                        add_log("📁 サブディレクトリを再帰的にスキャン中...")
                        add_log("📄 Markdownファイルを検索中...")

                        # 既存ディレクトリ構造をスキャン
                        existing_structure = directory_manager.scan_directory()
                        total_existing_files = sum(
                            len(files) for files in existing_structure.values()
                        )

                        scan_time = time.time() - scan_start
                        add_log(
                            f"📁 既存ファイル検出: {total_existing_files}個のMarkdownファイル ({scan_time:.2f}秒)"
                        )

                        if existing_structure:
                            add_log(f"📊 ディレクトリ数: {len(existing_structure)}個")

                        # ステップ3: 重複チェック
                        status_text.text("🔄 重複ファイルをチェック中...")
                        progress_bar.progress(0.6)

                        dup_start = time.time()
                        add_log("🔄 重複チェック開始...")
                        add_log(f"🔍 {len(bookmarks)}個のブックマークをチェック中...")

                        # 重複チェックの詳細進捗
                        batch_size = max(1, len(bookmarks) // 10)  # 10%ずつ進捗表示
                        for i in range(0, len(bookmarks), batch_size):
                            batch_end = min(i + batch_size, len(bookmarks))
                            progress_percent = (batch_end / len(bookmarks)) * 100
                            add_log(
                                f"📊 重複チェック進捗: {batch_end}/{len(bookmarks)} ({progress_percent:.0f}%)"
                            )
                            time.sleep(0.1)  # 進捗表示のための短い待機

                        duplicates = directory_manager.compare_with_bookmarks(bookmarks)

                        dup_time = time.time() - dup_start
                        add_log(
                            f"🔄 重複チェック完了: {len(duplicates['files'])}個の重複ファイルを検出 ({dup_time:.2f}秒)"
                        )

                        # ステップ4: 特殊ケース分析
                        status_text.text("🔍 特殊ケースを分析中...")
                        progress_bar.progress(0.8)

                        edge_start = time.time()
                        add_log("🔍 特殊ケース分析開始...")
                        add_log("🔍 URL形式とタイトルを検証中...")

                        # 特殊ケース分析の詳細進捗
                        batch_size = max(1, len(bookmarks) // 5)  # 20%ずつ進捗表示
                        for i in range(0, len(bookmarks), batch_size):
                            batch_end = min(i + batch_size, len(bookmarks))
                            progress_percent = (batch_end / len(bookmarks)) * 100
                            add_log(
                                f"🔍 特殊ケース分析進捗: {batch_end}/{len(bookmarks)} ({progress_percent:.0f}%)"
                            )
                            time.sleep(0.05)  # 進捗表示のための短い待機

                        edge_case_result = handle_edge_cases_and_errors(bookmarks)

                        edge_time = time.time() - edge_start
                        add_log(
                            f"🔍 特殊ケース分析完了: {edge_case_result['statistics']['valid_bookmarks']}個の有効なブックマークを検出 ({edge_time:.2f}秒)"
                        )

                        # ステップ5: 完了
                        status_text.text("✅ 解析完了")
                        progress_bar.progress(1.0)

                        total_time = time.time() - start_time
                        add_log(
                            f"✅ すべての解析が完了しました (総時間: {total_time:.2f}秒)"
                        )

                        # 最終統計
                        total_to_process = len(bookmarks) - len(duplicates["files"])
                        add_log(
                            f"📊 最終結果: {total_to_process}個が処理対象, {len(duplicates['files'])}個が重複除外"
                        )

                        # セッション状態に保存
                        st.session_state["directory_manager"] = directory_manager
                        st.session_state["existing_structure"] = existing_structure
                        st.session_state["duplicates"] = duplicates
                        st.session_state["edge_case_result"] = edge_case_result

                        # 少し待ってから進捗表示をクリア
                        time.sleep(1)
                        progress_container.empty()

                    # 解析結果の表示
                    if bookmarks:
                        stats = parser.get_statistics(bookmarks)

                        # 統計情報の表示
                        directory_manager = st.session_state["directory_manager"]
                        dir_stats = directory_manager.get_statistics()
                        duplicates = st.session_state["duplicates"]

                        logger.info("📊 統計情報:")
                        logger.info(
                            f"  📚 総ブックマーク数: {stats['total_bookmarks']}"
                        )
                        logger.info(
                            f"  🌐 ユニークドメイン数: {stats['unique_domains']}"
                        )
                        logger.info(f"  📁 フォルダ数: {stats['folder_count']}")
                        logger.info(f"  🔄 重複ファイル数: {len(duplicates['files'])}")

                        col_stat1, col_stat2, col_stat3, col_stat4 = st.columns(4)
                        with col_stat1:
                            st.metric("📚 総ブックマーク数", stats["total_bookmarks"])
                        with col_stat2:
                            st.metric("🌐 ユニークドメイン数", stats["unique_domains"])
                        with col_stat3:
                            st.metric("📁 フォルダ数", stats["folder_count"])
                        with col_stat4:
                            st.metric("🔄 重複ファイル数", len(duplicates["files"]))

                        # Task 12: 特殊ケース分析結果の表示
                        if "edge_case_result" in st.session_state:
                            display_edge_case_summary(
                                st.session_state["edge_case_result"]
                            )

                        # 重複チェック結果の表示
                        st.subheader("🔄 重複チェック結果")
                        existing_structure = st.session_state["existing_structure"]

                        if existing_structure:
                            st.info(
                                f"📂 既存ディレクトリから {dir_stats['total_files']} 個のMarkdownファイルを検出しました"
                            )

                            if duplicates["files"]:
                                st.warning(
                                    f"⚠️ {len(duplicates['files'])} 個の重複ファイルが見つかりました"
                                )

                                with st.expander("重複ファイル一覧を表示"):
                                    for duplicate_file in duplicates["files"][
                                        :20
                                    ]:  # 最初の20個を表示
                                        st.write(f"  - 🔄 {duplicate_file}")
                                    if len(duplicates["files"]) > 20:
                                        st.write(
                                            f"  ... 他 {len(duplicates['files']) - 20}個"
                                        )

                                st.info(
                                    "💡 重複ファイルは自動的に処理対象から除外されます"
                                )
                            else:
                                st.success("✅ 重複ファイルは見つかりませんでした")
                        else:
                            st.info("📂 保存先ディレクトリは空です（新規作成）")

                        # ディレクトリ構造の表示
                        st.subheader("📂 ブックマーク構造")
                        directory_structure = parser.extract_directory_structure(
                            bookmarks
                        )

                        # ツリー構造で表示
                        total_to_process, total_excluded = (
                            display_bookmark_structure_tree(
                                directory_structure, duplicates, directory_manager
                            )
                        )

                        # 処理予定の統計を表示
                        st.markdown("---")
                        col_process1, col_process2 = st.columns(2)
                        with col_process1:
                            st.metric("✅ 処理予定ファイル", total_to_process)
                        with col_process2:
                            st.metric("🔄 除外ファイル", total_excluded)

                        st.success("✅ ブックマーク解析と重複チェックが完了しました！")
                        st.info(
                            f"📊 {len(bookmarks)}個のブックマークが見つかり、{total_to_process}個が処理対象、{total_excluded}個が重複により除外されました。"
                        )

                        # Task 9: ページ一覧表示とプレビュー機能
                        if total_to_process > 0:
                            st.markdown("---")

                            # ファイル保存セクション（上部に表示）
                            display_page_list_and_preview(
                                bookmarks,
                                duplicates,
                                st.session_state["output_directory"],
                            )

                            # 2カラムレイアウトでページ一覧とプレビューを表示
                            st.markdown("---")
                            col1, col2 = st.columns([2, 1])

                            with col1:
                                st.header("📄 ブックマーク一覧")
                                display_bookmark_list_only(bookmarks, duplicates)

                            with col2:
                                st.header("🔍 プレビュー")
                                if (
                                    "preview_bookmark" in st.session_state
                                    and "preview_index" in st.session_state
                                ):
                                    show_page_preview(
                                        st.session_state["preview_bookmark"],
                                        st.session_state["preview_index"],
                                    )
                                else:
                                    st.info("📄 ページを選択してプレビューを表示")

                    else:
                        st.warning("⚠️ 有効なブックマークが見つかりませんでした。")

                except Exception as e:
                    st.error(f"❌ ブックマーク解析中にエラーが発生しました: {str(e)}")
                    st.session_state["start_analysis"] = False

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
                if "uploaded_file" in st.session_state:
                    uploaded_file = st.session_state["uploaded_file"]
                    st.info(f"📁 選択されたファイル: {uploaded_file.name}")

                if "output_directory" in st.session_state:
                    output_dir = st.session_state["output_directory"]
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
        file_validated = st.session_state.get("file_validated", False)
        dir_validated = st.session_state.get("directory_validated", False)

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
        if "bookmarks" in st.session_state and "directory_manager" in st.session_state:
            bookmarks = st.session_state["bookmarks"]
            directory_manager = st.session_state["directory_manager"]

            # 処理対象と除外対象を計算
            total_bookmarks = len(bookmarks)
            excluded_count = sum(
                1 for bookmark in bookmarks if directory_manager.is_duplicate(bookmark)
            )
            process_count = total_bookmarks - excluded_count

            st.metric("処理対象ページ", process_count)
            st.metric("除外ページ", excluded_count)
            st.metric("完了ページ", "0")  # 今後の実装で更新
        elif "bookmarks" in st.session_state:
            bookmarks = st.session_state["bookmarks"]
            st.metric("処理対象ページ", len(bookmarks))
            st.metric("除外ページ", "0")
            st.metric("完了ページ", "0")
        else:
            st.metric("処理対象ページ", "0")
            st.metric("除外ページ", "0")
            st.metric("完了ページ", "0")

    # フッター
    st.markdown("---")
    st.markdown(
        """
    <div style='text-align: center; color: #666;'>
        <small>Bookmark to Obsidian Converter v2.0 | Streamlit Application</small>
    </div>
    """,
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
