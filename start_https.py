#!/usr/bin/env python3
"""
HTTPS server startup script for testing SSL configuration
"""
import os
import uvicorn
from clipping_api import app

if __name__ == "__main__":
    # SSL configuration
    ssl_keyfile = "ssl/key.pem"
    ssl_certfile = "ssl/cert.pem"
    
    if not os.path.exists(ssl_keyfile) or not os.path.exists(ssl_certfile):
        print(f"Error: SSL files not found: {ssl_keyfile}, {ssl_certfile}")
        exit(1)
    
    print("Starting HTTPS server on port 8443...")
    print("Access at: https://localhost:8443")
    print("Note: You'll get a security warning due to self-signed certificate")
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8443,
        ssl_keyfile=ssl_keyfile,
        ssl_certfile=ssl_certfile,
        log_level="info"
    )