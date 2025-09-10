#!/usr/bin/env python3
"""
Startup wrapper to force IPv4 connections before any imports.
This must run before any network libraries are imported.
"""
import os
import socket
import sys

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