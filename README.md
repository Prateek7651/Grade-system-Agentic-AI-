# Automated Training Performance Management System

> ML & Agentic AI Summer Training — Lloyd Institute of Engineering & Technology

An end-to-end automated system that parses Google Forms quiz exports,
calculates student performance, generates personalized PDF grade cards
with AI commentary, and emails them — all with one command.

## Features
- Parses Google Forms CSV exports automatically
- Identifies students across multiple email addresses (roster system)
- Calculates scores, percentile, rank, and grades for students
- Generates personalized PDF grade cards with Claude AI comments
- Sends emails with PDF attachments via Gmail SMTP
- Animated glassmorphism web frontend (HTML/CSS/JS)
- Admin dashboard with live charts and leaderboard
- Student self-service grade card lookup
- REST API (Flask + JWT authentication)
- Streamlit analytics dashboard

## Tech Stack
Python · pandas · Flask · JWT · reportlab · smtplib · Streamlit · 
Plotly · Chart.js · Anthropic Claude API · openpyxl

## Run it
```bash
pip install -r requirements.txt
python main.py              # full pipeline
python api.py               # start REST API
streamlit run dashboard.py  # analytics dashboard
```

## Project Structure
```
src/
├── quiz_parser.py      # Google Forms CSV parser
├── roster.py           # Cross-email student identity resolver
├── calculator.py       # Scores, percentile, rank, grade
├── exporter.py         # Excel/CSV output files
├── ai_commentary.py    # Claude API personalized comments
├── grade_card.py       # PDF grade card generator
├── emailer.py          # SMTP email sender
└── auth.py             # JWT authentication
frontend/
├── index.html          # Animated login page
├── admin.html          # Admin dashboard
└── student.html        # Student grade card view
```
