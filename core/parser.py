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
            soup = BeautifulSoup(html_content, "html5lib")

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
            filtered_bookmarks = []
            # 再帰処理に両方のリストを渡す
            self._parse_dl_recursively(root_dl, [], all_bookmarks, filtered_bookmarks)

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

            # このリスト内包表記は不要になる
            # filtered_bookmarks = [b for b in all_bookmarks if not self._should_exclude_bookmark(b)]
            # logger.info("フィルタリングは抽出と同時に完了しました。")

            logger.info(f"フィルタリング完了: {len(filtered_bookmarks)}件のブックマークが残りました。")
            return filtered_bookmarks
        except Exception as e:
            logger.error(f"ブックマーク解析中にエラーが発生: {e}", exc_info=True)
            if isinstance(e, ValueError):
                raise
            raise ValueError(f"ブックマーク解析エラー: {str(e)}")

    def _parse_dl_recursively(
        self,
        dl_element: Tag,
        current_path: List[str],
        all_bookmarks: List[Bookmark],
        filtered_bookmarks: List[Bookmark],
    ):
        """
        <dl>タグを再帰的に処理する (html5lib向けにシンプル化)
        """
        path_str = "/".join(current_path) if current_path else "(ルート)"
        logger.debug(f"-> DL探索中: {path_str}")

        for dt_tag in dl_element.find_all("dt", recursive=False):
            h3_tag = dt_tag.find("h3", recursive=False)
            a_tag = dt_tag.find("a", recursive=False)

            if h3_tag:
                folder_name = h3_tag.get_text(strip=True)
                logger.debug(f"  フォルダ発見: {folder_name}")
                new_path = current_path + [html.unescape(folder_name)]

                nested_dl = dt_tag.find("dl", recursive=False)
                if nested_dl:
                    # 再帰呼び出しにも両方のリストを渡す
                    self._parse_dl_recursively(nested_dl, new_path, all_bookmarks, filtered_bookmarks)

            elif a_tag:
                if a_tag.has_attr("href") and a_tag["href"]:
                    logger.debug(f"  ブックマーク発見: {a_tag.get_text(strip=True) or a_tag['href']}")
                    # _create_bookmark... にも両方のリストを渡す
                    self._create_bookmark_from_a_tag(a_tag, current_path, all_bookmarks, filtered_bookmarks)

    def _create_bookmark_from_a_tag(
        self, a_tag: Tag, current_path: List[str], all_bookmarks: List[Bookmark], filtered_bookmarks: List[Bookmark]
    ):
        try:
            url = a_tag["href"].strip()
            title = a_tag.get_text(strip=True)

            if not url:
                return
            if not title:
                title = url
                logger.debug(f"    タイトルが空のためURLを仮タイトルに設定: {url}")

            add_date = None
            add_date_str = a_tag.get("add_date")
            if add_date_str:
                add_date = datetime.datetime.fromtimestamp(int(add_date_str))

            # Bookmarkオブジェクトを作成
            bookmark = Bookmark(
                title=html.unescape(title),
                url=html.unescape(url),
                folder_path=current_path,
                add_date=add_date,
                icon=a_tag.get("icon"),
            )

            # まず all_bookmarks に無条件で追加
            all_bookmarks.append(bookmark)

            # 次にフィルタリングして、条件を満たすものだけ filtered_bookmarks に追加
            if not self._should_exclude_bookmark(bookmark):
                filtered_bookmarks.append(bookmark)

        except Exception as e:
            logger.warning(f"個別ブックマークの解析失敗: {a_tag.get_text(strip=True)} - {e}")

    def _should_exclude_bookmark(self, bookmark: Bookmark) -> bool:
        url = bookmark.url
        if not self._is_valid_url(url):
            return True
        parsed_url = urlparse(url)
        domain = parsed_url.netloc.lower()
        path = parsed_url.path
        if domain in self.deny_domains:
            return True
        if any(k in domain for k in self.deny_subdomains):
            return True
        if self.deny_path_keywords and any(k in path for k in self.deny_path_keywords):
            return True
        if any(p.search(url) for p in self.regex_deny_patterns):
            return True
        if domain in self.allow_domains:
            return self._is_domain_root_url(url)
        if self.allow_path_keywords and any(k in path for k in self.allow_path_keywords):
            return self._is_domain_root_url(url)
        if self._is_domain_root_url(url):
            return True
        return True

    def _is_valid_url(self, url: str) -> bool:
        # javascript: bookmarklets are not valid http URLs
        if url.strip().lower().startswith("javascript:"):
            return False
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
        unique_domains = len(set(urlparse(b.url).netloc for b in bookmarks if self._is_valid_url(b.url)))
        folder_count = len(set("/".join(b.folder_path) for b in bookmarks if b.folder_path))
        return {"total_bookmarks": total_bookmarks, "unique_domains": unique_domains, "folder_count": folder_count}
