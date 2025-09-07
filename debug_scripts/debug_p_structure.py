#!/usr/bin/env python3
"""
P要素内の構造を詳しく調査
"""

import os
import sys
from bs4 import BeautifulSoup


def debug_p_structure(html_file_path):
    """P要素内の構造を調査"""

    print(f"📁 P要素内構造調査: {html_file_path}")

    # ファイル読み込み
    with open(html_file_path, "r", encoding="utf-8") as f:
        content = f.read()

    # BeautifulSoupで解析
    soup = BeautifulSoup(content, "html.parser")

    # ルートDLを取得
    root_dl = soup.find("dl")
    p_element = root_dl.find("p")

    if not p_element:
        print("❌ P要素が見つかりません")
        return

    print("✅ P要素発見")

    # P要素の直接の子要素を調査
    print("\n📊 P要素の直接の子要素 (最初の20個):")
    direct_children = list(p_element.children)

    dt_count = 0
    for i, child in enumerate(direct_children[:20]):
        if hasattr(child, "name"):
            if child.name == "dt":
                dt_count += 1
                print(
                    f"  {i + 1:2d}. DT {dt_count}: {child.get_text(strip=True)[:50]}..."
                )

                # DTの子要素を確認
                dt_children = list(child.children)
                dt_child_tags = [
                    c.name for c in dt_children if hasattr(c, "name") and c.name
                ]
                print(f"      子要素: {dt_child_tags}")

                # H3とAタグの確認
                h3 = child.find("h3")
                a_tag = child.find("a")
                internal_dl = child.find("dl")

                if h3:
                    print(f"      H3: {h3.get_text(strip=True)}")
                if a_tag:
                    print(
                        f"      A: {a_tag.get_text(strip=True)} → {a_tag.get('href')[:50]}..."
                    )
                if internal_dl:
                    print("      内部DL: あり")
            else:
                tag_name = child.name.upper() if child.name else "UNKNOWN"
                print(f"  {i + 1:2d}. {tag_name}: {child.get_text(strip=True)[:50]}...")
        else:
            # テキストノード
            text = str(child).strip()
            if text:
                print(f"  {i + 1:2d}. TEXT: '{text[:30]}...'")

    print(f"\n📈 P要素内の全DT数: {len(p_element.find_all('dt'))}")
    print(f"📈 P要素の直接の子DT数: {dt_count}")

    # 実際の処理をシミュレート
    print("\n🔍 処理シミュレーション:")

    direct_dt_elements = []
    for child in p_element.children:
        if hasattr(child, "name") and child.name == "dt":
            direct_dt_elements.append(child)

    print(f"📊 処理対象DT数: {len(direct_dt_elements)}")

    # 最初の数個を詳細表示
    for i, dt in enumerate(direct_dt_elements[:5]):
        h3 = dt.find("h3")
        a_tag = dt.find("a")
        internal_dl = dt.find("dl")

        print(f"  DT {i + 1}:")
        if h3 and internal_dl:
            print(f"    フォルダ: {h3.get_text(strip=True)}")
        elif a_tag:
            print(f"    ブックマーク: {a_tag.get_text(strip=True)}")
        else:
            print(f"    不明: {dt.get_text(strip=True)[:30]}...")


if __name__ == "__main__":
    html_file = "bookmarks_2025_09_06.html"

    if not os.path.exists(html_file):
        print(f"❌ ファイルが見つかりません: {html_file}")
        sys.exit(1)

    debug_p_structure(html_file)
