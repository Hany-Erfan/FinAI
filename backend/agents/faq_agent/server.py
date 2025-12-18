"""
FAQ A2A Agent Server
Uses the FAQExecutor and FAQ Agent components
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
from backend.agents.faq_agent.faq_executor import FAQExecutor
from backend.agents.faq_agent.routes.faq_health import get_faq_health

# Set Google API key explicitly
os.environ["GOOGLE_API_KEY"] = os.getenv('GOOGLE_API_KEY', "***REMOVED***")


def build_faq_app():
    """Build and return the FAQ A2A Starlette application"""
    print("[START] Building FAQ A2A Agent App...")
    # Check for required environment variables
    if not os.getenv('GOOGLE_API_KEY'):
        print("[ERROR] GOOGLE_API_KEY environment variable not set")
        # Still build; env can be injected at run
    
    # Load skills from MCP instance
    skill = AgentSkill(
                id="bilingual_product_information_retreival",
                name="Bilingual Product Information Retreival",
                description="Retrieves product related information based on user query.",
                examples=[
                    "What is the interest rate on the loan?",
                    "What is the minimum credit score required for the loan?",
                ],
                tags=["product_information", "retreival", "FAQ"],
            )
        
    # Create agent card
    agent_card = AgentCard(
        name='FAQ Agent',
        description='A dedicated FAQ assistant that provides detailed information about banking products and answers frequently asked questions. It utilizes real-time retrieval to provide accurate product details and does not require any personal user information to assist.',
        url=os.environ.get('FAQ_AGENT_URL', 'http://localhost:8001'),
        version='1.0.0',
        default_input_modes=['text'],
        default_output_modes=['text'],
        capabilities=AgentCapabilities(streaming=True),
        skills=[skill],
    )

    # Create executor
    agent_executor = FAQExecutor(agent_card)
    
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
    app.routes.append(Route("/health", get_faq_health, methods=["GET"]))
    return app


# Module-level app for uvicorn path syntax
faq_app = build_faq_app()


def main():
    """Main function to start the FAQ agent server"""
    print("[SERVER] Starting server...")
    uvicorn.run(
        "backend.agents.faq_agent.server:faq_app",
        host="0.0.0.0",
        port=8001,
        reload=True,
        log_level="info",
    )

if __name__ == "__main__":
    main()
