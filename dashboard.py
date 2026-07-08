"""
dashboard.py

Streamlit analytics dashboard for the Training Performance Management System.
Two views, one app:
  - Admin view: full cohort analytics, all student data
  - Student view: personal grade card lookup by email

Run with:
    streamlit run dashboard.py
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path

# ── Page config (must be first Streamlit call) ─────────────────────────────
st.set_page_config(
    page_title="Training Performance Dashboard",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ── Global CSS ─────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600&family=Inter:wght@400;500;600;700&display=swap');

/* Base */
[data-testid="stAppViewContainer"] {
    background: #0F1829;
    color: #E2E8F0;
}
[data-testid="stSidebar"] {
    background: #0A1020 !important;
    border-right: 1px solid #1E2D45;
}
[data-testid="stSidebar"] * { color: #94A3B8 !important; }
[data-testid="stSidebar"] .stRadio label { font-family: 'Inter', sans-serif; font-size: 14px; }

/* Hide default Streamlit header/footer */
#MainMenu, footer, header { visibility: hidden; }

/* Cards */
.kpi-card {
    background: #131F35;
    border: 1px solid #1E2D45;
    border-radius: 12px;
    padding: 20px 24px;
    text-align: center;
}
.kpi-value {
    font-family: 'JetBrains Mono', monospace;
    font-size: 36px;
    font-weight: 600;
    color: #3B9EFF;
    line-height: 1;
    margin-bottom: 6px;
}
.kpi-label {
    font-family: 'Inter', sans-serif;
    font-size: 12px;
    color: #64748B;
    text-transform: uppercase;
    letter-spacing: 0.08em;
}

/* Section headers */
.section-title {
    font-family: 'Inter', sans-serif;
    font-size: 13px;
    font-weight: 600;
    color: #64748B;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    margin: 28px 0 14px 0;
    padding-bottom: 8px;
    border-bottom: 1px solid #1E2D45;
}

/* Leaderboard */
.lb-row {
    display: flex;
    align-items: center;
    gap: 14px;
    padding: 10px 14px;
    border-radius: 8px;
    margin-bottom: 6px;
    background: #131F35;
    border: 1px solid #1E2D45;
    font-family: 'Inter', sans-serif;
}
.lb-row.gold   { border-color: #F59E0B; background: #1A1500; }
.lb-row.silver { border-color: #94A3B8; background: #141820; }
.lb-row.bronze { border-color: #B45309; background: #1A1100; }

.lb-medal { font-size: 22px; width: 30px; text-align: center; flex-shrink: 0; }
.lb-rank  { font-family: 'JetBrains Mono', monospace; font-size: 13px;
             color: #64748B; width: 28px; text-align: right; flex-shrink: 0; }
.lb-name  { flex: 1; font-size: 14px; font-weight: 500; color: #E2E8F0; }
.lb-pct   { font-family: 'JetBrains Mono', monospace; font-size: 14px;
             font-weight: 600; color: #3B9EFF; }
.lb-grade { font-size: 12px; padding: 2px 8px; border-radius: 20px;
             font-weight: 600; flex-shrink: 0; }

/* Grade badges */
.g-Ap { background:#052e16; color:#22C55E; }
.g-A  { background:#0c1a3a; color:#3B9EFF; }
.g-B  { background:#1a1a00; color:#EAB308; }
.g-C  { background:#1a0e00; color:#F97316; }
.g-F  { background:#1a0000; color:#EF4444; }

/* Student card */
.student-card {
    background: #131F35;
    border: 1px solid #1E2D45;
    border-radius: 16px;
    padding: 32px;
    margin-bottom: 20px;
}
.student-name {
    font-family: 'Inter', sans-serif;
    font-size: 26px;
    font-weight: 700;
    color: #E2E8F0;
    margin-bottom: 4px;
}
.student-email {
    font-family: 'JetBrains Mono', monospace;
    font-size: 12px;
    color: #64748B;
}

/* Page title */
.dash-title {
    font-family: 'Inter', sans-serif;
    font-size: 22px;
    font-weight: 700;
    color: #E2E8F0;
    margin-bottom: 2px;
}
.dash-sub {
    font-family: 'Inter', sans-serif;
    font-size: 13px;
    color: #64748B;
    margin-bottom: 24px;
}
</style>
""", unsafe_allow_html=True)

GRADE_COLORS = {
    'A+': '#22C55E', 'A': '#3B9EFF',
    'B':  '#EAB308', 'C': '#F97316', 'F': '#EF4444'
}
GRADE_CSS = {'A+': 'g-Ap', 'A': 'g-A', 'B': 'g-B', 'C': 'g-C', 'F': 'g-F'}
PLOTLY_THEME = dict(
    paper_bgcolor='rgba(0,0,0,0)',
    plot_bgcolor='rgba(0,0,0,0)',
    font=dict(family='Inter', color='#94A3B8', size=12),
    margin=dict(l=0, r=0, t=30, b=0),
)


# ── Data loading ───────────────────────────────────────────────────────────
@st.cache_data(ttl=60)
def load_data():
    master_path = Path('data/processed/master_performance.csv')
    module_path = Path('data/processed/module_summary.csv')
    daily_path  = Path('data/processed/daily_performance.csv')

    if not master_path.exists():
        return None, None, None

    master = pd.read_csv(master_path)
    module = pd.read_csv(module_path) if module_path.exists() else pd.DataFrame()
    daily  = pd.read_csv(daily_path)  if daily_path.exists()  else pd.DataFrame()
    return master, module, daily


# ── Sidebar nav ────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🎓 Grade System")
    st.markdown("---")
    view = st.radio("View", ["Admin Dashboard", "Student Lookup"], label_visibility="collapsed")
    st.markdown("---")
    st.markdown(
        "<div style='font-size:11px;color:#374151;'>Lloyd Institute of Engineering<br>ML & Agentic AI Training</div>",
        unsafe_allow_html=True
    )

master, module, daily = load_data()

if master is None:
    st.error("No processed data found. Run `python main.py` first to generate data.")
    st.stop()


# ══════════════════════════════════════════════════════════════════════════
# ADMIN DASHBOARD
# ══════════════════════════════════════════════════════════════════════════
if view == "Admin Dashboard":

    st.markdown('<div class="dash-title">Cohort Performance Overview</div>', unsafe_allow_html=True)
    st.markdown('<div class="dash-sub">ML & Agentic AI Summer Training — Live Analytics</div>', unsafe_allow_html=True)

    # ── KPI strip ─────────────────────────────────────────────────────────
    k1, k2, k3, k4, k5 = st.columns(5)
    kpis = [
        (k1, str(len(master)), "Total Students"),
        (k2, f"{master['avg_percentage'].mean():.1f}%", "Cohort Average"),
        (k3, f"{master['avg_percentage'].max():.1f}%", "Top Score"),
        (k4, str((master['grade'] == 'A+').sum()), "A+ Students"),
        (k5, str((master['grade'] == 'F').sum()), "Need Support"),
    ]
    for col, val, label in kpis:
        with col:
            st.markdown(f"""
            <div class="kpi-card">
                <div class="kpi-value">{val}</div>
                <div class="kpi-label">{label}</div>
            </div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Charts row ────────────────────────────────────────────────────────
    col_left, col_right = st.columns([1, 1], gap="large")

    with col_left:
        st.markdown('<div class="section-title">Grade Distribution</div>', unsafe_allow_html=True)
        grade_counts = master['grade'].value_counts().reindex(['A+','A','B','C','F']).fillna(0)
        fig_grade = go.Figure(go.Bar(
            x=grade_counts.index.tolist(),
            y=grade_counts.values.tolist(),
            marker_color=[GRADE_COLORS.get(g, '#64748B') for g in grade_counts.index],
            text=grade_counts.values.astype(int),
            textposition='outside',
            textfont=dict(color='#E2E8F0', size=13),
        ))
        fig_grade.update_layout(
            **PLOTLY_THEME,
            xaxis=dict(showgrid=False, tickfont=dict(size=14, color='#E2E8F0')),
            yaxis=dict(showgrid=True, gridcolor='#1E2D45', zeroline=False),
            showlegend=False, height=260
        )
        st.plotly_chart(fig_grade, use_container_width=True)

    with col_right:
        st.markdown('<div class="section-title">Score Distribution</div>', unsafe_allow_html=True)
        fig_hist = go.Figure(go.Histogram(
            x=master['avg_percentage'],
            nbinsx=15,
            marker_color='#3B9EFF',
            opacity=0.85,
        ))
        fig_hist.update_layout(
            **PLOTLY_THEME,
            xaxis=dict(title='Average %', showgrid=False, tickfont=dict(color='#94A3B8')),
            yaxis=dict(title='Students', showgrid=True, gridcolor='#1E2D45'),
            bargap=0.08, height=260
        )
        st.plotly_chart(fig_hist, use_container_width=True)

    # ── Module comparison ──────────────────────────────────────────────────
    if not module.empty:
        st.markdown('<div class="section-title">Module-wise Average Performance</div>', unsafe_allow_html=True)
        module_avg = module.groupby('module')['module_percentage'].mean().reset_index()
        module_avg.columns = ['module', 'avg_pct']
        module_avg = module_avg.sort_values('avg_pct', ascending=True)

        fig_mod = go.Figure(go.Bar(
            x=module_avg['avg_pct'],
            y=module_avg['module'],
            orientation='h',
            marker=dict(
                color=module_avg['avg_pct'],
                colorscale=[[0,'#EF4444'],[0.5,'#EAB308'],[1,'#22C55E']],
                showscale=False
            ),
            text=[f"{v:.1f}%" for v in module_avg['avg_pct']],
            textposition='outside',
            textfont=dict(color='#E2E8F0'),
        ))
        fig_mod.update_layout(
            **PLOTLY_THEME,
            xaxis=dict(range=[0, 105], showgrid=True, gridcolor='#1E2D45',
                       ticksuffix='%', tickfont=dict(color='#94A3B8')),
            yaxis=dict(showgrid=False, tickfont=dict(size=12, color='#E2E8F0')),
            height=max(180, len(module_avg) * 60)
        )
        st.plotly_chart(fig_mod, use_container_width=True)

    # ── Leaderboard + Weak students ───────────────────────────────────────
    lb_col, weak_col = st.columns([1, 1], gap="large")

    with lb_col:
        st.markdown('<div class="section-title">Top 10 — Leaderboard</div>', unsafe_allow_html=True)
        medals = {1: ('🥇', 'gold'), 2: ('🥈', 'silver'), 3: ('🥉', 'bronze')}
        for _, row in master.head(10).iterrows():
            medal_icon, medal_cls = medals.get(row['rank'], ('', ''))
            g_css = GRADE_CSS.get(str(row['grade']), 'g-B')
            st.markdown(f"""
            <div class="lb-row {medal_cls}">
                <div class="lb-medal">{medal_icon}</div>
                <div class="lb-rank">#{row['rank']}</div>
                <div class="lb-name">{row['name']}</div>
                <div class="lb-pct">{row['avg_percentage']}%</div>
                <div class="lb-grade {g_css}">{row['grade']}</div>
            </div>""", unsafe_allow_html=True)

    with weak_col:
        st.markdown('<div class="section-title">Needs Attention — Below 55%</div>', unsafe_allow_html=True)
        weak = master[master['avg_percentage'] < 55].sort_values('avg_percentage')
        if weak.empty:
            st.markdown("<p style='color:#64748B;font-size:13px;'>All students are above 55% — great cohort!</p>",
                        unsafe_allow_html=True)
        else:
            for _, row in weak.iterrows():
                g_css = GRADE_CSS.get(str(row['grade']), 'g-F')
                st.markdown(f"""
                <div class="lb-row">
                    <div class="lb-rank">#{row['rank']}</div>
                    <div class="lb-name">{row['name']}</div>
                    <div class="lb-pct" style="color:#EF4444">{row['avg_percentage']}%</div>
                    <div class="lb-grade {g_css}">{row['grade']}</div>
                </div>""", unsafe_allow_html=True)

    # ── Full data table ────────────────────────────────────────────────────
    st.markdown('<div class="section-title">Full Student Data</div>', unsafe_allow_html=True)
    display_cols = ['rank', 'name', 'email', 'quizzes_attempted',
                    'avg_percentage', 'final_percentile', 'grade']
    st.dataframe(
        master[display_cols].set_index('rank'),
        use_container_width=True,
        height=400,
        column_config={
            'avg_percentage': st.column_config.ProgressColumn(
                'Average %', min_value=0, max_value=100, format='%.1f%%'
            ),
            'final_percentile': st.column_config.NumberColumn('Percentile', format='%.1f'),
        }
    )


# ══════════════════════════════════════════════════════════════════════════
# STUDENT LOOKUP VIEW
# ══════════════════════════════════════════════════════════════════════════
else:
    st.markdown('<div class="dash-title">Your Performance</div>', unsafe_allow_html=True)
    st.markdown('<div class="dash-sub">Enter your email to view your grade card</div>', unsafe_allow_html=True)

    email_input = st.text_input("Email address", placeholder="yourname@liet.in",
                                 label_visibility="collapsed")

    if not email_input:
        st.info("Enter the email address you used to submit your quizzes.")
        st.stop()

    email_query = email_input.strip().lower()
    student = master[master['email'] == email_query]

    if student.empty:
        st.error(f"No record found for `{email_input}`. Check spelling or try your other email.")
        st.stop()

    row = student.iloc[0]
    grade = str(row['grade'])
    grade_color = GRADE_COLORS.get(grade, '#64748B')
    g_css = GRADE_CSS.get(grade, 'g-B')
    total_students = len(master)

    # Identity block
    st.markdown(f"""
    <div class="student-card">
        <div class="student-name">{row['name']}</div>
        <div class="student-email">{row['email']}</div>
    </div>""", unsafe_allow_html=True)

    # KPI strip
    m1, m2, m3, m4 = st.columns(4)
    student_kpis = [
        (m1, f"{row['avg_percentage']}%", "Your Average"),
        (m2, f"#{row['rank']} / {total_students}", "Your Rank"),
        (m3, f"{row['final_percentile']}", "Percentile"),
        (m4, grade, "Grade"),
    ]
    for col, val, label in student_kpis:
        with col:
            color = grade_color if label == "Grade" else "#3B9EFF"
            st.markdown(f"""
            <div class="kpi-card">
                <div class="kpi-value" style="color:{color}">{val}</div>
                <div class="kpi-label">{label}</div>
            </div>""", unsafe_allow_html=True)

    # Module breakdown
    if not module.empty:
        st.markdown('<div class="section-title">Module-wise Performance</div>', unsafe_allow_html=True)
        student_modules = module[module['email'] == email_query]

        if not student_modules.empty:
            fig_mod = go.Figure()
            for _, mrow in student_modules.iterrows():
                color = '#22C55E' if mrow['module_percentage'] >= 70 else \
                        '#EAB308' if mrow['module_percentage'] >= 55 else '#EF4444'
                fig_mod.add_trace(go.Bar(
                    name=mrow['module'],
                    x=[mrow['module']],
                    y=[mrow['module_percentage']],
                    text=f"{mrow['module_percentage']}%",
                    textposition='outside',
                    marker_color=color,
                    showlegend=False
                ))
            fig_mod.update_layout(
                **PLOTLY_THEME,
                yaxis=dict(range=[0, 110], showgrid=True, gridcolor='#1E2D45',
                           ticksuffix='%'),
                xaxis=dict(showgrid=False, tickfont=dict(size=13, color='#E2E8F0')),
                height=280
            )
            st.plotly_chart(fig_mod, use_container_width=True)

            # Module table
            mod_display = student_modules[['module', 'marks_scored', 'marks_possible',
                                           'module_percentage', 'module_percentile']].copy()
            mod_display.columns = ['Module', 'Scored', 'Out of', 'Percentage', 'Percentile']
            st.dataframe(mod_display.set_index('Module'), use_container_width=True)

    # Cohort comparison
    st.markdown('<div class="section-title">How you compare to the cohort</div>', unsafe_allow_html=True)
    fig_cmp = go.Figure()
    fig_cmp.add_trace(go.Histogram(
        x=master['avg_percentage'], name='All students',
        marker_color='#1E2D45', opacity=1, nbinsx=15
    ))
    fig_cmp.add_vline(
        x=row['avg_percentage'], line_color=grade_color,
        line_width=2, line_dash='dash',
        annotation_text=f"You — {row['avg_percentage']}%",
        annotation_font_color=grade_color
    )
    fig_cmp.update_layout(
        **PLOTLY_THEME,
        xaxis=dict(title='Average %', showgrid=False, tickfont=dict(color='#94A3B8')),
        yaxis=dict(title='Students', showgrid=True, gridcolor='#1E2D45'),
        showlegend=False, height=240
    )
    st.plotly_chart(fig_cmp, use_container_width=True)
