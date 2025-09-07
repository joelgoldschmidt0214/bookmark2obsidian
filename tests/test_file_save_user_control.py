"""
Task 11: ファイル保存機能とユーザー選択制御のテスト
"""

import pytest
import sys
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app import LocalDirectoryManager, MarkdownGenerator, Bookmark


class TestLocalDirectoryManagerEnhanced:
    """強化されたLocalDirectoryManagerのテスト"""

    @pytest.fixture
    def temp_directory(self):
        """一時ディレクトリを提供するフィクスチャ"""
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir)

    @pytest.fixture
    def sample_bookmark(self):
        """サンプルブックマークを提供するフィクスチャ"""
        return Bookmark(
            title="テスト記事",
            url="https://example.com/test",
            folder_path=["技術", "Python"],
        )

    def test_directory_manager_initialization(self, temp_directory):
        """ディレクトリマネージャーの初期化テスト"""
        manager = LocalDirectoryManager(temp_directory)

        assert manager.base_path == temp_directory
        assert temp_directory.exists()
        assert temp_directory.is_dir()

    def test_directory_manager_auto_creation(self):
        """ディレクトリの自動作成テスト"""
        with tempfile.TemporaryDirectory() as temp_dir:
            non_existent_path = Path(temp_dir) / "new_directory"

            # 存在しないディレクトリを指定
            assert not non_existent_path.exists()

            manager = LocalDirectoryManager(non_existent_path)

            # 自動作成されることを確認
            assert non_existent_path.exists()
            assert non_existent_path.is_dir()

    def test_create_directory_structure_simple(self, temp_directory):
        """シンプルなディレクトリ構造作成テスト"""
        manager = LocalDirectoryManager(temp_directory)

        folder_path = ["技術", "Python"]
        result_path = manager.create_directory_structure(folder_path)

        expected_path = temp_directory / "技術" / "Python"
        assert result_path == expected_path
        assert result_path.exists()
        assert result_path.is_dir()

    def test_create_directory_structure_empty(self, temp_directory):
        """空のフォルダパスでのディレクトリ構造作成テスト"""
        manager = LocalDirectoryManager(temp_directory)

        result_path = manager.create_directory_structure([])

        assert result_path == temp_directory

    def test_create_directory_structure_with_special_characters(self, temp_directory):
        """特殊文字を含むディレクトリ構造作成テスト"""
        manager = LocalDirectoryManager(temp_directory)

        folder_path = ["フォルダ/スラッシュ", "フォルダ:コロン", "フォルダ<>"]
        result_path = manager.create_directory_structure(folder_path)

        # 特殊文字がサニタイズされることを確認
        expected_path = (
            temp_directory / "フォルダ_スラッシュ" / "フォルダ_コロン" / "フォルダ"
        )
        assert result_path == expected_path
        assert result_path.exists()

    def test_sanitize_folder_name(self, temp_directory):
        """フォルダ名サニタイズ機能のテスト"""
        manager = LocalDirectoryManager(temp_directory)

        # 基本的なサニタイズ
        assert manager._sanitize_folder_name("normal_folder") == "normal_folder"
        assert (
            manager._sanitize_folder_name("folder/with\\slash") == "folder_with_slash"
        )
        assert manager._sanitize_folder_name("folder:with:colon") == "folder_with_colon"
        assert (
            manager._sanitize_folder_name("folder<>with<>brackets")
            == "folder_with_brackets"
        )

        # 連続するアンダースコアの処理
        assert (
            manager._sanitize_folder_name("folder___multiple___underscores")
            == "folder_multiple_underscores"
        )

        # 前後の空白とアンダースコアの除去
        assert manager._sanitize_folder_name("  _folder_  ") == "folder"

        # 長すぎる名前の切り詰め
        long_name = "a" * 150
        sanitized = manager._sanitize_folder_name(long_name)
        assert len(sanitized) <= 100

        # 予約語の処理
        assert manager._sanitize_folder_name("CON") == "_CON"
        assert manager._sanitize_folder_name("PRN") == "_PRN"

    def test_validate_file_save_operation_success(self, temp_directory):
        """ファイル保存操作の正常な検証テスト"""
        manager = LocalDirectoryManager(temp_directory)

        file_path = temp_directory / "test_file.md"
        validation = manager.validate_file_save_operation(file_path)

        assert validation["valid"] == True
        assert len(validation["errors"]) == 0

    def test_validate_file_save_operation_existing_file(self, temp_directory):
        """既存ファイルがある場合の検証テスト"""
        manager = LocalDirectoryManager(temp_directory)

        # 既存ファイルを作成
        file_path = temp_directory / "existing_file.md"
        file_path.write_text("existing content")

        validation = manager.validate_file_save_operation(file_path)

        assert validation["valid"] == True
        assert any("既に存在します" in warning for warning in validation["warnings"])

    def test_validate_file_save_operation_long_filename(self, temp_directory):
        """長すぎるファイル名の検証テスト"""
        manager = LocalDirectoryManager(temp_directory)

        # 256文字のファイル名（拡張子含む）
        long_filename = "a" * 252 + ".md"
        file_path = temp_directory / long_filename

        validation = manager.validate_file_save_operation(file_path)

        # ファイル名が255文字を超える場合はエラーになる
        if len(long_filename) > 255:
            assert validation["valid"] == False
            assert any(
                "ファイル名が長すぎます" in error for error in validation["errors"]
            )
        else:
            # 255文字以下の場合は有効
            assert validation["valid"] == True

    def test_validate_file_save_operation_long_path(self, temp_directory):
        """長すぎるパスの検証テスト"""
        manager = LocalDirectoryManager(temp_directory)

        # 非常に長いパスを作成
        long_path_parts = ["very_long_folder_name_" + "x" * 20] * 10
        long_path = temp_directory
        for part in long_path_parts:
            long_path = long_path / part
        file_path = long_path / "file.md"

        validation = manager.validate_file_save_operation(file_path)

        # パスが長すぎる場合の警告があることを確認
        if len(str(file_path)) > 260:
            assert any(
                "パスが長すぎる" in warning for warning in validation["warnings"]
            )

    def test_validate_file_save_operation_permission_error(self, temp_directory):
        """権限エラーの検証テスト"""
        manager = LocalDirectoryManager(temp_directory)

        # 読み取り専用ディレクトリを作成
        readonly_dir = temp_directory / "readonly"
        readonly_dir.mkdir()
        readonly_dir.chmod(0o444)  # 読み取り専用

        file_path = readonly_dir / "test_file.md"

        try:
            validation = manager.validate_file_save_operation(file_path)

            # 権限エラーが検出されることを確認
            # 注意: 一部のシステムでは権限チェックが異なる場合がある
            if not validation["valid"]:
                assert any(
                    "書き込み権限がありません" in error
                    for error in validation["errors"]
                )
            else:
                # 権限チェックが機能しない環境では警告を出す
                print("Warning: Permission check may not work on this system")
        finally:
            # クリーンアップ
            readonly_dir.chmod(0o755)


class TestMarkdownGeneratorEnhanced:
    """強化されたMarkdownGeneratorのテスト"""

    @pytest.fixture
    def temp_directory(self):
        """一時ディレクトリを提供するフィクスチャ"""
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir)

    @pytest.fixture
    def sample_bookmark(self):
        """サンプルブックマークを提供するフィクスチャ"""
        return Bookmark(
            title="テスト記事",
            url="https://example.com/test",
            folder_path=["技術", "Python"],
        )

    @pytest.fixture
    def markdown_generator(self):
        """MarkdownGeneratorインスタンスを提供するフィクスチャ"""
        return MarkdownGenerator()

    def test_generate_file_path_with_duplicate_avoidance(
        self, markdown_generator, sample_bookmark, temp_directory
    ):
        """重複回避機能付きファイルパス生成テスト"""
        # 既存ファイルを作成
        existing_dir = temp_directory / "技術" / "Python"
        existing_dir.mkdir(parents=True)
        existing_file = existing_dir / "テスト記事.md"
        existing_file.write_text("existing content")

        # 重複回避有効でファイルパス生成
        file_path = markdown_generator.generate_file_path(
            sample_bookmark, temp_directory, avoid_duplicates=True
        )

        # 重複回避されたファイル名になることを確認
        assert file_path.name == "テスト記事_001.md"
        assert file_path.parent == existing_dir

    def test_generate_file_path_without_duplicate_avoidance(
        self, markdown_generator, sample_bookmark, temp_directory
    ):
        """重複回避機能なしファイルパス生成テスト"""
        # 既存ファイルを作成
        existing_dir = temp_directory / "技術" / "Python"
        existing_dir.mkdir(parents=True)
        existing_file = existing_dir / "テスト記事.md"
        existing_file.write_text("existing content")

        # 重複回避無効でファイルパス生成
        file_path = markdown_generator.generate_file_path(
            sample_bookmark, temp_directory, avoid_duplicates=False
        )

        # 元のファイル名のままになることを確認
        assert file_path.name == "テスト記事.md"
        assert file_path.parent == existing_dir

    def test_generate_unique_filename_basic(self, markdown_generator, temp_directory):
        """基本的なユニークファイル名生成テスト"""
        # 既存ファイルなし
        filename = markdown_generator._generate_unique_filename(
            temp_directory, "test", ".md"
        )
        assert filename == "test.md"

    def test_generate_unique_filename_with_duplicates(
        self, markdown_generator, temp_directory
    ):
        """重複ファイルがある場合のユニークファイル名生成テスト"""
        # 既存ファイルを作成
        (temp_directory / "test.md").write_text("content")
        (temp_directory / "test_001.md").write_text("content")
        (temp_directory / "test_002.md").write_text("content")

        filename = markdown_generator._generate_unique_filename(
            temp_directory, "test", ".md"
        )
        assert filename == "test_003.md"

    def test_generate_unique_filename_fallback(
        self, markdown_generator, temp_directory
    ):
        """フォールバック機能のテスト"""
        # 1000個以上の重複ファイルをシミュレート
        with patch.object(Path, "exists", return_value=True):
            filename = markdown_generator._generate_unique_filename(
                temp_directory, "test", ".md"
            )

            # タイムスタンプが含まれることを確認
            assert "test_" in filename
            assert filename.endswith(".md")
            assert len(filename) > len("test.md")

    def test_generate_file_path_empty_title(self, markdown_generator, temp_directory):
        """空のタイトルでのファイルパス生成テスト"""
        bookmark = Bookmark(
            title="", url="https://example.com/test", folder_path=["技術"]
        )

        file_path = markdown_generator.generate_file_path(bookmark, temp_directory)

        # "untitled"がファイル名として使用されることを確認
        assert file_path.name == "untitled.md"

    def test_generate_file_path_special_characters_in_title(
        self, markdown_generator, temp_directory
    ):
        """特殊文字を含むタイトルでのファイルパス生成テスト"""
        bookmark = Bookmark(
            title="テスト/記事:特殊<文字>",
            url="https://example.com/test",
            folder_path=["技術"],
        )

        file_path = markdown_generator.generate_file_path(bookmark, temp_directory)

        # 特殊文字がサニタイズされることを確認
        assert file_path.name == "テスト_記事_特殊_文字.md"

    def test_generate_file_path_error_handling(
        self, markdown_generator, temp_directory
    ):
        """エラーハンドリングのテスト"""
        # 無効なブックマークオブジェクト
        invalid_bookmark = Mock()
        invalid_bookmark.title = None
        invalid_bookmark.folder_path = None

        # エラーが発生してもフォールバックファイルパスが返されることを確認
        file_path = markdown_generator.generate_file_path(
            invalid_bookmark, temp_directory
        )

        assert file_path.parent == temp_directory
        # Noneタイトルの場合は"untitled"になる
        assert file_path.name == "untitled.md" or file_path.name.startswith("bookmark_")
        assert file_path.name.endswith(".md")

    def test_generate_file_path_deep_hierarchy(
        self, markdown_generator, temp_directory
    ):
        """深い階層でのファイルパス生成テスト"""
        bookmark = Bookmark(
            title="深い記事",
            url="https://example.com/deep",
            folder_path=["レベル1", "レベル2", "レベル3", "レベル4", "レベル5"],
        )

        file_path = markdown_generator.generate_file_path(bookmark, temp_directory)

        expected_path = (
            temp_directory
            / "レベル1"
            / "レベル2"
            / "レベル3"
            / "レベル4"
            / "レベル5"
            / "深い記事.md"
        )
        assert file_path == expected_path

    def test_generate_file_path_no_folder_path(
        self, markdown_generator, temp_directory
    ):
        """フォルダパスなしでのファイルパス生成テスト"""
        bookmark = Bookmark(
            title="ルート記事", url="https://example.com/root", folder_path=[]
        )

        file_path = markdown_generator.generate_file_path(bookmark, temp_directory)

        assert file_path == temp_directory / "ルート記事.md"

    def test_generate_file_path_none_folder_path(
        self, markdown_generator, temp_directory
    ):
        """Noneフォルダパスでのファイルパス生成テスト"""
        bookmark = Bookmark(
            title="None記事", url="https://example.com/none", folder_path=None
        )

        file_path = markdown_generator.generate_file_path(bookmark, temp_directory)

        assert file_path == temp_directory / "None記事.md"
