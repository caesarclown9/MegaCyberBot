#!/usr/bin/env python3
"""
Startup wrapper to force IPv4 connections before any imports.
This must run before any network libraries are imported.
"""
import os
import socket
import sys

# Debug DATABASE_URL before any processing
db_url = os.getenv("DATABASE_URL", "")
if db_url:
    # Check for password presence without revealing it
    import re
    from urllib.parse import urlparse
    
    # Clean URL for parsing
    clean_url = db_url
    if clean_url.startswith("DATABASE_URL="):
        clean_url = clean_url.replace("DATABASE_URL=", "", 1)
    clean_url = clean_url.strip()
    clean_url = re.sub(r'\s+', '', clean_url)
    
    try:
        parsed = urlparse(clean_url)
        if parsed.password:
            print(f"[INIT] DATABASE_URL validated: user={parsed.username}, password=*****, host={parsed.hostname}, port={parsed.port}", flush=True)
        else:
            print(f"[INIT] WARNING: DATABASE_URL missing password! user={parsed.username}, host={parsed.hostname}", flush=True)
    except Exception as e:
        print(f"[INIT] WARNING: Could not parse DATABASE_URL: {e}", flush=True)

# Force IPv4 for all connections if FORCE_IPV4 is set
if os.getenv("FORCE_IPV4", "").lower() in ["true", "1", "yes"]:
    print("[INIT] Forcing IPv4 connections for all network operations", flush=True)
    
    # Save original getaddrinfo
    original_getaddrinfo = socket.getaddrinfo
    
    def getaddrinfo_ipv4_only(host, port, family=0, type=0, proto=0, flags=0):
        """Force IPv4 only resolution"""
        # Always use IPv4
        return original_getaddrinfo(host, port, socket.AF_INET, type, proto, flags)
    
    # Replace the function globally
    socket.getaddrinfo = getaddrinfo_ipv4_only
    print("[INIT] IPv4 enforcement enabled", flush=True)

# Now import and run the main application
import main
import asyncio

if __name__ == "__main__":
    asyncio.run(main.main())