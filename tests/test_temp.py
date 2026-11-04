from dummysensors import TemperatureSensor


def test_range():
    s = TemperatureSensor(min_val=10, max_val=20)
    vals = [s.read() for _ in range(100)]
    assert min(vals) > 8 and max(vals) < 22
