import ast
import contextlib
import io
import math
import operator
import re
from collections import Counter


def calculator(expression: str) -> str:
    try:
        if len(expression) > 300:
            return "Error: expression is too long."
        tree = ast.parse(expression, mode="eval")
        result = _eval_math_node(tree)
        return str(result)
    except Exception as exc:
        return f"Error: invalid calculation: {exc}"


def unit_converter(text: str) -> str:
    try:
        raw = text.strip()
        lowered = raw.lower()
        number_match = re.search(r"[-+]?\d+(?:\.\d+)?", lowered)
        if not number_match:
            return "Error: no numeric value found for unit conversion."

        value = float(number_match.group(0))
        conversions = [
            (("cm to m", "centimeter to meter", "centimeters to meters"), value / 100, "m"),
            (("m to cm", "meter to centimeter", "meters to centimeters"), value * 100, "cm"),
            (("km to m", "kilometer to meter", "kilometers to meters"), value * 1000, "m"),
            (("m to km", "meter to kilometer", "meters to kilometers"), value / 1000, "km"),
            (("kg to g", "kilogram to gram", "kilograms to grams"), value * 1000, "g"),
            (("g to kg", "gram to kilogram", "grams to kilograms"), value / 1000, "kg"),
            (("c to f", "celsius to fahrenheit"), value * 9 / 5 + 32, "F"),
            (("f to c", "fahrenheit to celsius"), (value - 32) * 5 / 9, "C"),
        ]
        for phrases, converted, unit in conversions:
            if any(phrase in lowered for phrase in phrases):
                return f"{value:g} -> {converted:g} {unit}"
        return f"Unsupported conversion: {raw}"
    except Exception as exc:
        return f"Error: unit conversion failed: {exc}"


def summarizer(text: str) -> str:
    cleaned = _normalize_text(text)
    if not cleaned:
        return "Summary: empty input."
    sentences = re.split(r"(?<=[.!?。！？])\s+", cleaned)
    summary = " ".join(sentences[:2]).strip()
    if len(summary) > 260:
        summary = summary[:257].rstrip() + "..."
    return f"Summary: {summary}"


def translator_zh_en(text: str) -> str:
    dictionary = {
        "你好": "hello",
        "谢谢": "thank you",
        "人工智能": "artificial intelligence",
        "技能": "skill",
        "检索": "retrieval",
        "调用": "calling",
        "智能体": "agent",
        "系统": "system",
    }
    translated = text
    for source, target in dictionary.items():
        translated = translated.replace(source, target)
    if translated == text:
        translated = f"[rule-based zh->en placeholder] {text}"
    return translated


def translator_en_zh(text: str) -> str:
    dictionary = {
        "hello": "你好",
        "thank you": "谢谢",
        "artificial intelligence": "人工智能",
        "skill": "技能",
        "retrieval": "检索",
        "calling": "调用",
        "agent": "智能体",
        "system": "系统",
    }
    translated = text
    for source, target in dictionary.items():
        translated = re.sub(re.escape(source), target, translated, flags=re.IGNORECASE)
    if translated == text:
        translated = f"[rule-based en->zh placeholder] {text}"
    return translated


def keyword_extractor(text: str) -> str:
    cleaned = _normalize_text(text).lower()
    if not cleaned:
        return "Keywords: empty input."

    tokens = re.findall(r"[a-z][a-z0-9_-]+|[\u4e00-\u9fff]{2,}", cleaned)
    stopwords = {
        "the",
        "and",
        "for",
        "with",
        "that",
        "this",
        "from",
        "are",
        "was",
        "were",
        "into",
        "about",
        "一个",
        "我们",
        "这个",
        "可以",
    }
    keywords = [token for token in tokens if token not in stopwords]
    if not keywords:
        return "Keywords: none"
    top = [word for word, _ in Counter(keywords).most_common(8)]
    return "Keywords: " + ", ".join(top)


def text_rewriter(text: str) -> str:
    cleaned = _normalize_text(text)
    if not cleaned:
        return "Rewritten: empty input."
    if cleaned[-1] not in ".!?。！？":
        cleaned += "."
    return f"Rewritten: {cleaned}"


def sentiment_analyzer(text: str) -> str:
    lowered = text.lower()
    positive_words = {"good", "great", "excellent", "happy", "love", "useful", "成功", "喜欢", "很好"}
    negative_words = {"bad", "poor", "terrible", "sad", "hate", "fail", "失败", "糟糕", "不好"}
    positive = sum(1 for word in positive_words if word in lowered)
    negative = sum(1 for word in negative_words if word in lowered)
    if positive > negative:
        label = "positive"
    elif negative > positive:
        label = "negative"
    else:
        label = "neutral"
    return f"Sentiment: {label} (positive={positive}, negative={negative})"


def paper_qa(question: str) -> str:
    cleaned = _normalize_text(question)
    if not cleaned:
        return "Paper QA: no question provided."
    return (
        "Paper QA placeholder: no paper corpus is loaded yet. "
        f"Received question: {cleaned}"
    )


def python_executor(code: str) -> str:
    try:
        if len(code) > 2000:
            return "Error: code is too long for the restricted executor."
        tree = ast.parse(code, mode="exec")
        _SafePythonValidator().visit(tree)

        stdout = io.StringIO()
        global_env = {"__builtins__": SAFE_BUILTINS, "math": math}
        global_env.update(SAFE_MATH_NAMES)
        local_env: dict = {}

        with contextlib.redirect_stdout(stdout):
            if tree.body and isinstance(tree.body[-1], ast.Expr):
                setup = ast.Module(body=tree.body[:-1], type_ignores=[])
                ast.fix_missing_locations(setup)
                exec(compile(setup, "<safe-python>", "exec"), global_env, local_env)

                expr = ast.Expression(tree.body[-1].value)
                ast.fix_missing_locations(expr)
                value = eval(compile(expr, "<safe-python>", "eval"), global_env, local_env)
            else:
                exec(compile(tree, "<safe-python>", "exec"), global_env, local_env)
                value = None

        printed = stdout.getvalue().strip()
        if printed:
            return printed
        if value is not None:
            return repr(value)

        visible = {
            key: value
            for key, value in local_env.items()
            if not key.startswith("_") and isinstance(value, (int, float, str, bool, list, tuple, dict))
        }
        if visible:
            rendered = ", ".join(f"{key}={value!r}" for key, value in sorted(visible.items()))
            return f"Execution finished. Variables: {rendered}"
        return "Execution finished."
    except Exception as exc:
        return f"Error: restricted python execution failed: {exc}"


ALLOWED_BINOPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
ALLOWED_UNARYOPS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}
SAFE_MATH_NAMES = {
    "abs": abs,
    "round": round,
    "min": min,
    "max": max,
    "pow": pow,
    "sqrt": math.sqrt,
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "log": math.log,
    "log10": math.log10,
    "pi": math.pi,
    "e": math.e,
}


def _eval_math_node(node):
    if isinstance(node, ast.Expression):
        return _eval_math_node(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in ALLOWED_BINOPS:
        left = _eval_math_node(node.left)
        right = _eval_math_node(node.right)
        if isinstance(node.op, ast.Pow) and (abs(left) > 1_000_000 or abs(right) > 12):
            raise ValueError("power expression is too large")
        return ALLOWED_BINOPS[type(node.op)](left, right)
    if isinstance(node, ast.UnaryOp) and type(node.op) in ALLOWED_UNARYOPS:
        return ALLOWED_UNARYOPS[type(node.op)](_eval_math_node(node.operand))
    if isinstance(node, ast.Name) and node.id in SAFE_MATH_NAMES:
        value = SAFE_MATH_NAMES[node.id]
        if callable(value):
            raise ValueError(f"function {node.id!r} must be called")
        return value
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        func_name = node.func.id
        if func_name not in SAFE_MATH_NAMES or not callable(SAFE_MATH_NAMES[func_name]):
            raise ValueError(f"function {func_name!r} is not allowed")
        if node.keywords:
            raise ValueError("keyword arguments are not allowed")
        args = [_eval_math_node(arg) for arg in node.args]
        if len(args) > 4:
            raise ValueError("too many function arguments")
        return SAFE_MATH_NAMES[func_name](*args)
    raise ValueError(f"unsupported expression node: {type(node).__name__}")


SAFE_BUILTINS = {
    "abs": abs,
    "all": all,
    "any": any,
    "bool": bool,
    "dict": dict,
    "enumerate": enumerate,
    "float": float,
    "int": int,
    "len": len,
    "list": list,
    "max": max,
    "min": min,
    "print": print,
    "range": range,
    "round": round,
    "set": set,
    "sorted": sorted,
    "str": str,
    "sum": sum,
    "tuple": tuple,
    "zip": zip,
}

FORBIDDEN_NAMES = {
    "__import__",
    "breakpoint",
    "compile",
    "delattr",
    "dir",
    "eval",
    "exec",
    "getattr",
    "globals",
    "help",
    "input",
    "locals",
    "memoryview",
    "open",
    "setattr",
    "vars",
}
FORBIDDEN_ATTRIBUTES = {
    "connect",
    "eval",
    "exec",
    "mkdir",
    "open",
    "popen",
    "read",
    "read_text",
    "remove",
    "rename",
    "replace",
    "request",
    "rmdir",
    "run",
    "spawn",
    "system",
    "unlink",
    "urlopen",
    "write",
    "write_text",
}
DISALLOWED_NODE_TYPES = (
    ast.AsyncFor,
    ast.AsyncFunctionDef,
    ast.AsyncWith,
    ast.Await,
    ast.ClassDef,
    ast.Delete,
    ast.FunctionDef,
    ast.Global,
    ast.Import,
    ast.ImportFrom,
    ast.Lambda,
    ast.Nonlocal,
    ast.Raise,
    ast.Try,
    ast.While,
    ast.With,
    ast.Yield,
    ast.YieldFrom,
)


class _SafePythonValidator(ast.NodeVisitor):
    def visit(self, node):
        if isinstance(node, DISALLOWED_NODE_TYPES):
            raise ValueError(f"disallowed syntax: {type(node).__name__}")
        return super().visit(node)

    def visit_Name(self, node: ast.Name):
        if node.id.startswith("__") or node.id in FORBIDDEN_NAMES:
            raise ValueError(f"disallowed name: {node.id}")
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute):
        if node.attr.startswith("__") or node.attr in FORBIDDEN_ATTRIBUTES:
            raise ValueError(f"disallowed attribute: {node.attr}")
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call):
        if isinstance(node.func, ast.Name) and node.func.id in FORBIDDEN_NAMES:
            raise ValueError(f"disallowed function call: {node.func.id}")
        if isinstance(node.func, ast.Attribute) and node.func.attr in FORBIDDEN_ATTRIBUTES:
            raise ValueError(f"disallowed method call: {node.func.attr}")
        self.generic_visit(node)


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", str(text)).strip()
