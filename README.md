# bookmark2obsidian

Retrieve all linked pages from the &lt;a> tags in Chrome bookmarks, preserving the folder structure, and generate a set of Obsidian pages accordingly.

## 🚀 新機能 (v0.2.0)

### パフォーマンス最適化
- **高速キャッシュシステム**: 解析済みブックマークをキャッシュして再処理を高速化
- **並列処理**: 大量のブックマークを効率的に並列処理
- **バッチ処理**: メモリ効率を向上させるバッチ処理機能
- **メモリ監視**: リアルタイムメモリ使用量監視

### UI/UX改善
- **リアルタイム進捗表示**: 処理進捗をリアルタイムで表示
- **改善されたログ表示**: マークダウン形式での見やすいログ表示
- **エラー回復機能**: 自動エラー回復とユーザーフレンドリーなエラーメッセージ
- **キャッシュ管理UI**: キャッシュ状況の表示と管理機能

### 対応ブラウザ拡張
- **Chrome**: 完全対応（従来通り）
- **Firefox**: Firefox形式のブックマークエクスポートに対応
- **混合形式**: 複数ブラウザの混合ブックマークファイルに対応

## 開発環境のセットアップ

このプロジェクトは **uv** を使用してPython仮想環境を管理しています。

### 初回セットアップ

```bash
# 依存関係のインストール（仮想環境も自動作成）
uv sync
```

### 日常的な開発作業

**重要**: このプロジェクトではuv仮想環境を使用するため、Pythonスクリプトの実行には `uv run` を使用してください。

```bash
# アプリケーションの起動
uv run streamlit run app.py

# Pythonスクリプトの実行
uv run python debug_bookmark_analysis.py

# その他のスクリプト実行例
uv run python tests/test_file_validation.py
```

### 仮想環境のアクティベート（オプション）

その日の最初の作業時に一度だけ仮想環境をアクティベートすることもできます：

```bash
# 仮想環境をアクティベート（一日一回）
source .venv/bin/activate  # Linux/macOS
# または
.venv\Scripts\activate     # Windows

# アクティベート後は通常のpythonコマンドが使用可能
python app.py
streamlit run app.py
```

ただし、`uv run` を使用する方が確実で推奨されます。

## テスト

### 自動テスト実行

新しいテストスイートが利用可能です：

```bash
# 全テストを実行（推奨）
uv run python run_tests.py

# 個別テストの実行
uv run pytest tests/test_functionality.py -v          # 機能テスト
uv run pytest tests/test_integration_performance.py -v # パフォーマンステスト
```

### 手動テスト

```bash
# ファイルアップロードとディレクトリ選択機能のテスト
uv run python tests/test_file_validation.py
```

### テスト用ブックマークファイルの作成

個人データを含むため、test_bookmarks.htmlファイルはリポジトリに含まれていません。
テスト用のブックマークファイルを作成するには、Chromeから「ブックマーク」→「ブックマークマネージャー」→「整理」→「ブックマークをHTMLファイルにエクスポート」でbookmarks.htmlファイルを作成し、test_bookmarks.htmlとしてプロジェクトルートに配置してください。

### パフォーマンステスト

```bash
# パフォーマンステストのみ実行
uv run pytest tests/test_integration_performance.py -v

# 大量データでのテスト（時間がかかります）
uv run pytest tests/test_integration_performance.py::TestRealWorldScenarios::test_chrome_bookmark_export_performance -v
```

## 🔧 設定とカスタマイズ

### キャッシュ設定

キャッシュは `~/.bookmark2obsidian/cache/` に保存されます。

```bash
# キャッシュクリア（アプリ内のボタンまたは手動）
rm -rf ~/.bookmark2obsidian/cache/
```

### パフォーマンス設定

アプリケーション内で以下の設定が可能です：
- バッチサイズ（デフォルト: 100）
- 並列処理ワーカー数（デフォルト: 4）
- キャッシュ有効期限（デフォルト: 7日）
