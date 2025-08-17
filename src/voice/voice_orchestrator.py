"""Voice-enabled orchestrator that integrates Gemini Live with Orchestrator Nova."""

import asyncio
import json
from typing import Dict, Any, Optional
from datetime import datetime

import structlog
from ..orchestrator import Orchestrator, runs_record_event, artifacts_write_text, etl_run_job
from .gemini_live import GeminiLiveHandler

logger = structlog.get_logger(__name__)


class VoiceOrchestrator:
    """Voice-enabled orchestrator combining Gemini Live and Orchestrator Nova."""
    
    def __init__(self):
        """Initialize voice orchestrator."""
        self.orchestrator = Orchestrator()
        self.voice_handler = GeminiLiveHandler()
        self.setup_voice_functions()
        
    def setup_voice_functions(self):
        """Register orchestrator functions for voice control."""
        
        # Register task execution
        self.voice_handler.register_function(
            name="execute_task",
            handler=self.execute_task,
            description="Execute an orchestration task with a specific goal",
            parameters={
                "type": "object",
                "properties": {
                    "goal": {
                        "type": "string",
                        "description": "The goal or task to execute"
                    },
                    "verbose": {
                        "type": "boolean",
                        "description": "Whether to provide detailed output"
                    }
                },
                "required": ["goal"]
            }
        )
        
        # Register status check
        self.voice_handler.register_function(
            name="check_status",
            handler=self.check_status,
            description="Check the status of the orchestrator and recent tasks",
            parameters={
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Number of recent tasks to show"
                    }
                }
            }
        )
        
        # Register ETL job execution
        self.voice_handler.register_function(
            name="run_etl",
            handler=self.run_etl,
            description="Run an ETL pipeline job",
            parameters={
                "type": "object",
                "properties": {
                    "pipeline_name": {
                        "type": "string",
                        "description": "Name of the ETL pipeline to run"
                    },
                    "parameters": {
                        "type": "object",
                        "description": "Parameters for the ETL job"
                    }
                },
                "required": ["pipeline_name"]
            }
        )
        
        # Register artifact creation
        self.voice_handler.register_function(
            name="create_artifact",
            handler=self.create_artifact,
            description="Create and store an artifact",
            parameters={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Name for the artifact"
                    },
                    "content": {
                        "type": "string",
                        "description": "Content of the artifact"
                    },
                    "path": {
                        "type": "string",
                        "description": "Storage path for the artifact"
                    }
                },
                "required": ["name", "content"]
            }
        )
        
        # Register training job
        self.voice_handler.register_function(
            name="start_training",
            handler=self.start_training,
            description="Start a model training job",
            parameters={
                "type": "object",
                "properties": {
                    "model_name": {
                        "type": "string",
                        "description": "Name of the model to train"
                    },
                    "config": {
                        "type": "object",
                        "description": "Training configuration",
                        "properties": {
                            "epochs": {
                                "type": "integer",
                                "description": "Number of training epochs"
                            },
                            "batch_size": {
                                "type": "integer",
                                "description": "Training batch size"
                            }
                        }
                    }
                },
                "required": ["model_name"]
            }
        )
        
        # Initialize model with functions
        self.voice_handler.initialize_model()
        logger.info("Voice functions registered", count=5)
    
    async def execute_task(self, goal: str, verbose: bool = False) -> Dict[str, Any]:
        """Execute an orchestration task."""
        try:
            # Record voice command
            await asyncio.to_thread(
                runs_record_event,
                "VOICE_COMMAND",
                {"goal": goal, "source": "gemini_live"}
            )
            
            # Plan the task
            plan = await self.orchestrator.plan(goal)
            
            # Execute the plan
            results = await self.orchestrator.act(plan)
            
            # Record completion
            await asyncio.to_thread(
                runs_record_event,
                "VOICE_COMPLETE",
                {
                    "goal": goal,
                    "steps_completed": len(results),
                    "status": "success"
                }
            )
            
            return {
                "status": "success",
                "goal": goal,
                "steps_completed": len(results),
                "plan": plan if verbose else None,
                "message": f"Successfully executed task: {goal}"
            }
            
        except Exception as e:
            logger.error("Task execution failed", goal=goal, error=str(e))
            return {
                "status": "error",
                "goal": goal,
                "error": str(e),
                "message": f"Failed to execute task: {str(e)}"
            }
    
    async def check_status(self, limit: int = 5) -> Dict[str, Any]:
        """Check orchestrator status and recent tasks."""
        try:
            summary = self.orchestrator.get_execution_summary()
            
            return {
                "status": "success",
                "orchestrator_status": "operational",
                "execution_summary": summary,
                "message": f"Orchestrator is operational. {summary.get('total_executions', 0)} tasks executed."
            }
            
        except Exception as e:
            logger.error("Status check failed", error=str(e))
            return {
                "status": "error",
                "error": str(e),
                "message": "Failed to check status"
            }
    
    async def run_etl(self, pipeline_name: str, parameters: Dict[str, Any] = None) -> Dict[str, Any]:
        """Run an ETL pipeline."""
        try:
            # Record ETL request
            await asyncio.to_thread(
                runs_record_event,
                "ETL_START",
                {"pipeline": pipeline_name, "parameters": parameters}
            )
            
            # Execute ETL job
            result = await asyncio.to_thread(
                etl_run_job,
                {
                    "pipeline": pipeline_name,
                    "parameters": parameters or {},
                    "triggered_by": "voice_command"
                }
            )
            
            return {
                "status": "success",
                "pipeline": pipeline_name,
                "job_id": result.get("job_id"),
                "duration_ms": result.get("duration_ms"),
                "message": f"ETL pipeline '{pipeline_name}' executed successfully"
            }
            
        except Exception as e:
            logger.error("ETL execution failed", pipeline=pipeline_name, error=str(e))
            return {
                "status": "error",
                "pipeline": pipeline_name,
                "error": str(e),
                "message": f"Failed to run ETL pipeline: {str(e)}"
            }
    
    async def create_artifact(self, name: str, content: str, path: str = "artifacts/") -> Dict[str, Any]:
        """Create and store an artifact."""
        try:
            # Generate full path
            timestamp = int(datetime.utcnow().timestamp())
            full_path = f"{path}{name}_{timestamp}.txt"
            
            # Write artifact
            result = await asyncio.to_thread(
                artifacts_write_text,
                full_path,
                content
            )
            
            return {
                "status": "success",
                "artifact_name": name,
                "gs_uri": result.get("gs_uri"),
                "size_bytes": result.get("size_bytes"),
                "message": f"Artifact '{name}' created successfully"
            }
            
        except Exception as e:
            logger.error("Artifact creation failed", name=name, error=str(e))
            return {
                "status": "error",
                "artifact_name": name,
                "error": str(e),
                "message": f"Failed to create artifact: {str(e)}"
            }
    
    async def start_training(self, model_name: str, config: Dict[str, Any] = None) -> Dict[str, Any]:
        """Start a model training job."""
        try:
            from ..orchestrator.tools import train_model
            
            # Set default config
            if config is None:
                config = {"epochs": 10, "batch_size": 32}
            
            # Record training request
            await asyncio.to_thread(
                runs_record_event,
                "TRAINING_START",
                {"model": model_name, "config": config, "source": "voice_command"}
            )
            
            # Start training
            result = await asyncio.to_thread(
                train_model,
                model_name,
                config
            )
            
            return {
                "status": "success",
                "model_name": model_name,
                "job_id": result.get("job_id"),
                "config": config,
                "message": f"Training job for '{model_name}' started successfully"
            }
            
        except Exception as e:
            logger.error("Training start failed", model=model_name, error=str(e))
            return {
                "status": "error",
                "model_name": model_name,
                "error": str(e),
                "message": f"Failed to start training: {str(e)}"
            }
    
    async def process_voice_command(self, transcript: str) -> Dict[str, Any]:
        """Process a voice command through the orchestrator."""
        logger.info("Processing voice command", transcript=transcript)
        
        # Process through Gemini with registered functions
        result = await self.voice_handler.process_voice_command(transcript)
        
        # Log the result
        if result.get("status") == "success":
            logger.info("Voice command processed", 
                       transcript=transcript,
                       function_calls=result.get("function_calls"))
        else:
            logger.error("Voice command failed",
                        transcript=transcript,
                        error=result.get("error"))
        
        return result
    
    async def start_voice_session(self):
        """Start an interactive voice session."""
        logger.info("Starting voice session")
        
        print("\n🎤 Voice Orchestrator Active")
        print("Say commands like:")
        print("  - 'Execute task to process ETL pipeline'")
        print("  - 'Check orchestrator status'")
        print("  - 'Run ETL pipeline for customer data'")
        print("  - 'Create an artifact with today's report'")
        print("  - 'Start training the recommendation model'")
        print("\nType 'exit' to quit\n")
        
        while True:
            try:
                # In production, this would capture actual voice input
                # For now, we use text input as a simulation
                command = input("🎤 Voice command (or type): ")
                
                if command.lower() in ['exit', 'quit', 'stop']:
                    break
                
                # Process the command
                result = await self.process_voice_command(command)
                
                # Display result
                if result.get("response"):
                    print(f"\n🤖 {result['response']}\n")
                else:
                    print(f"\n🤖 Command processed: {result.get('message', 'Success')}\n")
                
            except KeyboardInterrupt:
                break
            except Exception as e:
                logger.error("Voice session error", error=str(e))
                print(f"\n❌ Error: {str(e)}\n")
        
        print("\n👋 Voice session ended")
        logger.info("Voice session ended")