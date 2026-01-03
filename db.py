"""
Database module for ChatList application.
Provides database initialization, schema creation, and CRUD operations.
"""

import sqlite3
import logging
from contextlib import contextmanager
from datetime import datetime
from typing import Optional, List, Dict, Any
import os


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Database file path
DB_FILE = "chatlist.db"


@contextmanager
def get_db_connection():
    """
    Context manager for database connections.
    
    Yields:
        sqlite3.Connection: Database connection object
    """
    conn = None
    try:
        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row
        # Enable foreign key constraints
        conn.execute("PRAGMA foreign_keys = ON")
        yield conn
        conn.commit()
    except sqlite3.Error as e:
        if conn:
            conn.rollback()
        logger.error(f"Database error: {e}")
        raise
    finally:
        if conn:
            conn.close()


def init_database():
    """
    Initialize database and create schema.
    Creates all required tables if they don't exist.
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Create prompts table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS prompts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT NOT NULL,
                    prompt TEXT NOT NULL,
                    tags TEXT
                )
            """)
            
            # Create index on date for sorting
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_prompts_date 
                ON prompts(date)
            """)
            
            # Create index on tags for filtering
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_prompts_tags 
                ON prompts(tags)
            """)
            
            # Create models table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS models (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    model_id TEXT NOT NULL,
                    api_url TEXT NOT NULL,
                    api_id TEXT NOT NULL,
                    is_active INTEGER NOT NULL DEFAULT 1
                )
            """)
            
            # Migrate existing tables: add model_id column if it doesn't exist
            try:
                # Check if column exists
                cursor.execute("PRAGMA table_info(models)")
                columns = [row[1] for row in cursor.fetchall()]
                
                if "model_id" not in columns:
                    cursor.execute("ALTER TABLE models ADD COLUMN model_id TEXT")
                    # Set model_id = name for existing records
                    cursor.execute("UPDATE models SET model_id = name WHERE model_id IS NULL OR model_id = ''")
                    logger.info("Added model_id column to existing models table")
            except sqlite3.OperationalError as e:
                # Column already exists or other error, skip migration
                logger.debug(f"Migration skipped: {e}")
                pass
            
            # Create index on is_active for filtering active models
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_models_is_active 
                ON models(is_active)
            """)
            
            # Create results table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    prompt_id INTEGER NOT NULL,
                    model_id INTEGER NOT NULL,
                    response_text TEXT NOT NULL,
                    saved_date TEXT NOT NULL,
                    metadata TEXT,
                    FOREIGN KEY (prompt_id) REFERENCES prompts(id),
                    FOREIGN KEY (model_id) REFERENCES models(id)
                )
            """)
            
            # Create indexes on results table
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_results_prompt_id 
                ON results(prompt_id)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_results_model_id 
                ON results(model_id)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_results_saved_date 
                ON results(saved_date)
            """)
            
            # Create settings table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            
            # Initialize default settings
            init_default_settings(cursor)
            
            conn.commit()
            logger.info("Database initialized successfully")
            
    except sqlite3.Error as e:
        logger.error(f"Error initializing database: {e}")
        raise


def init_default_settings(cursor: sqlite3.Cursor):
    """
    Initialize default settings in the settings table.
    
    Args:
        cursor [in]: Database cursor object
    """
    default_settings = [
        ("default_timeout", "30"),
        ("max_retries", "3"),
        ("export_format", "markdown"),
        ("theme", "light"),
        ("default_improvement_model_id", ""),
        ("improvement_num_variants", "3"),
        ("default_adaptation_type", "general")
    ]
    
    current_time = datetime.now().isoformat()
    
    for key, value in default_settings:
        # Check if setting already exists
        cursor.execute("SELECT key FROM settings WHERE key = ?", (key,))
        if not cursor.fetchone():
            cursor.execute("""
                INSERT INTO settings (key, value, updated_at)
                VALUES (?, ?, ?)
            """, (key, value, current_time))


# CRUD operations for prompts table

def create_prompt(prompt_text: str, tags: Optional[str] = None) -> int:
    """
    Create a new prompt in the database.
    
    Args:
        prompt_text [in]: The prompt text
        tags [in]: Optional tags (comma-separated)
    
    Returns:
        int: ID of the created prompt
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            current_time = datetime.now().isoformat()
            
            cursor.execute("""
                INSERT INTO prompts (date, prompt, tags)
                VALUES (?, ?, ?)
            """, (current_time, prompt_text, tags))
            
            prompt_id = cursor.lastrowid
            logger.info(f"Created prompt with ID: {prompt_id}")
            return prompt_id
            
    except sqlite3.Error as e:
        logger.error(f"Error creating prompt: {e}")
        raise


def get_prompt(prompt_id: int) -> Optional[Dict[str, Any]]:
    """
    Get a prompt by ID.
    
    Args:
        prompt_id [in]: ID of the prompt
    
    Returns:
        Optional[Dict[str, Any]]: Prompt data or None if not found
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, date, prompt, tags
                FROM prompts
                WHERE id = ?
            """, (prompt_id,))
            
            row = cursor.fetchone()
            if row:
                return {
                    "id": row["id"],
                    "date": row["date"],
                    "prompt": row["prompt"],
                    "tags": row["tags"]
                }
            return None
            
    except sqlite3.Error as e:
        logger.error(f"Error getting prompt: {e}")
        raise


def get_all_prompts(sort_by: str = "date", order: str = "DESC") -> List[Dict[str, Any]]:
    """
    Get all prompts from the database.
    
    Args:
        sort_by [in]: Field to sort by (default: "date")
        order [in]: Sort order "ASC" or "DESC" (default: "DESC")
    
    Returns:
        List[Dict[str, Any]]: List of prompts
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Validate sort_by field
            valid_fields = ["id", "date", "prompt", "tags"]
            if sort_by not in valid_fields:
                sort_by = "date"
            
            # Validate order
            if order not in ["ASC", "DESC"]:
                order = "DESC"
            
            cursor.execute(f"""
                SELECT id, date, prompt, tags
                FROM prompts
                ORDER BY {sort_by} {order}
            """)
            
            rows = cursor.fetchall()
            return [
                {
                    "id": row["id"],
                    "date": row["date"],
                    "prompt": row["prompt"],
                    "tags": row["tags"]
                }
                for row in rows
            ]
            
    except sqlite3.Error as e:
        logger.error(f"Error getting prompts: {e}")
        raise


def update_prompt(prompt_id: int, prompt_text: Optional[str] = None, 
                  tags: Optional[str] = None) -> bool:
    """
    Update a prompt.
    
    Args:
        prompt_id [in]: ID of the prompt to update
        prompt_text [in]: New prompt text (optional)
        tags [in]: New tags (optional)
    
    Returns:
        bool: True if updated successfully, False otherwise
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Build update query dynamically
            updates = []
            params = []
            
            if prompt_text is not None:
                updates.append("prompt = ?")
                params.append(prompt_text)
            
            if tags is not None:
                updates.append("tags = ?")
                params.append(tags)
            
            if not updates:
                return False
            
            params.append(prompt_id)
            
            cursor.execute(f"""
                UPDATE prompts
                SET {', '.join(updates)}
                WHERE id = ?
            """, params)
            
            success = cursor.rowcount > 0
            if success:
                logger.info(f"Updated prompt with ID: {prompt_id}")
            return success
            
    except sqlite3.Error as e:
        logger.error(f"Error updating prompt: {e}")
        raise


def delete_prompt(prompt_id: int) -> bool:
    """
    Delete a prompt by ID.
    Also deletes all related results due to foreign key constraints.
    
    Args:
        prompt_id [in]: ID of the prompt to delete
    
    Returns:
        bool: True if deleted successfully, False otherwise
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Delete all related results first (due to foreign key constraint)
            cursor.execute("DELETE FROM results WHERE prompt_id = ?", (prompt_id,))
            results_deleted = cursor.rowcount
            if results_deleted > 0:
                logger.info(f"Deleted {results_deleted} related result(s) for prompt {prompt_id}")
            
            # Delete the prompt
            cursor.execute("DELETE FROM prompts WHERE id = ?", (prompt_id,))
            
            success = cursor.rowcount > 0
            if success:
                logger.info(f"Deleted prompt with ID: {prompt_id}")
            return success
            
    except sqlite3.Error as e:
        logger.error(f"Error deleting prompt: {e}")
        raise


def delete_all_prompts() -> int:
    """
    Delete all prompts from database.
    Also deletes all related results due to foreign key constraints.
    
    Returns:
        int: Number of deleted prompts
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            # Get count before deletion
            cursor.execute("SELECT COUNT(*) FROM prompts")
            count = cursor.fetchone()[0]
            
            # Delete all related results first (due to foreign key constraint)
            cursor.execute("DELETE FROM results")
            results_deleted = cursor.rowcount
            if results_deleted > 0:
                logger.info(f"Deleted {results_deleted} related result(s)")
            
            # Delete all prompts
            cursor.execute("DELETE FROM prompts")
            
            deleted_count = cursor.rowcount
            logger.info(f"Deleted {deleted_count} prompt(s)")
            return deleted_count
            
    except sqlite3.Error as e:
        logger.error(f"Error deleting all prompts: {e}")
        raise


def search_prompts(query: str) -> List[Dict[str, Any]]:
    """
    Search prompts by text or tags.
    
    Args:
        query [in]: Search query string
    
    Returns:
        List[Dict[str, Any]]: List of matching prompts
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            search_pattern = f"%{query}%"
            
            cursor.execute("""
                SELECT id, date, prompt, tags
                FROM prompts
                WHERE prompt LIKE ? OR tags LIKE ?
                ORDER BY date DESC
            """, (search_pattern, search_pattern))
            
            rows = cursor.fetchall()
            return [
                {
                    "id": row["id"],
                    "date": row["date"],
                    "prompt": row["prompt"],
                    "tags": row["tags"]
                }
                for row in rows
            ]
            
    except sqlite3.Error as e:
        logger.error(f"Error searching prompts: {e}")
        raise


# CRUD operations for models table

def create_model(name: str, model_id: str, api_url: str, api_id: str, is_active: int = 1) -> int:
    """
    Create a new model in the database.
    
    Args:
        name [in]: Model display name
        model_id [in]: Model identifier for API requests
        api_url [in]: API endpoint URL
        api_id [in]: Environment variable name for API key
        is_active [in]: Active status (1 = active, 0 = inactive)
    
    Returns:
        int: ID of the created model
    
    Raises:
        ValueError: If model with this name already exists
        sqlite3.Error: For other database errors
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Check if model with this name already exists
            cursor.execute("SELECT id FROM models WHERE name = ?", (name,))
            existing = cursor.fetchone()
            if existing:
                error_msg = f"Модель с названием '{name}' уже существует"
                logger.error(error_msg)
                raise ValueError(error_msg)
            
            cursor.execute("""
                INSERT INTO models (name, model_id, api_url, api_id, is_active)
                VALUES (?, ?, ?, ?, ?)
            """, (name, model_id, api_url, api_id, is_active))
            
            model_id = cursor.lastrowid
            logger.info(f"Created model with ID: {model_id}")
            return model_id
            
    except ValueError:
        # Re-raise ValueError as-is
        raise
    except sqlite3.IntegrityError as e:
        # Handle UNIQUE constraint violation
        if "UNIQUE constraint failed: models.name" in str(e):
            error_msg = f"Модель с названием '{name}' уже существует"
            logger.error(error_msg)
            raise ValueError(error_msg)
        raise
    except sqlite3.Error as e:
        logger.error(f"Error creating model: {e}")
        raise


def get_model(model_id: int) -> Optional[Dict[str, Any]]:
    """
    Get a model by ID.
    
    Args:
        model_id [in]: ID of the model
    
    Returns:
        Optional[Dict[str, Any]]: Model data or None if not found
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, name, model_id, api_url, api_id, is_active
                FROM models
                WHERE id = ?
            """, (model_id,))
            
            row = cursor.fetchone()
            if row:
                return {
                    "id": row["id"],
                    "name": row["name"],
                    "model_id": row["model_id"],
                    "api_url": row["api_url"],
                    "api_id": row["api_id"],
                    "is_active": row["is_active"]
                }
            return None
            
    except sqlite3.Error as e:
        logger.error(f"Error getting model: {e}")
        raise


def get_all_models() -> List[Dict[str, Any]]:
    """
    Get all models from the database.
    
    Returns:
        List[Dict[str, Any]]: List of models
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, name, model_id, api_url, api_id, is_active
                FROM models
                ORDER BY name
            """)
            
            rows = cursor.fetchall()
            return [
                {
                    "id": row["id"],
                    "name": row["name"],
                    "model_id": row["model_id"],
                    "api_url": row["api_url"],
                    "api_id": row["api_id"],
                    "is_active": row["is_active"]
                }
                for row in rows
            ]
            
    except sqlite3.Error as e:
        logger.error(f"Error getting models: {e}")
        raise


def get_active_models() -> List[Dict[str, Any]]:
    """
    Get all active models from the database.
    
    Returns:
        List[Dict[str, Any]]: List of active models
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, name, model_id, api_url, api_id, is_active
                FROM models
                WHERE is_active = 1
                ORDER BY name
            """)
            
            rows = cursor.fetchall()
            return [
                {
                    "id": row["id"],
                    "name": row["name"],
                    "model_id": row["model_id"],
                    "api_url": row["api_url"],
                    "api_id": row["api_id"],
                    "is_active": row["is_active"]
                }
                for row in rows
            ]
            
    except sqlite3.Error as e:
        logger.error(f"Error getting active models: {e}")
        raise


def update_model(model_id: int, name: Optional[str] = None,
                 model_id_value: Optional[str] = None,
                 api_url: Optional[str] = None, api_id: Optional[str] = None,
                 is_active: Optional[int] = None) -> bool:
    """
    Update a model.
    
    Args:
        model_id [in]: ID of the model to update
        name [in]: New model name (optional)
        model_id_value [in]: New model identifier (optional)
        api_url [in]: New API URL (optional)
        api_id [in]: New API ID (optional)
        is_active [in]: New active status (optional)
    
    Returns:
        bool: True if updated successfully, False otherwise
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Build update query dynamically
            updates = []
            params = []
            
            if name is not None:
                updates.append("name = ?")
                params.append(name)
            
            if model_id_value is not None:
                updates.append("model_id = ?")
                params.append(model_id_value)
            
            if api_url is not None:
                updates.append("api_url = ?")
                params.append(api_url)
            
            if api_id is not None:
                updates.append("api_id = ?")
                params.append(api_id)
            
            if is_active is not None:
                updates.append("is_active = ?")
                params.append(is_active)
            
            if not updates:
                return False
            
            params.append(model_id)
            
            cursor.execute(f"""
                UPDATE models
                SET {', '.join(updates)}
                WHERE id = ?
            """, params)
            
            success = cursor.rowcount > 0
            if success:
                logger.info(f"Updated model with ID: {model_id}")
            return success
            
    except sqlite3.Error as e:
        logger.error(f"Error updating model: {e}")
        raise


def delete_model(model_id: int) -> bool:
    """
    Delete a model by ID.
    
    Args:
        model_id [in]: ID of the model to delete
    
    Returns:
        bool: True if deleted successfully, False otherwise
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM models WHERE id = ?", (model_id,))
            
            success = cursor.rowcount > 0
            if success:
                logger.info(f"Deleted model with ID: {model_id}")
            return success
            
    except sqlite3.Error as e:
        logger.error(f"Error deleting model: {e}")
        raise


# CRUD operations for results table

def create_result(prompt_id: int, model_id: int, response_text: str,
                  metadata: Optional[str] = None) -> int:
    """
    Create a new result in the database.
    
    Args:
        prompt_id [in]: ID of the prompt
        model_id [in]: ID of the model
        response_text [in]: Response text from the model
        metadata [in]: Optional JSON metadata
    
    Returns:
        int: ID of the created result
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            current_time = datetime.now().isoformat()
            
            cursor.execute("""
                INSERT INTO results (prompt_id, model_id, response_text, saved_date, metadata)
                VALUES (?, ?, ?, ?, ?)
            """, (prompt_id, model_id, response_text, current_time, metadata))
            
            result_id = cursor.lastrowid
            logger.info(f"Created result with ID: {result_id}")
            return result_id
            
    except sqlite3.Error as e:
        logger.error(f"Error creating result: {e}")
        raise


def get_result(result_id: int) -> Optional[Dict[str, Any]]:
    """
    Get a result by ID.
    
    Args:
        result_id [in]: ID of the result
    
    Returns:
        Optional[Dict[str, Any]]: Result data or None if not found
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, prompt_id, model_id, response_text, saved_date, metadata
                FROM results
                WHERE id = ?
            """, (result_id,))
            
            row = cursor.fetchone()
            if row:
                return {
                    "id": row["id"],
                    "prompt_id": row["prompt_id"],
                    "model_id": row["model_id"],
                    "response_text": row["response_text"],
                    "saved_date": row["saved_date"],
                    "metadata": row["metadata"]
                }
            return None
            
    except sqlite3.Error as e:
        logger.error(f"Error getting result: {e}")
        raise


def get_results_by_prompt(prompt_id: int, sort_by: str = "saved_date", order: str = "DESC") -> List[Dict[str, Any]]:
    """
    Get all results for a specific prompt.
    
    Args:
        prompt_id [in]: ID of the prompt
        sort_by [in]: Field to sort by (default: "saved_date")
        order [in]: Sort order "ASC" or "DESC" (default: "DESC")
    
    Returns:
        List[Dict[str, Any]]: List of results for the prompt
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Validate sort_by field
            valid_fields = ["id", "prompt_id", "model_id", "saved_date"]
            if sort_by not in valid_fields:
                sort_by = "saved_date"
            
            # Validate order
            if order.upper() not in ["ASC", "DESC"]:
                order = "DESC"
            
            cursor.execute(f"""
                SELECT id, prompt_id, model_id, response_text, saved_date, metadata
                FROM results
                WHERE prompt_id = ?
                ORDER BY {sort_by} {order}
            """, (prompt_id,))
            
            rows = cursor.fetchall()
            return [
                {
                    "id": row["id"],
                    "prompt_id": row["prompt_id"],
                    "model_id": row["model_id"],
                    "response_text": row["response_text"],
                    "saved_date": row["saved_date"],
                    "metadata": row["metadata"]
                }
                for row in rows
            ]
            
    except sqlite3.Error as e:
        logger.error(f"Error getting results by prompt: {e}")
        raise


def get_all_results(sort_by: str = "saved_date", order: str = "DESC") -> List[Dict[str, Any]]:
    """
    Get all results from the database.
    
    Args:
        sort_by [in]: Field to sort by (default: "saved_date")
        order [in]: Sort order "ASC" or "DESC" (default: "DESC")
    
    Returns:
        List[Dict[str, Any]]: List of results
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Validate sort_by field
            valid_fields = ["id", "prompt_id", "model_id", "saved_date"]
            if sort_by not in valid_fields:
                sort_by = "saved_date"
            
            # Validate order
            if order not in ["ASC", "DESC"]:
                order = "DESC"
            
            cursor.execute(f"""
                SELECT id, prompt_id, model_id, response_text, saved_date, metadata
                FROM results
                ORDER BY {sort_by} {order}
            """)
            
            rows = cursor.fetchall()
            return [
                {
                    "id": row["id"],
                    "prompt_id": row["prompt_id"],
                    "model_id": row["model_id"],
                    "response_text": row["response_text"],
                    "saved_date": row["saved_date"],
                    "metadata": row["metadata"]
                }
                for row in rows
            ]
            
    except sqlite3.Error as e:
        logger.error(f"Error getting results: {e}")
        raise


def delete_result(result_id: int) -> bool:
    """
    Delete a result by ID.
    
    Args:
        result_id [in]: ID of the result to delete
    
    Returns:
        bool: True if deleted successfully, False otherwise
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM results WHERE id = ?", (result_id,))
            
            success = cursor.rowcount > 0
            if success:
                logger.info(f"Deleted result with ID: {result_id}")
            return success
            
    except sqlite3.Error as e:
        logger.error(f"Error deleting result: {e}")
        raise


def search_results(query: str) -> List[Dict[str, Any]]:
    """
    Search results by response text.
    
    Args:
        query [in]: Search query string
    
    Returns:
        List[Dict[str, Any]]: List of matching results
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            search_pattern = f"%{query}%"
            
            cursor.execute("""
                SELECT id, prompt_id, model_id, response_text, saved_date, metadata
                FROM results
                WHERE response_text LIKE ?
                ORDER BY saved_date DESC
            """, (search_pattern,))
            
            rows = cursor.fetchall()
            return [
                {
                    "id": row["id"],
                    "prompt_id": row["prompt_id"],
                    "model_id": row["model_id"],
                    "response_text": row["response_text"],
                    "saved_date": row["saved_date"],
                    "metadata": row["metadata"]
                }
                for row in rows
            ]
            
    except sqlite3.Error as e:
        logger.error(f"Error searching results: {e}")
        raise


# CRUD operations for settings table

def get_setting(key: str) -> Optional[str]:
    """
    Get a setting value by key.
    
    Args:
        key [in]: Setting key
    
    Returns:
        Optional[str]: Setting value or None if not found
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
            
            row = cursor.fetchone()
            return row["value"] if row else None
            
    except sqlite3.Error as e:
        logger.error(f"Error getting setting: {e}")
        raise


def set_setting(key: str, value: str) -> bool:
    """
    Set a setting value.
    
    Args:
        key [in]: Setting key
        value [in]: Setting value
    
    Returns:
        bool: True if set successfully, False otherwise
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            current_time = datetime.now().isoformat()
            
            # Check if setting exists
            cursor.execute("SELECT key FROM settings WHERE key = ?", (key,))
            if cursor.fetchone():
                # Update existing setting
                cursor.execute("""
                    UPDATE settings
                    SET value = ?, updated_at = ?
                    WHERE key = ?
                """, (value, current_time, key))
            else:
                # Insert new setting
                cursor.execute("""
                    INSERT INTO settings (key, value, updated_at)
                    VALUES (?, ?, ?)
                """, (key, value, current_time))
            
            logger.info(f"Set setting {key} = {value}")
            return True
            
    except sqlite3.Error as e:
        logger.error(f"Error setting setting: {e}")
        raise


def get_all_settings() -> Dict[str, str]:
    """
    Get all settings from the database.
    
    Returns:
        Dict[str, str]: Dictionary of all settings
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT key, value FROM settings")
            
            rows = cursor.fetchall()
            return {row["key"]: row["value"] for row in rows}
            
    except sqlite3.Error as e:
        logger.error(f"Error getting all settings: {e}")
        raise

