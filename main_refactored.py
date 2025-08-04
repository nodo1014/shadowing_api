#!/usr/bin/env python3
"""
Refactored main entry point for Video Clipping API
"""
import uvicorn
from shadowing_maker.api.app import app

if __name__ == "__main__":
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8080,
        log_level="info",
        access_log=True
    )