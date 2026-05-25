# Stage 2 to Stage 3 Data Flow Fixes

## Issues Identified

1. **Missing job_id Assignment**: Candidates were not getting `job_id` field set directly, only through Application table
2. **Incomplete Candidate Fetching**: Stage 3 expected `candidate.job_id` but it wasn't being set consistently
3. **Job Data Not Properly Linked**: Relationship between candidates and jobs was only through Application table
4. **Poor Error Handling**: Limited logging and error handling for missing job links

## Fixes Implemented

### 1. Profile Parser (`sourcing/profile_parser.py`)

**Changes Made:**
- Added job_id assignment to candidate record during parsing
- Enhanced logging to track job_id assignment
- Both auto-parsing and manual parsing now set candidate.job_id

**Key Fix:**
```python
# CRITICAL FIX: Set job_id on candidate for Stage 3 screening
if job_id:
    candidate.job_id = job_id
    print(f"✅ Set job_id {job_id} on candidate {candidate_id}")
else:
    print(f"⚠️ No job_id found for candidate {candidate_id} - Stage 3 screening will fail")
```

### 2. Resume Collector (`sourcing/resume_collector.py`)

**Changes Made:**
- Set job_id directly on candidate record during creation
- Ensures job_id is available from the start of the pipeline

**Key Fix:**
```python
candidate = Candidate(
    id=cand_id,
    name=filename.rsplit(".", 1)[0].replace("_", " ").replace("-", " ").title(),
    resume_url=file_path,
    source="upload",
    status="uploaded",
    job_id=job_id,  # CRITICAL FIX: Set job_id directly on candidate
)
```

### 3. Screening Processor (`screening/processor.py`)

**Changes Made:**
- Enhanced candidate fetching with fallback to Application table
- Added comprehensive logging for debugging
- Improved error handling and status reporting
- Added job_id to all return values

**Key Improvements:**
- Automatic linking of candidates to jobs through Application records
- Better error messages and logging
- Consistent job_id handling across all code paths

### 4. Screening Shortlister (`screening/shortlister.py`)

**Changes Made:**
- Enhanced event processing with job_id tracking
- Improved logging for debugging
- Better error handling in event processing

### 5. New Utility: Candidate Job Linker (`screening/candidate_job_linker.py`)

**Purpose:**
- Fix existing candidates that don't have job_id set
- Link candidates to jobs through Application records
- Provide utilities for ensuring candidate-job relationships

**Key Functions:**
- `link_candidates_to_jobs()`: Batch link all unlinked candidates
- `ensure_candidate_job_link()`: Ensure specific candidate has job_id

### 6. Enhanced Screening API (`screening/screening_api.py`)

**New Endpoint:**
- `POST /screening/link-candidates`: Fix candidates missing job_id links

## Testing

Created comprehensive test script (`test_stage2_to_stage3_flow.py`) that verifies:

1. **Complete Flow Testing:**
   - Job creation
   - Candidate creation with job_id
   - Application record creation
   - Event publishing (Stage 2 behavior)
   - Stage 3 processing
   - Database updates

2. **Edge Case Testing:**
   - Candidates without job_id
   - Orphaned candidates
   - Candidate linking utility

3. **Error Handling:**
   - Missing job records
   - Invalid candidate data
   - Event processing failures

## Usage Instructions

### For New Candidates (Stage 2)
1. When uploading resumes, always provide `job_id` parameter
2. The system will automatically set `candidate.job_id` during parsing
3. Events will include complete job information for Stage 3

### For Existing Candidates
1. Run the linking endpoint to fix candidates missing job_id:
   ```bash
   curl -X POST "http://localhost:8000/api/screening/link-candidates"
   ```

2. Or use the utility directly:
   ```python
   from screening.candidate_job_linker import link_candidates_to_jobs
   with db_session() as db:
       result = link_candidates_to_jobs(db)
   ```

### For Testing
Run the test script to verify everything works:
```bash
python test_stage2_to_stage3_flow.py
```

## API Endpoints Enhanced

- `POST /screening/link-candidates` - Fix candidate-job links
- `POST /screening/run` - Run screening with better error handling
- `GET /screening/candidates` - List candidates with job information
- `GET /screening/stats` - Get screening statistics by job

## Key Benefits

1. **Reliable Data Flow**: Candidates are now properly linked to jobs from Stage 2
2. **Better Error Handling**: Clear error messages when job_id is missing
3. **Automatic Recovery**: System can fix existing candidates missing job links
4. **Enhanced Logging**: Better visibility into the screening process
5. **Comprehensive Testing**: Test suite ensures reliability

## Monitoring

The system now provides better logging at key points:
- Job_id assignment during parsing
- Candidate-job linking attempts
- Screening process status
- Error conditions and recovery

Check logs for messages like:
- `✅ Set job_id {job_id} on candidate {candidate_id}`
- `✅ Successfully linked candidate {candidate_id} to job {job_id}`
- `⚠️ No job_id found for candidate {candidate_id}`