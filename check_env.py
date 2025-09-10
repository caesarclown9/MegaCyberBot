#!/usr/bin/env python3
"""Quick environment check script."""
import os
import sys

print("=== Environment Variables Check ===")
print(f"Python: {sys.version}")

# Check DATABASE_URL
db_url = os.environ.get("DATABASE_URL", "NOT SET")
print(f"\nDATABASE_URL raw value:")
print(f"  Length: {len(db_url)}")
print(f"  First 50 chars: {repr(db_url[:50])}")
print(f"  Last 50 chars: {repr(db_url[-50:])}")

# Check for common issues
if "DATABASE_URL=" in db_url:
    print("  ⚠️ WARNING: Contains 'DATABASE_URL=' prefix")
if db_url.count(" ") > 0:
    print(f"  ⚠️ WARNING: Contains {db_url.count(' ')} spaces")
if db_url.startswith(" ") or db_url.endswith(" "):
    print("  ⚠️ WARNING: Has leading or trailing spaces")

# Check other important vars
print("\nOther environment variables:")
for var in ["TELEGRAM_BOT_TOKEN", "TELEGRAM_GROUP_ID", "FORCE_IPV4", "ENVIRONMENT"]:
    value = os.environ.get(var)
    if value:
        if var == "TELEGRAM_BOT_TOKEN":
            print(f"  {var}: ***{value[-10:]}")
        else:
            print(f"  {var}: {value}")
    else:
        print(f"  {var}: NOT SET")

print("\n=== Testing URL Cleanup ===")
# Test the cleanup logic
test_url = db_url
if test_url.startswith("DATABASE_URL="):
    test_url = test_url.replace("DATABASE_URL=", "", 1)
test_url = test_url.strip()

import re
test_url = re.sub(r'\s+', '', test_url)

print(f"Cleaned URL first 50 chars: {test_url[:50]}")
print(f"Cleaned URL starts with 'postgresql': {test_url.startswith('postgresql')}")

print("\n=== Quick Import Test ===")
try:
    from src.config import settings
    print("✓ Settings imported successfully")
    print(f"  Database URL configured: {bool(settings.database_url)}")
except Exception as e:
    print(f"✗ Failed to import settings: {e}")