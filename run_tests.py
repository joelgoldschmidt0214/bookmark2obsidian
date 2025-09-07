#!/usr/bin/env python3
"""
テスト実行スクリプト
パフォーマンステストと機能テストを実行します。
"""

import subprocess
import sys
import time
import os


def run_command(command, description):
    """コマンドを実行し、結果を表示"""
    print(f"\n{'=' * 60}")
    print(f"実行中: {description}")
    print(f"コマンド: {command}")
    print(f"{'=' * 60}")

    start_time = time.time()
    result = subprocess.run(command, shell=True, capture_output=True, text=True)
    end_time = time.time()

    print(f"実行時間: {end_time - start_time:.2f}秒")
    print(f"終了コード: {result.returncode}")

    if result.stdout:
        print("標準出力:")
        print(result.stdout)

    if result.stderr:
        print("エラー出力:")
        print(result.stderr)

    return result.returncode == 0


def main():
    """メイン実行関数"""
    print("パフォーマンス・機能テスト実行スクリプト")
    print("=" * 60)

    # テストディレクトリの存在確認
    if not os.path.exists("tests"):
        print("エラー: testsディレクトリが見つかりません")
        sys.exit(1)

    # uvの存在確認
    uv_check = subprocess.run("uv --version", shell=True, capture_output=True)
    if uv_check.returncode != 0:
        print("警告: uvがインストールされていません。pipを使用します。")
        use_uv = False
        python_cmd = "python -m pytest"
    else:
        print(f"uv検出: {uv_check.stdout.decode().strip()}")
        use_uv = True
        python_cmd = "uv run pytest"

    # 必要なパッケージのインストール確認
    print("依存関係の確認...")
    if use_uv:
        print("uvを使用して依存関係を同期します...")
        subprocess.run("uv sync", shell=True)
    else:
        packages_to_check = ["pytest", "beautifulsoup4", "streamlit", "psutil"]
        for package in packages_to_check:
            result = subprocess.run(
                f"python -c 'import {package}'", shell=True, capture_output=True
            )
            if result.returncode != 0:
                print(f"警告: {package} がインストールされていません")
                install = input(f"{package} をインストールしますか？ (y/n): ")
                if install.lower() == "y":
                    subprocess.run(f"pip install {package}", shell=True)

    # テスト実行
    tests_passed = 0
    tests_failed = 0

    # 1. パフォーマンステストの実行
    if run_command(
        f"{python_cmd} tests/test_performance.py -v", "パフォーマンステスト"
    ):
        tests_passed += 1
        print("✅ パフォーマンステスト: 成功")
    else:
        tests_failed += 1
        print("❌ パフォーマンステスト: 失敗")

    # 2. 統合パフォーマンステストの実行
    if run_command(
        f"{python_cmd} tests/test_integration_performance.py -v",
        "統合パフォーマンステスト",
    ):
        tests_passed += 1
        print("✅ 統合パフォーマンステスト: 成功")
    else:
        tests_failed += 1
        print("❌ 統合パフォーマンステスト: 失敗")

    # 3. 機能テストの実行
    if run_command(f"{python_cmd} tests/test_functionality.py -v", "機能テスト"):
        tests_passed += 1
        print("✅ 機能テスト: 成功")
    else:
        tests_failed += 1
        print("❌ 機能テスト: 失敗")

    # 4. 全テストの実行（既存のテストも含む）
    if run_command(f"{python_cmd} tests/ -v --tb=short", "全テスト"):
        tests_passed += 1
        print("✅ 全テスト: 成功")
    else:
        tests_failed += 1
        print("❌ 全テスト: 失敗")

    # 結果サマリー
    print(f"\n{'=' * 60}")
    print("テスト実行結果サマリー")
    print(f"{'=' * 60}")
    print(f"成功: {tests_passed}")
    print(f"失敗: {tests_failed}")
    print(f"合計: {tests_passed + tests_failed}")

    if tests_failed == 0:
        print("🎉 すべてのテストが成功しました！")
        sys.exit(0)
    else:
        print("⚠️  一部のテストが失敗しました。詳細を確認してください。")
        sys.exit(1)


if __name__ == "__main__":
    main()
