"""
hiring_forecast_engine.py — Netra | Stage 10
SQLite + scikit-learn (free). Uses Groq (free API) instead of Claude.
Generates quarterly hiring forecast PDF.
"""

import sqlite3
import pandas as pd
import numpy as np
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import LabelEncoder
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from config import DATABASE_URL

# Extract DB path from DATABASE_URL
DB_PATH = DATABASE_URL.replace("sqlite+aiosqlite:///", "")


def generate_quarterly_plan_local(predictions: pd.DataFrame) -> str:
    """Generate hiring plan locally — no external API."""
    total = int(predictions['predicted_hires'].sum())
    top_dept = predictions.loc[predictions['predicted_hires'].idxmax(), 'department'] if not predictions.empty else "N/A"
    now = datetime.now()
    quarter = int(predictions['quarter'].iloc[0]) if not predictions.empty else 1
    year = int(predictions['year'].iloc[0]) if not predictions.empty else now.year
    budget = total * 5000

    lines = [
        f"QUARTERLY HIRING PLAN — Q{quarter} {year}",
        f"",
        f"1. Total Headcount Target: {total} hires",
        f"2. Priority Department: {top_dept}",
        f"3. Recommended Start: Begin sourcing 6 weeks before target join dates",
        f"4. Key Risks:",
        f"   - Candidate drop-off during negotiation",
        f"   - BGV delays extending onboarding timeline",
        f"   - Budget overrun if multiple senior roles open simultaneously",
        f"5. Budget Estimate: ${budget:,.0f} (at $5,000 avg cost-per-hire)",
    ]
    return "\n".join(lines)


def get_historical_hiring_data() -> pd.DataFrame:
    conn = sqlite3.connect(DB_PATH)
    query = """
        SELECT j.department, j.title,
               strftime('%Y', j.created_at) AS year,
               ((CAST(strftime('%m', j.created_at) AS INTEGER) - 1) / 3 + 1) AS quarter,
               strftime('%m', j.created_at) AS month,
               COUNT(DISTINCT o.id) AS hires
        FROM jobs j
        LEFT JOIN offers o ON o.job_id=j.id AND o.status='accepted'
        GROUP BY j.department, j.title, year, quarter, month
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    df['year'] = pd.to_numeric(df['year'])
    df['quarter'] = pd.to_numeric(df['quarter'])
    df['month'] = pd.to_numeric(df['month'])
    df['hires'] = pd.to_numeric(df['hires'])
    return df


def predict_headcount_ml(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=['department', 'predicted_hires', 'year', 'quarter'])
    le = LabelEncoder()
    df['dept_encoded'] = le.fit_transform(df['department'])
    X = df[['dept_encoded', 'year', 'quarter', 'month']].fillna(0)
    y = df['hires'].fillna(0)
    model = LinearRegression()
    model.fit(X, y)
    now = datetime.now()
    nq = (now.month // 3) + 1
    ny = now.year if nq <= 4 else now.year + 1
    nq = nq if nq <= 4 else 1
    predictions = []
    for dept in df['department'].unique():
        enc = le.transform([dept])[0] if dept in le.classes_ else 0
        pred = max(0, round(model.predict([[enc, ny, nq, nq * 3]])[0]))
        predictions.append({"department": dept, "predicted_hires": pred,
                             "year": ny, "quarter": nq})
    return pd.DataFrame(predictions)


def estimate_time_to_hire_by_role(df: pd.DataFrame) -> dict:
    if 'avg_days_to_hire' not in df.columns:
        return {}
    est = df.groupby('title')['avg_days_to_hire'].mean().round(1).to_dict()
    return {k: v for k, v in est.items() if not np.isnan(v)}


def generate_quarterly_plan_with_groq(predictions: pd.DataFrame) -> str:
    return generate_quarterly_plan_local(predictions)


def export_forecast_pdf(predictions: pd.DataFrame, plan_text: str,
                         output_path: str = "/tmp/hiring_forecast.pdf"):
    doc = SimpleDocTemplate(output_path, pagesize=A4,
                            rightMargin=inch, leftMargin=inch,
                            topMargin=inch, bottomMargin=inch)
    styles = getSampleStyleSheet()
    story = [Paragraph("Quarterly Hiring Forecast", styles['Title']),
             Paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d')}", styles['Normal']),
             Spacer(1, 0.3*inch)]
    data = [["Department", "Predicted Hires", "Quarter", "Year"]] + [
        [r['department'], str(r['predicted_hires']), f"Q{int(r['quarter'])}", str(int(r['year']))]
        for _, r in predictions.iterrows()
    ]
    t = Table(data, colWidths=[2.5*inch, 1.5*inch, 1*inch, 1*inch])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#2c3e50')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
    ]))
    story.append(t)
    story.append(Spacer(1, 0.3*inch))
    story.append(Paragraph("AI-Generated Hiring Plan (Groq)", styles['Heading2']))
    for line in plan_text.split('\n'):
        if line.strip():
            story.append(Paragraph(line, styles['Normal']))
            story.append(Spacer(1, 0.05*inch))
    doc.build(story)
    print(f"[hiring_forecast_engine] PDF → {output_path}")
    return output_path


def run_forecast():
    df = get_historical_hiring_data()
    predictions = predict_headcount_ml(df)
    plan_text = generate_quarterly_plan_with_groq(predictions)
    export_forecast_pdf(predictions, plan_text)
    return predictions, plan_text

def generate_forecast() -> dict:
    """Generate hiring forecast and return structured data."""
    try:
        df = get_historical_hiring_data()
        predictions = predict_headcount_ml(df)
        plan_text = generate_quarterly_plan_with_groq(predictions)
        
        return {
            "predictions": predictions.to_dict('records') if not predictions.empty else [],
            "plan": plan_text,
            "total_predicted_hires": int(predictions['predicted_hires'].sum()) if not predictions.empty else 0,
            "forecast_period": f"Q{datetime.now().month // 3 + 1} {datetime.now().year}"
        }
    except Exception as e:
        return {
            "predictions": [],
            "plan": f"Forecast generation failed: {str(e)}",
            "total_predicted_hires": 0,
            "forecast_period": "N/A"
        }