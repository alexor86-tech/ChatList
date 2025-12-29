"""
Network module for ChatList application.
Provides API request handling for different AI model providers.
"""

import os
import json
import logging
import time
from typing import Optional, Dict, Any
from dotenv import load_dotenv
import requests
from models import Model


# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class APIError(Exception):
    """
    Custom exception for API errors.
    """
    pass


class BaseAPIClient:
    """
    Base class for API clients.
    """
    
    def __init__(self, model: Model, timeout: int = 30, max_retries: int = 3):
        """
        Initialize API client.
        
        Args:
            model [in]: Model instance
            timeout [in]: Request timeout in seconds
            max_retries [in]: Maximum number of retry attempts
        """
        self.model = model
        self.timeout = timeout
        self.max_retries = max_retries
        
        # Load API key from environment
        api_key = os.getenv(model.api_id)
        if not api_key:
            raise ValueError(f"API key not found for {model.api_id}")
        self.api_key = api_key
    
    def send_request(self, prompt: str) -> str:
        """
        Send request to API and return response text.
        
        Args:
            prompt [in]: Prompt text
        
        Returns:
            str: Response text from model
        
        Raises:
            APIError: If request fails
        """
        raise NotImplementedError("Subclass must implement send_request")
    
    def _extract_error_from_html(self, html_text: str) -> str:
        """
        Extract error message from HTML response.
        
        Args:
            html_text [in]: HTML response text
        
        Returns:
            str: Extracted error message or default message
        """
        # Local variables
        html_lower = html_text.lower()
        
        # Try to find common error patterns in HTML
        error_patterns = [
            ('<title>', '</title>'),
            ('<h1>', '</h1>'),
            ('<h2>', '</h2>'),
            ('class="error"', '>'),
            ('id="error"', '>'),
        ]
        
        # Check for common error messages
        if '404' in html_text or 'not found' in html_lower:
            return "Возможно, неправильный URL API (404 Not Found)"
        elif '401' in html_text or 'unauthorized' in html_lower:
            return "Проблема с аутентификацией (401 Unauthorized)"
        elif '403' in html_text or 'forbidden' in html_lower:
            return "Доступ запрещен (403 Forbidden)"
        elif '500' in html_text or 'internal server error' in html_lower:
            return "Ошибка сервера (500 Internal Server Error)"
        elif 'bad request' in html_lower or '400' in html_text:
            return "Неверный запрос (400 Bad Request)"
        
        # Try to extract title
        try:
            title_start = html_text.find('<title>')
            title_end = html_text.find('</title>', title_start)
            if title_start != -1 and title_end != -1:
                title = html_text[title_start + 7:title_end].strip()
                if title and len(title) < 100:
                    return f"Заголовок страницы: {title}"
        except Exception:
            pass
        
        # Default message
        return "Проверьте правильность URL API и API-ключа"
    
    def _extract_error_from_json(self, json_text: str, status_code: int) -> str:
        """
        Extract error message from JSON error response.
        
        Args:
            json_text [in]: JSON response text
            status_code [in]: HTTP status code
        
        Returns:
            str: Extracted error message
        """
        try:
            # Try to parse JSON
            error_data = json.loads(json_text)
            
            # Check for common error structures
            if isinstance(error_data, dict):
                # OpenRouter/OpenAI format: {"error": {"message": "...", "code": 404}}
                if "error" in error_data and isinstance(error_data["error"], dict):
                    error_obj = error_data["error"]
                    if "message" in error_obj:
                        message = error_obj["message"]
                        # Add status code if not already in message
                        if str(status_code) not in message:
                            return f"({status_code}) {message}"
                        return message
                
                # Direct message format: {"message": "..."}
                if "message" in error_data:
                    message = error_data["message"]
                    if str(status_code) not in message:
                        return f"({status_code}) {message}"
                    return message
                
                # Fallback: return formatted JSON
                return f"({status_code}) {json.dumps(error_data, ensure_ascii=False)[:200]}"
        except (json.JSONDecodeError, ValueError):
            # Not valid JSON, return text
            pass
        
        # Fallback: return truncated text
        error_text = json_text[:200] if len(json_text) > 200 else json_text
        return f"({status_code}) {error_text}"
    
    def _make_request(self, url: str, headers: Dict[str, str], 
                      payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Make HTTP request with retry logic.
        
        Args:
            url [in]: Request URL
            headers [in]: Request headers
            payload [in]: Request payload
        
        Returns:
            Dict[str, Any]: Response JSON data
        
        Raises:
            APIError: If request fails after retries
        """
        # Local variables
        last_error = None
        
        for attempt in range(self.max_retries):
            try:
                response = requests.post(
                    url,
                    headers=headers,
                    json=payload,
                    timeout=self.timeout
                )
                
                # Check HTTP status
                if response.status_code == 200:
                    # Check Content-Type
                    content_type = response.headers.get('Content-Type', '').lower()
                    
                    # Check if response is HTML instead of JSON
                    response_text = response.text.strip()
                    if not response_text:
                        raise APIError("Пустой ответ от сервера")
                    
                    # Detect HTML response
                    is_html = (
                        'text/html' in content_type or
                        response_text.startswith('<!DOCTYPE') or
                        response_text.startswith('<html') or
                        response_text.startswith('<HTML')
                    )
                    
                    if is_html:
                        # Try to extract error message from HTML
                        error_msg = self._extract_error_from_html(response_text)
                        raise APIError(f"Сервер вернул HTML вместо JSON. {error_msg}")
                    
                    # Try to parse JSON response
                    try:
                        return response.json()
                    except ValueError as e:
                        # Not valid JSON
                        error_text = response.text[:200] if len(response.text) > 200 else response.text
                        raise APIError(f"Неверный формат ответа от сервера (не JSON): {error_text[:100]}")
                elif response.status_code == 401:
                    raise APIError("Неверный API-ключ")
                elif response.status_code == 429:
                    # Rate limit - wait and retry
                    wait_time = 2 ** attempt
                    logger.warning(f"Rate limited, waiting {wait_time}s before retry")
                    time.sleep(wait_time)
                    continue
                else:
                    # Check if response is HTML
                    response_text = response.text.strip()
                    is_html = (
                        response_text.startswith('<!DOCTYPE') or
                        response_text.startswith('<html') or
                        response_text.startswith('<HTML')
                    )
                    
                    if is_html:
                        error_msg = self._extract_error_from_html(response_text)
                        raise APIError(f"({response.status_code}) {error_msg}")
                    else:
                        # Try to parse JSON error response
                        error_msg = self._extract_error_from_json(response_text, response.status_code)
                        logger.error(f"API error {response.status_code}: {error_msg}")
                        raise APIError(error_msg)
                    
            except requests.exceptions.Timeout:
                last_error = f"Таймаут запроса после {self.timeout}с"
                logger.warning(f"Attempt {attempt + 1}/{self.max_retries}: {last_error}")
                if attempt < self.max_retries - 1:
                    time.sleep(1)
                continue
            except requests.exceptions.RequestException as e:
                last_error = f"Ошибка сети: {str(e)}"
                logger.warning(f"Attempt {attempt + 1}/{self.max_retries}: {last_error}")
                if attempt < self.max_retries - 1:
                    time.sleep(1)
                continue
            except ValueError as e:
                # JSON parsing error
                last_error = f"Ошибка парсинга ответа: {str(e)}"
                logger.warning(f"Attempt {attempt + 1}/{self.max_retries}: {last_error}")
                if attempt < self.max_retries - 1:
                    time.sleep(1)
                continue
        
        raise APIError(f"Запрос не удался после {self.max_retries} попыток: {last_error}")


class OpenRouterAPIClient(BaseAPIClient):
    """
    OpenRouter API client (OpenAI-compatible format).
    """
    
    def send_request(self, prompt: str) -> str:
        """
        Send request to OpenRouter API.
        
        Args:
            prompt [in]: Prompt text
        
        Returns:
            str: Response text
        
        Raises:
            APIError: If request fails
        """
        # Local variables
        url = self.model.api_url
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/yourusername/ChatList",
            "X-Title": "ChatList"
        }
        
        # Use model_id for API requests
        # OpenRouter format: https://openrouter.ai/api/v1/chat/completions
        # Model is specified in payload
        model_id = self.model.model_id
        
        payload = {
            "model": model_id,
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        }
        
        try:
            response_data = self._make_request(url, headers, payload)
            
            # Parse OpenAI-compatible response
            if "choices" in response_data and len(response_data["choices"]) > 0:
                return response_data["choices"][0]["message"]["content"]
            else:
                raise APIError("Неверный формат ответа от API")
                
        except Exception as e:
            if isinstance(e, APIError):
                raise
            raise APIError(f"Ошибка отправки запроса: {str(e)}")


class OpenAIAPIClient(BaseAPIClient):
    """
    OpenAI API client.
    """
    
    def send_request(self, prompt: str) -> str:
        """
        Send request to OpenAI API.
        
        Args:
            prompt [in]: Prompt text
        
        Returns:
            str: Response text
        
        Raises:
            APIError: If request fails
        """
        # Local variables
        url = self.model.api_url
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": self.model.model_id,
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        }
        
        try:
            response_data = self._make_request(url, headers, payload)
            
            # Parse OpenAI response
            if "choices" in response_data and len(response_data["choices"]) > 0:
                return response_data["choices"][0]["message"]["content"]
            else:
                raise APIError("Invalid response format from API")
                
        except Exception as e:
            if isinstance(e, APIError):
                raise
            raise APIError(f"Error sending request: {str(e)}")


class DeepSeekAPIClient(BaseAPIClient):
    """
    DeepSeek API client (OpenAI-compatible format).
    """
    
    def send_request(self, prompt: str) -> str:
        """
        Send request to DeepSeek API.
        
        Args:
            prompt [in]: Prompt text
        
        Returns:
            str: Response text
        
        Raises:
            APIError: If request fails
        """
        # Local variables
        url = self.model.api_url
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": self.model.model_id,
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        }
        
        try:
            response_data = self._make_request(url, headers, payload)
            
            # Parse OpenAI-compatible response
            if "choices" in response_data and len(response_data["choices"]) > 0:
                return response_data["choices"][0]["message"]["content"]
            else:
                raise APIError("Неверный формат ответа от API")
                
        except Exception as e:
            if isinstance(e, APIError):
                raise
            raise APIError(f"Ошибка отправки запроса: {str(e)}")


class GroqAPIClient(BaseAPIClient):
    """
    Groq API client (OpenAI-compatible format).
    """
    
    def send_request(self, prompt: str) -> str:
        """
        Send request to Groq API.
        
        Args:
            prompt [in]: Prompt text
        
        Returns:
            str: Response text
        
        Raises:
            APIError: If request fails
        """
        # Local variables
        url = self.model.api_url
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": self.model.model_id,
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        }
        
        try:
            response_data = self._make_request(url, headers, payload)
            
            # Parse OpenAI-compatible response
            if "choices" in response_data and len(response_data["choices"]) > 0:
                return response_data["choices"][0]["message"]["content"]
            else:
                raise APIError("Неверный формат ответа от API")
                
        except Exception as e:
            if isinstance(e, APIError):
                raise
            raise APIError(f"Ошибка отправки запроса: {str(e)}")


def create_api_client(model: Model, timeout: int = 30, 
                      max_retries: int = 3) -> BaseAPIClient:
    """
    Create appropriate API client based on model configuration.
    
    Args:
        model [in]: Model instance
        timeout [in]: Request timeout in seconds
        max_retries [in]: Maximum number of retry attempts
    
    Returns:
        BaseAPIClient: API client instance
    
    Raises:
        ValueError: If API client type is not supported
    """
    # Local variables
    api_url_lower = model.api_url.lower()
    
    # Determine client type based on URL
    if "openrouter" in api_url_lower:
        return OpenRouterAPIClient(model, timeout, max_retries)
    elif "openai" in api_url_lower or "api.openai.com" in api_url_lower:
        return OpenAIAPIClient(model, timeout, max_retries)
    elif "deepseek" in api_url_lower:
        return DeepSeekAPIClient(model, timeout, max_retries)
    elif "groq" in api_url_lower:
        return GroqAPIClient(model, timeout, max_retries)
    else:
        # Default to OpenAI-compatible format (works for most providers)
        logger.info(f"Using OpenAI-compatible client for {model.name}")
        return OpenAIAPIClient(model, timeout, max_retries)


def send_prompt_to_model(model: Model, prompt: str, 
                        timeout: int = 30, max_retries: int = 3) -> str:
    """
    Send prompt to a model and get response.
    
    Args:
        model [in]: Model instance
        prompt [in]: Prompt text
        timeout [in]: Request timeout in seconds
        max_retries [in]: Maximum number of retry attempts
    
    Returns:
        str: Response text
    
    Raises:
        APIError: If request fails
    """
    # Local variables
    client = create_api_client(model, timeout, max_retries)
    return client.send_request(prompt)

