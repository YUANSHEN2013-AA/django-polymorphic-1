"""
Pytest test coverage for the polymorphic models in pexp.models.

This module validates:
  * get_real_instance() / get_real_instance_class() behaviour
  * QuerySet.instance_of() / not_instance_of() filtering
  * delete(keep_parents=True) on polymorphic models
  * Multi-database round-trip behaviour (default + secondary).

The test harness uses polymorphic.tests.settings which configures two
databases (both SQLite by default, or both PostgreSQL when the RDBMS
environment variable is set to "postgres").
"""

from __future__ import annotations

import pytest

from pexp.models import (
    ArtProject,
    NormalModelA,
    NormalModelB,
    NormalModelC,
    Project,
    ProxyA,
    ProxyB,
    ProxyBase,
    ResearchProject,
    TestModelA,
    TestModelB,
    TestModelC,
    UUIDModelA,
    UUIDModelB,
    UUIDModelC,
)

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# Model introspection: the classes in pexp.models are really polymorphic
# ---------------------------------------------------------------------------


class TestPexpModelHierarchy:
    """Sanity-checks on the polymorphic / non-polymorphic model layout."""

    def test_polymorphic_marker_on_polymorphic_models(self):
        for model in (
            Project,
            ArtProject,
            ResearchProject,
            TestModelA,
            TestModelB,
            TestModelC,
            UUIDModelA,
            UUIDModelB,
            UUIDModelC,
            ProxyBase,
            ProxyA,
            ProxyB,
        ):
            assert model.polymorphic_model_marker is True

    def test_non_polymorphic_models_do_not_have_polymorphic_marker(self):
        for model in (NormalModelA, NormalModelB, NormalModelC):
            assert not getattr(model, "polymorphic_model_marker", False)

    @pytest.mark.parametrize(
        "parent,child",
        [
            (Project, ArtProject),
            (Project, ResearchProject),
            (TestModelA, TestModelB),
            (TestModelB, TestModelC),
            (UUIDModelA, UUIDModelB),
            (UUIDModelB, UUIDModelC),
            (ProxyBase, ProxyA),
            (ProxyBase, ProxyB),
        ],
    )
    def test_child_is_subclass_of_parent(self, parent, child):
        assert issubclass(child, parent)


# ---------------------------------------------------------------------------
# get_real_instance() and get_real_instance_class()
# ---------------------------------------------------------------------------


class TestGetRealInstance:
    def test_get_real_instance_class_returns_same_class_for_base(self):
        p = Project.objects.create(topic="Base")
        base = Project.objects.non_polymorphic().get(pk=p.pk)
        assert base.__class__ is Project
        assert base.get_real_instance_class() is Project

    def test_get_real_instance_class_returns_child_class(self):
        art = ArtProject.objects.create(topic="Art", artist="Alice")
        base = Project.objects.non_polymorphic().get(pk=art.pk)
        assert base.__class__ is Project
        assert base.get_real_instance_class() is ArtProject

    def test_get_real_instance_returns_actual_instance(self):
        research = ResearchProject.objects.create(topic="R&D", supervisor="Dr Bob")
        base = Project.objects.non_polymorphic().get(pk=research.pk)
        real = base.get_real_instance()
        assert real.__class__ is ResearchProject
        assert real.supervisor == "Dr Bob"
        assert real.pk == research.pk

    def test_get_real_instance_roundtrip_for_multiple_levels(self):
        c = TestModelC.objects.create(field1="1", field2="2", field3="3")
        base_a = TestModelA.objects.non_polymorphic().get(pk=c.pk)
        assert base_a.get_real_instance_class() is TestModelC
        assert base_a.get_real_instance().__class__ is TestModelC

        base_b = TestModelB.objects.non_polymorphic().get(pk=c.pk)
        assert base_b.get_real_instance_class() is TestModelC
        assert base_b.get_real_instance().field3 == "3"

    def test_get_real_instance_uuid_pk(self):
        import uuid

        pk = uuid.uuid4()
        c = UUIDModelC.objects.create(uuid_primary_key=pk, field1="u1", field2="u2", field3="u3")
        base_a = UUIDModelA.objects.non_polymorphic().get(uuid_primary_key=pk)
        assert base_a.get_real_instance().__class__ is UUIDModelC
        assert base_a.get_real_instance().field3 == "u3"
        assert base_a.get_real_instance().pk == pk

    def test_get_real_instance_on_self(self):
        """When the instance is already the real class, get_real_instance returns self."""
        p = Project.objects.create(topic="Same")
        real = p.get_real_instance()
        assert real is p
        assert real.pk == p.pk

    def test_get_real_concrete_instance_class_id(self):
        art = ArtProject.objects.create(topic="X", artist="Y")
        base = Project.objects.non_polymorphic().get(pk=art.pk)
        assert base.get_real_concrete_instance_class_id() is not None
        assert base.get_real_concrete_instance_class() is ArtProject


# ---------------------------------------------------------------------------
# instance_of / not_instance_of
# ---------------------------------------------------------------------------


class TestInstanceOf:
    def setup_method(self):
        Project.objects.create(topic="Plain")
        ArtProject.objects.create(topic="Art1", artist="Alice")
        ArtProject.objects.create(topic="Art2", artist="Bob")
        ResearchProject.objects.create(topic="R1", supervisor="S1")
        ResearchProject.objects.create(topic="R2", supervisor="S2")

    def test_instance_of_project_base_returns_all(self):
        assert Project.objects.instance_of(Project).count() == 5

    def test_instance_of_artproject_returns_only_art(self):
        qs = Project.objects.instance_of(ArtProject)
        assert qs.count() == 2
        assert {obj.__class__ for obj in qs} == {ArtProject}

    def test_instance_of_multiple_parents(self):
        qs = Project.objects.instance_of(ArtProject, ResearchProject)
        assert qs.count() == 4
        classes = {obj.__class__ for obj in qs}
        assert classes == {ArtProject, ResearchProject}

    def test_instance_of_filter_keyword_equivalent(self):
        via_method = Project.objects.instance_of(ArtProject)
        via_kwarg = Project.objects.filter(instance_of=ArtProject)
        assert set(via_method.values_list("pk", flat=True)) == set(
            via_kwarg.values_list("pk", flat=True)
        )

    def test_not_instance_of_excludes_classes(self):
        qs = Project.objects.not_instance_of(ArtProject)
        classes = {obj.__class__ for obj in qs}
        assert ArtProject not in classes
        assert Project in classes
        assert ResearchProject in classes

    def test_instance_of_mid_level_includes_children(self):
        a = TestModelA.objects.create(field1="a")
        b = TestModelB.objects.create(field1="b", field2="b2")
        c = TestModelC.objects.create(field1="c", field2="c2", field3="c3")

        qs = TestModelA.objects.instance_of(TestModelB)
        pks = set(qs.values_list("pk", flat=True))
        assert pks == {b.pk, c.pk}
        assert a.pk not in pks


# ---------------------------------------------------------------------------
# Proxy model support
# ---------------------------------------------------------------------------


class TestProxyModels:
    def setup_method(self):
        ProxyBase.objects.create(title="Plain proxy base")
        ProxyA.objects.create(title="Proxy A")
        ProxyB.objects.create(title="Proxy B")

    def test_proxy_instance_resolves_to_correct_class(self):
        a = ProxyA.objects.create(title="A2")
        base = ProxyBase.objects.non_polymorphic().get(pk=a.pk)
        assert base.get_real_instance_class() is ProxyA
        assert base.get_real_instance().__class__ is ProxyA

    def test_proxy_instance_of(self):
        qs = ProxyBase.objects.instance_of(ProxyA)
        for obj in qs:
            assert isinstance(obj, ProxyA)

    def test_proxy_manager_auto_filters(self):
        """Proxy models should restrict their default manager to their own class."""
        assert ProxyA.objects.count() >= 1
        for obj in ProxyA.objects.all():
            assert isinstance(obj, ProxyA)


# ---------------------------------------------------------------------------
# delete(keep_parents=True)
# ---------------------------------------------------------------------------


class TestDeleteKeepParents:
    def test_delete_child_keeps_parent_row(self):
        art = ArtProject.objects.create(topic="Art", artist="Alice")
        art_pk = art.pk

        art.delete(keep_parents=True)

        # The child row is gone
        assert ArtProject.objects.count() == 0
        # The parent row still exists and is now typed as Project
        assert Project.objects.count() == 1
        parent = Project.objects.get(pk=art_pk)
        assert parent.__class__ is Project
        assert parent.topic == "Art"

    def test_delete_child_on_multiple_levels(self):
        c = TestModelC.objects.create(field1="1", field2="2", field3="3")
        c_pk = c.pk

        c.delete(keep_parents=True)

        assert TestModelC.objects.count() == 0
        # The mid-level row should have been promoted to TestModelB
        b_row = TestModelB.objects.get(pk=c_pk)
        assert b_row.__class__ is TestModelB
        assert b_row.field2 == "2"

    def test_delete_base_instance_still_works(self):
        p = Project.objects.create(topic="plain")
        p_pk = p.pk
        p.delete()
        assert not Project.objects.filter(pk=p_pk).exists()

    def test_research_project_delete_keep_parents(self):
        r = ResearchProject.objects.create(topic="R", supervisor="S")
        r_pk = r.pk
        r.delete(keep_parents=True)
        assert ResearchProject.objects.count() == 0
        parent = Project.objects.get(pk=r_pk)
        assert parent.__class__ is Project


# ---------------------------------------------------------------------------
# Multi-database round trip behaviour
# ---------------------------------------------------------------------------


class TestMultiDatabaseRoundTrip:
    databases = {"default", "secondary"}

    def test_write_to_secondary_read_polymorphic(self):
        art = ArtProject.objects.db_manager("secondary").create(
            topic="Art2", artist="Alicia"
        )
        # Verify we can read it back on the secondary DB with the right class
        fetched = Project.objects.using("secondary").get(pk=art.pk)
        assert fetched.__class__ is ArtProject
        assert fetched.artist == "Alicia"

    def test_get_real_instance_on_secondary(self):
        research = ResearchProject.objects.db_manager("secondary").create(
            topic="R2", supervisor="Dr Charlie"
        )
        base = Project.objects.using("secondary").non_polymorphic().get(pk=research.pk)
        real = base.get_real_instance()
        assert real.__class__ is ResearchProject
        assert real.supervisor == "Dr Charlie"

    def test_instance_of_on_secondary(self):
        secondary = Project.objects.db_manager("secondary")
        secondary.create(topic="Base")
        ArtProject.objects.db_manager("secondary").create(topic="Art-db2", artist="D")
        ResearchProject.objects.db_manager("secondary").create(
            topic="Res-db2", supervisor="E"
        )
        count = Project.objects.using("secondary").instance_of(ArtProject).count()
        assert count >= 1

    def test_delete_keep_parents_on_secondary(self):
        art = ArtProject.objects.db_manager("secondary").create(
            topic="Art-db2-del", artist="G"
        )
        pk = art.pk
        Project.objects.using("secondary").get(pk=pk).delete(keep_parents=True)
        assert not ArtProject.objects.using("secondary").filter(pk=pk).exists()
        parent = Project.objects.using("secondary").get(pk=pk)
        assert parent.__class__ is Project
        assert parent.topic == "Art-db2-del"

    def test_cross_db_write_refreshes_ctype(self):
        """Saving a polymorphic instance to an explicit DB refreshes ctype on that DB."""
        art = ArtProject(topic="x", artist="y")
        art.save(using="secondary")
        base = Project.objects.using("secondary").non_polymorphic().get(pk=art.pk)
        assert base.polymorphic_ctype_id is not None
        assert base.get_real_instance_class() is ArtProject


# ---------------------------------------------------------------------------
# Round-trip verification: write → reload → modify → reload
# ---------------------------------------------------------------------------


class TestRoundTrip:
    def test_create_update_read(self):
        art = ArtProject.objects.create(topic="Painting", artist="Alice")
        art.topic = "New Painting"
        art.save()

        reloaded = Project.objects.get(pk=art.pk)
        assert reloaded.__class__ is ArtProject
        assert reloaded.topic == "New Painting"
        assert reloaded.artist == "Alice"

    def test_bulk_polymorphic_iteration(self):
        for cls in (Project, ArtProject, ResearchProject):
            cls.objects.all().delete()

        Project.objects.create(topic="P1")
        ArtProject.objects.create(topic="A1", artist="a")
        ResearchProject.objects.create(topic="R1", supervisor="s")

        classes = sorted(type(o).__name__ for o in Project.objects.all())
        assert classes == ["ArtProject", "Project", "ResearchProject"]
