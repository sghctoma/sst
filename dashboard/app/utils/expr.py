import math
import numbers
import ast
import operator as op


class ExpressionParser:
    """ Basic parser with local variable and math functions
    based on https://stackoverflow.com/a/69540962
    """

    _operators2method = {
        ast.Add: op.add,
        ast.Sub: op.sub,
        ast.Mult: op.mul,
        ast.Div: op.truediv,
        ast.Mod: op.mod,
        ast.BitXor: op.pow,
        ast.Not: op.not_,
        ast.And: op.and_,
        ast.Or:  op.or_,
        ast.USub: op.neg,
        ast.UAdd: lambda a: a,
    }

    _vars = {}
    _names2func = {}

    def __init__(self, env):
        for k, v in env.items():
            if callable(v):
                self._names2func[k] = v
            elif isinstance(v, numbers.Number):
                self._vars[k] = v

    def _Name(self, name):
        try:
            return self._vars[name]
        except KeyError:
            return self._alt_name(name)

    @staticmethod
    def _alt_name(name):
        if name.startswith("_"):
            raise NameError(f"{name!r}")
        try:
            return getattr(math, name)
        except AttributeError:
            raise NameError(f"{name!r}")

    def _validate(self, node):
        if isinstance(node, ast.Expression):
            return self._validate(node.body)
        if isinstance(node, ast.Constant):
            return 1
        if isinstance(node, ast.Name):
            return self._Name(node.id)
        if isinstance(node, ast.BinOp):
            method = self._operators2method[type(node.op)]
            return method(self._validate(node.left), self._validate(node.right))
        if isinstance(node, ast.UnaryOp):
            method = self._operators2method[type(node.op)]
            return method(self._validate(node.operand))
        if isinstance(node, ast.Attribute):
            return getattr(self._validate(node.value), node.attr)
        if isinstance(node, ast.Call):
            self._Name(node.func.id)
            [self._validate(a) for a in node.args]
            {k.arg: self._validate(k.value) for k in node.keywords}
            return 1
        else:
            raise TypeError(node)

    def _eval(self, node):
        if isinstance(node, ast.Expression):
            return self._eval(node.body)
        if isinstance(node, ast.Constant):
            return node.n
        if isinstance(node, ast.Name):
            return self._Name(node.id)
        if isinstance(node, ast.BinOp):
            method = self._operators2method[type(node.op)]
            return method(self._eval(node.left), self._eval(node.right))
        if isinstance(node, ast.UnaryOp):
            method = self._operators2method[type(node.op)]
            return method(self._eval(node.operand))
        if isinstance(node, ast.Attribute):
            return getattr(self._eval(node.value), node.attr)
        if isinstance(node, ast.Call):
            print(node.func)
            return self._eval(node.func)(
                      *(self._eval(a) for a in node.args),
                      **{k.arg: self._eval(k.value) for k in node.keywords}
                   )
        else:
            raise TypeError(node)

    def evaluate(self, expr):
        return self._eval(ast.parse(expr, mode='eval'))

    def validate(self, expr) -> bool:
        try:
            self._validate(ast.parse(expr, mode='eval'))
            return True
        except BaseException:
            return False
