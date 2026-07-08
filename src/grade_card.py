"""
src/grade_card.py

Generates one personalized PDF grade card per student using reportlab.
Each card includes:
  - Header with institute name and student identity
  - Overall summary: avg %, grade, rank, percentile
  - Module-wise performance table
  - A short AI-generated (or fallback rule-based) comment

Output: output/grade_cards/<safe_email>.pdf  -- one file per student.
"""

from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT


GRADE_COLORS = {
    'A+': colors.HexColor('#0F6E56'),
    'A':  colors.HexColor('#1F6FB2'),
    'B':  colors.HexColor('#B8860B'),
    'C':  colors.HexColor('#D2691E'),
    'F':  colors.HexColor('#B22222'),
}


def _safe_filename(email: str) -> str:
    """Turns an email into a filesystem-safe filename."""
    return email.replace('@', '_at_').replace('.', '_')


def _build_styles():
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name='InstituteTitle', fontSize=16, leading=20, alignment=TA_CENTER,
        textColor=colors.HexColor('#1F4E78'), fontName='Helvetica-Bold'
    ))
    styles.add(ParagraphStyle(
        name='CardTitle', fontSize=13, leading=16, alignment=TA_CENTER,
        textColor=colors.HexColor('#444444'), spaceAfter=10
    ))
    styles.add(ParagraphStyle(
        name='StudentName', fontSize=14, leading=18, alignment=TA_LEFT,
        fontName='Helvetica-Bold'
    ))
    styles.add(ParagraphStyle(
        name='CommentText', fontSize=10.5, leading=15, alignment=TA_LEFT,
        textColor=colors.HexColor('#333333'), spaceBefore=4
    ))
    styles.add(ParagraphStyle(
        name='SectionHeader', fontSize=11.5, leading=14, alignment=TA_LEFT,
        fontName='Helvetica-Bold', textColor=colors.HexColor('#1F4E78'),
        spaceBefore=14, spaceAfter=6
    ))
    return styles


def generate_grade_card_pdf(student_row: dict, module_rows: list, comment: str,
                             output_dir: str = 'output/grade_cards/') -> str:
    """
    Builds and saves one student's PDF grade card.
    Returns the filepath of the generated PDF.
    """
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    filepath = out_path / f"{_safe_filename(student_row['email'])}.pdf"

    styles = _build_styles()
    doc = SimpleDocTemplate(
        str(filepath), pagesize=A4,
        topMargin=20 * mm, bottomMargin=20 * mm,
        leftMargin=20 * mm, rightMargin=20 * mm
    )

    story = []

    # Header
    story.append(Paragraph("LLOYD INSTITUTE OF ENGINEERING &amp; TECHNOLOGY", styles['InstituteTitle']))
    story.append(Paragraph("Summer Training: ML and Agentic AI &mdash; Performance Grade Card", styles['CardTitle']))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#1F4E78')))
    story.append(Spacer(1, 14))

    # Student identity block
    story.append(Paragraph(student_row['name'], styles['StudentName']))
    story.append(Paragraph(student_row['email'], styles['Normal']))
    story.append(Spacer(1, 10))

    # Overall summary table
    grade = student_row['grade']
    grade_color = GRADE_COLORS.get(grade, colors.black)

    summary_data = [
        ['Overall Average', 'Rank', 'Percentile', 'Grade'],
        [
            f"{student_row['avg_percentage']}%",
            f"#{student_row['rank']}",
            f"{student_row['final_percentile']}",
            grade
        ]
    ]
    summary_table = Table(summary_data, colWidths=[40 * mm] * 4)
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1F4E78')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 11),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CCCCCC')),
        ('TEXTCOLOR', (3, 1), (3, 1), grade_color),
        ('FONTNAME', (3, 1), (3, 1), 'Helvetica-Bold'),
        ('FONTSIZE', (3, 1), (3, 1), 13),
    ]))
    story.append(summary_table)

    # Module-wise breakdown
    story.append(Paragraph("Module-wise Performance", styles['SectionHeader']))

    module_data = [['Module', 'Marks', 'Percentage', 'Percentile']]
    for m in module_rows:
        module_data.append([
            m['module'],
            f"{m['marks_scored']:.0f} / {m['marks_possible']:.0f}",
            f"{m['module_percentage']}%",
            f"{m['module_percentile']}"
        ])

    module_table = Table(module_data, colWidths=[70 * mm, 30 * mm, 30 * mm, 30 * mm])
    module_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#E6F1FB')),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CCCCCC')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F7F9FB')]),
    ]))
    story.append(module_table)

    # AI comment
    story.append(Paragraph("Mentor's Note", styles['SectionHeader']))
    story.append(Paragraph(comment, styles['CommentText']))

    # Footer
    story.append(Spacer(1, 20))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor('#CCCCCC')))
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        "Automatically generated by the Training Performance Management System.",
        ParagraphStyle(name='Footer', fontSize=8, textColor=colors.HexColor('#999999'), alignment=TA_CENTER)
    ))

    doc.build(story)
    return str(filepath)


def generate_all_grade_cards(results: dict, use_ai: bool = True, output_dir: str = 'output/grade_cards/') -> list:
    """
    Generates a PDF grade card for every student in results['master'],
    pulling each student's module rows and (optionally) an AI comment.
    Returns the list of generated filepaths.
    """
    import sys
    sys.path.insert(0, '.')
    from src.ai_commentary import generate_comment, get_anthropic_client

    client = get_anthropic_client() if use_ai else None

    master = results['master']
    module = results['module']

    generated = []
    print(f"Generating {len(master)} grade card(s)...")

    for _, student_row in master.iterrows():
        student_dict = student_row.to_dict()
        student_modules = module[module['email'] == student_dict['email']].to_dict('records')

        comment = generate_comment(student_dict, student_modules, client)
        filepath = generate_grade_card_pdf(student_dict, student_modules, comment, output_dir)
        generated.append(filepath)

    print(f"Done. {len(generated)} grade cards saved to {output_dir}")
    return generated


if __name__ == '__main__':
    import sys
    sys.path.insert(0, '.')
    from src.quiz_parser import parse_all_quiz_files
    from src.roster import apply_roster
    from src.calculator import build_master_performance

    long_df = parse_all_quiz_files('data/raw/')
    long_df = apply_roster(long_df)
    results = build_master_performance(long_df)

    # Generate just ONE grade card first as a quick visual check
    sample = results['master'].iloc[0].to_dict()
    sample_modules = results['module'][results['module']['email'] == sample['email']].to_dict('records')

    from src.ai_commentary import generate_comment, get_anthropic_client
    client = get_anthropic_client()
    comment = generate_comment(sample, sample_modules, client)

    path = generate_grade_card_pdf(sample, sample_modules, comment)
    print(f"\nSample grade card generated: {path}")
    print(f"For: {sample['name']} (rank #{sample['rank']}, grade {sample['grade']})")
