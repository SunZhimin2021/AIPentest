"""
Meta tool para gestionar el contexto de conversación.

Este módulo proporciona herramientas para mantener un contexto persistente
en las conversaciones que siempre se presenta justo antes del mensaje del usuario.
"""

import logging
import uuid
import json
from typing import Dict, Any, Optional, List
from nicegui import ui, app
from mcp_open_client.meta_tools.meta_tool import meta_tool

logger = logging.getLogger(__name__)

def _get_current_context() -> str:
    """Obtiene el contexto actual de la conversación desde el historial de mensajes."""
    from mcp_open_client.ui.chat_handlers import get_conversation_storage, get_current_conversation_id
    
    conversation_id = get_current_conversation_id()
    if not conversation_id:
        return ""
    
    conversations = get_conversation_storage()
    if conversation_id not in conversations:
        return ""
    
    messages = conversations[conversation_id]['messages']
    
    # Buscar el mensaje de contexto (sistema que contiene "CONTEXTO DE LA CONVERSACIÓN:")
    for msg in messages:
        if (msg.get('role') == 'system' and 
            msg.get('content', '').startswith('CONTEXTO DE LA CONVERSACIÓN:')):
            # Extraer solo el contenido del contexto, sin el prefijo
            content = msg.get('content', '')
            if content.startswith('CONTEXTO DE LA CONVERSACIÓN:\n\n'):
                return content[len('CONTEXTO DE LA CONVERSACIÓN:\n\n'):]
    
    return ""

def _set_context(context: str) -> None:
    """Establece el contexto de la conversación en el historial de mensajes."""
    from mcp_open_client.ui.chat_handlers import get_conversation_storage, get_current_conversation_id
    
    conversation_id = get_current_conversation_id()
    if not conversation_id:
        return
    
    conversations = get_conversation_storage()
    if conversation_id not in conversations:
        return
    
    messages = conversations[conversation_id]['messages']
    
    # Remover mensaje de contexto existente
    messages[:] = [msg for msg in messages if not (
        msg.get('role') == 'system' and 
        msg.get('content', '').startswith('CONTEXTO DE LA CONVERSACIÓN:')
    )]
    print(f"DEBUG _set_context: conversation_id={conversation_id}, context length={len(context) if context else 0}")
    
    # Si hay contexto, insertarlo como penúltimo mensaje
    if context and context.strip():
        context_message = {
            'role': 'system',
            'content': f'CONTEXTO DE LA CONVERSACIÓN:\n\n{context}',
            'timestamp': str(uuid.uuid1().time),
            'is_context': True
        }
        
        # Insertar antes del último mensaje (si existe)
        if messages:
            messages.insert(-1, context_message)
        else:
            messages.append(context_message)
            
        # Guardar cambios en el storage
        conversations[conversation_id]['updated_at'] = str(uuid.uuid1().time)
        app.storage.user['conversations'] = conversations

def _clear_context() -> None:
    """Limpia el contexto de la conversación del historial de mensajes."""
    from mcp_open_client.ui.chat_handlers import get_conversation_storage, get_current_conversation_id
    
    conversation_id = get_current_conversation_id()
    if not conversation_id:
        return
    
    conversations = get_conversation_storage()
    if conversation_id not in conversations:
        return
    
    messages = conversations[conversation_id]['messages']
    
    # Remover todos los mensajes de contexto
    messages[:] = [msg for msg in messages if not (
        msg.get('role') == 'system' and 
        msg.get('content', '').startswith('CONTEXTO DE LA CONVERSACIÓN:')
    )]
    
    # Guardar cambios en el storage
    conversations[conversation_id]['updated_at'] = str(uuid.uuid1().time)
    app.storage.user['conversations'] = conversations

def _get_context_items() -> List[Dict[str, Any]]:
    """Obtiene los elementos del contexto como lista."""
    context_content = _get_current_context()
    if not context_content:
        return []
    
    try:
        # Intentar parsear como JSON
        parsed = json.loads(context_content)
        
        # Verificar si es el nuevo formato con wrapper
        if isinstance(parsed, dict) and parsed.get("_mcp_context_format") == "elements_v1":
            return parsed.get("items", [])
        
        # Si es una lista directa (formato anterior), devolverla
        if isinstance(parsed, list):
            return parsed
    except (json.JSONDecodeError, ValueError):
        pass
    
    # Si no es JSON válido, ignorar el contexto anterior
    return []

def _set_context_items(items: List[Dict[str, Any]]) -> None:
    """Establece los elementos del contexto."""
    print(f"DEBUG _set_context_items: items count={len(items) if items else 0}")
    if not items:
        _clear_context()
        return
    
    # Crear wrapper con metadatos para distinguir el nuevo formato
    wrapper = {
        "_mcp_context_format": "elements_v1",
        "items": items
    }
    context_json = json.dumps(wrapper, ensure_ascii=False, indent=2)
    _set_context(context_json)

def _format_context_for_display(items: List[Dict[str, Any]]) -> str:
    """Formatea los elementos del contexto para mostrar al LLM."""
    if not items:
        return ""
    
    formatted_items = []
    for i, item in enumerate(items, 1):
        content = item.get('content', '')
        item_id = item.get('id', f'item-{i}')
        formatted_items.append(f"{i}. [{item_id}] {content}")
    
    return "\n".join(formatted_items)

def _ensure_context_as_penultimate(items_override: List[Dict[str, Any]] = None) -> None:
    """Asegura que el contexto esté siempre como penúltimo mensaje en la conversación."""
    from mcp_open_client.ui.chat_handlers import get_conversation_storage, get_current_conversation_id
    
    conversation_id = get_current_conversation_id()
    if not conversation_id:
        return
    
    conversations = get_conversation_storage()
    if conversation_id not in conversations:
        return
    
    messages = conversations[conversation_id]['messages']
    items = items_override if items_override is not None else _get_context_items()
    
    
    # Buscar mensaje de contexto existente
    existing_context_msg = None
    for msg in messages:
        if (msg.get('role') == 'system' and 
            msg.get('content', '').startswith('CONTEXTO DE LA CONVERSACIÓN:')):
            existing_context_msg = msg
            break
    
    # Si hay elementos de contexto, actualizar/crear el mensaje
    if items and messages:
        # Remover mensaje de contexto existente solo si vamos a reemplazarlo
        messages[:] = [msg for msg in messages if not (
            msg.get('role') == 'system' and 
            msg.get('content', '').startswith('CONTEXTO DE LA CONVERSACIÓN:')
        )]
        
        formatted_context = _format_context_for_display(items)
        
        # Guardar tanto el JSON de elementos como el texto formateado
        items_json = json.dumps({
            "_mcp_context_format": "elements_v1",
            "items": items
        })
        
        context_message = {
            'role': 'system',
            'content': f'CONTEXTO DE LA CONVERSACIÓN:\n\n{items_json}',
            'timestamp': str(uuid.uuid1().time),
            'is_context': True
        }
        
        # Insertar como penúltimo mensaje
        messages.insert(-1, context_message)
        
        # Guardar cambios en el storage
        conversations[conversation_id]['updated_at'] = str(uuid.uuid1().time)
        app.storage.user['conversations'] = conversations
    elif existing_context_msg:
        # Si no hay items pero existe un mensaje de contexto, preservarlo
        pass
        # El mensaje ya está en su lugar, no necesitamos hacer nada

def _update_persistent_context_message() -> None:
    """Actualiza o crea el mensaje de contexto persistente en la conversación actual."""
    from mcp_open_client.ui.chat_handlers import get_conversation_storage, get_current_conversation_id
    
    conversation_id = get_current_conversation_id()
    if not conversation_id:
        return
    
    conversations = get_conversation_storage()
    if conversation_id not in conversations:
        return
    
    messages = conversations[conversation_id]['messages']
    context_content = _get_current_context()
    
    # Buscar si ya existe un mensaje de contexto
    context_message_index = None
    for i, msg in enumerate(messages):
        if msg.get('role') == 'system' and msg.get('content', '').startswith('CONTEXTO DE LA CONVERSACIÓN:'):
            context_message_index = i
            break
    
    if context_content and context_content.strip():
        # Hay contexto, crear/actualizar el mensaje
        context_message = {
            'role': 'system',
            'content': f'CONTEXTO DE LA CONVERSACIÓN:\n\n{context_content}',
            'timestamp': str(uuid.uuid1().time),
            'is_context': True  # Marcador especial para identificar este mensaje
        }
        
        if context_message_index is not None:
            # Actualizar mensaje existente
            messages[context_message_index] = context_message
        else:
            # Agregar nuevo mensaje al principio (después del último mensaje del usuario)
            _insert_context_message_before_last_user(messages, context_message)
    else:
        # No hay contexto, eliminar el mensaje si existe
        if context_message_index is not None:
            messages.pop(context_message_index)
    
    # Guardar cambios
    conversations[conversation_id]['updated_at'] = str(uuid.uuid1().time)
    app.storage.user['conversations'] = conversations

def _insert_context_message_before_last_user(messages, context_message):
    """Inserta el mensaje de contexto antes del último mensaje del usuario."""
    # Buscar el último mensaje del usuario
    user_indices = [i for i, msg in enumerate(messages) if msg.get('role') == 'user']
    
    if user_indices:
        # Insertar antes del último mensaje del usuario
        last_user_index = user_indices[-1]
        messages.insert(last_user_index, context_message)
    else:
        # Si no hay mensajes de usuario, insertar al final
        messages.append(context_message)



# Función para obtener el mensaje de contexto formateado para el sistema
def get_context_system_message() -> Optional[Dict[str, str]]:
    """
    Obtiene el mensaje de contexto formateado como mensaje del sistema.
    Si no hay contexto, devuelve None.
    
    Returns:
        Dict o None: Mensaje del sistema con el contexto o None si no hay contexto
    """
    items = _get_context_items()
    if not items:
        return None
    
    formatted_context = _format_context_for_display(items)
    return {
        "role": "system",
        "content": f"CONTEXTO DE LA CONVERSACIÓN:\n\n{formatted_context}"
    }

# Función para inyectar el contexto en una lista de mensajes
def inject_context_to_messages(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    El contexto ahora se maneja directamente en el historial de mensajes.
    Esta función simplemente asegura que el contexto esté como penúltimo mensaje
    y retorna los mensajes tal como están.
    
    Args:
        messages: Lista de mensajes de la conversación
        
    Returns:
        List: Lista de mensajes (sin modificaciones, el contexto ya está en el historial)
    """
    # Asegurar que el contexto esté como penúltimo mensaje
    _ensure_context_as_penultimate()
    
    # Transformar mensajes de contexto JSON a texto formateado para el LLM
    transformed_messages = []
    for msg in messages:
        if (msg.get('role') == 'system' and 
            msg.get('content', '').startswith('CONTEXTO DE LA CONVERSACIÓN:')):
            # Extraer el JSON del mensaje de contexto
            content = msg.get('content', '')
            if content.startswith('CONTEXTO DE LA CONVERSACIÓN:\n\n'):
                json_content = content[len('CONTEXTO DE LA CONVERSACIÓN:\n\n'):]
                try:
                    # Parsear JSON y formatear para mostrar
                    parsed = json.loads(json_content)
                    if isinstance(parsed, dict) and parsed.get("_mcp_context_format") == "elements_v1":
                        items = parsed.get("items", [])
                        if items:
                            formatted_context = _format_context_for_display(items)
                            # Crear mensaje formateado para el LLM
                            formatted_msg = {
                                **msg,
                                'content': f'CONTEXTO DE LA CONVERSACIÓN:\n\n{formatted_context}'
                            }
                            transformed_messages.append(formatted_msg)
                        else:
                            transformed_messages.append(msg)
                    else:
                        transformed_messages.append(msg)
                except (json.JSONDecodeError, ValueError):
                    # Si no se puede parsear, mantener el mensaje original
                    transformed_messages.append(msg)
            else:
                transformed_messages.append(msg)
        else:
            transformed_messages.append(msg)
    
    return transformed_messages

# Registrar un hook para inyectar el contexto en las conversaciones
def register_conversation_hook():
    """
    Registra un hook para inyectar el contexto en las conversaciones.
    Este hook debe ser llamado durante la inicialización de la aplicación.
    
    Este hook ya está integrado en el sistema a través de la modificación de chat_handlers.py,
    que ahora usa inject_context_to_messages() antes de enviar mensajes al LLM.
    """
    # La integración ya está hecha en chat_handlers.py
    print("Contexto de conversación registrado correctamente.")
    
    # No intentar mostrar notificaciones UI desde tareas de fondo
    # La notificación se hará cuando el usuario interactúe con el sistema
    
    return {"success": True, "message": "Contexto registrado."}

# Nuevas meta tools para manejar elementos del contexto

@meta_tool(
    name="conversation_context_add_item",
    description="Agrega un nuevo elemento al contexto de la conversación",
    parameters_schema={
        "type": "object",
        "properties": {
            "content": {
                "type": "string",
                "description": "Contenido del elemento a agregar al contexto"
            },
            "id": {
                "type": "string",
                "description": "ID opcional para el elemento. Si no se proporciona, se genera uno automáticamente",
                "default": None
            }
        },
        "required": ["content"]
    }
)
def add_context_item(content: str, id: str = None) -> Dict[str, Any]:
    print(f"DEBUG add_context_item called with content={content[:20]}...")
    """
    Agrega un nuevo elemento al contexto de la conversación.
    
    Args:
        content: Contenido del elemento
        id: ID opcional del elemento
        
    Returns:
        Diccionario con el resultado de la operación
    """
    try:
        items = _get_context_items()
        
        # Generar ID si no se proporciona
        if not id:
            id = f"item-{str(uuid.uuid4())[:8]}"
        
        # Verificar que el ID no exista
        if any(item.get('id') == id for item in items):
            return {"error": f"Ya existe un elemento con ID '{id}'"}
        
        # Agregar nuevo elemento
        new_item = {
            "id": id,
            "content": content,
            "timestamp": str(uuid.uuid1().time)
        }
        items.append(new_item)
        
        _set_context_items(items)
        
        # Contexto actualizado - la notificación se maneja en el cliente
        
        return {
            "result": f"Elemento agregado correctamente con ID '{id}'",
            "item_id": id,
            "total_items": len(items)
        }
    except Exception as e:
        logger.error(f"Error al agregar elemento al contexto: {str(e)}")
        return {"error": f"Error al agregar elemento: {str(e)}"}

@meta_tool(
    name="conversation_context_update_item",
    description="Modifica un elemento específico del contexto",
    parameters_schema={
        "type": "object",
        "properties": {
            "id": {
                "type": "string",
                "description": "ID del elemento a modificar"
            },
            "content": {
                "type": "string",
                "description": "Nuevo contenido para el elemento"
            }
        },
        "required": ["id", "content"]
    }
)
def update_context_item(id: str, content: str) -> Dict[str, Any]:
    """
    Modifica un elemento específico del contexto.
    
    Args:
        id: ID del elemento a modificar
        content: Nuevo contenido
        
    Returns:
        Diccionario con el resultado de la operación
    """
    try:
        items = _get_context_items()
        
        # Buscar el elemento
        for i, item in enumerate(items):
            if item.get('id') == id:
                items[i]['content'] = content
                items[i]['timestamp'] = str(uuid.uuid1().time)
                
                _set_context_items(items)
                
                # Contexto actualizado - la notificación se maneja en el cliente
                
                return {
                    "result": f"Elemento '{id}' actualizado correctamente",
                    "item_id": id
                }
        
        return {"error": f"No se encontró un elemento con ID '{id}'"}
    except Exception as e:
        logger.error(f"Error al actualizar elemento del contexto: {str(e)}")
        return {"error": f"Error al actualizar elemento: {str(e)}"}

@meta_tool(
    name="conversation_context_remove_item",
    description="Elimina un elemento específico del contexto",
    parameters_schema={
        "type": "object",
        "properties": {
            "id": {
                "type": "string",
                "description": "ID del elemento a eliminar"
            }
        },
        "required": ["id"]
    }
)
def remove_context_item(id: str) -> Dict[str, Any]:
    """
    Elimina un elemento específico del contexto.
    
    Args:
        id: ID del elemento a eliminar
        
    Returns:
        Diccionario con el resultado de la operación
    """
    try:
        items = _get_context_items()
        
        # Buscar y eliminar el elemento
        for i, item in enumerate(items):
            if item.get('id') == id:
                removed_item = items.pop(i)
                
                _set_context_items(items)
                
                # Contexto actualizado - la notificación se maneja en el cliente
                
                return {
                    "result": f"Elemento '{id}' eliminado correctamente",
                    "removed_content": removed_item.get('content', ''),
                    "total_items": len(items)
                }
        
        return {"error": f"No se encontró un elemento con ID '{id}'"}
    except Exception as e:
        logger.error(f"Error al eliminar elemento del contexto: {str(e)}")
        return {"error": f"Error al eliminar elemento: {str(e)}"}


