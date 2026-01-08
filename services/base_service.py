"""Base service class for sequential database query execution.

All services inherit from this class to ensure queries run sequentially
and from a single, reusable database session.
"""

import logging
from typing import Optional
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class BaseService:
    """Base service class for database operations.
    
    Key principles:
    - All queries run sequentially (no parallel execution)
    - Single database session per request
    - Clear separation between business logic and data access
    - Automatic rollback on errors to prevent transaction state issues
    """
    
    def __init__(self, db: Session):
        """Initialize service with database session.
        
        Args:
            db: SQLAlchemy database session (from get_db dependency)
        """
        self.db = db
        self._query_count = 0
    
    def _log_query(self, query_name: str, description: str = ""):
        """Log query execution for debugging sequential flow.
        
        Args:
            query_name: Name of the query being executed
            description: Optional description of what the query does
        """
        self._query_count += 1
        logger.info(
            f"[Query {self._query_count}] {query_name} "
            f"{'- ' + description if description else ''}"
        )
    
    def _handle_error(self, error: Exception, message: str = "Database operation failed"):
        """Handle database errors by rolling back transaction.
        
        PostgreSQL requires rollback after any error before new queries can execute.
        
        Args:
            error: The exception that occurred
            message: Optional error message
        """
        logger.error(f"{message}: {error}", exc_info=True)
        try:
            self.db.rollback()
            logger.debug(f"Rolled back transaction after error: {error}")
        except Exception as rollback_error:
            logger.error(f"Failed to rollback transaction: {rollback_error}")
        raise error  # Re-raise the exception after handling
    
    def get_query_count(self) -> int:
        """Get the total number of queries executed by this service.
        
        Returns:
            Number of queries executed
        """
        return self._query_count

