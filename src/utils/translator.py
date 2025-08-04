from typing import Optional, Dict, Any
import asyncio
from functools import lru_cache
from deep_translator import GoogleTranslator, MicrosoftTranslator, ChatGptTranslator
from src.utils import LoggerMixin, MetricsMixin
from src.config import settings


class TranslationService(LoggerMixin, MetricsMixin):
    """Service for translating text using various translation APIs."""
    
    def __init__(self):
        self.target_language = getattr(settings, 'translation_target_language', 'ru')  # Default to Russian
        self.source_language = getattr(settings, 'translation_source_language', 'auto')  # Auto-detect
        self._translators = self._init_translators()
        
    def _init_translators(self) -> Dict[str, Any]:
        """Initialize available translators."""
        translators = {}
        
        try:
            # Google Translate (free, no API key required)
            translators['google'] = GoogleTranslator(
                source=self.source_language,
                target=self.target_language
            )
            self.log_info("Google Translator initialized")
        except Exception as e:
            self.log_warning("Failed to initialize Google Translator", error=str(e))
        
        try:
            # Microsoft Translator (requires API key)
            api_key = getattr(settings, 'microsoft_translator_key', None)
            if api_key:
                translators['microsoft'] = MicrosoftTranslator(
                    api_key=api_key,
                    source=self.source_language,
                    target=self.target_language
                )
                self.log_info("Microsoft Translator initialized")
        except Exception as e:
            self.log_warning("Failed to initialize Microsoft Translator", error=str(e))
            
        try:
            # ChatGPT Translator (requires OpenAI API key)
            api_key = getattr(settings, 'openai_api_key', None)
            if api_key:
                translators['chatgpt'] = ChatGptTranslator(
                    api_key=api_key,
                    source=self.source_language,
                    target=self.target_language
                )
                self.log_info("ChatGPT Translator initialized")
        except Exception as e:
            self.log_warning("Failed to initialize ChatGPT Translator", error=str(e))
        
        if not translators:
            self.log_error("No translators available!")
            
        return translators
    
    @lru_cache(maxsize=1000)
    def _translate_cached(self, text: str, translator_name: str) -> Optional[str]:
        """Cached translation to avoid repeated API calls."""
        try:
            translator = self._translators.get(translator_name)
            if not translator:
                return None
                
            result = translator.translate(text)
            return result
        except Exception as e:
            self.log_warning(f"Translation failed with {translator_name}", error=str(e))
            return None
    
    async def translate_text(self, text: str, preferred_translator: str = 'google') -> Optional[str]:
        """
        Translate text using the specified translator with fallback options.
        
        Args:
            text: Text to translate
            preferred_translator: Preferred translator ('google', 'microsoft', 'chatgpt')
            
        Returns:
            Translated text or None if translation fails
        """
        if not text or not text.strip():
            return text
            
        # Skip translation if text is too short or already seems to be in target language
        if len(text.strip()) < 10:
            return text
            
        # Try preferred translator first
        translators_to_try = [preferred_translator]
        
        # Add fallback translators
        for name in self._translators.keys():
            if name not in translators_to_try:
                translators_to_try.append(name)
        
        for translator_name in translators_to_try:
            try:
                # Run translation in thread pool to avoid blocking
                loop = asyncio.get_event_loop()
                translated = await loop.run_in_executor(
                    None, 
                    self._translate_cached, 
                    text, 
                    translator_name
                )
                
                if translated and translated.strip():
                    self.log_info(f"Successfully translated text using {translator_name}")
                    return translated
                    
            except Exception as e:
                self.log_warning(f"Translation attempt failed with {translator_name}", error=str(e))
                continue
        
        self.log_error("All translation attempts failed")
        return None
    
    async def translate_article(self, article: Dict[str, Any]) -> Dict[str, Any]:
        """
        Translate article title and description.
        
        Args:
            article: Article dictionary with 'title' and 'description' keys
            
        Returns:
            Article dictionary with translated content
        """
        translated_article = article.copy()
        
        # Translate title
        if article.get('title'):
            translated_title = await self.translate_text(article['title'])
            if translated_title:
                translated_article['title_original'] = article['title']
                # Replace title with translated version
                translated_article['title'] = translated_title
        
        # Translate description
        if article.get('description'):
            translated_desc = await self.translate_text(article['description'])
            if translated_desc:
                translated_article['description_original'] = article['description']
                # Replace description with translated version
                translated_article['description'] = translated_desc
        
        return translated_article
    
    def clear_cache(self):
        """Clear translation cache."""
        self._translate_cached.cache_clear()
        self.log_info("Translation cache cleared")
    
    def get_cache_info(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return {
            "cache_info": self._translate_cached.cache_info()._asdict(),
            "available_translators": list(self._translators.keys()),
            "target_language": self.target_language,
            "source_language": self.source_language
        }