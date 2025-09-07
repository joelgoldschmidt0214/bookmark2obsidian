# 設計文書

## 概要

この設計文書は、4260行のStreamlitアプリケーション（`app.py`）を関心の分離原則に基づいてモジュール化するためのアーキテクチャと実装戦略を定義します。現在のモノリシックな構造を、保守性と再利用性を向上させる明確な責任分離を持つモジュラー構造に変換します。

## アーキテクチャ

### 全体アーキテクチャ

```
bookmark-converter/
├── app.py                    # エントリーポイント（Streamlitアプリケーション）
├── core/                     # ビジネスロジック層
│   ├── __init__.py
│   ├── parser.py            # ブックマーク解析
│   ├── scraper.py           # Webスクレイピング
│   ├── generator.py         # Markdown生成
│   └── file_manager.py      # ファイル・ディレクトリ管理
├── ui/                      # プレゼンテーション層
│   ├── __init__.py
│   └── components.py        # UI表示コンポーネント
└── utils/                   # 共通ユーティリティ層
    ├── __init__.py
    ├── models.py           # データモデル
    └── error_handler.py    # エラーハンドリング
```

### レイヤー構造

1. **プレゼンテーション層（UI）**: Streamlitベースのユーザーインターフェース
2. **ビジネスロジック層（Core）**: アプリケーションの中核機能
3. **ユーティリティ層（Utils）**: 共通データモデルとエラーハンドリング

## コンポーネントと インターフェース

### 1. データモデル層（utils/models.py）

#### 責任
- アプリケーション全体で使用されるデータ構造の定義
- 型安全性の提供
- データの整合性保証

#### 主要コンポーネント
```python
class PageStatus(Enum):
    """ページ処理状態を表す列挙型"""
    
class Bookmark(dataclass):
    """ブックマーク情報を格納するデータクラス"""
    
class Page(dataclass):
    """処理対象ページの情報を格納するデータクラス"""
```

#### インターフェース
- 他のすべてのモジュールから参照される
- 循環依存を避けるため、他のモジュールに依存しない

### 2. エラーハンドリング層（utils/error_handler.py）

#### 責任
- 統一されたエラーログ記録
- エラー分類と統計
- リトライ可能エラーの管理

#### 主要コンポーネント
```python
class ErrorLogger:
    """エラーログの記録と管理を行うクラス"""
    
    def log_error(self, bookmark: 'Bookmark', error_msg: str, error_type: str, retryable: bool = False)
    def get_error_summary(self) -> Dict[str, Any]
    def get_retryable_errors(self) -> List[Dict]
```

#### インターフェース
- グローバルインスタンス `error_logger` を提供
- 他のすべてのモジュールから利用可能

### 3. ブックマーク解析層（core/parser.py）

#### 責任
- bookmarks.htmlファイルの解析
- ブックマーク情報の抽出
- ディレクトリ構造の生成

#### 主要コンポーネント
```python
class BookmarkParser:
    """bookmarks.htmlファイルを解析してブックマーク情報を抽出するクラス"""
    
    def parse_bookmarks(self, html_content: str) -> List[Bookmark]
    def extract_directory_structure(self, bookmarks: List[Bookmark]) -> Dict[str, List[str]]
    def _parse_dl_element(self, dl_element, current_path: List[str]) -> List[Bookmark]
```

#### 依存関係
- `utils.models.Bookmark` を使用
- BeautifulSoup、re、datetime等の標準ライブラリ

### 4. ファイル管理層（core/file_manager.py）

#### 責任
- ローカルディレクトリの管理
- 重複ファイルの検出
- ファイル保存操作

#### 主要コンポーネント
```python
class LocalDirectoryManager:
    """ローカルディレクトリの構造を解析し、重複チェックを行うクラス"""
    
    def scan_directory(self, path: Optional[str] = None) -> Dict[str, List[str]]
    def check_file_exists(self, path: str, filename: str) -> bool
    def compare_with_bookmarks(self, bookmarks: List[Bookmark]) -> Dict[str, List[str]]
    def save_markdown_file(self, path: str, content: str) -> bool
```

#### 依存関係
- `utils.models.Bookmark` を使用
- pathlib、os、re等の標準ライブラリ

### 5. Webスクレイピング層（core/scraper.py）

#### 責任
- Webページの取得
- robots.txt確認
- レート制限の実装
- 記事本文の抽出

#### 主要コンポーネント
```python
class WebScraper:
    """Webページ取得・解析クラス"""
    
    def fetch_page_content(self, url: str) -> Optional[str]
    def extract_article_content(self, html_content: str, url: str) -> Dict[str, Any]
    def check_robots_txt(self, domain: str) -> bool
```

#### 依存関係
- requests、BeautifulSoup、urllib等のWebライブラリ
- `utils.error_handler.error_logger` を使用

### 6. Markdown生成層（core/generator.py）

#### 責任
- Obsidian形式のMarkdown生成
- メタデータの埋め込み
- ファイルパスの生成

#### 主要コンポーネント
```python
class MarkdownGenerator:
    """Obsidian形式のMarkdown生成クラス"""
    
    def generate_obsidian_markdown(self, bookmark: Bookmark, content: str = None) -> str
    def generate_file_path(self, bookmark: Bookmark, base_path: Path) -> Path
```

#### 依存関係
- `utils.models.Bookmark` を使用
- pathlib、datetime等の標準ライブラリ

### 7. UIコンポーネント層（ui/components.py）

#### 責任
- Streamlitベースの画面表示
- ユーザー入力の検証
- インタラクティブな操作の提供

#### 主要コンポーネント
```python
# ファイル検証関数
def validate_bookmarks_file(uploaded_file) -> tuple[bool, str]
def validate_directory_path(directory_path: str) -> tuple[bool, str]

# 表示関数
def display_edge_case_summary(edge_case_result: Dict[str, Any])
def display_page_list_and_preview(bookmarks: List[Bookmark], duplicates: Dict, output_directory: Path)
def display_bookmark_tree(bookmarks: List[Bookmark], folder_groups: Dict, duplicates: Dict)
def show_page_preview(bookmark: Bookmark, index: int)

# 保存関数
def save_selected_pages_enhanced(selected_bookmarks: List[Bookmark], output_directory: Path)
def save_selected_pages(selected_bookmarks: List[Bookmark], output_directory: Path)
```

#### 依存関係
- streamlit
- すべてのcoreモジュール
- `utils.models` と `utils.error_handler`

### 8. メインアプリケーション（app.py）

#### 責任
- アプリケーションのエントリーポイント
- ログ設定
- 全体的なワークフローの制御

#### 主要コンポーネント
```python
def main():
    """メインアプリケーション関数"""
    # Streamlitアプリケーションの実行
```

## データモデル

### Bookmark
```python
@dataclass
class Bookmark:
    title: str                              # ブックマークタイトル
    url: str                               # URL
    folder_path: List[str]                 # フォルダ階層
    add_date: Optional[datetime.datetime]  # 追加日時
    icon: Optional[str]                    # アイコン情報
```

### Page
```python
@dataclass
class Page:
    bookmark: Bookmark                     # 関連ブックマーク
    content: Optional[str]                 # 取得したコンテンツ
    tags: List[str]                       # タグ情報
    metadata: Dict                        # メタデータ
    is_selected: bool                     # 選択状態
    status: PageStatus                    # 処理状態
```

### PageStatus
```python
class PageStatus(Enum):
    PENDING = "pending"    # 処理待ち
    FETCHING = "fetching"  # 取得中
    SUCCESS = "success"    # 成功
    EXCLUDED = "excluded"  # 除外
    ERROR = "error"        # エラー
```

## エラーハンドリング

### エラー分類
1. **ネットワークエラー**: 接続失敗、タイムアウト
2. **取得エラー**: HTTPエラー、SSL証明書エラー
3. **抽出エラー**: コンテンツ解析失敗
4. **ファイルシステムエラー**: 権限不足、ディスク容量不足
5. **予期しないエラー**: その他の例外

### エラーログ構造
```python
{
    'timestamp': datetime.datetime,
    'bookmark': Bookmark,
    'error': str,
    'type': str,
    'retryable': bool,
    'url': str,
    'title': str
}
```

## テスト戦略

### 単体テスト
- 各クラスの主要メソッドに対するテスト
- モックを使用した外部依存関係の分離
- エラーケースのテスト

### 統合テスト
- モジュール間の連携テスト
- ファイルI/Oのテスト
- Webスクレイピングのテスト（テストデータ使用）

### UIテスト
- Streamlitコンポーネントの表示テスト
- ユーザー操作のシミュレーション

## 実装戦略

### フェーズ1: 基盤構築
1. ディレクトリ構造の作成
2. データモデルの分離
3. エラーハンドラーの分離

### フェーズ2: コアロジック分離
1. BookmarkParserの分離
2. LocalDirectoryManagerの分離
3. WebScraperの分離
4. MarkdownGeneratorの分離

### フェーズ3: UI分離
1. UIコンポーネントの分離
2. インポートの更新

### フェーズ4: 統合とテスト
1. メインアプリケーションの更新
2. インポートエラーの解決
3. 機能テストの実行

## 移行計画

### 段階的移行
1. **準備段階**: 新しいディレクトリ構造の作成
2. **分離段階**: クラスと関数の段階的移動
3. **統合段階**: インポートの更新と動作確認
4. **検証段階**: 全機能の動作テスト

### リスク軽減策
- 各段階での動作確認
- 元のコードのバックアップ保持
- 段階的なコミットによる変更履歴の保持

## パフォーマンス考慮事項

### インポート最適化
- 必要最小限のインポートのみ実行
- 循環インポートの回避
- 遅延インポートの活用（必要に応じて）

### メモリ使用量
- 大きなファイルの段階的処理
- 不要なオブジェクトの適切な解放

## セキュリティ考慮事項

### ファイルアクセス
- パストラバーサル攻撃の防止
- ファイル権限の適切な確認

### Webスクレイピング
- robots.txtの遵守
- レート制限の実装
- 適切なUser-Agentの設定

## 保守性向上

### ドキュメント
- 各モジュールの責任の明確化
- 包括的なdocstringの追加
- 使用例の提供

### コード品質
- 一貫したコーディングスタイル
- 型ヒントの活用
- エラーハンドリングの統一