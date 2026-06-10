import uuid
import warnings

import pytest
from django.contrib.contenttypes.models import ContentType
from django.db.models import Q

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
from polymorphic.models import PolymorphicTypeInvalid, PolymorphicTypeUndefined


class TestProjectModelCreation:
    def test_create_project(self, db):
        obj = Project.objects.create(topic="Test Topic")
        assert obj.pk is not None
        assert obj.topic == "Test Topic"
        assert isinstance(obj, Project)

    def test_create_art_project(self, db):
        obj = ArtProject.objects.create(topic="Art Topic", artist="Van Gogh")
        assert obj.pk is not None
        assert obj.topic == "Art Topic"
        assert obj.artist == "Van Gogh"
        assert isinstance(obj, ArtProject)

    def test_create_research_project(self, db):
        obj = ResearchProject.objects.create(topic="Science", supervisor="Prof. Lee")
        assert obj.pk is not None
        assert obj.topic == "Science"
        assert obj.supervisor == "Prof. Lee"
        assert isinstance(obj, ResearchProject)

    def test_project_polymorphic_ctype(self, db, create_project_objects):
        project, art, research = create_project_objects
        ct_project = ContentType.objects.get_for_model(Project, for_concrete_model=False)
        ct_art = ContentType.objects.get_for_model(ArtProject, for_concrete_model=False)
        ct_research = ContentType.objects.get_for_model(ResearchProject, for_concrete_model=False)
        assert project.polymorphic_ctype_id == ct_project.pk
        assert art.polymorphic_ctype_id == ct_art.pk
        assert research.polymorphic_ctype_id == ct_research.pk

    def test_project_query_returns_correct_types(self, db, create_project_objects):
        project, art, research = create_project_objects
        results = list(Project.objects.all())
        assert len(results) == 3
        types = {type(r) for r in results}
        assert types == {Project, ArtProject, ResearchProject}

    def test_project_update(self, db, create_project_objects):
        project, art, research = create_project_objects
        project.topic = "Updated Topic"
        project.save()
        project.refresh_from_db()
        assert project.topic == "Updated Topic"

    def test_art_project_update(self, db, create_project_objects):
        _, art, _ = create_project_objects
        art.artist = "Monet"
        art.save()
        art.refresh_from_db()
        assert art.artist == "Monet"

    def test_research_project_update(self, db, create_project_objects):
        _, _, research = create_project_objects
        research.supervisor = "Dr. Johnson"
        research.save()
        research.refresh_from_db()
        assert research.supervisor == "Dr. Johnson"


class TestUUIDModelCreation:
    def test_create_uuid_model_a(self, db):
        pk = uuid.uuid4()
        obj = UUIDModelA.objects.create(uuid_primary_key=pk, field1="A1")
        assert obj.pk == pk
        assert obj.field1 == "A1"

    def test_create_uuid_model_b(self, db):
        pk = uuid.uuid4()
        obj = UUIDModelB.objects.create(uuid_primary_key=pk, field1="B1", field2="B2")
        assert obj.pk == pk
        assert obj.field1 == "B1"
        assert obj.field2 == "B2"

    def test_create_uuid_model_c(self, db):
        pk = uuid.uuid4()
        obj = UUIDModelC.objects.create(uuid_primary_key=pk, field1="C1", field2="C2", field3="C3")
        assert obj.pk == pk
        assert obj.field1 == "C1"
        assert obj.field2 == "C2"
        assert obj.field3 == "C3"

    def test_uuid_model_auto_pk(self, db):
        pk = uuid.uuid4()
        obj = UUIDModelA.objects.create(uuid_primary_key=pk, field1="Auto")
        assert obj.pk == pk
        assert isinstance(obj.pk, uuid.UUID)

    def test_uuid_polymorphic_query(self, db, create_uuid_objects):
        a, b, c = create_uuid_objects
        results = list(UUIDModelA.objects.all())
        assert len(results) == 3
        types = {type(r) for r in results}
        assert types == {UUIDModelA, UUIDModelB, UUIDModelC}

    def test_uuid_model_update(self, db, create_uuid_objects):
        a, b, c = create_uuid_objects
        a.field1 = "Updated A1"
        a.save()
        a.refresh_from_db()
        assert a.field1 == "Updated A1"

    def test_uuid_model_b_update(self, db, create_uuid_objects):
        _, b, _ = create_uuid_objects
        b.field2 = "Updated B2"
        b.save()
        b.refresh_from_db()
        assert b.field2 == "Updated B2"

    def test_uuid_model_c_update(self, db, create_uuid_objects):
        _, _, c = create_uuid_objects
        c.field3 = "Updated C3"
        c.save()
        c.refresh_from_db()
        assert c.field3 == "Updated C3"


class TestProxyModelCreation:
    def test_create_proxy_base(self, db):
        obj = ProxyBase.objects.create(title="Base")
        assert obj.pk is not None
        assert obj.title == "Base"
        assert isinstance(obj, ProxyBase)

    def test_create_proxy_a(self, db):
        obj = ProxyA.objects.create(title="ProxyA")
        assert obj.pk is not None
        assert obj.title == "ProxyA"
        assert isinstance(obj, ProxyA)

    def test_create_proxy_b(self, db):
        obj = ProxyB.objects.create(title="ProxyB")
        assert obj.pk is not None
        assert obj.title == "ProxyB"
        assert isinstance(obj, ProxyB)

    def test_proxy_base_unicode(self):
        obj = ProxyBase(title="Test")
        result = obj.__unicode__()
        assert "ProxyBase" in result
        assert "Test" in result

    def test_proxy_a_unicode(self):
        obj = ProxyA(title="TestA")
        result = obj.__unicode__()
        assert "ProxyA" in result
        assert "TestA" in result

    def test_proxy_b_unicode(self):
        obj = ProxyB(title="TestB")
        result = obj.__unicode__()
        assert "ProxyB" in result
        assert "TestB" in result

    def test_proxy_polymorphic_query(self, db, create_proxy_objects):
        base, a, b = create_proxy_objects
        results = list(ProxyBase.objects.all())
        assert len(results) == 3
        types = {type(r) for r in results}
        assert types == {ProxyBase, ProxyA, ProxyB}

    def test_proxy_ordering(self, db):
        ProxyBase.objects.create(title="Zebra")
        ProxyBase.objects.create(title="Alpha")
        ProxyBase.objects.create(title="Middle")
        results = list(ProxyBase.objects.all())
        titles = [r.title for r in results]
        assert titles == sorted(titles)

    def test_proxy_update(self, db, create_proxy_objects):
        base, a, b = create_proxy_objects
        base.title = "Updated Base"
        base.save()
        base.refresh_from_db()
        assert base.title == "Updated Base"


class TestTestModelCreation:
    def test_create_test_model_a(self, db):
        obj = TestModelA.objects.create(field1="A1")
        assert obj.pk is not None
        assert obj.field1 == "A1"

    def test_create_test_model_b(self, db):
        obj = TestModelB.objects.create(field1="B1", field2="B2")
        assert obj.pk is not None
        assert obj.field1 == "B1"
        assert obj.field2 == "B2"

    def test_create_test_model_c(self, db):
        obj = TestModelC.objects.create(field1="C1", field2="C2", field3="C3")
        assert obj.pk is not None
        assert obj.field1 == "C1"
        assert obj.field2 == "C2"
        assert obj.field3 == "C3"

    def test_test_model_c_m2m(self, db, create_test_model_objects):
        a, b, c = create_test_model_objects
        c.field4.add(b)
        assert b in c.field4.all()
        assert c in b.related_c.all()

    def test_test_model_c_m2m_multiple(self, db, create_test_model_objects):
        a, b, c = create_test_model_objects
        b2 = TestModelB.objects.create(field1="B3", field2="B4")
        c.field4.add(b, b2)
        assert c.field4.count() == 2
        assert set(c.field4.all()) == {b, b2}

    def test_test_model_polymorphic_query(self, db, create_test_model_objects):
        a, b, c = create_test_model_objects
        results = list(TestModelA.objects.all())
        assert len(results) == 3
        types = {type(r) for r in results}
        assert types == {TestModelA, TestModelB, TestModelC}

    def test_test_model_update(self, db, create_test_model_objects):
        a, b, c = create_test_model_objects
        a.field1 = "Updated A1"
        a.save()
        a.refresh_from_db()
        assert a.field1 == "Updated A1"


class TestNormalModelCreation:
    def test_create_normal_model_a(self, db):
        obj = NormalModelA.objects.create(field1="NA1")
        assert obj.pk is not None
        assert obj.field1 == "NA1"

    def test_create_normal_model_b(self, db):
        obj = NormalModelB.objects.create(field1="NB1", field2="NB2")
        assert obj.pk is not None
        assert obj.field1 == "NB1"
        assert obj.field2 == "NB2"

    def test_create_normal_model_c(self, db):
        obj = NormalModelC.objects.create(field1="NC1", field2="NC2", field3="NC3")
        assert obj.pk is not None
        assert obj.field1 == "NC1"
        assert obj.field2 == "NC2"
        assert obj.field3 == "NC3"

    def test_normal_model_no_polymorphic(self, db, create_normal_objects):
        a, b, c = create_normal_objects
        results = list(NormalModelA.objects.all())
        assert len(results) == 3
        types = {type(r) for r in results}
        assert types == {NormalModelA}

    def test_normal_model_update(self, db, create_normal_objects):
        a, b, c = create_normal_objects
        a.field1 = "Updated NA1"
        a.save()
        a.refresh_from_db()
        assert a.field1 == "Updated NA1"


class TestGetRealInstance:
    def test_get_real_instance_base_class(self, db, create_project_objects):
        project, art, research = create_project_objects
        base_obj = Project.objects.non_polymorphic().get(pk=project.pk)
        assert type(base_obj) is Project
        real = base_obj.get_real_instance()
        assert type(real) is Project
        assert real.pk == project.pk

    def test_get_real_instance_child_class(self, db, create_project_objects):
        project, art, research = create_project_objects
        base_obj = Project.objects.non_polymorphic().get(pk=art.pk)
        assert type(base_obj) is Project
        real = base_obj.get_real_instance()
        assert type(real) is ArtProject
        assert real.artist == "Picasso"

    def test_get_real_instance_research_project(self, db, create_project_objects):
        project, art, research = create_project_objects
        base_obj = Project.objects.non_polymorphic().get(pk=research.pk)
        assert type(base_obj) is Project
        real = base_obj.get_real_instance()
        assert type(real) is ResearchProject
        assert real.supervisor == "Dr. Smith"

    def test_get_real_instance_already_correct_type(self, db):
        art = ArtProject.objects.create(topic="Art", artist="Da Vinci")
        real = art.get_real_instance()
        assert real is art
        assert type(real) is ArtProject

    def test_get_real_instance_uuid_models(self, db, create_uuid_objects):
        a, b, c = create_uuid_objects
        base_obj = UUIDModelA.objects.non_polymorphic().get(pk=b.pk)
        assert type(base_obj) is UUIDModelA
        real = base_obj.get_real_instance()
        assert type(real) is UUIDModelB
        assert real.field2 == "B2"

    def test_get_real_instance_uuid_model_c(self, db, create_uuid_objects):
        a, b, c = create_uuid_objects
        base_obj = UUIDModelA.objects.non_polymorphic().get(pk=c.pk)
        assert type(base_obj) is UUIDModelA
        real = base_obj.get_real_instance()
        assert type(real) is UUIDModelC
        assert real.field3 == "C3"

    def test_get_real_instance_test_model(self, db, create_test_model_objects):
        a, b, c = create_test_model_objects
        base_obj = TestModelA.objects.non_polymorphic().get(pk=c.pk)
        assert type(base_obj) is TestModelA
        real = base_obj.get_real_instance()
        assert type(real) is TestModelC
        assert real.field3 == "C3"

    def test_get_real_instance_proxy_base(self, db, create_proxy_objects):
        base, a, b = create_proxy_objects
        base_obj = ProxyBase.objects.non_polymorphic().get(pk=a.pk)
        real = base_obj.get_real_instance()
        assert type(real) is ProxyA

    def test_get_real_instance_proxy_b(self, db, create_proxy_objects):
        base, a, b = create_proxy_objects
        base_obj = ProxyBase.objects.non_polymorphic().get(pk=b.pk)
        real = base_obj.get_real_instance()
        assert type(real) is ProxyB

    def test_get_real_instance_stale_content_type(self, db):
        stale_ct = ContentType.objects.create(app_label="pexp", model="nonexisting")
        obj = Project.objects.create(topic="Stale")
        Project.objects.filter(pk=obj.pk).update(polymorphic_ctype=stale_ct)
        base_obj = Project.objects.non_polymorphic().get(pk=obj.pk)
        assert base_obj.get_real_instance_class() is None
        with pytest.raises(PolymorphicTypeInvalid, match="does not have a corresponding model"):
            base_obj.get_real_instance()

    def test_get_real_instance_class_no_ctype_id(self, db):
        obj = Project(topic="NoCtype")
        obj.pk = 999
        obj.polymorphic_ctype_id = None
        with pytest.raises(PolymorphicTypeUndefined):
            obj.get_real_instance_class()

    def test_get_real_instance_class_returns_correct_type(self, db, create_project_objects):
        project, art, research = create_project_objects
        assert project.get_real_instance_class() == Project
        assert art.get_real_instance_class() == ArtProject
        assert research.get_real_instance_class() == ResearchProject

    def test_get_real_concrete_instance_class(self, db, create_project_objects):
        _, art, _ = create_project_objects
        concrete_class = art.get_real_concrete_instance_class()
        assert concrete_class == ArtProject

    def test_get_real_concrete_instance_class_id(self, db, create_project_objects):
        _, art, _ = create_project_objects
        ct_id = art.get_real_concrete_instance_class_id()
        expected_ct = ContentType.objects.get_for_model(ArtProject, for_concrete_model=True)
        assert ct_id == expected_ct.pk

    def test_get_real_concrete_instance_class_stale(self, db):
        stale_ct = ContentType.objects.create(app_label="pexp", model="nonexisting")
        obj = Project.objects.create(topic="StaleConcrete")
        Project.objects.filter(pk=obj.pk).update(polymorphic_ctype=stale_ct)
        base_obj = Project.objects.non_polymorphic().get(pk=obj.pk)
        assert base_obj.get_real_concrete_instance_class() is None
        assert base_obj.get_real_concrete_instance_class_id() is None

    def test_get_real_instance_uuid_already_correct(self, db):
        pk = uuid.uuid4()
        obj = UUIDModelA.objects.create(uuid_primary_key=pk, field1="Direct")
        real = obj.get_real_instance()
        assert real is obj

    def test_get_real_instance_test_model_b(self, db, create_test_model_objects):
        a, b, c = create_test_model_objects
        base_obj = TestModelA.objects.non_polymorphic().get(pk=b.pk)
        real = base_obj.get_real_instance()
        assert type(real) is TestModelB
        assert real.field2 == "B2"


class TestInstanceOf:
    def test_instance_of_project(self, db, create_project_objects):
        project, art, research = create_project_objects
        results = list(Project.objects.instance_of(Project))
        assert len(results) == 3
        pks = {r.pk for r in results}
        assert project.pk in pks
        assert art.pk in pks
        assert research.pk in pks

    def test_instance_of_art_project(self, db, create_project_objects):
        project, art, research = create_project_objects
        results = list(Project.objects.instance_of(ArtProject))
        assert len(results) == 1
        assert results[0].pk == art.pk
        assert type(results[0]) is ArtProject

    def test_instance_of_research_project(self, db, create_project_objects):
        project, art, research = create_project_objects
        results = list(Project.objects.instance_of(ResearchProject))
        assert len(results) == 1
        assert results[0].pk == research.pk
        assert type(results[0]) is ResearchProject

    def test_instance_of_base_returns_exact(self, db, create_project_objects):
        project, art, research = create_project_objects
        results = list(Project.objects.instance_of(Project))
        assert len(results) == 3
        types = {type(r) for r in results}
        assert Project in types
        assert ArtProject in types
        assert ResearchProject in types

    def test_instance_of_multiple_types(self, db, create_project_objects):
        project, art, research = create_project_objects
        results = list(Project.objects.instance_of(ArtProject, ResearchProject))
        assert len(results) == 2
        pks = {r.pk for r in results}
        assert art.pk in pks
        assert research.pk in pks

    def test_not_instance_of(self, db, create_project_objects):
        project, art, research = create_project_objects
        results = list(Project.objects.not_instance_of(ArtProject))
        assert len(results) == 2
        types = {type(r) for r in results}
        assert Project in types
        assert ResearchProject in types
        assert ArtProject not in types

    def test_not_instance_of_multiple(self, db, create_project_objects):
        project, art, research = create_project_objects
        results = list(Project.objects.not_instance_of(ArtProject, ResearchProject))
        assert len(results) == 1
        assert type(results[0]) is Project

    def test_instance_of_uuid_model_a(self, db, create_uuid_objects):
        a, b, c = create_uuid_objects
        results = list(UUIDModelA.objects.instance_of(UUIDModelA))
        assert len(results) == 3
        types = {type(r) for r in results}
        assert UUIDModelA in types
        assert UUIDModelB in types
        assert UUIDModelC in types

    def test_instance_of_uuid_model_b(self, db, create_uuid_objects):
        a, b, c = create_uuid_objects
        results = list(UUIDModelA.objects.instance_of(UUIDModelB))
        assert len(results) == 2
        types = {type(r) for r in results}
        assert UUIDModelB in types
        assert UUIDModelC in types

    def test_instance_of_uuid_model_c(self, db, create_uuid_objects):
        a, b, c = create_uuid_objects
        results = list(UUIDModelA.objects.instance_of(UUIDModelC))
        assert len(results) == 1
        assert type(results[0]) is UUIDModelC

    def test_instance_of_test_model_a(self, db, create_test_model_objects):
        a, b, c = create_test_model_objects
        results = list(TestModelA.objects.instance_of(TestModelA))
        assert len(results) == 3
        types = {type(r) for r in results}
        assert TestModelA in types
        assert TestModelB in types
        assert TestModelC in types

    def test_instance_of_test_model_b(self, db, create_test_model_objects):
        a, b, c = create_test_model_objects
        results = list(TestModelA.objects.instance_of(TestModelB))
        assert len(results) == 2
        types = {type(r) for r in results}
        assert TestModelB in types
        assert TestModelC in types

    def test_instance_of_test_model_c(self, db, create_test_model_objects):
        a, b, c = create_test_model_objects
        results = list(TestModelA.objects.instance_of(TestModelC))
        assert len(results) == 1
        assert type(results[0]) is TestModelC

    def test_instance_of_proxy_base(self, db, create_proxy_objects):
        base, a, b = create_proxy_objects
        results = list(ProxyBase.objects.instance_of(ProxyBase))
        assert len(results) == 3
        types = {type(r) for r in results}
        assert ProxyBase in types
        assert ProxyA in types
        assert ProxyB in types

    def test_instance_of_proxy_a(self, db, create_proxy_objects):
        base, a, b = create_proxy_objects
        results = list(ProxyBase.objects.instance_of(ProxyA))
        assert len(results) == 1
        assert type(results[0]) is ProxyA

    def test_instance_of_proxy_b(self, db, create_proxy_objects):
        base, a, b = create_proxy_objects
        results = list(ProxyBase.objects.instance_of(ProxyB))
        assert len(results) == 1
        assert type(results[0]) is ProxyB

    def test_instance_of_chained_with_filter(self, db, create_project_objects):
        project, art, research = create_project_objects
        results = list(Project.objects.instance_of(ArtProject).filter(topic="Art"))
        assert len(results) == 1
        assert results[0].pk == art.pk

    def test_instance_of_empty_result(self, db, create_project_objects):
        project, art, research = create_project_objects
        results = list(Project.objects.instance_of(ArtProject).filter(topic="NonExistent"))
        assert len(results) == 0


class TestDeleteKeepParents:
    def test_delete_art_project_keep_parents(self, db, create_project_objects):
        project, art, research = create_project_objects
        art_pk = art.pk
        art.delete(keep_parents=True)
        assert not ArtProject.objects.filter(pk=art_pk).exists()
        assert Project.objects.filter(pk=art_pk).exists()
        parent = Project.objects.get(pk=art_pk)
        assert type(parent) is Project
        assert parent.topic == "Art"

    def test_delete_research_project_keep_parents(self, db, create_project_objects):
        project, art, research = create_project_objects
        research_pk = research.pk
        research.delete(keep_parents=True)
        assert not ResearchProject.objects.filter(pk=research_pk).exists()
        assert Project.objects.filter(pk=research_pk).exists()
        parent = Project.objects.get(pk=research_pk)
        assert type(parent) is Project
        assert parent.topic == "Research"

    def test_delete_uuid_model_c_keep_parents(self, db, create_uuid_objects):
        a, b, c = create_uuid_objects
        c_pk = c.pk
        c.delete(keep_parents=True)
        assert not UUIDModelC.objects.filter(pk=c_pk).exists()
        assert UUIDModelB.objects.filter(pk=c_pk).exists()
        parent = UUIDModelB.objects.get(pk=c_pk)
        assert parent.field2 == "C2"

    def test_delete_uuid_model_b_keep_parents(self, db, create_uuid_objects):
        a, b, c = create_uuid_objects
        b_pk = b.pk
        b.delete(keep_parents=True)
        assert not UUIDModelB.objects.filter(pk=b_pk).exists()
        assert UUIDModelA.objects.filter(pk=b_pk).exists()
        parent = UUIDModelA.objects.get(pk=b_pk)
        assert parent.field1 == "B1"

    def test_delete_test_model_c_keep_parents(self, db, create_test_model_objects):
        a, b, c = create_test_model_objects
        c_pk = c.pk
        c.delete(keep_parents=True)
        assert not TestModelC.objects.filter(pk=c_pk).exists()
        assert TestModelB.objects.filter(pk=c_pk).exists()
        parent = TestModelB.objects.get(pk=c_pk)
        assert parent.field2 == "C2"

    def test_delete_test_model_b_keep_parents(self, db, create_test_model_objects):
        a, b, c = create_test_model_objects
        b_pk = b.pk
        b.delete(keep_parents=True)
        assert not TestModelB.objects.filter(pk=b_pk).exists()
        assert TestModelA.objects.filter(pk=b_pk).exists()
        parent = TestModelA.objects.get(pk=b_pk)
        assert parent.field1 == "B1"

    def test_delete_keep_parents_updates_polymorphic_ctype(self, db, create_project_objects):
        project, art, research = create_project_objects
        art_pk = art.pk
        ct_project = ContentType.objects.get_for_model(Project, for_concrete_model=False)
        art.delete(keep_parents=True)
        parent = Project.objects.non_polymorphic().get(pk=art_pk)
        assert parent.polymorphic_ctype_id == ct_project.pk

    def test_delete_keep_parents_uuid_c_updates_ctype(self, db, create_uuid_objects):
        a, b, c = create_uuid_objects
        c_pk = c.pk
        ct_b = ContentType.objects.get_for_model(UUIDModelB, for_concrete_model=False)
        c.delete(keep_parents=True)
        parent = UUIDModelA.objects.non_polymorphic().get(pk=c_pk)
        assert parent.polymorphic_ctype_id == ct_b.pk

    def test_delete_without_keep_parents(self, db, create_project_objects):
        project, art, research = create_project_objects
        art_pk = art.pk
        art.delete()
        assert not ArtProject.objects.filter(pk=art_pk).exists()
        assert not Project.objects.filter(pk=art_pk).exists()

    def test_delete_base_without_keep_parents(self, db, create_project_objects):
        project, art, research = create_project_objects
        project_pk = project.pk
        project.delete()
        assert not Project.objects.filter(pk=project_pk).exists()

    def test_delete_keep_parents_multiple_levels(self, db):
        c = TestModelC.objects.create(field1="C1", field2="C2", field3="C3")
        c_pk = c.pk
        c.delete(keep_parents=True)
        assert not TestModelC.objects.filter(pk=c_pk).exists()
        assert TestModelB.objects.filter(pk=c_pk).exists()
        assert TestModelA.objects.filter(pk=c_pk).exists()

    def test_delete_keep_parents_uuid_multiple_levels(self, db):
        c = UUIDModelC.objects.create(
            uuid_primary_key=uuid.uuid4(), field1="C1", field2="C2", field3="C3"
        )
        c_pk = c.pk
        c.delete(keep_parents=True)
        assert not UUIDModelC.objects.filter(pk=c_pk).exists()
        assert UUIDModelB.objects.filter(pk=c_pk).exists()
        assert UUIDModelA.objects.filter(pk=c_pk).exists()

    def test_delete_normal_model_no_keep_parents(self, db, create_normal_objects):
        a, b, c = create_normal_objects
        b_pk = b.pk
        b.delete()
        assert not NormalModelB.objects.filter(pk=b_pk).exists()
        assert not NormalModelA.objects.filter(pk=b_pk).exists()

    def test_delete_normal_model_keep_parents(self, db, create_normal_objects):
        a, b, c = create_normal_objects
        b_pk = b.pk
        b.delete(keep_parents=True)
        assert not NormalModelB.objects.filter(pk=b_pk).exists()
        assert NormalModelA.objects.filter(pk=b_pk).exists()


class TestMultiTableRoundtrip:
    def test_project_roundtrip(self, db):
        original = ArtProject.objects.create(topic="Roundtrip", artist="Test Artist")
        pk = original.pk
        fetched = Project.objects.get(pk=pk)
        assert type(fetched) is ArtProject
        assert fetched.topic == "Roundtrip"
        assert fetched.artist == "Test Artist"

    def test_research_project_roundtrip(self, db):
        original = ResearchProject.objects.create(topic="RResearch", supervisor="Dr. Round")
        pk = original.pk
        fetched = Project.objects.get(pk=pk)
        assert type(fetched) is ResearchProject
        assert fetched.topic == "RResearch"
        assert fetched.supervisor == "Dr. Round"

    def test_uuid_model_roundtrip(self, db):
        pk = uuid.uuid4()
        UUIDModelC.objects.create(uuid_primary_key=pk, field1="F1", field2="F2", field3="F3")
        fetched = UUIDModelA.objects.get(pk=pk)
        assert type(fetched) is UUIDModelC
        assert fetched.field1 == "F1"
        assert fetched.field2 == "F2"
        assert fetched.field3 == "F3"

    def test_uuid_model_b_roundtrip(self, db):
        pk = uuid.uuid4()
        UUIDModelB.objects.create(uuid_primary_key=pk, field1="F1", field2="F2")
        fetched = UUIDModelA.objects.get(pk=pk)
        assert type(fetched) is UUIDModelB
        assert fetched.field1 == "F1"
        assert fetched.field2 == "F2"

    def test_test_model_roundtrip(self, db):
        original = TestModelC.objects.create(field1="F1", field2="F2", field3="F3")
        pk = original.pk
        fetched = TestModelA.objects.get(pk=pk)
        assert type(fetched) is TestModelC
        assert fetched.field1 == "F1"
        assert fetched.field2 == "F2"
        assert fetched.field3 == "F3"

    def test_proxy_roundtrip(self, db):
        original = ProxyA.objects.create(title="Proxy Roundtrip")
        pk = original.pk
        fetched = ProxyBase.objects.get(pk=pk)
        assert type(fetched) is ProxyA
        assert fetched.title == "Proxy Roundtrip"

    def test_project_non_polymorphic_roundtrip(self, db):
        original = ArtProject.objects.create(topic="NonPoly", artist="Artist")
        pk = original.pk
        base_obj = Project.objects.non_polymorphic().get(pk=pk)
        assert type(base_obj) is Project
        real = base_obj.get_real_instance()
        assert type(real) is ArtProject
        assert real.artist == "Artist"

    def test_uuid_non_polymorphic_roundtrip(self, db):
        pk = uuid.uuid4()
        UUIDModelC.objects.create(uuid_primary_key=pk, field1="F1", field2="F2", field3="F3")
        base_obj = UUIDModelA.objects.non_polymorphic().get(pk=pk)
        assert type(base_obj) is UUIDModelA
        real = base_obj.get_real_instance()
        assert type(real) is UUIDModelC
        assert real.field3 == "F3"

    def test_test_model_non_polymorphic_roundtrip(self, db):
        original = TestModelC.objects.create(field1="F1", field2="F2", field3="F3")
        pk = original.pk
        base_obj = TestModelA.objects.non_polymorphic().get(pk=pk)
        assert type(base_obj) is TestModelA
        real = base_obj.get_real_instance()
        assert type(real) is TestModelC
        assert real.field3 == "F3"

    def test_delete_keep_parents_roundtrip(self, db):
        art = ArtProject.objects.create(topic="DeleteRT", artist="Artist")
        pk = art.pk
        art.delete(keep_parents=True)
        parent = Project.objects.get(pk=pk)
        assert type(parent) is Project
        assert parent.topic == "DeleteRT"

    def test_uuid_delete_keep_parents_roundtrip(self, db):
        pk = uuid.uuid4()
        c = UUIDModelC.objects.create(uuid_primary_key=pk, field1="F1", field2="F2", field3="F3")
        c.delete(keep_parents=True)
        parent = UUIDModelA.objects.get(pk=pk)
        assert type(parent) is UUIDModelB
        assert parent.field1 == "F1"
        assert parent.field2 == "F2"

    def test_test_model_delete_keep_parents_roundtrip(self, db):
        c = TestModelC.objects.create(field1="F1", field2="F2", field3="F3")
        pk = c.pk
        c.delete(keep_parents=True)
        parent = TestModelA.objects.get(pk=pk)
        assert type(parent) is TestModelB
        assert parent.field1 == "F1"
        assert parent.field2 == "F2"

    def test_mixed_types_query_roundtrip(self, db):
        Project.objects.create(topic="Base1")
        ArtProject.objects.create(topic="Art1", artist="A1")
        ResearchProject.objects.create(topic="Res1", supervisor="S1")
        ArtProject.objects.create(topic="Art2", artist="A2")

        results = list(Project.objects.all())
        assert len(results) == 4
        type_counts = {}
        for r in results:
            type_counts[type(r)] = type_counts.get(type(r), 0) + 1
        assert type_counts[Project] == 1
        assert type_counts[ArtProject] == 2
        assert type_counts[ResearchProject] == 1

    def test_uuid_mixed_types_roundtrip(self, db):
        UUIDModelA.objects.create(uuid_primary_key=uuid.uuid4(), field1="A")
        UUIDModelB.objects.create(uuid_primary_key=uuid.uuid4(), field1="B", field2="B2")
        UUIDModelC.objects.create(uuid_primary_key=uuid.uuid4(), field1="C", field2="C2", field3="C3")

        results = list(UUIDModelA.objects.all())
        assert len(results) == 3
        type_counts = {}
        for r in results:
            type_counts[type(r)] = type_counts.get(type(r), 0) + 1
        assert type_counts[UUIDModelA] == 1
        assert type_counts[UUIDModelB] == 1
        assert type_counts[UUIDModelC] == 1

    def test_test_model_m2m_roundtrip(self, db):
        b1 = TestModelB.objects.create(field1="B1", field2="B2")
        b2 = TestModelB.objects.create(field1="B3", field2="B4")
        c = TestModelC.objects.create(field1="C1", field2="C2", field3="C3")
        c.field4.add(b1, b2)

        fetched = TestModelC.objects.get(pk=c.pk)
        assert fetched.field4.count() == 2
        assert set(fetched.field4.all()) == {b1, b2}

        fetched_b1 = TestModelB.objects.get(pk=b1.pk)
        assert c in fetched_b1.related_c.all()

    def test_normal_model_roundtrip(self, db):
        original = NormalModelC.objects.create(field1="F1", field2="F2", field3="F3")
        pk = original.pk
        fetched = NormalModelA.objects.get(pk=pk)
        assert type(fetched) is NormalModelA
        assert fetched.field1 == "F1"

    def test_proxy_base_to_child_roundtrip(self, db):
        a = ProxyA.objects.create(title="ProxyA RT")
        pk = a.pk
        fetched = ProxyBase.objects.get(pk=pk)
        assert type(fetched) is ProxyA
        assert fetched.title == "ProxyA RT"

    def test_proxy_b_roundtrip(self, db):
        b = ProxyB.objects.create(title="ProxyB RT")
        pk = b.pk
        fetched = ProxyBase.objects.get(pk=pk)
        assert type(fetched) is ProxyB
        assert fetched.title == "ProxyB RT"

    def test_filter_by_child_field_roundtrip(self, db):
        ArtProject.objects.create(topic="Art", artist="Picasso")
        ArtProject.objects.create(topic="Art", artist="Monet")
        ResearchProject.objects.create(topic="Research", supervisor="Dr. Smith")

        results = list(Project.objects.filter(ArtProject___artist="Picasso"))
        assert len(results) == 1
        assert type(results[0]) is ArtProject
        assert results[0].artist == "Picasso"

    def test_filter_by_supervisor_roundtrip(self, db):
        ResearchProject.objects.create(topic="Res", supervisor="Dr. Lee")
        results = list(Project.objects.filter(ResearchProject___supervisor="Dr. Lee"))
        assert len(results) == 1
        assert type(results[0]) is ResearchProject
        assert results[0].supervisor == "Dr. Lee"

    def test_delete_keep_parents_then_query_roundtrip(self, db):
        art = ArtProject.objects.create(topic="ArtDel", artist="Artist")
        research = ResearchProject.objects.create(topic="ResDel", supervisor="Supervisor")
        art_pk = art.pk
        research_pk = research.pk

        art.delete(keep_parents=True)

        results = list(Project.objects.all())
        pks = {r.pk for r in results}
        assert art_pk in pks
        assert research_pk in pks

        art_parent = Project.objects.get(pk=art_pk)
        assert type(art_parent) is Project
        assert art_parent.topic == "ArtDel"

        research_obj = Project.objects.get(pk=research_pk)
        assert type(research_obj) is ResearchProject
        assert research_obj.supervisor == "Supervisor"


class TestPreSavePolymorphic:
    def test_pre_save_polymorphic_sets_ctype(self, db):
        art = ArtProject(topic="PreSave", artist="Artist")
        art.pre_save_polymorphic()
        ct = ContentType.objects.get_for_model(ArtProject, for_concrete_model=False)
        assert art.polymorphic_ctype_id == ct.pk

    def test_pre_save_polymorphic_idempotent(self, db):
        art = ArtProject.objects.create(topic="Idempotent", artist="Artist")
        original_ctype_id = art.polymorphic_ctype_id
        art.pre_save_polymorphic()
        assert art.polymorphic_ctype_id == original_ctype_id

    def test_save_sets_polymorphic_ctype(self, db):
        art = ArtProject(topic="SaveCtype", artist="Artist")
        art.save()
        ct = ContentType.objects.get_for_model(ArtProject, for_concrete_model=False)
        assert art.polymorphic_ctype_id == ct.pk


class TestPolymorphicTypeErrors:
    def test_polymorphic_type_undefined(self, db):
        obj = Project(topic="NoCtype")
        obj.pk = 99999
        obj.polymorphic_ctype_id = None
        with pytest.raises(PolymorphicTypeUndefined):
            obj.get_real_instance_class()

    def test_polymorphic_type_invalid_ctype(self, db):
        stale_ct = ContentType.objects.create(app_label="pexp", model="nonexisting")
        art = ArtProject.objects.create(topic="Invalid", artist="Artist")
        ArtProject.objects.filter(pk=art.pk).update(polymorphic_ctype=stale_ct)
        base_obj = Project.objects.non_polymorphic().get(pk=art.pk)
        assert base_obj.get_real_instance_class() is None
        with pytest.raises(PolymorphicTypeInvalid):
            base_obj.get_real_instance()

    def test_polymorphic_type_invalid_wrong_ctype(self, db):
        obj = Project.objects.create(topic="Wrong")
        ct_uuid = ContentType.objects.get_for_model(UUIDModelA, for_concrete_model=False)
        Project.objects.filter(pk=obj.pk).update(polymorphic_ctype=ct_uuid)
        base_obj = Project.objects.non_polymorphic().get(pk=obj.pk)
        with pytest.raises(PolymorphicTypeInvalid, match="does not point to a subclass"):
            base_obj.get_real_instance_class()


class TestShowFields:
    def test_project_show_field_content(self, db):
        Project.objects.create(topic="ShowField")
        repr_str = repr(Project.objects.all())
        assert "topic" in repr_str

    def test_uuid_model_show_field_type_and_content(self, db):
        UUIDModelA.objects.create(uuid_primary_key=uuid.uuid4(), field1="Show")
        repr_str = repr(UUIDModelA.objects.all())
        assert len(repr_str) > 0

    def test_test_model_show_field_type_and_content(self, db):
        TestModelA.objects.create(field1="Show")
        repr_str = repr(TestModelA.objects.all())
        assert len(repr_str) > 0


class TestQuerySetOperations:
    def test_project_count(self, db, create_project_objects):
        assert Project.objects.count() == 3

    def test_project_filter(self, db, create_project_objects):
        results = Project.objects.filter(topic="Art")
        assert results.count() == 1

    def test_project_exclude(self, db, create_project_objects):
        results = Project.objects.exclude(topic="Art")
        assert results.count() == 2

    def test_project_order_by(self, db, create_project_objects):
        results = list(Project.objects.order_by("topic"))
        topics = [r.topic for r in results]
        assert topics == sorted(topics)

    def test_uuid_model_filter(self, db, create_uuid_objects):
        a, b, c = create_uuid_objects
        results = UUIDModelA.objects.filter(field1="B1")
        assert results.count() == 1

    def test_test_model_filter(self, db, create_test_model_objects):
        a, b, c = create_test_model_objects
        results = TestModelA.objects.filter(field1="C1")
        assert results.count() == 1

    def test_proxy_base_count(self, db, create_proxy_objects):
        assert ProxyBase.objects.count() == 3

    def test_proxy_filter(self, db, create_proxy_objects):
        base, a, b = create_proxy_objects
        results = list(ProxyBase.objects.filter(title="Proxy A Item"))
        assert len(results) == 1
        assert type(results[0]) is ProxyA

    def test_project_values(self, db, create_project_objects):
        values = list(Project.objects.values("topic"))
        assert len(values) == 3
        assert all("topic" in v for v in values)

    def test_project_values_list(self, db, create_project_objects):
        values = list(Project.objects.values_list("topic", flat=True))
        assert len(values) == 3

    def test_project_exists(self, db, create_project_objects):
        assert Project.objects.filter(topic="Art").exists()
        assert not Project.objects.filter(topic="NonExistent").exists()

    def test_project_first_and_last(self, db, create_project_objects):
        first = Project.objects.first()
        assert first is not None
        last = Project.objects.last()
        assert last is not None

    def test_project_none(self, db):
        results = list(Project.objects.none())
        assert len(results) == 0

    def test_project_all(self, db, create_project_objects):
        results = list(Project.objects.all())
        assert len(results) == 3

    def test_project_get(self, db, create_project_objects):
        project, art, research = create_project_objects
        fetched = Project.objects.get(pk=art.pk)
        assert type(fetched) is ArtProject

    def test_uuid_model_get(self, db, create_uuid_objects):
        a, b, c = create_uuid_objects
        fetched = UUIDModelA.objects.get(pk=b.pk)
        assert type(fetched) is UUIDModelB

    def test_test_model_get(self, db, create_test_model_objects):
        a, b, c = create_test_model_objects
        fetched = TestModelA.objects.get(pk=c.pk)
        assert type(fetched) is TestModelC


class TestDeleteBasic:
    def test_delete_project(self, db, create_project_objects):
        project, art, research = create_project_objects
        count, models = project.delete()
        assert Project.objects.count() == 2
        assert not Project.objects.filter(pk=project.pk).exists()

    def test_delete_art_project(self, db, create_project_objects):
        project, art, research = create_project_objects
        art.delete()
        assert Project.objects.count() == 2
        assert not ArtProject.objects.filter(pk=art.pk).exists()

    def test_delete_research_project(self, db, create_project_objects):
        project, art, research = create_project_objects
        research.delete()
        assert Project.objects.count() == 2
        assert not ResearchProject.objects.filter(pk=research.pk).exists()

    def test_delete_uuid_model_a(self, db, create_uuid_objects):
        a, b, c = create_uuid_objects
        a.delete()
        assert UUIDModelA.objects.count() == 2

    def test_delete_uuid_model_c(self, db, create_uuid_objects):
        a, b, c = create_uuid_objects
        c.delete()
        assert UUIDModelA.objects.count() == 2
        assert not UUIDModelC.objects.filter(pk=c.pk).exists()

    def test_delete_test_model_c(self, db, create_test_model_objects):
        a, b, c = create_test_model_objects
        c.delete()
        assert TestModelA.objects.count() == 2
        assert not TestModelC.objects.filter(pk=c.pk).exists()

    def test_delete_proxy_base(self, db, create_proxy_objects):
        base, a, b = create_proxy_objects
        base.delete()
        assert ProxyBase.objects.count() == 2

    def test_delete_proxy_a(self, db, create_proxy_objects):
        base, a, b = create_proxy_objects
        a.delete()
        assert ProxyBase.objects.count() == 2
        assert not ProxyA.objects.filter(pk=a.pk).exists()

    def test_delete_normal_model(self, db, create_normal_objects):
        a, b, c = create_normal_objects
        a.delete()
        assert NormalModelA.objects.count() == 2

    def test_bulk_delete(self, db, create_project_objects):
        Project.objects.all().delete()
        assert Project.objects.count() == 0
        assert ArtProject.objects.count() == 0
        assert ResearchProject.objects.count() == 0

    def test_delete_with_using(self, db, create_project_objects):
        project, art, research = create_project_objects
        art.delete(using="default")
        assert not ArtProject.objects.filter(pk=art.pk).exists()

    def test_delete_keep_parents_with_using(self, db, create_project_objects):
        project, art, research = create_project_objects
        art_pk = art.pk
        art.delete(keep_parents=True, using="default")
        assert not ArtProject.objects.filter(pk=art_pk).exists()
        assert Project.objects.filter(pk=art_pk).exists()


class TestTestModelCM2M:
    def test_m2m_add(self, db, create_test_model_objects):
        a, b, c = create_test_model_objects
        c.field4.add(b)
        assert c.field4.count() == 1

    def test_m2m_remove(self, db, create_test_model_objects):
        a, b, c = create_test_model_objects
        c.field4.add(b)
        c.field4.remove(b)
        assert c.field4.count() == 0

    def test_m2m_clear(self, db, create_test_model_objects):
        a, b, c = create_test_model_objects
        c.field4.add(b)
        c.field4.clear()
        assert c.field4.count() == 0

    def test_m2m_set(self, db, create_test_model_objects):
        a, b, c = create_test_model_objects
        b2 = TestModelB.objects.create(field1="B3", field2="B4")
        c.field4.set([b, b2])
        assert c.field4.count() == 2

    def test_m2m_related_name(self, db, create_test_model_objects):
        a, b, c = create_test_model_objects
        c.field4.add(b)
        related = b.related_c.all()
        assert c in related

    def test_m2m_with_self_reference(self, db):
        b = TestModelB.objects.create(field1="B1", field2="B2")
        c = TestModelC.objects.create(field1="C1", field2="C2", field3="C3")
        c.field4.add(b)
        assert b in c.field4.all()
        assert c in b.related_c.all()

    def test_m2m_delete_cascade(self, db, create_test_model_objects):
        a, b, c = create_test_model_objects
        c.field4.add(b)
        c.delete()
        assert TestModelB.objects.filter(pk=b.pk).exists()
        assert b.related_c.count() == 0


class TestPolymorphicQuerySetMethods:
    def test_non_polymorphic(self, db, create_project_objects):
        project, art, research = create_project_objects
        results = list(Project.objects.non_polymorphic())
        assert all(type(r) is Project for r in results)

    def test_get_real_instances_from_queryset(self, db, create_project_objects):
        project, art, research = create_project_objects
        qs = Project.objects.all().non_polymorphic()
        real_instances = qs.get_real_instances()
        types = {type(r) for r in real_instances}
        assert types == {Project, ArtProject, ResearchProject}

    def test_translate_polymorphic_q(self):
        q = Q(topic="test")
        translated = Project.translate_polymorphic_Q_object(q)
        assert isinstance(translated, Q)
