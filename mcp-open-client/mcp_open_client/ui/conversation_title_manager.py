"""
Conversation Title Manager

This module handles automatic generation of conversation titles using LLM.
Provides functionality to generate descriptive titles based on conversation content.
"""

import logging
from typing import Dict, List, Optional, Any
from ..api_client import APIClient

logger = logging.getLogger("ConversationTitleManager")

class ConversationTitleManager:
    """Manages automatic generation of conversation titles using LLM."""
    
    def __init__(self, api_client: APIClient):
        """Initialize the title manager with an API client.
        
        Args:
            api_client: The API client instance to use for LLM calls
        """
        self.api_client = api_client
        self.max_title_length = 50
        self.trigger_message_count = 3  # Auto-rename after 3 messages
    
    async def generate_conversation_title(self, messages: List[Dict[str, Any]], max_length: Optional[int] = None) -> str:
        """Generate a descriptive title for a conversation based on its messages.
        
        Args:
            messages: List of conversation messages
            max_length: Maximum length of the generated title (defaults to self.max_title_length)
            
        Returns:
            A descriptive title for the conversation
        """
        max_length = max_length or self.max_title_length
        
        try:
            # Include user, assistant, and tool messages (tool calls contain actual LLM responses)
            relevant_messages = [msg for msg in messages if msg.get('role') in ['user', 'assistant', 'tool']]
            
            if not relevant_messages:
                return "New Conversation"
            
            sample_messages = relevant_messages[:6]
            
            # Build context from multiple messages for better title generation
            context_text = ""
            for i, msg in enumerate(sample_messages[:3]):
                role = msg.get('role', 'unknown')
                content = msg.get('content') or ''  # Handle None content
                content = str(content)[:150]  # Ensure it's a string and slice
                context_text += f"{role}: {content}\n"
            
            response = await self.api_client.chat_completion(
                messages=[{
                    "role": "system",
                    "content": "You are a title generator. Generate ONLY a short, descriptive title (2-6 words) for the conversation. Do not include quotes, prefixes, or explanations. Just return the title."
                }, {
                    "role": "user",
                    "content": f"Generate a title for this conversation:\n\n{context_text.strip()}"
                }]
            )
            
            if response and 'choices' in response and response['choices']:
                title = response['choices'][0]['message']['content'].strip()
                # Remove quotes, periods, and slashes
                title = title.strip('"\'.\\/').strip()
                
                # Remove common prefixes and phrases
                prefixes_to_remove = [
                    "Title:", "title:", "TITLE:", 
                    "Conversation:", "conversation:", "CONVERSATION:",
                    "Here's a title:", "Here is a title:",
                    "A good title would be:", "The title could be:",
                    "I suggest:", "How about:"
                ]
                for prefix in prefixes_to_remove:
                    if title.lower().startswith(prefix.lower()):
                        title = title[len(prefix):].strip()
                
                # Take only the first line (in case of multi-line response)
                title = title.split('\n')[0].strip()
                
                # Remove any remaining quotes
                title = title.strip('"\'')
                
                # Remove Markdown formatting (**, *, _, etc.)
                title = title.replace('**', '').replace('*', '').replace('_', '').replace('`', '')
                
                # Remove colons at the end (common in LLM responses)
                title = title.rstrip(':')
                
                # Clean up extra spaces
                title = ' '.join(title.split())
                
                print(f"Auto-rename: Generated title '{title}' for conversation")
                
                if len(title) > max_length:
                    title = title[:max_length-3] + "..."
                
                return title if title else "Conversation"
            
            return "Conversation"
            
        except Exception as e:
            print(f"Error generating conversation title: {e}")
            import traceback
            traceback.print_exc()
            return "Conversation"
    
    def should_auto_rename(self, messages: List[Dict[str, Any]]) -> bool:
        """Check if a conversation should be automatically renamed.
        
        Args:
            messages: List of conversation messages
            
        Returns:
            True if the conversation should be auto-renamed
        """
        # Count user, assistant, and tool messages (tool calls contain actual LLM responses)
        relevant_messages = [msg for msg in messages if msg.get('role') in ['user', 'assistant', 'tool']]
        return len(relevant_messages) >= self.trigger_message_count
    
    def validate_title(self, title: str, max_length: Optional[int] = None) -> str:
        """Validate and clean up a conversation title.
        
        Args:
            title: The title to validate
            max_length: Maximum allowed length (defaults to self.max_title_length)
            
        Returns:
            Cleaned and validated title
        """
        max_length = max_length or self.max_title_length
        
        if not title or not title.strip():
            return "Conversation"
        
        # Clean up the title
        cleaned_title = title.strip()
        
        # Remove invalid characters for file names (in case titles are used for file names)
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            cleaned_title = cleaned_title.replace(char, '')
        
        # Ensure length
        if len(cleaned_title) > max_length:
            cleaned_title = cleaned_title[:max_length-3] + "..."
        
        return cleaned_title if cleaned_title else "Conversation"


# Global instance (will be initialized when needed)
_title_manager_instance: Optional[ConversationTitleManager] = None

def get_title_manager() -> ConversationTitleManager:
    """Get the global title manager instance.
    
    Returns:
        The global ConversationTitleManager instance
    """
    global _title_manager_instance
    
    if _title_manager_instance is None:
        # Import here to avoid circular imports
        from ..ui.configure import get_api_client
        api_client = get_api_client()
        _title_manager_instance = ConversationTitleManager(api_client)
    
    return _title_manager_instance

def reset_title_manager():
    """Reset the global title manager instance (useful for testing)."""
    global _title_manager_instance
    _title_manager_instance = None