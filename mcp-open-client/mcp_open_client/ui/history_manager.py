"""
History Manager with accurate token counting using tiktoken
"""

import tiktoken
import json

class HistoryManager:
    def __init__(self, max_messages=50):
        self._default_max_messages = max_messages
        self._default_settings = {
            'max_messages': max_messages,
            'max_tokens_per_message': 10000,
            'max_tokens_per_conversation': 50000,  # Independent value, not derived
            'auto_cleanup': True,
            'preserve_tool_calls': True,
            'compression_enabled': False,
            'truncate_mode': 'simple',
            'token_counting_method': 'tiktoken'  # Using tiktoken for accurate counting
        }
    
    @property
    def max_messages(self):
        """Get max_messages from storage on-demand"""
        try:
            from nicegui import app
            settings = app.storage.user.get('history-settings', {})
            return settings.get('max_messages', self._default_settings['max_messages'])
        except:
            return self._default_settings['max_messages']
    
    
    def update_setting(self, setting_name, value):
        """Update a specific setting and save to storage"""
        if setting_name not in self._default_settings:
            return False
            
        try:
            from nicegui import app
            if 'history-settings' not in app.storage.user:
                app.storage.user['history-settings'] = {}
            app.storage.user['history-settings'][setting_name] = value
            return True
        except Exception as e:
            return False
    
    def update_max_messages(self, max_messages):
        """Update max messages setting (legacy method)"""
        return self.update_setting('max_messages', max_messages)
    
    def cleanup_conversation_if_needed(self, conversation_id: str) -> bool:
        """
        Cleanup conversation if it exceeds limits:
        1. If message count exceeds max_messages: keep only the last max_messages
        2. If token count exceeds max_tokens_per_conversation: remove oldest messages until below limit
        
        Tool call validation is handled by _final_tool_sequence_validation.
        """
        from .chat_handlers import get_conversation_storage
        conversations = get_conversation_storage()
        
        if conversation_id not in conversations:
            return False
        
        messages = conversations[conversation_id]['messages']
        original_count = len(messages)
        settings = self.settings
        max_tokens = settings.get('max_tokens_per_conversation', 50000)
        
        # Check if we need to clean up based on message count
        message_cleanup_needed = original_count > self.max_messages
        
        # Check if we need to clean up based on token count
        conv_stats = self.get_conversation_size(conversation_id)
        token_cleanup_needed = conv_stats['total_tokens'] > max_tokens
        
        if not message_cleanup_needed and not token_cleanup_needed:
            return False
        
        # If we need to clean up based on message count
        if message_cleanup_needed:
            # Separate context messages from regular messages
            context_messages = [msg for msg in messages if msg.get('is_context', False)]
            regular_messages = [msg for msg in messages if not msg.get('is_context', False)]
            
            # Only count regular messages for the limit
            regular_count = len(regular_messages)
            if regular_count > self.max_messages:
                # Simple rolling window: keep the last max_messages of regular messages
                messages_to_remove = regular_count - self.max_messages
                kept_regular_messages = regular_messages[messages_to_remove:]
                
                # Combine context messages with kept regular messages
                kept_messages = context_messages + kept_regular_messages
                
                print(f"Rolling window: removed {messages_to_remove} messages, kept {len(kept_messages)} (target: {self.max_messages})")
                print(f"Preserved {len(context_messages)} context messages")
            else:
                kept_messages = messages  # No cleanup needed
                print(f"No rolling window cleanup needed: {regular_count} regular messages (limit: {self.max_messages})")
                print(f"Preserved {len(context_messages)} context messages")
            
            conversations[conversation_id]['messages'] = kept_messages
        
        # If we need to clean up based on token count
        elif token_cleanup_needed:
            # Separate context messages from regular messages
            context_messages = [msg for msg in messages if msg.get('is_context', False)]
            regular_messages = [msg for msg in messages if not msg.get('is_context', False)]
            
            # Remove oldest regular messages until we're under the token limit
            # Start by removing 25% of the regular messages
            regular_count = len(regular_messages)
            messages_to_remove = max(1, int(regular_count * 0.25))
            kept_regular_messages = regular_messages[messages_to_remove:]
            
            # Combine context messages with kept regular messages
            kept_messages = context_messages + kept_regular_messages
            conversations[conversation_id]['messages'] = kept_messages
            
            print(f"Token limit cleanup: removed {messages_to_remove} oldest messages to reduce token count")
            print(f"Token count was {conv_stats['total_tokens']}, limit is {max_tokens}")
            print(f"Preserved {len(context_messages)} context messages")
        
        # Save to storage
        from nicegui import app
        app.storage.user['conversations'] = conversations

        return True
    

    def process_message_for_storage(self, message):
        """Process message for storage - simple passthrough"""
        return message
    
    def get_conversation_size(self, conversation_id: str):
        """Get conversation size info with accurate token counting"""
        from .chat_handlers import get_conversation_storage
        conversations = get_conversation_storage()
        
        if conversation_id not in conversations:
            return {'total_tokens': 0, 'message_count': 0}
        
        messages = conversations[conversation_id]['messages']
        
        # Accurate token counting using tiktoken
        total_tokens = self._estimate_tokens_from_messages(messages)
        
        return {
            'total_tokens': total_tokens,
            'message_count': len(messages)
        }
    
    def _estimate_tokens_from_messages(self, messages):
        """Count tokens accurately from messages using tiktoken
        
        This uses OpenAI's tiktoken library to accurately count tokens
        the same way they are counted by the actual models.
        """
        try:
            # Get the cl100k_base encoder which is used by gpt-3.5-turbo and gpt-4
            enc = tiktoken.get_encoding("cl100k_base")
            
            # Following the OpenAI API chat format guidelines
            # https://github.com/openai/openai-cookbook/blob/main/examples/How_to_count_tokens_with_tiktoken.ipynb
            
            tokens_per_message = 3  # every message follows <im_start>{role/name}\n{content}<im_end>
            tokens_per_name = 1     # if there's a name, the role is omitted
            
            total_tokens = 0
            for msg in messages:
                total_tokens += tokens_per_message
                
                # Count tokens for each component of the message
                for key, value in msg.items():
                    if key == "tool_calls" and isinstance(value, list):
                        # Handle tool calls specially
                        for tool_call in value:
                            # Convert tool call to a string representation for tokenization
                            if isinstance(tool_call, dict):
                                # Serialize the tool call to JSON and count its tokens
                                tool_call_str = json.dumps(tool_call)
                                total_tokens += len(enc.encode(tool_call_str))
                    elif key != "_truncated":  # Skip internal metadata
                        if value is not None and value != "":
                            total_tokens += len(enc.encode(str(value)))
                            
                            # If it's a name, we have the additional tokens_per_name
                            if key == "name":
                                total_tokens += tokens_per_name
            
            # Every reply is primed with <im_start>assistant
            total_tokens += 3
            
            return total_tokens
            
        except Exception as e:
            # Fallback to the heuristic method if tiktoken fails
            print(f"Error using tiktoken: {e}. Falling back to heuristic method.")
            return self._estimate_tokens_heuristic(messages)
    
    def _estimate_tokens_heuristic(self, messages):
        """Fallback heuristic method for token estimation"""
        total_tokens = 0
        
        for msg in messages:
            content = msg.get('content', '') or ''
            role = msg.get('role', 'user')
            
            # Base token estimation for content
            content_tokens = self._estimate_content_tokens(content)
            total_tokens += content_tokens
            
            # Add overhead for message structure
            if role == 'system':
                total_tokens += 3  # System message overhead
            elif role == 'user':
                total_tokens += 4  # User message overhead
            elif role == 'assistant':
                total_tokens += 3  # Assistant message overhead
                
                # Add tokens for tool calls if present
                if 'tool_calls' in msg and msg['tool_calls']:
                    for tool_call in msg['tool_calls']:
                        total_tokens += 10  # Tool call overhead
                        function_name = tool_call.get('function', {}).get('name', '')
                        arguments = tool_call.get('function', {}).get('arguments', '')
                        total_tokens += self._estimate_content_tokens(arguments)
                        
            elif role == 'tool':
                total_tokens += 5  # Tool response overhead
        
        return total_tokens
        
    def _estimate_content_tokens(self, content):
        """Estimate tokens for content using improved heuristics"""
        if not content:
            return 0
            
        try:
            # Try to use tiktoken for accurate counting
            enc = tiktoken.get_encoding("cl100k_base")
            return len(enc.encode(str(content)))
        except Exception:
            # Fallback to heuristic if tiktoken fails
            # Count different types of content
            words = str(content).split()
            chars = len(str(content))
            
            # Heuristic based on content analysis:
            # - Code and technical content: ~2.5 chars per token
            # - Natural language: ~4 chars per token
            # - JSON/structured data: ~3 chars per token
            
            # Detect content type
            if self._is_code_like(str(content)):
                return max(chars // 2.5, len(words) * 0.8)  # Code is more token-dense
            elif self._is_json_like(str(content)):
                return max(chars // 3, len(words) * 0.9)  # JSON is structured
            else:
                return max(chars // 4, len(words) * 0.75)  # Natural language
    
    def _is_code_like(self, content):
        """Detect if content looks like code"""
        code_indicators = ['def ', 'function ', 'import ', 'from ', 'class ', '{', '}', '()', '=>', '===', '!==', 'return ', 'if ', 'for ', 'while ']
        return any(indicator in content for indicator in code_indicators)
    
    def _is_json_like(self, content):
        """Detect if content looks like JSON"""
        stripped = content.strip()
        return (stripped.startswith('{') and stripped.endswith('}')) or \
               (stripped.startswith('[') and stripped.endswith(']'))
    
    @property
    def settings(self):
        """Get settings with values from storage when available"""
        try:
            from nicegui import app
            stored_settings = app.storage.user.get('history-settings', {})
            
            # Start with defaults, then update with stored values
            settings = self._default_settings.copy()
            for key, value in stored_settings.items():
                if key in settings:
                    settings[key] = value
            
            return settings
        except Exception as e:
            return self._default_settings.copy()
    
    def get_settings(self):
        """Get settings dict"""
        return self.settings
        
    def reset_settings(self):
        """Reset all settings to defaults"""
        try:
            from nicegui import app
            app.storage.user['history-settings'] = self._default_settings.copy()
            return True
        except Exception as e:
            return False

# Global instance
history_manager = HistoryManager(max_messages=50)
