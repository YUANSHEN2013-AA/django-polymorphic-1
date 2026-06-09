"""
Tests for async ORM support.
"""

import asyncio

from django.db import models
from django.test import TransactionTestCase

from polymorphic.tests.models import (
    Model2A,
    Model2B,
    Model2C,
    Model2D,
    BlogBase,
    BlogA,
    BlogB,
    BlogEntry,
)





class AsyncPolymorphicQuerySetTests(TransactionTestCase):
    """
    Test async ORM methods on PolymorphicQuerySet.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

    def setUp(self):
        for idx in range(10):
            Model2A.objects.create(field1=f"A{idx}")
            Model2B.objects.create(field1=f"A{idx}", field2=f"B{idx}")
            Model2C.objects.create(field1=f"A{idx}", field2=f"B{idx}", field3=f"C{idx}")
            Model2D.objects.create(
                field1=f"A{idx}", field2=f"B{idx}", field3=f"C{idx}", field4=f"D{idx}"
            )

    def test_aget(self):
        """Test async aget method with polymorphic downcasting."""
        obj = Model2B.objects.create(field1="aget_test", field2="aget_test")

        async def _test():
            result = await Model2B.objects.aget(pk=obj.pk)
            assert result is not None
            assert result.pk == obj.pk
            assert result.__class__ is Model2B
            assert hasattr(result, "field2")
            assert result.field2 == "aget_test"

            result_from_base = await Model2A.objects.aget(pk=obj.pk)
            assert result_from_base.__class__ is Model2B

        asyncio.run(_test())

    def test_afirst(self):
        """Test async afirst method with polymorphic downcasting."""
        async def _test():
            first = await Model2A.objects.order_by("pk").afirst()
            assert first is not None
            assert first.field1 == "A0"
            assert first.__class__ == Model2A

            first_b = await Model2B.objects.order_by("pk").afirst()
            assert first_b is not None
            assert first_b.__class__ == Model2B

        asyncio.run(_test())

    def test_alast(self):
        """Test async alast method with polymorphic downcasting."""
        async def _test():
            last = await Model2D.objects.order_by("pk").alast()
            assert last is not None
            assert last.field1 == "A9"
            assert last.__class__ == Model2D

        asyncio.run(_test())

    def test_acount(self):
        """Test async acount method with instance_of filtering."""
        async def _test():
            count = await Model2A.objects.acount()
            assert count == 40

            count_b = await Model2A.objects.instance_of(Model2B).acount()
            assert count_b == 30

            count_c = await Model2A.objects.instance_of(Model2C).acount()
            assert count_c == 20

            count_d = await Model2A.objects.instance_of(Model2D).acount()
            assert count_d == 10

            count_not_d = await Model2A.objects.not_instance_of(Model2D).acount()
            assert count_not_d == 30

        asyncio.run(_test())

    def test_aexists(self):
        """Test async aexists method."""
        async def _test():
            exists = await Model2A.objects.filter(field1="A0").aexists()
            assert exists is True

            not_exists = await Model2A.objects.filter(field1="nonexistent").aexists()
            assert not_exists is False

            exists_b = await Model2A.objects.instance_of(Model2B).aexists()
            assert exists_b is True

        asyncio.run(_test())

    def test_aupdate(self):
        """Test async aupdate method."""
        async def _test():
            updated = await Model2A.objects.filter(field1__startswith="A").aupdate(
                field1="updated_sync"
            )
            assert updated == 40

            first = await Model2A.objects.aget(pk=1)
            assert first.field1 == "updated_sync"

            updated_b = await Model2A.objects.instance_of(Model2B).filter(
                pk__lte=10
            ).aupdate(field2="b_updated")
            assert updated_b == 10

        asyncio.run(_test())

    def test_aiterator_basic(self):
        """Test async aiterator yields polymorphically downcast instances."""
        async def _test():
            count = 0
            async for obj in Model2A.objects.order_by("pk").aiterator():
                count += 1
                assert hasattr(obj, "field1")
                if isinstance(obj, Model2D):
                    assert hasattr(obj, "field4")
            assert count == 40

        asyncio.run(_test())

    def test_aiterator_chunked(self):
        """Test async aiterator with custom chunk_size."""
        async def _test():
            count = 0
            async for obj in Model2A.objects.order_by("pk").aiterator(chunk_size=5):
                count += 1
            assert count == 40

        asyncio.run(_test())

    def test_aiterator_small_chunk(self):
        """Test async aiterator with chunk_size=1."""
        async def _test():
            count = 0
            async for obj in Model2A.objects.order_by("pk").aiterator(chunk_size=1):
                count += 1
            assert count == 40

        asyncio.run(_test())

    def test_aiterator_non_polymorphic(self):
        """Test async aiterator with non-polymorphic query."""
        async def _test():
            count = 0
            async for obj in Model2A.objects.non_polymorphic().order_by("pk").aiterator():
                count += 1
                assert obj.__class__ == Model2A
            assert count == 40

        asyncio.run(_test())

    def test_aiterator_instance_of(self):
        """Test async aiterator with instance_of filtering."""
        async def _test():
            results = []
            async for obj in (
                Model2A.objects.instance_of(Model2C, Model2D).order_by("pk").aiterator()
            ):
                results.append(obj)

            assert len(results) == 30
            for obj in results:
                assert obj.__class__ in (Model2C, Model2D)

        asyncio.run(_test())

    def test_aiterator_not_instance_of(self):
        """Test async aiterator with not_instance_of filtering."""
        async def _test():
            results = []
            async for obj in (
                Model2A.objects.not_instance_of(Model2D).order_by("pk").aiterator()
            ):
                results.append(obj)

            assert len(results) == 30
            for obj in results:
                assert not isinstance(obj, Model2D)

        asyncio.run(_test())

    def test_aiterator_select_related(self):
        """Test async aiterator with select_related."""
        async def _test():
            blog_a = BlogA.objects.create(name="sr_a", info="sr_a")
            BlogEntry.objects.create(blog=blog_a, text="sr_entry")

            results = []
            async for obj in (
                BlogBase.objects.select_related().order_by("pk").aiterator()
            ):
                results.append(obj)

            assert len(results) == 1
            assert results[0].__class__ == BlogA

        asyncio.run(_test())

    def test_manager_async_proxies(self):
        """Test that manager proxies async methods correctly."""
        async def _test():
            obj = await Model2B.objects.aget(field1="A0")
            assert obj is not None
            assert obj.__class__ == Model2B

            count = await Model2A.objects.acount()
            assert count == 40

            exists = await Model2A.objects.aexists()
            assert exists is True

            first = await Model2A.objects.afirst()
            assert first is not None

            last = await Model2A.objects.alast()
            assert last is not None

            updated = await Model2A.objects.filter(pk=1).aupdate(
                field1="manager_changed"
            )
            assert updated == 1

            count_after = await Model2A.objects.filter(field1="manager_changed").acount()
            assert count_after == 1

        asyncio.run(_test())

    def test_downcasting_consistency(self):
        """Verify async downcasting behavior is the same as sync."""
        async def _test():
            sync_results = list(Model2A.objects.order_by("pk").all())
            async_results = []
            async for obj in Model2A.objects.order_by("pk").aiterator():
                async_results.append(obj)

            assert len(sync_results) == len(async_results)
            for sync_obj, async_obj in zip(sync_results, async_results):
                assert sync_obj.__class__ == async_obj.__class__
                assert sync_obj.pk == async_obj.pk

        asyncio.run(_test())

    def test_union_async(self):
        """Test async operations on union querysets."""
        async def _test():
            qs1 = Model2A.objects.filter(id__lte=10)
            qs2 = Model2A.objects.filter(id__gt=10)
            union_qs = qs1.union(qs2)
            count = await union_qs.acount()
            assert count == 40

        asyncio.run(_test())

    def test_intersection_async(self):
        """Test async operations on intersection querysets."""
        async def _test():
            qs1 = Model2A.objects.filter(field1__startswith="A")
            qs2 = Model2A.objects.instance_of(Model2B)
            intersect_qs = qs1.intersection(qs2)
            count = await intersect_qs.acount()
            assert count == 30

        asyncio.run(_test())

    def test_queryset_clone_async(self):
        """Verify clone preserves polymorphic state for async."""
        async def _test():
            qs = Model2A.objects.all().instance_of(Model2B)
            cloned = qs.all()
            count = await cloned.acount()
            assert count == 30
            assert not cloned.polymorphic_disabled

            non_poly = qs.non_polymorphic()
            assert non_poly.polymorphic_disabled
            cloned_non_poly = non_poly.all()
            assert cloned_non_poly.polymorphic_disabled
            non_poly_count = await cloned_non_poly.acount()
            assert non_poly_count == 30

        asyncio.run(_test())

    def test_abulk_create(self):
        """Test that abulk_create works with polymorphic models."""
        async def _test():
            objs = [Model2A(field1=f"bulk{i}") for i in range(10)]
            result = await Model2A.objects.abulk_create(objs)
            assert len(result) == 10
            count = await Model2A.objects.acount()
            assert count == 50

        asyncio.run(_test())

    def test_adelete(self):
        """Test that adelete works."""
        async def _test():
            deleted = await Model2A.objects.filter(field1="A0").adelete()
            assert deleted[0] == 4

            remaining = await Model2A.objects.filter(field1="A0").acount()
            assert remaining == 0

        asyncio.run(_test())


class AsyncCrossDBTests(TransactionTestCase):
    """
    Test async ORM with cross-database routing.
    """

    def test_aiterator_cross_db(self):
        """Test async aiterator with explicit database."""
        using = "secondary"

        async def _test():
            count = 0
            async for obj in (
                Model2A.objects.using(using).order_by("pk").aiterator()
            ):
                count += 1
            assert count == 0

        asyncio.run(_test())


class AsyncPolymorphicPerformanceTests(TransactionTestCase):
    """
    Performance tests for async ORM operations.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

    def setUp(self):
        for idx in range(100):
            Model2A.objects.create(field1=f"A{idx}")
            Model2B.objects.create(field1=f"A{idx}", field2=f"B{idx}")
            Model2C.objects.create(field1=f"A{idx}", field2=f"B{idx}", field3=f"C{idx}")
            Model2D.objects.create(
                field1=f"A{idx}", field2=f"B{idx}", field3=f"C{idx}", field4=f"D{idx}"
            )

    def test_baseline_async_query_count(self):
        """Test that async iteration uses reasonable number of queries."""
        async def _test():
            with self.assertNumQueries(4):
                results = []
                async for obj in Model2A.objects.order_by("pk").aiterator():
                    results.append(obj)
                assert len(results) == 400

            with self.assertNumQueries(3):
                results = []
                async for obj in Model2B.objects.order_by("pk").aiterator():
                    results.append(obj)
                assert len(results) == 300

            with self.assertNumQueries(2):
                results = []
                async for obj in Model2C.objects.order_by("pk").aiterator():
                    results.append(obj)
                assert len(results) == 200

            with self.assertNumQueries(1):
                results = []
                async for obj in Model2D.objects.order_by("pk").aiterator():
                    results.append(obj)
                assert len(results) == 100

        asyncio.run(_test())

    def test_async_query_count_with_chunking(self):
        """Test query count with different chunk sizes."""
        async def _test():
            with self.assertNumQueries(5):
                results = []
                async for obj in Model2A.objects.order_by("pk").aiterator(chunk_size=100):
                    results.append(obj)
                assert len(results) == 400

            with self.assertNumQueries(7):
                results = []
                async for obj in Model2A.objects.order_by("pk").aiterator(chunk_size=50):
                    results.append(obj)
                assert len(results) == 400

        asyncio.run(_test())