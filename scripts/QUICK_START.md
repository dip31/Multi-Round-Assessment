# Quick Start - Problem Bank Seeding

## TL;DR

```bash
# 1. Seed the database
python -m scripts.seed_problem_bank

# 2. Verify it worked
python -m scripts.verify_problem_bank
```

---

## Expected Results

### After Seeding
```
✅ 20 problems inserted
✅ 140 test cases inserted
✅ Database ready for coding round
```

### After Verification
```
✅ Total Problems: 20
✅ Total Test Cases: 140
✅ Easy: 8, Medium: 8, Hard: 4
✅ Visible: 40, Hidden: 100
```

---

## If Something Goes Wrong

### Import Error
```bash
# Make sure you're in project root
cd Multi-Round-Assesment
python -m scripts.seed_problem_bank
```

### Database Error
```bash
# Run migrations first
alembic upgrade head
```

### Already Seeded
```
# Script is idempotent - safe to re-run
# Will skip existing problems
```

---

## Files Created

1. `scripts/seed_problem_bank.py` - Main seeding script
2. `scripts/verify_problem_bank.py` - Verification script
3. `scripts/README.md` - Detailed documentation
4. `SEEDING_GUIDE.md` - Complete guide
5. `SEED_SCRIPT_SUMMARY.md` - Implementation summary

---

## What Changed

**Before** (broken):
```python
from database.session import SessionLocal  # ❌
```

**After** (fixed):
```python
from app.database.db import SessionLocal  # ✅
```

---

## Need Help?

See full documentation:
- `scripts/README.md` - Scripts usage
- `SEEDING_GUIDE.md` - Complete guide
- `SEED_SCRIPT_SUMMARY.md` - Technical details
