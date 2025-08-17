"""Gemini Live API integration for voice interactions."""

import os
import json
import asyncio
import logging
from typing import Dict, Any, Optional, Callable, List
from datetime import datetime

import google.generativeai as genai
from google.generativeai.types import FunctionDeclaration, Tool
import structlog

logger = structlog.get_logger(__name__)


class GeminiLiveHandler:
    """Handler for Gemini Live API voice interactions."""
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize Gemini Live handler."""
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            # Use default project authentication
            genai.configure(api_key=None)
        else:
            genai.configure(api_key=self.api_key)
        
        self.model = None
        self.tools = []
        self.function_handlers = {}
        self.conversation_history = []
        
    def register_function(self, name: str, handler: Callable, description: str, parameters: Dict[str, Any]):
        """Register a function that can be called from voice commands."""
        # Create function declaration for Gemini
        func_declaration = FunctionDeclaration(
            name=name,
            description=description,
            parameters=parameters
        )
        
        self.tools.append(func_declaration)
        self.function_handlers[name] = handler
        
        logger.info("Function registered", name=name, description=description)
    
    def initialize_model(self, model_name: str = "gemini-1.5-flash"):
        """Initialize the Gemini model with tools."""
        # Create Tool object with all registered functions
        if self.tools:
            tool = Tool(function_declarations=self.tools)
            self.model = genai.GenerativeModel(
                model_name=model_name,
                tools=[tool]
            )
        else:
            self.model = genai.GenerativeModel(model_name=model_name)
        
        logger.info("Model initialized", model=model_name, tools_count=len(self.tools))
    
    async def process_voice_command(self, transcript: str) -> Dict[str, Any]:
        """Process a voice command and execute functions if needed."""
        if not self.model:
            self.initialize_model()
        
        # Add to conversation history
        self.conversation_history.append({
            "role": "user",
            "parts": [transcript],
            "timestamp": datetime.utcnow().isoformat()
        })
        
        try:
            # Generate response with function calling
            response = self.model.generate_content(transcript)
            
            # Check if function was called
            if hasattr(response, 'candidates') and response.candidates:
                candidate = response.candidates[0]
                
                if hasattr(candidate, 'function_calls') and candidate.function_calls:
                    # Execute function calls
                    results = []
                    for func_call in candidate.function_calls:
                        result = await self._execute_function(
                            func_call.name,
                            func_call.args
                        )
                        results.append({
                            "function": func_call.name,
                            "result": result
                        })
                    
                    # Generate final response with function results
                    final_response = self._generate_response_with_results(transcript, results)
                    
                    return {
                        "status": "success",
                        "transcript": transcript,
                        "function_calls": results,
                        "response": final_response,
                        "timestamp": datetime.utcnow().isoformat()
                    }
            
            # Regular response without function calling
            return {
                "status": "success",
                "transcript": transcript,
                "response": response.text,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error("Voice command processing failed", error=str(e), transcript=transcript)
            return {
                "status": "error",
                "transcript": transcript,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    async def _execute_function(self, function_name: str, args: Dict[str, Any]) -> Any:
        """Execute a registered function."""
        if function_name not in self.function_handlers:
            logger.error("Unknown function called", function=function_name)
            return {"error": f"Unknown function: {function_name}"}
        
        try:
            handler = self.function_handlers[function_name]
            
            # Check if handler is async
            if asyncio.iscoroutinefunction(handler):
                result = await handler(**args)
            else:
                result = await asyncio.to_thread(handler, **args)
            
            logger.info("Function executed", function=function_name, result=result)
            return result
            
        except Exception as e:
            logger.error("Function execution failed", function=function_name, error=str(e))
            return {"error": str(e)}
    
    def _generate_response_with_results(self, original_request: str, results: List[Dict[str, Any]]) -> str:
        """Generate a natural language response based on function results."""
        # Format results for context
        context = f"User request: {original_request}\n\nFunction results:\n"
        for result in results:
            context += f"- {result['function']}: {json.dumps(result['result'], indent=2)}\n"
        
        # Generate response
        prompt = f"{context}\n\nGenerate a natural, conversational response based on these results:"
        
        try:
            response = self.model.generate_content(prompt)
            return response.text
        except Exception as e:
            logger.error("Failed to generate response", error=str(e))
            return f"I've completed the requested actions. {len(results)} functions were executed successfully."
    
    def get_conversation_history(self) -> List[Dict[str, Any]]:
        """Get the conversation history."""
        return self.conversation_history
    
    def clear_history(self):
        """Clear conversation history."""
        self.conversation_history = []
        logger.info("Conversation history cleared")


class VoiceStreamHandler:
    """Handler for real-time voice streaming with Gemini Live."""
    
    def __init__(self, gemini_handler: GeminiLiveHandler):
        """Initialize voice stream handler."""
        self.gemini_handler = gemini_handler
        self.is_streaming = False
        self.stream_session = None
        
    async def start_streaming(self):
        """Start voice streaming session."""
        # This would integrate with actual audio streaming
        # For now, it's a placeholder for the streaming logic
        self.is_streaming = True
        logger.info("Voice streaming started")
        
        # In production, this would:
        # 1. Initialize WebRTC or audio streaming
        # 2. Process audio chunks
        # 3. Send to Gemini for transcription
        # 4. Process commands in real-time
        
    async def stop_streaming(self):
        """Stop voice streaming session."""
        self.is_streaming = False
        logger.info("Voice streaming stopped")
    
    async def process_audio_chunk(self, audio_data: bytes) -> Optional[Dict[str, Any]]:
        """Process an audio chunk and return any commands detected."""
        # This would process actual audio data
        # For now, it's a placeholder
        pass