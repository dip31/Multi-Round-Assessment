import pytest

from app.services import phone_detection_service as pds


def test_detect_phones_invalid_bytes_returns_empty():
    res = pds.detect_phones(b"not an image")
    assert res == []


def test_detect_phones_filters_by_class_and_conf(monkeypatch):
    class FakeBox:
        def __init__(self):
            self.cls = 67
            self.conf = 0.85
            self.xyxy = [10.0, 11.0, 20.0, 21.0]

    class FakeRes:
        def __init__(self):
            self.boxes = [FakeBox()]

    class FakeModel:
        def __call__(self, img, conf=0.6, verbose=False):
            return [FakeRes()]

    monkeypatch.setattr(pds, "get_yolo_model", lambda: FakeModel())

    # Create a small valid JPEG header to satisfy OpenCV decode
    # This is a minimal valid JPEG header + EOI
    jpeg = b"\xff\xd8\xff\xd9"
    detections = pds.detect_phones(jpeg, confidence_threshold=0.6)
    assert isinstance(detections, list)
    assert len(detections) == 1
    assert detections[0]["confidence"] >= 0.6
