#!/usr/bin/env python3
"""
Legacy clipping_api.py - Preserved for backward compatibility
This file now redirects to the new modular main.py
"""

import warnings
warnings.warn(
    "clipping_api.py is deprecated. Please use main.py instead.",
    DeprecationWarning,
    stacklevel=2
)

# Import everything from main to maintain compatibility
from main import *

if __name__ == "__main__":
    import uvicorn
    import os
    
    # Get configuration from environment or use defaults
    host = os.getenv("API_HOST", "0.0.0.0")
    port = int(os.getenv("API_PORT", "8000"))
    workers = int(os.getenv("API_WORKERS", "4"))
    
    print("=" * 60)
    print("WARNING: clipping_api.py is deprecated!")
    print("Please use 'python main.py' or 'uvicorn main:app' instead")
    print("=" * 60)
    
    # Run the application
    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        workers=workers,
        reload=os.getenv("API_RELOAD", "false").lower() == "true"
    )