"""
キャッシュユーティリティモジュール

このモジュールは、キャッシュ機能の補助的な機能を提供します。
キャッシュ統計の計算、有効性検証、データ変換などの機能を含みます。
"""

import datetime
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
import logging

from .models import CacheEntry, CacheMetadata, CacheStatistics, Bookmark

logger = logging.getLogger(__name__)


class CacheValidator:
    """
    キャッシュの有効性を検証するクラス
    """

    @staticmethod
    def validate_bookmark_cache(cache_entry: Dict[str, Any]) -> bool:
        """
        ブックマークキャッシュエントリの有効性を検証

        Args:
            cache_entry: キャッシュエントリの辞書

        Returns:
            bool: 有効かどうか
        """
        try:
            # 必須フィールドの確認
            required_fields = ["file_hash", "timestamp", "bookmarks"]
            for field in required_fields:
                if field not in cache_entry:
                    logger.warning(f"必須フィールドが不足: {field}")
                    return False

            # タイムスタンプの形式確認
            try:
                datetime.datetime.fromisoformat(cache_entry["timestamp"])
            except ValueError:
                logger.warning("無効なタイムスタンプ形式")
                return False

            # ブックマークデータの確認
            bookmarks = cache_entry["bookmarks"]
            if not isinstance(bookmarks, list):
                logger.warning("ブックマークデータがリスト形式ではありません")
                return False

            # 各ブックマークの必須フィールド確認
            for i, bookmark in enumerate(bookmarks):
                if not isinstance(bookmark, dict):
                    logger.warning(f"ブックマーク {i} が辞書形式ではありません")
                    return False

                bookmark_required = ["title", "url", "folder_path"]
                for field in bookmark_required:
                    if field not in bookmark:
                        logger.warning(
                            f"ブックマーク {i} に必須フィールドが不足: {field}"
                        )
                        return False

            return True

        except Exception as e:
            logger.error(f"ブックマークキャッシュ検証エラー: {e}")
            return False

    @staticmethod
    def validate_directory_cache(cache_entry: Dict[str, Any]) -> bool:
        """
        ディレクトリキャッシュエントリの有効性を検証

        Args:
            cache_entry: キャッシュエントリの辞書

        Returns:
            bool: 有効かどうか
        """
        try:
            # 必須フィールドの確認
            required_fields = [
                "directory_path",
                "directory_hash",
                "timestamp",
                "structure",
            ]
            for field in required_fields:
                if field not in cache_entry:
                    logger.warning(f"必須フィールドが不足: {field}")
                    return False

            # タイムスタンプの形式確認
            try:
                datetime.datetime.fromisoformat(cache_entry["timestamp"])
            except ValueError:
                logger.warning("無効なタイムスタンプ形式")
                return False

            # ディレクトリ構造の確認
            structure = cache_entry["structure"]
            if not isinstance(structure, dict):
                logger.warning("ディレクトリ構造が辞書形式ではありません")
                return False

            # 各ディレクトリエントリの確認
            for dir_path, files in structure.items():
                if not isinstance(dir_path, str):
                    logger.warning(
                        f"ディレクトリパスが文字列ではありません: {dir_path}"
                    )
                    return False

                if not isinstance(files, list):
                    logger.warning(
                        f"ファイルリストがリスト形式ではありません: {dir_path}"
                    )
                    return False

                for file_name in files:
                    if not isinstance(file_name, str):
                        logger.warning(f"ファイル名が文字列ではありません: {file_name}")
                        return False

            return True

        except Exception as e:
            logger.error(f"ディレクトリキャッシュ検証エラー: {e}")
            return False

    @staticmethod
    def validate_file_integrity(file_path: Path) -> bool:
        """
        キャッシュファイルの整合性を検証

        Args:
            file_path: キャッシュファイルのパス

        Returns:
            bool: 整合性が保たれているかどうか
        """
        try:
            if not file_path.exists():
                return False

            # ファイルサイズの確認
            file_size = file_path.stat().st_size
            if file_size == 0:
                logger.warning(f"キャッシュファイルが空です: {file_path}")
                return False

            # 最大サイズの確認（100MB制限）
            max_size = 100 * 1024 * 1024  # 100MB
            if file_size > max_size:
                logger.warning(
                    f"キャッシュファイルが大きすぎます: {file_path} ({file_size / 1024 / 1024:.1f}MB)"
                )
                return False

            return True

        except Exception as e:
            logger.error(f"ファイル整合性検証エラー: {e}")
            return False


class CacheStatisticsCalculator:
    """
    キャッシュ統計を計算するクラス
    """

    @staticmethod
    def calculate_cache_statistics(
        bookmark_cache: Dict[str, Any],
        directory_cache: Dict[str, Any],
        cache_files: List[Path],
    ) -> CacheStatistics:
        """
        キャッシュ統計を計算

        Args:
            bookmark_cache: ブックマークキャッシュデータ
            directory_cache: ディレクトリキャッシュデータ
            cache_files: キャッシュファイルのリスト

        Returns:
            CacheStatistics: 計算された統計情報
        """
        try:
            stats = CacheStatistics()

            # エントリ数の計算
            stats.bookmark_cache_entries = len(bookmark_cache)
            stats.directory_cache_entries = len(directory_cache)

            # ファイルサイズの計算
            total_size = 0
            for file_path in cache_files:
                if file_path.exists():
                    total_size += file_path.stat().st_size
            stats.total_size_mb = total_size / 1024 / 1024

            # 最古・最新エントリの計算
            all_timestamps = []

            # ブックマークキャッシュのタイムスタンプ
            for entry in bookmark_cache.values():
                try:
                    timestamp = datetime.datetime.fromisoformat(entry["timestamp"])
                    all_timestamps.append(timestamp)
                except (KeyError, ValueError):
                    continue

            # ディレクトリキャッシュのタイムスタンプ
            for entry in directory_cache.values():
                try:
                    timestamp = datetime.datetime.fromisoformat(entry["timestamp"])
                    all_timestamps.append(timestamp)
                except (KeyError, ValueError):
                    continue

            if all_timestamps:
                stats.oldest_entry = min(all_timestamps)
                stats.newest_entry = max(all_timestamps)

            # 期限切れエントリの計算
            cutoff_time = datetime.datetime.now() - datetime.timedelta(days=7)
            expired_count = 0

            for timestamp in all_timestamps:
                if timestamp < cutoff_time:
                    expired_count += 1

            stats.expired_entries = expired_count

            return stats

        except Exception as e:
            logger.error(f"キャッシュ統計計算エラー: {e}")
            return CacheStatistics()

    @staticmethod
    def calculate_cache_efficiency(
        hit_count: int, miss_count: int, total_processing_time_saved: float
    ) -> Dict[str, float]:
        """
        キャッシュ効率を計算

        Args:
            hit_count: キャッシュヒット数
            miss_count: キャッシュミス数
            total_processing_time_saved: 節約された総処理時間（秒）

        Returns:
            Dict[str, float]: 効率指標の辞書
        """
        try:
            total_requests = hit_count + miss_count

            efficiency = {
                "hit_rate": hit_count / total_requests if total_requests > 0 else 0.0,
                "miss_rate": miss_count / total_requests if total_requests > 0 else 0.0,
                "time_saved_hours": total_processing_time_saved / 3600,
                "average_time_saved_per_hit": total_processing_time_saved / hit_count
                if hit_count > 0
                else 0.0,
            }

            return efficiency

        except Exception as e:
            logger.error(f"キャッシュ効率計算エラー: {e}")
            return {}


class CacheDataConverter:
    """
    キャッシュデータの変換を行うクラス
    """

    @staticmethod
    def bookmarks_to_cache_format(bookmarks: List[Bookmark]) -> List[Dict[str, Any]]:
        """
        ブックマークオブジェクトをキャッシュ形式に変換

        Args:
            bookmarks: ブックマークオブジェクトのリスト

        Returns:
            List[Dict[str, Any]]: キャッシュ形式のブックマークデータ
        """
        try:
            cache_bookmarks = []

            for bookmark in bookmarks:
                cache_bookmark = {
                    "title": bookmark.title,
                    "url": bookmark.url,
                    "folder_path": bookmark.folder_path,
                    "add_date": bookmark.add_date.isoformat()
                    if bookmark.add_date
                    else None,
                    "icon": bookmark.icon,
                }
                cache_bookmarks.append(cache_bookmark)

            return cache_bookmarks

        except Exception as e:
            logger.error(f"ブックマーク変換エラー: {e}")
            return []

    @staticmethod
    def cache_format_to_bookmarks(
        cache_bookmarks: List[Dict[str, Any]],
    ) -> List[Bookmark]:
        """
        キャッシュ形式からブックマークオブジェクトに変換

        Args:
            cache_bookmarks: キャッシュ形式のブックマークデータ

        Returns:
            List[Bookmark]: ブックマークオブジェクトのリスト
        """
        try:
            bookmarks = []

            for cache_bookmark in cache_bookmarks:
                add_date = None
                if cache_bookmark.get("add_date"):
                    try:
                        add_date = datetime.datetime.fromisoformat(
                            cache_bookmark["add_date"]
                        )
                    except ValueError:
                        logger.warning(
                            f"無効な日付形式: {cache_bookmark.get('add_date')}"
                        )

                bookmark = Bookmark(
                    title=cache_bookmark["title"],
                    url=cache_bookmark["url"],
                    folder_path=cache_bookmark["folder_path"],
                    add_date=add_date,
                    icon=cache_bookmark.get("icon"),
                )
                bookmarks.append(bookmark)

            return bookmarks

        except Exception as e:
            logger.error(f"キャッシュ形式変換エラー: {e}")
            return []

    @staticmethod
    def create_cache_entry(
        file_hash: str, data: Any, metadata: Optional[Dict[str, Any]] = None
    ) -> CacheEntry:
        """
        キャッシュエントリを作成

        Args:
            file_hash: ファイルハッシュ
            data: キャッシュするデータ
            metadata: メタデータ

        Returns:
            CacheEntry: 作成されたキャッシュエントリ
        """
        return CacheEntry(
            file_hash=file_hash,
            timestamp=datetime.datetime.now(),
            data=data,
            metadata=metadata or {},
        )
