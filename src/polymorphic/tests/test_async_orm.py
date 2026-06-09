from asgiref.sync import async_to_sync
from django.db import connection
from django.test import TransactionTestCase
from django.test.utils import CaptureQueriesContext

from polymorphic.tests.models import (
    Model2A,
    Model2B,
    Model2C,
    Model2D,
    One2OneRelatingModel,
    One2OneRelatingModelDerived,
    RelatingModel,
)


class AsyncPolymorphicTests(TransactionTestCase):
    reset_sequences = True

    def test_aget_afirst_alast_acount_aexists_aupdate(self):
        a = Model2A.objects.create(field1="A1")
        b = Model2B.objects.create(field1="B1", field2="B2")
        c = Model2C.objects.create(field1="C1", field2="C2", field3="C3")

        async def run():
            got_b = await Model2A.objects.instance_of(Model2B).aget(pk=b.pk)
            got_a = await Model2A.objects.not_instance_of(Model2B).aget(pk=a.pk)
            first_obj = await Model2A.objects.order_by("pk").afirst()
            last_obj = await Model2A.objects.order_by("pk").alast()
            count = await Model2A.objects.instance_of(Model2B, Model2C).acount()
            exists = await Model2A.objects.instance_of(Model2C).aexists()
            updated = await Model2A.objects.instance_of(Model2C).aupdate(field1="C1-updated")
            return got_b, got_a, first_obj, last_obj, count, exists, updated

        got_b, got_a, first_obj, last_obj, count, exists, updated = async_to_sync(run)()

        self.assertIsInstance(got_b, Model2B)
        self.assertEqual(got_b.pk, b.pk)
        self.assertIsInstance(got_a, Model2A)
        self.assertEqual(got_a.pk, a.pk)
        self.assertIsInstance(first_obj, Model2A)
        self.assertEqual(first_obj.pk, a.pk)
        self.assertIsInstance(last_obj, Model2C)
        self.assertEqual(last_obj.pk, c.pk)
        self.assertEqual(count, 2)
        self.assertTrue(exists)
        self.assertEqual(updated, 1)
        self.assertEqual(Model2C.objects.get(pk=c.pk).field1, "C1-updated")

    def test_aiterator_preserves_downcast_and_queryset_cache(self):
        b = Model2B.objects.create(field1="B1", field2="B2")
        c = Model2C.objects.create(field1="C1", field2="C2", field3="C3")
        d = Model2D.objects.create(field1="D1", field2="D2", field3="D3", field4="D4")

        queryset = Model2A.objects.instance_of(Model2B, Model2C, Model2D).order_by("pk")
        clone = queryset.all()

        async def run():
            return [obj async for obj in clone]

        objects = async_to_sync(run)()

        self.assertEqual([obj.pk for obj in objects], [b.pk, c.pk, d.pk])
        self.assertEqual([obj.__class__ for obj in objects], [Model2B, Model2C, Model2D])
        self.assertFalse(queryset.polymorphic_disabled)
        self.assertFalse(clone.polymorphic_disabled)
        self.assertEqual([obj.__class__ for obj in list(clone)], [Model2B, Model2C, Model2D])

    def test_async_union_and_intersection_keep_downcast(self):
        b = Model2B.objects.create(field1="B1", field2="B2")
        c = Model2C.objects.create(field1="C1", field2="C2", field3="C3")
        d = Model2D.objects.create(field1="D1", field2="D2", field3="D3", field4="D4")

        left = Model2A.objects.filter(pk__in=[b.pk, c.pk])
        right = Model2A.objects.filter(pk__in=[c.pk, d.pk])

        async def run():
            union_objects = [obj async for obj in left.union(right).order_by("pk")]
            intersection_objects = [obj async for obj in left.intersection(right).order_by("pk")]
            return union_objects, intersection_objects

        union_objects, intersection_objects = async_to_sync(run)()

        self.assertEqual([obj.__class__ for obj in union_objects], [Model2B, Model2C, Model2D])
        self.assertEqual([obj.pk for obj in union_objects], [b.pk, c.pk, d.pk])
        self.assertEqual([obj.__class__ for obj in intersection_objects], [Model2C])
        self.assertEqual([obj.pk for obj in intersection_objects], [c.pk])

    def test_async_select_related_and_prefetch_related_keep_related_caches(self):
        related = Model2B.objects.create(field1="B1", field2="B2")
        derived = One2OneRelatingModelDerived.objects.create(
            one2one=related,
            field1="base",
            field2="derived",
        )
        owner = RelatingModel.objects.create()
        owner.many2many.add(related)

        async def run():
            one_to_one = await One2OneRelatingModel.objects.select_related("one2one").aget(
                pk=derived.pk
            )
            relating_models = [
                obj
                async for obj in RelatingModel.objects.order_by("pk").prefetch_related("many2many")
            ]
            return one_to_one, relating_models

        one_to_one, relating_models = async_to_sync(run)()

        self.assertIsInstance(one_to_one, One2OneRelatingModelDerived)
        with self.assertNumQueries(0):
            cached_related = one_to_one.one2one
        self.assertIsInstance(cached_related, Model2B)

        self.assertEqual(len(relating_models), 1)
        with self.assertNumQueries(0):
            prefetched = list(relating_models[0].many2many.all())
        self.assertEqual([obj.__class__ for obj in prefetched], [Model2B])


class AsyncPolymorphicMultiDBTests(TransactionTestCase):
    databases = ["default", "secondary"]
    reset_sequences = True

    def test_async_queries_respect_secondary_database(self):
        Model2B.objects.db_manager("secondary").create(field1="B1", field2="B2")
        Model2C.objects.db_manager("secondary").create(field1="C1", field2="C2", field3="C3")

        async def fetch_from_secondary():
            first = await Model2A.objects.db_manager("secondary").order_by("pk").afirst()
            collected = [
                obj
                async for obj in Model2A.objects.db_manager("secondary")
                .instance_of(Model2B, Model2C)
                .order_by("pk")
            ]
            return first, collected

        with CaptureQueriesContext(connection) as default_queries:
            first, collected = async_to_sync(fetch_from_secondary)()

        self.assertEqual(len(default_queries), 0)
        self.assertIsInstance(first, Model2B)
        self.assertEqual([obj.__class__ for obj in collected], [Model2B, Model2C])
        self.assertEqual({obj._state.db for obj in collected}, {"secondary"})


class AsyncPolymorphicPerformanceTests(TransactionTestCase):
    reset_sequences = True

    def test_async_baseline_number_of_queries(self):
        for idx in range(50):
            Model2A.objects.create(field1=f"A{idx}")
            Model2B.objects.create(field1=f"B{idx}", field2=f"B2-{idx}")
            Model2C.objects.create(field1=f"C{idx}", field2=f"C2-{idx}", field3=f"C3-{idx}")
            Model2D.objects.create(
                field1=f"D{idx}",
                field2=f"D2-{idx}",
                field3=f"D3-{idx}",
                field4=f"D4-{idx}",
            )

        async def run_iterator():
            return [obj async for obj in Model2A.objects.order_by("pk").aiterator(chunk_size=100)]

        with self.assertNumQueries(4):
            result = async_to_sync(run_iterator)()

        self.assertEqual(len(result), 200)
        self.assertIsInstance(result[0], Model2A)
        self.assertIsInstance(result[-1], Model2D)
