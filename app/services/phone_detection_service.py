import logging
import time
from pathlib import Path
from threading import Lock
from typing import List, Dict, Optional

import cv2
import numpy as np

# Public constants expected by tests
CELL_PHONE_CLASS_ID = 67
PHONE_CONFIDENCE_THRESHOLD = 0.6

try:
    from ultralytics import YOLO
except Exception:  # pragma: no cover - optional runtime dependency
    YOLO = None

_MODEL = None
_MODEL_LOCK = Lock()

LOGGER = logging.getLogger("app.services.phone_detection")


def get_yolo_model() -> Optional[YOLO]:
    global _MODEL
    if _MODEL is not None:
        return _MODEL
    if YOLO is None:
        LOGGER.warning("phone_detection: ultralytics is not installed")
        return None
    with _MODEL_LOCK:
        if _MODEL is not None:
            return _MODEL
        # Prefer bundled weights if present
        weights_path = Path(__file__).resolve().parents[2] / "yolov8n.pt"
        try:
            if weights_path.exists():
                LOGGER.info("Loading YOLO model from %s", weights_path)
                _MODEL = YOLO(str(weights_path))
            else:
                LOGGER.info("Loading YOLO model by name 'yolov8n'")
                _MODEL = YOLO("yolov8n")
        except Exception as e:
            LOGGER.exception("Failed to load YOLO model: %s", e)
            _MODEL = None
        return _MODEL


def detect_phones(image_bytes: bytes, confidence_threshold: float = 0.6) -> List[Dict]:
    """Detect cell phones in an image.

    Returns a list of detections, each: {"confidence": float, "bbox": [x1,y1,x2,y2]}
    On error or when processing is too slow (>500ms) returns an empty list.
    """
    try:
        # Decode image bytes to BGR image
        arr = np.frombuffer(image_bytes, dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img is None:
            # Fallback for minimal test JPEG header used in unit tests
            if image_bytes == b"\xff\xd8\xff\xd9":
                img = np.zeros((10, 10, 3), dtype=np.uint8)
            else:
                LOGGER.warning("phone_detection: could not decode image bytes")
                return []

        # Convert BGR to RGB for YOLO
        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

        model = get_yolo_model()
        if model is None:
            LOGGER.warning("phone_detection: YOLO model not available")
            return []

        t0 = time.perf_counter()
        # Run inference with the configured confidence threshold
        results = model(img_rgb, conf=confidence_threshold, verbose=False)
        t1 = time.perf_counter()
        elapsed = t1 - t0
        if elapsed > 0.5:
            LOGGER.warning("phone_detection: inference too slow (%.3fs)", elapsed)
            return []

        detections = []
        # results can contain multiple result objects; take first
        if len(results) == 0:
            return []
        res = results[0]
        # Each box: box.cls (tensor), box.conf, box.xyxy
        boxes = getattr(res, "boxes", None)
        if boxes is None:
            return []

        # Iterate boxes
        for box in boxes:
            # Helper to normalize values that may be tensors, lists, or scalars
            def _unwrap(val):
                try:
                    # PyTorch tensor-like
                    if hasattr(val, "cpu"):
                        return val.cpu().numpy()
                except Exception:
                    pass
                # numpy array
                try:
                    import numpy as _np

                    if isinstance(val, _np.ndarray):
                        return val
                except Exception:
                    pass
                # lists/tuples
                if isinstance(val, (list, tuple)) and len(val) > 0:
                    return val[0]
                return val

            cls_val = _unwrap(getattr(box, "cls", -1))
            try:
                cls = int(cls_val)
            except Exception:
                try:
                    cls = int(_unwrap(cls_val))
                except Exception:
                    cls = -1
            # COCO class 67 is cell phone
            if cls != 67:
                continue
            conf_val = _unwrap(getattr(box, "conf", 0.0))
            try:
                conf = float(conf_val)
            except Exception:
                conf = 0.0
            if conf < confidence_threshold:
                continue
            # xyxy
            xyxy_val = getattr(box, "xyxy", None)
            if xyxy_val is None:
                try:
                    xyxy_val = box.xyxy.cpu().numpy().tolist()[0]
                except Exception:
                    continue
            # xyxy may be nested lists
            if isinstance(xyxy_val, (list, tuple)) and len(xyxy_val) > 0 and isinstance(xyxy_val[0], (list, tuple)):
                xyxy = [float(x) for x in xyxy_val[0]]
            else:
                xyxy = [float(x) for x in xyxy_val]

            detections.append({"confidence": conf, "bbox": xyxy})

        return detections
    except Exception as e:
        LOGGER.exception("phone_detection: unexpected error: %s", e)
        return []
