Async ORM Support
=================

As of the latest version, ``django-polymorphic`` provides complete and native Async ORM support.
All asynchronous queries return correctly downcasted polymorphic instances without relying on synchronous wrappers like ``sync_to_async``.

Supported Methods
-----------------

The ``PolymorphicQuerySet`` fully supports the following native async methods:

* ``aget()``
* ``afirst()``
* ``alast()``
* ``aiterator()``
* ``acount()``
* ``aexists()``
* ``aupdate()``

Usage
-----

You can use async methods directly on your polymorphic querysets. The models will be automatically and asynchronously downcasted to their real types:

.. code-block:: python

    # Get a specific object (returns ArtProject or ResearchProject asynchronously)
    project = await Project.objects.aget(topic="Painting with Tim")

    # Get the first project
    first_project = await Project.objects.afirst()

    # Iterate over projects asynchronously
    async for project in Project.objects.aiterator():
        print(project.topic)

    # Fast count without downcasting
    count = await Project.objects.acount()

Queryset Capabilities
---------------------

All async interfaces maintain complete polymorphic downcast behavior. In addition, they fully support:

* ``instance_of()`` and ``not_instance_of()`` filtering.
* Cross-database routing.
* ``select_related()`` and ``prefetch_related()``.
* QuerySet ``union()`` and ``intersection()``.
* Ensuring QuerySet clone logic remains unaffected.

Performance
-----------

The async implementation performs objects retrieval in chunks using async database drivers (supported in Django 4.2+), drastically improving performance for asynchronous workloads without blocking the event loop.

Upgrade Guide
-------------

If you previously used ``sync_to_async(list)(Project.objects.all())`` to evaluate polymorphic querysets asynchronously, you can now natively iterate over them:

.. code-block:: python

    # Old way (synchronous evaluation wrapped in thread)
    projects = await sync_to_async(list)(Project.objects.all())

    # New way (native async evaluation)
    projects = [project async for project in Project.objects.all()]
