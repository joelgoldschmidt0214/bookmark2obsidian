#!/usr/bin/env python3
"""
P要素内のDT構造を非常に詳しく調査
"""

import os
import sys
from bs4 import BeautifulSoup


def debug_p_dt_structure(html_file_path):
    """P要素内のDT構造を詳しく調査"""

    print(f"📁 P要素内DT構造詳細調査: {html_file_path}")

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

    # P要素内のすべてのDTを取得
    all_p_dts = p_element.find_all("dt")
    print(f"📊 P要素内の全DT数: {len(all_p_dts)}")

    # P要素の直接の子DTを取得
    direct_p_dts = []
    for child in p_element.children:
        if hasattr(child, "name") and child.name == "dt":
            direct_p_dts.append(child)

    print(f"📊 P要素の直接の子DT数: {len(direct_p_dts)}")

    # recursive=Falseでの取得
    recursive_false_dts = p_element.find_all("dt", recursive=False)
    print(f"📊 recursive=FalseでのDT数: {len(recursive_false_dts)}")

    # P要素内のネストしたDLを確認
    nested_dls_in_p = p_element.find_all("dl")
    print(f"📊 P要素内のネストDL数: {len(nested_dls_in_p)}")

    if nested_dls_in_p:
        nested_dt_in_p = set()
        for nested_dl in nested_dls_in_p:
            nested_dt_in_p.update(nested_dl.find_all("dt"))

        print(f"📊 ネストDL内のDT数: {len(nested_dt_in_p)}")

        # ネストしたDL内のDTを除外したDT
        non_nested_dts = [dt for dt in all_p_dts if dt not in nested_dt_in_p]
        print(f"📊 ネスト除外後のDT数: {len(non_nested_dts)}")

        # 最初の数個を詳細表示
        print("\n🔍 ネスト除外後のDTサンプル (最初の10個):")
        for i, dt in enumerate(non_nested_dts[:10]):
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

    # 実際の処理をシミュレート
    print("\n🔍 修正後の処理シミュレーション:")

    direct_dt_elements = []
    for child in p_element.children:
        if hasattr(child, "name") and child.name == "dt":
            direct_dt_elements.append(child)

    # P要素内にDTが見つからない場合は、すべてのDTを取得
    if not direct_dt_elements:
        direct_dt_elements = p_element.find_all("dt", recursive=False)

    # まだ見つからない場合は、P要素内のすべてのDTを取得
    if not direct_dt_elements:
        all_p_dts = p_element.find_all("dt")
        # ネストしたDL内のDTを除外
        nested_dls_in_p = p_element.find_all("dl")
        nested_dt_in_p = set()
        for nested_dl in nested_dls_in_p:
            nested_dt_in_p.update(nested_dl.find_all("dt"))

        direct_dt_elements = [dt for dt in all_p_dts if dt not in nested_dt_in_p]

    print(f"📊 最終的な処理対象DT数: {len(direct_dt_elements)}")


if __name__ == "__main__":
    html_file = "bookmarks_2025_09_06.html"

    if not os.path.exists(html_file):
        print(f"❌ ファイルが見つかりません: {html_file}")
        sys.exit(1)

    debug_p_dt_structure(html_file)
