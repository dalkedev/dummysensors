from dummysensors.spec import parse_spec


def test_parse_spec():
    ds = parse_spec("device=A: temp*2,vibration*1; device=B: temp*3")
    assert len(ds) == 2 and ds[0].id == "A"
    assert ds[0].sensors[0].kind == "temp" and ds[0].sensors[0].count == 2
