#!/usr/bin/env python3
"""
Database initialization script.
Creates database and adds example models.
"""

import db
import models


def init_example_models():
    """
    Initialize example models for OpenRouter.
    """
    # Local variables
    example_models = [
        {
            "name": "GPT-4",
            "model_id": "openai/gpt-4",
            "api_url": "https://openrouter.ai/api/v1/chat/completions",
            "api_id": "OPENROUTER_API_KEY",
            "is_active": 1
        },
        {
            "name": "GPT-3.5 Turbo",
            "model_id": "openai/gpt-3.5-turbo",
            "api_url": "https://openrouter.ai/api/v1/chat/completions",
            "api_id": "OPENROUTER_API_KEY",
            "is_active": 1
        },
        {
            "name": "Claude 3 Opus",
            "model_id": "anthropic/claude-3-opus",
            "api_url": "https://openrouter.ai/api/v1/chat/completions",
            "api_id": "OPENROUTER_API_KEY",
            "is_active": 1
        },
        {
            "name": "Claude 3 Sonnet",
            "model_id": "anthropic/claude-3-sonnet",
            "api_url": "https://openrouter.ai/api/v1/chat/completions",
            "api_id": "OPENROUTER_API_KEY",
            "is_active": 1
        },
        {
            "name": "Gemini Pro",
            "model_id": "google/gemini-pro",
            "api_url": "https://openrouter.ai/api/v1/chat/completions",
            "api_id": "OPENROUTER_API_KEY",
            "is_active": 1
        }
    ]
    
    # Check if models already exist
    existing_models = models.get_all_models()
    existing_names = {model.name for model in existing_models}
    
    # Add models that don't exist
    added_count = 0
    for model_data in example_models:
        if model_data["name"] not in existing_names:
            try:
                new_model = models.create_model(
                    model_data["name"],
                    model_data["model_id"],
                    model_data["api_url"],
                    model_data["api_id"],
                    model_data["is_active"]
                )
                if new_model:
                    added_count += 1
                    print(f"Added model: {model_data['name']}")
            except ValueError as e:
                # Model already exists (should not happen due to check above, but handle anyway)
                print(f"Skipped model {model_data['name']}: {e}")
            except Exception as e:
                print(f"Error adding model {model_data['name']}: {e}")
    
    print(f"\nInitialization complete. Added {added_count} new model(s).")
    print(f"Total models in database: {len(models.get_all_models())}")


if __name__ == "__main__":
    print("Initializing database...")
    db.init_database()
    print("Database initialized.")
    
    print("\nAdding example models...")
    init_example_models()

