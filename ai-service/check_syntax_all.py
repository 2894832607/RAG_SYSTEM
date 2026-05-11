import ast
files = ['app/main.py', 'app/agent/llm.py']
for f in files:
    try:
        with open(f, 'r', encoding='utf-8') as fp:
            ast.parse(fp.read())
        print(f'✅ {f} syntax OK')
    except SyntaxError as e:
        print(f'❌ {f} line {e.lineno}: {e.msg}')
        print(f'   {e.text}')
