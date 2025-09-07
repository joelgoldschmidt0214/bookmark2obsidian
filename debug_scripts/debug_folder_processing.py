#!/usr/bin/env python3
"""
フォルダ処理の詳細デバッグ
なぜフォルダ内のブックマークが処理されないかを調査
"""

import os
import sys
from bs4 import BeautifulSoup
from urllib.parse import urlparse

# app.pyから必要なクラスをインポート
sys.path.append(".")
from app import BookmarkParser


def debug_folder_processing(html_file_path):
    """フォルダ処理の詳細デバッグ"""

    print(f"📁 フォルダ処理の詳細デバッグ: {html_file_path}")

    # ファイル読み込み
    with open(html_file_path, "r", encoding="utf-8") as f:
        content = f.read()

    # BeautifulSoupで解析
    soup = BeautifulSoup(content, "html.parser")

    # ルートDLを取得
    root_dl = soup.find("dl")
    if not root_dl:
        print("❌ ルートDLエレメントが見つかりません")
        return

    print("✅ ルートDLエレメント発見")

    # カスタムパーサーでデバッグ
    debug_parser = DebugBookmarkParser()
    bookmarks = debug_parser.parse_bookmarks(content)

    print("\n📊 最終結果:")
    print(f"  - 解析されたブックマーク数: {len(bookmarks)}")
    print(f"  - 処理されたフォルダ数: {debug_parser.folder_count}")
    print(f"  - 処理されたレベル数: {debug_parser.max_level}")


class DebugBookmarkParser(BookmarkParser):
    """デバッグ用のBookmarkParser"""

    def __init__(self):
        super().__init__()
        self.folder_count = 0
        self.max_level = 0
        self.level_stats = {}

    def _parse_dl_element(self, dl_element, current_path):
        """デバッグ版のDL解析"""
        level = len(current_path)
        self.max_level = max(self.max_level, level)

        if level not in self.level_stats:
            self.level_stats[level] = {"folders": 0, "bookmarks": 0, "excluded": 0}

        indent = "  " * level
        print(
            f"{indent}📁 レベル {level} 処理開始: パス={'/'.join(current_path) if current_path else '(ルート)'}"
        )

        bookmarks = []

        # このDLレベルのDTエレメントを取得
        all_dt_in_dl = dl_element.find_all("dt")

        # ネストしたDL内のDTエレメントを除外
        nested_dls = dl_element.find_all("dl")[1:]  # 最初のDLは自分自身なので除外
        nested_dt_elements = set()
        for nested_dl in nested_dls:
            nested_dt_elements.update(nested_dl.find_all("dt"))

        # このDLレベルのDTエレメントのみを処理
        direct_dt_elements = [dt for dt in all_dt_in_dl if dt not in nested_dt_elements]

        print(f"{indent}  - 全DTエレメント: {len(all_dt_in_dl)}")
        print(f"{indent}  - ネストしたDL: {len(nested_dls)}")
        print(f"{indent}  - 直接のDT: {len(direct_dt_elements)}")

        folder_count_this_level = 0
        bookmark_count_this_level = 0
        excluded_count_this_level = 0

        for i, dt in enumerate(direct_dt_elements):
            # 最初の数個だけ詳細表示
            show_detail = (
                (level == 0 and i < 5)
                or (level == 1 and i < 3)
                or (level >= 2 and i < 2)
            )

            next_sibling = dt.find_next_sibling()

            if next_sibling and next_sibling.name == "dd":
                # フォルダ
                h3 = dt.find("h3")
                if h3:
                    folder_name = h3.get_text(strip=True)
                    new_path = current_path + [folder_name]
                    folder_count_this_level += 1
                    self.folder_count += 1

                    if show_detail:
                        print(
                            f"{indent}  📂 フォルダ {folder_count_this_level}: {folder_name}"
                        )

                    # DD内のDLを再帰的に処理
                    nested_dl = next_sibling.find("dl")
                    if nested_dl:
                        nested_bookmarks = self._parse_dl_element(nested_dl, new_path)
                        bookmarks.extend(nested_bookmarks)
                        if show_detail:
                            print(
                                f"{indent}    → {len(nested_bookmarks)}個のブックマークを取得"
                            )
                    elif show_detail:
                        print(f"{indent}    ⚠️ ネストしたDLが見つかりません")
            else:
                # ブックマーク
                a_tag = dt.find("a")
                if a_tag:
                    url = a_tag.get("href", "").strip()
                    title = a_tag.get_text(strip=True)

                    if url and title:
                        bookmark = self._extract_bookmark_from_a_tag(
                            a_tag, current_path
                        )
                        if bookmark and not self._should_exclude_bookmark(bookmark):
                            bookmarks.append(bookmark)
                            bookmark_count_this_level += 1
                            if show_detail:
                                print(
                                    f"{indent}  ✅ ブックマーク {bookmark_count_this_level}: {title[:30]}..."
                                )
                        else:
                            excluded_count_this_level += 1
                            if show_detail:
                                reason = (
                                    self._get_exclusion_reason(bookmark)
                                    if bookmark
                                    else "抽出失敗"
                                )
                                print(
                                    f"{indent}  ❌ 除外 {excluded_count_this_level}: {title[:30]}... ({reason})"
                                )

        # 統計更新
        self.level_stats[level]["folders"] += folder_count_this_level
        self.level_stats[level]["bookmarks"] += bookmark_count_this_level
        self.level_stats[level]["excluded"] += excluded_count_this_level

        print(
            f"{indent}📊 レベル {level} 完了: フォルダ={folder_count_this_level}, ブックマーク={bookmark_count_this_level}, 除外={excluded_count_this_level}"
        )

        return bookmarks

    def _get_exclusion_reason(self, bookmark):
        """除外理由を取得"""
        if not bookmark:
            return "抽出失敗"

        if self._is_domain_root_url(bookmark.url):
            return "ドメインルート"
        if not self._is_valid_url(bookmark.url):
            return "無効URL"
        if bookmark.url in self.excluded_urls:
            return "除外URL"

        try:
            parsed_url = urlparse(bookmark.url)
            domain = parsed_url.netloc.lower()
            if domain in self.excluded_domains:
                return "除外ドメイン"
        except:
            return "URL解析エラー"

        return "不明"

    def print_statistics(self):
        """統計情報を表示"""
        print("\n📊 レベル別統計:")
        for level in sorted(self.level_stats.keys()):
            stats = self.level_stats[level]
            print(
                f"  レベル {level}: フォルダ={stats['folders']}, ブックマーク={stats['bookmarks']}, 除外={stats['excluded']}"
            )


if __name__ == "__main__":
    html_file = "bookmarks_2025_09_06.html"

    if not os.path.exists(html_file):
        print(f"❌ ファイルが見つかりません: {html_file}")
        sys.exit(1)

    debug_folder_processing(html_file)
