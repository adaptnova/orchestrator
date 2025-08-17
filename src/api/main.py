"""FastAPI application for Orchestrator Nova on Vertex AI."""

import os
import sys
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
import structlog
from dotenv import load_dotenv

# Load environment
env_path = Path("/app/.env")
if env_path.exists():
    load_dotenv(env_path)

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.orchestrator import Orchestrator
from src.voice.voice_orchestrator import VoiceOrchestrator

# Configure logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)

# Initialize FastAPI
app = FastAPI(
    title="Orchestrator Nova",
    description="AI Agent Orchestration Platform on GCP",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Initialize orchestrators
orchestrator = Orchestrator()
voice_orchestrator = VoiceOrchestrator()


# Request/Response models
class TaskRequest(BaseModel):
    """Request model for task execution."""
    goal: str = Field(..., description="Task goal to execute")
    verbose: bool = Field(default=False, description="Verbose output")
    async_execution: bool = Field(default=False, description="Execute asynchronously")


class VoiceRequest(BaseModel):
    """Request model for voice commands."""
    transcript: str = Field(..., description="Voice command transcript")
    session_id: Optional[str] = Field(None, description="Session ID for context")


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    timestamp: str
    version: str
    services: Dict[str, str]


class TaskResponse(BaseModel):
    """Response model for task execution."""
    status: str
    task_id: Optional[str] = None
    goal: str
    message: str
    results: Optional[Dict[str, Any]] = None
    duration_seconds: Optional[float] = None


# Health check endpoint
@app.get("/", response_model=HealthResponse)
@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    try:
        # Check database connectivity
        from src.orchestrator.tools import runs_record_event
        db_status = "healthy"
        try:
            runs_record_event("HEALTH_CHECK", {"timestamp": datetime.utcnow().isoformat()})
        except Exception:
            db_status = "unhealthy"
        
        return HealthResponse(
            status="healthy",
            timestamp=datetime.utcnow().isoformat(),
            version="0.1.0",
            services={
                "database": db_status,
                "storage": "healthy",
                "orchestrator": "healthy",
                "voice": "healthy"
            }
        )
    except Exception as e:
        logger.error("Health check failed", error=str(e))
        raise HTTPException(status_code=503, detail="Service unhealthy")


# Task execution endpoint
@app.post("/execute", response_model=TaskResponse)
async def execute_task(request: TaskRequest, background_tasks: BackgroundTasks):
    """Execute an orchestration task."""
    try:
        if request.async_execution:
            # Execute in background
            task_id = f"task_{int(datetime.utcnow().timestamp())}"
            background_tasks.add_task(
                execute_task_async,
                task_id,
                request.goal,
                request.verbose
            )
            return TaskResponse(
                status="accepted",
                task_id=task_id,
                goal=request.goal,
                message=f"Task '{request.goal}' accepted for async execution"
            )
        else:
            # Execute synchronously
            import asyncio
            result = await execute_task_sync(request.goal, request.verbose)
            return TaskResponse(
                status=result["status"],
                goal=request.goal,
                message=result.get("message", "Task completed"),
                results=result.get("results"),
                duration_seconds=result.get("duration_seconds")
            )
    except Exception as e:
        logger.error("Task execution failed", goal=request.goal, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


async def execute_task_sync(goal: str, verbose: bool) -> Dict[str, Any]:
    """Execute task synchronously."""
    start_time = datetime.utcnow()
    
    # Plan and execute
    plan = await orchestrator.plan(goal)
    results = await orchestrator.act(plan)
    
    duration = (datetime.utcnow() - start_time).total_seconds()
    
    return {
        "status": "success",
        "goal": goal,
        "results": results if verbose else None,
        "duration_seconds": duration,
        "message": f"Successfully executed {len(results)} steps"
    }


async def execute_task_async(task_id: str, goal: str, verbose: bool):
    """Execute task asynchronously."""
    logger.info("Starting async task", task_id=task_id, goal=goal)
    try:
        result = await execute_task_sync(goal, verbose)
        logger.info("Async task completed", task_id=task_id, status=result["status"])
    except Exception as e:
        logger.error("Async task failed", task_id=task_id, error=str(e))


# Voice command endpoint
@app.post("/voice", response_model=Dict[str, Any])
async def process_voice(request: VoiceRequest):
    """Process a voice command."""
    try:
        result = await voice_orchestrator.process_voice_command(request.transcript)
        
        if result.get("status") == "success":
            return {
                "status": "success",
                "transcript": request.transcript,
                "response": result.get("response", "Command processed"),
                "function_calls": result.get("function_calls", []),
                "session_id": request.session_id
            }
        else:
            raise HTTPException(
                status_code=400,
                detail=result.get("error", "Voice processing failed")
            )
    except Exception as e:
        logger.error("Voice processing failed", transcript=request.transcript, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


# Status endpoint
@app.get("/status")
async def get_status():
    """Get orchestrator status."""
    try:
        summary = orchestrator.get_execution_summary()
        return {
            "status": "operational",
            "execution_summary": summary,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error("Status check failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


# Plan endpoint (for preview)
@app.post("/plan")
async def create_plan(request: TaskRequest):
    """Create an execution plan without executing."""
    try:
        plan = await orchestrator.plan(request.goal)
        return {
            "status": "success",
            "goal": request.goal,
            "plan": plan,
            "steps_count": len(plan.get("steps", [])),
            "message": "Plan created successfully"
        }
    except Exception as e:
        logger.error("Plan creation failed", goal=request.goal, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


# Startup event
@app.on_event("startup")
async def startup_event():
    """Initialize services on startup."""
    logger.info("Orchestrator Nova starting up",
                project=os.getenv("PROJECT_ID"),
                region=os.getenv("REGION"))
    
    # Verify database connection
    try:
        from src.orchestrator.tools import runs_record_event
        runs_record_event("STARTUP", {
            "timestamp": datetime.utcnow().isoformat(),
            "version": "0.1.0",
            "environment": os.getenv("ENV", "production")
        })
        logger.info("Database connection verified")
    except Exception as e:
        logger.warning("Database connection failed on startup", error=str(e))


# Shutdown event
@app.on_event("shutdown")
async def shutdown_event():
    """Clean up on shutdown."""
    logger.info("Orchestrator Nova shutting down")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)