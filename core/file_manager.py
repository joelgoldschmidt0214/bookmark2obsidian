"""
ファイル管理モジュール

このモジュールは、ローカルディレクトリの管理、ファイルの存在確認、
重複チェック、ファイル保存などの機能を提供します。
"""

from pathlib import Path
import os
import re
import logging
from typing import Optional, List, Dict, Any

from utils.models import Bookmark

# ロガーの取得
logger = logging.getLogger(__name__)


class LocalDirectoryManager:
    """
    ローカルディレクトリの構造を解析し、重複チェックを行うクラス

    指定されたベースディレクトリを基準として、ファイルの存在確認、
    重複チェック、ディレクトリ作成、ファイル保存などの機能を提供します。
    Markdownファイルの管理に特化した機能を持ちます。
    """

    def __init__(self, base_path: Path):
        """
        LocalDirectoryManagerを初期化

        指定されたベースパスを基準として、ディレクトリ管理機能を初期化します。
        ディレクトリの存在確認と権限チェックを自動的に実行します。

        Args:
            base_path: 基準となるディレクトリパス

        Raises:
            ValueError: 指定されたパスがディレクトリでない場合
            PermissionError: ディレクトリの読み書き権限がない場合
        """
        self.base_path = Path(base_path)
        self.existing_structure = {}
        self.duplicate_files = set()

        # ディレクトリの権限チェックと自動作成
        self._ensure_directory_exists()
        self._verify_directory_permissions()

    def scan_directory(self, path: Optional[str] = None) -> Dict[str, List[str]]:
        """
        指定されたディレクトリの既存ファイル構造を読み取る

        ディレクトリを再帰的にスキャンし、Markdownファイル（.md, .markdown）の
        構造を取得します。結果は内部キャッシュにも保存されます。

        Args:
            path: スキャン対象のパス（Noneの場合はbase_pathを使用）

        Returns:
            Dict[str, List[str]]: ディレクトリパスをキーとしたファイル名一覧

        Raises:
            RuntimeError: ディレクトリスキャンに失敗した場合
        """
        scan_path = Path(path) if path else self.base_path

        if not scan_path.exists() or not scan_path.is_dir():
            return {}

        structure = {}

        try:
            # ディレクトリを再帰的にスキャン
            for root, dirs, files in os.walk(scan_path):
                # 相対パスを計算
                relative_root = Path(root).relative_to(scan_path)
                relative_path = str(relative_root) if str(relative_root) != "." else ""

                # Markdownファイルのみを対象とする
                markdown_files = [
                    Path(f).stem
                    for f in files
                    if f.lower().endswith((".md", ".markdown"))
                ]

                if markdown_files:
                    structure[relative_path] = markdown_files

            self.existing_structure = structure
            return structure

        except Exception as e:
            raise RuntimeError(f"ディレクトリスキャンエラー: {str(e)}")

    def check_file_exists(self, path: str, filename: str) -> bool:
        """
        指定されたパスにファイルが存在するかチェック

        キャッシュされた構造情報と実際のファイルシステムの両方を確認して、
        ファイルの存在を判定します。

        Args:
            path: ディレクトリパス
            filename: ファイル名（拡張子なし）

        Returns:
            bool: ファイルが存在する場合True
        """
        try:
            # パスを正規化
            normalized_path = path.replace("\\", "/") if path else ""

            logger.debug(
                f"    ファイル存在チェック: パス='{normalized_path}', ファイル名='{filename}'"
            )
            logger.debug(f"    既存構造: {self.existing_structure}")

            # 既存構造から確認
            if normalized_path in self.existing_structure:
                exists_in_structure = (
                    filename in self.existing_structure[normalized_path]
                )
                logger.debug(f"    構造内チェック結果: {exists_in_structure}")
                if exists_in_structure:
                    return True

            # 実際のファイルシステムからも確認
            full_path = self.base_path / path if path else self.base_path
            if full_path.exists():
                md_file = full_path / f"{filename}.md"
                markdown_file = full_path / f"{filename}.markdown"
                file_exists = md_file.exists() or markdown_file.exists()
                logger.debug(
                    f"    ファイルシステムチェック: {md_file} → {md_file.exists()}"
                )
                logger.debug(
                    f"    ファイルシステムチェック: {markdown_file} → {markdown_file.exists()}"
                )
                return file_exists

            logger.debug("    結果: ファイル存在しない")
            return False

        except Exception as e:
            logger.error(f"    ファイル存在チェックエラー: {e}")
            return False

    def compare_with_bookmarks(self, bookmarks: List[Bookmark]) -> Dict[str, List[str]]:
        """
        ブックマーク階層と既存ディレクトリ構造を比較し、重複ファイルを特定

        ブックマークリストを基に生成されるファイル名と既存ファイルを比較し、
        重複するファイルを特定します。結果は内部の重複ファイルセットにも保存されます。

        Args:
            bookmarks: ブックマーク一覧

        Returns:
            Dict[str, List[str]]: 重複ファイルの情報
                - files: 重複ファイル一覧
                - paths: 重複パス一覧
        """
        duplicates = {
            "files": [],  # 重複ファイル一覧
            "paths": [],  # 重複パス一覧
        }

        self.duplicate_files.clear()

        logger.info(f"重複チェック対象: {len(bookmarks)}個のブックマーク")

        for i, bookmark in enumerate(bookmarks):
            # フォルダパスを文字列に変換
            folder_path = "/".join(bookmark.folder_path) if bookmark.folder_path else ""

            # ファイル名を生成（BookmarkParserと同じロジック）
            filename = self._sanitize_filename(bookmark.title)

            logger.debug(
                f"  {i + 1}. チェック中: '{bookmark.title}' → '{filename}' (パス: '{folder_path}')"
            )

            # 重複チェック
            file_exists = self.check_file_exists(folder_path, filename)
            logger.debug(f"     ファイル存在チェック結果: {file_exists}")

            if file_exists:
                duplicate_info = (
                    f"{folder_path}/{filename}" if folder_path else filename
                )
                duplicates["files"].append(duplicate_info)
                duplicates["paths"].append(folder_path)

                # 重複ファイルセットに追加
                self.duplicate_files.add((folder_path, filename))
                logger.info(f"  🔄 重複検出: {duplicate_info}")

        logger.info(f"重複チェック完了: {len(duplicates['files'])}個の重複を検出")
        return duplicates

    def save_markdown_file(self, path: str, content: str) -> bool:
        """
        Markdownファイルをローカルディレクトリに保存

        指定されたパスにMarkdownファイルを保存します。
        必要に応じてディレクトリを自動作成します。

        Args:
            path: 保存先パス（base_pathからの相対パス）
            content: ファイル内容

        Returns:
            bool: 保存成功の場合True

        Raises:
            RuntimeError: ファイル保存に失敗した場合
        """
        try:
            full_path = self.base_path / path

            # ディレクトリが存在しない場合は作成
            full_path.parent.mkdir(parents=True, exist_ok=True)

            # ファイルを保存
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(content)

            return True

        except Exception as e:
            raise RuntimeError(f"ファイル保存エラー: {str(e)}")

    def is_duplicate(self, bookmark: Bookmark) -> bool:
        """
        指定されたブックマークが重複ファイルかどうかを判定

        Args:
            bookmark: 判定対象のブックマーク

        Returns:
            bool: 重複ファイルの場合True
        """
        folder_path = "/".join(bookmark.folder_path) if bookmark.folder_path else ""
        filename = self._sanitize_filename(bookmark.title)

        return (folder_path, filename) in self.duplicate_files

    def get_duplicate_count(self) -> int:
        """
        重複ファイル数を取得

        Returns:
            int: 重複ファイル数
        """
        return len(self.duplicate_files)

    def get_statistics(self) -> Dict[str, int]:
        """
        ディレクトリ統計情報を取得

        現在スキャンされているディレクトリ構造の統計情報を返します。

        Returns:
            Dict[str, int]: 統計情報
                - total_files: 総ファイル数
                - total_directories: 総ディレクトリ数
                - duplicate_files: 重複ファイル数
        """
        total_files = sum(len(files) for files in self.existing_structure.values())
        total_directories = len(self.existing_structure)

        return {
            "total_files": total_files,
            "total_directories": total_directories,
            "duplicate_files": len(self.duplicate_files),
        }

    def create_directory_structure(self, folder_path: List[str]) -> Path:
        """
        指定されたフォルダ階層を自動作成

        ブックマークのフォルダ階層を基に、実際のディレクトリ構造を作成します。
        フォルダ名は自動的にサニタイズされます。

        Args:
            folder_path: 作成するフォルダ階層のリスト

        Returns:
            Path: 作成されたディレクトリパス

        Raises:
            RuntimeError: ディレクトリ作成に失敗した場合
        """
        try:
            if not folder_path:
                return self.base_path

            # パス要素をサニタイズ
            sanitized_parts = []
            for part in folder_path:
                sanitized = self._sanitize_folder_name(part)
                if sanitized:
                    sanitized_parts.append(sanitized)

            if not sanitized_parts:
                return self.base_path

            # ディレクトリパスを構築
            target_path = self.base_path
            for part in sanitized_parts:
                target_path = target_path / part

            # ディレクトリを作成
            if not target_path.exists():
                logger.info(f"📁 ディレクトリ作成: {target_path}")
                target_path.mkdir(parents=True, exist_ok=True)

            return target_path

        except Exception as e:
            logger.error(f"❌ ディレクトリ構造作成エラー: {str(e)}")
            raise

    def validate_file_save_operation(self, file_path: Path) -> Dict[str, Any]:
        """
        ファイル保存操作の事前検証

        ファイル保存前に、権限、パス長、ファイル名の妥当性などを検証します。

        Args:
            file_path: 保存予定のファイルパス

        Returns:
            Dict[str, Any]: 検証結果
                - valid: 検証結果（True/False）
                - warnings: 警告メッセージのリスト
                - errors: エラーメッセージのリスト
                - suggestions: 提案メッセージのリスト
        """
        result = {"valid": True, "warnings": [], "errors": [], "suggestions": []}

        try:
            # ディレクトリの存在確認
            directory = file_path.parent
            if not directory.exists():
                result["warnings"].append(
                    f"ディレクトリが存在しません（自動作成されます）: {directory}"
                )

            # ファイルの存在確認
            if file_path.exists():
                result["warnings"].append(
                    f"ファイルが既に存在します（上書きされます）: {file_path.name}"
                )

            # 権限確認
            if directory.exists():
                if not os.access(directory, os.W_OK):
                    result["valid"] = False
                    result["errors"].append(
                        f"ディレクトリの書き込み権限がありません: {directory}"
                    )

            # ファイル名の妥当性確認
            if len(file_path.name) > 255:
                result["valid"] = False
                result["errors"].append(
                    f"ファイル名が長すぎます（255文字以下にしてください）: {file_path.name}"
                )

            # パスの長さ確認（Windows対応）
            if len(str(file_path)) > 260:
                result["warnings"].append(
                    "パスが長すぎる可能性があります（Windows環境で問題が発生する可能性）"
                )
                result["suggestions"].append(
                    "より短いフォルダ名やファイル名を使用することを検討してください"
                )

        except Exception as e:
            result["valid"] = False
            result["errors"].append(f"検証中にエラーが発生しました: {str(e)}")

        return result

    def _ensure_directory_exists(self):
        """
        ディレクトリの存在確認と自動作成

        ベースディレクトリが存在しない場合は自動作成します。

        Raises:
            ValueError: 指定されたパスがディレクトリでない場合
        """
        try:
            if not self.base_path.exists():
                logger.info(f"📁 ベースディレクトリを作成: {self.base_path}")
                self.base_path.mkdir(parents=True, exist_ok=True)
            elif not self.base_path.is_dir():
                raise ValueError(
                    f"指定されたパスはディレクトリではありません: {self.base_path}"
                )
        except Exception as e:
            logger.error(f"❌ ディレクトリ作成エラー: {str(e)}")
            raise

    def _verify_directory_permissions(self):
        """
        ディレクトリの権限確認

        ベースディレクトリの読み書き権限を確認します。

        Raises:
            PermissionError: 読み書き権限がない場合
        """
        try:
            # 読み取り権限の確認
            if not os.access(self.base_path, os.R_OK):
                raise PermissionError(
                    f"ディレクトリの読み取り権限がありません: {self.base_path}"
                )

            # 書き込み権限の確認
            if not os.access(self.base_path, os.W_OK):
                raise PermissionError(
                    f"ディレクトリの書き込み権限がありません: {self.base_path}"
                )

            logger.debug(f"✅ ディレクトリ権限確認完了: {self.base_path}")

        except Exception as e:
            logger.error(f"❌ ディレクトリ権限エラー: {str(e)}")
            raise

    def _sanitize_filename(self, title: str) -> str:
        """
        タイトルから安全なファイル名を生成（BookmarkParserと同じロジック）

        Args:
            title: 元のタイトル

        Returns:
            str: 安全なファイル名
        """
        # 危険な文字を除去・置換（スペースは保持）
        filename = re.sub(r'[<>:"/\\|?*]', "_", title)

        # 連続するアンダースコアを単一に
        filename = re.sub(r"_+", "_", filename)

        # 前後の空白とアンダースコアを除去
        filename = filename.strip(" _")

        # 空の場合はデフォルト名を使用
        if not filename:
            filename = "untitled"

        # 長すぎる場合は切り詰め（拡張子を考慮して200文字以内）
        if len(filename) > 200:
            filename = filename[:200]

        return filename

    def _sanitize_folder_name(self, name: str) -> str:
        """
        フォルダ名をファイルシステム用にサニタイズ

        Args:
            name: 元のフォルダ名

        Returns:
            str: サニタイズされたフォルダ名
        """
        if not name:
            return ""

        # 危険な文字を除去・置換
        sanitized = re.sub(r'[<>:"/\\|?*]', "_", name)

        # 連続するアンダースコアを単一に
        sanitized = re.sub(r"_+", "_", sanitized)

        # 前後の空白とアンダースコアを除去
        sanitized = sanitized.strip(" _.")

        # 長すぎる場合は切り詰め
        if len(sanitized) > 100:
            sanitized = sanitized[:100]

        # 予約語をチェック（Windows）
        reserved_names = [
            "CON",
            "PRN",
            "AUX",
            "NUL",
            "COM1",
            "COM2",
            "COM3",
            "COM4",
            "COM5",
            "COM6",
            "COM7",
            "COM8",
            "COM9",
            "LPT1",
            "LPT2",
            "LPT3",
            "LPT4",
            "LPT5",
            "LPT6",
            "LPT7",
            "LPT8",
            "LPT9",
        ]
        if sanitized.upper() in reserved_names:
            sanitized = f"_{sanitized}"

        return sanitized
