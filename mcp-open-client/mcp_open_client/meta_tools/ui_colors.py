"""
Meta tool para modificar los colores de la interfaz de usuario.

Este módulo proporciona una meta tool que permite al LLM cambiar
los colores del tema de la aplicación de forma dinámica.
"""

from nicegui import ui, app
from mcp_open_client.meta_tools.meta_tool import meta_tool
import re

# Colores por defecto
DEFAULT_COLORS = {
    'primary': '#dc2626',      # Red to match favicon
    'secondary': '#1f2937',    # Dark gray
    'accent': '#3b82f6',       # Blue accent
    'positive': '#10b981',     # Green for success
    'negative': '#ef4444',     # Red for errors
    'info': '#3b82f6',         # Blue for info
    'warning': '#f59e0b'       # Orange for warnings
}

# Colores personalizados para el chat
CHAT_CUSTOM_COLORS = {
    'user_message_bg': '#1e293b',
    'user_message_border': '#fbbf24',
    'assistant_message_bg': '#374151',
    'assistant_message_border': '#f87171',  # red-300 equivalent
    'tool_call_bg': '#1e293b',              # slate-800 equivalent
    'tool_call_border': '#60a5fa',          # blue-400 equivalent
    'tool_args_label': '#93c5fd',           # blue-300 equivalent
    'tool_response_label': '#6ee7b7',       # emerald-300 equivalent
    'truncated_message': '#fbbf24'          # yellow-400 equivalent
}

# Todos los colores disponibles
ALL_COLORS = {**DEFAULT_COLORS, **CHAT_CUSTOM_COLORS}

def is_valid_hex_color(color: str) -> bool:
    """Validar que el color sea un código hexadecimal válido."""
    if not color.startswith('#'):
        return False
    if len(color) not in [4, 7]:  # #RGB o #RRGGBB
        return False
    return bool(re.match(r'^#[0-9A-Fa-f]+$', color))

@meta_tool(
    name="ui_change_color",
    description="Cambia un color específico del tema de la interfaz de usuario",
    parameters_schema={
        "type": "object",
        "properties": {
            "color_type": {
                "type": "string",
                "enum": list(ALL_COLORS.keys()),
                "description": "Tipo de color a cambiar (incluye colores estándar y personalizados del chat)"
            },
            "color_value": {
                "type": "string",
                "description": "Valor del color en formato hexadecimal (ej: #ff0000 para rojo)"
            }
        },
        "required": ["color_type", "color_value"]
    }
)
def change_ui_color(color_type: str, color_value: str):
    """
    Cambia un color específico del tema de la interfaz.
    
    Args:
        color_type: Tipo de color (primary, secondary, accent, positive, negative, info, warning)
        color_value: Valor del color en formato hexadecimal
    
    Returns:
        Mensaje con el resultado de la operación
    """
    # Validar el formato del color
    if not is_valid_hex_color(color_value):
        return {"error": f"Color inválido: {color_value}. Debe ser un valor hexadecimal como #ff0000"}
    
    # Validar que el tipo de color exista
    if color_type not in ALL_COLORS:
        return {"error": f"Tipo de color inválido: {color_type}. Debe ser uno de: {', '.join(ALL_COLORS.keys())}"}
    
    # Obtener colores actuales del storage o usar todos los colores por defecto
    current_colors = app.storage.user.get('ui_colors', ALL_COLORS.copy())
    
    # Actualizar el color específico
    current_colors[color_type] = color_value
    
    # Guardar en storage
    app.storage.user['ui_colors'] = current_colors
    
    # Aplicar los colores inmediatamente
    ui.colors(**current_colors)
    
    # Mostrar notificación
    ui.notify(
        f"Color {color_type} cambiado a {color_value}",
        color='positive',
        position='top'
    )
    
    return f"Color {color_type} actualizado a {color_value} correctamente"


@meta_tool(
    name="ui_get_colors",
    description="Obtiene los colores actuales del tema de la interfaz",
    parameters_schema={
        "type": "object",
        "properties": {},
        "required": []
    }
)
def get_ui_colors():
    """
    Obtiene los colores actuales del tema.
    
    Returns:
        Diccionario con los colores actuales
    """
    current_colors = app.storage.user.get('ui_colors', ALL_COLORS.copy())
    
    ui.notify("Colores actuales obtenidos", color='info', position='top')
    
    return {
        "colores_actuales": current_colors,
        "colores_disponibles": list(ALL_COLORS.keys())
    }

@meta_tool(
    name="ui_reset_colors",
    description="Restaura los colores del tema a los valores por defecto",
    parameters_schema={
        "type": "object",
        "properties": {},
        "required": []
    }
)
def reset_ui_colors():
    """
    Restaura los colores a los valores por defecto.
    
    Returns:
        Mensaje confirmando el reseteo
    """
    # Restaurar todos los colores por defecto (incluye custom)
    app.storage.user['ui_colors'] = ALL_COLORS.copy()
    
    # Aplicar todos los colores por defecto
    ui.colors(**ALL_COLORS)
    
    # Mostrar notificación
    ui.notify("Colores restaurados a los valores por defecto", color='positive', position='top')
    
    return "Colores del tema restaurados a los valores por defecto correctamente"

