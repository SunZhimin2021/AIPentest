import uuid
import json
from typing import Optional, List, Dict, Any
from nicegui import ui, app
from .message_parser import parse_and_render_message
from .message_validator import validate_tool_call_sequence
from .history_manager import history_manager
from mcp_open_client.meta_tools.conversation_context import inject_context_to_messages, get_context_system_message
import asyncio
import json

def _safe_delete_spinner(spinner):
    """Safely delete spinner and return None"""
    if spinner is not None:
        try:
            spinner.delete()
        except (ValueError, AttributeError) as e:
            # Spinner already deleted or not in parent list
            pass
        except Exception as e:
            print(f"Unexpected error deleting spinner: {e}")
    return None

def _get_tool_choice_required():
    """Get tool_choice_required setting from user configuration"""
    user_settings = app.storage.user.get('user-settings', {})
    return user_settings.get('tool_choice_required', False)

def _final_tool_sequence_validation(messages, force_cleanup=False):
    """Final validation for tool sequences with optional force cleanup"""
    return validate_tool_call_sequence(messages)

def _rebuild_conversation_from_cleaned_messages(cleaned_messages):
    """Rebuild conversation storage from cleaned messages"""
    if not current_conversation_id:
        return
    
    conversations = get_conversation_storage()
    if current_conversation_id in conversations:
        # Convert cleaned API messages back to storage format
        storage_messages = []
        for msg in cleaned_messages:
            storage_msg = {
                'role': msg['role'],
                'content': msg['content'],
                'timestamp': str(uuid.uuid1().time)
            }
            
            if 'tool_calls' in msg:
                storage_msg['tool_calls'] = msg['tool_calls']
            if 'tool_call_id' in msg:
                storage_msg['tool_call_id'] = msg['tool_call_id']
                
            storage_messages.append(storage_msg)
        
        conversations[current_conversation_id]['messages'] = storage_messages
        conversations[current_conversation_id]['updated_at'] = str(uuid.uuid1().time)
        app.storage.user['conversations'] = conversations

# Global variables
current_conversation_id: Optional[str] = None
stats_update_callback: Optional[callable] = None
conversations_refresh_callback: Optional[callable] = None

# Generation control variables
generation_active = False
stop_generation = False

def set_stop_generation():
    """Set the stop generation flag"""
    global stop_generation
    stop_generation = True

def is_generation_stopped():
    """Check if generation should be stopped"""
    return stop_generation

def reset_generation_state():
    """Reset generation state"""
    global generation_active, stop_generation
    generation_active = False
    stop_generation = False

def get_conversation_storage() -> Dict[str, Any]:
    """Get or initialize conversation storage"""
    if 'conversations' not in app.storage.user:
        app.storage.user['conversations'] = {}
    return app.storage.user['conversations']

def create_new_conversation() -> str:
    """Create a new conversation and return its ID"""
    global current_conversation_id
    conversation_id = str(uuid.uuid4())
    conversations = get_conversation_storage()
    conversations[conversation_id] = {
        'id': conversation_id,
        'title': f'Conversation {len(conversations) + 1}',
        'messages': [],
        'created_at': str(uuid.uuid1().time),
        'updated_at': str(uuid.uuid1().time)
    }
    current_conversation_id = conversation_id
    app.storage.user['conversations'] = conversations
    return conversation_id

def load_conversation(conversation_id: str) -> None:
    """Load a specific conversation"""
    global current_conversation_id
    conversations = get_conversation_storage()
    if conversation_id in conversations:
        current_conversation_id = conversation_id
        # Update stats when conversation changes
        if stats_update_callback:
            stats_update_callback()

def get_current_conversation_id() -> Optional[str]:
    """Get the current conversation ID"""
    return current_conversation_id

def set_stats_update_callback(callback: callable) -> None:
    """Set the callback function to update stats"""
    global stats_update_callback
    stats_update_callback = callback

def set_conversations_refresh_callback(callback: callable) -> None:
    """Set the callback function to refresh conversations list"""
    global conversations_refresh_callback
    conversations_refresh_callback = callback

def get_messages(include_stats: bool = False) -> List[Dict[str, Any]] | Dict[str, Any]:
    """Get messages from current conversation
    
    Args:
        include_stats: If True, include conversation stats in the result
        
    Returns:
        List of messages or a dict with messages and stats
    """
    if not current_conversation_id:
        return [] if not include_stats else {'messages': [], 'stats': {'total_tokens': 0, 'total_chars': 0, 'message_count': 0}}
    
    conversations = get_conversation_storage()
    if current_conversation_id in conversations:
        messages = conversations[current_conversation_id]['messages'].copy()
        if include_stats:
            # Get conversation stats
            stats = history_manager.get_conversation_size(current_conversation_id)
            return {
                'messages': messages,
                'stats': stats
            }
        return messages
    return [] if not include_stats else {'messages': [], 'stats': {'total_tokens': 0, 'total_chars': 0, 'message_count': 0}}

def add_message(role: str, content: str, tool_calls: Optional[List[Dict[str, Any]]] = None, tool_call_id: Optional[str] = None, **metadata) -> None:
    """Add a message to the current conversation"""
    if not current_conversation_id:
        create_new_conversation()
    
    conversations = get_conversation_storage()
    if current_conversation_id in conversations:
        message = {
            'role': role,
            'content': content,
            'timestamp': str(uuid.uuid1().time)
        }
        
        # Add tool calls if present (for assistant messages)
        if tool_calls:
            message['tool_calls'] = tool_calls
            
        # Add tool call ID if present (for tool messages)
        if tool_call_id:
            message['tool_call_id'] = tool_call_id
        
        # Add any additional metadata
        for key, value in metadata.items():
            message[key] = value
        
        # Process message through history manager for size limits
        processed_message = history_manager.process_message_for_storage(message)
        
        # Only add message if it passed validation (not None)
        if processed_message is not None:
            
            conversations[current_conversation_id]['messages'].append(processed_message)
        else:
            
            return  # Exit early if message was rejected
        conversations[current_conversation_id]['updated_at'] = str(uuid.uuid1().time)
        app.storage.user['conversations'] = conversations
        
        # Check if conversation or total history needs cleanup BEFORE ensuring context position
        if history_manager.settings['auto_cleanup']:
            # Cleanup conversation if needed
            conv_cleanup = history_manager.cleanup_conversation_if_needed(current_conversation_id)
            if conv_cleanup:
                pass
        
        # Asegurar que el contexto esté como penúltimo mensaje AFTER cleanup
        from mcp_open_client.meta_tools.conversation_context import _ensure_context_as_penultimate
        _ensure_context_as_penultimate()
        
        # Log conversation size with accurate token count from tiktoken
        conv_size = history_manager.get_conversation_size(current_conversation_id)
            
            # Note: Global history cleanup disabled - only per-conversation limits apply
        
        # Update stats in UI if callback is set
        # This will use our enhanced token counting with tiktoken
        if stats_update_callback:
            stats_update_callback()
        
        # Check if conversation should be auto-renamed
        asyncio.create_task(_check_auto_rename_conversation())

def find_tool_response(tool_call_id: str) -> Optional[Dict[str, Any]]:
    """Find the tool response object for a given tool call ID"""
    messages = get_messages()
    for msg in messages:
        if (msg.get('role') == 'tool' and 
            msg.get('tool_call_id') == tool_call_id):
            # Check if this is a respond_to_user or notify_user tool call
            # If so, don't show the tool response since it's already shown as assistant message
            if msg.get('_is_respond_to_user') or msg.get('_is_notify_user'):
                return None
            return msg  # Return the complete tool result object
    return None

def render_message_to_ui(message: dict, message_container) -> None:
    """Render a single message to the UI"""
    role = message.get('role', 'user')
    content = message.get('content', '')
    tool_calls = message.get('tool_calls', [])
    tool_call_id = message.get('tool_call_id')
    was_truncated = message.get('_truncated', False)
    original_length = message.get('_original_length', 0)
    
    with message_container:
        if role == 'user':
            with ui.card().classes('user-message message-bubble mb-2 max-w-4xl').style('border-left: 4px solid #fbbf24; background: #1e293b; padding: 8px;') as user_card:
                parse_and_render_message(content, user_card)
                
                # Show truncation notice if message was truncated
                if was_truncated:
                    ui.label(f'⚠️ Message truncated (original: {original_length:,} chars)').classes('text-xs mt-2 italic').style('color: #fbbf24;')
                    truncated_color = current_colors.get('truncated_message', '#fbbf24')
                    ui.label(f'⚠️ Message truncated (original: {original_length:,} chars)').classes('text-xs mt-2 italic').style(f'color: {truncated_color};')
        elif role == 'assistant':
            # Only create container if there's content, tool calls, or truncation info to show
            if content or tool_calls or was_truncated:
                with ui.card().classes('assistant-message message-bubble mb-2 max-w-5xl').style('border-left: 4px solid #f87171; background: #374151; padding: 8px;') as bot_card:
                    if content:
                        parse_and_render_message(content, bot_card)
                    
                    # Show truncation notice if message was truncated
                    if was_truncated:
                        ui.label(f'⚠️ Message truncated (original: {original_length:,} chars)').classes('text-xs mt-2 italic').style('color: #fbbf24;')
                    
                    # Show tool calls if present with enhanced metadata display
                    if tool_calls:
                        ui.separator().style('margin: 0;')
                        from .message_parser import render_tool_call_with_metadata
                        
                        for i, tool_call in enumerate(tool_calls):
                            # Find corresponding tool response
                            tool_call_id = tool_call.get('id')
                            tool_response = find_tool_response(tool_call_id) if tool_call_id else None
                            
                            # Use enhanced rendering with metadata
                            render_tool_call_with_metadata(tool_call, tool_response, bot_card)
        elif role == 'tool':
            # Skip individual tool messages - they're now grouped with assistant messages
            pass
        elif role == 'system':
            # Skip system messages - they're only for LLM context, not for user display
            pass

def save_current_conversation() -> None:
    """Save current conversation to storage"""
    # This is automatically handled by NiceGUI's storage system
    pass

def clear_messages() -> None:
    """Clear messages from current conversation"""
    if not current_conversation_id:
        return
    
    conversations = get_conversation_storage()
    if current_conversation_id in conversations:
        conversations[current_conversation_id]['messages'] = []
        conversations[current_conversation_id]['updated_at'] = str(uuid.uuid1().time)
        app.storage.user['conversations'] = conversations

def get_all_conversations() -> Dict[str, Any]:
    """Get all conversations"""
    return get_conversation_storage()

def delete_conversation(conversation_id: str) -> None:
    """Delete a conversation"""
    global current_conversation_id
    conversations = get_conversation_storage()
    if conversation_id in conversations:
        del conversations[conversation_id]
        app.storage.user['conversations'] = conversations
        
        # If we deleted the current conversation, clear the current ID
        if current_conversation_id == conversation_id:
            current_conversation_id = None

# Global variable to track scroll debouncing
_scroll_timer = None

async def safe_scroll_to_bottom(scroll_area, delay=0.2):
    """Safely scroll to bottom with error handling and improved timing"""
    global _scroll_timer
    
    try:
        # Cancel any existing scroll timer to debounce multiple calls
        if _scroll_timer is not None:
            _scroll_timer.cancel()
            _scroll_timer = None
        
        # Try to use ui.timer first (when in UI context)
        try:
            def do_scroll():
                try:
                    # Execute the scroll
                    scroll_area.scroll_to(percent=1.0)
                except Exception as e:
                    pass
            
            _scroll_timer = ui.timer(delay, do_scroll, once=True)
            
        except Exception as timer_error:
            # Fallback: Use asyncio.sleep when ui.timer fails (no UI context)
            async def async_scroll():
                try:
                    await asyncio.sleep(delay)
                    scroll_area.scroll_to(percent=1.0)
                except Exception as e:
                    pass
            
            # Execute the async scroll without blocking
            asyncio.create_task(async_scroll())
        
    except Exception as e:
        pass

# render_tool_call_and_result function removed - functionality integrated into render_message_to_ui

async def send_message_to_mcp(message: str, server_name: str, chat_container, message_input):
    """Send message to MCP server and handle response"""
    from mcp_open_client.mcp_client import mcp_client_manager
    
    # Add user message to conversation
    add_message('user', message)
    
    # Clear input
    message_input.value = ''
    
    try:
        # Show spinner while waiting for response
        with chat_container:
            with ui.row().classes('w-full justify-start mb-2'):
                spinner_card = ui.card().classes('bg-gray-200 p-2')
                with spinner_card:
                    ui.spinner('dots', size='md')
                    ui.label('Thinking...')
        
        # Get available tools and resources
        tools = await mcp_client_manager.list_tools()
        resources = await mcp_client_manager.list_resources()
        
        # Prepare the context for the LLM
        # Get all messages from the current conversation
        all_messages = get_messages()
        
        # Inject context into messages if available
        messages_with_context = inject_context_to_messages(all_messages)
        
        context = {
            "message": message,
            "messages": messages_with_context,
            "tools": tools,
            "resources": resources
        }
        
        # Send the context to the LLM
        try:
            llm_response = await mcp_client_manager.generate_response(context)
            
            # Check if the LLM response contains tool calls
            if isinstance(llm_response, dict) and 'tool_calls' in llm_response:
                for tool_call in llm_response['tool_calls']:
                    tool_name = tool_call['function']['name']
                    tool_args = json.loads(tool_call['function']['arguments'])
                    
                    # Execute the tool call
                    tool_result = await mcp_client_manager.call_tool(tool_name, tool_args)
                    
                    # Add tool call to conversation
                    add_message('assistant', f"Calling tool: {tool_name}", tool_calls=[tool_call])
                    
                    # Add tool result to conversation
                    add_message('tool', json.dumps(tool_result, indent=2), tool_call_id=tool_call['id'])
                    
                    # Render tool call and result in UI
                    render_tool_call_and_result(chat_container, tool_call, tool_result)
                
                # Add final assistant response to conversation
                if 'content' in llm_response:
                    add_message('assistant', llm_response['content'])
                    with chat_container:
                        ui.markdown(f"**AI:** {llm_response['content']}").classes('bg-blue-100 p-2 rounded-lg mb-2 max-w-full overflow-wrap-anywhere')
            else:
                # Add assistant response to conversation
                add_message('assistant', llm_response)
                with chat_container:
                    ui.markdown(f"**AI:** {llm_response}").classes('bg-blue-100 p-2 rounded-lg mb-2 max-w-full overflow-wrap-anywhere')
        except Exception as llm_error:
            error_message = f'Error generating LLM response: {str(llm_error)}'
            add_message('assistant', error_message)
            with chat_container:
                ui.markdown(f"**Error:** {error_message}").classes('bg-red-100 p-2 rounded-lg mb-2 max-w-full overflow-wrap-anywhere')
        
        # Remove spinner
        spinner_card.delete()
        
        # Scroll to bottom after adding new content
        await safe_scroll_to_bottom(chat_container)
        
    except Exception as e:
        print(f"Error in send_message_to_mcp: {e}")
        # Remove spinner if error occurs
        if 'spinner_card' in locals():
            spinner_card.delete()
        
        error_message = f'Error communicating with MCP server: {str(e)}'
        add_message('assistant', error_message)

async def handle_send(input_field, message_container, api_client, scroll_area, send_button=None):
    """Handle sending a message asynchronously with stop generation support"""
    global generation_active, stop_generation
    
    if input_field.value and input_field.value.strip():
        message = input_field.value.strip()
        generation_active = True
        stop_generation = False
        
        # Ensure we have a current conversation
        if not get_current_conversation_id():
            create_new_conversation()
        
        # Add user message to conversation storage
        add_message('user', message)
        
        # Clear input
        input_field.value = ''
        
        # Re-render all messages to show the new user message
        message_container.clear()
        from .chat_interface import render_messages
        render_messages(message_container)
        
        # Auto-scroll to bottom after adding user message
        await safe_scroll_to_bottom(scroll_area, delay=0.15)
        
        # Send message to API and get response
        try:
            # Check if generation was stopped before starting
            if stop_generation:
                return
                
            # Show spinner while waiting for response
            with message_container:
                spinner = ui.spinner('dots', size='lg')
            # No need to scroll here, spinner is small
            
            # Get full conversation history for context
            conversation_messages = get_messages()
            
            # Simple validation: remove orphaned tool calls
            def clean_orphaned_tools(messages):
                """Remove orphaned tool calls - keep only complete sequences"""
                if not messages:
                    return []
                
                # Convert to API format first
                api_messages = []
                for msg in messages:
                    if not msg.get("content") and msg.get("role") != "assistant":
                        continue
                    
                    api_msg = {
                        "role": msg["role"],
                        "content": msg.get("content") or ""
                    }
                    
                    if msg["role"] == "assistant" and msg.get("tool_calls"):
                        api_msg["tool_calls"] = msg["tool_calls"]
                    elif msg["role"] == "tool" and msg.get("tool_call_id"):
                        api_msg["tool_call_id"] = msg["tool_call_id"]
                    
                    api_messages.append(api_msg)
                
                # Find tool calls that have responses
                tool_call_ids = set()
                tool_response_ids = set()
                
                for msg in api_messages:
                    if msg["role"] == "assistant" and "tool_calls" in msg:
                        for tc in msg["tool_calls"]:
                            tool_call_ids.add(tc["id"])
                    elif msg["role"] == "tool" and "tool_call_id" in msg:
                        tool_response_ids.add(msg["tool_call_id"])
                
                # Remove assistant messages with orphaned tool calls (except the last one)
                cleaned = []
                for i, msg in enumerate(api_messages):
                    if msg["role"] == "assistant" and "tool_calls" in msg:
                        # Check if all tool calls have responses
                        has_orphaned = any(tc["id"] not in tool_response_ids for tc in msg["tool_calls"])
                        is_last_message = i == len(api_messages) - 1
                        
                        if has_orphaned and not is_last_message:
                            # Remove tool_calls from orphaned assistant message
                            cleaned_msg = {"role": msg["role"], "content": msg["content"] or "[Tool call removed]"}
                            cleaned.append(cleaned_msg)
                        else:
                            cleaned.append(msg)
                    elif msg["role"] == "tool":
                        # Only keep tool responses that have corresponding calls
                        if msg["tool_call_id"] in tool_call_ids:
                            cleaned.append(msg)
                    else:
                        cleaned.append(msg)
                
                return cleaned
            
            # Clean conversation messages
            api_messages = clean_orphaned_tools(conversation_messages)
            
            # Get available MCP tools for tool calling
            from .handle_tool_call import get_available_tools, is_tool_call_response, extract_tool_calls, handle_tool_call
            available_tools = await get_available_tools()
            
            # Call LLM with tools if available, with enhanced error handling
            try:
                if available_tools:
                    # Check if tool_choice should be required
                    tool_choice_required = _get_tool_choice_required()
                    if tool_choice_required:
                        response = await api_client.chat_completion(api_messages, tools=available_tools, tool_choice="required")
                    else:
                        response = await api_client.chat_completion(api_messages, tools=available_tools)
                else:
                    response = await api_client.chat_completion(api_messages)
            except Exception as api_error:
                error_str = str(api_error)
                
                # Check if it's a tool sequence error
                if ("toolresult" in error_str.lower() or
                    "tool_use" in error_str.lower() or
                    "unexpected" in error_str.lower()):
                    
                    print(f"Tool sequence error detected: {error_str}")
                    
                    # Fallback: Remove all tool calls and try again with clean messages
                    fallback_messages = []
                    for msg in api_messages:
                        if msg["role"] == "tool":
                            continue  # Skip all tool messages
                        elif msg["role"] == "assistant" and "tool_calls" in msg:
                            # Convert to regular assistant message
                            fallback_msg = {
                                "role": "assistant",
                                "content": msg.get("content") or "[Previous tool interaction]"
                            }
                            fallback_messages.append(fallback_msg)
                        else:
                            fallback_messages.append(msg)
            
                    
                    try:
                        # Validate fallback messages but preserve any remaining tool calls
                        fallback_messages = _final_tool_sequence_validation(fallback_messages, force_cleanup=False)
                        
                        if available_tools:
                            response = await api_client.chat_completion(fallback_messages, tools=available_tools)
                        else:
                            response = await api_client.chat_completion(fallback_messages)
                    except Exception as fallback_error:
                        print(f"Fallback also failed: {fallback_error}")
                        raise fallback_error
                else:
                    # Different type of error, re-raise
                    raise api_error
            
            # Check if response contains tool calls
            if is_tool_call_response(response):
                # Handle tool calls
                tool_calls = extract_tool_calls(response)
                
                # FILTRO ESPECIAL: Detectar si hay llamadas a respond_to_user o notify_user
                respond_to_user_call = None
                notify_user_calls = []
                for tool_call in tool_calls:
                    if tool_call.get('function', {}).get('name') == 'meta-respond_to_user':
                        respond_to_user_call = tool_call
                        break  # Solo puede haber uno de estos y termina la ejecución
                    elif tool_call.get('function', {}).get('name') == 'meta-notify_user':
                        notify_user_calls.append(tool_call)  # Puede haber múltiples
                
                if respond_to_user_call:
                    # CASO ESPECIAL: respond_to_user se trata como respuesta directa del asistente
                    # NO se agrega como tool call al historial, se convierte directamente en mensaje del asistente
                    try:
                        tool_result = await handle_tool_call(respond_to_user_call)
                        # Agregar directamente como mensaje del asistente (sin tool call en historial)
                        add_message('assistant', tool_result['content'])
                        
                        # Update UI
                        message_container.clear()
                        from .chat_interface import render_messages
                        render_messages(message_container)
                        await safe_scroll_to_bottom(scroll_area, delay=0.1)
                        
                        # TERMINAR AQUÍ - no continuar procesando ni enviar de vuelta al LLM
                        return
                        
                    except Exception as e:
                        print(f"Error processing respond_to_user: {e}")
                        # Fallback: agregar mensaje de error
                        add_message('assistant', f"Error generating response: {str(e)}")
                        message_container.clear()
                        from .chat_interface import render_messages
                        render_messages(message_container)
                        await safe_scroll_to_bottom(scroll_area, delay=0.1)
                        return
                
                if notify_user_calls:
                    # CASO ESPECIAL: Procesar TODAS las llamadas a notify_user
                    try:
                        # PRIMERO: Agregar el assistant message original solo si tiene tool calls no-meta o contenido relevante
                        assistant_message = response['choices'][0]['message']
                        original_tool_calls = assistant_message.get('tool_calls', [])
                        filtered_tool_calls = [tc for tc in original_tool_calls if tc.get('function', {}).get('name') not in ['meta-respond_to_user', 'meta-notify_user']]
                        original_content = (assistant_message.get('content') or '').strip()
                        
                        # Solo agregar el mensaje original si tiene tool calls no-meta y contenido
                        if filtered_tool_calls and original_content:
                            add_message('assistant', original_content, tool_calls=filtered_tool_calls)
                        
                        # SEGUNDO: Procesar cada notify_user secuencialmente
                        for notify_call in notify_user_calls:
                            tool_result = await handle_tool_call(notify_call)
                            
                            # Agregar mensaje del asistente con formato visual para el usuario
                            notification_content = tool_result.get('_notification_content', tool_result['content'])
                            add_message('assistant', notification_content)
                            
                            # Agregar confirmación del sistema para que el LLM sepa que la notificación fue exitosa
                            add_message('system', 'Has notificado exitosamente al usuario. No necesitas volver a notificar lo mismo. Puedes usar respond_to_user para finalizar o continuar con otras tareas.')
                        
                        # Update UI
                        message_container.clear()
                        from .chat_interface import render_messages
                        render_messages(message_container)
                        await safe_scroll_to_bottom(scroll_area, delay=0.1)
                        
                        # Procesar tool calls restantes (excluyendo notify_user)
                        remaining_tool_calls = [tc for tc in tool_calls if tc.get('function', {}).get('name') != 'meta-notify_user']
                        tool_calls = remaining_tool_calls
                        
                    except Exception as e:
                        print(f"Error processing notify_user: {e}")
                        # Continuar con otros tool calls en caso de error
                        tool_calls = [tc for tc in tool_calls if tc.get('function', {}).get('name') != 'meta-notify_user']
                        # No hacer return aquí - continuar el flujo incluso si hay error
                
                # Verificar si quedan tool calls para procesar
                if not tool_calls:
                    # Si no quedan tool calls (solo había notify_user), continuar el bucle para que el LLM pueda seguir trabajando
                    # Las notificaciones ya se mostraron al usuario, ahora el LLM puede continuar
                    # Update UI
                    message_container.clear()
                    from .chat_interface import render_messages
                    render_messages(message_container)
                    await safe_scroll_to_bottom(scroll_area, delay=0.1)
                    # Continuar el bucle naturalmente - no hacer return ni break
                else:
                    # CASO NORMAL: Procesar tool calls normales (no respond_to_user ni notify_user)
                    # Agregar el mensaje del asistente original al historial AHORA (después de procesar meta tools)
                    assistant_message = response['choices'][0]['message']
                
                # FILTRAR tool calls para la UI (excluir respond_to_user y notify_user)
                original_tool_calls = assistant_message.get('tool_calls', [])
                filtered_tool_calls = []
                for tool_call in original_tool_calls:
                    tool_name = tool_call.get('function', {}).get('name')
                    if tool_name not in ['meta-respond_to_user', 'meta-notify_user']:
                        filtered_tool_calls.append(tool_call)
                
                # Agregar mensaje del asistente al historial (con tool calls filtrados para UI)
                add_message('assistant', assistant_message.get('content', ''), tool_calls=filtered_tool_calls)
                
                # Update UI immediately after adding assistant message with tool calls
                message_container.clear()
                from .chat_interface import render_messages
                render_messages(message_container)
                await safe_scroll_to_bottom(scroll_area, delay=0.1)
                
                # Process tool calls - parallel execution for better performance
                tool_results = []
                
                # Create tasks for parallel execution
                async def process_single_tool_call(tool_call):
                    try:
                        return await handle_tool_call(tool_call)
                    except Exception as e:
                        # Return error result in consistent format
                        return {
                            'tool_call_id': tool_call['id'],
                            'content': f"Error executing tool '{tool_call.get('function', {}).get('name', 'unknown')}': {str(e)}",
                            '_is_error': True
                        }
                
                # Execute all tool calls in parallel
                tool_results = await asyncio.gather(*[process_single_tool_call(tc) for tc in tool_calls])
                
                # Process results sequentially for UI updates
                for i, (tool_call, tool_result) in enumerate(zip(tool_calls, tool_results)):
                    try:
                        # Add tool result to conversation storage with metadata
                        tool_metadata = tool_result.get('_tool_metadata', {})
                        add_message('tool', tool_result['content'], tool_call_id=tool_result['tool_call_id'], **tool_metadata)
                        
                        # ESPECIAL: Si es notify_user, agregar mensaje del asistente con el contenido de notificación
                        if tool_result.get('_is_notify_user', False):
                            notification_content = tool_result.get('_notification_content', '')
                            if notification_content:
                                # Agregar mensaje del asistente con el contenido formateado de la notificación
                                add_message('assistant', notification_content)
                        
                        # Verify the tool result was added correctly
                        messages_after_add = get_messages()
                        tool_msg_found = False
                        for msg in messages_after_add:
                            if msg.get('role') == 'tool' and msg.get('tool_call_id') == tool_result['tool_call_id']:
                                tool_msg_found = True
                                
                                break
                        if not tool_msg_found:
                            pass
                        # Update UI immediately after each tool result
                        message_container.clear()
                        render_messages(message_container)
                        await safe_scroll_to_bottom(scroll_area, delay=0.1)
                    
                    except Exception as e:
                        # Fallback error handling for UI operations
                        print(f"Error processing tool result: {str(e)}")
                        
                        # Handle error results (errors are already caught in parallel execution)
                        if tool_result.get('_is_error', False):
                            print(f"Tool call error: {tool_result['content']}")
                
                # Note: No need to add to api_messages here since they're already
                # added to conversation storage via add_message() calls above.
                # The next API call will rebuild api_messages from the updated conversation.
                
                # Continue processing until no more tool calls
                while True:
                    # Check if generation was stopped
                    if stop_generation:
                        print("Generation stopped by user")
                        # Clean up any orphaned tool calls before breaking
                        conversation_messages = get_messages()
                        api_messages = []
                        for msg in conversation_messages:
                            api_msg = {
                                "role": msg["role"],
                                "content": msg["content"]
                            }
                            
                            # Include tool_calls for assistant messages
                            if msg["role"] == "assistant" and "tool_calls" in msg:
                                api_msg["tool_calls"] = msg["tool_calls"]
                            
                            # Include tool_call_id for tool messages
                            if msg["role"] == "tool" and "tool_call_id" in msg:
                                api_msg["tool_call_id"] = msg["tool_call_id"]
                            
                            api_messages.append(api_msg)
                        
                        # Apply final validation to clean up orphaned tool calls (STOP PRESSED)
                        cleaned_messages = _final_tool_sequence_validation(api_messages, force_cleanup=True)
                        
                        # If orphaned tool calls were found, update the conversation
                        if len(cleaned_messages) != len(api_messages):
                            
                            # Rebuild conversation from cleaned messages
                            _rebuild_conversation_from_cleaned_messages(cleaned_messages)
                        
                        break
                        
                    # Rebuild api_messages from updated conversation for next API call
                    conversation_messages = get_messages()
                    
        
                    api_messages = []
                    for i, msg in enumerate(conversation_messages):
                        api_msg = {
                            "role": msg["role"],
                            "content": msg["content"]
                        }
                        
                        # Include tool_calls for assistant messages
                        if msg["role"] == "assistant" and "tool_calls" in msg:
                            api_msg["tool_calls"] = msg["tool_calls"]
     
                        
                        # Include tool_call_id for tool messages
                        if msg["role"] == "tool" and "tool_call_id" in msg:
                            api_msg["tool_call_id"] = msg["tool_call_id"]
                       
                        api_messages.append(api_msg)
                    
                    
                    
                    # Clean orphaned tools before API call
                    api_messages = clean_orphaned_tools(get_messages())
                    
                    
                    
                    # Check again before making API call
                    if stop_generation:
                        print("Generation stopped by user before API call")
                        # Clean up any orphaned tool calls before breaking (STOP PRESSED)
                        cleaned_messages = _final_tool_sequence_validation(api_messages, force_cleanup=True)
                        if len(cleaned_messages) != len(api_messages):
                            
                            _rebuild_conversation_from_cleaned_messages(cleaned_messages)
                        break
                    
                    # Show spinner for subsequent API calls
                    with message_container:
                        spinner = ui.spinner('dots', size='lg')
                    
                    # Make API call with stop check
                    try:
                        # Clean orphaned tools before API call
                        api_messages = clean_orphaned_tools(get_messages())
                        
                        if available_tools:
                            # Check if tool_choice should be required
                            tool_choice_required = _get_tool_choice_required()
                            if tool_choice_required:
                                response = await api_client.chat_completion(api_messages, tools=available_tools, tool_choice="required")
                            else:
                                response = await api_client.chat_completion(api_messages, tools=available_tools)
                        else:
                            response = await api_client.chat_completion(api_messages)
                        
                        # Remove spinner after API call safely
                        spinner = _safe_delete_spinner(spinner)
                        
                        # Check if stopped during API call
                        if stop_generation:
                            print("Generation stopped during API call")
                            break
                            
                        # Process response normally
                        if response and 'choices' in response and response['choices'] and 'message' in response['choices'][0]:
                            # Extract content and tool_calls from the correct structure
                            assistant_message = response['choices'][0]['message']
                            content = assistant_message.get('content', '')
                            tool_calls = assistant_message.get('tool_calls', [])
                            
                            # FILTRAR tool calls para excluir respond_to_user y notify_user de la UI (bucle)
                            filtered_tool_calls_loop = []
                            for tool_call in tool_calls:
                                tool_name = tool_call.get('function', {}).get('name')
                                if tool_name not in ['meta-respond_to_user', 'meta-notify_user']:
                                    filtered_tool_calls_loop.append(tool_call)
                            
                            # Add assistant response
                            add_message('assistant', content, filtered_tool_calls_loop)
                            
                            # Re-render messages to show assistant response
                            message_container.clear()
                            from .chat_interface import render_messages
                            render_messages(message_container)
                            await safe_scroll_to_bottom(scroll_area, delay=0.1)
                            
                            # If no tool calls, we're done
                            if not tool_calls:
                                break
                            
                            # Execute tool calls if present
                            
                            # FILTRO ESPECIAL: Detectar si hay llamada a respond_to_user o notify_user en el bucle
                            respond_to_user_call_in_loop = None
                            notify_user_call_in_loop = None
                            for tool_call in tool_calls:
                                tool_name = tool_call.get('function', {}).get('name')
                                if tool_name == 'meta-respond_to_user':
                                    respond_to_user_call_in_loop = tool_call
                                    break
                                elif tool_name == 'meta-notify_user':
                                    notify_user_call_in_loop = tool_call
                                    break
                            
                            if respond_to_user_call_in_loop:
                                # CASO ESPECIAL EN BUCLE: respond_to_user se trata como respuesta directa
                                try:
                                    tool_result = await handle_tool_call(respond_to_user_call_in_loop)
                                    # Agregar directamente como mensaje del asistente (sin tool call en historial)
                                    add_message('assistant', tool_result['content'])
                                    
                                    # Update UI
                                    message_container.clear()
                                    from .chat_interface import render_messages
                                    render_messages(message_container)
                                    await safe_scroll_to_bottom(scroll_area, delay=0.1)
                                    
                                    # TERMINAR BUCLE - no continuar procesando
                                    break
                                    
                                except Exception as e:
                                    print(f"Error processing respond_to_user in loop: {e}")
                                    # Fallback: agregar mensaje de error y terminar
                                    add_message('assistant', f"Error generating response: {str(e)}")
                                    message_container.clear()
                                    from .chat_interface import render_messages
                                    render_messages(message_container)
                                    await safe_scroll_to_bottom(scroll_area, delay=0.1)
                                    break
                            
                            if notify_user_call_in_loop:
                                # CASO ESPECIAL EN BUCLE: notify_user se procesa como notificación sin mostrar tool call EN LA UI
                                # PERO SÍ se agrega al historial para que el LLM vea el resultado
                                try:
                                    tool_result = await handle_tool_call(notify_user_call_in_loop)
                                    
                                    # Agregar mensaje del asistente con formato visual para el usuario
                                    notification_content = tool_result.get('_notification_content', tool_result['content'])
                                    add_message('assistant', notification_content)
                                    
                                    # Agregar confirmación del sistema para que el LLM sepa que la notificación fue exitosa
                                    add_message('system', 'Has notificado exitosamente al usuario. No necesitas volver a notificar lo mismo. Puedes usar respond_to_user para finalizar o continuar con otras tareas.')
                                    
                                    # Update UI
                                    message_container.clear()
                                    from .chat_interface import render_messages
                                    render_messages(message_container)
                                    await safe_scroll_to_bottom(scroll_area, delay=0.1)
                                    
                                    # NO TERMINAR BUCLE - notify_user no termina el flujo, continuar procesando otros tool calls
                                    # Procesar tool calls restantes (excluyendo notify_user)
                                    remaining_tool_calls_loop = [tc for tc in tool_calls if tc.get('function', {}).get('name') != 'meta-notify_user']
                                    if not remaining_tool_calls_loop:
                                        # Si solo había notify_user, continuar el bucle - el LLM ahora ve el tool result
                                        continue
                                    # Si hay más tool calls, continuar con el procesamiento normal
                                    tool_calls = remaining_tool_calls_loop
                                    
                                except Exception as e:
                                    print(f"Error processing notify_user in loop: {e}")
                                    # Continuar con otros tool calls en caso de error
                                    tool_calls = [tc for tc in tool_calls if tc.get('function', {}).get('name') != 'meta-notify_user']
                                    if not tool_calls:
                                        continue
                           
                            # CASO NORMAL: Procesar tool calls normales (no respond_to_user ni notify_user)
                            tool_results = []
                            for tool_call in tool_calls:
                                try:
                                    tool_result = await handle_tool_call(tool_call)
                                    tool_results.append(tool_result)
                                    
                                    # Add tool result to conversation storage
                                    add_message('tool', tool_result['content'], tool_call_id=tool_result['tool_call_id'])
                                    
                                    # ESPECIAL: Si es notify_user, agregar mensaje del asistente con el contenido de notificación
                                    if tool_result.get('_is_notify_user', False):
                                        notification_content = tool_result.get('_notification_content', '')
                                        if notification_content:
                                            # Agregar mensaje del asistente con el contenido formateado de la notificación
                                            add_message('assistant', notification_content)
                                    
                                    # Update UI immediately after each tool result
                                    message_container.clear()
                                    from .chat_interface import render_messages
                                    render_messages(message_container)
                                    await safe_scroll_to_bottom(scroll_area, delay=0.1)
                                    
                                except Exception as e:
                                    # Handle tool call failure - add error message as tool result
                                    error_message = f"Error executing tool '{tool_call.get('function', {}).get('name', 'unknown')}': {str(e)}"
                                    error_result = {
                                        'tool_call_id': tool_call['id'],
                                        'content': error_message
                                    }
                                    tool_results.append(error_result)
                                    
                                    # Add error result to conversation storage
                                    add_message('tool', error_message, tool_call_id=tool_call['id'])
                                    
                                    # Update UI immediately after error
                                    message_container.clear()
                                    from .chat_interface import render_messages
                                    render_messages(message_container)
                                    await safe_scroll_to_bottom(scroll_area, delay=0.1)
                                    
                                    print(f"Tool call error: {error_message}")
                            
                            # Continue to next iteration to process tool results
                            continue
                                
                        else:
                            print("No valid response received")
                            
                            break
                            
                    except Exception as api_error:
                        print(f"API call error: {api_error}")
                        # Remove spinner on error
                        if 'spinner' in locals() and spinner is not None:
                            spinner.delete()
                        add_message('assistant', f'Error: {str(api_error)}')
                        message_container.clear()
                        from .chat_interface import render_messages
                        render_messages(message_container)
                        break
            else:
               # Handle normal response (no tool calls) from first API call
               if response and 'choices' in response and response['choices'] and 'message' in response['choices'][0]:
                   # Extract content from the correct structure
                   assistant_message = response['choices'][0]['message']
                   content = assistant_message.get('content', '')
                   
                   # Add assistant response
                   add_message('assistant', content)
                   
                   # Re-render messages to show assistant response
                   message_container.clear()
                   from .chat_interface import render_messages
                   render_messages(message_container)
                   await safe_scroll_to_bottom(scroll_area, delay=0.1)
               else:
                   print("No valid response received from first API call")
       
        except Exception as e:
            # Remove spinner on error safely
            spinner = _safe_delete_spinner(spinner if 'spinner' in locals() else None)
            
            error_message = f'Error sending message: {str(e)}'
            add_message('assistant', error_message)
            
            # Re-render messages to show error
            message_container.clear()
            from .chat_interface import render_messages
            render_messages(message_container)
            
        finally:
            # Reset generation state
            generation_active = False
            stop_generation = False
            
            # Remove spinner if it still exists safely
            spinner = _safe_delete_spinner(spinner if 'spinner' in locals() else None)
            
            # Update stats after completion
            if stats_update_callback:
                stats_update_callback()
            
            # Check for auto-rename after successful completion
            try:
                await _check_auto_rename_conversation()
            except Exception as rename_error:
                print(f"Auto-rename error: {rename_error}")
 

async def _check_auto_rename_conversation():
    """Check if current conversation should be auto-renamed and perform the rename."""
    global current_conversation_id
    
    if not current_conversation_id:
        return
    
    try:
        from .conversation_title_manager import get_title_manager
        
        conversations = get_conversation_storage()
        if current_conversation_id not in conversations:
            return
        
        conversation = conversations[current_conversation_id]
        messages = conversation.get('messages', [])
        
        title_manager = get_title_manager()
        should_rename = title_manager.should_auto_rename(messages)
        
        if should_rename:
            current_title = conversation.get('title', '')
            
            if current_title.startswith('Conversation'):
                new_title = await title_manager.generate_conversation_title(messages)
                
                conversations[current_conversation_id]['title'] = new_title
                conversations[current_conversation_id]['updated_at'] = str(uuid.uuid1().time)
                app.storage.user['conversations'] = conversations
                
                # Refresh conversations list and force UI update
                try:
                    from .conversation_manager import conversation_manager
                    conversation_manager.refresh_conversations_list()
                    
                    # Also refresh the chat UI to update any title display
                    conversation_manager.refresh_chat_ui()
                    
                    # Force a complete UI update
                    ui.update()
                    
                    print(f"Auto-rename: Successfully updated UI for new title '{new_title}'")
                except Exception as refresh_error:
                    print(f"Warning: Could not refresh conversations list: {refresh_error}")
    
    except Exception as e:
        print(f"Error in auto-rename: {e}")


def rename_conversation(conversation_id: str, new_title: str) -> bool:
    """Manually rename a conversation.
    
    Args:
        conversation_id: ID of the conversation to rename
        new_title: New title for the conversation
        
    Returns:
        True if rename was successful, False otherwise
    """
    try:
        from .conversation_title_manager import get_title_manager
        
        conversations = get_conversation_storage()
        if conversation_id not in conversations:
            return False
        
        # Validate the new title
        title_manager = get_title_manager()
        validated_title = title_manager.validate_title(new_title)
        
        # Update conversation title
        conversations[conversation_id]['title'] = validated_title
        conversations[conversation_id]['updated_at'] = str(uuid.uuid1().time)
        app.storage.user['conversations'] = conversations
        
        # Refresh conversations list in UI
        try:
            from .conversation_manager import conversation_manager
            conversation_manager.refresh_conversations_list()
        except Exception as e:
            print(f"Error refreshing conversations list: {e}")
            # Don't force reload - just skip the refresh
            pass
        
        return True
    
    except Exception as e:
        print(f"Error renaming conversation: {str(e)}")
        return False

