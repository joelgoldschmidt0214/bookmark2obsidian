"""
エラーハンドリングモジュール

このモジュールは、アプリケーション全体で発生するエラーの記録と管理を行います。
エラーの分類、統計、リトライ可能エラーの管理などの機能を提供します。
"""

import datetime
from typing import Dict, Any, List

# 循環参照を避けるため、文字列型ヒントを使用
import logging

# ロガーの取得
logger = logging.getLogger(__name__)


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
        """
        return {
            "total_errors": len(self.errors),
            "error_counts": self.error_counts.copy(),
            "retryable_count": sum(1 for error in self.errors if error["retryable"]),
            "recent_errors": self.errors[-10:] if self.errors else [],
        }

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


# グローバルエラーログインスタンス
error_logger = ErrorLogger()
