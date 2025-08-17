#!/usr/bin/env python3
"""Main entry point for Orchestrator Nova."""

import os
import sys
import json
import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

import click
import structlog
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn

from .orchestrator import Orchestrator
from .tools import runs_record_event, artifacts_write_text, etl_run_job

# Load environment variables
env_path = Path(__file__).parent.parent.parent / ".claude/projects/agents-gcp/.env"
if env_path.exists():
    load_dotenv(env_path)

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)
console = Console()


class OrchestrationEngine:
    """Main orchestration engine for task execution."""
    
    def __init__(self):
        self.orchestrator = Orchestrator()
        self.console = console
        
    async def execute_task(self, goal: str, verbose: bool = False) -> Dict[str, Any]:
        """Execute a task with the given goal."""
        start_time = datetime.utcnow()
        
        # Record start event
        await self._record_event("TASK_START", {"goal": goal, "timestamp": start_time.isoformat()})
        
        try:
            # Plan the task
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=self.console,
            ) as progress:
                plan_task = progress.add_task("[cyan]Planning task...", total=None)
                plan = await self.orchestrator.plan(goal)
                progress.update(plan_task, completed=True)
                
            if verbose:
                self._display_plan(plan)
            
            # Execute the plan
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=self.console,
            ) as progress:
                exec_task = progress.add_task("[green]Executing plan...", total=len(plan["steps"]))
                results = []
                
                for i, step in enumerate(plan["steps"]):
                    result = await self.orchestrator.execute_step(step)
                    results.append(result)
                    progress.update(exec_task, advance=1)
                    
                    if verbose:
                        self.console.print(f"  ✓ {step['tool']}: {result.get('status', 'unknown')}")
            
            # Record completion
            end_time = datetime.utcnow()
            duration = (end_time - start_time).total_seconds()
            
            await self._record_event("TASK_COMPLETE", {
                "goal": goal,
                "duration_seconds": duration,
                "steps_completed": len(results),
                "timestamp": end_time.isoformat()
            })
            
            return {
                "status": "success",
                "goal": goal,
                "plan": plan,
                "results": results,
                "duration_seconds": duration
            }
            
        except Exception as e:
            logger.error("Task execution failed", goal=goal, error=str(e))
            await self._record_event("TASK_ERROR", {
                "goal": goal,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            })
            raise
    
    async def _record_event(self, event_type: str, details: Dict[str, Any]):
        """Record an event to the database."""
        try:
            await asyncio.to_thread(runs_record_event, event_type, details)
        except Exception as e:
            logger.warning("Failed to record event", event_type=event_type, error=str(e))
    
    def _display_plan(self, plan: Dict[str, Any]):
        """Display the execution plan in a table."""
        table = Table(title="Execution Plan", show_header=True, header_style="bold magenta")
        table.add_column("Step", style="dim", width=6)
        table.add_column("Tool", style="cyan")
        table.add_column("Arguments", style="green")
        
        for i, step in enumerate(plan["steps"], 1):
            args_str = json.dumps(step.get("args", {}), indent=2)
            if len(args_str) > 50:
                args_str = args_str[:47] + "..."
            table.add_row(str(i), step["tool"], args_str)
        
        self.console.print(table)


@click.group()
@click.option("--debug", is_flag=True, help="Enable debug logging")
def cli(debug: bool):
    """Orchestrator Nova - AI Agent Orchestration System."""
    if debug:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)


@cli.command()
@click.argument("goal")
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
@click.option("--dry-run", is_flag=True, help="Show plan without executing")
def run(goal: str, verbose: bool, dry_run: bool):
    """Execute a task with the given goal."""
    engine = OrchestrationEngine()
    
    try:
        if dry_run:
            console.print("[yellow]Dry run mode - showing plan only[/yellow]")
            plan = asyncio.run(engine.orchestrator.plan(goal))
            engine._display_plan(plan)
            console.print("\n[green]Plan generated successfully![/green]")
        else:
            result = asyncio.run(engine.execute_task(goal, verbose))
            console.print(f"\n[green]✓ Task completed successfully![/green]")
            console.print(f"Duration: {result['duration_seconds']:.2f} seconds")
            console.print(f"Steps completed: {len(result['results'])}")
            
    except Exception as e:
        console.print(f"[red]✗ Task failed: {str(e)}[/red]")
        sys.exit(1)


@cli.command()
def test():
    """Test database and storage connectivity."""
    console.print("[cyan]Testing infrastructure connectivity...[/cyan]\n")
    
    results = []
    
    # Test database
    try:
        result = runs_record_event("TEST", {"message": "Connectivity test"})
        results.append(("PostgreSQL", "✓", "Connected"))
        console.print("[green]✓[/green] PostgreSQL connection successful")
    except Exception as e:
        results.append(("PostgreSQL", "✗", str(e)[:30]))
        console.print(f"[red]✗[/red] PostgreSQL connection failed: {e}")
    
    # Test storage
    try:
        result = artifacts_write_text("test/connection.txt", "Test content")
        results.append(("Cloud Storage", "✓", result.get("gs_uri", "Unknown")))
        console.print("[green]✓[/green] Cloud Storage connection successful")
    except Exception as e:
        results.append(("Cloud Storage", "✗", str(e)[:30]))
        console.print(f"[red]✗[/red] Cloud Storage connection failed: {e}")
    
    # Test ETL runner
    try:
        result = etl_run_job({"test": True})
        results.append(("ETL Runner", "✓", "Working"))
        console.print("[green]✓[/green] ETL runner operational")
    except Exception as e:
        results.append(("ETL Runner", "✗", str(e)[:30]))
        console.print(f"[red]✗[/red] ETL runner failed: {e}")
    
    # Display summary
    console.print("\n[bold]Connectivity Test Summary:[/bold]")
    table = Table(show_header=True, header_style="bold blue")
    table.add_column("Component", style="dim")
    table.add_column("Status", justify="center")
    table.add_column("Details")
    
    for component, status, details in results:
        status_style = "green" if status == "✓" else "red"
        table.add_row(component, f"[{status_style}]{status}[/{status_style}]", details)
    
    console.print(table)


@cli.command()
def version():
    """Show version information."""
    from . import __version__
    console.print(f"Orchestrator Nova v{__version__}")
    console.print(f"Python {sys.version}")
    console.print(f"Project: {os.getenv('PROJECT_ID', 'Not configured')}")
    console.print(f"Region: {os.getenv('REGION', 'Not configured')}")


if __name__ == "__main__":
    cli()