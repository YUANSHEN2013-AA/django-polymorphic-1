.. _async-orm:

Async ORM Support
=================

django-polymorphic fully supports Django's async ORM interface.
All polymorphic querysets and managers expose async variants of the
common query methods, preserving polymorphic downcast behavior.


Quick Example
-------------

.. code-block:: python

    async def list_projects():
        async for obj in Project.objects.all().aiterator():
            print(type(obj))  # ArtProject, ResearchProject, etc.

    async def get_project(pk):
        return await Project.objects.aget(pk=pk)  # Returns concrete type

    async def count_art_projects():
        return await Project.objects.instance_of(ArtProject).acount()


Async Methods
-------------

All methods are direct async implementations (NOT ``sync_to_async`` wrappers
of the synchronous versions). The following async methods are available:

``aiterator()``
~~~~~~~~~~~~~~~~

Yields polymorphically downcast model instances asynchronously:

.. code-block:: python

    async for obj in Project.objects.all().aiterator():
        process(obj)

    async for obj in Project.objects.instance_of(ArtProject).aiterator():
        process(obj)

**Parameters:**

* ``chunk_size``: Number of base objects to fetch per database round-trip.
  Defaults to ``Polymorphic_QuerySet_objects_per_request``, capped by
  ``connections[self.db].features.max_query_params``.

**Notes:**

* Respects ``select_related`` queries and ``defer``/``only`` field selections
* Applies polymorphic downcasting in a single batch per chunk
* Iterates in ascending primary key order

``aget(*args, **kwargs)``
~~~~~~~~~~~~~~~~~~~~~~~~~

Returns a single polymorphically downcast model instance:

.. code-block:: python

    obj = await Project.objects.aget(pk=1)
    # obj is ArtProject, ResearchProject, etc.

    obj = await Project.objects.instance_of(ArtProject).aget(pk=2)
    # obj is guaranteed to be ArtProject

``afirst()``
~~~~~~~~~~~~~

Returns the first matching polymorphically downcast object, or ``None``:

.. code-block:: python

    first = await Project.objects.afirst()

``alast()``
~~~~~~~~~~~~

Returns the last matching polymorphically downcast object, or ``None``:

.. code-block:: python

    last = await Project.objects.alast()

``acount()``
~~~~~~~~~~~~~

Returns the number of objects in the queryset, respecting ``instance_of``
and ``not_instance_of`` filters:

.. code-block:: python

    total = await Project.objects.acount()
    art_count = await Project.objects.instance_of(ArtProject).acount()

``aexists()``
~~~~~~~~~~~~~

Returns ``True`` if the queryset has results:

.. code-block:: python

    if await Project.objects.filter(topic="AI").aexists():
        ...

``aupdate(**kwargs)``
~~~~~~~~~~~~~~~~~~~~~

Updates all matching objects and returns the count:

.. code-block:: python

    updated = await Project.objects.instance_of(ArtProject).aupdate(
        topic="Updated Art"
    )


Manager Proxy
-------------

The :class:`~polymorphic.managers.PolymorphicManager` exposes all async
methods directly, so you can call them without ``.all()``:

.. code-block:: python

    # These are equivalent:
    await Project.objects.aget(pk=1)
    await Project.objects.all().aget(pk=1)


Filtering (instance_of / not_instance_of)
------------------------------------------

Async methods fully respect ``instance_of()`` and ``not_instance_of()``
filters, just like their synchronous counterparts:

.. code-block:: python

    # Only ArtProject and ResearchProject
    qs = Project.objects.instance_of(ArtProject, ResearchProject)
    count = await qs.acount()

    # Exclude ArtProject
    qs = Project.objects.not_instance_of(ArtProject)
    async for obj in qs.aiterator():
        ...


Union / Intersection
---------------------

Async operations work on union and intersection querysets:

.. code-block:: python

    qs1 = Project.objects.filter(topic__startswith="A")
    qs2 = Project.objects.filter(topic__startswith="B")
    union = qs1.union(qs2)
    count = await union.acount()


select_related / prefetch_related
----------------------------------

Both ``select_related`` and ``prefetch_related`` are respected during
async iteration:

.. code-block:: python

    # select_related: joins are preserved in the async iteration
    qs = Project.objects.select_related("related_model")
    async for obj in qs.aiterator():
        print(obj.related_model)

    # prefetch_related: prefetched relations are available
    qs = Project.objects.prefetch_related("related_set")
    async for obj in qs.aiterator():
        print(obj.related_set.all())


Cross-Database Routing
-----------------------

Async operations respect database routing:

.. code-block:: python

    qs = Project.objects.using("secondary")
    async for obj in qs.aiterator():
        ...


QuerySet Clone Logic
--------------------

All ``_clone`` operations preserve the polymorphic state
(``polymorphic_disabled``, ``polymorphic_deferred_loading``) ensuring
that chaining methods behave correctly:

.. code-block:: python

    qs = Project.objects.all().instance_of(ArtProject)
    cloned = qs.order_by("pk")
    # cloned still only returns ArtProject instances


Non-Polymorphic Mode
---------------------

You can disable polymorphic downcasting in async mode using
``non_polymorphic()``:

.. code-block:: python

    async for obj in Project.objects.non_polymorphic().aiterator():
        # All objects are base Project instances
        assert type(obj) == Project


Django Compatibility
---------------------

Async ORM support is compatible with all supported Django versions:

* Django 4.2
* Django 5.2
* Django 6.0


Performance Considerations
--------------------------

* Async iteration fetches objects in chunks and applies polymorphic
  downcasting within each chunk
* The chunk size can be tuned via the ``chunk_size`` parameter
* For small result sets, the overhead of chunking is minimal
* For large result sets, chunking improves memory efficiency

See :ref:`performance` for general performance guidance.


Upgrade Guide
-------------

No changes are required to existing synchronous code. Async support is
fully additive and backward compatible.

To start using async:

1. Ensure your Django version is 4.2 or higher
2. Use ``async`` function definitions where you call async methods
3. Use ``async for`` with ``aiterator()`` instead of ``for obj in qs``

Existing synchronous code continues to work without any changes.