# bookmark2obsidian

Retrieve all linked pages from the &lt;a> tags in Chrome bookmarks, preserving the folder structure, and generate a set of Obsidian pages accordingly.

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

### 手動テスト
```bash
# ファイルアップロードとディレクトリ選択機能のテスト
uv run python tests/test_file_validation.py
```

### テスト用ブックマークファイルの作成
個人データを含むため、test_bookmarks.htmlファイルはリポジトリに含まれていません。
テスト用のブックマークファイルを作成するには、Chromeから「ブックマーク」→「ブックマークマネージャー」→「整理」→「ブックマークをHTMLファイルにエクスポート」でbookmarks.htmlファイルを作成し、test_bookmarks.htmlとしてプロジェクトルートに配置してください。

### pytest（オプション）
```bash
# 開発依存関係をインストール（pytest含む）
uv sync --dev

# pytestでテスト実行
uv run pytest tests/
```
