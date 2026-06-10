import pytest
from django.contrib.contenttypes.models import ContentType

from pexp.models import (
    ArtProject,
    Project,
    ProxyA,
    ProxyB,
    ProxyBase,
    ResearchProject,
    TestModelA,
    TestModelB,
    TestModelC,
)

pytestmark = pytest.mark.django_db


def test_project_polymorphic_roundtrip_and_instance_of():
    base_project = Project.objects.create(topic="base topic")
    art_project = ArtProject.objects.create(topic="art topic", artist="Paul Klee")
    research_project = ResearchProject.objects.create(
        topic="research topic",
        supervisor="Marie Curie",
    )

    roundtrip = list(Project.objects.order_by("pk"))

    assert [obj.__class__ for obj in roundtrip] == [
        Project,
        ArtProject,
        ResearchProject,
    ]
    assert [obj.pk for obj in roundtrip] == [
        base_project.pk,
        art_project.pk,
        research_project.pk,
    ]

    art_project_base = Project.objects.non_polymorphic().get(pk=art_project.pk)
    real_instance = art_project_base.get_real_instance()

    assert art_project_base.__class__ is Project
    assert isinstance(real_instance, ArtProject)
    assert real_instance.topic == "art topic"
    assert real_instance.artist == "Paul Klee"

    assert list(Project.objects.instance_of(ArtProject).values_list("pk", flat=True)) == [
        art_project.pk
    ]
    assert list(
        Project.objects.instance_of(ArtProject, ResearchProject)
        .order_by("pk")
        .values_list("pk", flat=True)
    ) == [art_project.pk, research_project.pk]


def test_delete_keep_parents_true_upcasts_to_project():
    art_project = ArtProject.objects.create(topic="delete me", artist="Louise Bourgeois")

    deleted_count, deleted_map = art_project.delete(keep_parents=True)
    parent_project = Project.objects.non_polymorphic().get(pk=art_project.pk)

    assert deleted_count == 1
    assert deleted_map == {"pexp.ArtProject": 1}
    assert not ArtProject.objects.filter(pk=art_project.pk).exists()
    assert Project.objects.count() == 1
    assert parent_project.__class__ is Project
    assert parent_project.get_real_instance().__class__ is Project
    assert parent_project.polymorphic_ctype == ContentType.objects.get_for_model(Project)


def test_multi_table_roundtrip_preserves_related_objects():
    related_child = TestModelB.objects.create(field1="related", field2="child")
    nested_child = TestModelC.objects.create(field1="root", field2="branch", field3="leaf")
    nested_child.field4.add(related_child)

    nested_child_base = TestModelA.objects.non_polymorphic().get(pk=nested_child.pk)
    real_instance = nested_child_base.get_real_instance()

    assert nested_child_base.__class__ is TestModelA
    assert isinstance(real_instance, TestModelC)
    assert real_instance.field1 == "root"
    assert real_instance.field2 == "branch"
    assert real_instance.field3 == "leaf"
    assert list(real_instance.field4.values_list("pk", flat=True)) == [related_child.pk]


def test_proxy_models_roundtrip_and_unicode_methods():
    base_proxy = ProxyBase.objects.create(title="Gamma")
    proxy_a = ProxyA.objects.create(title="Alpha")
    proxy_b = ProxyB.objects.create(title="Beta")

    roundtrip = list(ProxyBase.objects.order_by("title"))

    assert [obj.__class__ for obj in roundtrip] == [ProxyA, ProxyB, ProxyBase]
    assert base_proxy.__unicode__().startswith("<ProxyBase[type=")
    assert proxy_a.__unicode__() == "<ProxyA: Alpha>"
    assert proxy_b.__unicode__() == "<ProxyB: Beta>"
