from pathlib import Path
import pytest
# from contextlib import ExitStack as does_not_raise
from vpn_swapper.config import Config
from copy import deepcopy


def get_fixture_path(file: str = '') -> str:
    return str(Path(Path(Path(__file__).parent).joinpath(f"fixtures/{file}")).resolve())


def config():
    conf = {'config_file': get_fixture_path('config_test.json')}
    # bypassing the singleton for testing to allow parallel testing and distinct fixture setup
    return deepcopy(Config('test vpn swapper', conf))


@pytest.fixture
def config_fix():
    return config()
