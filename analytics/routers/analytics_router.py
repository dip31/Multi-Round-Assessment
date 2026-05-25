"""
Analytics API Router — Stage 10
Provides recruitment metrics, dashboards, and forecasting.
"""
from fastapi import APIRouter, HTTPException, Response
from fastapi.responses import FileResponse
from typing import Optional
import os

router = APIRouter(tags=["Stage 10: Analytics"])


@router.get("/analytics/dashboard")
async def get_dashboard():
    """Get recruitment funnel metrics."""
    from analytics.recruitment_dashboard import get_funnel_metrics, get_funnel_dropoff
    
    try:
        metrics = get_funnel_metrics()
        funnel = get_funnel_dropoff(metrics)
        
        return {
            "success": True,
            "metrics": metrics,
            "funnel": funnel
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analytics/jobs")
async def get_jobs_summary():
    """Get per-job recruitment summary."""
    from analytics.recruitment_dashboard import get_jobs_summary
    
    try:
        jobs = get_jobs_summary()
        return {"success": True, "jobs": jobs}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analytics/time-to-hire")
async def get_time_to_hire():
    """Get time-to-hire metrics."""
    from analytics.time_to_hire_reporter import calculate_time_to_hire
    
    try:
        metrics = calculate_time_to_hire()
        return {"success": True, "metrics": metrics}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analytics/source-tracker")
async def get_source_tracker():
    """Get source ROI analysis."""
    from analytics.source_tracker import track_source_roi
    
    try:
        roi = track_source_roi()
        return {"success": True, "roi": roi}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analytics/forecast")
async def get_hiring_forecast():
    """Get ML-based hiring forecast."""
    from analytics.hiring_forecast_engine import generate_forecast
    
    try:
        forecast = generate_forecast()
        return {"success": True, "forecast": forecast}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analytics/export/csv")
async def export_csv():
    """Export dashboard data as CSV."""
    from analytics.recruitment_dashboard import export_to_csv
    
    try:
        file_path = export_to_csv()
        if os.path.exists(file_path):
            return FileResponse(
                file_path,
                media_type="text/csv",
                filename="recruitment_dashboard.csv"
            )
        raise HTTPException(status_code=404, detail="Export file not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analytics/export/pdf")
async def export_pdf():
    """Export dashboard data as PDF."""
    from analytics.recruitment_dashboard import export_to_pdf
    
    try:
        file_path = export_to_pdf()
        if os.path.exists(file_path):
            return FileResponse(
                file_path,
                media_type="application/pdf",
                filename="recruitment_dashboard.pdf"
            )
        raise HTTPException(status_code=404, detail="Export file not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
