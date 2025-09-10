#!/usr/bin/env python3
"""
Validate Supabase connection and credentials.
Run this script to verify your DATABASE_URL is correct.
"""
import os
import sys
import re
import asyncio
from urllib.parse import urlparse
import asyncpg

def validate_url_format(url: str) -> tuple[bool, str, str]:
    """Validate and clean DATABASE_URL."""
    
    # Clean the URL
    if url.startswith("DATABASE_URL="):
        url = url.replace("DATABASE_URL=", "", 1)
    url = url.strip()
    url = re.sub(r'\s+', '', url)
    
    # Convert to asyncpg format if needed
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    
    # Parse and validate
    try:
        parsed = urlparse(url)
        
        errors = []
        warnings = []
        
        # Check scheme
        if not url.startswith("postgresql+asyncpg://"):
            errors.append(f"URL should start with 'postgresql+asyncpg://', not '{parsed.scheme}://'")
        
        # Check username
        if not parsed.username:
            errors.append("Username is missing")
        elif not parsed.username.startswith("postgres."):
            warnings.append(f"Username '{parsed.username}' doesn't start with 'postgres.' - is this correct?")
        
        # Check password
        if not parsed.password:
            errors.append("Password is missing!")
        
        # Check hostname
        if not parsed.hostname:
            errors.append("Hostname is missing")
        elif "pooler.supabase.com" not in parsed.hostname:
            warnings.append("Not using pooler.supabase.com endpoint - this may cause issues")
        
        # Check port
        if parsed.port != 6543:
            warnings.append(f"Port {parsed.port} is not the pooler port 6543")
        
        # Check database
        if not parsed.path or parsed.path == "/":
            errors.append("Database name is missing")
        
        if errors:
            return False, "\n".join(errors), url
        
        if warnings:
            print("⚠️ Warnings:")
            for w in warnings:
                print(f"   - {w}")
        
        return True, "URL format is valid", url
        
    except Exception as e:
        return False, f"Failed to parse URL: {e}", url


async def test_connection(url: str):
    """Test actual connection to Supabase."""
    
    parsed = urlparse(url)
    
    print("\n📡 Testing connection to Supabase...")
    print(f"   Host: {parsed.hostname}")
    print(f"   Port: {parsed.port}")
    print(f"   User: {parsed.username}")
    print(f"   Database: {parsed.path.lstrip('/')}")
    
    try:
        # Try to connect
        conn = await asyncpg.connect(
            host=parsed.hostname,
            port=parsed.port or 5432,
            user=parsed.username,
            password=parsed.password,
            database=parsed.path.lstrip('/'),
            timeout=10,
            ssl='require',  # Supabase requires SSL
        )
        
        print("\n✅ Connection successful!")
        
        # Test a query
        version = await conn.fetchval("SELECT version()")
        print(f"   PostgreSQL: {version[:60]}...")
        
        # Check if we can access tables
        tables = await conn.fetch("""
            SELECT tablename FROM pg_tables 
            WHERE schemaname = 'public' 
            LIMIT 5
        """)
        
        if tables:
            print(f"   Found {len(tables)} tables in public schema")
        else:
            print("   No tables found (database might be empty)")
        
        await conn.close()
        return True
        
    except asyncpg.exceptions.InvalidPasswordError:
        print("\n❌ Authentication failed: Invalid password")
        print("   Check your password in Supabase dashboard")
        return False
        
    except asyncpg.exceptions.InternalServerError as e:
        error_msg = str(e)
        if "Tenant or user not found" in error_msg:
            print("\n❌ Authentication failed: Tenant or user not found")
            print("\n   This usually means:")
            print("   1. The username format is wrong (should be postgres.[project-ref])")
            print("   2. The password is incorrect")
            print("   3. You're using the wrong endpoint")
            print("\n   Get the correct connection string from:")
            print("   Supabase Dashboard → Settings → Database → Connection Pooling")
        else:
            print(f"\n❌ Server error: {error_msg}")
        return False
        
    except Exception as e:
        print(f"\n❌ Connection failed: {type(e).__name__}: {e}")
        return False


async def main():
    """Main validation function."""
    
    print("🔍 Supabase Connection Validator")
    print("=" * 50)
    
    # Get DATABASE_URL
    database_url = os.environ.get("DATABASE_URL", "")
    
    if not database_url:
        print("\n❌ DATABASE_URL environment variable is not set!")
        print("\nTo test, set it like this:")
        print("export DATABASE_URL='postgresql+asyncpg://postgres.[PROJECT]:[PASSWORD]@aws-0-[REGION].pooler.supabase.com:6543/postgres'")
        sys.exit(1)
    
    print(f"\n📋 Checking DATABASE_URL (length: {len(database_url)})")
    
    # Validate format
    valid, message, cleaned_url = validate_url_format(database_url)
    
    if not valid:
        print(f"\n❌ URL validation failed:")
        print(f"   {message}")
        sys.exit(1)
    
    print(f"✅ {message}")
    
    # Test connection
    success = await test_connection(cleaned_url)
    
    if success:
        print("\n🎉 Everything looks good! Your DATABASE_URL is correctly configured.")
    else:
        print("\n💡 Tips:")
        print("1. Copy the connection string from Supabase Dashboard → Settings → Database → Connection Pooling")
        print("2. Make sure to use the pooler endpoint (port 6543)")
        print("3. Replace 'postgresql://' with 'postgresql+asyncpg://' in the URL")
        print("4. Check that the password doesn't contain unescaped special characters")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())