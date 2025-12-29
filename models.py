"""
Models module for ChatList application.
Provides model management and configuration.
"""

import logging
from typing import Optional, List, Dict, Any
import db


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Model:
    """
    Model class representing an AI model configuration.
    """
    
    def __init__(self, model_id: int, name: str, model_id_value: str, 
                 api_url: str, api_id: str, is_active: int = 1):
        """
        Initialize Model instance.
        
        Args:
            model_id [in]: Model ID from database
            name [in]: Model display name
            model_id_value [in]: Model identifier for API requests
            api_url [in]: API endpoint URL
            api_id [in]: Environment variable name for API key
            is_active [in]: Active status (1 = active, 0 = inactive)
        """
        self.id = model_id
        self.name = name
        self.model_id = model_id_value
        self.api_url = api_url
        self.api_id = api_id
        self.is_active = is_active
    
    def __repr__(self):
        """
        String representation of Model.
        
        Returns:
            str: String representation
        """
        return f"Model(id={self.id}, name='{self.name}', is_active={self.is_active})"
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert Model to dictionary.
        
        Returns:
            Dict[str, Any]: Model data as dictionary
        """
        return {
            "id": self.id,
            "name": self.name,
            "model_id": self.model_id,
            "api_url": self.api_url,
            "api_id": self.api_id,
            "is_active": self.is_active
        }


def get_active_models() -> List[Model]:
    """
    Get all active models from database.
    
    Returns:
        List[Model]: List of active Model instances
    """
    try:
        models_data = db.get_active_models()
        return [
            Model(
                model_id=model["id"],
                name=model["name"],
                model_id_value=model.get("model_id", model["name"]),  # Fallback to name for compatibility
                api_url=model["api_url"],
                api_id=model["api_id"],
                is_active=model["is_active"]
            )
            for model in models_data
        ]
    except Exception as e:
        logger.error(f"Error getting active models: {e}")
        return []


def load_model_config(model_id: int) -> Optional[Model]:
    """
    Load model configuration by ID.
    
    Args:
        model_id [in]: Model ID
    
    Returns:
        Optional[Model]: Model instance or None if not found
    """
    try:
        model_data = db.get_model(model_id)
        if model_data:
            return Model(
                model_id=model_data["id"],
                name=model_data["name"],
                model_id_value=model_data.get("model_id", model_data["name"]),  # Fallback to name for compatibility
                api_url=model_data["api_url"],
                api_id=model_data["api_id"],
                is_active=model_data["is_active"]
            )
        return None
    except Exception as e:
        logger.error(f"Error loading model config: {e}")
        return None


def validate_model_config(name: str, model_id: str, api_url: str, api_id: str) -> tuple[bool, Optional[str]]:
    """
    Validate model configuration.
    
    Args:
        name [in]: Model display name
        model_id [in]: Model identifier for API requests
        api_url [in]: API endpoint URL
        api_id [in]: Environment variable name for API key
    
    Returns:
        tuple[bool, Optional[str]]: (is_valid, error_message)
    """
    # Local variables
    error_msg = None
    
    # Validate name
    if not name or not name.strip():
        error_msg = "Название модели не может быть пустым"
        return (False, error_msg)
    
    # Validate model_id
    if not model_id or not model_id.strip():
        error_msg = "Идентификатор модели (model_id) не может быть пустым"
        return (False, error_msg)
    
    # Validate API URL
    if not api_url or not api_url.strip():
        error_msg = "API URL не может быть пустым"
        return (False, error_msg)
    
    # Check if URL starts with http:// or https://
    if not (api_url.startswith("http://") or api_url.startswith("https://")):
        error_msg = "API URL должен начинаться с http:// или https://"
        return (False, error_msg)
    
    # Validate API ID
    if not api_id or not api_id.strip():
        error_msg = "API ID (имя переменной окружения) не может быть пустым"
        return (False, error_msg)
    
    return (True, None)


def get_all_models() -> List[Model]:
    """
    Get all models from database.
    
    Returns:
        List[Model]: List of all Model instances
    """
    try:
        models_data = db.get_all_models()
        return [
            Model(
                model_id=model["id"],
                name=model["name"],
                model_id_value=model.get("model_id", model["name"]),  # Fallback to name for compatibility
                api_url=model["api_url"],
                api_id=model["api_id"],
                is_active=model["is_active"]
            )
            for model in models_data
        ]
    except Exception as e:
        logger.error(f"Error getting all models: {e}")
        return []


def create_model(name: str, model_id: str, api_url: str, api_id: str, is_active: int = 1) -> Optional[Model]:
    """
    Create a new model in database.
    
    Args:
        name [in]: Model display name
        model_id [in]: Model identifier for API requests
        api_url [in]: API endpoint URL
        api_id [in]: Environment variable name for API key
        is_active [in]: Active status (default: 1)
    
    Returns:
        Optional[Model]: Created Model instance or None on error
    """
    try:
        # Validate configuration
        is_valid, error_msg = validate_model_config(name, model_id, api_url, api_id)
        if not is_valid:
            logger.error(f"Invalid model config: {error_msg}")
            return None
        
        # Create in database
        try:
            db_model_id = db.create_model(name, model_id, api_url, api_id, is_active)
            return load_model_config(db_model_id)
        except ValueError as e:
            # Model already exists or validation error
            logger.error(f"Error creating model: {e}")
            return None
    except Exception as e:
        logger.error(f"Error creating model: {e}")
        return None


def update_model(model_id: int, name: Optional[str] = None,
                 model_id_value: Optional[str] = None,
                 api_url: Optional[str] = None, api_id: Optional[str] = None,
                 is_active: Optional[int] = None) -> bool:
    """
    Update model configuration.
    
    Args:
        model_id [in]: Model ID
        name [in]: New name (optional)
        model_id_value [in]: New model identifier (optional)
        api_url [in]: New API URL (optional)
        api_id [in]: New API ID (optional)
        is_active [in]: New active status (optional)
    
    Returns:
        bool: True if updated successfully
    """
    try:
        # If updating name, model_id, api_url, or api_id, validate them
        if name is not None or model_id_value is not None or api_url is not None or api_id is not None:
            # Load current model to get full config
            current_model = load_model_config(model_id)
            if not current_model:
                return False
            
            # Use provided values or current values
            new_name = name if name is not None else current_model.name
            new_model_id = model_id_value if model_id_value is not None else current_model.model_id
            new_api_url = api_url if api_url is not None else current_model.api_url
            new_api_id = api_id if api_id is not None else current_model.api_id
            
            # Validate
            is_valid, error_msg = validate_model_config(new_name, new_model_id, new_api_url, new_api_id)
            if not is_valid:
                logger.error(f"Invalid model config: {error_msg}")
                return False
        
        return db.update_model(model_id, name, model_id_value, api_url, api_id, is_active)
    except Exception as e:
        logger.error(f"Error updating model: {e}")
        return False


def delete_model(model_id: int) -> bool:
    """
    Delete a model from database.
    
    Args:
        model_id [in]: Model ID
    
    Returns:
        bool: True if deleted successfully
    """
    try:
        return db.delete_model(model_id)
    except Exception as e:
        logger.error(f"Error deleting model: {e}")
        return False

