"""
Progress Display Module
リアルタイム進捗表示とパフォーマンス統計表示機能を提供
"""

import streamlit as st
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import threading
import logging

logger = logging.getLogger(__name__)


@dataclass
class ProgressStats:
    """進捗統計情報を管理するデータクラス"""

    total_items: int = 0
    completed_items: int = 0
    success_count: int = 0
    error_count: int = 0
    skipped_count: int = 0
    start_time: Optional[datetime] = None
    current_item: str = ""

    # パフォーマンス統計
    items_per_second: float = 0.0
    estimated_remaining_time: float = 0.0
    memory_usage_mb: float = 0.0
    cache_hit_rate: float = 0.0

    # エラー詳細
    error_details: List[Dict[str, str]] = field(default_factory=list)

    @property
    def completion_rate(self) -> float:
        """完了率を計算"""
        if self.total_items == 0:
            return 0.0
        return (self.completed_items / self.total_items) * 100

    @property
    def elapsed_time(self) -> float:
        """経過時間を秒で返す"""
        if self.start_time is None:
            return 0.0
        return (datetime.now() - self.start_time).total_seconds()

    @property
    def success_rate(self) -> float:
        """成功率を計算"""
        if self.completed_items == 0:
            return 0.0
        return (self.success_count / self.completed_items) * 100


class ProgressDisplay:
    """
    リアルタイム進捗表示とパフォーマンス統計表示を提供するクラス

    要件:
    - リアルタイム進捗更新機能
    - パフォーマンス統計表示機能
    - エラー詳細の表示
    - 推定残り時間の計算
    """

    def __init__(self, title: str = "処理進捗"):
        """
        ProgressDisplayを初期化

        Args:
            title: 進捗表示のタイトル
        """
        self.title = title
        self.stats = ProgressStats()
        self._lock = threading.Lock()
        self._ui_elements = {}
        self._is_initialized = False

    def initialize_display(self, total_items: int) -> None:
        """
        進捗表示UIを初期化

        Args:
            total_items: 処理対象の総アイテム数
        """
        with self._lock:
            self.stats.total_items = total_items
            self.stats.start_time = datetime.now()
            self._is_initialized = True

        # UIコンポーネントの作成
        st.subheader(f"📊 {self.title}")

        # メイン進捗バー
        self._ui_elements["progress_bar"] = st.progress(0)
        self._ui_elements["status_text"] = st.empty()

        # 統計情報表示エリア
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            self._ui_elements["completed_metric"] = st.metric("完了", "0")
        with col2:
            self._ui_elements["success_metric"] = st.metric("成功", "0")
        with col3:
            self._ui_elements["error_metric"] = st.metric("エラー", "0")
        with col4:
            self._ui_elements["rate_metric"] = st.metric("処理速度", "0.0 items/sec")

        # パフォーマンス統計エリア
        st.markdown("### 📈 パフォーマンス統計")

        perf_col1, perf_col2, perf_col3 = st.columns(3)

        with perf_col1:
            self._ui_elements["time_metric"] = st.metric("経過時間", "00:00:00")
        with perf_col2:
            self._ui_elements["remaining_metric"] = st.metric(
                "推定残り時間", "計算中..."
            )
        with perf_col3:
            self._ui_elements["memory_metric"] = st.metric("メモリ使用量", "0.0 MB")

        # キャッシュ統計（利用可能な場合）
        cache_col1, cache_col2 = st.columns(2)

        with cache_col1:
            self._ui_elements["cache_hit_metric"] = st.metric(
                "キャッシュヒット率", "0.0%"
            )
        with cache_col2:
            self._ui_elements["success_rate_metric"] = st.metric("成功率", "0.0%")

        # 詳細情報エリア
        self._ui_elements["details_expander"] = st.expander(
            "📋 詳細情報", expanded=False
        )

        logger.info(f"進捗表示を初期化: {total_items}アイテム")

    def update_progress(
        self,
        completed: int,
        current_item: str = "",
        success_count: Optional[int] = None,
        error_count: Optional[int] = None,
        memory_usage_mb: Optional[float] = None,
        cache_hit_rate: Optional[float] = None,
    ) -> None:
        """
        進捗情報を更新

        Args:
            completed: 完了したアイテム数
            current_item: 現在処理中のアイテム名
            success_count: 成功したアイテム数
            error_count: エラーが発生したアイテム数
            memory_usage_mb: メモリ使用量（MB）
            cache_hit_rate: キャッシュヒット率（0-100）
        """
        if not self._is_initialized:
            logger.warning("進捗表示が初期化されていません")
            return

        with self._lock:
            # 基本統計の更新
            self.stats.completed_items = completed
            self.stats.current_item = current_item

            if success_count is not None:
                self.stats.success_count = success_count
            if error_count is not None:
                self.stats.error_count = error_count
            if memory_usage_mb is not None:
                self.stats.memory_usage_mb = memory_usage_mb
            if cache_hit_rate is not None:
                self.stats.cache_hit_rate = cache_hit_rate

            # パフォーマンス統計の計算
            self._calculate_performance_stats()

        # UI更新
        self._update_ui_elements()

    def add_error(self, item_name: str, error_message: str) -> None:
        """
        エラー詳細を追加

        Args:
            item_name: エラーが発生したアイテム名
            error_message: エラーメッセージ
        """
        with self._lock:
            self.stats.error_details.append(
                {
                    "item": item_name,
                    "error": error_message,
                    "timestamp": datetime.now().strftime("%H:%M:%S"),
                }
            )
            self.stats.error_count += 1

    def _calculate_performance_stats(self) -> None:
        """パフォーマンス統計を計算"""
        elapsed = self.stats.elapsed_time

        if elapsed > 0 and self.stats.completed_items > 0:
            # 処理速度の計算
            self.stats.items_per_second = self.stats.completed_items / elapsed

            # 推定残り時間の計算
            remaining_items = self.stats.total_items - self.stats.completed_items
            if self.stats.items_per_second > 0:
                self.stats.estimated_remaining_time = (
                    remaining_items / self.stats.items_per_second
                )

    def _update_ui_elements(self) -> None:
        """UIエレメントを更新"""
        try:
            # デバッグログ
            logger.debug(
                f"UI更新: 完了={self.stats.completed_items}, 処理速度={self.stats.items_per_second:.1f}"
            )

            # 進捗バーの更新
            progress_value = self.stats.completion_rate / 100
            self._ui_elements["progress_bar"].progress(progress_value)

            # ステータステキストの更新
            status_text = f"📄 処理中: {self.stats.current_item[:50]}... ({self.stats.completed_items}/{self.stats.total_items})"
            self._ui_elements["status_text"].text(status_text)

            # メトリクスの更新（強制的に新しい値で更新）
            self._ui_elements["completed_metric"].metric(
                "完了",
                f"{self.stats.completed_items}/{self.stats.total_items}",
                delta=f"{self.stats.completion_rate:.1f}%",
            )

            self._ui_elements["success_metric"].metric(
                "成功",
                str(self.stats.success_count),
                delta=f"{self.stats.success_rate:.1f}%",
            )

            self._ui_elements["error_metric"].metric(
                "エラー", str(self.stats.error_count)
            )

            # 処理速度の表示（0の場合も明示的に表示）
            rate_text = f"{self.stats.items_per_second:.1f} items/sec"
            self._ui_elements["rate_metric"].metric("処理速度", rate_text)

            # パフォーマンス統計の更新
            elapsed_str = str(timedelta(seconds=int(self.stats.elapsed_time)))
            self._ui_elements["time_metric"].metric("経過時間", elapsed_str)

            if self.stats.estimated_remaining_time > 0:
                remaining_str = str(
                    timedelta(seconds=int(self.stats.estimated_remaining_time))
                )
                self._ui_elements["remaining_metric"].metric(
                    "推定残り時間", remaining_str
                )

            self._ui_elements["memory_metric"].metric(
                "メモリ使用量", f"{self.stats.memory_usage_mb:.1f} MB"
            )

            self._ui_elements["cache_hit_metric"].metric(
                "キャッシュヒット率", f"{self.stats.cache_hit_rate:.1f}%"
            )

            self._ui_elements["success_rate_metric"].metric(
                "成功率", f"{self.stats.success_rate:.1f}%"
            )

            # 詳細情報の更新
            self._update_details_section()

        except Exception as e:
            logger.error(f"UI更新エラー: {e}")

    def _update_details_section(self) -> None:
        """詳細情報セクションを更新"""
        with self._ui_elements["details_expander"]:
            # 処理統計
            st.markdown("#### 📊 処理統計")

            col1, col2 = st.columns(2)

            with col1:
                st.markdown(f"""
                - **総アイテム数**: {self.stats.total_items}
                - **完了数**: {self.stats.completed_items}
                - **成功数**: {self.stats.success_count}
                - **エラー数**: {self.stats.error_count}
                """)

            with col2:
                st.markdown(f"""
                - **完了率**: {self.stats.completion_rate:.1f}%
                - **成功率**: {self.stats.success_rate:.1f}%
                - **処理速度**: {self.stats.items_per_second:.1f} items/sec
                - **キャッシュヒット率**: {self.stats.cache_hit_rate:.1f}%
                """)

            # エラー詳細（エラーがある場合のみ）
            if self.stats.error_details:
                st.markdown("#### ❌ エラー詳細")

                # 最新の5件のエラーを表示
                recent_errors = self.stats.error_details[-5:]

                for error in recent_errors:
                    st.error(
                        f"**{error['timestamp']}** - {error['item']}: {error['error']}"
                    )

                if len(self.stats.error_details) > 5:
                    st.info(
                        f"他に{len(self.stats.error_details) - 5}件のエラーがあります"
                    )

    def complete_progress(self, final_message: str = "処理完了") -> None:
        """
        進捗表示を完了状態にする

        Args:
            final_message: 完了時に表示するメッセージ
        """
        with self._lock:
            self.stats.completed_items = self.stats.total_items

        # 最終UI更新
        self._ui_elements["progress_bar"].progress(1.0)
        self._ui_elements["status_text"].text(f"🎉 {final_message}")

        # 完了サマリーの表示
        st.success(f"""
        ✅ **処理完了**
        
        - 総処理数: {self.stats.total_items}
        - 成功: {self.stats.success_count}
        - エラー: {self.stats.error_count}
        - 処理時間: {str(timedelta(seconds=int(self.stats.elapsed_time)))}
        - 平均処理速度: {self.stats.items_per_second:.1f} items/sec
        """)

        logger.info(
            f"進捗表示完了: {self.stats.success_count}成功, {self.stats.error_count}エラー"
        )

    def get_stats(self) -> ProgressStats:
        """
        現在の統計情報を取得

        Returns:
            ProgressStats: 現在の進捗統計
        """
        with self._lock:
            return self.stats


# ユーティリティ関数


def create_simple_progress_display(title: str, total_items: int) -> ProgressDisplay:
    """
    シンプルな進捗表示を作成するヘルパー関数

    Args:
        title: 進捗表示のタイトル
        total_items: 処理対象の総アイテム数

    Returns:
        ProgressDisplay: 初期化済みの進捗表示オブジェクト
    """
    progress_display = ProgressDisplay(title)
    progress_display.initialize_display(total_items)
    return progress_display


def display_performance_summary(stats: ProgressStats) -> None:
    """
    パフォーマンス統計のサマリーを表示

    Args:
        stats: 表示する統計情報
    """
    st.markdown("### 📈 パフォーマンスサマリー")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            "総処理時間",
            str(timedelta(seconds=int(stats.elapsed_time))),
            help="処理開始から完了までの時間",
        )

    with col2:
        st.metric(
            "平均処理速度",
            f"{stats.items_per_second:.1f} items/sec",
            help="1秒あたりの平均処理アイテム数",
        )

    with col3:
        st.metric(
            "成功率",
            f"{stats.success_rate:.1f}%",
            help="正常に処理されたアイテムの割合",
        )

    with col4:
        st.metric(
            "キャッシュ効率",
            f"{stats.cache_hit_rate:.1f}%",
            help="キャッシュからデータを取得できた割合",
        )


# ログ表示機能


@dataclass
class LogEntry:
    """ログエントリを管理するデータクラス"""

    timestamp: datetime
    level: str
    message: str
    category: str = "general"

    def to_markdown(self) -> str:
        """ログエントリをマークダウン形式で返す"""
        time_str = self.timestamp.strftime("%H:%M:%S")

        # ログレベル別のアイコンと色
        level_icons = {
            "DEBUG": "🔍",
            "INFO": "ℹ️",
            "WARNING": "⚠️",
            "ERROR": "❌",
            "CRITICAL": "🚨",
        }

        icon = level_icons.get(self.level, "📝")
        return f"**{time_str}** {icon} {self.message}"


class ImprovedLogDisplay:
    """
    改善されたログ表示機能を提供するクラス

    要件:
    - マークダウン形式でのログ表示
    - 改行文字の正しい処理
    - ログレベル別の表示機能
    """

    def __init__(self, max_entries: int = 100):
        """
        ImprovedLogDisplayを初期化

        Args:
            max_entries: 保持する最大ログエントリ数
        """
        self.max_entries = max_entries
        self.log_entries: List[LogEntry] = []
        self._ui_elements = {}
        self._is_initialized = False

        # ログレベルフィルター
        self.level_filter = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        self.category_filter = []

    def initialize_display(self, title: str = "処理ログ") -> None:
        """
        ログ表示UIを初期化

        Args:
            title: ログ表示のタイトル
        """
        st.markdown(f"### 📝 {title}")

        # フィルターコントロール
        col1, col2 = st.columns(2)

        with col1:
            self._ui_elements["level_filter"] = st.multiselect(
                "ログレベルフィルター",
                ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
                default=["INFO", "WARNING", "ERROR", "CRITICAL"],
                key="log_level_filter",
            )

        with col2:
            self._ui_elements["auto_scroll"] = st.checkbox(
                "自動スクロール", value=True, key="log_auto_scroll"
            )

        # ログ表示エリア
        self._ui_elements["log_container"] = st.container()

        # 統計情報
        self._ui_elements["stats_container"] = st.container()

        self._is_initialized = True
        logger.info("改善されたログ表示を初期化")

    def add_log(
        self, message: str, level: str = "INFO", category: str = "general"
    ) -> None:
        """
        ログエントリを追加

        Args:
            message: ログメッセージ
            level: ログレベル (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            category: ログカテゴリ
        """
        # 改行文字の正しい処理
        processed_message = message.replace("\\n", "\n").replace("\\t", "\t")

        log_entry = LogEntry(
            timestamp=datetime.now(),
            level=level.upper(),
            message=processed_message,
            category=category,
        )

        self.log_entries.append(log_entry)

        # 最大エントリ数を超えた場合、古いエントリを削除
        if len(self.log_entries) > self.max_entries:
            self.log_entries = self.log_entries[-self.max_entries :]

        # UI更新
        if self._is_initialized:
            self._update_log_display()

    def _update_log_display(self) -> None:
        """ログ表示を更新"""
        try:
            # フィルター設定の取得
            if "level_filter" in self._ui_elements:
                selected_levels = st.session_state.get(
                    "log_level_filter", self.level_filter
                )
            else:
                selected_levels = self.level_filter

            # フィルタリング
            filtered_logs = [
                entry for entry in self.log_entries if entry.level in selected_levels
            ]

            # ログ表示
            with self._ui_elements["log_container"]:
                if filtered_logs:
                    # マークダウン形式でログを表示
                    log_markdown = "\n\n".join(
                        [
                            entry.to_markdown()
                            for entry in filtered_logs[-20:]  # 最新20件
                        ]
                    )

                    st.markdown(log_markdown)

                    # 自動スクロールが有効な場合
                    if st.session_state.get("log_auto_scroll", True):
                        # JavaScriptで最下部にスクロール
                        st.markdown(
                            """
                            <script>
                            setTimeout(function() {
                                var element = document.querySelector('[data-testid="stMarkdown"]');
                                if (element) {
                                    element.scrollTop = element.scrollHeight;
                                }
                            }, 100);
                            </script>
                            """,
                            unsafe_allow_html=True,
                        )
                else:
                    st.info("表示するログがありません")

            # 統計情報の更新
            self._update_log_statistics(filtered_logs)

        except Exception as e:
            logger.error(f"ログ表示更新エラー: {e}")

    def _update_log_statistics(self, filtered_logs: List[LogEntry]) -> None:
        """ログ統計情報を更新"""
        with self._ui_elements["stats_container"]:
            if filtered_logs:
                # レベル別統計
                level_counts = {}
                for entry in filtered_logs:
                    level_counts[entry.level] = level_counts.get(entry.level, 0) + 1

                # 統計表示
                st.markdown("#### 📊 ログ統計")

                cols = st.columns(len(level_counts))

                for i, (level, count) in enumerate(level_counts.items()):
                    with cols[i]:
                        # レベル別のアイコン
                        level_icons = {
                            "DEBUG": "🔍",
                            "INFO": "ℹ️",
                            "WARNING": "⚠️",
                            "ERROR": "❌",
                            "CRITICAL": "🚨",
                        }

                        icon = level_icons.get(level, "📝")
                        st.metric(f"{icon} {level}", count)

    def clear_logs(self) -> None:
        """ログをクリア"""
        self.log_entries.clear()
        if self._is_initialized:
            self._update_log_display()
        logger.info("ログをクリアしました")

    def export_logs(self, format: str = "markdown") -> str:
        """
        ログをエクスポート

        Args:
            format: エクスポート形式 ("markdown", "text", "json")

        Returns:
            str: エクスポートされたログ
        """
        if format == "markdown":
            return "\n\n".join([entry.to_markdown() for entry in self.log_entries])
        elif format == "text":
            return "\n".join(
                [
                    f"{entry.timestamp.strftime('%Y-%m-%d %H:%M:%S')} [{entry.level}] {entry.message}"
                    for entry in self.log_entries
                ]
            )
        elif format == "json":
            import json

            return json.dumps(
                [
                    {
                        "timestamp": entry.timestamp.isoformat(),
                        "level": entry.level,
                        "message": entry.message,
                        "category": entry.category,
                    }
                    for entry in self.log_entries
                ],
                indent=2,
                ensure_ascii=False,
            )
        else:
            raise ValueError(f"サポートされていない形式: {format}")

    def get_log_summary(self) -> Dict[str, Any]:
        """
        ログサマリーを取得

        Returns:
            Dict[str, Any]: ログサマリー情報
        """
        if not self.log_entries:
            return {"total": 0, "by_level": {}, "latest": None}

        # レベル別集計
        by_level = {}
        for entry in self.log_entries:
            by_level[entry.level] = by_level.get(entry.level, 0) + 1

        return {
            "total": len(self.log_entries),
            "by_level": by_level,
            "latest": self.log_entries[-1].timestamp if self.log_entries else None,
            "oldest": self.log_entries[0].timestamp if self.log_entries else None,
        }


def display_improved_logs(logs: List[str], title: str = "処理ログ") -> None:
    """
    改善されたログ表示関数（既存コードとの互換性のため）

    Args:
        logs: ログメッセージのリスト
        title: ログ表示のタイトル
    """
    st.markdown(f"### 📝 {title}")

    if not logs:
        st.info("表示するログがありません")
        return

    # マークダウン形式でログを表示
    log_markdown = ""

    for i, log_message in enumerate(logs):
        # 改行文字の正しい処理
        processed_message = log_message.replace("\\n", "\n").replace("\\t", "\t")

        # タイムスタンプとアイコンを追加
        timestamp = datetime.now().strftime("%H:%M:%S")

        # メッセージの内容に基づいてアイコンを選択
        if "エラー" in processed_message or "❌" in processed_message:
            icon = "❌"
        elif "警告" in processed_message or "⚠️" in processed_message:
            icon = "⚠️"
        elif "完了" in processed_message or "✅" in processed_message:
            icon = "✅"
        elif "開始" in processed_message or "🚀" in processed_message:
            icon = "🚀"
        else:
            icon = "ℹ️"

        log_markdown += f"**{timestamp}** {icon} {processed_message}\n\n"

    # スクロール可能なマークダウン表示
    st.markdown(
        f"""
        <div style="height: 300px; overflow-y: auto; padding: 10px; 
                    border: 1px solid #ddd; border-radius: 5px; 
                    background-color: #f8f9fa;">
        {log_markdown}
        </div>
        """,
        unsafe_allow_html=True,
    )


def create_improved_log_display(
    title: str = "処理ログ", max_entries: int = 100
) -> ImprovedLogDisplay:
    """
    改善されたログ表示を作成するヘルパー関数

    Args:
        title: ログ表示のタイトル
        max_entries: 保持する最大ログエントリ数

    Returns:
        ImprovedLogDisplay: 初期化済みのログ表示オブジェクト
    """
    log_display = ImprovedLogDisplay(max_entries)
    log_display.initialize_display(title)
    return log_display
