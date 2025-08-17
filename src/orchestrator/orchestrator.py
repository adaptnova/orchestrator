"""Core Orchestrator class for task planning and execution."""

import asyncio
import json
from typing import Dict, Any, List, Optional
from datetime import datetime
from enum import Enum

import structlog
from pydantic import BaseModel, Field

from .tools import get_tool, TOOL_REGISTRY

logger = structlog.get_logger(__name__)


class TaskStatus(str, Enum):
    """Task execution status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskStep(BaseModel):
    """Single step in a task plan."""
    tool: str = Field(..., description="Tool to execute")
    args: Dict[str, Any] = Field(default_factory=dict, description="Tool arguments")
    depends_on: List[int] = Field(default_factory=list, description="Step dependencies")
    timeout: int = Field(default=300, description="Timeout in seconds")
    retry_count: int = Field(default=3, description="Number of retries on failure")


class TaskPlan(BaseModel):
    """Complete task execution plan."""
    goal: str = Field(..., description="Task goal")
    steps: List[TaskStep] = Field(..., description="Execution steps")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Plan metadata")
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Orchestrator:
    """Main orchestrator for task planning and execution."""
    
    def __init__(self):
        self.logger = logger
        self.tools = TOOL_REGISTRY
        self.current_plan: Optional[TaskPlan] = None
        self.execution_history: List[Dict[str, Any]] = []
    
    async def plan(self, goal: str) -> Dict[str, Any]:
        """
        Create an execution plan for the given goal.
        
        This is a simplified planner. In production, this would use:
        - LLM for dynamic planning
        - Task decomposition algorithms
        - Dependency analysis
        - Resource optimization
        """
        self.logger.info("Creating plan", goal=goal)
        
        # Determine plan based on goal keywords
        steps = []
        
        # Always start with recording the plan
        steps.append(TaskStep(
            tool="runs_record_event",
            args={"event_type": "PLAN", "details": {"goal": goal}}
        ))
        
        # Analyze goal and add appropriate steps
        goal_lower = goal.lower()
        
        if "etl" in goal_lower or "data" in goal_lower or "pipeline" in goal_lower:
            steps.append(TaskStep(
                tool="etl_run_job",
                args={"payload": {"goal": goal, "pipeline": "default"}},
                depends_on=[0]
            ))
            steps.append(TaskStep(
                tool="artifacts_write_text",
                args={
                    "path": f"etl/results/{int(datetime.utcnow().timestamp())}.json",
                    "content": json.dumps({"goal": goal, "status": "completed"})
                },
                depends_on=[1]
            ))
        
        elif "train" in goal_lower or "model" in goal_lower:
            steps.append(TaskStep(
                tool="train_model",
                args={
                    "model_name": "orchestrator-model",
                    "config": {"epochs": 10, "batch_size": 32}
                },
                depends_on=[0]
            ))
            steps.append(TaskStep(
                tool="artifacts_write_text",
                args={
                    "path": f"training/logs/{int(datetime.utcnow().timestamp())}.txt",
                    "content": f"Training initiated for goal: {goal}"
                },
                depends_on=[1]
            ))
        
        elif "deploy" in goal_lower or "agent" in goal_lower:
            steps.append(TaskStep(
                tool="deploy_agent",
                args={
                    "agent_name": "orchestrator-nova",
                    "version": "v1.0.0",
                    "config": {"replicas": 1, "memory": "2Gi"}
                },
                depends_on=[0]
            ))
        
        else:
            # Default workflow
            steps.append(TaskStep(
                tool="etl_run_job",
                args={"payload": {"goal": goal, "type": "generic"}},
                depends_on=[0]
            ))
            steps.append(TaskStep(
                tool="artifacts_write_text",
                args={
                    "path": f"runs/{int(datetime.utcnow().timestamp())}.txt",
                    "content": f"Goal: {goal}\nStatus: Processing"
                },
                depends_on=[1]
            ))
        
        # Always end with recording completion
        steps.append(TaskStep(
            tool="runs_record_event",
            args={"event_type": "DONE", "details": {"goal": goal}},
            depends_on=[len(steps) - 1] if len(steps) > 1 else []
        ))
        
        # Create plan
        plan = TaskPlan(
            goal=goal,
            steps=steps,
            metadata={
                "planner_version": "1.0.0",
                "estimated_duration_seconds": len(steps) * 5
            }
        )
        
        self.current_plan = plan
        
        return {
            "goal": plan.goal,
            "steps": [step.dict() for step in plan.steps],
            "metadata": plan.metadata,
            "created_at": plan.created_at.isoformat()
        }
    
    async def execute_step(self, step: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a single step from the plan."""
        step_obj = TaskStep(**step) if isinstance(step, dict) else step
        
        self.logger.info("Executing step", tool=step_obj.tool, args=step_obj.args)
        
        try:
            # Get the tool function
            tool_func = get_tool(step_obj.tool)
            
            # Execute with timeout
            result = await asyncio.wait_for(
                asyncio.to_thread(tool_func, **step_obj.args),
                timeout=step_obj.timeout
            )
            
            # Record execution
            self.execution_history.append({
                "tool": step_obj.tool,
                "args": step_obj.args,
                "result": result,
                "status": "success",
                "timestamp": datetime.utcnow().isoformat()
            })
            
            return result
            
        except asyncio.TimeoutError:
            self.logger.error("Step timed out", tool=step_obj.tool, timeout=step_obj.timeout)
            return {
                "status": "timeout",
                "tool": step_obj.tool,
                "error": f"Step timed out after {step_obj.timeout} seconds"
            }
        
        except Exception as e:
            self.logger.error("Step failed", tool=step_obj.tool, error=str(e))
            
            # Record failure
            self.execution_history.append({
                "tool": step_obj.tool,
                "args": step_obj.args,
                "error": str(e),
                "status": "failed",
                "timestamp": datetime.utcnow().isoformat()
            })
            
            # Retry logic would go here
            return {
                "status": "error",
                "tool": step_obj.tool,
                "error": str(e)
            }
    
    async def act(self, plan: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Execute all steps in a plan."""
        results = []
        
        for step in plan["steps"]:
            result = await self.execute_step(step)
            results.append({
                "tool": step["tool"],
                "result": result
            })
            
            # Stop on critical failure
            if result.get("status") == "error" and step["tool"] == "runs_record_event":
                self.logger.warning("Critical step failed, continuing anyway", tool=step["tool"])
        
        return results
    
    def validate_plan(self, plan: Dict[str, Any]) -> bool:
        """Validate that a plan is executable."""
        try:
            # Check all tools exist
            for step in plan["steps"]:
                if step["tool"] not in self.tools:
                    self.logger.error("Unknown tool in plan", tool=step["tool"])
                    return False
            
            # Check dependencies are valid
            for i, step in enumerate(plan["steps"]):
                for dep in step.get("depends_on", []):
                    if dep >= i:
                        self.logger.error("Invalid dependency", step=i, depends_on=dep)
                        return False
            
            return True
            
        except Exception as e:
            self.logger.error("Plan validation failed", error=str(e))
            return False
    
    def get_execution_summary(self) -> Dict[str, Any]:
        """Get summary of execution history."""
        if not self.execution_history:
            return {"message": "No execution history"}
        
        successful = sum(1 for h in self.execution_history if h.get("status") == "success")
        failed = sum(1 for h in self.execution_history if h.get("status") == "failed")
        
        return {
            "total_executions": len(self.execution_history),
            "successful": successful,
            "failed": failed,
            "success_rate": successful / len(self.execution_history) if self.execution_history else 0,
            "last_execution": self.execution_history[-1] if self.execution_history else None
        }