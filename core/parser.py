"""
ブックマーク解析モジュール

BeautifulSoupで構築した木構造を、責務を分離した関数群でたどる
ハイブリッド方式のパーサー。
"""

import datetime
import html
import logging
import re
from typing import Dict, List
from urllib.parse import urlparse

import yaml
from bs4 import BeautifulSoup, Tag

from utils.models import Bookmark

logger = logging.getLogger(__name__)


class BookmarkParser:
    def __init__(self, rules_path: str = "filter_rules.yml"):
        self.rules_path = rules_path
        self._load_filter_rules()

    def _load_filter_rules(self):
        try:
            with open(self.rules_path, "r", encoding="utf-8") as f:
                rules = yaml.safe_load(f) or {}
            self.allow_rules, self.deny_rules, self.regex_deny_rules = (
                rules.get("allow", {}),
                rules.get("deny", {}),
                rules.get("regex_deny", {}),
            )
            self.allow_domains, self.deny_domains = (
                set(self.allow_rules.get("domains", [])),
                set(self.deny_rules.get("domains", [])),
            )
            self.deny_subdomains = self.deny_rules.get("subdomain_keywords", [])
            self.allow_path_keywords, self.deny_path_keywords = (
                self.allow_rules.get("path_keywords", []),
                self.deny_rules.get("path_keywords", []),
            )
            self.regex_deny_patterns = [re.compile(p) for p in self.regex_deny_rules.get("patterns", [])]
            logger.info(f"フィルタリングルールを '{self.rules_path}' から読み込みました。")
        except FileNotFoundError:
            logger.warning(f"ルールファイル '{self.rules_path}' が見つかりません。")
            (
                self.allow_domains,
                self.deny_domains,
                self.deny_subdomains,
                self.allow_path_keywords,
                self.deny_path_keywords,
                self.regex_deny_patterns,
            ) = set(), set(), [], [], [], []
        except Exception as e:
            logger.error(f"ルールファイルの読み込みに失敗しました: {e}")
            raise ValueError("ルールファイルの解析に失敗しました。")

    def parse(self, html_content: str) -> List[Bookmark]:
        logger.info("ブックマークの解析を開始します。")
        try:
            soup = BeautifulSoup(html_content, "lxml")

            expected_count = len([a for a in soup.find_all("a") if a.has_attr("href") and a["href"]])
            logger.info(f"ファイル内に存在する有効なリンク(Aタグ)の総数: {expected_count}件")

            root_h1 = soup.find("h1", string="Bookmarks")
            root_dl = root_h1.find_next_sibling("dl") if root_h1 else None
            if not root_dl:
                root_dl = soup.find("dl")
            if not root_dl:
                logger.error("解析対象のDL要素が見つかりませんでした。")
                return []

            all_bookmarks = []
            self._parse_dl_recursively(root_dl, [], all_bookmarks)

            extracted_count = len(all_bookmarks)
            logger.info(f"抽出完了: {extracted_count}件のブックマークを抽出しました。")

            if extracted_count != expected_count:
                error_message = (
                    f"抽出されたブックマーク数({extracted_count}件)がファイル内の"
                    f"リンク総数({expected_count}件)と一致しません。"
                    "HTMLの構造が予期せぬ形式であるか、パーサーのロジックに問題がある可能性があります。"
                )
                logger.error(error_message)
                raise ValueError(error_message)

            logger.info("フィルタリングを開始します。")
            filtered_bookmarks = [b for b in all_bookmarks if not self._should_exclude_bookmark(b)]
            logger.info(f"フィルタリング完了: {len(filtered_bookmarks)}件のブックマークが残りました。")
            return filtered_bookmarks
        except Exception as e:
            logger.error(f"ブックマーク解析中にエラーが発生: {e}", exc_info=True)
            if isinstance(e, ValueError):
                raise
            raise ValueError(f"ブックマーク解析エラー: {str(e)}")

    def _parse_dl_recursively(self, dl_element: Tag, current_path: List[str], bookmarks: List[Bookmark]):
        path_str = "/".join(current_path) if current_path else "(ルート)"
        logger.debug(f"-> DL探索中: {path_str}")

        # [ロジック修正] DLの直接の子要素だけを順番に処理する
        for child in dl_element.find_all(["dt", "p"], recursive=False):
            if child.name == "p":
                # Pタグの場合は、その中のDTタグを処理対象とする
                nodes_to_process = child.find_all("dt", recursive=False)
            else:
                # DTタグの場合は、それ自身を処理対象とする
                nodes_to_process = [child]

            for dt_node in nodes_to_process:
                h3_tag = dt_node.find("h3", recursive=False)
                a_tag = dt_node.find("a", recursive=False)

                if h3_tag:
                    folder_name = h3_tag.get_text(strip=True)
                    logger.debug(f"  フォルダ発見: {folder_name}")
                    new_path = current_path + [html.unescape(folder_name)]

                    dd_tag = dt_node.find_next_sibling("dd")
                    if dd_tag and (nested_dl := dd_tag.find("dl", recursive=False)):
                        self._parse_dl_recursively(nested_dl, new_path, bookmarks)

                elif a_tag:
                    # [ロジック修正] ネストされたブックマークをすべて見つけ出す
                    # このDTノードがマトリョーシカのようになっているので、中のAタグを再帰的に全て探す
                    all_a_tags_in_dt = dt_node.find_all("a", recursive=True)
                    for link in all_a_tags_in_dt:
                        if link.has_attr("href") and link["href"]:
                            logger.debug(f"  ブックマーク発見: {link.get_text(strip=True)}")
                            self._create_bookmark_from_a_tag(link, current_path, bookmarks)

    def _create_bookmark_from_a_tag(self, a_tag: Tag, current_path: List[str], bookmarks: List[Bookmark]):
        """AタグからBookmarkオブジェクトを生成してリストに追加するヘルパー関数"""
        try:
            url, title = a_tag["href"].strip(), a_tag.get_text(strip=True)
            if not url or not title:
                return

            add_date = None
            add_date_str = a_tag.get("add_date")
            if add_date_str:
                add_date = datetime.datetime.fromtimestamp(int(add_date_str))

            bookmarks.append(
                Bookmark(
                    title=html.unescape(title),
                    url=html.unescape(url),
                    folder_path=current_path,
                    add_date=add_date,
                    icon=a_tag.get("icon"),
                )
            )
        except Exception as e:
            logger.warning(f"個別ブックマークの解析失敗: {a_tag.get_text(strip=True)} - {e}")

    def _should_exclude_bookmark(self, bookmark: Bookmark) -> bool:
        url = bookmark.url
        if not self._is_valid_url(url):
            return True
        parsed_url = urlparse(url)
        domain = parsed_url.netloc.lower()
        path = parsed_url.path
        if any(p.search(url) for p in self.regex_deny_patterns):
            return True
        if domain in self.deny_domains:
            return True
        if any(k in domain for k in self.deny_subdomains):
            return True
        if domain in self.allow_domains:
            return self._is_domain_root_url(url)
        if self.deny_path_keywords and any(k in path for k in self.deny_path_keywords):
            return True
        if self.allow_path_keywords and any(k in path for k in self.allow_path_keywords):
            return self._is_domain_root_url(url)
        if self._is_domain_root_url(url):
            return True
        return True

    def _is_valid_url(self, url: str) -> bool:
        try:
            parsed = urlparse(url)
            return bool(parsed.scheme and parsed.netloc)
        except Exception:
            return False

    def _is_domain_root_url(self, url: str) -> bool:
        try:
            parsed = urlparse(url)
            path = parsed.path.strip("/")
            return len(path) == 0 and not parsed.query and not parsed.fragment
        except Exception:
            return False

    def get_statistics(self, bookmarks: List[Bookmark]) -> Dict[str, int]:
        total_bookmarks = len(bookmarks)
        unique_domains = len(set(urlparse(b.url).netloc for b in bookmarks))
        folder_count = len(set("/".join(b.folder_path) for b in bookmarks if b.folder_path))
        return {"total_bookmarks": total_bookmarks, "unique_domains": unique_domains, "folder_count": folder_count}
