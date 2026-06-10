import pytest


@pytest.fixture
def create_project_objects(db):
    from pexp.models import ArtProject, Project, ResearchProject

    project = Project.objects.create(topic="General")
    art = ArtProject.objects.create(topic="Art", artist="Picasso")
    research = ResearchProject.objects.create(topic="Research", supervisor="Dr. Smith")
    return project, art, research


@pytest.fixture
def create_uuid_objects(db):
    import uuid

    from pexp.models import UUIDModelA, UUIDModelB, UUIDModelC

    a = UUIDModelA.objects.create(uuid_primary_key=uuid.uuid4(), field1="A1")
    b = UUIDModelB.objects.create(uuid_primary_key=uuid.uuid4(), field1="B1", field2="B2")
    c = UUIDModelC.objects.create(uuid_primary_key=uuid.uuid4(), field1="C1", field2="C2", field3="C3")
    return a, b, c


@pytest.fixture
def create_test_model_objects(db):
    from pexp.models import TestModelA, TestModelB, TestModelC

    a = TestModelA.objects.create(field1="A1")
    b = TestModelB.objects.create(field1="B1", field2="B2")
    c = TestModelC.objects.create(field1="C1", field2="C2", field3="C3")
    return a, b, c


@pytest.fixture
def create_proxy_objects(db):
    from pexp.models import ProxyA, ProxyB, ProxyBase

    base = ProxyBase.objects.create(title="Base Item")
    a = ProxyA.objects.create(title="Proxy A Item")
    b = ProxyB.objects.create(title="Proxy B Item")
    return base, a, b


@pytest.fixture
def create_normal_objects(db):
    from pexp.models import NormalModelA, NormalModelB, NormalModelC

    a = NormalModelA.objects.create(field1="NA1")
    b = NormalModelB.objects.create(field1="NB1", field2="NB2")
    c = NormalModelC.objects.create(field1="NC1", field2="NC2", field3="NC3")
    return a, b, c
