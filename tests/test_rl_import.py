"""
Simple test to check RLSession import.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    from app.models.aptitude import RLSession
    print("✅ RLSession import successful")
    print(f"RLSession class: {RLSession}")
    
    # Try to create an instance
    session = RLSession(
        round_id=1,
        step_number=1,
        action_taken="medium"
    )
    print(f"✅ RLSession instance created: {session}")
    
except ImportError as e:
    print(f"❌ RLSession import failed: {e}")
    print("Checking available models...")
    
    # Check what's available in aptitude models
    from app.models.aptitude import *
    print("Available in aptitude module:")
    for name in dir():
        if not name.startswith('_'):
            print(f"  - {name}")
