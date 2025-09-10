#!/usr/bin/env python3
"""Debug script to verify DATABASE_URL parsing."""
import os
import sys
import re
from urllib.parse import urlparse

def debug_database_url():
    """Debug DATABASE_URL parsing and show what's being sent to database."""
    
    # Get raw environment variable
    raw_url = os.environ.get("DATABASE_URL", "NOT SET")
    
    print("=== DATABASE_URL Debug ===")
    print(f"Raw environment variable length: {len(raw_url)}")
    
    # Check for common issues
    if raw_url == "NOT SET":
        print("❌ DATABASE_URL is not set!")
        return
    
    # Clean the URL (same logic as settings.py)
    cleaned_url = raw_url
    if cleaned_url.startswith("DATABASE_URL="):
        print("⚠️ Found 'DATABASE_URL=' prefix, removing...")
        cleaned_url = cleaned_url.replace("DATABASE_URL=", "", 1)
    
    cleaned_url = cleaned_url.strip()
    original_with_spaces = cleaned_url
    cleaned_url = re.sub(r'\s+', '', cleaned_url)
    
    if original_with_spaces != cleaned_url:
        print(f"⚠️ Removed {len(original_with_spaces) - len(cleaned_url)} spaces from URL")
    
    # Parse the URL
    try:
        parsed = urlparse(cleaned_url)
        print("\n=== Parsed URL Components ===")
        print(f"Scheme: {parsed.scheme}")
        print(f"Username: {parsed.username}")
        print(f"Password: {'*' * len(parsed.password) if parsed.password else 'MISSING!'}")
        print(f"Hostname: {parsed.hostname}")
        print(f"Port: {parsed.port}")
        print(f"Database: {parsed.path.lstrip('/')}")
        
        # Check Supabase pooler requirements
        print("\n=== Supabase Pooler Validation ===")
        if parsed.port == 6543:
            print("✓ Using pooler port 6543")
        else:
            print(f"⚠️ Not using pooler port (current: {parsed.port}, expected: 6543)")
        
        if parsed.hostname and "pooler.supabase.com" in parsed.hostname:
            print("✓ Using pooler endpoint")
        else:
            print("⚠️ Not using pooler endpoint")
        
        if parsed.username and "postgres." in parsed.username:
            print("✓ Username includes project reference")
        else:
            print("⚠️ Username might be incorrect for Supabase")
        
        if not parsed.password:
            print("❌ PASSWORD IS MISSING! This will cause authentication to fail.")
        else:
            print(f"✓ Password is present ({len(parsed.password)} characters)")
        
        # Test connection string reconstruction
        print("\n=== Reconstructed URL ===")
        if parsed.password:
            reconstructed = f"{parsed.scheme}://{parsed.username}:{'*' * len(parsed.password)}@{parsed.hostname}:{parsed.port}{parsed.path}"
        else:
            reconstructed = f"{parsed.scheme}://{parsed.username}@{parsed.hostname}:{parsed.port}{parsed.path}"
        print(f"URL that will be used: {reconstructed}")
        
    except Exception as e:
        print(f"❌ Failed to parse URL: {e}")
        print(f"URL starts with: {cleaned_url[:50]}...")
        print(f"URL ends with: ...{cleaned_url[-50:]}")

if __name__ == "__main__":
    debug_database_url()