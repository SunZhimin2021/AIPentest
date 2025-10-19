"""
Message Validator for Tool Call Sequences

This module provides robust validation and repair for tool call sequences
to prevent API errors caused by orphaned tool calls or incomplete sequences.
"""

def validate_tool_call_sequence(messages):
    """
    Validates tool call sequences to prevent API errors.
    
    Args:
        messages: List of messages to validate
        
    Returns:
        List of validated messages with complete tool call sequences
    """
    if not messages:
        return []
    
    validated = []
    pending_tool_calls = set()
    
    for msg in messages:
        role = msg.get('role')
        
        if role == 'assistant' and 'tool_calls' in msg:
            # Track tool calls that need responses
            for tc in msg.get('tool_calls', []):
                if tc.get('id'):
                    pending_tool_calls.add(tc['id'])
            validated.append(msg)
            
        elif role == 'tool':
            # Check if this tool result has a corresponding tool call
            tool_call_id = msg.get('tool_call_id')
            if tool_call_id and tool_call_id in pending_tool_calls:
                validated.append(msg)
                pending_tool_calls.remove(tool_call_id)
            # Skip orphaned tool results
            
        else:
            # Regular messages
            validated.append(msg)
    
    # Remove assistant messages with unresolved tool calls
    if pending_tool_calls:
        final_validated = []
        for msg in validated:
            if msg.get('role') == 'assistant' and 'tool_calls' in msg:
                has_unresolved = any(tc.get('id') in pending_tool_calls 
                                   for tc in msg.get('tool_calls', []))
                if not has_unresolved:
                    final_validated.append(msg)
            else:
                final_validated.append(msg)
        validated = final_validated
    
    return validated
