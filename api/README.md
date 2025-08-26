# Video Clipping API - Modular Structure

This directory contains the modularized Video Clipping API, refactored from the monolithic clipping_api.py.

## Directory Structure

```
api/
├── __init__.py           # Package initialization
├── config.py            # API configuration and constants
├── models/              # Pydantic models
│   ├── __init__.py
│   ├── requests.py      # Request models
│   ├── responses.py     # Response models
│   └── validators.py    # Media validation
├── routes/              # API endpoints
│   ├── __init__.py
│   ├── health.py        # Health check routes
│   ├── clip.py          # Single clip creation
│   ├── batch.py         # Batch processing
│   ├── textbook.py      # Textbook lessons
│   ├── status.py        # Job status checking
│   ├── download.py      # File downloads
│   └── admin.py         # Admin operations
└── utils/               # Utility functions
    ├── __init__.py
    ├── text_processing.py  # Text manipulation
    └── job_management.py   # Job status tracking
```

## Usage

The API is now started using `main.py` instead of `clipping_api.py`:

```bash
# Using uvicorn directly
uvicorn main:app --host 0.0.0.0 --port 8000

# Or using the Python script
python main.py
```

## Migration Notes

- `clipping_api.py` is now a compatibility wrapper that redirects to `main.py`
- All functionality remains the same, just organized into modules
- The original file is preserved as `clipping_api_old.py`

## Key Changes

1. **Models Separation**: Request/response models are in `api/models/`
2. **Route Organization**: Each endpoint group has its own file in `api/routes/`
3. **Utility Functions**: Common functions are in `api/utils/`
4. **Configuration**: Centralized in `api/config.py`
5. **Main Application**: Clean entry point in `main.py`

## Benefits

- Better code organization and maintainability
- Easier to find and modify specific functionality
- Reduced file size (from 2198 lines to modular components)
- Improved testability
- Clear separation of concerns