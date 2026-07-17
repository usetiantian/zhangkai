"""AST-based search for UnboundLocalError: use of var before local binding."""
import os, ast

BASE = r"C:\Users\87999\.nexus"

def find_local_shadow_ast(filepath, var_name):
    """Use AST to find functions where var_name is used before being locally bound."""
    results = []
    try:
        with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
            source = f.read()
        tree = ast.parse(source, filename=filepath)
    except SyntaxError:
        return results
    except:
        return results
    
    class LocalShadowFinder(ast.NodeVisitor):
        def visit_FunctionDef(self, node):
            self._check_scope(node, node.body, var_name)
            self.generic_visit(node)
        
        def visit_AsyncFunctionDef(self, node):
            self._check_scope(node, node.body, var_name)
            self.generic_visit(node)
        
        def _check_scope(self, node, body, var):
            # Find all assignments/imports to var in this scope
            local_bindings = set()
            references = []  # (lineno, type: 'use'|'shadow')
            
            for stmt in ast.walk(ast.Module(body=body, type_ignores=[])):
                # Check for import var
                if isinstance(stmt, ast.Import):
                    for alias in stmt.names:
                        if alias.name == var or alias.asname == var:
                            local_bindings.add(var)
                            references.append((stmt.lineno, 'import'))
                elif isinstance(stmt, ast.ImportFrom):
                    for alias in stmt.names:
                        if alias.name == var or (alias.asname and alias.asname == var):
                            local_bindings.add(var)
                            references.append((stmt.lineno, 'import_from'))
                # Check for assignment to var
                elif isinstance(stmt, ast.Assign):
                    for target in stmt.targets:
                        if isinstance(target, ast.Name) and target.id == var:
                            local_bindings.add(var)
                            references.append((stmt.lineno, 'assign'))
                # Check for augmented assignment
                elif isinstance(stmt, ast.AugAssign):
                    if isinstance(stmt.target, ast.Name) and stmt.target.id == var:
                        local_bindings.add(var)
                        references.append((stmt.lineno, 'aug_assign'))
                # Check for Name reference
                elif isinstance(stmt, ast.Name):
                    if stmt.id == var and isinstance(stmt.ctx, ast.Load):
                        references.append((stmt.lineno, 'use'))
            
            if local_bindings:
                # Check if any 'use' comes before any binding
                first_use = None
                first_bind = None
                for lineno, kind in sorted(references):
                    if kind == 'use' and first_use is None:
                        first_use = lineno
                    if kind in ('import', 'import_from', 'assign', 'aug_assign') and first_bind is None:
                        first_bind = lineno
                
                if first_use is not None and first_bind is not None and first_use < first_bind:
                    results.append((filepath, node.lineno, node.name, var, first_use, first_bind))
    
    finder = LocalShadowFinder()
    finder.visit(tree)
    return results

print("AST-BASED SEARCH")
print("=" * 60)

for var in ['datetime', 'asyncio']:
    print(f"\n--- Searching for '{var}' violations ---")
    count = 0
    for root, dirs, files in os.walk(BASE):
        if '__pycache__' in root or '.git' in root:
            continue
        dirs[:] = [d for d in dirs if not d.startswith('.')]
        for fname in files:
            if not fname.endswith('.py'):
                continue
            fpath = os.path.join(root, fname)
            for r in find_local_shadow_ast(fpath, var):
                short = fpath.replace(BASE + '\\', '')
                print(f"  {short}:{r[1]} {r[2]}() — {r[3]} used at line {r[4]}, bound at line {r[5]}")
                count += 1
    print(f"  Total: {count}")
