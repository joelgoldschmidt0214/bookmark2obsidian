"""
ブックマーク解析モジュール

このモジュールは、ブラウザのbookmarks.htmlファイルを解析して
ブックマーク情報を抽出する機能を提供します。
"""

import datetime
import logging
import re
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Dict, List, Optional
from urllib.parse import urlparse

import yaml
from bs4 import BeautifulSoup

from utils.models import Bookmark
from utils.performance_utils import PerformanceOptimizer, performance_monitor

logger = logging.getLogger(__name__)


class BookmarkParser:
    """
    bookmarks.htmlファイルを解析してブックマーク情報を抽出するクラス

    ブラウザのエクスポートしたbookmarks.htmlファイルを解析し、
    ブックマーク情報を構造化されたデータとして抽出します。
    フォルダ階層の解析、除外ルールの適用、統計情報の生成などの機能を提供します。
    """

    def __init__(self, rules_path: str = "filter_rules.yml"):
        """
        BookmarkParserを初期化

        Args:
            rules_path (str): フィルタリングルールを定義したYAMLファイルのパス
        """
        self.performance_optimizer = PerformanceOptimizer()
        self._lock = threading.Lock()  # スレッドセーフ用のロック
        self.rules_path = rules_path
        self._load_filter_rules()

    def _load_filter_rules(self):
        """フィルタリングルールをYAMLファイルから読み込む"""
        try:
            with open(self.rules_path, "r", encoding="utf-8") as f:
                rules = yaml.safe_load(f) or {}

            # 各ルールを属性として設定（getでキーが存在しない場合も考慮）
            self.allow_rules = rules.get("allow", {})
            self.deny_rules = rules.get("deny", {})
            self.regex_deny_rules = rules.get("regex_deny", {})

            # 高速な検索のためにセットやリストに変換して保持
            self.allow_domains = set(self.allow_rules.get("domains", []))
            self.deny_domains = set(self.deny_rules.get("domains", []))
            self.deny_subdomains = self.deny_rules.get("subdomain_keywords", [])
            self.allow_path_keywords = self.allow_rules.get("path_keywords", [])
            self.deny_path_keywords = self.deny_rules.get("path_keywords", [])
            self.regex_deny_patterns = self.regex_deny_rules.get("patterns", [])

            logger.info(f"フィルタリングルールを '{self.rules_path}' から読み込みました。")

        except FileNotFoundError:
            logger.warning(f"ルールファイル '{self.rules_path}' が見つかりません。基本的なフィルタリングのみ行います。")
            # ルールが存在しない場合のデフォルト値を設定
            self.allow_domains, self.deny_domains = set(), set()
            self.deny_subdomains, self.allow_path_keywords, self.deny_path_keywords, self.regex_deny_patterns = (
                [],
                [],
                [],
                [],
            )
        except Exception as e:
            logger.error(f"ルールファイルの読み込みに失敗しました: {e}")
            raise ValueError("ルールファイルの解析に失敗しました。")

    def parse_bookmarks(self, html_content: str) -> List[Bookmark]:
        """
        HTMLコンテンツからブックマーク一覧を抽出する

        bookmarks.htmlファイルの内容を解析し、ブックマーク情報を
        Bookmarkオブジェクトのリストとして返します。

        Args:
            html_content: bookmarks.htmlの内容

        Returns:
            List[Bookmark]: 抽出されたブックマーク一覧

        Raises:
            ValueError: ブックマーク解析に失敗した場合
        """
        try:
            soup = BeautifulSoup(html_content, "lxml")
            bookmarks = []

            # ルートDLエレメントから開始
            root_dl = soup.find("dl")
            if root_dl:
                bookmarks = self._parse_dl_element(root_dl, [])

            return bookmarks

        except Exception as e:
            raise ValueError(f"ブックマーク解析エラー: {str(e)}")

    def extract_directory_structure(self, bookmarks: List[Bookmark]) -> Dict[str, List[str]]:
        """
        ブックマークからディレクトリ構造を抽出

        ブックマークのフォルダ階層情報を基に、ディレクトリ構造を生成します。
        各ディレクトリに含まれるファイル名のリストを返します。

        Args:
            bookmarks: ブックマーク一覧

        Returns:
            Dict[str, List[str]]: ディレクトリパスをキーとしたファイル名一覧
        """
        structure = {}

        for bookmark in bookmarks:
            # フォルダパスを文字列に変換
            folder_path = "/".join(bookmark.folder_path) if bookmark.folder_path else ""

            # ファイル名を生成（タイトルから安全なファイル名を作成）
            filename = self._sanitize_filename(bookmark.title, bookmark.folder_path)

            if folder_path not in structure:
                structure[folder_path] = []

            structure[folder_path].append(filename)

        return structure

    def _parse_dl_element(self, dl_element, current_path: List[str], processed_dls=None) -> List[Bookmark]:
        """
        DLエレメントを愚直に解析してブックマークを抽出

        Args:
            dl_element: BeautifulSoupのDLエレメント
            current_path: 現在のフォルダパス
            processed_dls: 処理済みのDLエレメントのセット

        Returns:
            List[Bookmark]: 抽出されたブックマーク一覧
        """
        if processed_dls is None:
            processed_dls = set()

        # 既に処理済みの場合はスキップ
        if id(dl_element) in processed_dls:
            return []

        # 処理済みとしてマーク
        processed_dls.add(id(dl_element))

        bookmarks = []

        # DLエレメント内のDTを処理（Pタグ内にある場合も考慮）
        # まず、このDLレベルのDTエレメントを取得
        # all_dt_in_dl = dl_element.find_all("dt")  # 未使用のため削除

        # このDLの直接の子DTエレメントのみを取得（pタグ内も含む）
        direct_dt_elements = []
        for child in dl_element.children:
            if hasattr(child, "name"):
                if child.name == "dt":
                    direct_dt_elements.append(child)
                elif child.name == "p":
                    # P要素内のすべてのDTエレメントを取得（ネストしたDL内のものは除く）
                    all_p_dts = child.find_all("dt")

                    # ネストしたDL内のDTを除外
                    nested_dls_in_p = child.find_all("dl")
                    # TagオブジェクトのIDを格納するsetに変更
                    nested_dt_ids_in_p = set()
                    for nested_dl in nested_dls_in_p:
                        # id() を使ってIDをsetに追加する
                        nested_dt_ids_in_p.update(id(t) for t in nested_dl.find_all("dt"))

                    # 存在チェックも id() で行う
                    p_dt_elements = [dt for dt in all_p_dts if id(dt) not in nested_dt_ids_in_p]
                    direct_dt_elements.extend(p_dt_elements)

        for dt in direct_dt_elements:
            # DTの次の兄弟要素がDDかどうかをチェック
            next_sibling = dt.find_next_sibling()

            if next_sibling and next_sibling.name == "dd":
                # DTの後にDDがある場合 → フォルダ構造
                h3 = dt.find("h3")
                if h3:
                    folder_name = h3.get_text(strip=True)
                    new_path = current_path + [folder_name]

                    # DD内のDLを再帰的に処理
                    nested_dl = next_sibling.find("dl")
                    if nested_dl:
                        nested_bookmarks = self._parse_dl_element(nested_dl, new_path, processed_dls)
                        bookmarks.extend(nested_bookmarks)
            else:
                # DTの後にDDがない場合の処理
                # H3タグがあり、内部にDLがある場合はフォルダとして処理
                h3 = dt.find("h3")
                internal_dl = dt.find("dl")

                if h3 and internal_dl:
                    # DTの内部にフォルダ構造がある場合（ブックマークバーなど）
                    folder_name = h3.get_text(strip=True)
                    new_path = current_path + [folder_name]
                    nested_bookmarks = self._parse_dl_element(internal_dl, new_path, processed_dls)
                    bookmarks.extend(nested_bookmarks)
                else:
                    # 通常のブックマーク
                    a_tag = dt.find("a")
                    if a_tag:
                        bookmark = self._extract_bookmark_from_a_tag(a_tag, current_path)
                        if bookmark and not self._should_exclude_bookmark(bookmark):
                            bookmarks.append(bookmark)

        return bookmarks

    def _extract_bookmark_from_a_tag(self, a_tag, folder_path: List[str]) -> Optional[Bookmark]:
        """
        Aタグからブックマーク情報を抽出

        Args:
            a_tag: BeautifulSoupのAエレメント
            folder_path: フォルダパス

        Returns:
            Optional[Bookmark]: 抽出されたブックマーク（除外対象の場合はNone）
        """
        try:
            url = a_tag.get("href", "").strip()
            title = a_tag.get_text(strip=True)

            if not url or not title:
                return None

            # 日付の解析（ADD_DATE属性）
            add_date = None
            add_date_str = a_tag.get("add_date")
            if add_date_str:
                try:
                    # Unix timestampから変換
                    add_date = datetime.datetime.fromtimestamp(int(add_date_str))
                except (ValueError, TypeError):
                    pass

            # アイコン情報の取得
            icon = a_tag.get("icon")

            return Bookmark(
                title=title,
                url=url,
                folder_path=folder_path,
                add_date=add_date,
                icon=icon,
            )

        except Exception:
            # 個別のブックマーク解析エラーは警告レベルで処理
            return None

    def _should_exclude_bookmark(self, bookmark: Bookmark) -> bool:
        """
        ブックマークを除外すべきかどうかをルールベースで判定する

        Args:
            bookmark: 判定対象のブックマーク

        Returns:
            bool: 除外すべき場合True (スクレイピングしない) / False (スクレイピング対象)
        """
        url = bookmark.url

        # 1. 基本的なURLの有効性チェック
        if not self._is_valid_url(url):
            return True

        parsed_url = urlparse(url)
        domain = parsed_url.netloc.lower()
        path = parsed_url.path

        # 2. 【最優先・拒否】正規表現による拒否
        if any(re.search(pattern, url) for pattern in self.regex_deny_patterns):
            return True

        # 3. 【拒否】ドメインによる拒否
        if domain in self.deny_domains:
            return True

        # 4. 【拒否】サブドメインキーワードによる拒否
        if any(domain.startswith(keyword) for keyword in self.deny_subdomains):
            return True

        # 5. 【最優先・許可】ドメインによる許可
        if domain in self.allow_domains:
            return self._is_domain_root_url(url)  # ドメインルートは除外

        # 6. 【パス】パスキーワードによる拒否
        if self.deny_path_keywords and any(keyword in path for keyword in self.deny_path_keywords):
            return True

        # 7. 【パス】パスキーワードによる許可
        if self.allow_path_keywords and any(keyword in path for keyword in self.allow_path_keywords):
            return self._is_domain_root_url(url)  # ドメインルートは除外

        # 8. 【デフォルト】上記ルールに非該当
        # ドメインルートは常に除外
        if self._is_domain_root_url(url):
            return True

        # ここまで到達したURLは、どの許可ルールにも一致しなかったということ。
        # 安全のため、デフォルトでは除外する。
        return True

    def _is_domain_root_url(self, url: str) -> bool:
        """
        URLがドメインのルートかどうかを判定

        Args:
            url: 判定対象のURL

        Returns:
            bool: ドメインルートの場合True
        """
        try:
            parsed = urlparse(url)
            # パスが空、または「/」のみの場合はルートと判定
            path = parsed.path.strip("/")
            is_root = len(path) == 0 and not parsed.query and not parsed.fragment
            return is_root
        except Exception:
            return False

    def _is_valid_url(self, url: str) -> bool:
        """
        URLが有効かどうかを判定

        Args:
            url: 判定対象のURL

        Returns:
            bool: 有効なURLの場合True
        """
        try:
            parsed = urlparse(url)
            # スキームとネットロケーションが存在することを確認
            return bool(parsed.scheme and parsed.netloc)
        except Exception:
            return False

    def _sanitize_filename(self, title: str, folder_path: List[str] = None) -> str:
        """
        タイトルから安全なファイル名を生成（パス長制限を考慮）

        Args:
            title: 元のタイトル
            folder_path: フォルダパス（パス長計算用）

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

        # パス長制限を考慮した動的な長さ制限
        folder_path_str = "/".join(folder_path) if folder_path else ""
        folder_path_len = len(folder_path_str)
        extension_len = 9  # ".markdown" の長さ

        # 安全マージンを含めて計算（Windows制限260文字 - 安全マージン10文字）
        # ベースパス長は推定値を使用（実際のパスが不明なため）
        estimated_base_len = 50  # 推定ベースパス長
        max_total_len = 250
        available_len = max_total_len - estimated_base_len - folder_path_len - extension_len - 2

        # 最小限の長さを保証（20文字以上）
        max_filename_len = max(20, min(100, available_len))

        if len(filename) > max_filename_len:
            filename = filename[:max_filename_len]
            # 切り詰めた場合は末尾に識別子を追加
            if max_filename_len > 10:
                filename = filename[:-3] + "..."

        return filename

    def get_statistics(self, bookmarks: List[Bookmark]) -> Dict[str, int]:
        """
        ブックマーク統計情報を取得

        Args:
            bookmarks: ブックマーク一覧

        Returns:
            Dict[str, int]: 統計情報
                - total_bookmarks: 総ブックマーク数
                - unique_domains: ユニークドメイン数
                - folder_count: フォルダ数
        """
        total_bookmarks = len(bookmarks)
        unique_domains = len(set(urlparse(b.url).netloc for b in bookmarks))
        folder_count = len(set("/".join(b.folder_path) for b in bookmarks if b.folder_path))

        return {
            "total_bookmarks": total_bookmarks,
            "unique_domains": unique_domains,
            "folder_count": folder_count,
        }

    @performance_monitor
    def parse_bookmarks_optimized(
        self,
        html_content: str,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,  # message引数を追加
        batch_size: Optional[int] = None,
        use_parallel: bool = True,
    ) -> List[Bookmark]:
        """
        最適化されたブックマーク解析メソッド

        バッチ処理と並列処理を活用して大量のブックマークを効率的に解析します。

        Args:
            html_content: bookmarks.htmlの内容
            progress_callback: 進捗コールバック関数
            batch_size: バッチサイズ（Noneの場合は自動計算）
            use_parallel: 並列処理を使用するかどうか
            message: メッセージ

        Returns:
            List[Bookmark]: 抽出されたブックマーク一覧

        Raises:
            ValueError: ブックマーク解析に失敗した場合
        """
        try:
            logger.info("最適化されたブックマーク解析を開始")
            soup = BeautifulSoup(html_content, "lxml")
            root_dl = soup.find("dl")
            if not root_dl:
                return []

            all_dt_elements = self._collect_all_dt_elements(root_dl)
            total_elements = len(all_dt_elements)
            logger.info(f"収集されたDT要素数: {total_elements}")

            if progress_callback:
                progress_callback(0, total_elements, "DT要素の収集完了")

            if not all_dt_elements:
                return []

            if batch_size is None:
                batch_size = self.performance_optimizer.get_optimal_batch_size(total_elements)

            # --- ✨修正点: より堅牢な並列処理メソッドを呼び出すように変更 ---
            if use_parallel and total_elements > 100:
                # `_parse_elements_parallel` から `_parse_elements_parallel_enhanced` に変更
                bookmarks = self._parse_elements_parallel_enhanced(all_dt_elements, progress_callback, batch_size)
            else:
                bookmarks = self._parse_elements_batch(all_dt_elements, progress_callback, batch_size)

            logger.info(f"最適化された解析完了: {len(bookmarks)}個のブックマークを抽出")
            if progress_callback:
                progress_callback(total_elements, total_elements, "解析完了")
            return bookmarks

        except Exception as e:
            logger.error(f"最適化されたブックマーク解析エラー: {e}")
            raise ValueError(f"最適化されたブックマーク解析エラー: {str(e)}")

    def _collect_all_dt_elements(self, root_dl) -> List[Dict[str, any]]:
        """
        すべてのDT要素を階層情報と共に収集

        Args:
            root_dl: ルートDLエレメント

        Returns:
            List[Dict[str, any]]: DT要素と階層情報のリスト
        """
        dt_elements = []

        def collect_recursive(dl_element, current_path):
            """再帰的にDT要素を収集"""
            try:
                # このDLの直接の子DTエレメントを取得
                direct_dt_elements = []
                for child in dl_element.children:
                    if hasattr(child, "name"):
                        if child.name == "dt":
                            direct_dt_elements.append(child)
                        elif child.name == "p":
                            # P要素内のDTエレメントも収集
                            all_p_dts = child.find_all("dt")
                            nested_dls_in_p = child.find_all("dl")
                            # TagオブジェクトのIDを格納するsetに変更
                            nested_dt_ids_in_p = set()
                            for nested_dl in nested_dls_in_p:
                                # id() を使って高速な整数IDをsetに追加する
                                nested_dt_ids_in_p.update(id(t) for t in nested_dl.find_all("dt"))

                            # 存在チェックも id() で高速に行う
                            p_dt_elements = [dt for dt in all_p_dts if id(dt) not in nested_dt_ids_in_p]
                            direct_dt_elements.extend(p_dt_elements)

                for dt in direct_dt_elements:
                    # DTの次の兄弟要素をチェック
                    next_sibling = dt.find_next_sibling()

                    if next_sibling and next_sibling.name == "dd":
                        # フォルダ構造の場合
                        h3 = dt.find("h3")
                        if h3:
                            folder_name = h3.get_text(strip=True)
                            new_path = current_path + [folder_name]

                            # DD内のDLを再帰的に処理
                            nested_dl = next_sibling.find("dl")
                            if nested_dl:
                                collect_recursive(nested_dl, new_path)
                    else:
                        # DTの内部構造をチェック
                        h3 = dt.find("h3")
                        internal_dl = dt.find("dl")

                        if h3 and internal_dl:
                            # 内部フォルダ構造
                            folder_name = h3.get_text(strip=True)
                            new_path = current_path + [folder_name]
                            collect_recursive(internal_dl, new_path)
                        else:
                            # 通常のブックマーク
                            a_tag = dt.find("a")
                            if a_tag:
                                dt_elements.append({
                                    "dt_element": dt,
                                    "a_tag": a_tag,
                                    "folder_path": current_path.copy(),
                                })

            except Exception as e:
                logger.warning(f"DT要素収集中にエラー: {e}")

        collect_recursive(root_dl, [])
        return dt_elements

    def _parse_elements_batch(
        self,
        dt_elements: List[Dict[str, any]],
        progress_callback: Optional[Callable[[int, int, str], None]],
        batch_size: int,
    ) -> List[Bookmark]:
        """
        バッチ処理によるDT要素の解析

        Args:
            dt_elements: DT要素のリスト
            progress_callback: 進捗コールバック関数
            batch_size: バッチサイズ

        Returns:
            List[Bookmark]: 解析されたブックマークのリスト
        """
        logger.info(f"バッチ処理開始: {len(dt_elements)}個の要素を{batch_size}個ずつ処理")

        bookmarks = []
        processed_count = 0

        for i in range(0, len(dt_elements), batch_size):
            batch = dt_elements[i : i + batch_size]
            batch_bookmarks = []

            for dt_info in batch:
                try:
                    bookmark = self._extract_bookmark_from_a_tag(dt_info["a_tag"], dt_info["folder_path"])
                    if bookmark and not self._should_exclude_bookmark(bookmark):
                        batch_bookmarks.append(bookmark)
                except Exception as e:
                    logger.debug(f"ブックマーク抽出エラー: {e}")
                    continue

            bookmarks.extend(batch_bookmarks)
            processed_count += len(batch)

            # 進捗報告
            if progress_callback:
                progress_callback(processed_count, len(dt_elements), f"バッチ {i // batch_size + 1} 完了")

            logger.debug(f"バッチ {i // batch_size + 1} 完了: {len(batch_bookmarks)}個のブックマークを抽出")

        return bookmarks

    def _parse_elements_parallel_enhanced(
        self,
        dt_elements: List[Dict[str, any]],
        progress_callback: Optional[Callable[[int, int, str], None]],
        batch_size: int,
        max_retries: int = 3,
    ) -> List[Bookmark]:
        """
        並列処理によるDT要素の解析

        Args:
            dt_elements: DT要素のリスト
            progress_callback: 進捗コールバック関数
            batch_size: バッチサイズ

        Returns:
            List[Bookmark]: 解析されたブックマークのリスト
        """
        worker_count = self.performance_optimizer.get_optimal_worker_count()
        logger.info(f"強化された並列処理開始: {len(dt_elements)}個の要素、{worker_count}ワーカー")

        bookmarks = []
        processed_count = 0
        lock = threading.Lock()

        def update_progress():
            nonlocal processed_count
            with lock:
                processed_count += 1
                if progress_callback and processed_count % (batch_size // 2) == 0:  # 頻繁すぎないように更新
                    progress_callback(processed_count, len(dt_elements), "並列処理中...")

        def process_dt_batch(dt_batch):
            batch_bookmarks = []
            for dt_info in dt_batch:
                try:
                    # --- ✨修正点: スレッドセーフな関数を呼び出す ---
                    bookmark = self._thread_safe_extract_bookmark(dt_info["a_tag"], dt_info["folder_path"])
                    if bookmark and not self._should_exclude_bookmark(bookmark):
                        batch_bookmarks.append(bookmark)
                except Exception as e:
                    logger.debug(f"並列処理中のブックマーク抽出エラー: {e}")
                finally:
                    update_progress()
            return batch_bookmarks

        batches = [dt_elements[i : i + batch_size] for i in range(0, len(dt_elements), batch_size)]

        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            future_to_batch = {executor.submit(process_dt_batch, batch): batch for batch in batches}
            for future in as_completed(future_to_batch):
                try:
                    batch_bookmarks = future.result()
                    bookmarks.extend(batch_bookmarks)
                except Exception as e:
                    logger.error(f"並列処理中にエラー: {e}")

        return bookmarks

    def parse_bookmarks_with_cache_support(
        self,
        html_content: str,
        cache_manager=None,
        progress_callback: Optional[Callable[[int, int], None]] = None,
        force_reparse: bool = False,
    ) -> List[Bookmark]:
        """
        キャッシュサポート付きのブックマーク解析

        Args:
            html_content: bookmarks.htmlの内容
            cache_manager: キャッシュマネージャー（オプション）
            progress_callback: 進捗コールバック関数
            force_reparse: 強制再解析フラグ

        Returns:
            List[Bookmark]: 解析されたブックマークのリスト
        """
        if cache_manager and not force_reparse:
            # キャッシュから読み込みを試行
            file_hash = cache_manager.calculate_file_hash(html_content)
            cached_bookmarks = cache_manager.load_bookmark_cache(file_hash)

            if cached_bookmarks:
                logger.info(f"キャッシュからブックマークを読み込み: {len(cached_bookmarks)}個")
                return cached_bookmarks

        # 新規解析を実行
        bookmarks = self.parse_bookmarks_optimized(html_content, progress_callback=progress_callback)

        # キャッシュに保存
        if cache_manager and bookmarks:
            file_hash = cache_manager.calculate_file_hash(html_content)
            metadata = {
                "bookmark_count": len(bookmarks),
                "file_size": len(html_content),
                "parsing_method": "optimized",
            }
            cache_manager.save_bookmark_cache(file_hash, bookmarks, metadata)
            logger.info(f"ブックマークをキャッシュに保存: {len(bookmarks)}個")

        return bookmarks

    # def _parse_elements_parallel_enhanced(
    #     self,
    #     dt_elements: List[Dict[str, any]],
    #     progress_callback: Optional[Callable[[int, int, str], None]],
    #     batch_size: int,
    #     max_retries: int = 3,
    # ) -> List[Bookmark]:
    #     """
    #     強化された並列処理によるDT要素の解析

    #     エラーハンドリング、リトライ機能、スレッドセーフティを強化した並列処理版

    #     Args:
    #         dt_elements: DT要素のリスト
    #         progress_callback: 進捗コールバック関数
    #         batch_size: バッチサイズ
    #         max_retries: 最大リトライ回数

    #     Returns:
    #         List[Bookmark]: 解析されたブックマークのリスト
    #     """
    #     worker_count = self.performance_optimizer.get_optimal_worker_count()
    #     logger.info(f"強化された並列処理開始: {len(dt_elements)}個の要素、{worker_count}ワーカー")

    #     # スレッドセーフなデータ構造
    #     bookmarks = []
    #     processed_count = 0
    #     error_count = 0
    #     retry_queue = []

    #     # ロックオブジェクト
    #     bookmarks_lock = threading.Lock()
    #     progress_lock = threading.Lock()
    #     error_lock = threading.Lock()

    #     def update_progress(increment=1):
    #         """スレッドセーフな進捗更新"""
    #         nonlocal processed_count
    #         with progress_lock:
    #             processed_count += increment
    #             if progress_callback:
    #                 try:
    #                     progress_callback(processed_count, len(dt_elements))
    #                 except Exception as e:
    #                     logger.warning(f"進捗コールバックエラー: {e}")

    #     def add_bookmark(bookmark):
    #         """スレッドセーフなブックマーク追加"""
    #         with bookmarks_lock:
    #             bookmarks.append(bookmark)

    #     def add_error():
    #         """スレッドセーフなエラーカウント"""
    #         nonlocal error_count
    #         with error_lock:
    #             error_count += 1

    #     def process_dt_batch_with_retry(dt_batch, retry_count=0):
    #         """リトライ機能付きのDT要素バッチ処理"""
    #         batch_bookmarks = []
    #         batch_errors = []

    #         for dt_info in dt_batch:
    #             try:
    #                 # スレッドセーフなブックマーク抽出
    #                 bookmark = self._thread_safe_extract_bookmark(dt_info["a_tag"], dt_info["folder_path"])

    #                 if bookmark and not self._should_exclude_bookmark(bookmark):
    #                     batch_bookmarks.append(bookmark)

    #             except Exception as e:
    #                 batch_errors.append({
    #                     "dt_info": dt_info,
    #                     "error": str(e),
    #                     "retry_count": retry_count,
    #                 })
    #                 logger.debug(f"バッチ処理エラー (試行{retry_count + 1}): {e}")
    #             finally:
    #                 update_progress()

    #         # 成功したブックマークを追加
    #         for bookmark in batch_bookmarks:
    #             add_bookmark(bookmark)

    #         # エラーの処理
    #         for error_info in batch_errors:
    #             add_error()
    #             if retry_count < max_retries:
    #                 # リトライキューに追加
    #                 with error_lock:
    #                     retry_queue.append(error_info)

    #         return len(batch_bookmarks), len(batch_errors)

    #     # バッチに分割
    #     batches = [dt_elements[i : i + batch_size] for i in range(0, len(dt_elements), batch_size)]

    #     # 初回並列処理
    #     logger.info(f"初回並列処理: {len(batches)}個のバッチを処理")

    #     with ThreadPoolExecutor(max_workers=worker_count) as executor:
    #         future_to_batch = {executor.submit(process_dt_batch_with_retry, batch): batch for batch in batches}

    #         for future in as_completed(future_to_batch):
    #             try:
    #                 success_count, error_count_batch = future.result()
    #                 logger.debug(f"バッチ完了: 成功{success_count}個, エラー{error_count_batch}個")
    #             except Exception as e:
    #                 logger.error(f"並列処理中の予期しないエラー: {e}")
    #                 add_error()

    #     # リトライ処理
    #     retry_attempts = 0
    #     while retry_queue and retry_attempts < max_retries:
    #         retry_attempts += 1
    #         logger.info(f"リトライ処理 {retry_attempts}/{max_retries}: {len(retry_queue)}個の要素")

    #         current_retry_queue = retry_queue.copy()
    #         retry_queue.clear()

    #         # リトライバッチを作成
    #         retry_batches = [
    #             [error_info["dt_info"] for error_info in current_retry_queue[i : i + batch_size]]
    #             for i in range(0, len(current_retry_queue), batch_size)
    #         ]

    #         with ThreadPoolExecutor(max_workers=max(1, worker_count // 2)) as executor:
    #             retry_futures = {
    #                 executor.submit(process_dt_batch_with_retry, batch, retry_attempts): batch
    #                 for batch in retry_batches
    #             }

    #             for future in as_completed(retry_futures):
    #                 try:
    #                     future.result()
    #                 except Exception as e:
    #                     logger.error(f"リトライ処理中のエラー: {e}")

    #     # 最終統計
    #     success_rate = (len(bookmarks) / len(dt_elements)) * 100 if dt_elements else 0
    #     logger.info(f"強化された並列処理完了: {len(bookmarks)}個成功, {error_count}個エラー, 成功率{success_rate:.1f}%")

    #     return bookmarks

    def _thread_safe_extract_bookmark(self, a_tag, folder_path: List[str]) -> Optional[Bookmark]:
        """
        スレッドセーフなブックマーク抽出

        Args:
            a_tag: BeautifulSoupのAエレメント
            folder_path: フォルダパス

        Returns:
            Optional[Bookmark]: 抽出されたブックマーク
        """
        try:
            # BeautifulSoupの操作はスレッドセーフではないため、ロックを使用
            with self._lock:
                url = a_tag.get("href", "").strip()
                title = a_tag.get_text(strip=True)

                if not url or not title:
                    return None

                # 日付の解析
                add_date = None
                add_date_str = a_tag.get("add_date")
                if add_date_str:
                    try:
                        add_date = datetime.datetime.fromtimestamp(int(add_date_str))
                    except (ValueError, TypeError):
                        pass

                # アイコン情報の取得
                icon = a_tag.get("icon")

            # Bookmarkオブジェクトの作成（ロック外で実行）
            return Bookmark(
                title=title,
                url=url,
                folder_path=folder_path.copy(),  # リストのコピーを作成
                add_date=add_date,
                icon=icon,
            )

        except Exception as e:
            logger.debug(f"スレッドセーフなブックマーク抽出エラー: {e}")
            return None

    def get_parsing_performance_stats(self) -> Dict[str, any]:
        """
        解析パフォーマンスの統計情報を取得

        Returns:
            Dict[str, any]: パフォーマンス統計
        """
        try:
            memory_info = self.performance_optimizer.monitor_memory_usage()
            optimal_batch_size = self.performance_optimizer.get_optimal_batch_size(1000)
            optimal_workers = self.performance_optimizer.get_optimal_worker_count()

            return {
                "memory_usage": memory_info,
                "optimal_batch_size": optimal_batch_size,
                "optimal_worker_count": optimal_workers,
                "excluded_domains_count": len(self.excluded_domains),
                "excluded_urls_count": len(self.excluded_urls),
            }
        except Exception as e:
            logger.error(f"パフォーマンス統計取得エラー: {e}")
            return {}

    def benchmark_parsing_methods(self, html_content: str, iterations: int = 3) -> Dict[str, Dict[str, float]]:
        """
        異なる解析メソッドのベンチマークを実行

        Args:
            html_content: テスト用のHTML内容
            iterations: 実行回数

        Returns:
            Dict[str, Dict[str, float]]: ベンチマーク結果
        """
        import time

        results = {
            "original": {"times": [], "avg_time": 0, "bookmark_count": 0},
            "optimized": {"times": [], "avg_time": 0, "bookmark_count": 0},
            "parallel": {"times": [], "avg_time": 0, "bookmark_count": 0},
        }

        logger.info(f"解析メソッドベンチマーク開始: {iterations}回実行")

        for i in range(iterations):
            logger.info(f"ベンチマーク実行 {i + 1}/{iterations}")

            # オリジナルメソッド
            try:
                start_time = time.time()
                bookmarks_original = self.parse_bookmarks(html_content)
                end_time = time.time()

                results["original"]["times"].append(end_time - start_time)
                results["original"]["bookmark_count"] = len(bookmarks_original)
            except Exception as e:
                logger.error(f"オリジナルメソッドベンチマークエラー: {e}")

            # 最適化メソッド（並列処理なし）
            try:
                start_time = time.time()
                bookmarks_optimized = self.parse_bookmarks_optimized(html_content, use_parallel=False)
                end_time = time.time()

                results["optimized"]["times"].append(end_time - start_time)
                results["optimized"]["bookmark_count"] = len(bookmarks_optimized)
            except Exception as e:
                logger.error(f"最適化メソッドベンチマークエラー: {e}")

            # 並列処理メソッド
            try:
                start_time = time.time()
                bookmarks_parallel = self.parse_bookmarks_optimized(html_content, use_parallel=True)
                end_time = time.time()

                results["parallel"]["times"].append(end_time - start_time)
                results["parallel"]["bookmark_count"] = len(bookmarks_parallel)
            except Exception as e:
                logger.error(f"並列処理メソッドベンチマークエラー: {e}")

        # 平均時間を計算
        for method, data in results.items():
            if data["times"]:
                data["avg_time"] = sum(data["times"]) / len(data["times"])
                data["min_time"] = min(data["times"])
                data["max_time"] = max(data["times"])

        logger.info("ベンチマーク結果:")
        for method, data in results.items():
            if data["times"]:
                logger.info(
                    f"  {method}: 平均{data['avg_time']:.2f}秒, "
                    f"最小{data['min_time']:.2f}秒, 最大{data['max_time']:.2f}秒, "
                    f"ブックマーク数{data['bookmark_count']}"
                )

        return results
