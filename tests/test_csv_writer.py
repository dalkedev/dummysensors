from dummysensors.io import csv_writer


def test_csv_writes_header_and_rows(tmp_path):
    path = tmp_path / "out.csv"
    w = csv_writer(str(path))
    w({"ts_ms": 1, "device_id": "A", "sensor_id": "temp-0", "type": "temp", "value": 42})
    text = path.read_text().strip().splitlines()
    assert text[0].startswith("ts_ms,device_id,sensor_id,type,value")
    assert len(text) == 2
