"""
Performance benchmark for async ORM.
"""

import time
import asyncio
from typing import Callable

from django.db import connections
from django.db.models import QuerySet
from polymorphic.tests.models import Model2A, Model2B, Model2C, Model2D


def setup_data(count: int = 1000):
    """Create benchmark data."""
    for idx in range(count):
        Model2A.objects.create(field1=f"A{idx}")
        Model2B.objects.create(field1=f"A{idx}", field2=f"B{idx}")
        Model2C.objects.create(field1=f"A{idx}", field2=f"B{idx}", field3=f"C{idx}")
        Model2D.objects.create(
            field1=f"A{idx}", field2=f"B{idx}", field3=f"C{idx}", field4=f"D{idx}"
        )


async def benchmark_async_iteration(qs: QuerySet, chunk_size: int | None = None) -> float:
    """Benchmark async iteration."""
    start = time.perf_counter()
    count = 0
    async for obj in qs.order_by("pk").aiterator(chunk_size=chunk_size):
        _ = obj.pk
        count += 1
    end = time.perf_counter()
    return end - start


def benchmark_sync_iteration(qs: QuerySet) -> float:
    """Benchmark sync iteration for comparison."""
    start = time.perf_counter()
    count = 0
    for obj in qs.order_by("pk").iterator():
        _ = obj.pk
        count += 1
    end = time.perf_counter()
    return end - start


async def benchmark_async_methods():
    """Benchmark individual async methods."""
    results = {}

    qs_all = Model2A.objects.all()
    qs_b = Model2A.objects.instance_of(Model2B)

    start = time.perf_counter()
    count = await qs_all.acount()
    end = time.perf_counter()
    results["acount_all"] = end - start

    start = time.perf_counter()
    exists = await qs_all.filter(pk=1).aexists()
    end = time.perf_counter()
    results["aexists"] = end - start

    start = time.perf_counter()
    obj = await qs_all.aget(pk=1)
    end = time.perf_counter()
    results["aget"] = end - start

    start = time.perf_counter()
    first = await qs_all.afirst()
    end = time.perf_counter()
    results["afirst"] = end - start

    start = time.perf_counter()
    last = await qs_all.alast()
    end = time.perf_counter()
    results["alast"] = end - start

    start = time.perf_counter()
    updated = await qs_b.filter(pk__lte=100).aupdate(field2="updated")
    end = time.perf_counter()
    results["aupdate"] = end - start

    return results


def run_benchmark():
    """Run the full benchmark suite."""
    print("=" * 60)
    print("django-polymorphic Async ORM Performance Benchmark")
    print("=" * 60)

    with connections["default"].schema_editor():
        setup_data(1000)
        print(f"\nCreated 4000 total objects (1000 of each type)\n")

        print("Query count verification:")
        from django.test.utils import CaptureQueriesContext
        from django.db import connection

        with CaptureQueriesContext(connection) as ctx:
            asyncio.run(list(Model2A.objects.all().aiterator()))
        print(f"Full iteration total queries: {len(ctx)}")

        print("\n")
        print("Benchmarking iteration...")

        sync_time = benchmark_sync_iteration(Model2A.objects.all())
        print(f"  Sync iterator  : {sync_time:.3f}s")

        async_time_full = asyncio.run(benchmark_async_iteration(Model2A.objects.all()))
        print(f"  Async aiterator : {async_time_full:.3f}s")

        async_time_100 = asyncio.run(benchmark_async_iteration(Model2A.objects.all(), 100))
        print(f"  Async (chunk 100): {async_time_100:.3f}s")

        async_time_500 = asyncio.run(benchmark_async_iteration(Model2A.objects.all(), 500))
        print(f"  Async (chunk 500): {async_time_500:.3f}s")

        print("\nBenchmarking individual async methods...")
        method_results = asyncio.run(benchmark_async_methods())
        for name, duration in method_results.items():
            print(f"  {name:<12} : {duration:.4f}s")

        print("\nBenchmarking filtered queries...")

        async_time_b = asyncio.run(benchmark_async_iteration(Model2A.objects.instance_of(Model2B)))
        print(f"  instance_of(Model2B): {async_time_b:.3f}s")

        async_time_d = asyncio.run(benchmark_async_iteration(Model2A.objects.instance_of(Model2D)))
        print(f"  instance_of(Model2D): {async_time_d:.3f}s")

        print("\n" + "=" * 60)
        print("Summary:")
        print(f"  Async / Sync ratio: {async_time_full / sync_time:.2f}x")
        print("=" * 60)


if __name__ == "__main__":
    run_benchmark()
