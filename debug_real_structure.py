#!/usr/bin/env python3
"""
実際のHTMLファイルの構造を詳しく調査
"""

import os
import sys
from pathlib import Path
from bs4 import BeautifulSoup

def debug_real_structure(html_file_path):
    """実際のHTMLファイルの構造を調査"""
    
    print(f"📁 実際のHTMLファイル構造調査: {html_file_path}")
    
    # ファイル読み込み
    with open(html_file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # BeautifulSoupで解析
    soup = BeautifulSoup(content, 'html.parser')
    
    # ルートDLを取得
    root_dl = soup.find('dl')
    if not root_dl:
        print("❌ ルートDLエレメントが見つかりません")
        return
    
    print(f"✅ ルートDLエレメント発見")
    
    # ルートDLの直接の子要素を調査
    print(f"\n📊 ルートDLの直接の子要素:")
    direct_children = list(root_dl.children)
    
    dt_count = 0
    p_count = 0
    other_count = 0
    
    for i, child in enumerate(direct_children):
        if hasattr(child, 'name'):
            if child.name == 'dt':
                dt_count += 1
                if dt_count <= 3:  # 最初の3個だけ詳細表示
                    print(f"  {i+1:2d}. DT: {child.get_text(strip=True)[:50]}...")
                    
                    # DTの子要素を確認
                    dt_children = list(child.children)
                    dt_child_tags = [c.name for c in dt_children if hasattr(c, 'name') and c.name]
                    print(f"      子要素: {dt_child_tags}")
                    
            elif child.name == 'p':
                p_count += 1
                print(f"  {i+1:2d}. P: {child.get_text(strip=True)[:50]}...")
                
                # P内のDTを確認
                p_dts = child.find_all('dt')
                if p_dts:
                    print(f"      P内のDT数: {len(p_dts)}")
                    for j, p_dt in enumerate(p_dts[:3]):  # 最初の3個
                        print(f"        DT {j+1}: {p_dt.get_text(strip=True)[:30]}...")
            else:
                other_count += 1
                print(f"  {i+1:2d}. {child.name.upper()}: {child.get_text(strip=True)[:50]}...")
        else:
            # テキストノード
            text = str(child).strip()
            if text:
                print(f"  {i+1:2d}. TEXT: '{text[:30]}...'")
    
    print(f"\n📈 子要素統計:")
    print(f"  - DT要素: {dt_count}個")
    print(f"  - P要素: {p_count}個")
    print(f"  - その他: {other_count}個")
    
    # 実際の処理をシミュレート
    print(f"\n🔍 処理シミュレーション:")
    
    direct_dt_elements = []
    for child in root_dl.children:
        if hasattr(child, 'name'):
            if child.name == 'dt':
                direct_dt_elements.append(child)
                print(f"  ✅ 直接DT追加: {child.get_text(strip=True)[:30]}...")
            elif child.name == 'p':
                # pタグ内のdtエレメントも取得
                for p_child in child.children:
                    if hasattr(p_child, 'name') and p_child.name == 'dt':
                        direct_dt_elements.append(p_child)
                        print(f"  ✅ P内DT追加: {p_child.get_text(strip=True)[:30]}...")
    
    print(f"\n📊 処理対象DT数: {len(direct_dt_elements)}")

if __name__ == "__main__":
    html_file = "bookmarks_2025_09_06.html"
    
    if not os.path.exists(html_file):
        print(f"❌ ファイルが見つかりません: {html_file}")
        sys.exit(1)
    
    debug_real_structure(html_file)