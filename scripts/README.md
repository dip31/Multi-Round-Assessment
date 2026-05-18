# Scripts Directory

Utility scripts for database seeding and verification.

---

## Available Scripts

### 1. seed_problem_bank.py

Seeds the coding problem bank from `problem_bank.json` into the database.

**Usage:**
```bash
python -m scripts.seed_problem_bank
```

**What it does:**
- Loads 20 coding problems from `problem_bank.json`
- Inserts problems into `coding_problems` table
- Inserts test cases into `coding_test_cases` table
- Maintains test case order and visibility (hidden/visible)
- **Idempotent**: Safe to run multiple times (skips existing problems)

**Expected Output:**
```
Loading problems from: /path/to/problem_bank.json
Found 20 problems in JSON.

  [OK]     'Sum of Array Elements' inserted with 7 test cases.
  [OK]     'Reverse a String' inserted with 7 test cases.
  ...

=======================================================
  Problems  inserted : 20
  Problems  skipped  : 0
  Test cases inserted: 140
=======================================================
  Problem bank seeded successfully!
```

**If run again:**
```
  [SKIP]   'Sum of Array Elements' already in database.
  [SKIP]   'Reverse a String' already in database.
  ...

=======================================================
  Problems  inserted : 0
  Problems  skipped  : 20
  Test cases inserted: 0
=======================================================
  All problems already exist. Database unchanged.
```

---

### 2. verify_problem_bank.py

Verifies that the problem bank was seeded correctly.

**Usage:**
```bash
python -m scripts.verify_problem_bank
```

**What it does:**
- Counts total problems and test cases
- Shows difficulty breakdown (easy/medium/hard)
- Shows test case breakdown (visible/hidden)
- Lists sample problems
- Validates expected counts (20 problems, 140 test cases)

**Expected Output:**
```
============================================================
  PROBLEM BANK VERIFICATION
============================================================

  Total Problems:      20
  Total Test Cases:    140

  Difficulty Breakdown:
    - Easy:            8
    - Medium:          8
    - Hard:            4

  Test Case Breakdown:
    - Visible:         40
    - Hidden:          100

============================================================

  Sample Problems:
  --------------------------------------------------------
    [easy  ] Sum of Array Elements (7 test cases)
    [easy  ] Reverse a String (7 test cases)
    [easy  ] Check Palindrome (7 test cases)
    [easy  ] Find Maximum Element (7 test cases)
    [easy  ] Count Vowels (7 test cases)
  --------------------------------------------------------

  ✅ SUCCESS: Expected 20 problems and 140 test cases found!
```

---

## Prerequisites

Before running these scripts, ensure:

1. **Database is running** (PostgreSQL)
2. **Migrations are applied**:
   ```bash
   alembic upgrade head
   ```
3. **Environment variables are set** (`.env` file exists)
4. **problem_bank.json exists** in project root

---

## Database Tables

### coding_problems
- id (PK)
- title
- description
- difficulty (easy/medium/hard)
- tags (array)
- input_format
- output_format
- constraints
- created_by
- created_at

### coding_test_cases
- id (PK)
- problem_id (FK → coding_problems.id)
- input_data
- expected_output
- is_hidden (boolean)
- case_order (integer)
- explanation

---

## Troubleshooting

### Import Errors
If you see `ModuleNotFoundError`, ensure you're running from the project root:
```bash
cd Multi-Round-Assesment
python -m scripts.seed_problem_bank
```

### Database Connection Errors
Check your `.env` file has the correct `DATABASE_URL`:
```env
DATABASE_URL=postgresql://postgres:password@localhost/ai_placement_platform
```

### No Problems Found
If verification shows 0 problems, run the seed script first:
```bash
python -m scripts.seed_problem_bank
```

---

## Development Notes

- Scripts use `sys.path.insert(0, PROJECT_ROOT)` to resolve `app.*` imports
- Database session is properly closed in `finally` block
- Transactions are rolled back on error
- All scripts are production-safe and idempotent
