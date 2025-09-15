"""
ブックマーク解析モジュール

このモジュールは、ブラウザのbookmarks.htmlファイルを解析して
ブックマーク情報を抽出する機能を提供します。
"""

import datetime
import logging
import re
from typing import Dict, List
from urllib.parse import urlparse

import yaml
from bs4 import BeautifulSoup

from utils.models import Bookmark

# from utils.performance_utils import PerformanceOptimizer, performance_monitor # 不要なので削除

logger = logging.getLogger(__name__)


class BookmarkParser:
    """
    Netscape Bookmark File Format のHTMLファイルを
    構造に特化した方法で高速に解析するクラス。
    """

    def __init__(self, rules_path: str = "filter_rules.yml"):
        """
        BookmarkParserを初期化
        """
        # self.performance_optimizer = PerformanceOptimizer() # 不要なので削除
        self.rules_path = rules_path
        self._load_filter_rules()

    def _load_filter_rules(self):
        """フィルタリングルールをYAMLファイルから読み込む"""
        try:
            with open(self.rules_path, "r", encoding="utf-8") as f:
                rules = yaml.safe_load(f) or {}

            self.allow_rules = rules.get("allow", {})
            self.deny_rules = rules.get("deny", {})
            self.regex_deny_rules = rules.get("regex_deny", {})
            self.allow_domains = set(self.allow_rules.get("domains", []))
            self.deny_domains = set(self.deny_rules.get("domains", []))
            self.deny_subdomains = self.deny_rules.get("subdomain_keywords", [])
            self.allow_path_keywords = self.allow_rules.get("path_keywords", [])
            self.deny_path_keywords = self.deny_rules.get("path_keywords", [])

            # 正規表現は事前にコンパイルして高速化
            self.regex_deny_patterns = [re.compile(p) for p in rules.get("regex_deny", {}).get("patterns", [])]

            logger.info(f"フィルタリングルールを '{self.rules_path}' から読み込みました。")

        except FileNotFoundError:
            logger.warning(f"ルールファイル '{self.rules_path}' が見つかりません。基本的なフィルタリングのみ行います。")
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

    def parse(self, html_content: str) -> List[Bookmark]:
        """
        ブックマークHTMLコンテンツを解析し、フィルタリング後のブックマークのリストを返す。
        """
        logger.info("構造特化型パーサーによる解析を開始します。")
        try:
            soup = BeautifulSoup(html_content, "lxml")
            root_dl = soup.find("h1").find_next_sibling("dl")

            if not root_dl:
                logger.warning("ルートDLが見つかりません。最初のDLから解析します。")
                root_dl = soup.find("dl")
                if not root_dl:
                    logger.error("解析対象のDL要素がありません。")
                    return []

            all_bookmarks = []
            self._parse_dl_recursively(root_dl, [], all_bookmarks)

            logger.info(f"抽出完了: {len(all_bookmarks)}件のブックマークを抽出しました。フィルタリングを開始します。")

            # ★★★ 抽出後にフィルタリングを実行 ★★★
            filtered_bookmarks = [b for b in all_bookmarks if not self._should_exclude_bookmark(b)]

            logger.info(f"フィルタリング完了: {len(filtered_bookmarks)}件のブックマークが残りました。")
            return filtered_bookmarks

        except Exception as e:
            logger.error(f"ブックマーク解析中にエラーが発生: {e}", exc_info=True)
            raise ValueError(f"ブックマーク解析エラー: {str(e)}")

    def _parse_dl_recursively(self, dl_element, current_path: List[str], bookmarks: List[Bookmark]):
        """
        DL要素を再帰的にたどり、フォルダ構造を維持しながらブックマークを抽出する。
        """
        for child in dl_element.children:
            if not hasattr(child, "name") or child.name != "dt":
                continue

            dt = child
            h3_tag = dt.find("h3", recursive=False)

            if h3_tag:
                folder_name = h3_tag.get_text(strip=True)
                new_path = current_path + [folder_name]
                nested_dl = dt.find_next_sibling("dl")
                if nested_dl:
                    self._parse_dl_recursively(nested_dl, new_path, bookmarks)
            else:
                a_tag = dt.find("a", recursive=False)
                if a_tag and a_tag.has_attr("href"):
                    try:
                        url = a_tag["href"].strip()
                        title = a_tag.get_text(strip=True)
                        if not url or not title:
                            continue

                        add_date = None
                        add_date_str = a_tag.get("add_date")
                        if add_date_str:
                            add_date = datetime.datetime.fromtimestamp(int(add_date_str))

                        bookmarks.append(
                            Bookmark(
                                title=title,
                                url=url,
                                folder_path=current_path,
                                add_date=add_date,
                                icon=a_tag.get("icon"),
                            )
                        )
                    except Exception as e:
                        logger.warning(f"個別ブックマークの解析失敗: {a_tag.get_text(strip=True)} - {e}")
                        continue

    def _should_exclude_bookmark(self, bookmark: Bookmark) -> bool:
        """ブックマークを除外すべきかルールベースで判定する"""
        url = bookmark.url
        if not self._is_valid_url(url):
            return True

        parsed_url = urlparse(url)
        domain = parsed_url.netloc.lower()
        path = parsed_url.path

        if any(pattern.search(url) for pattern in self.regex_deny_patterns):
            return True
        if domain in self.deny_domains:
            return True
        if any(domain.startswith(keyword) for keyword in self.deny_subdomains):
            return True
        if domain in self.allow_domains:
            return self._is_domain_root_url(url)
        if self.deny_path_keywords and any(keyword in path for keyword in self.deny_path_keywords):
            return True
        if self.allow_path_keywords and any(keyword in path for keyword in self.allow_path_keywords):
            return self._is_domain_root_url(url)
        if self._is_domain_root_url(url):
            return True

        return True  # Default Deny

    def _is_valid_url(self, url: str) -> bool:
        """URLが有効かどうかを判定"""
        try:
            parsed = urlparse(url)
            return bool(parsed.scheme and parsed.netloc)
        except Exception:
            return False

    def _is_domain_root_url(self, url: str) -> bool:
        """URLがドメインのルートかどうかを判定"""
        try:
            parsed = urlparse(url)
            path = parsed.path.strip("/")
            return len(path) == 0 and not parsed.query and not parsed.fragment
        except Exception:
            return False

    def get_statistics(self, bookmarks: List[Bookmark]) -> Dict[str, int]:
        """ブックマーク統計情報を取得"""
        total_bookmarks = len(bookmarks)
        unique_domains = len(set(urlparse(b.url).netloc for b in bookmarks))
        folder_count = len(set("/".join(b.folder_path) for b in bookmarks if b.folder_path))
        return {
            "total_bookmarks": total_bookmarks,
            "unique_domains": unique_domains,
            "folder_count": folder_count,
        }
