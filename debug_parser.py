#!/usr/bin/env python3
"""
BookmarkParserのデバッグ用スクリプト
"""

from bs4 import BeautifulSoup

def debug_html_structure():
    html_content = '''<!DOCTYPE NETSCAPE-Bookmark-file-1>
<HTML><HEAD><TITLE>Bookmarks</TITLE></HEAD>
<BODY><H1>Bookmarks</H1>
<DL><p>
    <DT><A HREF="https://www.google.com/search" ADD_DATE="1640995200">Google Search</A>
    <DT><A HREF="https://github.com/explore" ADD_DATE="1640995300">GitHub Explore</A>
</DL></BODY></HTML>'''
    
    soup = BeautifulSoup(html_content, 'html.parser')
    
    print("=== HTML構造の解析 ===")
    
    # DLエレメントを探す
    dl_elements = soup.find_all('dl')
    print(f"DLエレメント数: {len(dl_elements)}")
    
    for i, dl in enumerate(dl_elements):
        print(f"\nDL {i+1}:")
        print(f"  内容: {dl}")
        
        # DTエレメントを探す
        dt_elements = dl.find_all('dt', recursive=False)
        print(f"  直接の子DTエレメント数: {len(dt_elements)}")
        
        for j, dt in enumerate(dt_elements):
            print(f"    DT {j+1}: {dt}")
            
            # DTの次の兄弟要素をチェック
            next_sibling = dt.find_next_sibling()
            print(f"      次の兄弟要素: {next_sibling}")
            
            # DTの中のAタグをチェック
            a_tag = dt.find('a')
            if a_tag:
                print(f"      Aタグ: {a_tag}")
                print(f"        HREF: {a_tag.get('href')}")
                print(f"        テキスト: {a_tag.get_text(strip=True)}")

if __name__ == "__main__":
    debug_html_structure()