"""
Property-Based Tests for Phone Detection Service

Tests universal properties of the phone detection threshold filtering logic.
Uses hypothesis library with 100 iterations per property.

Feature: interview-enhancements
"""

import sys
from pathlib import Path
from unittest.mock import Mock, patch
from typing import List, Dict

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from hypothesis import given, strategies as st, settings
import pytest

# Import the service module
from app.services.phone_detection_service import (
    PHONE_CONFIDENCE_THRESHOLD,
    CELL_PHONE_CLASS_ID
)


# ============================================================================
# Property 4: Violation Threshold Filtering
# ============================================================================
# **Validates: Requirements 5.4**
#
# For any detection with a confidence score, if the confidence is above the
# threshold (0.6 for phones), then a violation should be logged; if below
# the threshold, no violation should be logged.
# ============================================================================

@pytest.mark.property
@settings(max_examples=100)
@given(
    confidence_scores=st.lists(
        st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
        min_size=0,
        max_size=20
    )
)
def test_property_4_violation_threshold_filtering(confidence_scores: List[float]):
    """
    Property 4: Violation Threshold Filtering
    
    **Validates: Requirements 5.4**
    
    For any list of confidence scores (0.0 to 1.0), verify that:
    - Detections with confidence >= 0.6 are included in results
    - Detections with confidence < 0.6 are filtered out
    
    Tag: Feature: interview-enhancements, Property 4: Violation Threshold Filtering
    """
    # Mock the YOLO model and its results
    mock_model = Mock()
    mock_results = []
    
    # Create mock result object with boxes
    mock_result = Mock()
    mock_boxes = []
    
    for confidence in confidence_scores:
        # Create a mock box for each confidence score
        mock_box = Mock()
        mock_box.conf = [confidence]
        mock_box.cls = [CELL_PHONE_CLASS_ID]
        mock_box.xyxy = [[100.0, 100.0, 200.0, 200.0]]  # dummy bbox
        mock_boxes.append(mock_box)
    
    mock_result.boxes = mock_boxes
    mock_results.append(mock_result)
    
    # Configure the mock model to return our mock results
    mock_model.return_value = mock_results
    
    # Create a valid test image (1x1 black pixel JPEG)
    # This is a minimal valid JPEG image
    test_image_bytes = bytes([
        0xFF, 0xD8, 0xFF, 0xE0, 0x00, 0x10, 0x4A, 0x46,
        0x49, 0x46, 0x00, 0x01, 0x01, 0x00, 0x00, 0x01,
        0x00, 0x01, 0x00, 0x00, 0xFF, 0xDB, 0x00, 0x43,
        0x00, 0x08, 0x06, 0x06, 0x07, 0x06, 0x05, 0x08,
        0x07, 0x07, 0x07, 0x09, 0x09, 0x08, 0x0A, 0x0C,
        0x14, 0x0D, 0x0C, 0x0B, 0x0B, 0x0C, 0x19, 0x12,
        0x13, 0x0F, 0x14, 0x1D, 0x1A, 0x1F, 0x1E, 0x1D,
        0x1A, 0x1C, 0x1C, 0x20, 0x24, 0x2E, 0x27, 0x20,
        0x22, 0x2C, 0x23, 0x1C, 0x1C, 0x28, 0x37, 0x29,
        0x2C, 0x30, 0x31, 0x34, 0x34, 0x34, 0x1F, 0x27,
        0x39, 0x3D, 0x38, 0x32, 0x3C, 0x2E, 0x33, 0x34,
        0x32, 0xFF, 0xC0, 0x00, 0x0B, 0x08, 0x00, 0x01,
        0x00, 0x01, 0x01, 0x01, 0x11, 0x00, 0xFF, 0xC4,
        0x00, 0x14, 0x00, 0x01, 0x00, 0x00, 0x00, 0x00,
        0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
        0x00, 0x00, 0x00, 0x03, 0xFF, 0xC4, 0x00, 0x14,
        0x10, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
        0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
        0x00, 0x00, 0xFF, 0xDA, 0x00, 0x08, 0x01, 0x01,
        0x00, 0x00, 0x3F, 0x00, 0x37, 0xFF, 0xD9
    ])
    
    # Patch the model getter and run the detection
    with patch('app.services.phone_detection_service.get_yolo_model', return_value=mock_model):
        from app.services.phone_detection_service import detect_phones
        
        detections = detect_phones(test_image_bytes)
    
    # Verify the property: only detections >= threshold should be included
    expected_count = sum(1 for score in confidence_scores if score >= PHONE_CONFIDENCE_THRESHOLD)
    actual_count = len(detections)
    
    assert actual_count == expected_count, (
        f"Expected {expected_count} detections (scores >= {PHONE_CONFIDENCE_THRESHOLD}), "
        f"but got {actual_count}. "
        f"Input scores: {confidence_scores}, "
        f"Detections: {detections}"
    )
    
    # Verify all returned detections have confidence >= threshold
    for detection in detections:
        assert detection['confidence'] >= PHONE_CONFIDENCE_THRESHOLD, (
            f"Detection with confidence {detection['confidence']} should not be included "
            f"(threshold is {PHONE_CONFIDENCE_THRESHOLD})"
        )
    
    # Verify all returned detections are from the input scores
    returned_confidences = [d['confidence'] for d in detections]
    for conf in returned_confidences:
        # Account for rounding to 3 decimal places in the service
        assert any(abs(conf - score) < 0.001 for score in confidence_scores), (
            f"Returned confidence {conf} not found in input scores {confidence_scores}"
        )


if __name__ == "__main__":
    # Run the property test
    print("Running Property 4: Violation Threshold Filtering")
    print("=" * 70)
    print("Feature: interview-enhancements")
    print("Property 4: Violation Threshold Filtering")
    print("Validates: Requirements 5.4")
    print("=" * 70)
    
    pytest.main([__file__, "-v", "-m", "property"])
