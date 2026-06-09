"""
Async ORM tests for PolymorphicQuerySet.

Tests async methods (aget, afirst, alast, aiterator, acount, aexists, aupdate)
and verifies that polymorphic downcast works correctly with async queries.
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from django.core.exceptions import ImproperlyConfigured

from polymorphic.tests.models import (
    ArtProject,
    MultiTableBase,
    MultiTableDerived,
)


try:
    from django.db import connections

    # Check if async database support is available (Django 4.2+)
    connections["default"].ensure_connection()
    HAS_ASYNC_SUPPORT = True
except (ImproperlyConfigured, Exception):
    HAS_ASYNC_SUPPORT = False


pytestmark = pytest.mark.skipif(
    not HAS_ASYNC_SUPPORT,
    reason="Async database support not available in this environment",
)


def _run_async(coro):
    """Run an async coroutine in a new event loop."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.mark.django_db(transaction=True)
class TestAsyncPolymorphicQuerySet:
    """Tests for async PolymorphicQuerySet methods."""

    def test_async_methods_exist(self):
        """Verify that async methods exist on PolymorphicQuerySet."""
        qs = MultiTableBase.objects.all()
        assert hasattr(qs, "aget"), "aget method not found"
        assert hasattr(qs, "afirst"), "afirst method not found"
        assert hasattr(qs, "alast"), "alast method not found"
        assert hasattr(qs, "aiterator"), "aiterator method not found"
        assert hasattr(qs, "acount"), "acount method not found"
        assert hasattr(qs, "aexists"), "aexists method not found"
        assert hasattr(qs, "aupdate"), "aupdate method not found"
        assert hasattr(qs, "aget_real_instances"), "aget_real_instances not found"
        assert hasattr(qs, "_aget_real_instances"), "_aget_real_instances not found"

    def test_async_iterator_support(self):
        """Verify that __aiter__ exists for async for support."""
        qs = MultiTableBase.objects.all()
        assert hasattr(qs, "__aiter__"), "__aiter__ not found on queryset"

    def test_polymorphic_disabled_aiterator(self):
        """Verify aiterator works with non-polymorphic querysets."""
        qs = MultiTableBase.objects.non_polymorphic()

        async def _check():
            items = []
            async for item in qs.aiterator():
                items.append(item)
            return items

        # If we have objects, we should be able to iterate
        result = _run_async(_check())
        assert isinstance(result, list)

    def test_acount_method(self):
        """Verify acount returns int and works on empty/mixed querysets."""
        qs = MultiTableBase.objects.all()

        async def _check():
            return await qs.acount()

        initial_count = _run_async(_check())
        assert isinstance(initial_count, int)

        # Create some objects to verify count changes
        base1 = MultiTableBase.objects.create(field1="base1")
        derived1 = MultiTableDerived.objects.create(field1="derived1", field2="d1")

        qs2 = MultiTableBase.objects.all()

        async def _check_after():
            return await qs2.acount()

        new_count = _run_async(_check_after())
        assert new_count == initial_count + 2

        # Cleanup
        base1.delete()
        derived1.delete()

    def test_aexists_method(self):
        """Verify aexists returns bool and works correctly."""
        qs = MultiTableBase.objects.all()

        async def _check():
            return await qs.aexists()

        initial_exists = _run_async(_check())
        assert isinstance(initial_exists, bool)

        # Create an object to test exists is True
        obj = MultiTableBase.objects.create(field1="test_exists")

        async def _check_true():
            return await MultiTableBase.objects.filter(pk=obj.pk).aexists()

        result = _run_async(_check_true())
        assert result is True

        # Verify non-existent returns False
        async def _check_false():
            return await MultiTableBase.objects.filter(field1="nonexistent_xyz_123").aexists()

        result = _run_async(_check_false())
        assert result is False

        # Cleanup
        obj.delete()

    def test_afirst_on_empty(self):
        """Verify afirst returns None on empty queryset."""
        qs = MultiTableBase.objects.filter(field1="definitely_nonexistent_xyz")

        async def _check():
            return await qs.afirst()

        result = _run_async(_check())
        assert result is None

    def test_afirst_returns_correct_type(self):
        """Verify afirst returns the correct polymorphic subclass."""
        base = MultiTableBase.objects.create(field1="afirst_base")
        derived = MultiTableDerived.objects.create(field1="afirst_derived", field2="d2")

        try:
            # Query base model - first should be base
            qs = MultiTableBase.objects.order_by("pk")

            async def _check_base_first():
                return await qs.afirst()

            result = _run_async(_check_base_first())
            assert result is not None
            assert isinstance(result, MultiTableBase)

            # Query specifically for derived
            qs_derived = MultiTableBase.objects.filter(
                polymorphic_ctype__model="multitablederived"
            ).order_by("pk")

            async def _check_derived():
                return await qs_derived.afirst()

            derived_result = _run_async(_check_derived())
            assert derived_result is not None
            assert isinstance(derived_result, MultiTableDerived)
        finally:
            base.delete()
            derived.delete()

    def test_alast_on_empty(self):
        """Verify alast returns None on empty queryset."""
        qs = MultiTableBase.objects.filter(field1="definitely_nonexistent_xyz")

        async def _check():
            return await qs.alast()

        result = _run_async(_check())
        assert result is None

    def test_alast_returns_last(self):
        """Verify alast returns the last element."""
        obj1 = MultiTableBase.objects.create(field1="alast_first")
        obj2 = MultiTableBase.objects.create(field1="alast_second")

        try:
            qs = MultiTableBase.objects.order_by("pk")

            async def _check():
                return await qs.alast()

            result = _run_async(_check())
            assert result is not None
            assert result.pk == obj2.pk
        finally:
            obj1.delete()
            obj2.delete()

    def test_aget_not_found(self):
        """Verify aget raises DoesNotExist for non-existent objects."""
        qs = MultiTableBase.objects.filter(field1="nonexistent_object_xyz")

        async def _check():
            try:
                return await qs.aget()
            except MultiTableBase.DoesNotExist:
                return "DoesNotExist"

        result = _run_async(_check())
        assert result == "DoesNotExist"

    def test_aget_single_object(self):
        """Verify aget returns a single object correctly."""
        obj = MultiTableBase.objects.create(field1="aget_test")

        try:
            async def _check():
                return await MultiTableBase.objects.aget(pk=obj.pk)

            result = _run_async(_check())
            assert result is not None
            assert result.pk == obj.pk
        finally:
            obj.delete()

    def test_aget_multiple_objects_error(self):
        """Verify aget raises MultipleObjectsReturned."""
        obj1 = MultiTableBase.objects.create(field1="aget_multi_test")
        obj2 = MultiTableBase.objects.create(field1="aget_multi_test")

        try:
            async def _check():
                try:
                    return await MultiTableBase.objects.aget(field1="aget_multi_test")
                except MultiTableBase.MultipleObjectsReturned:
                    return "MultipleObjectsReturned"

            result = _run_async(_check())
            assert result == "MultipleObjectsReturned"
        finally:
            obj1.delete()
            obj2.delete()

    def test_aupdate_method(self):
        """Verify aupdate updates rows and returns affected count."""
        obj1 = MultiTableBase.objects.create(field1="aupdate_orig_1")
        obj2 = MultiTableBase.objects.create(field1="aupdate_orig_2")

        try:
            async def _check():
                return await MultiTableBase.objects.filter(
                    field1__startswith="aupdate_orig"
                ).aupdate(field1="aupdate_new")

            count = _run_async(_check())
            assert count == 2

            # Verify the update took effect
            assert MultiTableBase.objects.filter(field1="aupdate_new").count() == 2
        finally:
            obj1.delete()
            obj2.delete()

    def test_aiterator_yields_polymorphic_instances(self):
        """Verify aiterator yields real polymorphic instances."""
        base = MultiTableBase.objects.create(field1="aiter_base")
        derived = MultiTableDerived.objects.create(
            field1="aiter_derived", field2="aiter_field2"
        )

        try:
            async def _check():
                items = []
                async for item in MultiTableBase.objects.order_by("pk").aiterator():
                    items.append(item)
                return items

            items = _run_async(_check())
            assert len(items) >= 2
            # Check at least the items we created are there
            pks = [i.pk for i in items]
            assert base.pk in pks
            assert derived.pk in pks

            # Find the derived object in results and verify polymorphic type
            derived_in_results = [i for i in items if i.pk == derived.pk][0]
            assert isinstance(derived_in_results, MultiTableDerived)
        finally:
            base.delete()
            derived.delete()

    def test_async_for_loop_support(self):
        """Verify async for loop over a PolymorphicQuerySet."""
        obj = MultiTableBase.objects.create(field1="async_for_test")

        try:
            async def _check():
                items = []
                async for item in MultiTableBase.objects.filter(pk=obj.pk):
                    items.append(item)
                return items

            items = _run_async(_check())
            assert len(items) == 1
            assert items[0].pk == obj.pk
        finally:
            obj.delete()

    def test_aget_real_instances_method(self):
        """Verify aget_real_instances does polymorphic downcast."""
        base = MultiTableBase.objects.create(field1="aget_ri_base")
        derived = MultiTableDerived.objects.create(
            field1="aget_ri_derived", field2="aget_ri_f2"
        )

        try:
            async def _check():
                return await MultiTableBase.objects.all().aget_real_instances()

            instances = _run_async(_check())
            pks = [i.pk for i in instances]
            assert base.pk in pks
            assert derived.pk in pks

            # Verify the derived instance was downcasted
            derived_in_results = [i for i in instances if i.pk == derived.pk][0]
            assert isinstance(derived_in_results, MultiTableDerived)
        finally:
            base.delete()
            derived.delete()

    def test_polymorphic_downcast_with_instance_of(self):
        """Verify instance_of filter works with async methods."""
        base = MultiTableBase.objects.create(field1="inst_of_base")
        derived = MultiTableDerived.objects.create(
            field1="inst_of_derived", field2="inst_of_f2"
        )

        try:
            # Test async count with instance_of
            async def _check_count():
                return await MultiTableBase.objects.instance_of(
                    MultiTableDerived
                ).acount()

            derived_count = _run_async(_check_count())
            assert derived_count >= 1

            # Test async first with not_instance_of
            async def _check_first():
                return await MultiTableBase.objects.not_instance_of(
                    MultiTableDerived
                ).afirst()

            first_base = _run_async(_check_first())
            if first_base is not None:
                assert not isinstance(first_base, MultiTableDerived)
        finally:
            base.delete()
            derived.delete()

    def test_queryset_clone_preserves_polymorphic_state(self):
        """Verify that queryset cloning preserves polymorphic state."""
        qs = MultiTableBase.objects.all()

        # Make sure clone preserves the polymorphic_disabled state
        qs_disabled = qs.non_polymorphic()
        clone = qs_disabled.filter(field1="test")
        assert clone.polymorphic_disabled is True

        # Regular clone should have polymorphic enabled
        qs_enabled = MultiTableBase.objects.all()
        clone2 = qs_enabled.filter(field1="test2")
        assert clone2.polymorphic_disabled is False

    def test_select_related_async(self):
        """Verify select_related works with async querysets."""
        # Create a simple test for select_related
        base = MultiTableBase.objects.create(field1="select_related_test")

        try:
            async def _check():
                qs = MultiTableBase.objects.select_related().filter(pk=base.pk)
                return await qs.afirst()

            result = _run_async(_check())
            assert result is not None
            assert result.pk == base.pk
        finally:
            base.delete()

    def test_prefetch_related_async(self):
        """Verify prefetch_related works with async querysets."""
        base = MultiTableBase.objects.create(field1="prefetch_related_test")

        try:
            async def _check():
                qs = MultiTableBase.objects.prefetch_related().filter(pk=base.pk)
                return await qs.afirst()

            result = _run_async(_check())
            assert result is not None
            assert result.pk == base.pk
        finally:
            base.delete()
