# 設計文書

## 概要

この設計文書は、bookmark2obsidianアプリケーションのパフォーマンス改善とUI表示問題の修正のためのアーキテクチャと実装戦略を定義します。現在の4000件のブックマーク解析に90秒かかる問題、ログ表示の改行問題、結果表示の問題、およびキャッシュ機能の不足を解決します。

## アーキテクチャ

### 現在の問題分析

#### 1. パフォーマンス問題
- **ボトルネック**: `BookmarkParser.parse_bookmarks()`での逐次処理
- **原因**: BeautifulSoupによる大量のDOM操作が単一スレッドで実行
- **影響**: 4000件のブックマークで90秒の処理時間

#### 2. ログ表示問題
- **問題**: `st.text_area()`で`\n`がエスケープされて表示
- **原因**: `"\\n".join(logs)`でエスケープ文字として処理
- **影響**: ログが1行で表示され、可読性が低下

#### 3. 結果表示問題
- **問題**: 解析完了後にブックマーク一覧とプレビューが表示されない
- **原因**: セッション状態の管理とUI更新のタイミング問題
- **影響**: ユーザーが次のステップに進めない

#### 4. キャッシュ機能不足
- **問題**: 同じファイルを再度解析する必要がある
- **原因**: 解析結果の永続化機能がない
- **影響**: 作業効率の低下

### 改善アーキテクチャ

```
bookmark-converter/
├── app.py                           # エントリーポイント（改善済み）
├── core/                           # ビジネスロジック層（改善対象）
│   ├── parser.py                   # ← パフォーマンス改善
│   ├── scraper.py                  
│   ├── generator.py                
│   ├── file_manager.py             
│   └── cache_manager.py            # ← 新規追加
├── ui/                            # プレゼンテーション層（改善対象）
│   ├── components.py               # ← ログ表示・結果表示改善
│   └── progress_display.py         # ← 新規追加
└── utils/                         # 共通ユーティリティ層
    ├── models.py                   
    ├── error_handler.py            
    └── performance_utils.py         # ← 新規追加
```

## コンポーネントと インターフェース

### 1. パフォーマンス改善層（utils/performance_utils.py）

#### 責任
- 並列処理の管理
- バッチ処理の最適化
- メモリ使用量の監視

#### 主要コンポーネント
```python
class PerformanceOptimizer:
    """パフォーマンス最適化を管理するクラス"""
    
    def optimize_parsing(self, html_content: str, batch_size: int = 1000) -> List[Bookmark]
    def parallel_process_bookmarks(self, bookmarks: List[Bookmark], worker_count: int = 4) -> List[Bookmark]
    def monitor_memory_usage(self) -> Dict[str, float]
```

#### インターフェース
- `BookmarkParser`から利用される
- バッチサイズと並列度を動的に調整

### 2. キャッシュ管理層（core/cache_manager.py）

#### 責任
- 解析結果のローカルストレージ保存
- キャッシュの有効性検証
- キャッシュデータの管理

#### 主要コンポーネント
```python
class CacheManager:
    """解析結果のキャッシュを管理するクラス"""
    
    def save_bookmark_cache(self, file_hash: str, bookmarks: List[Bookmark]) -> bool
    def load_bookmark_cache(self, file_hash: str) -> Optional[List[Bookmark]]
    def save_directory_cache(self, path: str, structure: Dict[str, List[str]]) -> bool
    def load_directory_cache(self, path: str) -> Optional[Dict[str, List[str]]]
    def clear_all_cache(self) -> bool
    def get_cache_info(self) -> Dict[str, Any]
```

#### データ構造
```python
# キャッシュエントリ
{
    'file_hash': str,           # ファイルのハッシュ値
    'timestamp': datetime,      # キャッシュ作成時刻
    'bookmarks': List[Bookmark], # ブックマークデータ
    'metadata': {
        'file_size': int,
        'bookmark_count': int,
        'processing_time': float
    }
}
```

### 3. 進捗表示層（ui/progress_display.py）

#### 責任
- リアルタイム進捗表示
- ログ表示の改善
- パフォーマンス統計の表示

#### 主要コンポーネント
```python
class ProgressDisplay:
    """進捗表示を管理するクラス"""
    
    def create_progress_container(self) -> Tuple[Any, Any, Any]
    def update_progress(self, progress: float, message: str) -> None
    def add_log_message(self, message: str, level: str = "info") -> None
    def display_performance_stats(self, stats: Dict[str, Any]) -> None
```

#### ログ表示改善
```python
# 現在の問題のあるコード
log_placeholder.text_area("📝 処理ログ", "\\n".join(logs[-10:]), height=200)

# 改善後のコード
log_placeholder.markdown("\\n".join([f"```\\n{log}\\n```" for log in logs[-10:]]))
```

### 4. 改善されたブックマーク解析層（core/parser.py）

#### パフォーマンス改善戦略
1. **バッチ処理**: 大量のブックマークを小さなバッチに分割
2. **並列処理**: CPU集約的な処理を複数スレッドで実行
3. **メモリ最適化**: 不要なオブジェクトの早期解放
4. **進捗レポート**: リアルタイムの進捗更新

#### 改善されたメソッド
```python
class BookmarkParser:
    def parse_bookmarks_optimized(self, html_content: str, progress_callback=None) -> List[Bookmark]:
        """最適化されたブックマーク解析"""
        
    def _parse_in_batches(self, soup: BeautifulSoup, batch_size: int = 1000) -> List[Bookmark]:
        """バッチ処理による解析"""
        
    def _parallel_parse_elements(self, elements: List, worker_count: int = 4) -> List[Bookmark]:
        """並列処理による要素解析"""
```

### 5. 改善されたUIコンポーネント層（ui/components.py）

#### ログ表示改善
```python
def display_improved_logs(logs: List[str], container) -> None:
    """改善されたログ表示"""
    # マークダウン形式で改行を正しく処理
    formatted_logs = "\\n".join(logs[-10:])
    container.markdown(f"```\\n{formatted_logs}\\n```")

def display_results_with_error_handling(bookmarks: List[Bookmark], duplicates: Dict) -> None:
    """エラーハンドリング付きの結果表示"""
    try:
        # 結果表示ロジック
        pass
    except Exception as e:
        st.error(f"結果表示エラー: {str(e)}")
        logger.exception("結果表示でエラーが発生しました")
```

## データモデル

### キャッシュエントリ
```python
@dataclass
class CacheEntry:
    file_hash: str
    timestamp: datetime.datetime
    data: Any
    metadata: Dict[str, Any]
    
@dataclass
class PerformanceMetrics:
    processing_time: float
    memory_usage: float
    items_processed: int
    batch_size: int
    worker_count: int
```

## エラーハンドリング

### 新しいエラー分類
1. **パフォーマンスエラー**: メモリ不足、処理タイムアウト
2. **キャッシュエラー**: ストレージアクセス失敗、データ破損
3. **UI表示エラー**: レンダリング失敗、セッション状態エラー
4. **並列処理エラー**: スレッド例外、リソース競合

### エラー回復戦略
```python
class ErrorRecoveryStrategy:
    def handle_performance_error(self, error: Exception) -> bool:
        """パフォーマンスエラーの回復処理"""
        
    def handle_cache_error(self, error: Exception) -> bool:
        """キャッシュエラーの回復処理"""
        
    def handle_ui_error(self, error: Exception) -> bool:
        """UI表示エラーの回復処理"""
```

## テスト戦略

### パフォーマンステスト
- 大量データ（1000, 4000, 10000件）での処理時間測定
- メモリ使用量の監視
- 並列処理の効果測定

### キャッシュテスト
- キャッシュの保存・読み込み機能
- データ整合性の確認
- キャッシュ無効化の動作

### UI表示テスト
- ログ表示の改行確認
- 結果表示の正常性確認
- エラー時の表示確認

## 実装戦略

### フェーズ1: パフォーマンス改善
1. `PerformanceOptimizer`クラスの実装
2. `BookmarkParser`の最適化
3. バッチ処理と並列処理の導入

### フェーズ2: キャッシュ機能
1. `CacheManager`クラスの実装
2. ファイルハッシュ計算機能
3. キャッシュUI機能の追加

### フェーズ3: UI改善
1. ログ表示の修正
2. 結果表示の改善
3. 進捗表示の強化

### フェーズ4: エラーハンドリング強化
1. 新しいエラー分類の実装
2. 回復戦略の実装
3. ユーザーフレンドリーなエラーメッセージ

## パフォーマンス目標

### 処理時間目標
- **現在**: 4000件で90秒
- **目標**: 4000件で30秒以下（66%改善）
- **手段**: バッチ処理（50%改善）+ 並列処理（33%改善）

### メモリ使用量目標
- **現在**: 制限なし（メモリリーク可能性）
- **目標**: 最大500MB以下
- **手段**: バッチ処理とガベージコレクション

### レスポンス性目標
- **進捗更新**: 1秒間隔
- **ログ更新**: リアルタイム
- **UI応答**: 100ms以下

## セキュリティ考慮事項

### キャッシュセキュリティ
- ファイルハッシュによる整合性確認
- ローカルストレージのアクセス制御
- 機密情報の暗号化（必要に応じて）

### 並列処理セキュリティ
- スレッドセーフなデータアクセス
- リソース競合の回避
- 例外の適切な処理

## 保守性向上

### モニタリング
- パフォーマンスメトリクスの収集
- エラー発生率の追跡
- キャッシュヒット率の監視

### ログ改善
- 構造化ログの導入
- パフォーマンス情報の記録
- デバッグ情報の充実

### 設定管理
- パフォーマンス設定の外部化
- キャッシュ設定の調整可能化
- デバッグモードの提供