#!/usr/bin/env python3
"""
HTML構造の詳細分析
フォルダ構造がどのように表現されているかを調査
"""

import os
import sys
from pathlib import Path
from bs4 import BeautifulSoup

def analyze_html_structure(html_file_path):
    """HTML構造の詳細分析"""
    
    print(f"📁 HTML構造の詳細分析: {html_file_path}")
    
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
    
    # ルートレベルのDTエレメントを詳しく調べる
    all_dt_in_dl = root_dl.find_all('dt')
    
    # ネストしたDL内のDTエレメントを除外
    nested_dls = root_dl.find_all('dl')[1:]  # 最初のDLは自分自身なので除外
    nested_dt_elements = set()
    for nested_dl in nested_dls:
        nested_dt_elements.update(nested_dl.find_all('dt'))
    
    # このDLレベルのDTエレメントのみを処理
    direct_dt_elements = [dt for dt in all_dt_in_dl if dt not in nested_dt_elements]
    
    print(f"\n📊 ルートレベル構造:")
    print(f"  - 全DTエレメント: {len(all_dt_in_dl)}")
    print(f"  - ネストしたDL: {len(nested_dls)}")
    print(f"  - 直接のDT: {len(direct_dt_elements)}")
    
    print(f"\n🔍 ルートレベルDTエレメントの詳細分析 (最初の20個):")
    
    folder_count = 0
    bookmark_count = 0
    
    for i, dt in enumerate(direct_dt_elements[:20]):
        print(f"\n{i+1:2d}. DTエレメント分析:")
        
        # DTの内容を表示
        dt_text = dt.get_text(strip=True)[:60]
        print(f"    テキスト: {dt_text}...")
        
        # DTの子要素を調べる
        children = list(dt.children)
        child_tags = [child.name for child in children if hasattr(child, 'name') and child.name]
        print(f"    子要素: {child_tags}")
        
        # H3タグの存在確認
        h3 = dt.find('h3')
        if h3:
            print(f"    H3発見: {h3.get_text(strip=True)}")
        
        # Aタグの存在確認
        a_tag = dt.find('a')
        if a_tag:
            url = a_tag.get('href', '')[:60]
            title = a_tag.get_text(strip=True)[:40]
            print(f"    A発見: {title}... → {url}...")
        
        # 次の兄弟要素を確認
        next_sibling = dt.find_next_sibling()
        if next_sibling:
            print(f"    次の兄弟: {next_sibling.name}")
            
            if next_sibling.name == 'dd':
                print(f"    → フォルダ候補")
                folder_count += 1
                
                # DD内のDLを確認
                nested_dl = next_sibling.find('dl')
                if nested_dl:
                    nested_dt_count = len(nested_dl.find_all('dt'))
                    print(f"      ネストしたDL発見: {nested_dt_count}個のDT")
                else:
                    print(f"      ⚠️ ネストしたDLなし")
            else:
                print(f"    → ブックマーク候補")
                bookmark_count += 1
        else:
            print(f"    次の兄弟: なし")
            bookmark_count += 1
    
    print(f"\n📊 分析結果 (最初の20個):")
    print(f"  - フォルダ候補: {folder_count}")
    print(f"  - ブックマーク候補: {bookmark_count}")
    
    # 実際のフォルダ構造をサンプル表示
    print(f"\n📂 実際のフォルダ構造サンプル:")
    show_folder_structure_sample(root_dl)

def show_folder_structure_sample(root_dl):
    """フォルダ構造のサンプルを表示"""
    
    # ネストしたDLを探す
    nested_dls = root_dl.find_all('dl')[1:]  # 最初のDLは自分自身なので除外
    
    print(f"  発見されたネストDL数: {len(nested_dls)}")
    
    for i, nested_dl in enumerate(nested_dls[:5]):  # 最初の5個
        print(f"\n  📁 ネストDL {i+1}:")
        
        # このDLの親要素を探す
        parent_dd = nested_dl.find_parent('dd')
        if parent_dd:
            parent_dt = parent_dd.find_previous_sibling('dt')
            if parent_dt:
                h3 = parent_dt.find('h3')
                if h3:
                    folder_name = h3.get_text(strip=True)
                    print(f"    フォルダ名: {folder_name}")
        
        # このDL内のDTエレメント数
        dt_count = len(nested_dl.find_all('dt'))
        print(f"    内部DTエレメント数: {dt_count}")
        
        # サンプルのブックマークを表示
        sample_dts = nested_dl.find_all('dt')[:3]
        for j, dt in enumerate(sample_dts):
            a_tag = dt.find('a')
            if a_tag:
                title = a_tag.get_text(strip=True)[:40]
                print(f"      {j+1}. {title}...")

if __name__ == "__main__":
    html_file = "bookmarks_2025_09_06.html"
    
    if not os.path.exists(html_file):
        print(f"❌ ファイルが見つかりません: {html_file}")
        sys.exit(1)
    
    analyze_html_structure(html_file)