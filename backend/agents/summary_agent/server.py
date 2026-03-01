"""
Summary A2A Agent Server
Uses the SummaryExecutor and Summary Agent components
"""
import os
import uvicorn
from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentSkill,
)
from starlette.routing import Route
from starlette.middleware.cors import CORSMiddleware

from backend.agents.summary_agent.routes.summary_health import get_summary_health
from backend.agents.summary_agent.summary_executor import SummaryExecutor

# Set Google API key explicitly
os.environ["GOOGLE_API_KEY"] = os.getenv('GOOGLE_API_KEY', "***REMOVED***")


def build_summary_app():
    """Build and return the Summary A2A Starlette application"""
    print("[START] Building Summary A2A Agent App...")
    # Check for required environment variables
    if not os.getenv('GOOGLE_API_KEY'):
        print("[ERROR] GOOGLE_API_KEY environment variable not set")
        # Still build; env can be injected at run
    
    # Load skills from MCP instance
    skill = AgentSkill(
            id="summary_agent",
            name="Summary Agent",
            description='A dedicated Summary assistant that summarizes the transcripts at the end of the conversations or on export',
            tags=["summary", "export"],
            )

    # Create agent card
    agent_card = AgentCard(
        name='Summary Agent',
        description='A dedicated Summary assistant that summarizes the transcripts at the end of the conversations or on export',
        url=os.environ.get('SUMMARY_AGENT', 'http://localhost:8003'),
        version='1.0.0',
        default_input_modes=['text'],
        default_output_modes=['text'],
        capabilities=AgentCapabilities(streaming=True),
        skills=[skill],
    )
             
    # Create executor
    agent_executor = SummaryExecutor(agent_card)
    
    # Create request handler
    request_handler = DefaultRequestHandler(
        agent_executor=agent_executor, 
        task_store=InMemoryTaskStore()
    )
    
    # Create A2A application
    a2a_app = A2AStarletteApplication(
        agent_card=agent_card, 
        http_handler=request_handler
    )

    app = a2a_app.build()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # adjust to specific origins if needed
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.routes.append(Route("/health", get_summary_health, methods=["GET"]))
    return app


# Module-level app for uvicorn path syntax
summary_app = build_summary_app()


def main():
    """Main function to start the Summary agent server"""
    print("[SERVER] Starting server...")
    uvicorn.run(
        "backend.agents.faq_agent.server:summary_app",
        host="0.0.0.0",
        port=8003,
        reload=True,
        log_level="info",
    )

if __name__ == "__main__":
    main()
