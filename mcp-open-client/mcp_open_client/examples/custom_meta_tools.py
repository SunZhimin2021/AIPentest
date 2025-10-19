"""
Ejemplo de cómo crear y registrar meta tools personalizadas.

Este archivo muestra cómo crear nuevas meta tools que pueden ser utilizadas
por el LLM para interactuar con la interfaz de usuario o realizar otras tareas
que no son parte de las herramientas MCP estándar.
"""

from mcp_open_client.meta_tools import meta_tool, meta_tool_registry
from nicegui import ui
import asyncio
import datetime
import random

# Ejemplo 1: Herramienta para mostrar una alerta en la UI
@meta_tool(
    name="ui_alert",
    description="Muestra una alerta en la interfaz de usuario con un título y mensaje",
    parameters_schema={
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "Título de la alerta"},
            "message": {"type": "string", "description": "Mensaje a mostrar en la alerta"},
            "type": {"type": "string", "enum": ["positive", "negative", "warning", "info"], "default": "info"}
        },
        "required": ["title", "message"]
    }
)
def show_alert(title: str, message: str, type: str = "info"):
    """Muestra una alerta en la interfaz de usuario."""
    with ui.dialog() as dialog, ui.card():
        ui.label(title).classes('text-h6')
        ui.separator()
        ui.label(message)
        ui.button('Cerrar', on_click=dialog.close).classes(f'bg-{type}')
    
    dialog.open()
    return f"Alerta mostrada: {title} - {message}"

# Ejemplo 2: Herramienta para obtener la fecha y hora actual
@meta_tool(
    name="get_current_datetime",
    description="Obtiene la fecha y hora actual del sistema",
    parameters_schema={
        "type": "object",
        "properties": {
            "format": {"type": "string", "description": "Formato de fecha (opcional, por defecto ISO)"}
        },
        "required": []
    }
)
def get_current_datetime(format: str = None):
    """Obtiene la fecha y hora actual del sistema."""
    now = datetime.datetime.now()
    
    if format:
        try:
            return now.strftime(format)
        except ValueError as e:
            return {"error": f"Formato de fecha inválido: {str(e)}"}
    
    return now.isoformat()

# Ejemplo 3: Herramienta asíncrona para simular una tarea que toma tiempo
@meta_tool(
    name="delayed_response",
    description="Simula una tarea que toma tiempo en completarse",
    parameters_schema={
        "type": "object",
        "properties": {
            "seconds": {"type": "number", "description": "Segundos a esperar"},
            "message": {"type": "string", "description": "Mensaje a devolver después de la espera"}
        },
        "required": ["seconds"]
    }
)
async def delayed_response(seconds: float, message: str = "Tarea completada"):
    """Simula una tarea asíncrona que toma tiempo en completarse."""
    if seconds > 30:
        return {"error": "El tiempo máximo de espera es de 30 segundos"}
    
    await asyncio.sleep(seconds)
    return f"{message} (después de {seconds} segundos)"

# Ejemplo 4: Herramienta para generar números aleatorios
@meta_tool(
    name="generate_random",
    description="Genera números aleatorios dentro de un rango especificado",
    parameters_schema={
        "type": "object",
        "properties": {
            "min": {"type": "integer", "description": "Valor mínimo (inclusive)"},
            "max": {"type": "integer", "description": "Valor máximo (inclusive)"},
            "count": {"type": "integer", "description": "Cantidad de números a generar", "default": 1}
        },
        "required": ["min", "max"]
    }
)
def generate_random(min: int, max: int, count: int = 1):
    """Genera números aleatorios dentro de un rango especificado."""
    if min > max:
        return {"error": "El valor mínimo debe ser menor o igual al valor máximo"}
    
    if count <= 0:
        return {"error": "La cantidad debe ser un número positivo"}
    
    if count > 100:
        return {"error": "La cantidad máxima es 100"}
    
    if count == 1:
        return random.randint(min, max)
    
    return [random.randint(min, max) for _ in range(count)]

# Para usar estas herramientas, simplemente importa este módulo en tu aplicación
# Las herramientas se registrarán automáticamente en el registro de meta tools
print(f"Se han registrado {len(meta_tool_registry.tools)} meta tools")