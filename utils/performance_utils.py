"""
パフォーマンス最適化ユーティリティモジュール

このモジュールは、ブックマーク解析のパフォーマンス最適化機能を提供します。
バッチ処理、並列処理、メモリ使用量監視などの機能を含みます。
"""

import time
import psutil
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any, Callable, Optional, Tuple
from dataclasses import dataclass
import logging
from functools import wraps

logger = logging.getLogger(__name__)


@dataclass
class PerformanceMetrics:
    """
    パフォーマンス測定結果を格納するデータクラス

    Attributes:
        processing_time: 処理時間（秒）
        memory_usage: メモリ使用量（MB）
        items_processed: 処理されたアイテム数
        batch_size: 使用されたバッチサイズ
        worker_count: 使用されたワーカー数
        throughput: スループット（アイテム/秒）
    """

    processing_time: float
    memory_usage: float
    items_processed: int
    batch_size: int
    worker_count: int
    throughput: float = 0.0

    def __post_init__(self):
        """スループットを自動計算"""
        if self.processing_time > 0:
            self.throughput = self.items_processed / self.processing_time


class MemoryMonitor:
    """
    メモリ使用量を監視するクラス
    """

    def __init__(self):
        self.process = psutil.Process()
        self.initial_memory = self.get_memory_usage()

    def get_memory_usage(self) -> float:
        """
        現在のメモリ使用量を取得（MB単位）

        Returns:
            float: メモリ使用量（MB）
        """
        try:
            memory_info = self.process.memory_info()
            return memory_info.rss / 1024 / 1024  # バイトからMBに変換
        except Exception as e:
            logger.warning(f"メモリ使用量の取得に失敗: {e}")
            return 0.0

    def get_memory_delta(self) -> float:
        """
        初期値からのメモリ使用量の変化を取得

        Returns:
            float: メモリ使用量の変化（MB）
        """
        current = self.get_memory_usage()
        return current - self.initial_memory

    def log_memory_usage(self, context: str = ""):
        """
        現在のメモリ使用量をログに記録

        Args:
            context: ログのコンテキスト情報
        """
        current = self.get_memory_usage()
        delta = self.get_memory_delta()
        logger.info(f"メモリ使用量 {context}: {current:.1f}MB (変化: {delta:+.1f}MB)")


class PerformanceOptimizer:
    """
    パフォーマンス最適化を管理するクラス

    バッチ処理、並列処理、メモリ監視などの機能を提供し、
    大量のブックマーク解析を効率的に実行します。
    """

    def __init__(self, default_batch_size: int = 1000, default_worker_count: int = 4):
        """
        PerformanceOptimizerを初期化

        Args:
            default_batch_size: デフォルトのバッチサイズ
            default_worker_count: デフォルトのワーカー数
        """
        self.default_batch_size = default_batch_size
        self.default_worker_count = default_worker_count
        self.memory_monitor = MemoryMonitor()

    def optimize_parsing(
        self,
        items: List[Any],
        parse_function: Callable,
        batch_size: Optional[int] = None,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> Tuple[List[Any], PerformanceMetrics]:
        """
        バッチ処理による最適化された解析を実行

        Args:
            items: 解析対象のアイテムリスト
            parse_function: 解析関数
            batch_size: バッチサイズ（Noneの場合はデフォルト値を使用）
            progress_callback: 進捗コールバック関数

        Returns:
            Tuple[List[Any], PerformanceMetrics]: 解析結果とパフォーマンス情報
        """
        if batch_size is None:
            batch_size = self.default_batch_size

        start_time = time.time()
        initial_memory = self.memory_monitor.get_memory_usage()

        logger.info(
            f"バッチ処理開始: {len(items)}個のアイテム, バッチサイズ: {batch_size}"
        )

        results = []
        processed_count = 0

        # バッチごとに処理
        for i in range(0, len(items), batch_size):
            batch = items[i : i + batch_size]
            batch_start = time.time()

            # バッチを処理
            batch_results = []
            for item in batch:
                try:
                    result = parse_function(item)
                    if result is not None:
                        batch_results.extend(
                            result if isinstance(result, list) else [result]
                        )
                except Exception as e:
                    logger.error(f"バッチ処理中にエラー: {e}")
                    continue

            results.extend(batch_results)
            processed_count += len(batch)

            # 進捗報告
            if progress_callback:
                progress_callback(processed_count, len(items))

            # メモリ使用量をログ
            batch_time = time.time() - batch_start
            self.memory_monitor.log_memory_usage(f"バッチ {i // batch_size + 1}")
            logger.debug(
                f"バッチ {i // batch_size + 1} 完了: {len(batch_results)}個の結果, {batch_time:.2f}秒"
            )

        # パフォーマンス情報を計算
        end_time = time.time()
        processing_time = end_time - start_time
        final_memory = self.memory_monitor.get_memory_usage()

        metrics = PerformanceMetrics(
            processing_time=processing_time,
            memory_usage=final_memory - initial_memory,
            items_processed=len(items),
            batch_size=batch_size,
            worker_count=1,  # バッチ処理は単一スレッド
            throughput=len(items) / processing_time if processing_time > 0 else 0,
        )

        logger.info(
            f"バッチ処理完了: {len(results)}個の結果, {processing_time:.2f}秒, {metrics.throughput:.1f}個/秒"
        )

        return results, metrics

    def parallel_process_bookmarks(
        self,
        items: List[Any],
        process_function: Callable,
        worker_count: Optional[int] = None,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> Tuple[List[Any], PerformanceMetrics]:
        """
        並列処理による最適化された処理を実行

        Args:
            items: 処理対象のアイテムリスト
            process_function: 処理関数
            worker_count: ワーカー数（Noneの場合はデフォルト値を使用）
            progress_callback: 進捗コールバック関数

        Returns:
            Tuple[List[Any], PerformanceMetrics]: 処理結果とパフォーマンス情報
        """
        if worker_count is None:
            worker_count = self.default_worker_count

        start_time = time.time()
        initial_memory = self.memory_monitor.get_memory_usage()

        logger.info(
            f"並列処理開始: {len(items)}個のアイテム, ワーカー数: {worker_count}"
        )

        results = []
        processed_count = 0
        lock = threading.Lock()

        def update_progress():
            nonlocal processed_count
            with lock:
                processed_count += 1
                if progress_callback:
                    progress_callback(processed_count, len(items))

        # ThreadPoolExecutorを使用して並列処理
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            # 全てのタスクを投入
            future_to_item = {
                executor.submit(process_function, item): item for item in items
            }

            # 結果を収集
            for future in as_completed(future_to_item):
                try:
                    result = future.result()
                    if result is not None:
                        results.extend(result if isinstance(result, list) else [result])
                    update_progress()
                except Exception as e:
                    item = future_to_item[future]
                    logger.error(f"並列処理中にエラー (アイテム: {item}): {e}")
                    update_progress()

        # パフォーマンス情報を計算
        end_time = time.time()
        processing_time = end_time - start_time
        final_memory = self.memory_monitor.get_memory_usage()

        metrics = PerformanceMetrics(
            processing_time=processing_time,
            memory_usage=final_memory - initial_memory,
            items_processed=len(items),
            batch_size=0,  # 並列処理ではバッチサイズは適用されない
            worker_count=worker_count,
            throughput=len(items) / processing_time if processing_time > 0 else 0,
        )

        logger.info(
            f"並列処理完了: {len(results)}個の結果, {processing_time:.2f}秒, {metrics.throughput:.1f}個/秒"
        )

        return results, metrics

    def monitor_memory_usage(self) -> Dict[str, float]:
        """
        現在のメモリ使用状況を取得

        Returns:
            Dict[str, float]: メモリ使用状況の辞書
        """
        try:
            current_memory = self.memory_monitor.get_memory_usage()
            memory_delta = self.memory_monitor.get_memory_delta()

            # システム全体のメモリ情報も取得
            system_memory = psutil.virtual_memory()

            return {
                "current_memory_mb": current_memory,
                "memory_delta_mb": memory_delta,
                "system_memory_percent": system_memory.percent,
                "system_available_mb": system_memory.available / 1024 / 1024,
            }
        except Exception as e:
            logger.error(f"メモリ使用量の監視に失敗: {e}")
            return {}

    def get_optimal_batch_size(
        self, total_items: int, target_memory_mb: float = 100
    ) -> int:
        """
        メモリ使用量を考慮した最適なバッチサイズを計算

        Args:
            total_items: 総アイテム数
            target_memory_mb: 目標メモリ使用量（MB）

        Returns:
            int: 推奨バッチサイズ
        """
        # 簡単なヒューリスティック: アイテム数とメモリ制限から計算
        base_batch_size = min(self.default_batch_size, total_items)

        # メモリ制限を考慮した調整
        current_memory = self.memory_monitor.get_memory_usage()
        available_memory = target_memory_mb - (current_memory * 0.1)  # 10%のバッファ

        if available_memory < 50:  # メモリが不足している場合
            adjusted_batch_size = max(100, base_batch_size // 2)
        else:
            adjusted_batch_size = base_batch_size

        logger.info(
            f"最適バッチサイズ計算: {adjusted_batch_size} (総アイテム: {total_items}, 利用可能メモリ: {available_memory:.1f}MB)"
        )

        return adjusted_batch_size

    def get_optimal_worker_count(self) -> int:
        """
        システムリソースを考慮した最適なワーカー数を計算

        Returns:
            int: 推奨ワーカー数
        """
        # CPU数を基準に計算
        cpu_count = psutil.cpu_count(logical=False) or 1
        logical_cpu_count = psutil.cpu_count(logical=True) or 1

        # メモリ使用量も考慮
        memory_info = psutil.virtual_memory()
        memory_available_gb = memory_info.available / 1024 / 1024 / 1024

        # ヒューリスティック: 物理CPU数を基準に、メモリ制限も考慮
        if memory_available_gb < 2:  # 2GB未満の場合
            optimal_workers = max(1, cpu_count // 2)
        elif memory_available_gb < 4:  # 4GB未満の場合
            optimal_workers = cpu_count
        else:  # 十分なメモリがある場合
            optimal_workers = min(logical_cpu_count, cpu_count * 2)

        # デフォルト値との比較
        final_workers = min(optimal_workers, self.default_worker_count * 2)

        logger.info(
            f"最適ワーカー数計算: {final_workers} (CPU: {cpu_count}, 論理CPU: {logical_cpu_count}, 利用可能メモリ: {memory_available_gb:.1f}GB)"
        )

        return final_workers


def performance_monitor(func: Callable) -> Callable:
    """
    関数のパフォーマンスを監視するデコレータ

    Args:
        func: 監視対象の関数

    Returns:
        Callable: デコレートされた関数
    """

    @wraps(func)
    def wrapper(*args, **kwargs):
        monitor = MemoryMonitor()
        start_time = time.time()

        logger.info(f"パフォーマンス監視開始: {func.__name__}")
        monitor.log_memory_usage("開始時")

        try:
            result = func(*args, **kwargs)

            end_time = time.time()
            processing_time = end_time - start_time

            monitor.log_memory_usage("完了時")
            logger.info(
                f"パフォーマンス監視完了: {func.__name__} - {processing_time:.2f}秒"
            )

            return result

        except Exception as e:
            end_time = time.time()
            processing_time = end_time - start_time

            monitor.log_memory_usage("エラー時")
            logger.error(
                f"パフォーマンス監視エラー: {func.__name__} - {processing_time:.2f}秒, エラー: {e}"
            )

            raise

    return wrapper
