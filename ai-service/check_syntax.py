import ast
with open('app/main.py', 'r', encoding='utf-8') as f:
    src = f.read()
try:
    ast.parse(src)
    print('syntax OK')
except SyntaxError as e:
    print(f'SyntaxError at line {e.lineno}: {e.msg}')
    print(f'  {e.text}')
