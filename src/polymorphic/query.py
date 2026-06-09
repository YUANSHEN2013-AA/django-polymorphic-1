"""
QuerySet for PolymorphicModel
"""

from __future__ import annotations

import copy
import heapq
from collections import defaultdict
from collections.abc import AsyncIterator, Collection, Iterable, Iterator, Sequence
from typing import TYPE_CHECKING, Any, Generic, cast, overload

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import FieldDoesNotExist
from django.db import NotSupportedError, connections, models
from django.db.models import FilteredRelation, Q
from django.db.models.expressions import Combinable
from django.db.models.query import ModelIterable, QuerySet
from typing_extensions import Self, TypeVar

try:
    from django.db.models import aprefetch_related_objects
except ImportError:
    try:
        from django.db.models.query import aprefetch_related_objects
    except ImportError:
        aprefetch_related_objects = None

try:
    from django.db.models.query import MAX_GET_RESULTS
except ImportError:
    MAX_GET_RESULTS = 21

from .query_translate import (
    translate_polymorphic_field_path,
    translate_polymorphic_filter_definitions_in_args,
    translate_polymorphic_filter_definitions_in_kwargs,
    translate_polymorphic_Q_object,
)
from .utils import concrete_descendants, route_to_ancestor

if TYPE_CHECKING:
    from .models import PolymorphicModel  # noqa: F401

_All = TypeVar("_All", bound="PolymorphicModel", covariant=True)
_Base = TypeVar("_Base", bound="PolymorphicModel", default="PolymorphicModel", covariant=True)

_A = TypeVar("_A", bound="PolymorphicModel")
_B = TypeVar("_B", bound="PolymorphicModel")
_C = TypeVar("_C", bound="PolymorphicModel")
_D = TypeVar("_D", bound="PolymorphicModel")

Polymorphic_QuerySet_objects_per_request: int = 2000
"""
The maximum number of objects requested per db-request by the polymorphic
queryset.iterator() implementation
"""

if TYPE_CHECKING:

    class BasePolymorphicModelIterable(ModelIterable[_All]):
        pass
else:

    class BasePolymorphicModelIterable(ModelIterable):
        pass


class _Inconsistent:
    """
    A marker class indicating that there is a mismatch between the content type
    and the actual class of an object retrieved from the database.
    """

    ...


class PolymorphicModelIterable(BasePolymorphicModelIterable, Generic[_All, _Base]):
    """
    ModelIterable for PolymorphicModel

    Yields real instances if qs.polymorphic_disabled is False,
    otherwise acts like a regular ModelIterable.
    """

    queryset: "PolymorphicQuerySet[_All, _Base]"

    def __iter__(self) -> Iterator[_All]:
        base_iter = super().__iter__()
        if self.queryset.polymorphic_disabled:
            return base_iter
        return self._polymorphic_iterator(base_iter)

    def _polymorphic_iterator(self, base_iter: Iterator[_All]) -> Iterator[_All]:
        sql_chunk = self.queryset._polymorphic_chunk_size(
            chunked_fetch=self.chunked_fetch,
            chunk_size=self.chunk_size,
        )

        while True:
            base_result_objects = []
            reached_end = False

            for _ in range(sql_chunk):
                try:
                    o = next(base_iter)
                    base_result_objects.append(o)
                except StopIteration:
                    reached_end = True
                    break

            yield from self.queryset._get_real_instances(base_result_objects)

            if reached_end:
                return


def transmogrify(cls: type[_All], obj: models.Model) -> _All:
    """
    Upcast a class to a different type without asking questions.
    """
    if "__init__" not in obj.__class__.__dict__:
        new = obj
        new.__class__ = cls
        return cast(_All, new)
    else:
        new = cls()
        for k, v in obj.__dict__.items():
            new.__dict__[k] = v  # pyright: ignore[reportIndexIssue]
        return new


class PolymorphicQuerySet(QuerySet[_All], Generic[_All, _Base]):
    """
    QuerySet for PolymorphicModel

    Contains the core functionality for PolymorphicModel

    Usually not explicitly needed, except if a custom queryset class
    is to be used.
    """

    polymorphic_disabled: bool
    polymorphic_deferred_loading: tuple[set[str], bool]

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._iterable_class = PolymorphicModelIterable

        self.polymorphic_disabled = False
        self.polymorphic_deferred_loading = (set(), True)

    def _clone(self, *args: Any, **kwargs: Any) -> Self:
        new = cast(Self, super()._clone(*args, **kwargs))  # type: ignore[misc]
        new.polymorphic_disabled = self.polymorphic_disabled
        new.polymorphic_deferred_loading = (
            copy.copy(self.polymorphic_deferred_loading[0]),
            self.polymorphic_deferred_loading[1],
        )
        return new

    @classmethod
    def as_manager(cls) -> models.Manager[_All]:
        """
        Override base :meth:`~django.db.models.query.QuerySet.as_manager` to return
        a manager extended from :class:`polymorphic.managers.PolymorphicManager`.
        """

        from .managers import PolymorphicManager

        manager = PolymorphicManager[_All, _Base].from_queryset(cls)()
        setattr(manager, "_built_with_as_manager", True)
        return manager

    as_manager.queryset_only = True  # type: ignore[attr-defined]

    def bulk_create(
        self,
        objs: Iterable[_All],
        batch_size: int | None = None,
        ignore_conflicts: bool = False,
        update_conflicts: bool = False,
        update_fields: Collection[str] | None = None,
        unique_fields: Collection[str] | None = None,
    ) -> list[_All]:
        objs = list(objs)
        for obj in objs:
            obj.pre_save_polymorphic()
        return super().bulk_create(objs, batch_size, ignore_conflicts=ignore_conflicts)

    def non_polymorphic(self) -> PolymorphicQuerySet[_Base, _Base]:
        qs = self._clone()
        qs.polymorphic_disabled = True
        if issubclass(qs._iterable_class, PolymorphicModelIterable):
            qs._iterable_class = ModelIterable
        return cast(PolymorphicQuerySet[_Base, _Base], qs)

    @overload
    def instance_of(self, __a: type[_A], /) -> PolymorphicQuerySet[_A, _Base]: ...

    @overload
    def instance_of(
        self, __a: type[_A], __b: type[_B], /
    ) -> PolymorphicQuerySet[_A | _B, _Base]: ...

    @overload
    def instance_of(
        self, __a: type[_A], __b: type[_B], __c: type[_C], /
    ) -> PolymorphicQuerySet[_A | _B | _C, _Base]: ...

    @overload
    def instance_of(
        self, __a: type[_A], __b: type[_B], __c: type[_C], __d: type[_D], /
    ) -> PolymorphicQuerySet[_A | _B | _C | _D, _Base]: ...

    @overload
    def instance_of(self, *args: type["PolymorphicModel"]) -> PolymorphicQuerySet[_All, _Base]: ...

    def instance_of(
        self, *args: type["PolymorphicModel"]
    ) -> PolymorphicQuerySet["PolymorphicModel", _Base]:
        return self.filter(instance_of=args)

    def not_instance_of(self, *args: type["PolymorphicModel"]) -> Self:
        return self.filter(not_instance_of=args)

    def _filter_or_exclude(self, negate: bool, args: Any, kwargs: Any) -> Self:
        q_objects = translate_polymorphic_filter_definitions_in_args(
            queryset_model=self.model, args=args, using=self.db
        )
        additional_args = translate_polymorphic_filter_definitions_in_kwargs(
            queryset_model=self.model, kwargs=kwargs, using=self.db
        )
        args = list(q_objects) + additional_args
        return cast(Self, super()._filter_or_exclude(negate=negate, args=args, kwargs=kwargs))  # type: ignore[misc]

    def order_by(self, *field_names: str | Combinable) -> Self:
        translated_fields = [
            translate_polymorphic_field_path(self.model, a)
            if isinstance(a, str)
            else a
            for a in field_names
        ]
        return super().order_by(*translated_fields)

    @overload
    def defer(self, field: None, /) -> Self: ...
    @overload
    def defer(self, *fields: str) -> Self: ...
    def defer(self, *fields: str | None) -> Self:
        str_fields = tuple(f for f in fields if f is not None)
        if str_fields:
            new_fields = tuple(translate_polymorphic_field_path(self.model, a) for a in str_fields)
            clone = super().defer(*new_fields)
            clone._polymorphic_add_deferred_loading(str_fields)
        else:
            clone = super().defer(None)
        return clone

    def only(self, *fields: str) -> Self:
        new_fields = {translate_polymorphic_field_path(self.model, a) for a in fields}
        new_fields.add("polymorphic_ctype_id")
        clone = super().only(*new_fields)
        clone._polymorphic_add_immediate_loading(fields)
        return clone

    def _polymorphic_add_deferred_loading(self, field_names: Iterable[str]) -> None:
        existing, defer = self.polymorphic_deferred_loading
        if defer:
            self.polymorphic_deferred_loading = existing.union(field_names), True
        else:
            self.polymorphic_deferred_loading = existing.difference(field_names), False

    def _polymorphic_add_immediate_loading(self, field_names: Iterable[str]) -> None:
        existing, defer = self.polymorphic_deferred_loading
        field_names = set(field_names)
        if "pk" in field_names:
            field_names.remove("pk")
            field_names.add(self.model._meta.pk.name)

        if defer:
            self.polymorphic_deferred_loading = field_names.difference(existing), False
        else:
            self.polymorphic_deferred_loading = field_names, False

    def _process_aggregate_args(self, args: Sequence[Any], kwargs: dict[str, Any]) -> None:
        ___lookup_assert_msg = "PolymorphicModel: annotate()/aggregate(): ___ model lookup supported for keyword arguments only"

        def patch_lookup(a):
            if isinstance(a, Q):
                a.children = translate_polymorphic_Q_object(self.model, a).children
            elif isinstance(a, FilteredRelation):
                patch_lookup(a.condition)
            elif isinstance(a, models.F):
                a.name = translate_polymorphic_field_path(self.model, a.name)  # type: ignore[attr-defined]
            elif hasattr(a, "get_source_expressions"):
                for source_expression in a.get_source_expressions():
                    if source_expression is not None:
                        patch_lookup(source_expression)
            else:
                a.name = translate_polymorphic_field_path(self.model, a.name)

        def test___lookup(a):
            if isinstance(a, Q):

                def tree_node_test___lookup(my_model, node):
                    for i in range(len(node.children)):
                        child = node.children[i]

                        if type(child) is tuple:
                            assert "___" not in child[0], ___lookup_assert_msg
                        else:
                            tree_node_test___lookup(my_model, child)

                tree_node_test___lookup(self.model, a)
            elif hasattr(a, "get_source_expressions"):
                for source_expression in a.get_source_expressions():
                    if source_expression is not None:
                        test___lookup(source_expression)
            else:
                assert "___" not in a.name, ___lookup_assert_msg

        for a in args:
            test___lookup(a)
        for a in kwargs.values():
            patch_lookup(a)

    def annotate(self, *args: Any, **kwargs: Any) -> Self:
        self._process_aggregate_args(args, kwargs)
        return super().annotate(*args, **kwargs)

    def aggregate(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        self._process_aggregate_args(args, kwargs)
        qs = self.non_polymorphic()
        return super(PolymorphicQuerySet, qs).aggregate(*args, **kwargs)

    def _values(self, *args: Any, **kwargs: Any) -> Self:
        clone = cast(Self, super()._values(*args, **kwargs))  # type: ignore[misc]
        clone.polymorphic_disabled = True
        return clone

    def _polymorphic_chunk_size(self, chunked_fetch: bool, chunk_size: int | None) -> int:
        max_chunk = connections[self.db].features.max_query_params
        sql_chunk = chunk_size if chunked_fetch else None
        if max_chunk:
            sql_chunk = (
                max_chunk
                if not chunked_fetch
                else min(max_chunk, chunk_size or max_chunk)
            )
        return sql_chunk or Polymorphic_QuerySet_objects_per_request

    def _copy_related_caches(self, source: _All, target: _All) -> None:
        source_fields_cache = getattr(source._state, "fields_cache", None)
        target_fields_cache = getattr(target._state, "fields_cache", None)
        if source_fields_cache and target_fields_cache is not None:
            target_fields_cache.update(source_fields_cache)

        source_prefetched_cache = getattr(source, "_prefetched_objects_cache", None)
        if source_prefetched_cache:
            target._prefetched_objects_cache = dict(source_prefetched_cache)

    def _get_real_instances(self, base_result_objects: Sequence[_All]) -> list[_All]:
        resultlist: list[Any] = []
        idlist_per_model: defaultdict[Any, list[Any]] = defaultdict(list)
        indexlist_per_model: defaultdict[Any, list[tuple[int, int]]] = defaultdict(list)
        classes_to_query: list[tuple[int, Any]] = []
        pk_name = self.model._meta.pk.attname

        content_type_manager = ContentType.objects.db_manager(self.db)
        self_model_class_id = content_type_manager.get_for_model(
            self.model, for_concrete_model=False
        ).pk
        self_concrete_model_class_id = content_type_manager.get_for_model(
            self.model, for_concrete_model=True
        ).pk

        class_priorities = {
            mdl: idx + 1
            for idx, mdl in enumerate((*reversed(concrete_descendants(self.model)), self.model))
        }

        for i, base_object in enumerate(base_result_objects):
            if base_object.polymorphic_ctype_id == self_model_class_id:
                resultlist.append(base_object)
            else:
                real_concrete_class = base_object.get_real_instance_class()
                real_concrete_class_id = base_object.get_real_concrete_instance_class_id()

                if real_concrete_class_id is None:
                    continue
                elif real_concrete_class_id == self_concrete_model_class_id:
                    upcasted_object = transmogrify(
                        cast("type[PolymorphicModel]", real_concrete_class), base_object
                    )
                    self._copy_related_caches(base_object, upcasted_object)
                    resultlist.append(upcasted_object)
                else:
                    real_concrete_class = cast(
                        "type[_All] | None",
                        content_type_manager.get_for_id(real_concrete_class_id).model_class(),
                    )
                    if real_concrete_class is not None:
                        if real_concrete_class not in idlist_per_model:
                            heapq.heappush(
                                classes_to_query,
                                (
                                    class_priorities.get(real_concrete_class, 0),
                                    real_concrete_class,
                                ),
                            )
                        idlist_per_model[real_concrete_class].append(getattr(base_object, pk_name))
                        indexlist_per_model[real_concrete_class].append((i, len(resultlist)))
                    resultlist.append(None)

        while classes_to_query:
            _, real_concrete_class = heapq.heappop(classes_to_query)
            assert real_concrete_class is not None
            idlist = idlist_per_model.pop(real_concrete_class)
            indices = indexlist_per_model.pop(real_concrete_class)
            real_objects = real_concrete_class._base_objects.db_manager(self.db).filter(
                **{(f"{pk_name}__in"): idlist}
            )
            real_objects.query.select_related = self.query.select_related

            deferred_loading_fields = []
            existing_fields = self.polymorphic_deferred_loading[0]
            for field in existing_fields:
                try:
                    translated_field_name = translate_polymorphic_field_path(
                        real_concrete_class, field
                    )
                except AssertionError:
                    if "___" in field:
                        translated_field_name = field.rpartition("___")[-1]
                        try:
                            real_concrete_class._meta.get_field(translated_field_name)
                        except FieldDoesNotExist:
                            continue
                    else:
                        raise

                deferred_loading_fields.append(translated_field_name)
            real_objects.query.deferred_loading = (
                set(deferred_loading_fields),
                self.query.deferred_loading[1],
            )

            real_objects_dict = {
                getattr(real_object, pk_name): real_object for real_object in real_objects
            }

            for base_idx, result_idx in indices:
                base_object = base_result_objects[base_idx]
                o_pk = getattr(base_object, pk_name)
                real_object = real_objects_dict.get(o_pk)
                if real_object is None:
                    inheritance_path = route_to_ancestor(real_concrete_class, self.model)
                    if not inheritance_path or inheritance_path[0].model is self.model:
                        resultlist[result_idx] = base_object
                    else:
                        next_best_class = inheritance_path[0].model
                        if next_best_class not in idlist_per_model:
                            heapq.heappush(
                                classes_to_query,
                                (class_priorities.get(next_best_class, 0), next_best_class),
                            )
                        idlist_per_model[next_best_class].append(o_pk)
                        indexlist_per_model[next_best_class].append((base_idx, result_idx))
                        resultlist[result_idx] = _Inconsistent
                    continue

                real_object = copy.copy(real_object)
                real_class = (
                    real_concrete_class
                    if resultlist[result_idx] is _Inconsistent
                    else real_object.get_real_instance_class()
                )

                if real_class != real_concrete_class:
                    real_object = transmogrify(
                        cast("type[PolymorphicModel]", real_class), real_object
                    )

                self._copy_related_caches(base_object, real_object)

                if self.query.annotations:
                    annotation_select = getattr(
                        self.query, "annotation_select", self.query.annotations
                    )
                    for anno_field_name in annotation_select.keys():
                        if hasattr(base_object, anno_field_name):
                            attr = getattr(base_object, anno_field_name)
                            setattr(real_object, anno_field_name, attr)

                if self.query.extra_select:
                    for select_field_name in self.query.extra_select.keys():
                        attr = getattr(base_object, select_field_name)
                        setattr(real_object, select_field_name, attr)

                resultlist[result_idx] = real_object

        resultlist = [i for i in resultlist if i and i is not _Inconsistent]

        if self.query.annotations:
            annotation_select = getattr(self.query, "annotation_select", self.query.annotations)
            annotate_names = list(annotation_select.keys())
            for real_object in resultlist:
                real_object.polymorphic_annotate_names = annotate_names

        if self.query.extra_select:
            extra_select_names = list(self.query.extra_select.keys())
            for real_object in resultlist:
                real_object.polymorphic_extra_select_names = extra_select_names

        return resultlist

    async def _aget_real_instances(self, base_result_objects: Sequence[_All]) -> list[_All]:
        resultlist: list[Any] = []
        idlist_per_model: defaultdict[Any, list[Any]] = defaultdict(list)
        indexlist_per_model: defaultdict[Any, list[tuple[int, int]]] = defaultdict(list)
        classes_to_query: list[tuple[int, Any]] = []
        pk_name = self.model._meta.pk.attname

        content_type_manager = ContentType.objects.db_manager(self.db)
        self_model_class_id = content_type_manager.get_for_model(
            self.model, for_concrete_model=False
        ).pk
        self_concrete_model_class_id = content_type_manager.get_for_model(
            self.model, for_concrete_model=True
        ).pk

        class_priorities = {
            mdl: idx + 1
            for idx, mdl in enumerate((*reversed(concrete_descendants(self.model)), self.model))
        }

        for i, base_object in enumerate(base_result_objects):
            if base_object.polymorphic_ctype_id == self_model_class_id:
                resultlist.append(base_object)
            else:
                real_concrete_class = base_object.get_real_instance_class()
                real_concrete_class_id = base_object.get_real_concrete_instance_class_id()

                if real_concrete_class_id is None:
                    continue
                elif real_concrete_class_id == self_concrete_model_class_id:
                    upcasted_object = transmogrify(
                        cast("type[PolymorphicModel]", real_concrete_class), base_object
                    )
                    self._copy_related_caches(base_object, upcasted_object)
                    resultlist.append(upcasted_object)
                else:
                    real_concrete_class = cast(
                        "type[_All] | None",
                        content_type_manager.get_for_id(real_concrete_class_id).model_class(),
                    )
                    if real_concrete_class is not None:
                        if real_concrete_class not in idlist_per_model:
                            heapq.heappush(
                                classes_to_query,
                                (
                                    class_priorities.get(real_concrete_class, 0),
                                    real_concrete_class,
                                ),
                            )
                        idlist_per_model[real_concrete_class].append(getattr(base_object, pk_name))
                        indexlist_per_model[real_concrete_class].append((i, len(resultlist)))
                    resultlist.append(None)

        while classes_to_query:
            _, real_concrete_class = heapq.heappop(classes_to_query)
            assert real_concrete_class is not None
            idlist = idlist_per_model.pop(real_concrete_class)
            indices = indexlist_per_model.pop(real_concrete_class)
            real_objects = real_concrete_class._base_objects.db_manager(self.db).filter(
                **{(f"{pk_name}__in"): idlist}
            )
            real_objects.query.select_related = self.query.select_related

            deferred_loading_fields = []
            existing_fields = self.polymorphic_deferred_loading[0]
            for field in existing_fields:
                try:
                    translated_field_name = translate_polymorphic_field_path(
                        real_concrete_class, field
                    )
                except AssertionError:
                    if "___" in field:
                        translated_field_name = field.rpartition("___")[-1]
                        try:
                            real_concrete_class._meta.get_field(translated_field_name)
                        except FieldDoesNotExist:
                            continue
                    else:
                        raise

                deferred_loading_fields.append(translated_field_name)
            real_objects.query.deferred_loading = (
                set(deferred_loading_fields),
                self.query.deferred_loading[1],
            )

            real_objects_dict = {}
            async for real_object in real_objects.aiterator(
                chunk_size=self._polymorphic_chunk_size(True, len(idlist) or None)
            ):
                real_objects_dict[getattr(real_object, pk_name)] = real_object

            for base_idx, result_idx in indices:
                base_object = base_result_objects[base_idx]
                o_pk = getattr(base_object, pk_name)
                real_object = real_objects_dict.get(o_pk)
                if real_object is None:
                    inheritance_path = route_to_ancestor(real_concrete_class, self.model)
                    if not inheritance_path or inheritance_path[0].model is self.model:
                        resultlist[result_idx] = base_object
                    else:
                        next_best_class = inheritance_path[0].model
                        if next_best_class not in idlist_per_model:
                            heapq.heappush(
                                classes_to_query,
                                (class_priorities.get(next_best_class, 0), next_best_class),
                            )
                        idlist_per_model[next_best_class].append(o_pk)
                        indexlist_per_model[next_best_class].append((base_idx, result_idx))
                        resultlist[result_idx] = _Inconsistent
                    continue

                real_object = copy.copy(real_object)
                real_class = (
                    real_concrete_class
                    if resultlist[result_idx] is _Inconsistent
                    else real_object.get_real_instance_class()
                )

                if real_class != real_concrete_class:
                    real_object = transmogrify(
                        cast("type[PolymorphicModel]", real_class), real_object
                    )

                self._copy_related_caches(base_object, real_object)

                if self.query.annotations:
                    annotation_select = getattr(
                        self.query, "annotation_select", self.query.annotations
                    )
                    for anno_field_name in annotation_select.keys():
                        if hasattr(base_object, anno_field_name):
                            attr = getattr(base_object, anno_field_name)
                            setattr(real_object, anno_field_name, attr)

                if self.query.extra_select:
                    for select_field_name in self.query.extra_select.keys():
                        attr = getattr(base_object, select_field_name)
                        setattr(real_object, select_field_name, attr)

                resultlist[result_idx] = real_object

        resultlist = [i for i in resultlist if i and i is not _Inconsistent]

        if self.query.annotations:
            annotation_select = getattr(self.query, "annotation_select", self.query.annotations)
            annotate_names = list(annotation_select.keys())
            for real_object in resultlist:
                real_object.polymorphic_annotate_names = annotate_names

        if self.query.extra_select:
            extra_select_names = list(self.query.extra_select.keys())
            for real_object in resultlist:
                real_object.polymorphic_extra_select_names = extra_select_names

        return resultlist

    async def _yield_real_instances(self, base_result_objects: Sequence[_All]) -> AsyncIterator[_All]:
        real_objects = await self._aget_real_instances(base_result_objects)
        if self._prefetch_related_lookups and aprefetch_related_objects is not None:
            await aprefetch_related_objects(real_objects, *self._prefetch_related_lookups)
        for real_object in real_objects:
            yield real_object

    async def aiterator(self, chunk_size: int = Polymorphic_QuerySet_objects_per_request):
        if chunk_size <= 0:
            raise ValueError("Chunk size must be strictly positive.")
        if self.polymorphic_disabled:
            async for obj in super().aiterator(chunk_size=chunk_size):
                yield obj
            return

        base_chunk_size = self._polymorphic_chunk_size(True, chunk_size)
        base_qs = self.non_polymorphic()
        base_result_objects: list[_All] = []

        async for base_object in super(PolymorphicQuerySet, base_qs).aiterator(chunk_size=chunk_size):
            base_result_objects.append(base_object)
            if len(base_result_objects) >= base_chunk_size:
                async for real_object in self._yield_real_instances(base_result_objects):
                    yield real_object
                base_result_objects = []

        if base_result_objects:
            async for real_object in self._yield_real_instances(base_result_objects):
                yield real_object

    def __aiter__(self) -> AsyncIterator[_All]:
        async def generator() -> AsyncIterator[_All]:
            if self._result_cache is None:
                self._result_cache = []
                async for item in self.aiterator():
                    self._result_cache.append(item)
                self._prefetch_done = True
            for item in self._result_cache:
                yield item

        return generator()

    async def aget(self, *args: Any, **kwargs: Any) -> _All:
        if self.query.combinator and (args or kwargs):
            raise NotSupportedError(
                f"Calling QuerySet.get(...) with filters after {self.query.combinator}() is not supported."
            )

        clone = self._chain() if self.query.combinator else self.filter(*args, **kwargs)
        if clone.query.can_filter() and not clone.query.distinct_fields:
            clone = clone.order_by()
        clone.query.set_limits(high=MAX_GET_RESULTS)

        results: list[_All] = []
        async for obj in clone.aiterator(chunk_size=min(MAX_GET_RESULTS, Polymorphic_QuerySet_objects_per_request)):
            results.append(obj)

        num = len(results)
        if num == 1:
            return results[0]
        if num == 0:
            raise self.model.DoesNotExist(
                "%s matching query does not exist." % self.model._meta.object_name
            )

        limit_text = (
            str(num)
            if num < MAX_GET_RESULTS
            else "more than %s" % (MAX_GET_RESULTS - 1)
        )
        raise self.model.MultipleObjectsReturned(
            "get() returned more than one %s -- it returned %s!"
            % (self.model._meta.object_name, limit_text)
        )

    async def afirst(self) -> _All | None:
        queryset = self if self.ordered else self.order_by("pk")
        async for obj in queryset[:1].aiterator(chunk_size=1):
            return obj
        return None

    async def alast(self) -> _All | None:
        queryset = self.reverse() if self.ordered else self.order_by("-pk")
        async for obj in queryset[:1].aiterator(chunk_size=1):
            return obj
        return None

    async def acount(self) -> int:
        if self._result_cache is not None:
            return len(self._result_cache)
        return await super().acount()

    async def aexists(self) -> bool:
        if self._result_cache is not None:
            return bool(self._result_cache)
        return await super().aexists()

    async def aupdate(self, **kwargs: Any) -> int:
        return await super().aupdate(**kwargs)

    def __repr__(self, *args, **kwargs):
        if self.model.polymorphic_query_multiline_output:
            result = ",\n  ".join(repr(o) for o in self.all())
            return f"[ {result} ]"
        else:
            return super().__repr__(*args, **kwargs)

    class _p_list_class(list[Any]):
        def __repr__(self, *args: Any, **kwargs: Any) -> str:
            result = ",\n  ".join(repr(o) for o in self)
            return f"[ {result} ]"

    def get_real_instances(self, base_result_objects: Iterable[_All] | None = None) -> list[_All]:
        if base_result_objects is None:
            base_result_objects = cast(Iterable[_All], self)
        base_result_list: Sequence[_All]
        if not isinstance(base_result_objects, list):
            base_result_list = list(base_result_objects)
        else:
            base_result_list = base_result_objects
        olist = self._get_real_instances(base_result_list)
        if not self.model.polymorphic_query_multiline_output:
            return olist
        clist = PolymorphicQuerySet._p_list_class(olist)
        return clist

    def delete(self) -> tuple[int, dict[str, int]]:
        return QuerySet.delete(self.non_polymorphic())


PolymorphicQuerySet.aupdate.alters_data = True
PolymorphicQuerySet.aupdate.queryset_only = False