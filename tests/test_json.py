import json
import datetime as dt

from src.typedal.serializers.as_json import SerializedJson, encode


class CustomClass:
    value: int

    def __init__(self):
        self.value = 3


class JsonableCustomClass(CustomClass):
    def __json__(self):
        return {"the_value": self.value}


encoder = SerializedJson()


def test_set():
    dumped = encode({1, 2, 3})
    loaded: list = json.loads(dumped)

    converted: list = encoder.default({1, 2, 3})
    converted.sort()  # set order is not guaranteed
    loaded.sort()

    assert converted == [1, 2, 3] == loaded


def test_datetime():
    now = dt.datetime.utcnow()
    today = dt.date.today()
    time = now.time()

    assert encode(now) == f'"{now}"'
    assert encode(today) == f'"{today}"'
    assert encode(time) == f'"{time}"'

    assert encoder.default(now) == str(now)
    assert encoder.default(today) == str(today)
    assert encoder.default(time) == str(time)


def test_classes():
    assert encoder.default(CustomClass()) == {"value": 3}
    assert encode(CustomClass()) == '{"value": 3}'

    assert encoder.default(JsonableCustomClass()) == {"the_value": 3}
    assert encode(JsonableCustomClass()) == '{"the_value": 3}'

    instance = CustomClass()
    instance.__json__ = '<private information>'
    assert encoder.default(instance) == '<private information>'
    assert encode([instance]) == '["<private information>"]'