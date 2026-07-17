# AST search covering ALL of .nexus
import os, ast

BASE = r"C:\Users\87999\.nexus"

def find_local_shadow_ast(filepath, var_name):
    results = []
    try:
        with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
            source = f.read()
        tree = ast.parse(source, filename=filepath)
    except:
        return results
    
    class Finder(ast.NodeVisitor):
        def visit_FunctionDef(self, node):
            self._check(node, node.body, var_name)
            self.generic_visit(node)
        def visit_AsyncFunctionDef(self, node):
            self._check(node, node.body, var_name)
            self.generic_visit(node)
        def _check(self, node, body, var):
            local_bindings = set()
            refs = []
            for stmt in ast.walk(ast.Module(body=body, type_ignores=[])):
                if isinstance(stmt, (ast.Import, ast.ImportFrom)):
                    for alias in stmt.names:
                        name = alias.asname or alias.name
                        if name == var:
                            local_bindings.add(var)
                            refs.append((stmt.lineno, 'bind'))
                elif isinstance(stmt, (ast.Assign, ast.AugAssign)):
                    targets = stmt.targets if isinstance(stmt, ast.Assign) else [stmt.target]
                    for t in targets:
                        if isinstance(t, ast.Name) and t.id == var:
                            local_bindings.add(var)
                            refs.append((stmt.lineno, 'bind'))
                elif isinstance(stmt, ast.Name) and stmt.id == var and isinstance(stmt.ctx, ast.Load):
                    refs.append((stmt.lineno, 'use'))
            
            if local_bindings:
                refs.sort()
                first_use = None
                first_bind = None
                for lineno, kind in refs:
                    if kind == 'use' and first_use is None:
                        first_use = lineno
                    if kind == 'bind' and first_bind is None:
                        first_bind = lineno
                if first_use is not None and first_bind is not None and first_use < first_bind:
                    results.append((filepath, node.lineno, node.name, var, first_use, first_bind))
    
    Finder().visit(tree)
    return results

for var in ['datetime', 'asyncio']:
    print(f"--- {var} ---")
    count = 0
    for root, dirs, files in os.walk(BASE):
        dirs[:] = [d for d in dirs if d != '__pycache__']
        for fname in files:
            if not fname.endswith('.py'):
                continue
            fpath = os.path.join(root, fname)
            for r in find_local_shadow_ast(fpath, var):
                short = fpath.replace(BASE + '\\', '')
                print(f"  {short}:{r[1]} {r[2]}() use@{r[4]} bind@{r[5]}")
                count += 1
    print(f"  Total: {count}")
