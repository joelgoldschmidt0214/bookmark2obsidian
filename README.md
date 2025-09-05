# bookmark2obsidian

Retrieve all linked pages from the &lt;a> tags in Chrome bookmarks, preserving the folder structure, and generate a set of Obsidian pages accordingly.

## 開発環境のセットアップ

```bash
# 依存関係のインストール
uv sync

# アプリケーションの起動
uv run streamlit run app.py
```

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
