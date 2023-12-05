import os
import shutil
import tempfile
import warnings
from contextlib import chdir
from pathlib import Path

import psycopg2
import pytest

from src.typedal import TypeDAL
from src.typedal.config import _load_dotenv, _load_toml, load_config


@pytest.fixture
def at_temp_dir():
    with tempfile.TemporaryDirectory() as d:
        with chdir(d):
            yield d


def _load_db_after_setup(dialect: str):
    config = load_config()
    try:
        db = TypeDAL(attempts=1)
        assert db._uri == config.database
    except (psycopg2.OperationalError, RuntimeError) as e:
        # postgres not running
        warnings.warn("Postgres is not running!", source=e)

    assert f"'dialect': '{dialect}'" in repr(config)

    return True


def test_load_toml(at_temp_dir):
    base = Path("pyproject.toml")
    base.write_text("# empty")

    assert _load_toml(False) == ("", {})
    assert _load_toml(None) == (str(base.resolve().absolute()), {})
    assert _load_toml(str(base)) == ("pyproject.toml", {})
    assert _load_toml(".") == (str(base.resolve().absolute()), {})


def test_load_dotenv(at_temp_dir):
    base = Path(".env")
    base.write_text("# empty")

    assert _load_dotenv(False)[0] == ""
    assert _load_dotenv(None)[0] == str(base.resolve().absolute())
    assert _load_dotenv(str(base))[0] == ".env"
    assert _load_dotenv(".")[0] == ".env"


def test_load_empty_config(at_temp_dir):
    assert _load_db_after_setup("sqlite")


def test_load_toml_config(at_temp_dir):
    examples = Path(__file__).parent / "configs"
    shutil.copy(examples / "valid.toml", "./pyproject.toml")

    assert _load_db_after_setup("sqlite")


def test_load_env_config(at_temp_dir):
    examples = Path(__file__).parent / "configs"
    shutil.copy(examples / "valid.env", "./.env")

    assert _load_db_after_setup("postgres")


def test_load_simple_config(at_temp_dir):
    examples = Path(__file__).parent / "configs"
    shutil.copy(examples / "valid.env", "./.env")
    shutil.copy(examples / "simple.toml", "./pyproject.toml")

    assert _load_db_after_setup("postgres")


def test_load_both_config(at_temp_dir):
    examples = Path(__file__).parent / "configs"
    shutil.copy(examples / "valid.env", "./.env")
    shutil.copy(examples / "valid.toml", "./pyproject.toml")

    assert _load_db_after_setup("postgres")


def test_converting(at_temp_dir):
    from edwh_migrate import Config as MigrateConfig
    from pydal2sql.typer_support import Config as P2SConfig

    config = load_config()

    assert isinstance(config.to_migrate(), MigrateConfig)
    assert isinstance(config.to_pydal2sql(), P2SConfig)