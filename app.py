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

                        parser = BookmarkParser()
                        add_log("🔍 HTMLパーサーを初期化...")

                        # ブックマーク解析の詳細ログ
                        add_log("📄 HTMLコンテンツを解析中...")
                        add_log("🔍 HTMLパーサーでDOMツリーを構築中...")
                        add_log("📂 フォルダ構造を解析中...")
                        add_log("🔗 ブックマークリンクを抽出中...")

                        bookmarks = parser.parse_bookmarks(content)

                        parse_time = time.time() - start_time
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
