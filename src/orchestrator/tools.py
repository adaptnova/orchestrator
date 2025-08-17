"""Tool implementations for Orchestrator Nova."""

import os
import json
import time
import asyncio
from datetime import datetime
from typing import Dict, Any, Optional
from pathlib import Path

import psycopg
from google.cloud import storage
# from google.cloud.sql.connector import Connector  # Optional, not needed for public IP
import structlog

logger = structlog.get_logger(__name__)

# Database connection configuration
def get_db_connection_string() -> str:
    """Get the database connection string."""
    # Check if running in Cloud Run/GCP
    if os.getenv("K_SERVICE"):
        # Use Unix socket in GCP
        return (
            f"host=/cloudsql/{os.environ['PROJECT_ID']}:{os.environ['REGION']}:{os.environ['SQL_INSTANCE_ID']} "
            f"dbname={os.environ['SQL_DB_NAME']} user={os.environ['SQL_USER']} password={os.environ['SQL_PASS']}"
        )
    else:
        # Use direct public IP connection for development
        # SQL instance has public IP: 34.31.222.209
        return (
            f"host=34.31.222.209 port=5432 "
            f"dbname={os.environ.get('SQL_DB_NAME', 'orch_runs')} "
            f"user={os.environ.get('SQL_USER', 'orch_admin')} "
            f"password={os.environ.get('SQL_PASS', '@@ALALzmzm102938!!')}"
        )


def runs_record_event(event_type: str, details: Dict[str, Any]) -> Dict[str, Any]:
    """
    Record a run event in PostgreSQL.
    
    Args:
        event_type: Type of event (e.g., PLAN, EXECUTE, DONE, ERROR)
        details: Event details as a dictionary
    
    Returns:
        Dictionary with status and run_event_id
    """
    try:
        conn_str = get_db_connection_string()
        
        with psycopg.connect(conn_str) as conn:
            with conn.cursor() as cur:
                # Create table if not exists
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS run_events (
                        id BIGSERIAL PRIMARY KEY,
                        ts TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        event_type TEXT NOT NULL,
                        details JSONB NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Insert event
                cur.execute(
                    """
                    INSERT INTO run_events (ts, event_type, details) 
                    VALUES (%s, %s, %s) 
                    RETURNING id
                    """,
                    (datetime.utcnow(), event_type, json.dumps(details))
                )
                
                run_id = cur.fetchone()[0]
                conn.commit()
                
                logger.info("Event recorded", event_type=event_type, run_id=run_id)
                
                return {
                    "status": "success",
                    "run_event_id": run_id,
                    "timestamp": datetime.utcnow().isoformat()
                }
                
    except Exception as e:
        logger.error("Failed to record event", event_type=event_type, error=str(e))
        raise


def artifacts_write_text(path: str, content: str) -> Dict[str, Any]:
    """
    Write a text artifact to Cloud Storage.
    
    Args:
        path: Path within the bucket for the artifact
        content: Text content to write
    
    Returns:
        Dictionary with status and gs_uri
    """
    try:
        client = storage.Client(project=os.environ.get("PROJECT_ID", "echovaeris"))
        bucket_name = os.environ.get("GCS_BUCKET", f"orchestrator-{os.environ.get('PROJECT_ID', 'echovaeris')}-{os.environ.get('REGION', 'us-central1')}")
        
        # Remove gs:// prefix if present
        if bucket_name.startswith("gs://"):
            bucket_name = bucket_name[5:].rstrip("/")
        
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(path)
        
        # Add metadata
        blob.metadata = {
            "created_by": "orchestrator-nova",
            "timestamp": datetime.utcnow().isoformat(),
            "content_type": "text/plain"
        }
        
        # Upload content
        blob.upload_from_string(content.encode("utf-8"))
        
        gs_uri = f"gs://{bucket_name}/{path}"
        logger.info("Artifact written", path=path, gs_uri=gs_uri, size=len(content))
        
        return {
            "status": "success",
            "gs_uri": gs_uri,
            "size_bytes": len(content),
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error("Failed to write artifact", path=path, error=str(e))
        raise


def etl_run_job(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute an ETL job (placeholder implementation).
    
    Args:
        payload: Job configuration and parameters
    
    Returns:
        Dictionary with job execution results
    """
    try:
        job_id = f"etl_{int(time.time())}"
        start_time = datetime.utcnow()
        
        logger.info("Starting ETL job", job_id=job_id, payload=payload)
        
        # Simulate job execution
        # In production, this would trigger actual ETL pipeline
        time.sleep(1)  # Simulate processing
        
        # Record job metadata
        job_metadata = {
            "job_id": job_id,
            "job_type": "ETL",
            "payload": payload,
            "start_time": start_time.isoformat(),
            "status": "running"
        }
        
        # In production, this would:
        # 1. Submit job to Cloud Run Jobs or Dataflow
        # 2. Track job progress
        # 3. Return job handle for monitoring
        
        end_time = datetime.utcnow()
        duration_ms = int((end_time - start_time).total_seconds() * 1000)
        
        result = {
            "status": "success",
            "job_id": job_id,
            "echo": payload,
            "duration_ms": duration_ms,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat()
        }
        
        logger.info("ETL job completed", job_id=job_id, duration_ms=duration_ms)
        
        return result
        
    except Exception as e:
        logger.error("ETL job failed", payload=payload, error=str(e))
        raise


def train_model(model_name: str, config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Start a model training job.
    
    Args:
        model_name: Name of the model to train
        config: Training configuration
    
    Returns:
        Dictionary with training job details
    """
    try:
        job_id = f"train_{model_name}_{int(time.time())}"
        
        logger.info("Starting training job", job_id=job_id, model_name=model_name)
        
        # In production, this would:
        # 1. Submit training job to Vertex AI
        # 2. Configure compute resources
        # 3. Set up monitoring
        
        return {
            "status": "submitted",
            "job_id": job_id,
            "model_name": model_name,
            "config": config,
            "estimated_duration_minutes": 30,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error("Failed to start training", model_name=model_name, error=str(e))
        raise


def deploy_agent(agent_name: str, version: str, config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Deploy an agent to Vertex AI.
    
    Args:
        agent_name: Name of the agent to deploy
        version: Version to deploy
        config: Deployment configuration
    
    Returns:
        Dictionary with deployment details
    """
    try:
        deployment_id = f"deploy_{agent_name}_{version}_{int(time.time())}"
        
        logger.info("Deploying agent", deployment_id=deployment_id, agent_name=agent_name, version=version)
        
        # In production, this would:
        # 1. Build container image
        # 2. Push to Container Registry
        # 3. Deploy to Cloud Run or Vertex AI
        # 4. Configure endpoints
        
        return {
            "status": "deployed",
            "deployment_id": deployment_id,
            "agent_name": agent_name,
            "version": version,
            "endpoint": f"https://{os.environ.get('REGION', 'us-central1')}-aiplatform.googleapis.com/v1/projects/{os.environ.get('PROJECT_ID', 'echovaeris')}/endpoints/{deployment_id}",
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error("Failed to deploy agent", agent_name=agent_name, version=version, error=str(e))
        raise


# Tool registry for dynamic invocation
TOOL_REGISTRY = {
    "runs_record_event": runs_record_event,
    "artifacts_write_text": artifacts_write_text,
    "etl_run_job": etl_run_job,
    "train_model": train_model,
    "deploy_agent": deploy_agent,
}


def get_tool(tool_name: str):
    """Get a tool function by name."""
    if tool_name not in TOOL_REGISTRY:
        raise ValueError(f"Unknown tool: {tool_name}")
    return TOOL_REGISTRY[tool_name]