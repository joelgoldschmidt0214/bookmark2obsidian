"""
Webスクレイピングモジュール

このモジュールは、Webページの取得、robots.txt確認、レート制限、
記事本文抽出などのWebスクレイピング機能を提供します。
"""

import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser
import time
import logging
import re
from typing import Optional, Dict, List, Any

# ロガーの取得
logger = logging.getLogger(__name__)


class WebScraper:
    """
    Webページ取得・解析クラス

    robots.txt確認、レート制限、記事本文抽出機能を提供します。
    複数のアルゴリズムを使用してWebページから高品質なコンテンツを抽出し、
    適切なレート制限とエラーハンドリングを実装しています。
    """

    def __init__(self):
        """
        WebScraperを初期化

        セッション設定、レート制限、タイムアウト設定などを初期化します。
        適切なUser-Agentを設定し、ドメインごとのアクセス管理を準備します。
        """
        self.domain_last_access = {}  # ドメインごとの最終アクセス時刻
        self.rate_limit_delay = 3  # デフォルトの待ち時間（秒）
        self.timeout = 10  # リクエストタイムアウト（秒）
        self.user_agent = "Mozilla/5.0 (compatible; BookmarkToObsidian/1.0; +https://github.com/user/bookmark-to-obsidian)"

        # セッション設定
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": self.user_agent,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "ja,en-US;q=0.7,en;q=0.3",
                "Accept-Encoding": "gzip, deflate",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
            }
        )

        logger.info(f"🌐 WebScraper初期化完了 (User-Agent: {self.user_agent})")

    def fetch_page_content(self, url: str) -> Optional[str]:
        """
        エラーハンドリングを強化したページ取得機能

        指定されたURLからHTMLコンテンツを取得します。
        robots.txt確認、レート制限、SSL証明書検証、適切なエラーハンドリングを実装しています。

        Args:
            url: 取得対象のURL

        Returns:
            Optional[str]: 取得されたHTMLコンテンツ（失敗時はNone）

        Raises:
            requests.exceptions.ConnectionError: ネットワーク接続エラー
            requests.exceptions.Timeout: タイムアウトエラー
            requests.exceptions.HTTPError: HTTPエラー
            requests.exceptions.SSLError: SSL証明書エラー
            ValueError: 無効なURL形式
        """
        try:
            # URLの解析
            parsed_url = urlparse(url)
            domain = parsed_url.netloc.lower()

            logger.debug(f"🌐 ページ取得開始: {url}")

            # robots.txtチェック
            if not self.check_robots_txt(domain):
                logger.info(f"🚫 robots.txt拒否によりスキップ: {url}")
                return None

            # レート制限の適用
            self.apply_rate_limiting(domain)

            # HTTPリクエストの実行（エラーハンドリング強化）
            try:
                response = self.session.get(
                    url,
                    timeout=self.timeout,
                    allow_redirects=True,
                    verify=True,  # SSL証明書検証を有効化
                )

                # ステータスコードの確認
                response.raise_for_status()

            except requests.exceptions.Timeout:
                logger.warning(f"⏰ タイムアウト: {url} (timeout={self.timeout}s)")
                raise requests.exceptions.Timeout(
                    f"ページ取得がタイムアウトしました: {url}"
                )

            except requests.exceptions.SSLError:
                logger.warning(f"🔒 SSL証明書エラー: {url}")
                raise requests.exceptions.SSLError(
                    f"SSL証明書の検証に失敗しました: {url}"
                )

            except requests.exceptions.ConnectionError:
                logger.warning(f"🔌 接続エラー: {url}")
                raise requests.exceptions.ConnectionError(
                    f"ネットワーク接続に失敗しました: {url}"
                )

            except requests.exceptions.HTTPError as e:
                status_code = e.response.status_code if e.response else "不明"
                logger.warning(
                    f"🚫 HTTPエラー: {url} - ステータスコード: {status_code}"
                )

                # 特定のHTTPエラーに対する詳細メッセージ
                if status_code == 403:
                    raise requests.exceptions.HTTPError(
                        f"アクセスが拒否されました (403): {url}"
                    )
                elif status_code == 404:
                    raise requests.exceptions.HTTPError(
                        f"ページが見つかりません (404): {url}"
                    )
                elif status_code == 429:
                    raise requests.exceptions.HTTPError(
                        f"リクエスト制限に達しました (429): {url}"
                    )
                elif status_code >= 500:
                    raise requests.exceptions.HTTPError(
                        f"サーバーエラー ({status_code}): {url}"
                    )
                else:
                    raise requests.exceptions.HTTPError(
                        f"HTTPエラー ({status_code}): {url}"
                    )

            # 文字エンコーディングの自動検出
            if response.encoding is None:
                response.encoding = response.apparent_encoding

            # HTMLコンテンツを取得
            html_content = response.text

            # コンテンツサイズの検証
            if len(html_content) < 100:
                logger.warning(
                    f"⚠️ コンテンツサイズが小さすぎます: {url} (サイズ: {len(html_content)} 文字)"
                )
                return None

            logger.debug(
                f"✅ ページ取得成功: {url} (サイズ: {len(html_content):,} 文字)"
            )

            # 最終アクセス時刻を更新
            self.domain_last_access[domain] = time.time()

            return html_content

        except (
            requests.exceptions.Timeout,
            requests.exceptions.ConnectionError,
            requests.exceptions.HTTPError,
            requests.exceptions.SSLError,
        ):
            # 既知のネットワークエラーは再発生させる
            raise

        except requests.exceptions.MissingSchema:
            logger.warning(f"⚠️ 無効なURL形式: {url}")
            raise ValueError(f"無効なURL形式です: {url}")

        except requests.exceptions.InvalidURL:
            logger.warning(f"⚠️ 無効なURL: {url}")
            raise ValueError(f"無効なURLです: {url}")

        except Exception as e:
            logger.error(f"❌ 予期しないページ取得エラー: {url} - {str(e)}")
            raise Exception(f"予期しないエラーが発生しました: {str(e)}")

    def extract_article_content(self, html: str, url: str = "") -> Optional[Dict]:
        """
        HTMLから記事本文とメタデータを抽出（高度な抽出アルゴリズム）

        複数のアルゴリズムを使用してWebページから記事本文を抽出します。
        セマンティックタグ、コンテンツ密度、一般的なセレクタなどを試行し、
        最も品質の高いコンテンツを選択します。

        Args:
            html: HTMLコンテンツ
            url: 元のURL（ログ用、デフォルト: ""）

        Returns:
            Optional[Dict]: 抽出された記事データ（失敗時はNone）
                - title: 記事タイトル
                - content: 記事本文
                - tags: タグ一覧
                - metadata: メタデータ
                - quality_score: 品質スコア（0.0-1.0）
                - extraction_method: 使用した抽出方法
        """
        try:
            soup = BeautifulSoup(html, "html.parser")

            # 記事データの初期化
            article_data = {
                "title": "",
                "content": "",
                "tags": [],
                "metadata": {},
                "quality_score": 0.0,
                "extraction_method": "",
            }

            # 不要な要素を事前に除去
            self._remove_unwanted_elements(soup)

            # タイトルの抽出（複数の方法を試行）
            article_data["title"] = self._extract_title(soup, url)

            # メタデータの抽出
            article_data["metadata"] = self._extract_metadata(soup)

            # タグ情報の抽出
            article_data["tags"] = self._extract_tags(soup, article_data["metadata"])

            # 記事本文の抽出（複数のアルゴリズムを試行）
            content_result = self._extract_main_content(soup, url)

            if content_result:
                article_data["content"] = content_result["content"]
                article_data["quality_score"] = content_result["quality_score"]
                article_data["extraction_method"] = content_result["method"]

                # コンテンツ品質の検証
                if self._validate_content_quality(article_data, url):
                    logger.debug(
                        f"✅ 記事本文抽出成功: {url} (文字数: {len(article_data['content'])}, 品質スコア: {article_data['quality_score']:.2f}, 方法: {article_data['extraction_method']})"
                    )
                    return article_data
                else:
                    logger.warning(f"⚠️ コンテンツ品質が基準を満たしません: {url}")
                    return None
            else:
                logger.warning(f"⚠️ 記事本文が見つかりません: {url}")
                return None

        except Exception as e:
            logger.error(f"❌ 記事本文抽出エラー: {url} - {str(e)}")
            return None

    def check_robots_txt(self, domain: str) -> bool:
        """
        指定されたドメインのrobots.txtを確認し、スクレイピングが許可されているかチェック

        Args:
            domain: 確認対象のドメイン

        Returns:
            bool: スクレイピングが許可されている場合True
        """
        try:
            robots_url = f"https://{domain}/robots.txt"
            logger.debug(f"🤖 robots.txt確認: {robots_url}")

            # RobotFileParserを使用してrobots.txtを解析
            rp = RobotFileParser()
            rp.set_url(robots_url)

            # robots.txtを読み込み（タイムアウト付き）
            try:
                rp.read()

                # User-Agentに対してアクセス許可をチェック
                # 一般的なクローラー名とカスタムUser-Agentの両方をチェック
                user_agents_to_check = [
                    self.user_agent,
                    "*",  # 全てのUser-Agent
                    "Mozilla/5.0",  # 一般的なブラウザ
                ]

                for ua in user_agents_to_check:
                    if rp.can_fetch(ua, "/"):
                        logger.debug(f"✅ robots.txt許可: {domain} (User-Agent: {ua})")
                        return True

                logger.info(f"🚫 robots.txt拒否: {domain}")
                return False

            except Exception as e:
                # robots.txtが存在しない、またはアクセスできない場合は許可とみなす
                logger.debug(
                    f"⚠️ robots.txt読み込みエラー（許可として処理）: {domain} - {str(e)}"
                )
                return True

        except Exception as e:
            # エラーが発生した場合は安全側に倒して許可とみなす
            logger.debug(
                f"⚠️ robots.txtチェックエラー（許可として処理）: {domain} - {str(e)}"
            )
            return True

    def apply_rate_limiting(self, domain: str) -> None:
        """
        指定されたドメインに対してレート制限を適用

        Args:
            domain: 対象ドメイン
        """
        current_time = time.time()

        if domain in self.domain_last_access:
            time_since_last_access = current_time - self.domain_last_access[domain]

            if time_since_last_access < self.rate_limit_delay:
                sleep_time = self.rate_limit_delay - time_since_last_access
                logger.debug(f"⏳ レート制限待機: {domain} ({sleep_time:.1f}秒)")
                time.sleep(sleep_time)

        # 最終アクセス時刻を更新
        self.domain_last_access[domain] = time.time()

    def group_urls_by_domain(self, urls: List[str]) -> Dict[str, List[str]]:
        """
        URLリストをドメインごとにグループ化

        Args:
            urls: URL一覧

        Returns:
            Dict[str, List[str]]: ドメインをキーとしたURL一覧
        """
        domain_groups = {}

        for url in urls:
            try:
                parsed_url = urlparse(url)
                domain = parsed_url.netloc.lower()

                if domain not in domain_groups:
                    domain_groups[domain] = []

                domain_groups[domain].append(url)

            except Exception as e:
                logger.warning(f"⚠️ URL解析エラー: {url} - {str(e)}")
                continue

        logger.info(f"🌐 ドメイングループ化完了: {len(domain_groups)}個のドメイン")
        for domain, domain_urls in domain_groups.items():
            logger.debug(f"  📍 {domain}: {len(domain_urls)}個のURL")

        return domain_groups

    def set_rate_limit_delay(self, delay: float) -> None:
        """
        レート制限の待ち時間を設定

        Args:
            delay: 待ち時間（秒）
        """
        self.rate_limit_delay = max(1.0, delay)  # 最小1秒
        logger.info(f"⏳ レート制限設定: {self.rate_limit_delay}秒")

    def set_timeout(self, timeout: int) -> None:
        """
        リクエストタイムアウトを設定

        Args:
            timeout: タイムアウト時間（秒）
        """
        self.timeout = max(5, timeout)  # 最小5秒
        logger.info(f"⏰ タイムアウト設定: {self.timeout}秒")

    def get_statistics(self) -> Dict[str, Any]:
        """
        WebScraper統計情報を取得

        Returns:
            Dict[str, Any]: 統計情報
                - domains_accessed: アクセスしたドメイン数
                - rate_limit_delay: レート制限待ち時間
                - timeout: タイムアウト時間
                - user_agent: 使用中のUser-Agent
        """
        return {
            "domains_accessed": len(self.domain_last_access),
            "rate_limit_delay": self.rate_limit_delay,
            "timeout": self.timeout,
            "user_agent": self.user_agent,
        }

    # プライベートメソッド群

    def _remove_unwanted_elements(self, soup: BeautifulSoup) -> None:
        """
        不要な要素を除去（広告、ナビゲーション、スクリプトなど）

        Args:
            soup: BeautifulSoupオブジェクト
        """
        # 除去対象のセレクタ
        unwanted_selectors = [
            # スクリプトとスタイル
            "script",
            "style",
            "noscript",
            # ナビゲーション要素
            "nav",
            "header",
            "footer",
            "aside",
            ".navigation",
            ".navbar",
            ".nav-menu",
            ".menu",
            ".breadcrumb",
            ".breadcrumbs",
            # 広告関連
            ".advertisement",
            ".ads",
            ".ad",
            ".advert",
            ".google-ads",
            ".adsense",
            ".ad-container",
            '[id*="ad"]',
            '[class*="ad-"]',
            '[class*="ads-"]',
            # ソーシャル・共有ボタン
            ".share-buttons",
            ".social-share",
            ".social-buttons",
            ".share",
            ".sharing",
            ".social-media",
            # コメント・関連記事
            ".comments",
            ".comment-section",
            ".disqus",
            ".related-posts",
            ".related-articles",
            ".recommendations",
            # サイドバー・ウィジェット
            ".sidebar",
            ".widget",
            ".widgets",
            # その他の不要要素
            ".popup",
            ".modal",
            ".overlay",
            ".newsletter",
            ".subscription",
            ".cookie-notice",
            ".cookie-banner",
            ".back-to-top",
            ".scroll-to-top",
        ]

        for selector in unwanted_selectors:
            for element in soup.select(selector):
                element.decompose()

    def _extract_title(self, soup: BeautifulSoup, url: str) -> str:
        """
        ページタイトルを抽出（複数の方法を試行）

        Args:
            soup: BeautifulSoupオブジェクト
            url: 元のURL

        Returns:
            str: 抽出されたタイトル
        """
        # タイトル抽出の優先順位
        title_selectors = [
            "h1",  # メインタイトル
            "title",  # HTMLタイトル
            '[property="og:title"]',  # Open Graphタイトル
            ".title",
            ".post-title",
            ".article-title",
            ".entry-title",
            ".page-title",
        ]

        for selector in title_selectors:
            elements = soup.select(selector)
            for element in elements:
                if selector == '[property="og:title"]':
                    title = element.get("content", "").strip()
                else:
                    title = element.get_text(strip=True)

                if title and len(title) > 5:  # 最小文字数チェック
                    # タイトルのクリーニング
                    title = re.sub(r"\s+", " ", title)  # 連続する空白を単一に
                    title = title.replace("\n", " ").replace("\t", " ")
                    return title[:200]  # 最大200文字に制限

        # タイトルが見つからない場合はURLから生成
        parsed_url = urlparse(url)
        return f"記事 - {parsed_url.netloc}"

    def _extract_metadata(self, soup: BeautifulSoup) -> Dict[str, str]:
        """
        メタデータを抽出

        Args:
            soup: BeautifulSoupオブジェクト

        Returns:
            Dict[str, str]: 抽出されたメタデータ
        """
        metadata = {}

        # メタタグから情報を抽出
        meta_tags = soup.find_all("meta")
        for meta in meta_tags:
            name = meta.get("name", "").lower()
            property_attr = meta.get("property", "").lower()
            content = meta.get("content", "").strip()

            if content:
                # 標準的なメタタグ
                if name in ["description", "keywords", "author", "robots", "viewport"]:
                    metadata[name] = content

                # Open Graphタグ
                elif property_attr.startswith("og:"):
                    metadata[property_attr] = content

                # Articleタグ
                elif property_attr.startswith("article:"):
                    metadata[property_attr] = content

                # Twitterカード
                elif name.startswith("twitter:"):
                    metadata[name] = content

        # 構造化データ（JSON-LD）の抽出
        json_ld_scripts = soup.find_all("script", type="application/ld+json")
        for script in json_ld_scripts:
            try:
                import json

                data = json.loads(script.string)
                if isinstance(data, dict):
                    if data.get("@type") in ["Article", "BlogPosting", "NewsArticle"]:
                        if "author" in data:
                            metadata["structured_author"] = str(data["author"])
                        if "datePublished" in data:
                            metadata["structured_date"] = data["datePublished"]
                        if "description" in data:
                            metadata["structured_description"] = data["description"]
            except (json.JSONDecodeError, AttributeError):
                continue

        return metadata

    def _extract_tags(self, soup: BeautifulSoup, metadata: Dict[str, str]) -> List[str]:
        """
        タグ情報を抽出

        Args:
            soup: BeautifulSoupオブジェクト
            metadata: メタデータ

        Returns:
            List[str]: 抽出されたタグ一覧
        """
        tags = set()

        # メタデータのキーワードから抽出
        keywords = metadata.get("keywords", "")
        if keywords:
            # カンマ区切りのキーワードを分割
            keyword_list = [kw.strip() for kw in keywords.split(",") if kw.strip()]
            tags.update(keyword_list)

        # HTMLからタグ要素を抽出
        tag_selectors = [
            ".tags a",
            ".tag a",
            ".categories a",
            ".category a",
            ".labels a",
            ".label a",
            ".topics a",
            ".topic a",
            '[rel="tag"]',
            ".post-tags a",
            ".entry-tags a",
        ]

        for selector in tag_selectors:
            elements = soup.select(selector)
            for element in elements:
                tag_text = element.get_text(strip=True)
                if tag_text and len(tag_text) <= 50:  # 最大50文字のタグのみ
                    # タグのクリーニング
                    tag_text = re.sub(r"[^\w\s\-_]", "", tag_text)  # 特殊文字を除去
                    tag_text = re.sub(
                        r"\s+", "-", tag_text.strip()
                    )  # スペースをハイフンに
                    if tag_text:
                        tags.add(tag_text)

        # タグ数を制限（最大20個）
        return list(tags)[:20]

    def _extract_main_content(self, soup: BeautifulSoup, url: str) -> Optional[Dict]:
        """
        メインコンテンツを抽出（複数のアルゴリズムを試行）

        Args:
            soup: BeautifulSoupオブジェクト
            url: 元のURL

        Returns:
            Optional[Dict]: 抽出結果（content, quality_score, method）
        """
        extraction_methods = [
            ("semantic_tags", self._extract_by_semantic_tags),
            ("content_density", self._extract_by_content_density),
            ("common_selectors", self._extract_by_common_selectors),
            ("body_fallback", self._extract_by_body_fallback),
        ]

        best_result = None
        best_score = 0.0

        for method_name, method_func in extraction_methods:
            try:
                result = method_func(soup)
                if result and result["quality_score"] > best_score:
                    best_result = result
                    best_score = result["quality_score"]
                    best_result["method"] = method_name

                    # 十分に高品質なコンテンツが見つかった場合は早期終了
                    if best_score >= 0.8:
                        break

            except Exception as e:
                logger.debug(f"抽出方法 {method_name} でエラー: {str(e)}")
                continue

        return best_result

    def _extract_by_semantic_tags(self, soup: BeautifulSoup) -> Optional[Dict]:
        """セマンティックタグを使用した抽出"""
        semantic_selectors = ["article", "main", '[role="main"]']

        for selector in semantic_selectors:
            elements = soup.select(selector)
            if elements:
                # 最も長いコンテンツを選択
                best_element = max(elements, key=lambda x: len(x.get_text()))
                content = self._clean_content(best_element.get_text())

                if len(content) > 50:  # 閾値を下げる
                    return {
                        "content": content,
                        "quality_score": 0.9,  # セマンティックタグは高品質
                        "method": "semantic_tags",
                    }

        return None

    def _extract_by_content_density(self, soup: BeautifulSoup) -> Optional[Dict]:
        """コンテンツ密度による抽出"""
        # 各要素のコンテンツ密度を計算
        candidates = []

        for element in soup.find_all(["div", "section", "article"]):
            text = element.get_text(strip=True)
            if len(text) < 50:  # 閾値を下げる
                continue

            # リンク密度を計算（リンクテキスト / 全テキスト）
            link_text = "".join([a.get_text() for a in element.find_all("a")])
            link_density = len(link_text) / len(text) if text else 1.0

            # 段落数を計算
            paragraphs = len(element.find_all("p"))

            # 品質スコアを計算
            quality_score = (
                min(len(text) / 500, 1.0) * 0.4  # 文字数（最大500文字で1.0）
                + (1.0 - link_density) * 0.4  # リンク密度が低いほど高スコア
                + min(paragraphs / 3, 1.0) * 0.2  # 段落数（最大3段落で1.0）
            )

            candidates.append(
                {"element": element, "text": text, "quality_score": quality_score}
            )

        if candidates:
            # 最高スコアの要素を選択
            best_candidate = max(candidates, key=lambda x: x["quality_score"])
            content = self._clean_content(best_candidate["text"])

            return {
                "content": content,
                "quality_score": best_candidate["quality_score"],
                "method": "content_density",
            }

        return None

    def _extract_by_common_selectors(self, soup: BeautifulSoup) -> Optional[Dict]:
        """一般的なセレクタによる抽出"""
        common_selectors = [
            ".content",
            ".post-content",
            ".entry-content",
            ".article-content",
            "#content",
            "#main-content",
            ".main-content",
            ".post-body",
            ".entry-body",
            ".article-body",
            ".content-body",
        ]

        for selector in common_selectors:
            elements = soup.select(selector)
            if elements:
                best_element = max(elements, key=lambda x: len(x.get_text()))
                content = self._clean_content(best_element.get_text())

                if len(content) > 100:
                    return {
                        "content": content,
                        "quality_score": 0.7,  # 中程度の品質
                        "method": "common_selectors",
                    }

        return None

    def _extract_by_body_fallback(self, soup: BeautifulSoup) -> Optional[Dict]:
        """bodyタグからのフォールバック抽出"""
        body = soup.find("body")
        if body:
            content = self._clean_content(body.get_text())

            if len(content) > 200:
                return {
                    "content": content,
                    "quality_score": 0.3,  # 低品質（フォールバック）
                    "method": "body_fallback",
                }

        return None

    def _clean_content(self, text: str) -> str:
        """
        テキストコンテンツをクリーニング

        Args:
            text: 元のテキスト

        Returns:
            str: クリーニング済みテキスト
        """
        if not text:
            return ""

        # 連続する空白を単一のスペースに
        text = re.sub(r"[ \t]+", " ", text)

        # 行ごとに処理
        lines = []
        for line in text.split("\n"):
            line = line.strip()
            if line and len(line) > 3:  # 短すぎる行は除外
                lines.append(line)

        # 段落として結合
        content = "\n\n".join(lines)

        # 最大文字数制限（10,000文字）
        if len(content) > 10000:
            content = content[:10000] + "..."

        return content

    def _validate_content_quality(self, article_data: Dict, url: str) -> bool:
        """
        コンテンツ品質を検証

        Args:
            article_data: 記事データ
            url: 元のURL

        Returns:
            bool: 品質基準を満たす場合True
        """
        content = article_data.get("content", "")
        quality_score = article_data.get("quality_score", 0.0)

        # 基本的な品質チェック
        checks = {
            "min_length": len(content) >= 100,  # 最小100文字
            "max_length": len(content) <= 50000,  # 最大50,000文字
            "quality_score": quality_score >= 0.3,  # 最小品質スコア
            "has_title": bool(article_data.get("title", "").strip()),  # タイトル存在
            "reasonable_structure": content.count("\n") >= 2,  # 最低限の構造
        }

        # すべてのチェックをパス
        passed_checks = sum(checks.values())
        total_checks = len(checks)

        success_rate = passed_checks / total_checks

        if success_rate < 0.8:  # 80%以上のチェックをパスする必要
            logger.debug(f"品質チェック失敗: {url} - {checks}")
            return False

        # 特定のパターンをチェック（エラーページなど）
        error_patterns = [
            r"404.*not found",
            r"page not found",
            r"access denied",
            r"forbidden",
            r"error occurred",
        ]

        content_lower = content.lower()
        for pattern in error_patterns:
            if re.search(pattern, content_lower):
                logger.debug(f"エラーページパターン検出: {url} - {pattern}")
                return False

        return True
