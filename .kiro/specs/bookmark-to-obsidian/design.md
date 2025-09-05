# 設計書

## 概要

bookmark-to-obsidianアプリケーションは、Google Chromeのブックマークファイルを解析し、Webページの内容を取得してObsidian用のMarkdownファイルを生成するStreamlitベースのデスクトップアプリケーションです。単一の`app.py`ファイルとして実装され、ユーザーのローカル環境で動作します。

## アーキテクチャ

### システム構成

```
bookmark-to-obsidian/
├── app.py              # Streamlitメインアプリケーション
├── pyproject.toml      # プロジェクト設定と依存関係
├── README.md           # プロジェクト説明書
└── PROJECT_CHARTER.md  # プロジェクト憲法
```

### 技術スタック

- **フレームワーク**: Streamlit (UI構築)
- **HTML解析**: BeautifulSoup4 (bookmarks.html解析、Webスクレイピング)
- **HTTP通信**: requests (Webページ取得)
- **ファイル処理**: pathlib (ローカルファイルシステム操作)
- **テキスト処理**: re (正規表現)、urllib.robotparser (robots.txt確認)

## コンポーネントと インターフェース

### 1. UIコンポーネント (Streamlit)

```python
class StreamlitUI:
    """Streamlit UIの管理クラス"""
    
    def render_file_upload() -> UploadedFile
    def render_directory_selector() -> str
    def render_page_tree(pages: List[Page]) -> Dict[str, bool]
    def render_preview(page: Page) -> None
    def render_progress_bar(current: int, total: int) -> None
    def render_save_button() -> bool
```

### 2. ブックマーク解析コンポーネント

```python
class BookmarkParser:
    """bookmarks.html解析クラス"""
    
    def parse_bookmarks(html_content: str) -> List[Bookmark]
    def extract_directory_structure(bookmarks: List[Bookmark]) -> Dict
    def validate_bookmark_file(content: str) -> bool
```

### 3. ローカルディレクトリ管理コンポーネント

```python
class LocalDirectoryManager:
    """ローカルディレクトリ操作クラス"""
    
    def scan_directory(path: str) -> Dict[str, List[str]]
    def check_file_exists(path: str, filename: str) -> bool
    def create_directory_structure(base_path: str, structure: Dict) -> None
    def save_markdown_file(path: str, content: str) -> bool
```

### 4. Webスクレイピングコンポーネント

```python
class WebScraper:
    """Webページ取得・解析クラス"""
    
    def check_robots_txt(domain: str) -> bool
    def fetch_page_content(url: str) -> Optional[str]
    def extract_article_content(html: str) -> Optional[Dict]
    def group_urls_by_domain(urls: List[str]) -> Dict[str, List[str]]
    def apply_rate_limiting(domain: str) -> None
```

### 5. Markdown生成コンポーネント

```python
class MarkdownGenerator:
    """Obsidian Markdown生成クラス"""
    
    def generate_obsidian_markdown(page_data: Dict) -> str
    def create_yaml_frontmatter(metadata: Dict) -> str
    def format_content_for_obsidian(content: str) -> str
    def extract_and_format_tags(html: str) -> List[str]
```

## データモデル

### Bookmark

```python
@dataclass
class Bookmark:
    title: str
    url: str
    folder_path: List[str]  # ディレクトリ階層
    add_date: Optional[datetime]
    icon: Optional[str]
```

### Page

```python
@dataclass
class Page:
    bookmark: Bookmark
    content: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    metadata: Dict = field(default_factory=dict)
    is_selected: bool = True
    status: PageStatus = PageStatus.PENDING
```

### PageStatus

```python
class PageStatus(Enum):
    PENDING = "pending"
    FETCHING = "fetching"
    SUCCESS = "success"
    EXCLUDED = "excluded"
    ERROR = "error"
```

## エラーハンドリング

### エラー分類と対応

1. **ファイル関連エラー**
   - 無効なbookmarks.htmlファイル → ユーザーに再アップロードを促す
   - ディレクトリアクセス権限エラー → 適切な権限設定を案内

2. **ネットワーク関連エラー**
   - 接続タイムアウト → リトライ機能付きエラー表示
   - robots.txt違反 → 該当URLを自動除外

3. **スクレイピング関連エラー**
   - 記事本文取得失敗 → 該当ページを除外リストに追加
   - レート制限 → 適切な待ち時間を設定

### エラーログ機能

```python
class ErrorLogger:
    """エラーログ管理クラス"""
    
    def log_error(error_type: str, url: str, message: str) -> None
    def get_error_summary() -> Dict[str, int]
    def display_error_report() -> None
```

## テスト戦略

### 単体テスト対象

1. **BookmarkParser**
   - 有効なbookmarks.htmlの解析
   - 無効なファイルの検出
   - ディレクトリ構造の正確な抽出

2. **WebScraper**
   - robots.txt確認機能
   - レート制限の実装
   - 記事本文抽出の精度

3. **MarkdownGenerator**
   - Obsidian形式のYAML front matter生成
   - タグの適切な変換
   - Markdown構文の正確性

### 統合テスト

1. **エンドツーエンドフロー**
   - bookmarks.htmlアップロード → Markdown生成 → ファイル保存
   - 重複チェック機能の動作確認
   - エラーハンドリングの動作確認

### テストデータ

- サンプルbookmarks.htmlファイル（様々な構造パターン）
- テスト用Webページ（記事形式、非記事形式）
- robots.txtテストケース

## パフォーマンス考慮事項

### スクレイピング最適化

1. **ドメイン別レート制限**
   - 同一ドメインへのアクセス間隔：2-5秒
   - 並行処理数の制限：最大3ドメイン同時

2. **キャッシュ機能**
   - 取得済みページの一時保存
   - セッション内での重複アクセス防止

3. **プログレス表示**
   - リアルタイム進捗バー
   - 処理中ページの状態表示

### メモリ管理

- 大量ブックマーク処理時のメモリ使用量制御
- ストリーミング処理による大容量ファイル対応

## セキュリティ考慮事項

1. **ファイルアクセス制限**
   - ユーザー指定ディレクトリ外へのアクセス防止
   - 危険なファイル拡張子の制限

2. **Webスクレイピング**
   - robots.txt遵守の徹底
   - User-Agentの適切な設定
   - SSL証明書検証

3. **入力検証**
   - HTMLインジェクション対策
   - パストラバーサル攻撃防止