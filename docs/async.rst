Async ORM Support
=================

django-polymorphic provides native async queryset support for the polymorphic
operations that materialize model instances:

* :meth:`~polymorphic.managers.PolymorphicQuerySet.aget`
* :meth:`~polymorphic.managers.PolymorphicQuerySet.afirst`
* :meth:`~polymorphic.managers.PolymorphicQuerySet.alast`
* :meth:`~polymorphic.managers.PolymorphicQuerySet.aiterator`
* :meth:`~polymorphic.managers.PolymorphicQuerySet.acount`
* :meth:`~polymorphic.managers.PolymorphicQuerySet.aexists`
* :meth:`~polymorphic.managers.PolymorphicQuerySet.aupdate`
* ``async for`` iteration on polymorphic querysets

The async APIs preserve the same downcast behavior as the synchronous queryset.
When a queryset is evaluated from the base model, the yielded objects are still
returned as their concrete subclasses.

Examples
--------

.. code-block:: python

    project = await Project.objects.aget(pk=1)

    first_project = await Project.objects.instance_of(ArtProject).afirst()

    async for project in Project.objects.not_instance_of(ArchivedProject).order_by("pk"):
        print(project.__class__.__name__, project.pk)

Filters and queryset combinations
--------------------------------

The async queryset methods support the same polymorphic filters and queryset
composition features as the synchronous APIs:

.. code-block:: python

    qs = Project.objects.instance_of(ArtProject, ResearchProject)
    archived = Project.objects.not_instance_of(LiveProject)

    async for project in qs.union(archived).order_by("pk"):
        ...

    async for project in qs.intersection(archived).order_by("pk"):
        ...

Related object loading
----------------------

``select_related()`` and ``prefetch_related()`` remain available with async
queries. Related-object caches are preserved across polymorphic downcasting, so
subclass instances keep the same eager-loading behavior as the corresponding
synchronous queryset.

.. code-block:: python

    invoice = await Invoice.objects.select_related("customer").aget(pk=1)
    customer = invoice.customer

    async for order in Order.objects.prefetch_related("items").order_by("pk"):
        print(len(order.items.all()))

Multi-database routing
----------------------

Async queryset evaluation respects the configured database alias. Calls made via
``using()`` or ``db_manager()`` continue to fetch :class:`~django.contrib.contenttypes.models.ContentType`
records, base rows, and subclass rows from the same database.

Compatibility
-------------

The async queryset support is tested across Django 4.2, 5.2, and 6.0, and runs
inside the existing SQLite, PostgreSQL, and MySQL CI matrix.
