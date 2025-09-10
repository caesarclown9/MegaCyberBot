#!/usr/bin/env python3
"""Debug script to test database connection and bot startup."""

import asyncio
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


async def test_database_connection():
    """Test database connection."""
    print("\n=== Testing Database Connection ===")
    
    try:
        from src.config import settings
        from src.database import db_manager
        
        print(f"Database URL configured: {bool(settings.database_url)}")
        
        # Hide password in URL for logging
        db_url_parts = settings.database_url.split('@')
        if len(db_url_parts) > 1:
            db_info = db_url_parts[0].split('://')[-1].split(':')[0] + '@' + db_url_parts[-1]
            print(f"Connecting to: {db_info}")
        
        # Try to initialize database
        await db_manager.init()
        print("✓ Database connection successful!")
        
        # Try to get a session
        async with db_manager.get_session() as session:
            # Simple query to test connection
            from sqlalchemy import text
            result = await session.execute(text("SELECT 1"))
            print("✓ Database query successful!")
        
        await db_manager.close()
        return True
        
    except Exception as e:
        print(f"✗ Database connection failed: {e}")
        return False


async def test_telegram_connection():
    """Test Telegram bot token."""
    print("\n=== Testing Telegram Connection ===")
    
    try:
        from src.config import settings
        from aiogram import Bot
        
        if not settings.telegram_bot_token:
            print("✗ No Telegram bot token configured!")
            return False
        
        print(f"Bot token configured: {settings.telegram_bot_token[:10]}...")
        
        bot = Bot(token=settings.telegram_bot_token)
        bot_info = await bot.get_me()
        print(f"✓ Bot connected: @{bot_info.username}")
        
        await bot.session.close()
        return True
        
    except Exception as e:
        print(f"✗ Telegram connection failed: {e}")
        return False


async def test_environment_variables():
    """Check all required environment variables."""
    print("\n=== Checking Environment Variables ===")
    
    required_vars = [
        "TELEGRAM_BOT_TOKEN",
        "TELEGRAM_GROUP_ID",
        "TELEGRAM_VULNERABILITIES_GROUP_ID",
        "DATABASE_URL"
    ]
    
    optional_vars = [
        "TELEGRAM_TOPIC_ID",
        "TELEGRAM_VULNERABILITIES_TOPIC_ID",
        "MICROSOFT_TRANSLATOR_KEY",
        "OPENAI_API_KEY",
        "PROXY_URL",
        "SENTRY_DSN",
        "PARSE_API_KEY"
    ]
    
    all_ok = True
    
    print("Required variables:")
    for var in required_vars:
        value = os.getenv(var)
        if value:
            print(f"  ✓ {var}: configured")
        else:
            print(f"  ✗ {var}: MISSING!")
            all_ok = False
    
    print("\nOptional variables:")
    for var in optional_vars:
        value = os.getenv(var)
        if value:
            print(f"  ✓ {var}: configured")
        else:
            print(f"  - {var}: not set")
    
    return all_ok


async def main():
    """Run all tests."""
    print("=== MegaCyberBot Startup Diagnostics ===")
    print(f"Python: {os.sys.version}")
    print(f"Working directory: {os.getcwd()}")
    
    # Test environment variables
    env_ok = await test_environment_variables()
    
    # Test database
    db_ok = await test_database_connection()
    
    # Test Telegram
    tg_ok = await test_telegram_connection()
    
    print("\n=== Summary ===")
    print(f"Environment variables: {'✓' if env_ok else '✗'}")
    print(f"Database connection: {'✓' if db_ok else '✗'}")
    print(f"Telegram connection: {'✓' if tg_ok else '✗'}")
    
    if env_ok and db_ok and tg_ok:
        print("\n✓ All checks passed! Bot should start successfully.")
        return 0
    else:
        print("\n✗ Some checks failed. Please fix the issues above.")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)