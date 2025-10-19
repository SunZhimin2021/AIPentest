"""
Meta tool para respuestas estructuradas al usuario.
Permite al LLM generar respuestas tipificadas con mejor presentación visual.
"""

from typing import Dict, Any, Optional
from mcp_open_client.meta_tools.meta_tool import meta_tool
from nicegui import ui
import json

# Tipos de respuesta terminales específicos para respond_to_user
# Enfocados en finalizar conversaciones y dar respuestas definitivas
RESPONSE_TYPES = {
    "final_answer": {
        "icon": "✅",
        "description": "Respuesta final o conclusión definitiva",
        "background_color": "#e8f5e9",  # Verde suave
        "border_color": "#4caf50",
        "text_color": "#2e7d32",
        "icon_bg": "#c8e6c9"
    },
    "completed": {
        "icon": "🎉",
        "description": "Tarea completada exitosamente",
        "background_color": "#e8f5e9",  # Verde suave
        "border_color": "#4caf50",
        "text_color": "#2e7d32",
        "icon_bg": "#c8e6c9"
    },
    "explanation": {
        "icon": "💡",
        "description": "Explicación completa y detallada",
        "background_color": "#fff8e1",  # Amarillo suave
        "border_color": "#ffc107",
        "text_color": "#f57f17",
        "icon_bg": "#fff3c4"
    },
    "need_clarification": {
        "icon": "❓",
        "description": "Necesita información adicional del usuario",
        "background_color": "#e1f5fe",  # Azul claro suave
        "border_color": "#03a9f4",
        "text_color": "#0277bd",  # Azul oscuro
        "icon_bg": "#b3e5fc"
    },
    "error_final": {
        "icon": "❌",
        "description": "Error crítico que termina el proceso",
        "background_color": "#ffebee",  # Rojo suave
        "border_color": "#f44336",
        "text_color": "#c62828",
        "icon_bg": "#ffcdd2"
    }
}

@meta_tool(
    name="respond_to_user",
    description="""
    🔚 HERRAMIENTA TERMINAL - Envía respuesta final al usuario y TERMINA la conversación.
    
    ⚠️ CRÍTICO: Esta herramienta DEBE ser la ÚLTIMA acción en tu respuesta.
    🚫 NO ejecutes más herramientas después de usar respond_to_user.
    🔚 NO continues procesando después de llamar esta función.
    
    Esta herramienta devuelve el control al usuario con una respuesta estructurada
    que se muestra con iconos y estilos específicos en la interfaz.
    
    Tipos de respuesta terminales disponibles:
    - final_answer: Respuesta final o conclusión definitiva ✅
    - completed: Tarea completada exitosamente 🎉
    - explanation: Explicación completa y detallada 💡
    - need_clarification: Necesita información adicional del usuario ❓
    - error_final: Error crítico que termina el proceso ❌
    
    🔚 REGLA ABSOLUTA: Después de llamar respond_to_user, tu trabajo TERMINA.
    Esta herramienta marca el FIN DEFINITIVO de tu procesamiento.
    El control vuelve al usuario inmediatamente después de esta llamada.
    
    💡 CUÁNDO USAR:
    - Cuando hayas completado la tarea solicitada
    - Cuando necesites dar una respuesta final
    - Cuando quieras terminar la conversación elegantemente
    - Cuando hayas proporcionado toda la información necesaria
    - Cuando necesites más información del usuario para continuar (need_clarification)
    
    🚫 NO USAR si planeas ejecutar más herramientas después.
    """,
    parameters_schema={
        "type": "object",
        "properties": {
            "content": {
                "type": "string",
                "description": "Contenido de la respuesta al usuario"
            },
            "response_type": {
                "type": "string",
                "enum": list(RESPONSE_TYPES.keys()),
                "description": "Tipo de respuesta para determinar la presentación visual",
                "default": "info"
            },
            "title": {
                "type": "string",
                "description": "Título opcional para la respuesta",
                "default": None
            },
            "format": {
                "type": "string",
                "enum": ["markdown", "html"],
                "description": "Formato de la respuesta: 'markdown' para texto normal o 'html' para contenido interactivo. Para HTML interactivo, incluye 'html_content' en metadatos con botones que tengan: data-choice attribute, onclick='sendUserChoice(valor, this)'",
                "default": "markdown"
            }
        },
        "required": ["content"]
    }
)
async def respond_to_user(content: str, response_type: str = "info", title: Optional[str] = None, format: str = "markdown") -> str:
    """
    Genera una respuesta estructurada al usuario.
    
    Args:
        content: Contenido principal de la respuesta
        response_type: Tipo de respuesta para determinar el estilo visual
        title: Título opcional para la respuesta
        format: Formato de la respuesta ('markdown' para texto normal o 'html' para contenido interactivo)
               Para HTML interactivo, debe incluir 'html_content' en metadatos con botones que tengan:
               - Atributo data-choice en cada botón
               - Función onclick que llame sendUserChoice()
               - Parámetros correctos en onclick: ('valor', this)
               Ejemplo: <button data-choice onclick="sendUserChoice('Sí', this)">Sí</button>
        
    Returns:
        Respuesta formateada con metadatos para renderizado visual
    """
    # Validar tipo de respuesta
    if response_type not in RESPONSE_TYPES:
        response_type = "info"
    
    # Validar formato
    if format not in ["markdown", "html"]:
        format = "markdown"
    
    # Obtener configuración del tipo
    type_config = RESPONSE_TYPES[response_type]
    icon = type_config["icon"]
    
    # Si es formato HTML, usar metadatos interactivos
    if format == "html":
        # Generar ID único para esta instancia interactiva
        import uuid
        interaction_id = f"interactive-{str(uuid.uuid4())[:8]}"
        
        # Construir respuesta formateada
        formatted_response = ""
        
        if title:
            formatted_response += f"**{title}**\n\n"
        
        # Agregar metadatos para renderizado HTML interactivo
        interactive_metadata = {
            "type": "interactive_choice",
            "interaction_id": interaction_id,
            "html_content": content,
            "is_interactive": True,
            "response_type": response_type,
            "icon": icon,
            "background_color": type_config["background_color"],
            "border_color": type_config["border_color"],
            "text_color": type_config["text_color"],
            "icon_bg": type_config["icon_bg"],
            "is_terminal": True
        }
        
        # Agregar metadatos embebidos que serán procesados por message_parser.py
        formatted_response += f"<!-- INTERACTIVE_METADATA: {json.dumps(interactive_metadata)} -->"
        
        return formatted_response
    
    else:
        # Formato markdown normal (comportamiento original)
        # Construir respuesta formateada
        formatted_response = content
        
        if title:
            formatted_response = f"**{title}**\n\n{content}"
        
        # Agregar metadatos como comentario para que la UI pueda aplicar estilos
        response_metadata = {
            "response_type": response_type,
            "icon": icon,
            "background_color": type_config["background_color"],
            "border_color": type_config["border_color"],
            "text_color": type_config["text_color"],
            "icon_bg": type_config["icon_bg"],
            "is_terminal": True  # Marca que esta es una respuesta terminal
        }
        
        # Agregar metadatos embebidos que serán procesados por message_parser.py
        formatted_response += f"\n\n<!-- RESPONSE_METADATA: {response_metadata} -->"
        
        return formatted_response

def get_response_types() -> Dict[str, Dict[str, Any]]:
    """
    Obtiene la lista de tipos de respuesta disponibles.
    
    Returns:
        Diccionario con los tipos de respuesta y sus configuraciones
    """
    return RESPONSE_TYPES.copy()

def is_structured_response(content: str) -> bool:
    """
    Verifica si un contenido es una respuesta estructurada.
    
    Args:
        content: Contenido a verificar
        
    Returns:
        True si es una respuesta estructurada, False en caso contrario
    """
    return "<!-- RESPONSE_METADATA:" in content

def extract_response_metadata(content: str) -> Optional[Dict[str, Any]]:
    """
    Extrae los metadatos de una respuesta estructurada.
    
    Args:
        content: Contenido de la respuesta
        
    Returns:
        Diccionario con los metadatos o None si no es respuesta estructurada
    """
    import re
    import json
    
    if not is_structured_response(content):
        return None
    
    # Buscar el comentario con metadatos
    pattern = r'<!-- RESPONSE_METADATA: ({.*?}) -->'
    match = re.search(pattern, content)
    
    if match:
        try:
            metadata_str = match.group(1)
            # Reemplazar comillas simples por dobles para JSON válido
            metadata_str = metadata_str.replace("'", '"')
            return json.loads(metadata_str)
        except json.JSONDecodeError:
            return None
    
    return None

def clean_response_content(content: str) -> str:
    """
    Limpia el contenido de respuesta removiendo metadatos.
    
    Args:
        content: Contenido con posibles metadatos
        
    Returns:
        Contenido limpio sin metadatos
    """
    import re
    
    # Remover comentario de metadatos
    pattern = r'\n\n<!-- RESPONSE_METADATA: {.*?} -->'
    cleaned = re.sub(pattern, '', content)
    
    return cleaned.strip()