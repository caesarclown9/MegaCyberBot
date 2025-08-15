#!/usr/bin/env python3
"""
Migration script to add category column to articles table
Run this script to update your database schema for vulnerability categorization
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from src.database import db_manager
from src.config import settings


async def run_migration():
    """Add category column to articles table."""
    print("Starting migration: Adding category column to articles table...")
    
    try:
        # Initialize database connection
        await db_manager.init()
        
        async with db_manager.get_session() as session:
            # Check if column already exists
            check_query = text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'articles' 
                AND column_name = 'category'
            """)
            
            result = await session.execute(check_query)
            existing_column = result.fetchone()
            
            if existing_column:
                print("✓ Column 'category' already exists in articles table")
                return
            
            # Add category column
            print("Adding category column...")
            alter_query = text("""
                ALTER TABLE articles 
                ADD COLUMN category VARCHAR(50) DEFAULT 'general'
            """)
            await session.execute(alter_query)
            
            # Create index for better performance
            print("Creating index for category column...")
            index_query = text("""
                CREATE INDEX IF NOT EXISTS idx_category_sent 
                ON articles(category, is_sent)
            """)
            await session.execute(index_query)
            
            # Commit changes
            await session.commit()
            
            print("✓ Migration completed successfully!")
            print("  - Added column: category (VARCHAR(50), default='general')")
            print("  - Created index: idx_category_sent")
            
            # Update existing articles to have category
            print("\nUpdating existing articles...")
            update_query = text("""
                UPDATE articles 
                SET category = 'general' 
                WHERE category IS NULL
            """)
            result = await session.execute(update_query)
            await session.commit()
            
            print(f"✓ Updated {result.rowcount} existing articles with default category")
            
    except Exception as e:
        print(f"✗ Migration failed: {str(e)}")
        print("\nIf you're seeing 'column already exists' error, the migration may have been partially applied.")
        print("You can safely ignore this error if the bot is working correctly.")
        sys.exit(1)
    finally:
        await db_manager.close()


async def rollback_migration():
    """Rollback the migration (remove category column)."""
    print("Rolling back migration: Removing category column from articles table...")
    
    try:
        await db_manager.init()
        
        async with db_manager.get_session() as session:
            # Drop index first
            print("Dropping index...")
            drop_index_query = text("DROP INDEX IF EXISTS idx_category_sent")
            await session.execute(drop_index_query)
            
            # Drop column
            print("Dropping category column...")
            drop_column_query = text("ALTER TABLE articles DROP COLUMN IF EXISTS category")
            await session.execute(drop_column_query)
            
            await session.commit()
            
            print("✓ Rollback completed successfully!")
            
    except Exception as e:
        print(f"✗ Rollback failed: {str(e)}")
        sys.exit(1)
    finally:
        await db_manager.close()


def main():
    """Main entry point for the migration script."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Database migration for category column")
    parser.add_argument(
        "--rollback", 
        action="store_true", 
        help="Rollback the migration (remove category column)"
    )
    
    args = parser.parse_args()
    
    if args.rollback:
        asyncio.run(rollback_migration())
    else:
        asyncio.run(run_migration())


if __name__ == "__main__":
    main()