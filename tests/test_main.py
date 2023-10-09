import re
import typing
from sqlite3 import IntegrityError

import pydal
import pytest
from pydal.objects import Query

from src.typedal import *
from src.typedal.__about__ import __version__
from src.typedal.fields import *


def test_about():
    version_re = re.compile(r"\d+\.\d+\.\d+.*")
    assert version_re.findall(__version__)


db = TypeDAL("sqlite:memory")


def test_mixed_defines():
    ### DEFINE

    # before:

    db.define_table("relation")

    db.define_table(
        "old_syntax",
        pydal.Field("name", "string", notnull=True),
        pydal.Field("age", "float", notnull=False),
        pydal.Field("location", "text", default="Amsterdam"),
        pydal.Field("relation", "reference relation"),
    )

    # after:

    @db.define
    class NewRelation(TypedTable):
        ...

    class SecondNewRelation(TypedTable):
        ...

    # db.define can be used as decorator or later on
    db.define(SecondNewRelation)

    # you can use native types or TypedField (if more settings are required, otherwise default are used)

    @db.define
    class FirstNewSyntax(TypedTable):
        # simple:
        name: str
        # optional: (sets required=False and notnull=False)
        age: float | None
        # with extra options (and non-native type 'text'):
        location = TypedField(str, type="text", default="Amsterdam")
        # references:
        # can only be made optional with typing.Optional, not '| None'
        first_new_relation: typing.Optional[NewRelation]
        second_new_relation: typing.Optional[SecondNewRelation]
        # backwards compatible:
        old_relation: typing.Optional[db.relation]
        # generics:
        tags: list[str]

    # instead of using just a native type, TypedField can also always be used:
    class SecondNewSyntax(TypedTable):
        # simple:
        name = TypedField(str)
        # optional: (sets required=False and notnull=False)
        # note: TypedField can NOT be used with typing.Optional or '| None' !!
        age = TypedField(float, notnull=False)
        # with extra options (and non-native type 'text'):
        location = TextField(default="Rotterdam")
        first_new_relation = ReferenceField(NewRelation)
        second_new_relation = ReferenceField(db.second_new_relation)
        # backwards compatible:
        old_relation = TypedField(db.relation, notnull=False)
        # generics:
        tags = TypedField(list[str])

    db.define(SecondNewSyntax)

    ### INSERTS
    db.relation.insert()

    db.new_relation.insert()
    # OR
    NewRelation.insert()
    SecondNewRelation.insert()

    ## insert without all required:

    with pytest.raises(IntegrityError):
        db.old_syntax.insert()

    with pytest.raises(IntegrityError):
        db.first_new_syntax.insert()

    # equals:

    with pytest.raises(IntegrityError):
        FirstNewSyntax.insert()

    with pytest.raises(IntegrityError):
        SecondNewSyntax.insert()

    ## insert normal
    db.old_syntax.insert(name="First", age=99, location="Norway", relation=db.relation(id=1))
    db.first_new_syntax.insert(
        name="First", age=99, location="Norway", old_relation=db.relation(id=1), tags=["first", "second"]
    )
    # equals
    FirstNewSyntax.insert(
        name="First", age=99, location="Norway", old_relation=db.relation(id=1), tags=["first", "second"]
    )
    # similar
    SecondNewSyntax.insert(
        name="Second",
        age=101,
        first_new_relation=NewRelation(id=1),
        second_new_relation=SecondNewRelation(id=1),
        tags=["first", "second"],
    )

    ### Select
    from pprint import pprint

    assert db(FirstNewSyntax.name == "First").count()
    assert db(FirstNewSyntax.location == "Norway").count()
    assert not db(FirstNewSyntax.location == "Nope").count()
    assert not db(FirstNewSyntax.location == "Nope").count()

    assert db(SecondNewSyntax.name == "Second").count()
    assert db(SecondNewSyntax.location == "Rotterdam").count()
    assert not db(SecondNewSyntax.location == "Nope").count()
    assert not db(SecondNewSyntax.location == "Nope").count()

    def _print_and_assert_len(lst, exp):
        pprint(lst)
        real = len(lst)
        assert real == exp, f"{real} != {exp}"

    _print_and_assert_len(db(db.old_syntax).select().as_list(), 1)
    _print_and_assert_len(db(db.old_syntax.id > 0).select().as_list(), 1)

    _print_and_assert_len(db(db.first_new_syntax).select().as_list(), 2)
    _print_and_assert_len(db(db.first_new_syntax.id > 0).select().as_list(), 2)

    _print_and_assert_len(db(FirstNewSyntax).select().as_list(), 2)
    _print_and_assert_len(db(FirstNewSyntax.id > 0).select().as_list(), 2)

    assert SecondNewSyntax(id=1) is not None
    assert SecondNewSyntax(1) is not None
    assert SecondNewSyntax(id=2) is None
    assert SecondNewSyntax(2) is None
    _print_and_assert_len(db(SecondNewSyntax).select().as_list(), 1)
    _print_and_assert_len(db(SecondNewSyntax.id > 0).select().as_list(), 1)

    assert SecondNewSyntax(1).location == "Rotterdam"


def test_dont_allow_bool_in_query():
    with pytest.raises(ValueError):
        db(True)


def test_invalid_union():
    with pytest.raises(NotImplementedError):
        @db.define
        class Invalid(TypedTable):
            valid: int | None
            invalid: int | str

    with pytest.raises(NotImplementedError):
        @db.define
        class Invalid(TypedTable):
            valid: list[int]
            invalid: dict[str, int]


def test_using_model_without_define():
    class Invalid(TypedTable):
        name: str

    # no db.define used
    with pytest.raises(EnvironmentError):
        Invalid.insert(name="error")

    with pytest.raises(EnvironmentError):
        Invalid(name="error")


def test_typedfield_reprs():
    # str() and repr()

    @db.define()
    class Demo(TypedTable):
        field1 = TypedField(str | None, default="yes")
        field2: TypedField[int | None]
        field3: int
        textfield = TypedField(type="text")

    assert Demo.field1
    assert Demo.field2
    assert Demo.field3
    assert Demo.textfield

    assert str(Demo.field1) == "demo.field1"
    assert str(Demo.field2) == "demo.field2"
    assert str(Demo.field3) == "demo.field3"
    assert str(Demo.textfield) == "demo.textfield"

    assert isinstance(Demo.field1, TypedField)
    assert isinstance(Demo.field2, TypedField)
    assert isinstance(Demo.field3, pydal.objects.Field)
    assert isinstance(Demo.textfield, TypedField)

    assert repr(Demo.field1) == "<TypedField[str].demo.field1 with options {'default': 'yes'}>"
    assert repr(Demo.field2) == "<TypedField[int].demo.field2 with options {}>"
    assert repr(Demo.textfield) == "<TypedField[text].demo.textfield with options {}>"


def test_typedfield_to_field_type():
    @db.define()
    class SomeTable(TypedTable):
        name = TypedField(str)  # basic mapping

    @db.define()
    class OtherTable(TypedTable):
        second = ReferenceField(SomeTable)  # reference to TypedTable
        third = ReferenceField(db.some_table)  # reference to pydal table
        fourth = TypedField(list[str])  # generic alias
        optional_one = TypedField(typing.Optional[str])
        optional_two = TypedField(str | None)

    with pytest.raises(NotImplementedError):
        @db.define()
        class Invalid(TypedTable):
            third = TypedField(dict[str, int])  # not supported


def test_fields():
    @db.define
    class SomeNewTable(TypedTable):
        name: str
        name_alt = TypedField(str)

    class OtherNewTable(TypedTable):
        name: str

    db.define(OtherNewTable)

    @db.define()
    class Everything(TypedTable):
        stringfield = StringField()
        blobfield = BlobField()
        booleanfield = Boolean()
        integerfield = IntegerField()
        doublefield = DoubleField()
        decimalfield = DecimalField(1, 1)
        datefield = DateField()
        timefield = TimeField()
        datetimefield = DatetimeField()
        passwordfield = PasswordField()
        uploadfield = UploadField()
        referencefield_some_new_table = ReferenceField(db.some_new_table)
        referencefield_SomeNewTable = ReferenceField(SomeNewTable)
        referencefield_other = ReferenceField("other_new_table")
        referencefield_OtherNewTable = ReferenceField(OtherNewTable)
        liststringfield = ListStringField()
        listintegerfield = ListIntegerField()
        listreferencefield_somenewtable = ListReferenceField("somenewtable")
        jsonfield = JSONField()
        bigintfield = BigintField()

    with pytest.raises(ValueError):
        @db.define()
        class Wrong(TypedTable):
            stringfield = ReferenceField(object())

    # test typedset:
    counted1 = db(SomeNewTable).count()
    counted2 = db(OtherNewTable).count()
    counted3 = db(db.some_new_table).count()

    assert counted1 == counted2 == counted3 == 0

    select2: TypedRows[SomeNewTable] = db(SomeNewTable.id > 0).select(SomeNewTable.name, SomeNewTable.name_alt)

    if list(select2):
        raise ValueError("no rows should exist")

    SomeNewTable.update_or_insert(
        SomeNewTable.name == "Hendrik",
        name="Hendrik 2",
        name_alt="Hendrik II"
    )

    instance = OtherNewTable.update_or_insert(
        OtherNewTable.name == "Hendrik",
        name="Hendrik 2",
    )
    assert instance

    OtherNewTable.update_or_insert(
        OtherNewTable.name == "Hendrik",
        name="Hendrik 2",
    )

    assert db(SomeNewTable.name == "Hendrik").count() == 0
    assert db(SomeNewTable.name == "Hendrik 2").count() == 1

    assert db(OtherNewTable.name == "Hendrik").count() == 0
    assert db(OtherNewTable.name == "Hendrik 2").count() == 2

    instance = OtherNewTable.update_or_insert(
        OtherNewTable.name == "Hendrik 2",
        name="Hendrik 3",
    )  # should update and return new version

    assert instance
    assert instance.name == "Hendrik 3"

    assert db(OtherNewTable.name == "Hendrik 2").count() == 1
    assert db(OtherNewTable.name == "Hendrik 3").count() == 1


def test_quirks():
    # don't inherit TypedTable:

    class NonInherit:
        name: str

    with pytest.warns(UserWarning):
        db.define(NonInherit)

    # instanciating a TypedTable with an existing TypedTable
    @db.define()
    class MyTypedTable(TypedTable):
        string: str

    inst = MyTypedTable.insert(string="111")

    inst_copy = MyTypedTable(inst)

    assert inst == inst_copy

    repred = repr(inst)
    assert "MyTypedTable" in repred
    assert "string" in repred
    assert "111" in repred
    inst.delete_record()

    repred = repr(inst)
    assert "MyTypedTable" in repred
    assert "string" not in repred
    assert "111" not in repred

    with pytest.raises(EnvironmentError):
        # inst is deleted, so almost everything will raise an error now (except repr).
        inst.as_dict()
