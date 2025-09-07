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
