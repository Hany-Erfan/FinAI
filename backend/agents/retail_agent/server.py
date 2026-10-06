"""
Retail A2A Agent Server
Uses the RetailExecutor and Retail Agent components
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
from backend.agents.retail_agent.retail_executor import RetailExecutor
from backend.agents.retail_agent.routes.retail_health import get_retail_health
from observability import setup_telemetry, setup_logging, instrument_app


# Set Google API key explicitly
os.environ["GOOGLE_API_KEY"] = os.getenv('GOOGLE_API_KEY', "")


def build_retail_app():
    """Build and return the Retail A2A Starlette application"""
    print("[START] Building Retail A2A Agent App...")
    # Check for required environment variables
    if not os.getenv('GOOGLE_API_KEY'):
        print("[ERROR] GOOGLE_API_KEY environment variable not set")
        # Still build; env can be injected at run
    
    # Load skills from MCP instance
    skill = AgentSkill(
            id="retail_banking_services",
            name="Retail Banking Services",
            description="Accesses user-specific banking information including account balances, transaction history, and account details.",
            examples=[
                "What is my current account balance?",
                "Show me my last 5 transactions.",
            ],
            tags=["banking", "balance", "transactions"],
        )
        
    # Create agent card
    agent_card = AgentCard(
        name='Retail Agent',
        description='A retail banking assistant that helps customers with account information, balances, transactions. Provides real-time account balances, detailed account information and transaction history.',
        url=os.environ.get('RETAIL_AGENT_URL', 'http://localhost:8002'),
        version='1.0.0',
        default_input_modes=['text'],
        default_output_modes=['text'],
        capabilities=AgentCapabilities(streaming=True),
        skills=[skill],
    )

    # Create executor using your existing InventoryExecutor
    agent_executor = RetailExecutor(agent_card)
    
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
    instrument_app(app)

    @app.on_event("startup")
    async def startup_event():
        setup_telemetry()
        setup_logging()

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # adjust to specific origins if needed
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.routes.append(Route("/health", get_retail_health, methods=["GET"]))
    return app


# Module-level app for uvicorn path syntax
retail_app = build_retail_app()


def main():
    """Main function to start the retail agent server"""
    print("[SERVER] Starting server...")
    uvicorn.run(
        "backend.agents.retail_agent.server:retail_app",
        host="0.0.0.0",
        port=8002,
        reload=True,
        log_level="info",
    )

if __name__ == "__main__":
    main()
