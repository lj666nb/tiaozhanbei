"""Fix literal newlines in Python strings that should be \\n escapes."""
import re

PATH = 'D:/education/11/backend/services/code_lab_templates.py'
with open(PATH, encoding='utf-8') as f:
    content = f.read()

# Fix all occurrences of literal newlines inside strings in hint tuples
# Replace patterns like "text\nmore text" (actual newline) with "text\\nmore text" (escape sequence)
# Only within hint arrays

lines = content.split('\n')
i = 0
fixed = 0
while i < len(lines):
    line = lines[i]
    stripped = line.strip()

    # Case 1: Line is a continuation of a previous string (no quote at start, no structural chars)
    if i > 0 and not stripped.startswith('"') and not stripped.startswith("'") and not stripped.startswith('(') and not stripped.startswith(')') and not stripped.startswith(']') and not stripped.startswith('['):
        prev = lines[i-1].strip()
        if '"' in prev and not prev.rstrip().endswith('",') and not prev.rstrip().endswith('")'):
            # Join with previous line
            lines[i-1] = lines[i-1].rstrip() + '\\n' + lines[i].lstrip()
            lines.pop(i)
            fixed += 1
            continue

    # Case 2: Line starts a string but doesn't close it properly (content after quote without comma)
    if stripped.startswith('"') and i+1 < len(lines):
        next_line = lines[i+1].strip()
        # If this line doesn't end with ", or ") and next line is continuation
        if not stripped.endswith('",') and not stripped.endswith('")'):
            if not next_line.startswith(']') and not next_line.startswith('[') and not next_line.startswith('(') and not next_line.startswith(')'):
                if '"' not in next_line[:5]:  # Next line is code, not a new string
                    lines[i] = lines[i].rstrip() + '\\n' + lines[i+1].lstrip()
                    lines.pop(i+1)
                    fixed += 1
                    continue

    i += 1

content = '\n'.join(lines)

# Verify: check for any remaining unbalanced quotes in hints
import ast
try:
    ast.parse(content)
    print(f'Fixed {fixed} lines. Syntax is clean!')
except SyntaxError as e:
    print(f'Fixed {fixed} lines. Still has syntax error: {e}')

with open(PATH, 'w', encoding='utf-8') as f:
    f.write(content)
