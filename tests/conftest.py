import pytest

from fleet.config import Paths, spark_session


@pytest.fixture(scope="session")
def spark():
    session = spark_session()
    yield session
    session.stop()


@pytest.fixture
def paths(tmp_path):
    return Paths(tmp_path)
