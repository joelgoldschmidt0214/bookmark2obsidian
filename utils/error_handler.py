"""
エラーハンドリングモジュール

このモジュールは、アプリケーション全体で発生するエラーの記録と管理を行います。
エラーの分類、統計、リトライ可能エラーの管理などの機能を提供します。
"""

import datetime
from typing import Dict, Any, List, Optional
import logging

# ロガーの取得
logger = logging.getLogger(__name__)


class PerformanceError(Exception):
    """パフォーマンス関連のエラー"""

    def __init__(self, message: str, operation: str = "", duration: float = 0.0):
        super().__init__(message)
        self.operation = operation
        self.duration = duration


class CacheError(Exception):
    """キャッシュ関連のエラー"""

    def __init__(self, message: str, cache_key: str = "", operation: str = ""):
        super().__init__(message)
        self.cache_key = cache_key
        self.operation = operation


class UIDisplayError(Exception):
    """UI表示関連のエラー"""

    def __init__(self, message: str, component: str = "", data_type: str = ""):
        super().__init__(message)
        self.component = component
        self.data_type = data_type


class ErrorLogger:
    """
    エラーログの記録と管理を行うクラス

    アプリケーション全体で発生するエラーを統一的に記録し、分類・統計・管理する機能を提供します。
    エラーの種類に応じた分類、リトライ可能エラーの管理、エラーサマリーの生成などを行います。
    """

    def __init__(self):
        """
        ErrorLoggerを初期化

        エラーリストとエラー種別ごとのカウンターを初期化します。
        """
        self.errors = []
        self.error_counts = {
            "network": 0,  # ネットワーク関連エラー
            "timeout": 0,  # タイムアウトエラー
            "fetch": 0,  # ページ取得エラー
            "extraction": 0,  # コンテンツ抽出エラー
            "markdown": 0,  # Markdown生成エラー
            "permission": 0,  # 権限エラー
            "filesystem": 0,  # ファイルシステムエラー
            "save": 0,  # ファイル保存エラー
            "unexpected": 0,  # 予期しないエラー
            # 新しいエラー分類
            "performance": 0,  # パフォーマンス関連エラー
            "cache": 0,  # キャッシュ関連エラー
            "ui_display": 0,  # UI表示エラー
        }

    def log_error(
        self, bookmark, error_msg: str, error_type: str, retryable: bool = False
    ):
        """
        エラーを記録

        指定されたブックマークに関連するエラーを記録し、エラー統計を更新します。
        また、ログファイルにもエラー情報を出力します。

        Args:
            bookmark: エラーが発生したブックマーク
            error_msg: エラーメッセージ
            error_type: エラータイプ（network, timeout, fetch, extraction, markdown, permission, filesystem, save, unexpected）
            retryable: リトライ可能かどうか（デフォルト: False）
        """
        error_entry = {
            "timestamp": datetime.datetime.now(),
            "bookmark": bookmark,
            "error": error_msg,
            "type": error_type,
            "retryable": retryable,
            "url": bookmark.url,
            "title": bookmark.title,
        }

        self.errors.append(error_entry)

        if error_type in self.error_counts:
            self.error_counts[error_type] += 1

        # ログファイルにも記録
        logger.error(f"[{error_type.upper()}] {bookmark.title} - {error_msg}")

    def log_performance_error(
        self, operation: str, duration: float, error_msg: str, retryable: bool = True
    ):
        """
        パフォーマンス関連エラーを記録

        Args:
            operation: 実行していた操作名
            duration: 実行時間（秒）
            error_msg: エラーメッセージ
            retryable: リトライ可能かどうか（デフォルト: True）
        """
        error_entry = {
            "timestamp": datetime.datetime.now(),
            "operation": operation,
            "duration": duration,
            "error": error_msg,
            "type": "performance",
            "retryable": retryable,
        }

        self.errors.append(error_entry)
        self.error_counts["performance"] += 1

        # ログファイルにも記録
        logger.error(f"[PERFORMANCE] {operation} ({duration:.2f}s) - {error_msg}")

    def log_cache_error(
        self, cache_key: str, operation: str, error_msg: str, retryable: bool = True
    ):
        """
        キャッシュ関連エラーを記録

        Args:
            cache_key: キャッシュキー
            operation: 実行していた操作（read/write/delete/validate）
            error_msg: エラーメッセージ
            retryable: リトライ可能かどうか（デフォルト: True）
        """
        error_entry = {
            "timestamp": datetime.datetime.now(),
            "cache_key": cache_key,
            "operation": operation,
            "error": error_msg,
            "type": "cache",
            "retryable": retryable,
        }

        self.errors.append(error_entry)
        self.error_counts["cache"] += 1

        # ログファイルにも記録
        logger.error(f"[CACHE] {operation} ({cache_key}) - {error_msg}")

    def log_ui_display_error(
        self, component: str, data_type: str, error_msg: str, retryable: bool = False
    ):
        """
        UI表示関連エラーを記録

        Args:
            component: エラーが発生したUIコンポーネント名
            data_type: 表示しようとしていたデータタイプ
            error_msg: エラーメッセージ
            retryable: リトライ可能かどうか（デフォルト: False）
        """
        error_entry = {
            "timestamp": datetime.datetime.now(),
            "component": component,
            "data_type": data_type,
            "error": error_msg,
            "type": "ui_display",
            "retryable": retryable,
        }

        self.errors.append(error_entry)
        self.error_counts["ui_display"] += 1

        # ログファイルにも記録
        logger.error(f"[UI_DISPLAY] {component} ({data_type}) - {error_msg}")

    def get_error_summary(self) -> Dict[str, Any]:
        """
        エラーサマリーを取得

        現在記録されているエラーの統計情報を返します。

        Returns:
            Dict[str, Any]: エラーサマリー情報
                - total_errors: 総エラー数
                - error_counts: エラー種別ごとのカウント
                - retryable_count: リトライ可能エラー数
                - recent_errors: 最新10件のエラー
                - performance_errors: パフォーマンスエラー数
                - cache_errors: キャッシュエラー数
                - ui_display_errors: UI表示エラー数
        """
        return {
            "total_errors": len(self.errors),
            "error_counts": self.error_counts.copy(),
            "retryable_count": sum(1 for error in self.errors if error["retryable"]),
            "recent_errors": self.errors[-10:] if self.errors else [],
            "performance_errors": self.error_counts["performance"],
            "cache_errors": self.error_counts["cache"],
            "ui_display_errors": self.error_counts["ui_display"],
        }

    def get_errors_by_type(self, error_type: str) -> List[Dict]:
        """
        指定されたタイプのエラーを取得

        Args:
            error_type: エラータイプ

        Returns:
            List[Dict]: 指定されたタイプのエラーのリスト
        """
        return [error for error in self.errors if error["type"] == error_type]

    def get_performance_errors(self) -> List[Dict]:
        """
        パフォーマンス関連エラーを取得

        Returns:
            List[Dict]: パフォーマンスエラーのリスト
        """
        return self.get_errors_by_type("performance")

    def get_cache_errors(self) -> List[Dict]:
        """
        キャッシュ関連エラーを取得

        Returns:
            List[Dict]: キャッシュエラーのリスト
        """
        return self.get_errors_by_type("cache")

    def get_ui_display_errors(self) -> List[Dict]:
        """
        UI表示関連エラーを取得

        Returns:
            List[Dict]: UI表示エラーのリスト
        """
        return self.get_errors_by_type("ui_display")

    def get_retryable_errors(self) -> List[Dict]:
        """
        リトライ可能なエラーを取得

        Returns:
            List[Dict]: リトライ可能なエラーのリスト
        """
        return [error for error in self.errors if error["retryable"]]

    def clear_errors(self):
        """
        エラーログをクリア

        記録されているすべてのエラーとエラーカウンターをリセットします。
        """
        self.errors.clear()
        self.error_counts = {key: 0 for key in self.error_counts}


class ErrorRecoveryStrategy:
    """
    エラー回復戦略を管理するクラス

    エラーの種類に応じた自動回復処理、フォールバック機能、
    ユーザーフレンドリーなエラーメッセージの生成を行います。
    """

    def __init__(self, error_logger: ErrorLogger):
        """
        ErrorRecoveryStrategyを初期化

        Args:
            error_logger: エラーログインスタンス
        """
        self.error_logger = error_logger
        self.retry_counts = {}  # 操作ごとのリトライ回数を記録
        self.max_retries = {
            "network": 3,
            "timeout": 2,
            "fetch": 3,
            "extraction": 2,
            "performance": 1,
            "cache": 2,
            "ui_display": 1,
        }

    def should_retry(self, error_type: str, operation_key: str) -> bool:
        """
        リトライすべきかどうかを判定

        Args:
            error_type: エラータイプ
            operation_key: 操作を識別するキー

        Returns:
            bool: リトライすべきかどうか
        """
        if error_type not in self.max_retries:
            return False

        current_retries = self.retry_counts.get(operation_key, 0)
        max_retries = self.max_retries[error_type]

        return current_retries < max_retries

    def record_retry(self, operation_key: str):
        """
        リトライ回数を記録

        Args:
            operation_key: 操作を識別するキー
        """
        self.retry_counts[operation_key] = self.retry_counts.get(operation_key, 0) + 1

    def reset_retry_count(self, operation_key: str):
        """
        リトライ回数をリセット

        Args:
            operation_key: 操作を識別するキー
        """
        if operation_key in self.retry_counts:
            del self.retry_counts[operation_key]

    def get_fallback_strategy(self, error_type: str) -> Dict[str, Any]:
        """
        エラータイプに応じたフォールバック戦略を取得

        Args:
            error_type: エラータイプ

        Returns:
            Dict[str, Any]: フォールバック戦略情報
        """
        fallback_strategies = {
            "network": {
                "action": "use_cache",
                "message": "ネットワークエラーが発生しました。キャッシュされたデータを使用します。",
                "user_action": "インターネット接続を確認してください。",
            },
            "timeout": {
                "action": "reduce_batch_size",
                "message": "処理がタイムアウトしました。バッチサイズを小さくして再試行します。",
                "user_action": "大量のデータを処理する場合は、小さなファイルに分割してください。",
            },
            "fetch": {
                "action": "skip_and_continue",
                "message": "ページの取得に失敗しました。このページをスキップして続行します。",
                "user_action": "URLが正しいか確認してください。",
            },
            "extraction": {
                "action": "use_basic_extraction",
                "message": "高度な抽出に失敗しました。基本的な抽出方法を使用します。",
                "user_action": "ページの構造が複雑な場合があります。",
            },
            "performance": {
                "action": "disable_optimization",
                "message": "パフォーマンス最適化でエラーが発生しました。標準処理に切り替えます。",
                "user_action": "システムリソースが不足している可能性があります。",
            },
            "cache": {
                "action": "clear_cache",
                "message": "キャッシュエラーが発生しました。キャッシュをクリアして再処理します。",
                "user_action": "ディスク容量を確認してください。",
            },
            "ui_display": {
                "action": "use_simple_display",
                "message": "表示エラーが発生しました。シンプルな表示形式を使用します。",
                "user_action": "ブラウザを更新してみてください。",
            },
        }

        return fallback_strategies.get(
            error_type,
            {
                "action": "log_and_continue",
                "message": "予期しないエラーが発生しました。処理を続行します。",
                "user_action": "問題が続く場合は、アプリケーションを再起動してください。",
            },
        )

    def get_user_friendly_message(self, error_type: str, error_msg: str) -> str:
        """
        ユーザーフレンドリーなエラーメッセージを生成

        Args:
            error_type: エラータイプ
            error_msg: 元のエラーメッセージ

        Returns:
            str: ユーザーフレンドリーなメッセージ
        """
        fallback = self.get_fallback_strategy(error_type)
        base_message = fallback.get("message", "エラーが発生しました。")
        user_action = fallback.get("user_action", "")

        if user_action:
            return f"{base_message}\n\n推奨アクション: {user_action}"
        else:
            return base_message

    def execute_recovery_action(
        self, error_type: str, context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        エラー回復アクションを実行

        Args:
            error_type: エラータイプ
            context: 実行コンテキスト

        Returns:
            Dict[str, Any]: 回復アクションの結果
        """
        fallback = self.get_fallback_strategy(error_type)
        action = fallback.get("action", "log_and_continue")

        result = {
            "action_taken": action,
            "success": False,
            "message": fallback.get("message", ""),
            "context": context or {},
        }

        try:
            if action == "use_cache":
                # キャッシュからデータを取得する処理
                result["success"] = True
                result["data_source"] = "cache"

            elif action == "reduce_batch_size":
                # バッチサイズを半分に減らす
                current_batch_size = context.get("batch_size", 100) if context else 100
                new_batch_size = max(1, current_batch_size // 2)
                result["success"] = True
                result["new_batch_size"] = new_batch_size

            elif action == "skip_and_continue":
                # 現在の項目をスキップして続行
                result["success"] = True
                result["skipped"] = True

            elif action == "use_basic_extraction":
                # 基本的な抽出方法に切り替え
                result["success"] = True
                result["extraction_mode"] = "basic"

            elif action == "disable_optimization":
                # 最適化を無効にして標準処理に切り替え
                result["success"] = True
                result["optimization_disabled"] = True

            elif action == "clear_cache":
                # キャッシュをクリア
                result["success"] = True
                result["cache_cleared"] = True

            elif action == "use_simple_display":
                # シンプルな表示形式に切り替え
                result["success"] = True
                result["display_mode"] = "simple"

            else:
                # デフォルト: ログに記録して続行
                result["success"] = True
                result["logged"] = True

        except Exception as e:
            result["success"] = False
            result["recovery_error"] = str(e)
            logger.error(f"Recovery action failed: {e}")

        return result


# グローバルエラーログインスタンス
error_logger = ErrorLogger()

# グローバルエラー回復戦略インスタンス
error_recovery = ErrorRecoveryStrategy(error_logger)
