"""
Automatic database migrations
Runs on bot startup to ensure database schema is up to date
"""

from sqlalchemy import text
from src.utils import LoggerMixin


class DatabaseMigrator(LoggerMixin):
    """Handles automatic database migrations on startup."""
    
    async def run_migrations(self, session):
        """Run all necessary migrations."""
        try:
            # Migration 1: Add category column
            await self._add_category_column(session)
            
            self.log_info("All database migrations completed successfully")
            
        except Exception as e:
            self.log_error(f"Migration error (non-critical): {str(e)}")
            # Don't fail startup if migration fails - it might already be applied
    
    async def _add_category_column(self, session):
        """Add category column to articles table if it doesn't exist."""
        try:
            # Check if column exists
            check_query = text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'articles' 
                AND column_name = 'category'
            """)
            
            result = await session.execute(check_query)
            existing_column = result.fetchone()
            
            if existing_column:
                self.log_debug("Column 'category' already exists in articles table")
                return
            
            # Add category column
            self.log_info("Adding category column to articles table...")
            
            # Add column with default value
            alter_query = text("""
                ALTER TABLE articles 
                ADD COLUMN category VARCHAR(50) DEFAULT 'general'
            """)
            await session.execute(alter_query)
            
            # Create index for better performance
            index_query = text("""
                CREATE INDEX IF NOT EXISTS idx_category_sent 
                ON articles(category, is_sent)
            """)
            await session.execute(index_query)
            
            # Update existing articles
            update_query = text("""
                UPDATE articles 
                SET category = 'general' 
                WHERE category IS NULL
            """)
            await session.execute(update_query)
            
            await session.commit()
            
            self.log_info("Successfully added category column to articles table")
            
        except Exception as e:
            # If column already exists or any other error, just log and continue
            if "already exists" in str(e).lower() or "duplicate column" in str(e).lower():
                self.log_debug("Category column already exists (migration previously applied)")
            else:
                self.log_warning(f"Could not add category column: {str(e)}")
            # Don't raise - allow bot to continue