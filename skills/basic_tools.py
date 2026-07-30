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


def percentage_calculator(text: str) -> str:
    try:
        numbers = _numbers_from_text(text)
        if not numbers:
            return "Error: no numeric value found for percentage calculation."
        lowered = text.lower()
        if len(numbers) >= 2:
            percent_match = re.search(r"([-+]?\d+(?:\.\d+)?)\s*%", lowered)
            percent_first = bool(percent_match and float(percent_match.group(1)) == numbers[0])
            if percent_first:
                percent, base = numbers[0], numbers[1]
            else:
                base, percent = numbers[0], numbers[1]
            if any(word in lowered for word in ["increase", "increased", "raise"]):
                return f"Percentage: {base:g} increased by {percent:g}% = {base * (1 + percent / 100):g}"
            if any(word in lowered for word in ["decrease", "decreased", "discount", "reduce"]):
                return f"Percentage: {base:g} decreased by {percent:g}% = {base * (1 - percent / 100):g}"
            if any(word in lowered for word in ["of", "percent of", "% of"]):
                if percent_first:
                    return f"Percentage: {percent:g}% of {base:g} = {percent * base / 100:g}"
                return f"Percentage: {base:g} is {base / percent * 100:g}% of {percent:g}"
            return f"Percentage: {numbers[0]:g} is {numbers[0] / numbers[1] * 100:g}% of {numbers[1]:g}"
        return "Error: percentage calculation needs at least two numbers."
    except Exception as exc:
        return f"Error: percentage calculation failed: {exc}"


def statistics_calculator(text: str) -> str:
    try:
        numbers = _numbers_from_text(text)
        if not numbers:
            return "Error: no numbers found for statistics calculation."
        ordered = sorted(numbers)
        count = len(numbers)
        mean = sum(numbers) / count
        median = (
            ordered[count // 2]
            if count % 2
            else (ordered[count // 2 - 1] + ordered[count // 2]) / 2
        )
        lowered = text.lower()
        if "sum" in lowered:
            return f"Statistics: sum={sum(numbers):g}"
        if "median" in lowered and "mean" not in lowered:
            return f"Statistics: median={median:g}"
        if "mean" in lowered or "average" in lowered:
            return f"Statistics: mean={mean:g}, median={median:g}, count={count}"
        return f"Statistics: mean={mean:g}, median={median:g}, min={min(numbers):g}, max={max(numbers):g}, count={count}"
    except Exception as exc:
        return f"Error: statistics calculation failed: {exc}"


def date_difference_calculator(text: str) -> str:
    try:
        from datetime import date

        matches = re.findall(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b", text)
        if len(matches) < 2:
            return "Error: date difference needs two dates in YYYY-MM-DD format."
        first = date(*(int(part) for part in matches[0]))
        second = date(*(int(part) for part in matches[1]))
        days = abs((second - first).days)
        return f"Date difference: {days} days"
    except Exception as exc:
        return f"Error: date difference calculation failed: {exc}"


def regex_extractor(text: str) -> str:
    emails = re.findall(r"[\w.\-+]+@[\w.\-]+\.\w+", text)
    dates = re.findall(r"\b\d{4}-\d{1,2}-\d{1,2}\b|\b\d{1,2}/\d{1,2}/\d{2,4}\b", text)
    phone_text = text
    for date_value in dates:
        phone_text = phone_text.replace(date_value, " ")
    phones = re.findall(r"(?<!\d)(?:\+?\d[\d\- ]{7,}\d)(?!\d)", phone_text)
    urls = re.findall(r"https?://[^\s,]+", text)
    parts = []
    if emails:
        parts.append("emails=" + ", ".join(emails))
    if dates:
        parts.append("dates=" + ", ".join(dates))
    if phones:
        parts.append("phones=" + ", ".join(phones))
    if urls:
        parts.append("urls=" + ", ".join(urls))
    return "Regex matches: " + ("; ".join(parts) if parts else "none")


def entity_extractor(text: str) -> str:
    entities = []
    patterns = [
        ("person", r"\b(?:Alice|Bob|Carol|David|Dr\. Smith|Professor Lee)\b"),
        ("organization", r"\b(?:OpenAI|Tsinghua University|MIT|Google|SkillBench|NASA)\b"),
        ("location", r"\b(?:Beijing|Shanghai|New York|London|Paris|China|USA)\b"),
    ]
    for label, pattern in patterns:
        values = re.findall(pattern, text)
        if values:
            entities.append(f"{label}=" + ", ".join(dict.fromkeys(values)))
    return "Entities: " + ("; ".join(entities) if entities else "none")


def topic_classifier(text: str) -> str:
    lowered = text.lower()
    topics = {
        "machine_learning": {"model", "training", "dataset", "neural", "retrieval", "agent"},
        "finance": {"stock", "market", "revenue", "profit", "investment", "price"},
        "health": {"medical", "patient", "doctor", "disease", "treatment", "health"},
        "education": {"student", "course", "teacher", "exam", "learning", "school"},
        "software": {"code", "python", "api", "database", "system", "software"},
    }
    scores = {
        topic: sum(1 for word in words if word in lowered)
        for topic, words in topics.items()
    }
    best = max(scores, key=scores.get)
    if scores[best] == 0:
        best = "general"
    return f"Topic: {best}"


def intent_classifier(text: str) -> str:
    lowered = text.lower()
    if any(word in lowered for word in ["translate", "convert into", "in chinese", "in english"]):
        intent = "translation_request"
    elif any(word in lowered for word in ["calculate", "compute", "how many", "what is"]):
        intent = "calculation_request"
    elif any(word in lowered for word in ["summarize", "summary", "shorten"]):
        intent = "summarization_request"
    elif any(word in lowered for word in ["extract", "find emails", "find dates"]):
        intent = "information_extraction_request"
    elif any(word in lowered for word in ["rewrite", "fix grammar", "make it formal"]):
        intent = "editing_request"
    else:
        intent = "general_question"
    return f"Intent: {intent}"


def grammar_corrector(text: str) -> str:
    corrected = _normalize_text(text)
    replacements = {
        r"\bi has\b": "I have",
        r"\bshe go\b": "she goes",
        r"\bhe go\b": "he goes",
        r"\bthey is\b": "they are",
        r"\bwe was\b": "we were",
        r"\ba agent\b": "an agent",
    }
    for pattern, replacement in replacements.items():
        corrected = re.sub(pattern, replacement, corrected, flags=re.IGNORECASE)
    if corrected and corrected[0].islower():
        corrected = corrected[0].upper() + corrected[1:]
    if corrected and corrected[-1] not in ".!?":
        corrected += "."
    return f"Grammar corrected: {corrected or 'empty input.'}"


def tone_converter(text: str) -> str:
    lowered = text.lower()
    content = re.sub(r"\b(make it|rewrite as|tone:|formal|friendly|polite)\b", "", text, flags=re.IGNORECASE)
    content = _normalize_text(content).strip(":, ")
    if "formal" in lowered or "polite" in lowered:
        return f"Formal tone: Please note that {content}."
    if "friendly" in lowered:
        return f"Friendly tone: {content}! Happy to help."
    return f"Tone converted: {content}"


def outline_generator(text: str) -> str:
    cleaned = _normalize_text(text)
    topic = re.sub(r"^(make|create|generate)?\s*(an?\s*)?outline\s*(for|about|on)?", "", cleaned, flags=re.IGNORECASE).strip(":,. ")
    if not topic:
        topic = cleaned or "the topic"
    return f"Outline: 1. Introduction to {topic}; 2. Key points; 3. Method or evidence; 4. Conclusion."


def citation_formatter(text: str) -> str:
    cleaned = _normalize_text(text)
    year = re.search(r"\b(19|20)\d{2}\b", cleaned)
    quoted_title = re.search(r'"([^"]+)"', cleaned)
    title_match = re.search(r"title[: ]+(.+?)(?:\s+year[: ]|\s+author[: ]|$)", cleaned, flags=re.IGNORECASE)
    title = quoted_title.group(1) if quoted_title else (title_match.group(1).strip(" .") if title_match else "Untitled work")
    author_match = re.search(r"(?:by|author[: ]+)([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)*)", cleaned)
    author = author_match.group(1) if author_match else "Unknown Author"
    rendered_year = year.group(0) if year else "n.d."
    return f"Citation: {author} ({rendered_year}). {title}."


def table_formatter(text: str) -> str:
    rows = []
    for chunk in re.split(r";|\n", text):
        if ":" in chunk:
            key, value = chunk.split(":", 1)
            rows.append((key.strip(), value.strip()))
    if not rows:
        items = [item.strip() for item in re.split(r",", text) if item.strip()]
        rows = [(f"item_{index}", item) for index, item in enumerate(items, start=1)]
    if not rows:
        return "Table:\n| field | value |\n| --- | --- |\n| empty | empty |"
    lines = ["Table:", "| field | value |", "| --- | --- |"]
    lines.extend(f"| {key} | {value} |" for key, value in rows)
    return "\n".join(lines)


def ratio_calculator(text: str) -> str:
    try:
        numbers = _numbers_from_text(text)
        if len(numbers) < 2:
            return "Error: ratio calculation needs at least two numbers."
        first, second = numbers[0], numbers[1]
        if second == 0:
            return "Error: ratio denominator cannot be zero."
        divisor = math.gcd(int(abs(first)), int(abs(second))) if first.is_integer() and second.is_integer() else 1
        if divisor > 1:
            simplified = f"{int(first / divisor)}:{int(second / divisor)}"
        else:
            simplified = f"{first:g}:{second:g}"
        return f"Ratio: {first:g}:{second:g} = {simplified}; decimal={first / second:g}"
    except Exception as exc:
        return f"Error: ratio calculation failed: {exc}"


def equation_solver(text: str) -> str:
    try:
        cleaned = _normalize_text(text)
        equation_match = re.search(r"([-+*/().\dxX\s]+=[-+*/().\dxX\s]+)", cleaned)
        equation = equation_match.group(1) if equation_match else cleaned
        equation = re.sub(r"^(solve|find x for|equation)[: ]+", "", equation, flags=re.IGNORECASE)
        match = re.search(r"(.+?)=(.+)", equation)
        if not match:
            return "Error: equation solver needs a linear equation like 2*x + 3 = 11."
        left, right = match.group(1).strip(), match.group(2).strip()
        x0 = _safe_eval_linear_expr(left, 0) - _safe_eval_linear_expr(right, 0)
        x1 = _safe_eval_linear_expr(left, 1) - _safe_eval_linear_expr(right, 1)
        coeff = x1 - x0
        if abs(coeff) < 1e-12:
            return "Error: equation has no unique linear solution."
        solution = -x0 / coeff
        return f"Equation solution: x={solution:g}"
    except Exception as exc:
        return f"Error: equation solving failed: {exc}"


def number_sequence_analyzer(text: str) -> str:
    numbers = _numbers_from_text(text)
    if len(numbers) < 3:
        return "Error: sequence analysis needs at least three numbers."
    diffs = [numbers[index + 1] - numbers[index] for index in range(len(numbers) - 1)]
    ratios = [
        numbers[index + 1] / numbers[index]
        for index in range(len(numbers) - 1)
        if numbers[index] != 0
    ]
    if diffs and all(abs(diff - diffs[0]) < 1e-9 for diff in diffs):
        next_value = numbers[-1] + diffs[0]
        return f"Sequence: arithmetic difference={diffs[0]:g}; next={next_value:g}"
    if len(ratios) == len(numbers) - 1 and all(abs(ratio - ratios[0]) < 1e-9 for ratio in ratios):
        next_value = numbers[-1] * ratios[0]
        return f"Sequence: geometric ratio={ratios[0]:g}; next={next_value:g}"
    return f"Sequence: differences={', '.join(f'{diff:g}' for diff in diffs)}"


def range_filter(text: str) -> str:
    numbers = _numbers_from_text(text)
    if not numbers:
        return "Error: range filter needs numbers."
    lowered = text.lower()
    range_match = re.search(r"(?:between|from)\s+([-+]?\d+(?:\.\d+)?)\s+(?:and|to)\s+([-+]?\d+(?:\.\d+)?)", lowered)
    if range_match:
        low, high = sorted((float(range_match.group(1)), float(range_match.group(2))))
        values = list(numbers)
        for bound in (float(range_match.group(1)), float(range_match.group(2))):
            for index, value in enumerate(values):
                if abs(value - bound) < 1e-9:
                    values.pop(index)
                    break
        kept = [value for value in values if low <= value <= high]
    elif "above" in lowered or "greater than" in lowered:
        threshold_match = re.search(r"(?:above|greater than)\s+([-+]?\d+(?:\.\d+)?)", lowered)
        threshold = float(threshold_match.group(1)) if threshold_match else numbers[-1]
        values = list(numbers)
        for index, value in enumerate(values):
            if abs(value - threshold) < 1e-9:
                values.pop(index)
                break
        kept = [value for value in values if value > threshold]
        return "Filtered values: " + (", ".join(f"{value:g}" for value in kept) if kept else "none")
    elif "below" in lowered or "less than" in lowered:
        threshold_match = re.search(r"(?:below|less than)\s+([-+]?\d+(?:\.\d+)?)", lowered)
        threshold = float(threshold_match.group(1)) if threshold_match else numbers[-1]
        values = list(numbers)
        for index, value in enumerate(values):
            if abs(value - threshold) < 1e-9:
                values.pop(index)
                break
        kept = [value for value in values if value < threshold]
        return "Filtered values: " + (", ".join(f"{value:g}" for value in kept) if kept else "none")
    else:
        if len(numbers) < 3:
            return "Error: provide values plus a low and high range."
        values, low, high = numbers[:-2], min(numbers[-2:]), max(numbers[-2:])
        kept = [value for value in values if low <= value <= high]
        return "Filtered values: " + (", ".join(f"{value:g}" for value in kept) if kept else "none")
    return "Filtered values: " + (", ".join(f"{value:g}" for value in kept) if kept else "none")


def list_sorter(text: str) -> str:
    items = _split_items(text)
    if not items:
        return "Sorted list: empty input."
    reverse = any(word in text.lower() for word in ["descending", "desc", "reverse", "largest"])
    numeric_values = []
    all_numeric = True
    for item in items:
        try:
            numeric_values.append(float(item))
        except ValueError:
            all_numeric = False
            break
    if all_numeric:
        ordered = sorted(numeric_values, reverse=reverse)
        rendered = ", ".join(f"{value:g}" for value in ordered)
    else:
        ordered = sorted(items, key=str.lower, reverse=reverse)
        rendered = ", ".join(ordered)
    return f"Sorted list: {rendered}"


def deduplicator(text: str) -> str:
    items = _split_items(text)
    if not items:
        return "Deduplicated items: empty input."
    seen = set()
    unique = []
    for item in items:
        key = item.lower()
        if key not in seen:
            seen.add(key)
            unique.append(item)
    return "Deduplicated items: " + ", ".join(unique)


def json_validator(text: str) -> str:
    import json

    cleaned = _normalize_text(text)
    match = re.search(r"(\{.*\}|\[.*\])", cleaned)
    candidate = match.group(1) if match else cleaned
    try:
        parsed = json.loads(candidate)
    except Exception as exc:
        return f"JSON invalid: {exc}"
    return f"JSON valid: type={type(parsed).__name__}"


def csv_summarizer(text: str) -> str:
    import csv

    cleaned = str(text).strip()
    if not cleaned:
        return "CSV summary: empty input."
    try:
        rows = list(csv.reader(io.StringIO(cleaned)))
        if not rows:
            return "CSV summary: empty input."
        header = rows[0]
        data_rows = rows[1:]
        numeric_columns = []
        for column_index, name in enumerate(header):
            values = []
            for row in data_rows:
                if column_index < len(row):
                    try:
                        values.append(float(row[column_index]))
                    except ValueError:
                        pass
            if values:
                numeric_columns.append(f"{name}:sum={sum(values):g},mean={sum(values)/len(values):g}")
        details = "; ".join(numeric_columns) if numeric_columns else "no numeric columns"
        return f"CSV summary: rows={len(data_rows)}, columns={len(header)}; {details}"
    except Exception as exc:
        return f"Error: CSV summarization failed: {exc}"


def language_detector(text: str) -> str:
    cleaned = str(text)
    if re.search(r"[\u4e00-\u9fff]", cleaned):
        language = "Chinese"
    elif re.search(r"[A-Za-z]", cleaned):
        language = "English"
    elif re.search(r"\d", cleaned):
        language = "numeric_or_symbolic"
    else:
        language = "unknown"
    return f"Language: {language}"


def readability_scorer(text: str) -> str:
    cleaned = _normalize_text(text)
    if not cleaned:
        return "Readability: empty input."
    sentences = [part for part in re.split(r"[.!?]+", cleaned) if part.strip()]
    words = re.findall(r"[A-Za-z]+", cleaned)
    if not words:
        return "Readability: non-English or no word tokens."
    avg_words = len(words) / max(1, len(sentences))
    avg_chars = sum(len(word) for word in words) / len(words)
    if avg_words <= 12 and avg_chars <= 5.5:
        label = "easy"
    elif avg_words <= 20:
        label = "medium"
    else:
        label = "hard"
    return f"Readability: {label}; avg_words_per_sentence={avg_words:g}; avg_chars_per_word={avg_chars:g}"


def title_generator(text: str) -> str:
    cleaned = _normalize_text(text)
    if not cleaned:
        return "Title: Untitled"
    keywords = re.findall(r"[A-Za-z][A-Za-z0-9_-]+", cleaned)
    stop = {"the", "and", "for", "with", "this", "that", "from", "into", "about"}
    selected = [word.capitalize() for word in keywords if word.lower() not in stop][:7]
    if not selected:
        selected = cleaned.split()[:7]
    return "Title: " + " ".join(selected)


def question_generator(text: str) -> str:
    cleaned = _normalize_text(text)
    if not cleaned:
        return "Questions: no input."
    topic = cleaned.rstrip(".")
    return (
        "Questions: "
        f"1. What is the main idea of {topic}? "
        f"2. Why does {topic} matter? "
        f"3. What evidence supports {topic}?"
    )


def checklist_generator(text: str) -> str:
    cleaned = _normalize_text(text)
    topic = re.sub(r"^(make|create|generate)?\s*(a\s*)?checklist\s*(for|about|on)?", "", cleaned, flags=re.IGNORECASE).strip(":,. ")
    if not topic:
        topic = cleaned or "the task"
    return f"Checklist: [ ] Define {topic}; [ ] Prepare inputs; [ ] Run the process; [ ] Verify outputs."


def pros_cons_analyzer(text: str) -> str:
    cleaned = _normalize_text(text)
    topic = cleaned or "the option"
    return f"Pros/Cons: Pros - {topic} may improve coverage and clarity. Cons - {topic} may add complexity and cost."


def argument_mapper(text: str) -> str:
    cleaned = _normalize_text(text)
    if not cleaned:
        return "Argument map: no claim provided."
    claim_match = re.search(r"(?:claim|argument)[: ]+(.+?)(?:\s+(?:because|evidence)[: ]+|$)", cleaned, flags=re.IGNORECASE)
    evidence_match = re.search(r"(?:because|evidence)[: ]+(.+)", cleaned, flags=re.IGNORECASE)
    claim = claim_match.group(1).strip(" .") if claim_match else cleaned
    evidence = evidence_match.group(1).strip(" .") if evidence_match else "not specified"
    return f"Argument map: claim={claim}; evidence={evidence}; relation=supports"


def email_drafter(text: str) -> str:
    cleaned = _normalize_text(text)
    recipient_match = re.search(r"(?:to|for)[: ]+([A-Za-z][A-Za-z .-]*?)(?:\s+about\b|$)", cleaned, flags=re.IGNORECASE)
    recipient = recipient_match.group(1).strip() if recipient_match else "there"
    topic_match = re.search(r"\babout\s+(.+)", cleaned, flags=re.IGNORECASE)
    topic = topic_match.group(1).strip(":,. ") if topic_match else re.sub(
        r"^(draft|write|compose)?\s*(an?\s*)?email\s*(to|for)?",
        "",
        cleaned,
        flags=re.IGNORECASE,
    ).strip(":,. ")
    if not topic:
        topic = cleaned or "the request"
    return f"Email draft: Dear {recipient}, I am writing about {topic}. Please let me know if this works. Best regards."


def todo_extractor(text: str) -> str:
    cleaned = _normalize_text(text)
    patterns = [
        r"\b(?:todo|task|action item)[: ]+([^.;]+)",
        r"\b(?:need to|must|should|remember to)\s+([^.;]+)",
    ]
    todos = []
    for pattern in patterns:
        todos.extend(match.strip() for match in re.findall(pattern, cleaned, flags=re.IGNORECASE))
    if not todos:
        todos = [part.strip() for part in re.split(r";|\n", cleaned) if part.strip().lower().startswith(("-", "[ ]"))]
    return "Todos: " + ("; ".join(dict.fromkeys(todos)) if todos else "none")


def meeting_notes_extractor(text: str) -> str:
    cleaned = _normalize_text(text)
    decisions = re.findall(r"(?:decision|decided)[: ]+([^.;]+)", cleaned, flags=re.IGNORECASE)
    actions = re.findall(r"(?:action|todo|owner)[: ]+([^.;]+)", cleaned, flags=re.IGNORECASE)
    dates = re.findall(r"\b\d{4}-\d{1,2}-\d{1,2}\b", cleaned)
    parts = [
        "decisions=" + (", ".join(decisions) if decisions else "none"),
        "actions=" + (", ".join(actions) if actions else "none"),
        "dates=" + (", ".join(dates) if dates else "none"),
    ]
    return "Meeting notes: " + "; ".join(parts)


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


def _numbers_from_text(text: str) -> list[float]:
    return [float(match) for match in re.findall(r"[-+]?\d+(?:\.\d+)?", str(text))]


def _split_items(text: str) -> list[str]:
    cleaned = _normalize_text(text)
    cleaned = re.sub(
        r"^(sort|order|deduplicate|remove duplicates from|unique items from|remove repeated skills from)[^:]*:\s*",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"^(sort|order|deduplicate|remove duplicates from|unique items from|remove repeated skills from)\s+", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(
        r"\b(?:ascending|descending|asc|desc|reverse|largest first|smallest first|alphabetically)\b",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    items = [item.strip(" -[].") for item in re.split(r",|;|\n", cleaned) if item.strip(" -[].")]
    if len(items) <= 1:
        items = re.findall(r"[-+]?\d+(?:\.\d+)?|[A-Za-z][A-Za-z0-9_-]+", cleaned)
    return items


def _safe_eval_linear_expr(expression: str, x_value: float) -> float:
    prepared = re.sub(r"\bx\b", f"({x_value})", expression)
    tree = ast.parse(prepared, mode="eval")
    value = _eval_math_node(tree)
    if not isinstance(value, (int, float)):
        raise ValueError("linear expression did not evaluate to a number")
    return float(value)
