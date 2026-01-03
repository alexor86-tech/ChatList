"""
Prompt improver module for ChatList application.
Provides functionality to improve prompts using AI models.
"""

import logging
import json
import re
from typing import Optional, Dict, List, Any
import network
import models


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PromptImprover:
    """
    Class for improving prompts using AI models.
    """
    
    def __init__(self, timeout: int = 30, max_retries: int = 3):
        """
        Initialize prompt improver.
        
        @param [in] timeout Request timeout in seconds
        @param [in] max_retries Maximum number of retry attempts
        """
        self.timeout = timeout
        self.max_retries = max_retries
    
    def improve_prompt(self, original_prompt: str, model: models.Model) -> Optional[str]:
        """
        Improve a prompt using AI model.
        
        @param [in] original_prompt Original prompt text
        @param [in] model Model instance to use for improvement
        
        @return [out] Improved prompt text or None on error
        """
        try:
            # Create improvement prompt
            improvement_prompt = self._create_improvement_prompt(original_prompt)
            
            # Send request to model
            response = network.send_prompt_to_model(
                model, improvement_prompt, self.timeout, self.max_retries
            )
            
            # Extract improved prompt from response
            improved = self._extract_improved_prompt(response, original_prompt)
            return improved
            
        except Exception as e:
            logger.error(f"Error improving prompt: {e}")
            raise
    
    def generate_variants(self, original_prompt: str, model: models.Model, 
                         num_variants: int = 3) -> List[str]:
        """
        Generate alternative variants of a prompt.
        
        @param [in] original_prompt Original prompt text
        @param [in] model Model instance to use
        @param [in] num_variants Number of variants to generate (2-3)
        
        @return [out] List of variant prompts
        """
        try:
            # Limit variants to 2-3
            if num_variants < 2:
                num_variants = 2
            elif num_variants > 3:
                num_variants = 3
            
            # Create variants prompt
            variants_prompt = self._create_variants_prompt(original_prompt, num_variants)
            
            # Send request to model
            response = network.send_prompt_to_model(
                model, variants_prompt, self.timeout, self.max_retries
            )
            
            # Extract variants from response
            variants = self._extract_variants(response, num_variants)
            return variants
            
        except Exception as e:
            logger.error(f"Error generating variants: {e}")
            raise
    
    def adapt_for_model_type(self, prompt: str, model: models.Model, 
                            adaptation_type: str) -> Optional[str]:
        """
        Adapt prompt for specific model type (code, analysis, creative).
        
        @param [in] prompt Original prompt text
        @param [in] model Model instance to use
        @param [in] adaptation_type Type of adaptation: "code", "analysis", "creative", or "general"
        
        @return [out] Adapted prompt text or None on error
        """
        try:
            # Create adaptation prompt
            adaptation_prompt = self._create_adaptation_prompt(prompt, adaptation_type)
            
            # Send request to model
            response = network.send_prompt_to_model(
                model, adaptation_prompt, self.timeout, self.max_retries
            )
            
            # Extract adapted prompt from response
            adapted = self._extract_improved_prompt(response, prompt)
            return adapted
            
        except Exception as e:
            logger.error(f"Error adapting prompt: {e}")
            raise
    
    def improve_with_variants(self, original_prompt: str, model: models.Model,
                             adaptation_type: Optional[str] = None) -> Dict[str, Any]:
        """
        Improve prompt and generate variants in one request.
        
        @param [in] original_prompt Original prompt text
        @param [in] model Model instance to use
        @param [in] adaptation_type Optional adaptation type
        
        @return [out] Dictionary with improved prompt and variants
        """
        try:
            # Create combined prompt
            if adaptation_type:
                combined_prompt = self._create_combined_prompt(
                    original_prompt, adaptation_type
                )
            else:
                combined_prompt = self._create_combined_prompt(original_prompt)
            
            # Send request to model
            response = network.send_prompt_to_model(
                model, combined_prompt, self.timeout, self.max_retries
            )
            
            # Parse response
            result = self._parse_combined_response(response, original_prompt)
            return result
            
        except Exception as e:
            logger.error(f"Error improving with variants: {e}")
            raise
    
    def _create_improvement_prompt(self, original_prompt: str) -> str:
        """
        Create prompt for improving a prompt.
        
        @param [in] original_prompt Original prompt text
        
        @return [out] Improvement prompt text
        """
        return f"""Улучши следующий промт, сделав его более четким, конкретным и эффективным. 
Сохрани основную суть и цель промта, но улучши формулировку для лучшего понимания AI-моделью.

Исходный промт:
{original_prompt}

Верни только улучшенную версию промта без дополнительных объяснений."""
    
    def _create_variants_prompt(self, original_prompt: str, num_variants: int) -> str:
        """
        Create prompt for generating variants.
        
        @param [in] original_prompt Original prompt text
        @param [in] num_variants Number of variants to generate
        
        @return [out] Variants prompt text
        """
        return f"""Создай {num_variants} альтернативных варианта следующего промта, переформулировав его разными способами, но сохраняя основную суть.

Исходный промт:
{original_prompt}

Верни {num_variants} варианта, каждый на отдельной строке, пронумеровав их как:
1. [первый вариант]
2. [второй вариант]
3. [третий вариант] (если нужно)

Только варианты, без дополнительных объяснений."""
    
    def _create_adaptation_prompt(self, prompt: str, adaptation_type: str) -> str:
        """
        Create prompt for adapting a prompt to specific type.
        
        @param [in] prompt Original prompt text
        @param [in] adaptation_type Type of adaptation
        
        @return [out] Adaptation prompt text
        """
        # Local variables
        type_descriptions = {
            "code": "для работы с кодом, программированием и техническими задачами",
            "analysis": "для аналитических задач, анализа данных и логических рассуждений",
            "creative": "для творческих задач, генерации идей и креативного контента",
            "general": "для общего использования"
        }
        
        description = type_descriptions.get(adaptation_type, type_descriptions["general"])
        
        return f"""Адаптируй следующий промт {description}. 
Сохрани основную суть, но оптимизируй формулировку для указанного типа задач.

Исходный промт:
{prompt}

Верни только адаптированную версию промта без дополнительных объяснений."""
    
    def _create_combined_prompt(self, original_prompt: str, 
                               adaptation_type: Optional[str] = None) -> str:
        """
        Create combined prompt for improvement and variants.
        
        @param [in] original_prompt Original prompt text
        @param [in] adaptation_type Optional adaptation type
        
        @return [out] Combined prompt text
        """
        # Local variables
        base_prompt = f"""Улучши следующий промт и создай 2-3 альтернативных варианта его переформулировки.

Исходный промт:
{original_prompt}

Верни ответ в следующем формате:
УЛУЧШЕННАЯ ВЕРСИЯ:
[улучшенная версия промта]

ВАРИАНТЫ:
1. [первый вариант]
2. [второй вариант]
3. [третий вариант]"""
        
        if adaptation_type:
            type_descriptions = {
                "code": "для работы с кодом",
                "analysis": "для аналитических задач",
                "creative": "для творческих задач",
                "general": "для общего использования"
            }
            description = type_descriptions.get(adaptation_type, "")
            if description:
                base_prompt = f"""Адаптируй следующий промт {description} и создай 2-3 альтернативных варианта его переформулировки.

Исходный промт:
{original_prompt}

Верни ответ в следующем формате:
УЛУЧШЕННАЯ ВЕРСИЯ:
[адаптированная версия промта]

ВАРИАНТЫ:
1. [первый вариант]
2. [второй вариант]
3. [третий вариант]"""
        
        return base_prompt
    
    def _extract_improved_prompt(self, response: str, original_prompt: str) -> str:
        """
        Extract improved prompt from AI response.
        
        @param [in] response AI response text
        @param [in] original_prompt Original prompt (fallback)
        
        @return [out] Extracted improved prompt
        """
        # Local variables
        response_clean = response.strip()
        
        # Try to find improved version markers
        markers = [
            "УЛУЧШЕННАЯ ВЕРСИЯ:",
            "Улучшенная версия:",
            "Улучшенный промт:",
            "Исправленный промт:",
            "Улучшенная:"
        ]
        
        for marker in markers:
            if marker in response_clean:
                # Extract text after marker
                parts = response_clean.split(marker, 1)
                if len(parts) > 1:
                    improved = parts[1].strip()
                    # Remove "ВАРИАНТЫ:" section if present
                    if "ВАРИАНТЫ:" in improved:
                        improved = improved.split("ВАРИАНТЫ:")[0].strip()
                    if improved:
                        return improved
        
        # If no marker found, try to extract first paragraph
        lines = response_clean.split('\n')
        non_empty_lines = [line.strip() for line in lines if line.strip()]
        
        if non_empty_lines:
            # Return first substantial line (not too short)
            for line in non_empty_lines:
                if len(line) > 20 and not line.startswith(('1.', '2.', '3.', '-', '*')):
                    return line
        
        # Fallback: return response if it's different from original
        if response_clean != original_prompt and len(response_clean) > 10:
            return response_clean
        
        # Last resort: return original
        return original_prompt
    
    def _extract_variants(self, response: str, num_variants: int) -> List[str]:
        """
        Extract variant prompts from AI response.
        
        @param [in] response AI response text
        @param [in] num_variants Expected number of variants
        
        @return [out] List of variant prompts
        """
        # Local variables
        variants = []
        response_clean = response.strip()
        
        # Try to find variants section
        if "ВАРИАНТЫ:" in response_clean:
            variants_section = response_clean.split("ВАРИАНТЫ:")[1].strip()
        elif "Варианты:" in response_clean:
            variants_section = response_clean.split("Варианты:")[1].strip()
        else:
            variants_section = response_clean
        
        # Extract numbered variants
        # Pattern: "1. text" or "1) text" or "- text"
        patterns = [
            r'^\d+[\.\)]\s*(.+)$',  # "1. text" or "1) text"
            r'^-\s*(.+)$',  # "- text"
            r'^\*\s*(.+)$'  # "* text"
        ]
        
        lines = variants_section.split('\n')
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Try each pattern
            for pattern in patterns:
                match = re.match(pattern, line)
                if match:
                    variant_text = match.group(1).strip()
                    if variant_text and len(variant_text) > 5:
                        variants.append(variant_text)
                        break
        
        # If not enough variants found, try to split by lines
        if len(variants) < num_variants:
            # Look for lines that look like variants
            for line in lines:
                line = line.strip()
                if (line and len(line) > 10 and 
                    not line.startswith(('УЛУЧШЕННАЯ', 'ВАРИАНТЫ', 'Варианты')) and
                    line not in variants):
                    variants.append(line)
        
        # Limit to requested number
        return variants[:num_variants] if variants else []
    
    def _parse_combined_response(self, response: str, 
                                original_prompt: str) -> Dict[str, Any]:
        """
        Parse combined response with improved prompt and variants.
        
        @param [in] response AI response text
        @param [in] original_prompt Original prompt (fallback)
        
        @return [out] Dictionary with improved and variants
        """
        # Local variables
        result = {
            "improved": None,
            "variants": []
        }
        
        response_clean = response.strip()
        
        # Extract improved version
        if "УЛУЧШЕННАЯ ВЕРСИЯ:" in response_clean:
            improved_section = response_clean.split("УЛУЧШЕННАЯ ВЕРСИЯ:")[1]
            if "ВАРИАНТЫ:" in improved_section:
                improved_section = improved_section.split("ВАРИАНТЫ:")[0]
            result["improved"] = improved_section.strip()
        else:
            # Try to extract first part as improved
            result["improved"] = self._extract_improved_prompt(response_clean, original_prompt)
        
        # Extract variants
        if "ВАРИАНТЫ:" in response_clean:
            variants_section = response_clean.split("ВАРИАНТЫ:")[1].strip()
            result["variants"] = self._extract_variants(variants_section, 3)
        else:
            # Try to extract variants from whole response
            result["variants"] = self._extract_variants(response_clean, 3)
        
        return result

