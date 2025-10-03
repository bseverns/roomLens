import csv
import io

from tools.capture_logger import capture_stream


def test_capture_stream_creates_csv_on_confirmation(tmp_path):
    stdin = io.StringIO(
        """
{"sensor": "imu", "value": 42}
not json
{"sensor": "imu", "value": 43}
""".strip()
    )

    out_path = tmp_path / "capture.csv"

    confirmed = capture_stream(stdin, out_path, lambda _: True)

    assert confirmed is True
    assert out_path.exists()

    with out_path.open() as fh:
        reader = csv.DictReader(fh)
        rows = list(reader)

    assert reader.fieldnames == ["sensor", "value"]
    assert rows == [
        {"sensor": "imu", "value": "42"},
        {"sensor": "imu", "value": "43"},
    ]


def test_capture_stream_skips_file_when_not_confirmed(tmp_path):
    out_path = tmp_path / "capture.csv"

    confirmed = capture_stream(io.StringIO("{}"), out_path, lambda _: False)

    assert confirmed is False
    assert not out_path.exists()
