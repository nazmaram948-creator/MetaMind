import copy

import pytest

from engine.build import build
from engine.config import load_config
from engine.service import Engine
from engine.store import Store


@pytest.fixture(scope="session")
def cfg():
    c = copy.deepcopy(load_config())
    c["parse"]["similarity_backend"] = "lexical"  # no model download in tests
    c["futures"]["runs"] = 200                      # keep the suite fast
    return c


@pytest.fixture(scope="session")
def store(tmp_path_factory):
    path = tmp_path_factory.mktemp("db") / "test.db"
    build(path)
    return Store.open(path)


@pytest.fixture(scope="session")
def engine(store, cfg):
    return Engine(store=store, cfg=cfg)
