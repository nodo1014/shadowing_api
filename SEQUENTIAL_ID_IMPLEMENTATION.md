# Sequential ID Implementation

## Overview
Implemented date-based sequential folder naming system to replace UUID-based folders.

## Changes Made

### 1. ID Generator Module
Created `api/utils/id_generator.py`:
- Date-based sequential ID generation
- Maintains counters per date in `daily_job_counters.json`
- Thread-safe implementation with file persistence
- Format: 001, 002, 003... per day

### 2. API Updates
Updated all clip generation APIs:
- `/api/clip` - Single clip
- `/api/clip/batch` - Batch clips  
- `/api/clip/mixed` - Mixed templates
- `/api/extract/range` - Range extraction

Each API now:
- Generates sequential folder ID on request
- Passes folder_id to job processing
- Stores folder_id in job_status and database

### 3. Database Schema
Added `extra_data` JSON column to jobs table to store folder_id

### 4. Folder Structure
New structure:
```
output/
├── 2025-09-11/
│   ├── 001/
│   ├── 002/
│   ├── 003/
│   └── ...
└── 2025-09-12/
    ├── 001/
    ├── 002/
    └── ...
```

## Benefits
1. **Easy ordering**: Folders appear in creation order
2. **Daily reset**: Counter resets each day
3. **Simple navigation**: No more complex UUIDs
4. **Preserved job tracking**: Job IDs remain UUIDs in database

## Implementation Details
- Counter persisted in `daily_job_counters.json`
- Old date entries can be cleaned up automatically
- Zero-padded to 3 digits (001-999 per day)
- Thread-safe for concurrent requests

## Testing
Successfully tested sequential folder creation:
- Folder 007 created at 16:35
- Folder 008 created at 17:06
- Counter properly increments across requests