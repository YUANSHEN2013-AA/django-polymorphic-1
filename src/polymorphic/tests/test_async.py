import pytest
from django.test import TransactionTestCase
from polymorphic.tests.models import Model2A, Model2B, Model2C, Model2D

class AsyncTests(TransactionTestCase):
    def setUp(self):
        Model2A.objects.create(field1="A1")
        Model2B.objects.create(field1="A2", field2="B2")
        Model2C.objects.create(field1="A3", field2="B3", field3="C3")
        Model2D.objects.create(field1="A4", field2="B4", field3="C4", field4="D4")

    async def test_aiterator(self):
        qs = Model2A.objects.order_by("pk")
        results = [obj async for obj in qs.aiterator()]
        self.assertEqual(len(results), 4)
        self.assertIsInstance(results[0], Model2A)
        self.assertIsInstance(results[1], Model2B)
        self.assertIsInstance(results[2], Model2C)
        self.assertIsInstance(results[3], Model2D)

    async def test_aget(self):
        obj = await Model2A.objects.aget(field1="A2")
        self.assertIsInstance(obj, Model2B)
        self.assertEqual(obj.field2, "B2")

    async def test_afirst_alast(self):
        qs = Model2A.objects.order_by("pk")
        first = await qs.afirst()
        self.assertIsInstance(first, Model2A)
        self.assertEqual(first.field1, "A1")

        last = await qs.alast()
        self.assertIsInstance(last, Model2D)
        self.assertEqual(last.field4, "D4")

    async def test_acount_aexists(self):
        count = await Model2A.objects.acount()
        self.assertEqual(count, 4)

        exists = await Model2A.objects.filter(field1="A3").aexists()
        self.assertTrue(exists)

        not_exists = await Model2A.objects.filter(field1="X").aexists()
        self.assertFalse(not_exists)

    async def test_aupdate(self):
        updated = await Model2A.objects.filter(field1="A1").aupdate(field1="A1_updated")
        self.assertEqual(updated, 1)
        obj = await Model2A.objects.aget(field1="A1_updated")
        self.assertEqual(obj.field1, "A1_updated")

    async def test_union_intersection(self):
        qs1 = Model2A.objects.filter(field1__in=["A1", "A2"])
        qs2 = Model2A.objects.filter(field1__in=["A2", "A3"])
        
        # Intersection
        qs_int = qs1.intersection(qs2)
        results_int = [obj async for obj in qs_int]
        self.assertEqual(len(results_int), 1)
        self.assertIsInstance(results_int[0], Model2B)

        # Union
        qs_union = qs1.union(qs2).order_by("field1")
        results_union = [obj async for obj in qs_union]
        self.assertEqual(len(results_union), 3)
        self.assertIsInstance(results_union[0], Model2A)
        self.assertIsInstance(results_union[1], Model2B)
        self.assertIsInstance(results_union[2], Model2C)

    async def test_instance_of(self):
        qs = Model2A.objects.instance_of(Model2B)
        results = [obj async for obj in qs.order_by("pk")]
        self.assertEqual(len(results), 3)
        self.assertIsInstance(results[0], Model2B)
        self.assertIsInstance(results[1], Model2C)
        self.assertIsInstance(results[2], Model2D)

        qs_not = Model2A.objects.not_instance_of(Model2C)
        results_not = [obj async for obj in qs_not.order_by("pk")]
        self.assertEqual(len(results_not), 2)
        self.assertIsInstance(results_not[0], Model2A)
        self.assertIsInstance(results_not[1], Model2B)

class AsyncPerformanceTests(TransactionTestCase):
    async def test_async_baseline_number_of_queries(self):
        for idx in range(100):
            await Model2A.objects.acreate(field1=f"A{idx}")
            await Model2B.objects.acreate(field1=f"A{idx}", field2=f"B{idx}")
            await Model2C.objects.acreate(field1=f"A{idx}", field2=f"B{idx}", field3=f"C{idx}")
            await Model2D.objects.acreate(
                field1=f"A{idx}", field2=f"B{idx}", field3=f"C{idx}", field4=f"D{idx}"
            )

        with self.assertNumQueries(4):
            results = [obj async for obj in Model2A.objects.all().order_by("pk")]
            self.assertEqual(len(results), 400)
            
        with self.assertNumQueries(3):
            results_b = [obj async for obj in Model2B.objects.all().order_by("pk")]
            self.assertEqual(len(results_b), 300)

        with self.assertNumQueries(2):
            results_c = [obj async for obj in Model2C.objects.all().order_by("pk")]
            self.assertEqual(len(results_c), 200)

        with self.assertNumQueries(1):
            results_d = [obj async for obj in Model2D.objects.all().order_by("pk")]
            self.assertEqual(len(results_d), 100)
