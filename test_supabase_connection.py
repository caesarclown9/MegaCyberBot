#!/usr/bin/env python3
"""Test Supabase connection with detailed error reporting."""
import asyncio
import os
import sys
from urllib.parse import urlparse
import asyncpg

async def test_connection():
    """Test direct connection to Supabase."""
    
    # Get DATABASE_URL
    database_url = os.environ.get("DATABASE_URL", "")
    
    # Clean it up
    if database_url.startswith("DATABASE_URL="):
        database_url = database_url.replace("DATABASE_URL=", "", 1)
    database_url = database_url.strip()
    
    # Remove any spaces
    import re
    database_url = re.sub(r'\s+', '', database_url)
    
    # Convert to asyncpg format
    if database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    
    print(f"Testing connection to Supabase...")
    print(f"URL length: {len(database_url)}")
    
    # Parse URL for asyncpg
    parsed = urlparse(database_url)
    
    print(f"\nConnection details:")
    print(f"  Host: {parsed.hostname}")
    print(f"  Port: {parsed.port}")
    print(f"  User: {parsed.username}")
    print(f"  Pass: {'*' * len(parsed.password) if parsed.password else 'MISSING'}")
    print(f"  Database: {parsed.path.lstrip('/')}")
    
    # Try to connect with asyncpg directly
    try:
        print("\nAttempting connection...")
        conn = await asyncpg.connect(
            host=parsed.hostname,
            port=parsed.port or 5432,
            user=parsed.username,
            password=parsed.password,
            database=parsed.path.lstrip('/'),
            timeout=30,
            command_timeout=30,
        )
        
        print("✓ Connected successfully!")
        
        # Test query
        version = await conn.fetchval("SELECT version()")
        print(f"✓ PostgreSQL version: {version[:50]}...")
        
        await conn.close()
        print("✓ Connection closed")
        
    except asyncpg.exceptions.InvalidPasswordError as e:
        print(f"❌ Invalid password: {e}")
    except asyncpg.exceptions.InvalidCatalogNameError as e:
        print(f"❌ Invalid database name: {e}")
    except asyncpg.exceptions.InternalServerError as e:
        print(f"❌ Internal server error: {e}")
        if "Tenant or user not found" in str(e):
            print("\nThis error usually means:")
            print("1. The project reference in username is incorrect")
            print("2. The password is wrong")
            print("3. The pooler endpoint expects a different format")
            print("\nVerify your connection string matches Supabase dashboard:")
            print("  Dashboard → Settings → Database → Connection Pooling")
    except Exception as e:
        print(f"❌ Connection failed: {type(e).__name__}: {e}")

if __name__ == "__main__":
    asyncio.run(test_connection())