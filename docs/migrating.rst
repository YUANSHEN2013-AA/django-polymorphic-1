Migrating Existing Models
=========================

Existing models can be migrated to become polymorphic models. During migration, the
:attr:`~polymorphic.models.PolymorphicModel.polymorphic_ctype` field needs to be populated.

This can be done in the following steps:

#. Inherit your model from :class:`~polymorphic.models.PolymorphicModel`.
#. Create a Django migration file to create the ``polymorphic_ctype_id`` database column.
#. Make sure the proper :class:`~django.contrib.contenttypes.models.ContentType` value is filled in.

Filling the content type value
------------------------------

The following code can be used to fill the value of a model:

.. code-block:: python

    from django.contrib.contenttypes.models import ContentType
    from myapp.models import MyModel

    new_ct = ContentType.objects.get_for_model(MyModel)
    MyModel.objects.filter(polymorphic_ctype__isnull=True).update(polymorphic_ctype=new_ct)

The creation and update of the ``polymorphic_ctype_id`` column can be included in a single Django
migration. For example:

.. code-block:: python

    # -*- coding: utf-8 -*-
    from django.db import migrations, models


    def forwards_func(apps, schema_editor):
        MyModel = apps.get_model('myapp', 'MyModel')
        ContentType = apps.get_model('contenttypes', 'ContentType')

        new_ct = ContentType.objects.get_for_model(MyModel)
        MyModel.objects.filter(polymorphic_ctype__isnull=True).update(
            polymorphic_ctype=new_ct
        )


    class Migration(migrations.Migration):

        dependencies = [
            ('contenttypes', '0001_initial'),
            ('myapp', '0001_initial'),
        ]

        operations = [
            migrations.AddField(
                model_name='mymodel',
                name='polymorphic_ctype',
                field=models.ForeignKey(
                    related_name='polymorphic_myapp.mymodel_set+',
                    editable=False,
                    to='contenttypes.ContentType',
                    null=True
                ),
            ),
            migrations.RunPython(forwards_func, migrations.RunPython.noop),
        ]

It's recommended to let :django-admin:`makemigrations` create the migration file, and include the
:class:`~django.db.migrations.operations.RunPython` manually before running the migration.

.. versionadded:: 1.1

When the model is created elsewhere, you can also use the
:func:`~polymorphic.utils.reset_polymorphic_ctype` function:

.. code-block:: python

    from polymorphic.utils import reset_polymorphic_ctype
    from myapp.models import Base, Sub1, Sub2

    reset_polymorphic_ctype(Base, Sub1, Sub2)

    reset_polymorphic_ctype(Base, Sub1, Sub2, ignore_existing=True)

Upgrading to Async QuerySets
---------------------------

No public API changes are required to start using the async queryset methods.
Existing polymorphic managers and querysets continue to work with the same
``instance_of()`` and ``not_instance_of()`` filters, queryset cloning, related
loading, and multi-database routing behavior.

When moving existing code to async views or tasks:

#. Replace blocking queryset evaluation with the async variants such as
   ``aget()``, ``afirst()``, ``alast()``, ``aiterator()``, ``acount()``,
   ``aexists()``, and ``aupdate()``.
#. Replace synchronous iteration with ``async for`` where the queryset itself is
   consumed.
#. Keep the same eager-loading calls. ``select_related()`` and
   ``prefetch_related()`` preserve polymorphic downcasting when used with async
   queryset evaluation.
#. Keep the same database selection calls. ``using()`` and ``db_manager()``
   continue to route base-model, subclass, and content-type queries to the same
   database alias.

Example migration:

.. code-block:: python

    project = await Project.objects.instance_of(ArtProject).aget(pk=project_id)

    async for project in Project.objects.not_instance_of(ArchivedProject).order_by("pk"):
        ...

The async implementation is covered by the existing SQLite, PostgreSQL, and
MySQL test matrix for Django 4.2, 5.2, and 6.0.
