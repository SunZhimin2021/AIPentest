# Sistema de Meta Tools para MCP Open Client

El sistema de Meta Tools permite crear y registrar herramientas personalizadas que pueden ser utilizadas por el LLM para interactuar con la interfaz de usuario o realizar otras tareas que no son parte de las herramientas MCP estándar.

## Características

- **Integración transparente con el sistema de herramientas MCP existente**
- **Soporte para funciones síncronas y asíncronas**
- **Decorador para facilitar el registro de meta tools**
- **Esquema compatible con OpenAI Function Calling**
- **Manejo de errores integrado**

## Uso básico

### 1. Registrar una meta tool

Hay dos formas de registrar una meta tool:

#### Usando el decorador `@meta_tool`

```python
from mcp_open_client.meta_tools import meta_tool

@meta_tool(
    name="ui_notify",
    description="Muestra una notificación en la interfaz de usuario",
    parameters_schema={
        "type": "object",
        "properties": {
            "message": {"type": "string", "description": "Mensaje a mostrar"},
            "type": {"type": "string", "enum": ["positive", "negative", "warning", "info"], "default": "info"}
        },
        "required": ["message"]
    }
)
def show_notification(message: str, type: str = "info"):
    """Muestra una notificación en la interfaz de usuario."""
    ui.notify(message, type=type)
    return f"Notificación mostrada: {message}"
```

#### Registrando directamente en el registro

```python
from mcp_open_client.meta_tools import meta_tool_registry

def show_notification(message: str, type: str = "info"):
    """Muestra una notificación en la interfaz de usuario."""
    ui.notify(message, type=type)
    return f"Notificación mostrada: {message}"

meta_tool_registry.register_tool(
    name="ui_notify",
    func=show_notification,
    description="Muestra una notificación en la interfaz de usuario",
    parameters_schema={
        "type": "object",
        "properties": {
            "message": {"type": "string", "description": "Mensaje a mostrar"},
            "type": {"type": "string", "enum": ["positive", "negative", "warning", "info"], "default": "info"}
        },
        "required": ["message"]
    }
)
```

### 2. Funciones asíncronas

Las meta tools también pueden ser funciones asíncronas:

```python
@meta_tool(
    name="delayed_task",
    description="Ejecuta una tarea después de un retraso",
    parameters_schema={
        "type": "object",
        "properties": {
            "seconds": {"type": "number", "description": "Segundos a esperar"},
            "message": {"type": "string", "description": "Mensaje a mostrar después del retraso"}
        },
        "required": ["seconds", "message"]
    }
)
async def delayed_task(seconds: float, message: str):
    """Ejecuta una tarea después de un retraso."""
    await asyncio.sleep(seconds)
    ui.notify(message)
    return f"Tarea ejecutada después de {seconds} segundos: {message}"
```

### 3. Manejo de errores

Puedes devolver errores desde tus meta tools de la siguiente manera:

```python
@meta_tool(
    name="divide_numbers",
    description="Divide dos números",
    parameters_schema={
        "type": "object",
        "properties": {
            "a": {"type": "number", "description": "Dividendo"},
            "b": {"type": "number", "description": "Divisor"}
        },
        "required": ["a", "b"]
    }
)
def divide_numbers(a: float, b: float):
    """Divide dos números."""
    if b == 0:
        return {"error": "No se puede dividir por cero"}
    
    return a / b
```

## Ejemplos

Consulta el archivo `mcp_open_client/examples/custom_meta_tools.py` para ver ejemplos completos de meta tools personalizadas.

## Referencia de la API

### `meta_tool_registry`

Instancia global del registro de meta tools.

#### Métodos

- `register_tool(name, func, description, parameters_schema)`: Registra una nueva meta tool
- `execute_tool(tool_name, params)`: Ejecuta una meta tool registrada
- `get_tools_schema()`: Obtiene el esquema de todas las meta tools en formato compatible con OpenAI

### Decorador `@meta_tool`

Decorador para registrar una función como meta tool.

#### Parámetros

- `name`: Nombre de la meta tool
- `description`: Descripción de la meta tool
- `parameters_schema`: Esquema de parámetros en formato JSON Schema

## Herramientas predefinidas

El sistema viene con algunas meta tools predefinidas:

### Herramientas de UI
- `meta-ui_notify`: Muestra una notificación en la interfaz de usuario

### Herramientas de control de servidores MCP
- `meta-mcp_toggle_server`: Activa o desactiva un servidor MCP específico
- `meta-mcp_list_servers`: Lista todos los servidores MCP configurados y su estado
- `meta-mcp_restart_all_servers`: Reinicia todos los servidores MCP activos
