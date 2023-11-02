# TypeDAL

[![PyPI - Version](https://img.shields.io/pypi/v/TypeDAL.svg)](https://pypi.org/project/TypeDAL)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/TypeDAL.svg)](https://pypi.org/project/TypeDAL)  
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)  
[![su6 checks](https://github.com/trialandsuccess/TypeDAL/actions/workflows/su6.yml/badge.svg?branch=development)](https://github.com/trialandsuccess/TypeDAL/actions)
![coverage.svg](coverage.svg)

Typing support for [PyDAL](http://web2py.com/books/default/chapter/29/6).
This package aims to improve the typing support for PyDAL. By using classes instead of the define_table method,
type hinting the result of queries can improve the experience while developing. In the background, the queries are still
generated and executed by pydal itself, this package only proves some logic to properly pass calls from class methods to
the underlying `db.define_table` pydal Tables.

- `TypeDAL` is the replacement class for DAL that manages the code on top of DAL.
- `TypedTable` must be the parent class of any custom Tables you define (e.g. `class SomeTable(TypedTable)`)
- `TypedField` can be used instead of Python native types when extra settings (such as `default`) are required (
  e.g. `name = TypedField(str, default="John Doe")`). It can also be used in an annotation (`name: TypedField[str]`) to improve
  editor support over only annotating with `str`.
- `TypedRows`: can be used as the return type annotation of pydal's `.select()` and subscribed with the actual table class, so
  e.g. `rows: TypedRows[SomeTable] = db(...).select()`. When using the QueryBuilder, a `TypedRows` instance is returned by `.collect()`.

Version 2.0 also introduces more ORM-like funcionality.
Most notably, a Typed Query Builder that sees your table classes as models with relationships to each other.
See [3. Building Queries](https://github.com/trialandsuccess/TypeDAL/blob/master/docs/3_building_queries.md) for more
details.

## Quick Overview

Below you'll find a quick overview of translation from pydal to TypeDAL. For more info,
see [the docs](https://github.com/trialandsuccess/TypeDAL/tree/master/docs).

### Translations from pydal to typedal

<table>
<tr>
<td>Description</td>
<td> pydal </td> <td> typedal </td> <td> typedal alternative(s) </td> <td> ... </td>
</tr>
<tr>
<tr>
<td>Setup</td>
<td>

```python
from pydal import DAL, Field

db = DAL(...)
```

</td>

<td>

```python
from typedal import TypeDAL, TypedTable, TypedField

db = TypeDAL(...)
```

</td>

</tr>
<tr>
<td>Table Definitions</td>
<td>

```python
db.define_table("table_name",
                Field("fieldname", "string", required=True),
                Field("otherfield", "float"),
                Field("yet_another", "text", default="Something")
                )
```

</td>

<td>

```python
@db.define
class TableName(TypedTable):
    fieldname: str
    otherfield: float | None
    yet_another = TypedField(str, type="text", default="something", required=False)
```

</td>

<td>

```python
import typing


class TableName(TypedTable):
    fieldname: TypedField[str]
    otherfield: TypedField[typing.Optional[float]]
    yet_another = TextField(default="something", required=False)


db.define(TableName)
```

</td>
</tr>

<tr>
<td>Insert</td>

<td>

```python
db.table_name.insert(fieldname="value")
```

</td>

<td>

```python
TableName.insert(fieldname="value")
```

<td>

```python
# the old syntax is also still supported:
db.table_name.insert(fieldname="value")
```

</td>
</tr>

<tr>
<td>(quick) Select</td>


<td>

```python
# all:
all_rows = db(db.table_name).select()  # -> Any (Rows)
# some:
rows = db((db.table_name.id > 5) & (db.table_name.id < 50)).select(db.table_name.id)
# one:
row = db.table_name(id=1)  # -> Any (Row)
```

</td>

<td>

```python
# all:
all_rows = TableName.collect()  # or .all()
# some:
# order of select and where is interchangable here
rows = TableName.select(Tablename.id).where(TableName.id > 5).where(TableName.id < 50).collect()
# one:
row = TableName(id=1)  # or .where(...).first()

```

<td>

```python
# you can also still use the old syntax and type hint on top of it;
# all:
all_rows: TypedRows[TableName] = db(db.table_name).select()
# some:
rows: TypedRows[TableName] = db((db.table_name.id > 5) & (db.table_name.id < 50)).select(db.table_name.id)
# one:
row: TableName = db.table_name(id=1)
```

</td>


</tr>

</table>


<!-- 
<td>

```python

```

</td>

<td>

<td>

```python

```

</td>
</tr>
-->

### All Types

See [2. Defining Tables](docs/2_defining_tables.md)

## Roadmap

This section contains a non-exhaustive list of planned features for future feature releases:

- 2.2
    - Migrations: currently, you can use pydal's automatic migrations or disable those and manage them yourself, but
      adding something like [`edwh-migrate`](https://github.com/educationwarehouse/migrate#readme)
      with [`pydal2sql`](https://github.com/robinvandernoord/pydal2sql-core) as an option could make this project more
      production-friendly.

## Caveats

- This package depends heavily on the current implementation of annotations (which are computed when the class is
  defined). PEP 563 (Postponed Evaluation of Annotations, accepted) aims to change this behavior (
  and `from __future__ import annotations` already does) in a way that this module currently can not handle: all
  annotations are converted to string representations. This makes it very hard to re-evaluate the annotation into the
  original type, since the variable scope is lost (and thus references to variables or other classes are ambiguous or
  simply impossible to find).
- `TypedField` limitations; Since pydal implements some magic methods to perform queries, some features of typing will
  not work on a typed field: `typing.Optional` or a union (`Field() | None`) will result in errors. The only way to make
  a typedfield optional right now, would be to set `required=False` as an argument yourself. This is also a reason
  why `typing.get_type_hints` is not a solution for the first caveat.
