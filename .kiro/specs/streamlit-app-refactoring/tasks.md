# 実装計画

- [ ] 1. プロジェクト構造の準備とディレクトリ作成
  - 必要なディレクトリ構造（core/, ui/, utils/）を作成
  - 各ディレクトリに空の__init__.pyファイルを作成
  - _要件: 1.1, 1.2, 1.3_

- [ ] 2. 共通データモデルの分離
  - [ ] 2.1 データモデルファイルの作成と基本構造の実装
    - utils/models.pyファイルを作成
    - 必要なインポート（Enum, dataclass, field, List, Dict, Optional, datetime）を追加
    - _要件: 2.1, 2.2_
  
  - [ ] 2.2 データクラスの移動と実装
    - PageStatus(Enum)をutils/models.pyに移動
    - Bookmark(dataclass)をutils/models.pyに移動  
    - Page(dataclass)をutils/models.pyに移動
    - 各クラスに適切なdocstringを追加
    - _要件: 2.1, 8.1, 8.2_

- [ ] 3. エラーハンドリングシステムの分離
  - [ ] 3.1 エラーハンドラーファイルの作成
    - utils/error_handler.pyファイルを作成
    - 必要なインポート（datetime, Dict, Any, List）を追加
    - Bookmarkモデルの相対インポートを追加（循環参照対策で文字列型ヒント使用）
    - _要件: 3.1, 3.3, 7.2_
  
  - [ ] 3.2 ErrorLoggerクラスの移動と強化
    - ErrorLoggerクラス全体をutils/error_handler.pyに移動
    - グローバルerror_loggerインスタンスを移動
    - ErrorLoggerクラスとlog_errorメソッドに包括的なdocstringを追加
    - _要件: 3.1, 3.2, 8.1, 8.2_

- [ ] 4. ブックマーク解析機能の分離
  - [ ] 4.1 パーサーファイルの作成と基本構造
    - core/parser.pyファイルを作成
    - 必要なインポート（BeautifulSoup, re, datetime, Optional, List, Dict）を追加
    - データモデルの相対インポート（from ..utils.models import Bookmark）を追加
    - _要件: 4.1, 4.5, 7.2_
  
  - [ ] 4.2 BookmarkParserクラスの移動と文書化
    - BookmarkParserクラス全体をcore/parser.pyに移動
    - クラスとparse_bookmarks, extract_directory_structureメソッドにdocstringを追加
    - すべてのプライベートメソッドも含めて完全に移動
    - _要件: 4.1, 4.6, 8.1, 8.2, 9.1, 9.3_

- [ ] 5. ファイル管理機能の分離
  - [ ] 5.1 ファイルマネージャーファイルの作成
    - core/file_manager.pyファイルを作成
    - 必要なインポート（Path, os, re, logging, Optional, List, Dict, Any）を追加
    - データモデルの相対インポート（from ..utils.models import Bookmark）を追加
    - _要件: 4.2, 4.5, 7.1_
  
  - [ ] 5.2 LocalDirectoryManagerクラスの移動と文書化
    - LocalDirectoryManagerクラス全体をcore/file_manager.pyに移動
    - クラスとscan_directory, check_file_exists, compare_with_bookmarks, save_markdown_fileメソッドにdocstringを追加
    - すべてのプライベートメソッドも含めて完全に移動
    - _要件: 4.2, 4.6, 8.1, 8.2, 9.1, 9.3_

- [ ] 6. Webスクレイピング機能の分離
  - [ ] 6.1 スクレイパーファイルの作成
    - core/scraper.pyファイルを作成
    - 必要なインポート（requests, BeautifulSoup, urlparse, RobotFileParser, time, logging, re, Optional, Dict, List, Any）を追加
    - _要件: 4.3, 4.5, 7.1_
  
  - [ ] 6.2 WebScraperクラスの移動と文書化
    - WebScraperクラス全体をcore/scraper.pyに移動
    - クラスとfetch_page_content, extract_article_contentメソッドにdocstringを追加
    - すべてのプライベートメソッドも含めて完全に移動
    - _要件: 4.3, 4.6, 8.1, 8.2, 9.1, 9.3_

- [ ] 7. Markdown生成機能の分離
  - [ ] 7.1 ジェネレーターファイルの作成
    - core/generator.pyファイルを作成
    - 必要なインポート（logging, datetime, re, Path, Dict, List, Any）を追加
    - データモデルの相対インポート（from ..utils.models import Bookmark）を追加
    - _要件: 4.4, 4.5, 7.2_
  
  - [ ] 7.2 MarkdownGeneratorクラスの移動と文書化
    - MarkdownGeneratorクラス全体をcore/generator.pyに移動
    - クラスとgenerate_obsidian_markdown, generate_file_pathメソッドにdocstringを追加
    - すべてのプライベートメソッドも含めて完全に移動
    - _要件: 4.4, 4.6, 8.1, 8.2, 9.1, 9.3_

- [ ] 8. UIコンポーネントの分離
  - [ ] 8.1 UIコンポーネントファイルの作成
    - ui/components.pyファイルを作成
    - 必要なStreamlitインポート（streamlit）を追加
    - 必要な標準ライブラリインポート（Path, os, BeautifulSoup, requests等）を追加
    - 作成したモジュールの相対インポート（..utils.models, ..core.file_manager等）を追加
    - _要件: 5.1, 5.4, 7.1, 7.2_
  
  - [ ] 8.2 検証関数の移動と文書化
    - validate_bookmarks_file関数をui/components.pyに移動
    - validate_directory_path関数をui/components.pyに移動
    - handle_edge_cases_and_errors関数と関連ヘルパー関数を移動
    - 各関数にUI機能を説明するdocstringを追加
    - _要件: 5.2, 5.3, 8.3, 9.1_
  
  - [ ] 8.3 表示関数の移動と文書化
    - display_edge_case_summary, display_user_friendly_messages, show_application_info関数を移動
    - display_page_list_and_preview, display_bookmark_tree関数を移動
    - organize_bookmarks_by_folder, display_bookmark_structure_tree関数を移動
    - display_bookmark_list_only, show_page_preview関数を移動
    - 各関数にUI表示内容を説明するdocstringを追加
    - _要件: 5.2, 5.3, 8.3, 9.1_
  
  - [ ] 8.4 保存関数の移動と文書化
    - save_selected_pages_enhanced関数をui/components.pyに移動
    - save_selected_pages関数をui/components.pyに移動
    - 関連するヘルパー関数（_display_tree_recursive等）も移動
    - 各関数にUI操作を説明するdocstringを追加
    - _要件: 5.2, 5.3, 8.3, 9.1_

- [ ] 9. メインアプリケーションファイルのリファクタリング
  - [ ] 9.1 app.pyのインポート更新
    - 分離したモジュールからの適切なインポート文を追加
    - core.parser, core.file_manager, core.scraper, core.generatorからのクラスインポート
    - ui.componentsからの関数インポート
    - utils.models, utils.error_handlerからの必要な要素インポート
    - _要件: 6.2, 7.2, 7.3_
  
  - [ ] 9.2 main関数の更新と文書化
    - main関数内のクラスインスタンス化を新しいインポートに更新
    - main関数内の関数呼び出しを新しいインポートに更新
    - main関数にアプリケーションエントリーポイントとしてのdocstringを追加
    - ログ設定以外の不要なコードを削除
    - _要件: 6.1, 6.3, 6.4, 8.1, 8.2_

- [ ] 10. インポートエラーの解決と動作確認
  - [ ] 10.1 循環依存関係の確認と修正
    - すべてのモジュール間で循環インポートが発生していないことを確認
    - 必要に応じて文字列型ヒントを使用して循環参照を回避
    - 各モジュールが独立してインポート可能であることを確認
    - _要件: 2.4, 3.4, 7.3, 7.4_
  
  - [ ] 10.2 機能テストと検証
    - リファクタリング後のアプリケーションが正常に起動することを確認
    - 主要機能（ブックマーク解析、ファイル保存、UI表示）が正常に動作することを確認
    - エラーハンドリングが適切に機能することを確認
    - 元の機能と同じ動作をすることを確認
    - _要件: 9.2, 9.4, 10.1, 10.2, 10.3, 10.4_

- [ ] 11. 最終検証とクリーンアップ
  - [ ] 11.1 コード品質の確認
    - 各モジュールが指定された責任のみを持つことを確認
    - 重複コードが存在しないことを確認
    - すべてのdocstringが適切に追加されていることを確認
    - 一貫したコーディングスタイルが維持されていることを確認
    - _要件: 8.3, 8.4, 10.1, 10.2_
  
  - [ ] 11.2 ファイル構成の最終確認
    - すべてのファイルが正しいディレクトリに配置されていることを確認
    - app.pyがmain関数とログ設定のみを含むことを確認
    - 不要なコードや未使用のインポートが残っていないことを確認
    - プロジェクト構造が設計通りになっていることを確認
    - _要件: 10.3, 10.4_