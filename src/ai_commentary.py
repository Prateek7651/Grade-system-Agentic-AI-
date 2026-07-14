import os

try:
    import anthropic
    _ANTHROPIC_AVAILABLE = True
except ImportError:
    _ANTHROPIC_AVAILABLE = False


def _build_prompt(student_row: dict, module_rows: list) -> str:
    modules_text = "\n".join(
        f"  - {m['module']}: {m['module_percentage']}% (percentile {m['module_percentile']})"
        for m in module_rows
    )
    return f"""You are a supportive training mentor writing a 2-3 sentence comment
for a student's grade card in a Machine Learning & Agentic AI summer training program.

Student: {student_row['name']}
Overall average: {student_row['avg_percentage']}%
Overall grade: {student_row['grade']}
Overall percentile: {student_row['final_percentile']}
Quizzes attempted: {student_row['quizzes_attempted']}

Module-wise performance:
{modules_text}

Write a short, encouraging, specific comment (2-3 sentences max). Mention
their strongest area by name, and if there's a clearly weaker module,
gently point to it with ONE concrete next step. Keep tone warm but
professional, not generic. Do not use bullet points. Output ONLY the
comment text, nothing else."""


def generate_comment(student_row: dict, module_rows: list, client=None, model: str = "claude-sonnet-4-6") -> str:
    if client is None:
        return _fallback_comment(student_row, module_rows)
    prompt = _build_prompt(student_row, module_rows)
    response = client.messages.create(
        model=model, max_tokens=150,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.content[0].text.strip()


def _fallback_comment(student_row: dict, module_rows: list) -> str:
    name = student_row['name']
    pct = student_row['avg_percentage']
    grade = student_row['grade']
    if module_rows:
        best = max(module_rows, key=lambda m: m['module_percentage'])
        worst = min(module_rows, key=lambda m: m['module_percentage'])
    else:
        best = worst = None
    if pct >= 85:
        opening = f"Excellent work, {name}!"
    elif pct >= 70:
        opening = f"Good effort, {name}."
    elif pct >= 55:
        opening = f"Solid progress, {name}, with room to grow."
    else:
        opening = f"{name}, this module needs more focused attention."
    if best and worst and best['module'] != worst['module']:
        detail = (f" You're performing strongly in {best['module']} ({best['module_percentage']}%) -- keep that momentum going. "
                  f"Consider revisiting {worst['module']} ({worst['module_percentage']}%) to strengthen that area.")
    elif best:
        detail = f" Your performance in {best['module']} ({best['module_percentage']}%) reflects grade {grade}."
    else:
        detail = ""
    return opening + detail


def get_anthropic_client():
    if not _ANTHROPIC_AVAILABLE:
        print("  Note: anthropic package not installed -- using fallback comments.")
        return None
    api_key = os.environ.get('ANTHROPIC_API_KEY')
    if not api_key:
        print("  Note: ANTHROPIC_API_KEY not set -- using fallback comments.")
        return None
    return anthropic.Anthropic(api_key=api_key)
