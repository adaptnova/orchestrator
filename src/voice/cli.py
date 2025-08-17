#!/usr/bin/env python3
"""CLI for voice-enabled orchestrator."""

import os
import sys
import asyncio
from pathlib import Path

import click
from rich.console import Console

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.voice.voice_orchestrator import VoiceOrchestrator

console = Console()


@click.group()
def cli():
    """Voice-enabled Orchestrator Nova CLI."""
    pass


@cli.command()
def interactive():
    """Start interactive voice session."""
    console.print("[cyan]Initializing Voice Orchestrator...[/cyan]")
    
    # Set up Google credentials if available
    sa_key_path = Path("sa-key.json")
    if sa_key_path.exists():
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(sa_key_path.absolute())
    
    orchestrator = VoiceOrchestrator()
    
    console.print("[green]✓ Voice Orchestrator initialized[/green]")
    console.print("[yellow]Starting interactive session...[/yellow]\n")
    
    # Run interactive session
    asyncio.run(orchestrator.start_voice_session())


@cli.command()
@click.argument("command")
def process(command: str):
    """Process a single voice command."""
    console.print(f"[cyan]Processing: {command}[/cyan]")
    
    # Set up Google credentials if available
    sa_key_path = Path("sa-key.json")
    if sa_key_path.exists():
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(sa_key_path.absolute())
    
    orchestrator = VoiceOrchestrator()
    
    # Process command
    result = asyncio.run(orchestrator.process_voice_command(command))
    
    if result.get("status") == "success":
        console.print(f"[green]✓ Success[/green]")
        if result.get("response"):
            console.print(f"\n{result['response']}")
        if result.get("function_calls"):
            console.print("\n[cyan]Functions executed:[/cyan]")
            for call in result["function_calls"]:
                console.print(f"  • {call['function']}: {call['result'].get('message', 'Completed')}")
    else:
        console.print(f"[red]✗ Error: {result.get('error', 'Unknown error')}[/red]")


@cli.command()
def test():
    """Test voice functions."""
    console.print("[cyan]Testing voice functions...[/cyan]\n")
    
    # Set up Google credentials if available
    sa_key_path = Path("sa-key.json")
    if sa_key_path.exists():
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(sa_key_path.absolute())
    
    orchestrator = VoiceOrchestrator()
    
    # Test commands
    test_commands = [
        "Check the orchestrator status",
        "Run an ETL pipeline for test data",
        "Create an artifact with the message 'Voice test successful'"
    ]
    
    async def run_tests():
        for cmd in test_commands:
            console.print(f"[yellow]Testing:[/yellow] {cmd}")
            result = await orchestrator.process_voice_command(cmd)
            if result.get("status") == "success":
                console.print(f"  [green]✓ Passed[/green]")
            else:
                console.print(f"  [red]✗ Failed: {result.get('error')}[/red]")
            console.print("")
    
    asyncio.run(run_tests())
    console.print("[green]Voice function tests completed![/green]")


if __name__ == "__main__":
    cli()