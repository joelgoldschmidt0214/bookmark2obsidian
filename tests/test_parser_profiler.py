import cProfile
import pstats

from core.parser import BookmarkParser

# テスト用のHTMLファイルを読み込む
with open("test_data/bookmarks_2025_09_06.html", "r", encoding="utf-8") as f:
    html_content = f.read()

parser = BookmarkParser()

# cProfile を使って実行
profiler = cProfile.Profile()
profiler.enable()

# 時間を計測したい関数を実行
parser.parse_bookmarks_optimized(html_content, use_parallel=True)

profiler.disable()

# 結果をソートして表示
stats = pstats.Stats(profiler).sort_stats("cumulative")
stats.print_stats(30)  # 上位30件を表示
