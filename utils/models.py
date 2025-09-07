"""
データモデル定義モジュール

このモジュールは、アプリケーション全体で使用されるデータ構造を定義します。
ブックマーク情報、ページ情報、処理状態などの基本的なデータクラスを提供します。
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
import datetime


class PageStatus(Enum):
    """
    ページ処理状態を表す列挙型

    ブックマークから生成されるページの処理状況を管理するために使用されます。
    """

    PENDING = "pending"  # 処理待ち
    FETCHING = "fetching"  # 取得中
    SUCCESS = "success"  # 成功
    EXCLUDED = "excluded"  # 除外
    ERROR = "error"  # エラー


@dataclass
class Bookmark:
    """
    ブックマーク情報を格納するデータクラス

    ブラウザのブックマークファイルから抽出された個々のブックマーク情報を保持します。

    Attributes:
        title: ブックマークのタイトル
        url: ブックマークのURL
        folder_path: フォルダ階層のリスト（ルートから順番）
        add_date: ブックマーク追加日時（オプション）
        icon: ブックマークのアイコン情報（オプション）
    """

    title: str
    url: str
    folder_path: List[str]
    add_date: Optional[datetime.datetime] = None
    icon: Optional[str] = None


@dataclass
class Page:
    """
    処理対象ページの情報を格納するデータクラス

    ブックマークから生成され、コンテンツ取得や変換処理の対象となるページ情報を管理します。

    Attributes:
        bookmark: 関連するブックマーク情報
        content: 取得したWebページのコンテンツ（オプション）
        tags: ページに付与されるタグのリスト
        metadata: ページのメタデータ情報
        is_selected: ユーザーによる選択状態
        status: 現在の処理状態
    """

    bookmark: Bookmark
    content: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    is_selected: bool = True
    status: PageStatus = PageStatus.PENDING


@dataclass
class CacheEntry:
    """
    キャッシュエントリを格納するデータクラス

    解析結果やディレクトリ構造などのキャッシュデータを管理します。

    Attributes:
        file_hash: ファイルのハッシュ値（一意識別子）
        timestamp: キャッシュ作成時刻
        data: キャッシュされたデータ
        metadata: キャッシュのメタデータ情報
    """

    file_hash: str
    timestamp: datetime.datetime
    data: Any
    metadata: Dict[str, Any] = field(default_factory=dict)

    def is_valid(self, max_age_days: int = 7) -> bool:
        """
        キャッシュエントリの有効性を確認

        Args:
            max_age_days: キャッシュの最大有効日数

        Returns:
            bool: キャッシュが有効かどうか
        """
        cutoff_time = datetime.datetime.now() - datetime.timedelta(days=max_age_days)
        return self.timestamp > cutoff_time

    def age_in_hours(self) -> float:
        """
        キャッシュエントリの経過時間を時間単位で取得

        Returns:
            float: 経過時間（時間）
        """
        delta = datetime.datetime.now() - self.timestamp
        return delta.total_seconds() / 3600


@dataclass
class CacheMetadata:
    """
    キャッシュシステム全体のメタデータを格納するデータクラス

    Attributes:
        created_at: キャッシュシステム作成時刻
        last_cleanup: 最後のクリーンアップ実行時刻
        cache_version: キャッシュシステムのバージョン
        total_entries: 総エントリ数
        total_size_mb: 総サイズ（MB）
        hit_count: キャッシュヒット数
        miss_count: キャッシュミス数
    """

    created_at: datetime.datetime
    last_cleanup: datetime.datetime
    cache_version: str
    total_entries: int = 0
    total_size_mb: float = 0.0
    hit_count: int = 0
    miss_count: int = 0

    def hit_rate(self) -> float:
        """
        キャッシュヒット率を計算

        Returns:
            float: ヒット率（0.0-1.0）
        """
        total_requests = self.hit_count + self.miss_count
        if total_requests == 0:
            return 0.0
        return self.hit_count / total_requests


@dataclass
class CacheStatistics:
    """
    キャッシュ統計情報を格納するデータクラス

    Attributes:
        bookmark_cache_entries: ブックマークキャッシュエントリ数
        directory_cache_entries: ディレクトリキャッシュエントリ数
        total_size_mb: 総サイズ（MB）
        oldest_entry: 最古のエントリの作成時刻
        newest_entry: 最新のエントリの作成時刻
        expired_entries: 期限切れエントリ数
    """

    bookmark_cache_entries: int = 0
    directory_cache_entries: int = 0
    total_size_mb: float = 0.0
    oldest_entry: Optional[datetime.datetime] = None
    newest_entry: Optional[datetime.datetime] = None
    expired_entries: int = 0

    def total_entries(self) -> int:
        """総エントリ数を取得"""
        return self.bookmark_cache_entries + self.directory_cache_entries
