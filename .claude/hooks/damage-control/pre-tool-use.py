#!/usr/bin/env python3
"""
Claude Code PreToolUse Hook - Damage Control

Blocks or requires confirmation for dangerous operations.
Reads patterns from patterns.yaml in the same directory.
"""

import json
import os
import re
import sys
from pathlib import Path

# Load YAML without external dependency
def load_yaml_simple(path: Path) -> dict:
    """Simple YAML parser for our config format."""
    content = path.read_text()
    result: dict = {}
    current_key = None
    current_list: list = []
    in_list = False

    for line in content.split('\n'):
        stripped = line.strip()

        # Skip comments and empty lines
        if not stripped or stripped.startswith('#'):
            continue

        # Top-level key
        if not line.startswith(' ') and not line.startswith('-') and ':' in stripped:
            if current_key and current_list:
                result[current_key] = current_list
            key = stripped.split(':')[0].strip()
            value = stripped.split(':', 1)[1].strip() if ':' in stripped else ''
            if value:
                result[key] = value
                current_key = None
                current_list = []
                in_list = False
            else:
                current_key = key
                current_list = []
                in_list = True
            continue

        # List item with dict (pattern entry)
        if stripped.startswith('- pattern:'):
            pattern_value = stripped.split(':', 1)[1].strip().strip("'\"")
            current_list.append({'pattern': pattern_value})
            continue

        # Dict key within list item
        if in_list and current_list and ':' in stripped and not stripped.startswith('-'):
            key, value = stripped.split(':', 1)
            key = key.strip()
            value = value.strip().strip("'\"")
            if isinstance(current_list[-1], dict):
                current_list[-1][key] = value
            continue

        # Simple list item
        if stripped.startswith('- '):
            value = stripped[2:].strip().strip("'\"")
            current_list.append(value)
            continue

    # Don't forget last key
    if current_key and current_list:
        result[current_key] = current_list

    return result


def expand_path(path: str) -> str:
    """Expand ~ and environment variables in path."""
    return os.path.expandvars(os.path.expanduser(path))


def path_matches(file_path: str, pattern: str) -> bool:
    """Check if a file path matches a pattern."""
    # Handle negation
    if pattern.startswith('!'):
        return False  # Negation patterns are handled separately

    expanded_pattern = expand_path(pattern)
    expanded_file = expand_path(file_path)

    # Glob-style matching
    if '*' in pattern:
        import fnmatch
        return fnmatch.fnmatch(expanded_file, expanded_pattern) or \
               fnmatch.fnmatch(os.path.basename(expanded_file), pattern)

    # Directory prefix matching
    if pattern.endswith('/'):
        return expanded_file.startswith(expanded_pattern) or \
               f'/{pattern[:-1]}/' in expanded_file

    # Exact or suffix matching
    return expanded_file == expanded_pattern or \
           expanded_file.endswith(f'/{pattern}') or \
           expanded_file.endswith(pattern)


def check_path_access(file_path: str, config: dict, is_write: bool, is_delete: bool) -> dict | None:
    """Check if path access should be blocked or require confirmation."""

    # Check zero access paths (complete block)
    for pattern in config.get('zeroAccessPaths', []):
        if path_matches(file_path, pattern):
            return {
                'decision': 'deny',
                'reason': f"Access to '{file_path}' is blocked (matches '{pattern}')"
            }

    # Check read-only paths (block writes)
    if is_write:
        for pattern in config.get('readOnlyPaths', []):
            if path_matches(file_path, pattern):
                return {
                    'decision': 'deny',
                    'reason': f"'{file_path}' is read-only (matches '{pattern}')"
                }

    # Check no-delete paths
    if is_delete:
        for pattern in config.get('noDeletePaths', []):
            if path_matches(file_path, pattern):
                return {
                    'decision': 'deny',
                    'reason': f"'{file_path}' cannot be deleted (matches '{pattern}')"
                }

    # Check ask-access paths
    for pattern in config.get('askAccessPaths', []):
        if pattern.startswith('!'):
            continue  # Skip negation patterns in main check
        if path_matches(file_path, pattern):
            return {
                'decision': 'ask',
                'reason': f"Access to '{file_path}' requires confirmation (matches '{pattern}')"
            }

    return None


def check_bash_command(command: str, config: dict) -> dict | None:
    """Check if a bash command should be blocked or require confirmation."""

    for entry in config.get('bashToolPatterns', []):
        if not isinstance(entry, dict):
            continue

        pattern = entry.get('pattern', '')
        description = entry.get('description', 'Dangerous command')
        action = entry.get('action', 'ask')

        try:
            if re.search(pattern, command, re.IGNORECASE):
                return {
                    'decision': 'deny' if action == 'block' else 'ask',
                    'reason': f"{description}: '{command[:100]}{'...' if len(command) > 100 else ''}'"
                }
        except re.error:
            continue  # Skip invalid patterns

    return None


def main():
    # Read input from Claude Code
    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)  # Allow on parse error

    tool_name = input_data.get('tool_name', '')
    tool_input = input_data.get('tool_input', {})

    # Load config
    config_path = Path(__file__).parent / 'patterns.yaml'
    if not config_path.exists():
        sys.exit(0)  # Allow if no config

    try:
        config = load_yaml_simple(config_path)
    except Exception:
        sys.exit(0)  # Allow on config error

    result = None

    # Check based on tool type
    if tool_name == 'Bash':
        command = tool_input.get('command', '')
        result = check_bash_command(command, config)

    elif tool_name in ('Edit', 'Write'):
        file_path = tool_input.get('file_path', '')
        is_delete = False
        result = check_path_access(file_path, config, is_write=True, is_delete=is_delete)

    elif tool_name == 'Read':
        file_path = tool_input.get('file_path', '')
        result = check_path_access(file_path, config, is_write=False, is_delete=False)

    # Output decision
    if result:
        output = {
            'hookSpecificOutput': {
                'hookEventName': 'PreToolUse',
                'permissionDecision': result['decision'],
                'permissionDecisionReason': result['reason']
            }
        }
        print(json.dumps(output))

    sys.exit(0)


if __name__ == '__main__':
    main()
