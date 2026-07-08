"""
src/ai_commentary.py

The "Agentic AI" layer of the project. For each student, sends their
performance data to Claude and gets back a short, personalized comment
-- acknowledging strengths, flagging the weakest module, and giving one
concrete suggestion. This is what turns a static report card into
something that reads like personal feedback from a mentor.

Design choices worth noting in your project report:
- We batch nothing -- one API call per student, because comments must
  be genuinely personalized (a batched prompt risks generic, repetitive
  output across 50 students).
- We pass ONLY the data needed (name, %, grade, weakest/strongest module)
  -- not raw question-by-question answers -- keeping the prompt small,
  fast, and cheap.
- A 'dry_run' mode lets you build/test the whole pipeline (PDF layout,
  email sending) without burning API calls or needing a key yet.
"""

import os
from pathlib import Path

try:
    import anthropic
    _ANTHROPIC_AVAILABLE = True
except ImportError:
    _ANTHROPIC_AVAILABLE = False


def _build_prompt(student_row: dict, module_rows: list) -> str:
    """Builds the per-student prompt from their performance data."""
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
    """
    Returns a personalized comment for one student.
    If `client` is None or anthropic isn't installed, returns a
    rule-based fallback comment instead of crashing -- useful for
    testing the pipeline before an API key is configured.
    """
    if client is None:
        return _fallback_comment(student_row, module_rows)

    prompt = _build_prompt(student_row, module_rows)
    response = client.messages.create(
        model=model,
        max_tokens=150,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.content[0].text.strip()


def _fallback_comment(student_row: dict, module_rows: list) -> str:
    """
    Simple rule-based comment used when no API key is available.
    Lets you build and test the full PDF/email pipeline for free,
    then switch to real AI comments once a key is set up.
    """
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
        detail = (
            f" You're performing strongly in {best['module']} "
            f"({best['module_percentage']}%) -- keep that momentum going. "
            f"Consider revisiting {worst['module']} ({worst['module_percentage']}%) "
            f"to strengthen that area."
        )
    elif best:
        detail = f" Your performance in {best['module']} ({best['module_percentage']}%) reflects grade {grade}."
    else:
        detail = ""

    return opening + detail


def get_anthropic_client():
    """
    Creates an Anthropic client from the ANTHROPIC_API_KEY environment
    variable. Returns None (triggering fallback comments) if the key
    isn't set or the package isn't installed, rather than crashing --
    so the rest of the pipeline keeps working either way.
    """
    if not _ANTHROPIC_AVAILABLE:
        print("  Note: anthropic package not installed -- using fallback comments.")
        return None

    api_key = os.environ.get('ANTHROPIC_API_KEY')
    if not api_key:
        print("  Note: ANTHROPIC_API_KEY not set -- using fallback comments.")
        return None

    return anthropic.Anthropic(api_key=api_key)


if __name__ == '__main__':
    # Quick manual test with a sample student
    sample_student = {
        'name': 'Test Student',
        'avg_percentage': 78.5,
        'grade': 'A',
        'final_percentile': 65.0,
        'quizzes_attempted': 2
    }
    sample_modules = [
        {'module': 'AI Fundamentals', 'module_percentage': 93.3, 'module_percentile': 80},
        {'module': 'Python DataStructures', 'module_percentage': 64.0, 'module_percentile': 40},
    ]

    client = get_anthropic_client()
    comment = generate_comment(sample_student, sample_modules, client)
    print("\nGenerated comment:")
    print(comment)
