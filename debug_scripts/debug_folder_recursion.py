#!/usr/bin/env python3
"""
フォルダの再帰処理をデバッグ
"""

import os
import sys
from urllib.parse import urlparse

# app.pyから必要なクラスをインポート
sys.path.append(".")
from app import BookmarkParser


class DebugBookmarkParser(BookmarkParser):
    """デバッグ用のBookmarkParser"""

    def __init__(self):
        super().__init__()
        self.debug_level = 0

    def _parse_dl_element(self, dl_element, current_path, processed_dls=None):
        """デバッグ版のDL解析"""
        if processed_dls is None:
            processed_dls = set()

        # 既に処理済みの場合はスキップ
        if id(dl_element) in processed_dls:
            return []

        # 処理済みとしてマーク
        processed_dls.add(id(dl_element))

        indent = "  " * self.debug_level
        folder_path = "/".join(current_path) if current_path else "(ルート)"
        print(f"{indent}📁 DL処理開始: {folder_path}")

        bookmarks = []

        # このDLの直接の子DTエレメントのみを取得（pタグ内も含む）
        direct_dt_elements = []
        for child in dl_element.children:
            if hasattr(child, "name"):
                if child.name == "dt":
                    direct_dt_elements.append(child)
                elif child.name == "p":
                    # pタグ内の直接の子DTエレメントを取得
                    for p_child in child.children:
                        if hasattr(p_child, "name") and p_child.name == "dt":
                            direct_dt_elements.append(p_child)

        print(f"{indent}  処理対象DT数: {len(direct_dt_elements)}")

        for i, dt in enumerate(direct_dt_elements):
            if i >= 10:  # 最初の10個だけ詳細表示
                print(f"{indent}  ... 残り{len(direct_dt_elements) - i}個のDT")
                break

            # DTの次の兄弟要素がDDかどうかをチェック
            next_sibling = dt.find_next_sibling()

            if next_sibling and next_sibling.name == "dd":
                # DTの後にDDがある場合 → フォルダ構造
                h3 = dt.find("h3")
                if h3:
                    folder_name = h3.get_text(strip=True)
                    new_path = current_path + [folder_name]
                    print(f"{indent}  📂 DD型フォルダ: {folder_name}")

                    # DD内のDLを再帰的に処理
                    nested_dl = next_sibling.find("dl")
                    if nested_dl:
                        self.debug_level += 1
                        nested_bookmarks = self._parse_dl_element(
                            nested_dl, new_path, processed_dls
                        )
                        self.debug_level -= 1
                        bookmarks.extend(nested_bookmarks)
                        print(
                            f"{indent}    → {len(nested_bookmarks)}個のブックマークを取得"
                        )
                    else:
                        print(f"{indent}    ⚠️ DD内にDLが見つかりません")
            else:
                # DTの後にDDがない場合の処理
                # H3タグがあり、内部にDLがある場合はフォルダとして処理
                h3 = dt.find("h3")
                internal_dl = dt.find("dl")

                if h3 and internal_dl:
                    # DTの内部にフォルダ構造がある場合（ブックマークバーなど）
                    folder_name = h3.get_text(strip=True)
                    new_path = current_path + [folder_name]
                    print(f"{indent}  📂 内部型フォルダ: {folder_name}")

                    self.debug_level += 1
                    nested_bookmarks = self._parse_dl_element(
                        internal_dl, new_path, processed_dls
                    )
                    self.debug_level -= 1
                    bookmarks.extend(nested_bookmarks)
                    print(
                        f"{indent}    → {len(nested_bookmarks)}個のブックマークを取得"
                    )
                else:
                    # 通常のブックマーク
                    a_tag = dt.find("a")
                    if a_tag:
                        url = a_tag.get("href", "").strip()
                        title = a_tag.get_text(strip=True)

                        bookmark = self._extract_bookmark_from_a_tag(
                            a_tag, current_path
                        )
                        if bookmark and not self._should_exclude_bookmark(bookmark):
                            bookmarks.append(bookmark)
                            print(f"{indent}  ✅ ブックマーク: {title[:30]}...")
                        else:
                            reason = (
                                self._get_exclusion_reason(bookmark)
                                if bookmark
                                else "抽出失敗"
                            )
                            print(f"{indent}  ❌ 除外: {title[:30]}... ({reason})")

        print(f"{indent}📊 DL処理完了: {len(bookmarks)}個のブックマーク")
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


def debug_folder_recursion(html_file_path):
    """フォルダの再帰処理をデバッグ"""

    print(f"📁 フォルダ再帰処理デバッグ: {html_file_path}")

    # ファイル読み込み
    with open(html_file_path, "r", encoding="utf-8") as f:
        content = f.read()

    # デバッグパーサーで解析
    parser = DebugBookmarkParser()
    bookmarks = parser.parse_bookmarks(content)

    print(f"\n📊 最終結果: {len(bookmarks)}個のブックマーク")


if __name__ == "__main__":
    html_file = "bookmarks_2025_09_06.html"

    if not os.path.exists(html_file):
        print(f"❌ ファイルが見つかりません: {html_file}")
        sys.exit(1)

    debug_folder_recursion(html_file)
