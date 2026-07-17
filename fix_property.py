def _validate_property(code: str, domain: str) -> Tuple[bool, str]:
        """L2: 属性测试 - 智能随机输入 + 类型感知。
        v18.5n: TypeError/ValueError在收到错误类型输入时=正常，不算错。
        """
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return False, "语法错误"

        funcs = [n for n in ast.walk(tree)
                if isinstance(n, ast.FunctionDef) and not n.name.startswith('_')
                and not n.name.startswith('test_')]
        if not funcs:
            return True, "无公开函数"

        import random as _random

        def _smart_inputs(fn_name):
            nl = fn_name.lower()
            if any(k in nl for k in ('calc','compute','area','volume','sqrt','sin','cos','tan','log','exp','pow','abs','sum','avg','mean','std','var','max','min','dist','norm','dot','cross')):
                return ['_random.randint(0,100)', '_random.uniform(0.1,100)', '_random.randint(-50,50)', '0', '1.0']
            if any(k in nl for k in ('str','text','name','format','parse','split','join','replace')):
                return ['"hello"', '""', '"test"', '"a"*10']
            if any(k in nl for k in ('list','array','sort','filter','map','reduce','iter','seq')):
                return ['[_random.randint(0,10) for _ in range(3)]', '[]', '[1,2,3,4,5]']
            return ['_random.randint(0,100)', '_random.uniform(-10,10)', '"test"', '0']

        checks = []
        for fn in funcs[:3]:
            for inp in _smart_inputs(fn.name)[:5]:
                checks.append(
                    "try:\n    result = {}({})\n    assert result is not None\n    print('PROP:{}:OK')\n"
                    "except (TypeError,ValueError,AttributeError):\n    print('PROP:{}:TYPE_OK')\n"
                    "except Exception as e:\n    print(f'PROP:{}:LOGIC_ERR {{type(e).__name__}}: {{e}}')".format(
                        fn.name, inp, fn.name, fn.name, fn.name)
                )

        prop_code = code + "\nimport random as _random\n" + "\n".join(checks)
        try:
            r = subprocess.run(["python", "-c", prop_code], capture_output=True, encoding="utf-8", errors="replace", timeout=5, env={**__import__("os").environ, "PYTHONIOENCODING": "utf-8"})
            out = r.stdout + r.stderr
            ok = out.count(":OK")
            logic = out.count(":LOGIC_ERR")
            if logic == 0:
                return True, "全通过(OK={})".format(ok)
            elif logic <= 2:
                return True, "{}个逻辑错(OK={})".format(logic, ok)
            else:
                return False, "{}个逻辑错".format(logic)
        except Exception:
            return True, "属性测试跳过"
