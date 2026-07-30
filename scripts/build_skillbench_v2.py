import json
from collections import Counter
from pathlib import Path

try:
    from build_skillbench_dev import NEW_DEV_TASKS, abstain_task, tool_task
except ModuleNotFoundError:
    from scripts.build_skillbench_dev import NEW_DEV_TASKS, abstain_task, tool_task


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MINI_PATH = PROJECT_ROOT / "data" / "skillbench_mini.json"
DEV_PATH = PROJECT_ROOT / "data" / "skillbench_dev.json"
HARD_PATH = PROJECT_ROOT / "data" / "skillbench_hard.json"
HIDDEN_PATH = PROJECT_ROOT / "data" / "skillbench_hidden.json"
HIDDEN_KEY_PATH = PROJECT_ROOT / "data" / "skillbench_hidden_answer_key.json"


SOURCES = [
    "MetaTool_tool_decision",
    "BFCL_irrelevance",
    "BFCL_missing_param",
    "BFCL_missing_func",
    "APIBank_level1",
    "APIBank_level2",
    "ToolBench_trajectory_taxonomy",
    "StableToolBench_evaluation_setting",
]


SINGLE_SPECS = [
    {
        "skill": "calculator",
        "category": "arithmetic_numeric",
        "instruction": "Compute (9 + 6) * 3.",
        "expected": "45",
        "arguments": ["9", "6", "3"],
        "observations": ["45"],
        "hard_negatives": ["percentage_calculator", "ratio_calculator", "statistics_calculator"],
    },
    {
        "skill": "percentage_calculator",
        "category": "arithmetic_numeric",
        "instruction": "A survey has 36 successful runs out of 144; compute the percentage.",
        "expected": "25%",
        "arguments": ["36", "144"],
        "observations": ["25"],
        "hard_negatives": ["calculator", "ratio_calculator", "statistics_calculator"],
    },
    {
        "skill": "ratio_calculator",
        "category": "arithmetic_numeric",
        "instruction": "Simplify the ratio 42 to 56.",
        "expected": "3:4",
        "arguments": ["42", "56"],
        "observations": ["3:4"],
        "hard_negatives": ["calculator", "percentage_calculator", "statistics_calculator"],
    },
    {
        "skill": "equation_solver",
        "category": "arithmetic_numeric",
        "instruction": "Find x for 7*x - 14 = 21.",
        "expected": "x=5",
        "arguments": ["7*x", "21"],
        "observations": ["x=5"],
        "hard_negatives": ["calculator", "statistics_calculator"],
    },
    {
        "skill": "statistics_calculator",
        "category": "arithmetic_numeric",
        "instruction": "For the values 5, 9, 13, 17, report the mean and median.",
        "expected": "mean=11, median=11",
        "arguments": ["5", "9", "13", "17"],
        "observations": ["mean=11", "median=11"],
        "hard_negatives": ["calculator", "number_sequence_analyzer"],
    },
    {
        "skill": "number_sequence_analyzer",
        "category": "arithmetic_numeric",
        "instruction": "Continue the sequence 6, 12, 18, 24.",
        "expected": "next=30",
        "arguments": ["6", "12", "18", "24"],
        "observations": ["next=30"],
        "hard_negatives": ["statistics_calculator", "calculator"],
    },
    {
        "skill": "unit_converter",
        "category": "conversion_time",
        "instruction": "Convert 3.5 kg to g.",
        "expected": "3500 g",
        "arguments": ["3.5", "kg", "g"],
        "observations": ["3500", "g"],
        "hard_negatives": ["calculator", "percentage_calculator"],
    },
    {
        "skill": "date_difference_calculator",
        "category": "conversion_time",
        "instruction": "How many days are between 2026-03-01 and 2026-03-18?",
        "expected": "17 days",
        "arguments": ["2026-03-01", "2026-03-18"],
        "observations": ["17 days"],
        "hard_negatives": ["calculator", "statistics_calculator"],
    },
    {
        "skill": "range_filter",
        "category": "list_data_ops",
        "instruction": "Keep values between 10 and 20 from 4, 10, 12, 20, 25.",
        "expected": "10, 12, 20",
        "arguments": ["4", "10", "12", "20", "25"],
        "observations": ["10", "12", "20"],
        "hard_negatives": ["list_sorter", "statistics_calculator"],
    },
    {
        "skill": "list_sorter",
        "category": "list_data_ops",
        "instruction": "Sort these labels alphabetically: retriever, agent, benchmark.",
        "expected": "agent, benchmark, retriever",
        "arguments": ["retriever", "agent", "benchmark"],
        "observations": ["agent", "benchmark", "retriever"],
        "hard_negatives": ["deduplicator", "range_filter"],
    },
    {
        "skill": "deduplicator",
        "category": "list_data_ops",
        "instruction": "Remove duplicates from: bm25, embedding, bm25, full, embedding.",
        "expected": "bm25, embedding, full",
        "arguments": ["bm25", "embedding", "full"],
        "observations": ["bm25", "embedding", "full"],
        "hard_negatives": ["list_sorter", "keyword_extractor"],
    },
    {
        "skill": "json_validator",
        "category": "structured_formatting",
        "instruction": "Validate this JSON string: {\"agent\":\"v2\",\"valid\":true}",
        "expected": "JSON valid",
        "arguments": ["agent", "valid"],
        "observations": ["JSON valid"],
        "hard_negatives": ["table_formatter", "csv_summarizer"],
    },
    {
        "skill": "csv_summarizer",
        "category": "structured_formatting",
        "instruction": "Summarize CSV rows:\nname,score\nKai,8\nLin,10",
        "expected": "rows=2, columns=2",
        "arguments": ["name,score", "Kai,8", "Lin,10"],
        "observations": ["rows=2", "columns=2"],
        "hard_negatives": ["table_formatter", "json_validator"],
    },
    {
        "skill": "language_detector",
        "category": "classification",
        "instruction": "Detect the language of this text: Skill retrieval baseline.",
        "expected": "English",
        "arguments": ["Skill retrieval baseline"],
        "observations": ["English"],
        "hard_negatives": ["translator_en_zh", "intent_classifier"],
    },
    {
        "skill": "readability_scorer",
        "category": "classification",
        "instruction": "Estimate readability: This agent uses tools. It checks outputs.",
        "expected": "Readability",
        "arguments": ["agent uses tools"],
        "observations": ["Readability"],
        "hard_negatives": ["summarizer", "text_rewriter"],
    },
    {
        "skill": "title_generator",
        "category": "transformation_generation",
        "instruction": "Create a title for: tool contracts improve skill calling.",
        "expected": "Title",
        "arguments": ["tool contracts improve skill calling"],
        "observations": ["Title"],
        "hard_negatives": ["summarizer", "outline_generator"],
    },
    {
        "skill": "question_generator",
        "category": "transformation_generation",
        "instruction": "Generate study questions about no-tool decisions.",
        "expected": "Questions",
        "arguments": ["no-tool decisions"],
        "observations": ["Questions"],
        "hard_negatives": ["outline_generator", "checklist_generator"],
    },
    {
        "skill": "checklist_generator",
        "category": "transformation_generation",
        "instruction": "Create a checklist for running an ablation experiment.",
        "expected": "Checklist",
        "arguments": ["ablation experiment"],
        "observations": ["Checklist"],
        "hard_negatives": ["todo_extractor", "outline_generator"],
    },
    {
        "skill": "pros_cons_analyzer",
        "category": "transformation_generation",
        "instruction": "Give pros and cons of using embedding retrieval.",
        "expected": "Pros/Cons",
        "arguments": ["embedding retrieval"],
        "observations": ["Pros/Cons"],
        "hard_negatives": ["summarizer", "argument_mapper"],
    },
    {
        "skill": "argument_mapper",
        "category": "transformation_generation",
        "instruction": "Map this argument: claim: contracts improve agents because they clarify inputs.",
        "expected": "Argument map",
        "arguments": ["contracts improve agents", "clarify inputs"],
        "observations": ["Argument map"],
        "hard_negatives": ["pros_cons_analyzer", "summarizer"],
    },
    {
        "skill": "email_drafter",
        "category": "transformation_generation",
        "instruction": "Draft an email to Professor Lee about SkillBench results.",
        "expected": "Email draft",
        "arguments": ["Professor Lee", "SkillBench results"],
        "observations": ["Email draft"],
        "hard_negatives": ["tone_converter", "text_rewriter"],
    },
    {
        "skill": "todo_extractor",
        "category": "extraction",
        "instruction": "Extract todos: We need to inspect Dev; remember to export metrics.",
        "expected": "Todos",
        "arguments": ["inspect Dev", "export metrics"],
        "observations": ["Todos"],
        "hard_negatives": ["keyword_extractor", "meeting_notes_extractor"],
    },
    {
        "skill": "meeting_notes_extractor",
        "category": "extraction",
        "instruction": "Extract meeting notes: decision: keep BM25; action: rerun Hard on 2026-08-05.",
        "expected": "Meeting notes",
        "arguments": ["decision", "action", "2026-08-05"],
        "observations": ["Meeting notes"],
        "hard_negatives": ["todo_extractor", "regex_extractor"],
    },
    {
        "skill": "translator_zh_en",
        "category": "translation",
        "instruction": "Translate into English: 浣犲ソ skill agent",
        "expected": "hello skill agent",
        "arguments": ["浣犲ソ", "skill agent"],
        "observations": ["placeholder"],
        "hard_negatives": ["translator_en_zh", "language_detector"],
    },
    {
        "skill": "translator_en_zh",
        "category": "translation",
        "instruction": "Translate into Chinese: hello skill agent",
        "expected": "Chinese translation",
        "arguments": ["hello", "skill", "agent"],
        "observations": ["浣"],
        "hard_negatives": ["translator_zh_en", "language_detector"],
    },
    {
        "skill": "keyword_extractor",
        "category": "extraction",
        "instruction": "Extract keywords from: retrieval-aware contracts reduce wrong tool calls.",
        "expected": "Keywords",
        "arguments": ["retrieval-aware contracts"],
        "observations": ["Keywords"],
        "hard_negatives": ["entity_extractor", "regex_extractor"],
    },
    {
        "skill": "regex_extractor",
        "category": "extraction",
        "instruction": "Extract emails and dates from: lab@example.com on 2026-10-11.",
        "expected": "lab@example.com, 2026-10-11",
        "arguments": ["lab@example.com", "2026-10-11"],
        "observations": ["lab@example.com", "2026-10-11"],
        "hard_negatives": ["keyword_extractor", "entity_extractor"],
    },
    {
        "skill": "entity_extractor",
        "category": "extraction",
        "instruction": "Extract people, organizations, and locations: Alice joined OpenAI in Beijing.",
        "expected": "Alice, OpenAI, Beijing",
        "arguments": ["Alice", "OpenAI", "Beijing"],
        "observations": ["Alice", "OpenAI", "Beijing"],
        "hard_negatives": ["keyword_extractor", "regex_extractor"],
    },
    {
        "skill": "topic_classifier",
        "category": "classification",
        "instruction": "Classify the topic: neural retrieval models use datasets and training.",
        "expected": "machine_learning",
        "arguments": ["neural retrieval models"],
        "observations": ["machine_learning"],
        "hard_negatives": ["intent_classifier", "keyword_extractor"],
    },
    {
        "skill": "intent_classifier",
        "category": "classification",
        "instruction": "Classify the intent: please translate this sentence into Chinese.",
        "expected": "translation_request",
        "arguments": ["translate this sentence"],
        "observations": ["translation_request"],
        "hard_negatives": ["translator_en_zh", "topic_classifier"],
    },
    {
        "skill": "sentiment_analyzer",
        "category": "classification",
        "instruction": "Analyze sentiment: I love the stable benchmark but hate slow runs.",
        "expected": "neutral",
        "arguments": ["love", "hate"],
        "observations": ["Sentiment"],
        "hard_negatives": ["tone_converter", "intent_classifier"],
    },
    {
        "skill": "text_rewriter",
        "category": "transformation_generation",
        "instruction": "Rewrite clearly: contracts help agents choose tools",
        "expected": "Rewritten",
        "arguments": ["contracts help agents choose tools"],
        "observations": ["Rewritten"],
        "hard_negatives": ["grammar_corrector", "tone_converter"],
    },
    {
        "skill": "grammar_corrector",
        "category": "transformation_generation",
        "instruction": "Fix grammar: we was testing a agent.",
        "expected": "we were testing an agent",
        "arguments": ["we was", "a agent"],
        "observations": ["we were", "an agent"],
        "hard_negatives": ["text_rewriter", "tone_converter"],
    },
    {
        "skill": "tone_converter",
        "category": "transformation_generation",
        "instruction": "Make this formal: send the logs now.",
        "expected": "Formal tone",
        "arguments": ["formal", "send the logs"],
        "observations": ["Formal tone"],
        "hard_negatives": ["email_drafter", "grammar_corrector"],
    },
    {
        "skill": "outline_generator",
        "category": "transformation_generation",
        "instruction": "Create an outline about evaluating skill calling.",
        "expected": "Outline",
        "arguments": ["evaluating skill calling"],
        "observations": ["Outline"],
        "hard_negatives": ["summarizer", "title_generator"],
    },
    {
        "skill": "summarizer",
        "category": "transformation_generation",
        "instruction": "Summarize: A retriever proposes candidate skills. A planner calls one or more skills. Evaluation checks the trace.",
        "expected": "Summary",
        "arguments": ["retriever proposes candidate skills"],
        "observations": ["Summary"],
        "hard_negatives": ["title_generator", "outline_generator"],
    },
    {
        "skill": "paper_qa",
        "category": "code_and_research",
        "instruction": "Answer this paper question: what does the method contribute?",
        "expected": "Paper QA placeholder",
        "arguments": ["method contribute"],
        "observations": ["Paper QA placeholder"],
        "hard_negatives": ["summarizer", "citation_formatter"],
    },
    {
        "skill": "citation_formatter",
        "category": "structured_formatting",
        "instruction": "Format citation: title: Tool Learning Baseline author: Smith year: 2026.",
        "expected": "Smith (2026)",
        "arguments": ["Smith", "2026"],
        "observations": ["Citation"],
        "hard_negatives": ["paper_qa", "regex_extractor"],
    },
    {
        "skill": "table_formatter",
        "category": "structured_formatting",
        "instruction": "Format as a table: method: BM25; score: 0.82.",
        "expected": "Table",
        "arguments": ["method", "BM25", "score"],
        "observations": ["Table"],
        "hard_negatives": ["csv_summarizer", "json_validator"],
    },
    {
        "skill": "python_executor",
        "category": "code_and_research",
        "instruction": "Execute safe Python code: values=[2,4,6]; sum(values)",
        "expected": "12",
        "arguments": ["values", "sum"],
        "observations": ["12"],
        "hard_negatives": ["calculator", "statistics_calculator"],
    },
]


MULTI_PAIRS = [
    ("calculator", "summarizer", "Compute (8 + 4) * 2 and express the result in one short sentence."),
    ("percentage_calculator", "text_rewriter", "A score rose from 80 by 10%; rewrite the computed result clearly."),
    ("ratio_calculator", "table_formatter", "Simplify the ratio 24 to 36 and present the ratio result as a table."),
    ("equation_solver", "summarizer", "Find x for 4*x + 8 = 28 and summarize the solution."),
    ("number_sequence_analyzer", "title_generator", "Continue 3, 6, 9, 12 and give the analysis a concise title."),
    ("unit_converter", "summarizer", "Convert 750 g to kg and state the converted value briefly."),
    ("date_difference_calculator", "summarizer", "Find the days between 2026-04-01 and 2026-04-20 and summarize it."),
    ("range_filter", "table_formatter", "Keep 5 to 15 from 3, 5, 8, 15, 22 and organize the kept values as a table."),
    ("list_sorter", "deduplicator", "Sort alpha, beta, alpha, gamma alphabetically and remove repeated items."),
    ("deduplicator", "table_formatter", "Remove duplicates from bm25, full, bm25, embedding and format the unique methods as a table."),
    ("json_validator", "summarizer", "Check JSON {\"ok\":true,\"task\":\"hard\"} and summarize the validation result."),
    ("csv_summarizer", "table_formatter", "Summarize CSV data name,score; A,1; B,3 and format the summary as a table."),
    ("language_detector", "intent_classifier", "Detect the language and classify the intent: please translate this into Chinese."),
    ("readability_scorer", "text_rewriter", "Score readability for 'Agents call tools. They verify outputs.' and rewrite the text cleanly."),
    ("title_generator", "keyword_extractor", "Give 'contracts guide skill calling' a title and extract keywords from that title."),
    ("question_generator", "checklist_generator", "Generate questions about no-tool gating and turn them into a study checklist."),
    ("checklist_generator", "email_drafter", "Make a checklist for the SkillBench experiment and draft an email about it."),
    ("pros_cons_analyzer", "summarizer", "Analyze pros and cons of embedding retrieval and summarize the result."),
    ("argument_mapper", "table_formatter", "Map claim: contracts help because inputs are explicit, and put the argument map in a table."),
    ("email_drafter", "tone_converter", "Draft an email to Professor Lee about ablation results and make it formal."),
    ("todo_extractor", "table_formatter", "Extract todos from 'must run Hard; remember to save metrics' and put them in a table."),
    ("meeting_notes_extractor", "summarizer", "Extract meeting notes from 'decision: freeze Dev; action: run Hard on 2026-08-01' and summarize them."),
    ("translator_zh_en", "keyword_extractor", "Translate '浣犲ソ skill agent' into English and extract keywords from the translation."),
    ("translator_en_zh", "keyword_extractor", "Translate 'hello skill retrieval' into Chinese and extract keywords from the translation."),
    ("keyword_extractor", "table_formatter", "Extract keywords from 'retrieval contracts reduce wrong calls' and show them in a table."),
    ("regex_extractor", "summarizer", "Find emails and dates in 'kai@example.com 2026-09-09' and summarize what was found."),
    ("entity_extractor", "table_formatter", "Identify entities in 'Alice joined OpenAI in Beijing' and organize them as a table."),
    ("topic_classifier", "outline_generator", "Classify the topic of 'neural retrieval training uses datasets' and outline the topic."),
    ("intent_classifier", "question_generator", "Classify the intent of 'please calculate 2+2' and generate questions about that intent."),
    ("sentiment_analyzer", "tone_converter", "Analyze sentiment of 'I hate unstable runs' and make the statement polite."),
    ("grammar_corrector", "readability_scorer", "Fix grammar in 'they is using a agent' and estimate readability after correction."),
    ("tone_converter", "sentiment_analyzer", "Make 'I hate slow experiments' formal and judge the sentiment afterward."),
    ("outline_generator", "checklist_generator", "Create an outline for strict evaluation and convert it into a checklist."),
    ("summarizer", "title_generator", "Summarize a paragraph about skill retrieval and create a title for the summary."),
    ("paper_qa", "summarizer", "Answer this paper question about the core contribution and summarize the placeholder answer."),
    ("citation_formatter", "keyword_extractor", "Format citation for Smith 2026 Tool Learning and extract keywords from the citation."),
    ("table_formatter", "summarizer", "Format method: BM25; score: 0.82 as a table and summarize the table."),
    ("python_executor", "summarizer", "Run code values=[2,4,6]; sum(values) and summarize the result."),
    ("statistics_calculator", "title_generator", "Compute statistics for 4, 8, 12, 16 and title the analysis."),
    ("unit_converter", "table_formatter", "Convert 250 cm to m and put the conversion result in a table."),
    ("regex_extractor", "todo_extractor", "Extract dates from 'deadline 2026-10-10, must submit report' and pull action items."),
    ("entity_extractor", "email_drafter", "Extract entities from 'Professor Lee at Tsinghua University' and draft an email to the person."),
    ("topic_classifier", "question_generator", "Classify a text about software APIs and make study questions about the topic."),
    ("list_sorter", "table_formatter", "Sort gamma, alpha, beta and show the sorted list in a table."),
    ("deduplicator", "keyword_extractor", "Deduplicate tool, skill, tool, agent and extract keywords from the unique list."),
    ("csv_summarizer", "keyword_extractor", "Summarize CSV 'name,score; A,2; B,5' and extract keywords from the summary."),
    ("json_validator", "table_formatter", "Validate JSON {\"method\":\"bm25\"} and put the validation result in a table."),
    ("readability_scorer", "summarizer", "Score readability of a short agent paragraph and summarize the score."),
    ("argument_mapper", "email_drafter", "Map the argument that contracts reduce errors and draft an email about the claim."),
    ("pros_cons_analyzer", "table_formatter", "List pros and cons of rule-based final answers and format them as a table."),
]


NO_TOOL_PROMPTS = [
    ("Explain why the word convert can appear in a concept question without requiring unit conversion.", ["unit_converter"]),
    ("What does it mean for a benchmark to have hard negatives? Do not extract anything.", ["keyword_extractor"]),
    ("Why might a model choose a wrong translation direction? Do not translate.", ["translator_zh_en", "translator_en_zh"]),
    ("Describe why exact skill sequence accuracy is stricter than selection accuracy.", ["summarizer"]),
    ("Define argument correctness in tool calling without running a tool.", ["python_executor"]),
    ("Why can an email drafting tool not send a real email?", ["email_drafter"]),
    ("Explain how no-tool examples help evaluate agents.", ["intent_classifier"]),
    ("What is the difference between validating JSON and formatting a table?", ["json_validator", "table_formatter"]),
    ("Why should final answers be grounded in observations?", ["summarizer"]),
    ("Give a conceptual reason that retrieval recall alone is not enough.", ["keyword_extractor"]),
    ("Explain what an unsupported tool request means.", ["intent_classifier"]),
    ("Why are missing parameters dangerous for tool calls?", ["calculator"]),
    ("Describe sequence planning in one paragraph.", ["outline_generator"]),
    ("What does 'tool overcall' mean in evaluation?", ["todo_extractor"]),
    ("Why should benchmark hidden sets not be used for prompt tuning?", ["paper_qa"]),
    ("Explain the difference between a ratio and a percentage in words only.", ["ratio_calculator", "percentage_calculator"]),
    ("What does a placeholder paper QA skill imply for strict evaluation?", ["paper_qa"]),
    ("Describe why repeating the same task template can overfit an agent.", ["text_rewriter"]),
    ("Why is a hard benchmark useful after Dev tuning?", ["topic_classifier"]),
    ("Define skill contract in plain language.", ["json_validator"]),
    ("Why can a Python executor become a shortcut that hides skill selection errors?", ["python_executor"]),
    ("What makes multi-skill tasks harder than single-skill tasks?", ["checklist_generator"]),
    ("Explain why a table formatter is not a CSV summarizer.", ["table_formatter", "csv_summarizer"]),
    ("Why should an agent ask for clarification when input text is missing?", ["summarizer"]),
    ("What does retrieval-aware mean in a skill library?", ["keyword_extractor"]),
    ("Explain why a user mentioning 'calculate' is not always a calculation request.", ["calculator"]),
    ("What is the role of observations in a ReAct-like loop?", ["paper_qa"]),
    ("Why should unsupported external actions be refused by a local-only agent?", ["python_executor"]),
    ("Describe the difference between sentiment and intent classification.", ["sentiment_analyzer", "intent_classifier"]),
    ("Why do minimal pairs help diagnose similar-skill confusion?", ["ratio_calculator"]),
]


MISSING_PROMPTS = [
    ("Convert the earlier value to kilograms.", ["unit_converter"], r"(value|unit|number|provide|missing)"),
    ("Compute the percentage for that result.", ["percentage_calculator"], r"(part|total|number|value|provide)"),
    ("Solve it for x.", ["equation_solver"], r"(equation|provide|missing)"),
    ("Extract the emails from the passage.", ["regex_extractor"], r"(passage|text|provide)"),
    ("Summarize the article.", ["summarizer"], r"(article|text|provide)"),
    ("Sort those items.", ["list_sorter"], r"(items|list|provide)"),
    ("Validate the JSON I meant.", ["json_validator"], r"(json|string|content|provide)"),
    ("Make it formal.", ["tone_converter"], r"(text|sentence|provide)"),
    ("Draft the email to that professor.", ["email_drafter"], r"(recipient|professor|topic|provide)"),
    ("Find the date difference.", ["date_difference_calculator"], r"(dates|provide|missing)"),
    ("Generate keywords from the title.", ["keyword_extractor"], r"(title|text|provide)"),
    ("Format the data as a table.", ["table_formatter"], r"(data|results|provide)"),
    ("Analyze the meeting notes.", ["meeting_notes_extractor"], r"(meeting|notes|provide)"),
    ("Run the code and show the output.", ["python_executor"], r"(code|provide|missing)"),
    ("Classify the topic of the text.", ["topic_classifier"], r"(text|provide|missing)"),
    ("Give mean and median.", ["statistics_calculator"], r"(numbers|values|provide)"),
    ("Extract entities from the note.", ["entity_extractor"], r"(note|text|provide)"),
]


UNSUPPORTED_PROMPTS = [
    ("Buy a train ticket using my account.", ["intent_classifier"], "ticket"),
    ("Send the final report to GitHub and create a release.", ["python_executor"], "github"),
    ("Open WeChat and message my teammate.", ["email_drafter"], "message"),
    ("Search the live web for today's currency rate.", ["unit_converter"], "live"),
    ("Reserve a hotel room near campus.", ["email_drafter"], "hotel"),
    ("Control PowerPoint and present slides automatically.", ["outline_generator"], "powerpoint"),
    ("Call a remote weather API and return tomorrow's forecast.", ["topic_classifier"], "weather"),
    ("Submit this form on a university website.", ["python_executor"], "website"),
]


def main() -> None:
    seed_tasks = json.loads(MINI_PATH.read_text(encoding="utf-8"))
    dev_tasks = seed_tasks + NEW_DEV_TASKS
    dev_tasks.extend(make_single_tasks("dev", 181, 35, variant_offset=1))
    dev_tasks.extend(make_multi_tasks("dev", 216, 25, pair_offset=0))

    hard_tasks = []
    hard_tasks.extend(make_single_tasks("hard", 1, 50, variant_offset=2))
    hard_tasks.extend(make_multi_tasks("hard", 51, 40, pair_offset=5))
    hard_tasks.extend(make_abstain_tasks("hard", 91, "no_tool", 15, NO_TOOL_PROMPTS, tag="hard_no_tool"))
    hard_tasks.extend(make_abstain_tasks("hard", 106, "missing_info", 10, MISSING_PROMPTS, tag="missing_info"))
    hard_tasks.extend(make_abstain_tasks("hard", 116, "unsupported_tool", 5, UNSUPPORTED_PROMPTS, tag="unsupported_tool"))

    hidden_tasks = []
    hidden_tasks.extend(make_single_tasks("hidden", 1, 30, variant_offset=0))
    hidden_tasks.extend(make_multi_tasks("hidden", 31, 25, pair_offset=13))
    hidden_tasks.extend(make_abstain_tasks("hidden", 56, "no_tool", 15, NO_TOOL_PROMPTS[15:] + NO_TOOL_PROMPTS, tag="hidden_no_tool"))
    hidden_tasks.extend(make_abstain_tasks("hidden", 71, "missing_info", 7, MISSING_PROMPTS[10:] + MISSING_PROMPTS, tag="missing_info"))
    hidden_tasks.extend(make_abstain_tasks("hidden", 78, "unsupported_tool", 3, UNSUPPORTED_PROMPTS[5:] + UNSUPPORTED_PROMPTS, tag="unsupported_tool"))

    write_json(DEV_PATH, dev_tasks)
    write_json(HARD_PATH, hard_tasks)
    write_json(HIDDEN_PATH, hidden_tasks)
    write_json(HIDDEN_KEY_PATH, make_hidden_answer_key(hidden_tasks))

    for name, tasks in [
        ("dev", dev_tasks),
        ("hard", hard_tasks),
        ("hidden", hidden_tasks),
    ]:
        counts = Counter(task["task_type"] for task in tasks)
        covered = sorted({skill for task in tasks for skill in task.get("gold_skills", [])})
        print(f"{name}: total={len(tasks)} counts={dict(counts)} covered_skills={len(covered)}")


def make_single_tasks(split: str, start_id: int, count: int, variant_offset: int = 0) -> list[dict]:
    tasks = []
    for index in range(count):
        spec = SINGLE_SPECS[(index + variant_offset) % len(SINGLE_SPECS)]
        task_id = format_task_id(split, start_id + index)
        instruction = single_instruction_variant(spec, split, index + variant_offset)
        tasks.append(
            tool_task(
                task_id=task_id,
                instruction=instruction,
                gold_skills=[spec["skill"]],
                expected_answer=spec["expected"],
                task_type="single_skill",
                notes=f"{split} single-skill contract task for {spec['skill']}.",
                difficulty="hard" if split != "dev" else "medium",
                benchmark_tags=[
                    split,
                    "single_skill",
                    "skill_contract_v2",
                    spec["category"],
                ],
                source_inspiration=SOURCES[(index + variant_offset) % len(SOURCES)],
                hard_negative_skills=spec["hard_negatives"],
                argument_checks=[
                    {"skill": spec["skill"], "contains": spec["arguments"][:3]}
                ],
                observation_checks=[
                    {"skill": spec["skill"], "contains": spec["observations"][:3]}
                ],
                final_answer_check={"contains": spec["observations"][:1]},
            )
        )
    return tasks


def make_multi_tasks(split: str, start_id: int, count: int, pair_offset: int = 0) -> list[dict]:
    tasks = []
    spec_by_skill = {spec["skill"]: spec for spec in SINGLE_SPECS}
    for index in range(count):
        first_skill, second_skill, instruction = MULTI_PAIRS[(index + pair_offset) % len(MULTI_PAIRS)]
        first_spec = spec_by_skill[first_skill]
        second_spec = spec_by_skill[second_skill]
        task_id = format_task_id(split, start_id + index)
        if split != "dev" and index % 3 == 0:
            instruction = f"Without using a numbered plan, {instruction[0].lower()}{instruction[1:]}"
        elif split == "hidden" and index % 4 == 0:
            instruction = f"I need the final response only after both parts are handled: {instruction}"
        tasks.append(
            tool_task(
                task_id=task_id,
                instruction=instruction,
                gold_skills=[first_skill, second_skill],
                expected_answer=f"{first_skill} followed by {second_skill}",
                task_type="multi_skill",
                notes=f"{split} implicit multi-skill task: {first_skill} -> {second_skill}.",
                difficulty="hard",
                benchmark_tags=[
                    split,
                    "multi_skill",
                    "implicit_or_composed",
                    "skill_contract_v2",
                    "dependency" if second_skill in DEPENDENT_SECOND_SKILLS else "parallel_composition",
                ],
                source_inspiration=SOURCES[(index + pair_offset) % len(SOURCES)],
                hard_negative_skills=unique(first_spec["hard_negatives"] + second_spec["hard_negatives"]),
                argument_checks=[
                    {"skill": first_skill, "contains": first_spec["arguments"][:2]},
                    {
                        "skill": second_skill,
                        "regex": [
                            r"(\$PREVIOUS_OUTPUT|Summary|Title|Table|Email draft|Keywords|Readability|Sentiment|"
                            + "|".join(re_escape_items(second_spec["arguments"][:2]))
                            + r")"
                        ],
                    },
                ],
                observation_checks=[
                    {"skill": first_skill, "contains": first_spec["observations"][:1]},
                    {"skill": second_skill, "contains": second_spec["observations"][:1]},
                ],
                final_answer_check={"contains": second_spec["observations"][:1]},
            )
        )
    return tasks


def make_abstain_tasks(
    split: str,
    start_id: int,
    task_type: str,
    count: int,
    pool: list[tuple],
    tag: str,
) -> list[dict]:
    tasks = []
    for index in range(count):
        item = pool[index % len(pool)]
        prompt = item[0]
        hard_negatives = item[1]
        if task_type == "no_tool":
            expected = "Answer directly without using tools."
            final_check = {"regex": [r"(explain|because|means|concept|difference|role|important|should|can)"]}
        elif task_type == "missing_info":
            expected = "Ask for the missing input before using a tool."
            final_check = {"regex": [item[2]]}
        else:
            expected = "State that the request is unsupported by the local skill set."
            final_check = {"regex": [r"(cannot|can't|unable|unsupported|no.*tool|not able|" + item[2] + r")"]}

        task_id = format_task_id(split, start_id + index)
        tasks.append(
            abstain_task(
                task_id=task_id,
                instruction=prompt,
                expected_answer=expected,
                task_type=task_type,
                notes=f"{split} {task_type} abstention task with hard negatives.",
                difficulty="hard",
                benchmark_tags=[split, task_type, tag, "skill_contract_v2"],
                source_inspiration=SOURCES[(index + start_id) % len(SOURCES)],
                hard_negative_skills=hard_negatives,
                final_answer_check=final_check,
            )
        )
    return tasks


def single_instruction_variant(spec: dict, split: str, index: int) -> str:
    base = spec["instruction"]
    if split == "dev":
        variants = [
            base,
            f"For a Dev contract check, {base[0].lower()}{base[1:]}",
            f"Use the most specific skill for this request: {base}",
        ]
    elif split == "hard":
        variants = [
            f"The request is easy to confuse with {spec['hard_negatives'][0]}, but the intended operation is: {base}",
            f"Handle only the requested operation, not its similar neighbors: {base}",
            f"In a natural user note, please handle this: {base}",
        ]
    else:
        variants = [
            f"Please answer from the appropriate local skill only: {base}",
            f"I want the result, not an explanation of the skill choice: {base}",
            f"Resolve the concrete request here: {base}",
        ]
    return variants[index % len(variants)]


DEPENDENT_SECOND_SKILLS = {
    "summarizer",
    "text_rewriter",
    "table_formatter",
    "title_generator",
    "keyword_extractor",
    "checklist_generator",
    "email_drafter",
    "tone_converter",
    "sentiment_analyzer",
    "readability_scorer",
    "outline_generator",
    "question_generator",
    "todo_extractor",
}


def format_task_id(split: str, value: int) -> str:
    if split == "dev":
        return f"dev_{value:03d}"
    if split == "hard":
        return f"hard_{value:03d}"
    if split == "hidden":
        return f"hidden_{value:03d}"
    raise ValueError(f"Unknown split: {split}")


def make_hidden_answer_key(tasks: list[dict]) -> list[dict]:
    return [
        {
            "task_id": task["task_id"],
            "gold_skills": task.get("gold_skills", []),
            "gold_sequence": task.get("gold_sequence", []),
            "expected_answer": task.get("expected_answer", ""),
            "task_type": task.get("task_type", ""),
            "expected_checks": task.get("expected_checks", {}),
            "hard_negative_skills": task.get("hard_negative_skills", []),
        }
        for task in tasks
    ]


def write_json(path: Path, data) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def unique(items: list[str]) -> list[str]:
    seen = set()
    result = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


def re_escape_items(items: list[str]) -> list[str]:
    replacements = {
        ".": r"\.",
        "*": r"\*",
        "+": r"\+",
        "?": r"\?",
        "(": r"\(",
        ")": r"\)",
        "[": r"\[",
        "]": r"\]",
        "{": r"\{",
        "}": r"\}",
        "|": r"\|",
    }
    escaped = []
    for item in items:
        value = str(item)
        for source, target in replacements.items():
            value = value.replace(source, target)
        escaped.append(value)
    return escaped or [r"\S+"]


if __name__ == "__main__":
    main()
