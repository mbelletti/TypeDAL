"""
Typer CLI for TypeDAL.
"""
import sys
import typing
import warnings
from pathlib import Path
from typing import Optional

import tomli
from configuraptor import asdict
from configuraptor.alias import is_alias
from configuraptor.helpers import is_optional

try:
    import edwh_migrate
    import pydal2sql  # noqa: F401
    import questionary
    import rich
    import tomlkit
    import typer
except ImportError as e:  # pragma: no cover
    # ImportWarning is hidden by default
    warnings.warn(
        "`migrations` extra not installed. Please run `pip install typedal[migrations]` to fix this.",
        source=e,
        category=RuntimeWarning,
    )
    exit(127)  # command not found

from pydal2sql.typer_support import IS_DEBUG, with_exit_code
from pydal2sql.types import (
    DBType_Option,
    OptionalArgument,
    OutputFormat_Option,
    Tables_Option,
)
from pydal2sql_core import core_alter, core_create
from typing_extensions import Never

from .__about__ import __version__
from .config import TypeDALConfig, fill_defaults, load_config, transform

app = typer.Typer(
    no_args_is_help=True,
)

questionary_types: dict[typing.Hashable, Optional[dict[str, typing.Any]]] = {
    str: {
        "type": "text",
        "validate": lambda text: True if len(text) > 0 else "Please enter a value",
    },
    Optional[str]: {
        "type": "text",
        # no validate because it's optional
    },
    bool: {
        "type": "confirm",
    },
    int: {"type": "text", "validate": lambda text: True if text.isdigit() else "Please enter a number"},
    # specific props:
    "dialect": {
        "type": "select",
        "choices": ["sqlite", "postgres", "mysql"],
    },
    "folder": {
        "type": "path",
        "message": "Database directory:",
        "only_directories": True,
        "default": "",
    },
    "input": {
        "type": "path",
        "message": "Python file containing table definitions.",
        "file_filter": lambda file: "." not in file or file.endswith(".py"),
    },
    "output": {
        "type": "path",
        "message": "Python file where migrations will be written to.",
        "file_filter": lambda file: "." not in file or file.endswith(".py"),
    },
    # disabled props:
    "pyproject": None,
    "noop": None,
    # bool: questionary.confirm,
    # int: questionary.text,
    # 'pyproject': None,
    # 'input': questionary.text,
    # 'output': questionary.text,
    # 'tables': questionary.print,
    # 'flag_location': questionary.path,  # directory
}

T = typing.TypeVar("T")

notfound = object()


def _get_question(prop: str, annotation: typing.Type[T]) -> Optional[dict[str, typing.Any]]:  # pragma: no cover
    question = questionary_types.get(prop, notfound)
    if question is notfound:
        # None means skip the question, notfound means use the type default!
        question = questionary_types.get(annotation)  # type: ignore

    if not question:
        return None
    # make a copy so the original is not overwritten:
    return question.copy()  # type: ignore


def get_question(prop: str, annotation: typing.Type[T], default: T | None) -> Optional[T]:  # pragma: no cover
    """
    Generate a question based on a config property and prompt the user for it.
    """
    if not (question := _get_question(prop, annotation)):
        return default

    question["name"] = prop
    question["message"] = question.get("message", f"{prop}? ")
    default = typing.cast(T, default or question.get("default") or "")

    if annotation == int:
        default = typing.cast(T, str(default))

    response = questionary.unsafe_prompt([question], default=default)[prop]
    return typing.cast(T, response)


@app.command()
@with_exit_code(hide_tb=IS_DEBUG)
def setup(
    config_file: typing.Annotated[Optional[str], typer.Option("--config", "-c")] = None,
    minimal: bool = False,
) -> None:  # pragma: no cover
    """
    Setup a [tool.typedal] entry in the local pyproject.toml.
    """
    # 1. check if [tool.typedal] in pyproject.toml and ask missing questions (excl .env vars)
    # 2. else if [tool.migrate] and/or [tool.pydal2sql] exist in the config, ask the user with copied defaults
    # 3. else: ask the user every question or minimal questions based on cli arg

    config = load_config(config_file)

    toml_path = Path(config.pyproject)

    if not (config.pyproject and toml_path.exists()):
        # no pyproject.toml found!
        toml_path = toml_path if config.pyproject else Path("pyproject.toml")
        rich.print(f"[blue]Config toml doesn't exist yet, creating {toml_path}[/blue]", file=sys.stderr)
        toml_path.touch()

    toml_contents = toml_path.read_text()
    # tomli has native Python types, tomlkit doesn't but preserves comments
    toml_obj: dict[str, typing.Any] = tomli.loads(toml_contents)

    if "[tool.typedal]" in toml_contents:
        section = toml_obj["tool"]["typedal"]
        config.update(**section, _overwrite=True)

    if "[tool.pydal2sql]" in toml_contents:
        mapping = {"": ""}  # <- placeholder

        extra_config = toml_obj["tool"]["pydal2sql"]
        extra_config = {mapping.get(k, k): v for k, v in extra_config.items()}
        extra_config.pop("format", None)  # always edwh-migrate
        config.update(**extra_config)

    if "[tool.migrate]" in toml_contents:
        mapping = {"migrate_uri": "database"}

        extra_config = toml_obj["tool"]["migrate"]
        extra_config = {mapping.get(k, k): v for k, v in extra_config.items()}

        config.update(**extra_config)

    data = asdict(config, with_top_level_key=False)
    data["migrate"] = None  # determined based on existence of input/output file.
    for prop, annotation in TypeDALConfig.__annotations__.items():
        if is_alias(config.__class__, prop):
            # don't store aliases!
            data.pop(prop, None)
            continue

        if minimal and getattr(config, prop, None) not in (None, "") or is_optional(annotation):
            # property already present or not required, SKIP!
            data[prop] = getattr(config, prop, None)
            continue

        fill_defaults(data, prop)
        # default_value = getattr(config, prop, None)
        default_value = data.get(prop, None)
        answer: typing.Any = get_question(prop, annotation, default_value)

        if annotation == bool:
            answer = bool(answer)
        elif annotation == int:
            answer = int(answer)

        config.update(**{prop: answer})
        data[prop] = answer

    for prop in TypeDALConfig.__annotations__:
        transform(data, prop)

    with toml_path.open("r") as f:
        old_contents: dict[str, typing.Any] = tomlkit.load(f)

    if "tool" not in old_contents:
        old_contents["tool"] = {}

    data.pop("pyproject", None)

    # ignore any None:
    old_contents["tool"]["typedal"] = {k: v for k, v in data.items() if v is not None}

    with toml_path.open("w") as f:
        tomlkit.dump(old_contents, f)

    rich.print(f"[green]Wrote updated config to {toml_path}![/green]")


@app.command()
@with_exit_code(hide_tb=IS_DEBUG)
def generate_migrations(
    filename_before: OptionalArgument[str] = None,
    filename_after: OptionalArgument[str] = None,
    dialect: DBType_Option = None,
    tables: Tables_Option = None,
    magic: Optional[bool] = None,
    noop: Optional[bool] = None,
    function: Optional[str] = None,
    output_format: OutputFormat_Option = None,
    output_file: Optional[str] = None,
    dry_run: bool = False,
) -> bool:
    """
    Run pydal2sql based on the typedal config.
    """
    # 1. choose CREATE or ALTER based on whether 'output' exists?
    # 2. pass right args based on 'config' to function chosen in 1.
    generic_config = load_config()
    pydal2sql_config = generic_config.to_pydal2sql()
    pydal2sql_config.update(
        magic=magic,
        noop=noop,
        tables=tables,
        db_type=dialect.value if dialect else None,
        function=function,
        format=output_format,
        input=filename_before,
        output=output_file,
    )

    if pydal2sql_config.output and Path(pydal2sql_config.output).exists():
        if dry_run:
            print("Would run `pyda2sql alter` with config", asdict(pydal2sql_config), file=sys.stderr)
            sys.stderr.flush()

            return True
        else:  # pragma: no cover
            return core_alter(
                pydal2sql_config.input,
                filename_after or pydal2sql_config.input,
                db_type=pydal2sql_config.db_type,
                tables=pydal2sql_config.tables,
                noop=pydal2sql_config.noop,
                magic=pydal2sql_config.magic,
                function=pydal2sql_config.function,
                output_format=pydal2sql_config.format,
                output_file=pydal2sql_config.output,
            )
    else:
        if dry_run:
            print("Would run `pyda2sql create` with config", asdict(pydal2sql_config), file=sys.stderr)
            sys.stderr.flush()

            return True
        else:  # pragma: no cover
            return core_create(
                filename=pydal2sql_config.input,
                db_type=pydal2sql_config.db_type,
                tables=pydal2sql_config.tables,
                noop=pydal2sql_config.noop,
                magic=pydal2sql_config.magic,
                function=pydal2sql_config.function,
                output_format=pydal2sql_config.format,
                output_file=pydal2sql_config.output,
            )


@app.command()
@with_exit_code(hide_tb=IS_DEBUG)
def run_migrations(
    migrations_file: OptionalArgument[str] = None,
    db_uri: Optional[str] = None,
    db_folder: Optional[str] = None,
    schema_version: Optional[str] = None,
    redis_host: Optional[str] = None,
    migrate_cat_command: Optional[str] = None,
    database_to_restore: Optional[str] = None,
    migrate_table: Optional[str] = None,
    flag_location: Optional[str] = None,
    schema: Optional[str] = None,
    create_flag_location: Optional[bool] = None,
    dry_run: bool = False,
) -> bool:
    """
    Run edwh-migrate based on the typedal config.
    """
    # 1. build migrate Config from TypeDAL config
    # 2. import right file
    # 3. `activate_migrations`
    generic_config = load_config()
    migrate_config = generic_config.to_migrate()

    migrate_config.update(
        migrate_uri=db_uri,
        schema_version=schema_version,
        redis_host=redis_host,
        migrate_cat_command=migrate_cat_command,
        database_to_restore=database_to_restore,
        migrate_table=migrate_table,
        flag_location=flag_location,
        schema=schema,
        create_flag_location=create_flag_location,
        db_folder=db_folder,
        migrations_file=migrations_file,
    )

    if dry_run:
        print("Would run `migrate` with config", asdict(migrate_config), file=sys.stderr)
    else:  # pragma: no cover
        edwh_migrate.console_hook([], config=migrate_config)
    return True


def version_callback() -> Never:
    """
    --version requested!
    """
    print(f"pydal2sql Version: {__version__}")

    raise typer.Exit(0)


def config_callback() -> Never:
    """
    --show-config requested.
    """
    config = load_config()

    print(repr(config))

    raise typer.Exit(0)


@app.callback(invoke_without_command=True)
def main(
    _: typer.Context,
    # stops the program:
    show_config: bool = False,
    version: bool = False,
) -> None:
    """
    This script can be used to generate the create or alter sql from pydal or typedal.
    """
    if show_config:
        config_callback()
    elif version:
        version_callback()
    # else: just continue


if __name__ == "__main__":  # pragma: no cover
    app()
