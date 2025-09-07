"""
キャッシュ管理モジュール

このモジュールは、ブックマーク解析結果とディレクトリ構造のキャッシュ機能を提供します。
ファイルハッシュによる一意識別、ローカルストレージへの保存・読み込み、
キャッシュの有効性検証などの機能を含みます。
"""

import json
import hashlib
import os
import time
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import datetime
import logging

from utils.models import Bookmark, CacheEntry

logger = logging.getLogger(__name__)


class CacheManager:
    """
    解析結果のキャッシュを管理するクラス

    ブックマーク解析結果とディレクトリ構造をローカルストレージに保存し、
    同じファイルの再解析を避けることで処理効率を向上させます。
    """

    def __init__(self, cache_dir: Optional[Path] = None):
        """
        CacheManagerを初期化

        Args:
            cache_dir: キャッシュディレクトリのパス（Noneの場合はデフォルト値を使用）
        """
        if cache_dir is None:
            # デフォルトのキャッシュディレクトリを設定
            cache_dir = Path.home() / ".bookmark2obsidian" / "cache"

        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # キャッシュファイルのパス
        self.bookmark_cache_file = self.cache_dir / "bookmark_cache.json"
        self.directory_cache_file = self.cache_dir / "directory_cache.json"
        self.metadata_file = self.cache_dir / "cache_metadata.json"

        logger.info(f"キャッシュマネージャー初期化: {self.cache_dir}")

        # キャッシュメタデータを初期化
        self._initialize_metadata()

    def _initialize_metadata(self):
        """キャッシュメタデータファイルを初期化"""
        if not self.metadata_file.exists():
            metadata = {
                "created_at": datetime.datetime.now().isoformat(),
                "last_cleanup": datetime.datetime.now().isoformat(),
                "cache_version": "1.0",
                "total_entries": 0,
            }
            self._save_json(self.metadata_file, metadata)
            logger.info("キャッシュメタデータファイルを作成しました")

    def calculate_file_hash(self, file_content: str) -> str:
        """
        ファイル内容のハッシュ値を計算

        Args:
            file_content: ファイルの内容

        Returns:
            str: SHA256ハッシュ値
        """
        try:
            # UTF-8でエンコードしてハッシュを計算
            content_bytes = file_content.encode("utf-8")
            hash_object = hashlib.sha256(content_bytes)
            file_hash = hash_object.hexdigest()

            logger.debug(f"ファイルハッシュ計算完了: {file_hash[:16]}...")
            return file_hash

        except Exception as e:
            logger.error(f"ファイルハッシュ計算エラー: {e}")
            raise

    def calculate_directory_hash(self, directory_path: str) -> str:
        """
        ディレクトリパスとタイムスタンプからハッシュ値を計算

        Args:
            directory_path: ディレクトリのパス

        Returns:
            str: SHA256ハッシュ値
        """
        try:
            # ディレクトリパスと最終更新時刻を組み合わせてハッシュ化
            path_obj = Path(directory_path)
            if path_obj.exists():
                # ディレクトリの最終更新時刻を取得
                mtime = path_obj.stat().st_mtime
                hash_input = f"{directory_path}:{mtime}"
            else:
                # ディレクトリが存在しない場合はパスのみ
                hash_input = directory_path

            hash_object = hashlib.sha256(hash_input.encode("utf-8"))
            dir_hash = hash_object.hexdigest()

            logger.debug(f"ディレクトリハッシュ計算完了: {dir_hash[:16]}...")
            return dir_hash

        except Exception as e:
            logger.error(f"ディレクトリハッシュ計算エラー: {e}")
            raise

    def save_bookmark_cache(
        self,
        file_hash: str,
        bookmarks: List[Bookmark],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        ブックマーク解析結果をキャッシュに保存

        Args:
            file_hash: ファイルのハッシュ値
            bookmarks: ブックマークのリスト
            metadata: 追加のメタデータ

        Returns:
            bool: 保存成功の可否
        """
        try:
            # 既存のキャッシュを読み込み
            cache_data = self._load_json(self.bookmark_cache_file, {})

            # ブックマークデータをシリアライズ可能な形式に変換
            serializable_bookmarks = []
            for bookmark in bookmarks:
                bookmark_dict = {
                    "title": bookmark.title,
                    "url": bookmark.url,
                    "folder_path": bookmark.folder_path,
                    "add_date": bookmark.add_date.isoformat()
                    if bookmark.add_date
                    else None,
                    "icon": bookmark.icon,
                }
                serializable_bookmarks.append(bookmark_dict)

            # キャッシュエントリを作成
            cache_entry = {
                "file_hash": file_hash,
                "timestamp": datetime.datetime.now().isoformat(),
                "bookmarks": serializable_bookmarks,
                "metadata": metadata or {},
            }

            # キャッシュに追加
            cache_data[file_hash] = cache_entry

            # ファイルに保存
            self._save_json(self.bookmark_cache_file, cache_data)

            # メタデータを更新
            self._update_metadata("bookmark_cache_saved", len(bookmarks))

            logger.info(
                f"ブックマークキャッシュ保存完了: {len(bookmarks)}個のブックマーク (ハッシュ: {file_hash[:16]}...)"
            )
            return True

        except Exception as e:
            logger.error(f"ブックマークキャッシュ保存エラー: {e}")
            return False

    def load_bookmark_cache(self, file_hash: str) -> Optional[List[Bookmark]]:
        """
        ブックマーク解析結果をキャッシュから読み込み

        Args:
            file_hash: ファイルのハッシュ値

        Returns:
            Optional[List[Bookmark]]: キャッシュされたブックマークのリスト（存在しない場合はNone）
        """
        try:
            # キャッシュファイルを読み込み
            cache_data = self._load_json(self.bookmark_cache_file, {})

            if file_hash not in cache_data:
                logger.debug(
                    f"ブックマークキャッシュが見つかりません: {file_hash[:16]}..."
                )
                return None

            cache_entry = cache_data[file_hash]

            # キャッシュの有効性を確認
            if not self._is_cache_valid(cache_entry):
                logger.info(f"ブックマークキャッシュが無効です: {file_hash[:16]}...")
                # 無効なキャッシュを削除
                del cache_data[file_hash]
                self._save_json(self.bookmark_cache_file, cache_data)
                return None

            # ブックマークデータを復元
            bookmarks = []
            for bookmark_dict in cache_entry["bookmarks"]:
                add_date = None
                if bookmark_dict["add_date"]:
                    add_date = datetime.datetime.fromisoformat(
                        bookmark_dict["add_date"]
                    )

                bookmark = Bookmark(
                    title=bookmark_dict["title"],
                    url=bookmark_dict["url"],
                    folder_path=bookmark_dict["folder_path"],
                    add_date=add_date,
                    icon=bookmark_dict["icon"],
                )
                bookmarks.append(bookmark)

            logger.info(
                f"ブックマークキャッシュ読み込み完了: {len(bookmarks)}個のブックマーク (ハッシュ: {file_hash[:16]}...)"
            )
            return bookmarks

        except Exception as e:
            logger.error(f"ブックマークキャッシュ読み込みエラー: {e}")
            return None

    def save_directory_cache(self, path: str, structure: Dict[str, List[str]]) -> bool:
        """
        ディレクトリ構造をキャッシュに保存

        Args:
            path: ディレクトリのパス
            structure: ディレクトリ構造の辞書

        Returns:
            bool: 保存成功の可否
        """
        try:
            # ディレクトリハッシュを計算
            dir_hash = self.calculate_directory_hash(path)

            # 既存のキャッシュを読み込み
            cache_data = self._load_json(self.directory_cache_file, {})

            # キャッシュエントリを作成
            cache_entry = {
                "directory_path": path,
                "directory_hash": dir_hash,
                "timestamp": datetime.datetime.now().isoformat(),
                "structure": structure,
                "metadata": {
                    "total_directories": len(structure),
                    "total_files": sum(len(files) for files in structure.values()),
                },
            }

            # キャッシュに追加
            cache_data[dir_hash] = cache_entry

            # ファイルに保存
            self._save_json(self.directory_cache_file, cache_data)

            # メタデータを更新
            self._update_metadata("directory_cache_saved", len(structure))

            logger.info(
                f"ディレクトリキャッシュ保存完了: {len(structure)}個のディレクトリ (パス: {path})"
            )
            return True

        except Exception as e:
            logger.error(f"ディレクトリキャッシュ保存エラー: {e}")
            return False

    def load_directory_cache(self, path: str) -> Optional[Dict[str, List[str]]]:
        """
        ディレクトリ構造をキャッシュから読み込み

        Args:
            path: ディレクトリのパス

        Returns:
            Optional[Dict[str, List[str]]]: キャッシュされたディレクトリ構造（存在しない場合はNone）
        """
        try:
            # ディレクトリハッシュを計算
            dir_hash = self.calculate_directory_hash(path)

            # キャッシュファイルを読み込み
            cache_data = self._load_json(self.directory_cache_file, {})

            if dir_hash not in cache_data:
                logger.debug(f"ディレクトリキャッシュが見つかりません: {path}")
                return None

            cache_entry = cache_data[dir_hash]

            # キャッシュの有効性を確認
            if not self._is_cache_valid(cache_entry):
                logger.info(f"ディレクトリキャッシュが無効です: {path}")
                # 無効なキャッシュを削除
                del cache_data[dir_hash]
                self._save_json(self.directory_cache_file, cache_data)
                return None

            structure = cache_entry["structure"]
            logger.info(
                f"ディレクトリキャッシュ読み込み完了: {len(structure)}個のディレクトリ (パス: {path})"
            )
            return structure

        except Exception as e:
            logger.error(f"ディレクトリキャッシュ読み込みエラー: {e}")
            return None

    def clear_all_cache(self) -> bool:
        """
        すべてのキャッシュデータを削除

        Returns:
            bool: 削除成功の可否
        """
        try:
            # キャッシュファイルを削除
            cache_files = [self.bookmark_cache_file, self.directory_cache_file]

            deleted_count = 0
            for cache_file in cache_files:
                if cache_file.exists():
                    cache_file.unlink()
                    deleted_count += 1

            # メタデータをリセット
            self._initialize_metadata()

            logger.info(f"キャッシュクリア完了: {deleted_count}個のファイルを削除")
            return True

        except Exception as e:
            logger.error(f"キャッシュクリアエラー: {e}")
            return False

    def get_cache_info(self) -> Dict[str, Any]:
        """
        キャッシュの情報を取得

        Returns:
            Dict[str, Any]: キャッシュ情報の辞書
        """
        try:
            info = {
                "cache_directory": str(self.cache_dir),
                "bookmark_cache_exists": self.bookmark_cache_file.exists(),
                "directory_cache_exists": self.directory_cache_file.exists(),
                "bookmark_cache_entries": 0,
                "directory_cache_entries": 0,
                "total_cache_size_mb": 0.0,
                "last_updated": None,
            }

            # ブックマークキャッシュの情報
            if self.bookmark_cache_file.exists():
                bookmark_cache = self._load_json(self.bookmark_cache_file, {})
                info["bookmark_cache_entries"] = len(bookmark_cache)
                info["total_cache_size_mb"] += (
                    self.bookmark_cache_file.stat().st_size / 1024 / 1024
                )

                # 最新の更新日時を取得
                if bookmark_cache:
                    latest_timestamp = max(
                        entry["timestamp"] for entry in bookmark_cache.values()
                    )
                    info["last_updated"] = latest_timestamp

            # ディレクトリキャッシュの情報
            if self.directory_cache_file.exists():
                directory_cache = self._load_json(self.directory_cache_file, {})
                info["directory_cache_entries"] = len(directory_cache)
                info["total_cache_size_mb"] += (
                    self.directory_cache_file.stat().st_size / 1024 / 1024
                )

                # 最新の更新日時を更新
                if directory_cache:
                    latest_timestamp = max(
                        entry["timestamp"] for entry in directory_cache.values()
                    )
                    if (
                        not info["last_updated"]
                        or latest_timestamp > info["last_updated"]
                    ):
                        info["last_updated"] = latest_timestamp

            return info

        except Exception as e:
            logger.error(f"キャッシュ情報取得エラー: {e}")
            return {}

    def cleanup_expired_cache(self, max_age_days: int = 30) -> int:
        """
        期限切れのキャッシュエントリを削除

        Args:
            max_age_days: キャッシュの最大保持日数

        Returns:
            int: 削除されたエントリ数
        """
        try:
            deleted_count = 0
            cutoff_time = datetime.datetime.now() - datetime.timedelta(
                days=max_age_days
            )

            # ブックマークキャッシュのクリーンアップ
            if self.bookmark_cache_file.exists():
                bookmark_cache = self._load_json(self.bookmark_cache_file, {})
                original_count = len(bookmark_cache)

                # 期限切れエントリを削除
                bookmark_cache = {
                    hash_key: entry
                    for hash_key, entry in bookmark_cache.items()
                    if datetime.datetime.fromisoformat(entry["timestamp"]) > cutoff_time
                }

                deleted_count += original_count - len(bookmark_cache)
                self._save_json(self.bookmark_cache_file, bookmark_cache)

            # ディレクトリキャッシュのクリーンアップ
            if self.directory_cache_file.exists():
                directory_cache = self._load_json(self.directory_cache_file, {})
                original_count = len(directory_cache)

                # 期限切れエントリを削除
                directory_cache = {
                    hash_key: entry
                    for hash_key, entry in directory_cache.items()
                    if datetime.datetime.fromisoformat(entry["timestamp"]) > cutoff_time
                }

                deleted_count += original_count - len(directory_cache)
                self._save_json(self.directory_cache_file, directory_cache)

            # メタデータを更新
            self._update_metadata("cache_cleanup", deleted_count)

            logger.info(
                f"期限切れキャッシュクリーンアップ完了: {deleted_count}個のエントリを削除"
            )
            return deleted_count

        except Exception as e:
            logger.error(f"キャッシュクリーンアップエラー: {e}")
            return 0

    def _load_json(self, file_path: Path, default_value: Any = None) -> Any:
        """JSONファイルを読み込み"""
        try:
            if file_path.exists():
                with open(file_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            else:
                return default_value
        except Exception as e:
            logger.error(f"JSONファイル読み込みエラー ({file_path}): {e}")
            return default_value

    def _save_json(self, file_path: Path, data: Any) -> bool:
        """JSONファイルに保存"""
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            logger.error(f"JSONファイル保存エラー ({file_path}): {e}")
            return False

    def _is_cache_valid(
        self, cache_entry: Dict[str, Any], max_age_days: int = 7
    ) -> bool:
        """
        キャッシュエントリの有効性を確認

        Args:
            cache_entry: キャッシュエントリ
            max_age_days: キャッシュの最大有効日数

        Returns:
            bool: キャッシュが有効かどうか
        """
        try:
            # タイムスタンプを確認
            timestamp = datetime.datetime.fromisoformat(cache_entry["timestamp"])
            cutoff_time = datetime.datetime.now() - datetime.timedelta(
                days=max_age_days
            )

            return timestamp > cutoff_time

        except Exception as e:
            logger.error(f"キャッシュ有効性確認エラー: {e}")
            return False

    def _update_metadata(self, operation: str, count: int):
        """キャッシュメタデータを更新"""
        try:
            metadata = self._load_json(self.metadata_file, {})
            metadata["last_operation"] = operation
            metadata["last_operation_time"] = datetime.datetime.now().isoformat()
            metadata["last_operation_count"] = count

            if "operations" not in metadata:
                metadata["operations"] = []

            metadata["operations"].append(
                {
                    "operation": operation,
                    "timestamp": datetime.datetime.now().isoformat(),
                    "count": count,
                }
            )

            # 操作履歴は最新の100件のみ保持
            metadata["operations"] = metadata["operations"][-100:]

            self._save_json(self.metadata_file, metadata)

        except Exception as e:
            logger.error(f"メタデータ更新エラー: {e}")

    def get_cached_result(self, file_content: str) -> Optional[List[Bookmark]]:
        """
        ファイル内容に対するキャッシュされた解析結果を取得

        Args:
            file_content: ファイル内容

        Returns:
            Optional[List[Bookmark]]: キャッシュされたブックマークリスト
        """
        try:
            file_hash = self.calculate_file_hash(file_content)
            return self.load_bookmark_cache(file_hash)
        except Exception as e:
            logger.error(f"キャッシュ結果取得エラー: {e}")
            return None

    def save_to_cache(self, file_content: str, bookmarks: List[Bookmark]) -> bool:
        """
        解析結果をキャッシュに保存

        Args:
            file_content: ファイル内容
            bookmarks: ブックマークリスト

        Returns:
            bool: 保存成功かどうか
        """
        try:
            file_hash = self.calculate_file_hash(file_content)
            return self.save_bookmark_cache(file_hash, bookmarks)
        except Exception as e:
            logger.error(f"キャッシュ保存エラー: {e}")
            return False

    def get_cache_details(self) -> List[Dict[str, Any]]:
        """
        キャッシュの詳細情報を取得

        Returns:
            List[Dict[str, Any]]: キャッシュエントリの詳細リスト
        """
        try:
            details = []

            # ブックマークキャッシュの詳細
            bookmark_cache = self._load_json(self.bookmark_cache_file, {})

            for file_hash, entry in bookmark_cache.items():
                try:
                    timestamp = entry.get("timestamp", "Unknown")
                    bookmark_count = len(entry.get("bookmarks", []))

                    details.append(
                        {
                            "file_name": f"bookmark_{file_hash[:8]}.json",
                            "type": "bookmark",
                            "created_at": timestamp,
                            "item_count": bookmark_count,
                            "file_hash": file_hash,
                        }
                    )
                except Exception:
                    continue

            # 作成日時でソート（新しい順）
            details.sort(key=lambda x: x.get("created_at", ""), reverse=True)

            return details

        except Exception as e:
            logger.error(f"キャッシュ詳細取得エラー: {e}")
            return []

    def cleanup_old_cache(self, max_age_days: int = 7) -> int:
        """
        古いキャッシュエントリを削除

        Args:
            max_age_days: 最大保持日数

        Returns:
            int: 削除されたエントリ数
        """
        return self.cleanup_expired_cache(max_age_days)
