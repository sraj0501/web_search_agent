# WARP.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

## Project Overview

This is a **Generic Search Agent System** that provides a unified interface for searching across multiple search engines and resources. The system supports extensible agent architecture where new search agents can be dynamically added, and users can choose from available agents when initiating searches for people, entities, businesses, or any other search targets.

## Architecture

The system follows a plugin-based architecture for maximum extensibility:

- **Core Agent Framework**: `ai/bi_agent/BIAgent.py` - Base agent implementation using LangChain
- **Search Agent Registry**: Dynamic registration system for search agents
- **Search Tools**: `data_scraper/search_tools.py` - Individual search engine integrations
- **Agent Selection Interface**: User can choose from available search agents
- **Unified Search Interface**: Common API for all search types (person/entity/business)
- **Multi-Interface Support**: CLI, Web UI, and API endpoints

## Development Commands

### Environment Setup
```bash
# Create environment file from template
cp .env_template .env

# Install dependencies using uv (recommended)
uv sync

# Alternative: Install with pip
pip install -e .
```

### Configuration Setup
```bash
# Create search agent configuration
python -c "from utils.common_config import AzureOpenAIHelper; AzureOpenAIHelper.create_sample_config()"
# Edit azure_config.json with your API keys and endpoints
```

### Running the Search Agent System

#### CLI Search Interface (Primary)
```bash
# Interactive mode - displays available agents
python ai/search_agent/kyc_agent_main.py

# List all available search agents
python ai/search_agent/kyc_agent_main.py --list-agents

# Search using specific agent
python ai/search_agent/kyc_agent_main.py --agent wikipedia --search "Elon Musk" --type person

# Search business entity with multiple agents
python ai/search_agent/kyc_agent_main.py --agent companies_house,web --search "Apple Inc" --type business

# Batch search from file
python ai/search_agent/kyc_agent_main.py --batch searches.txt --agents all
```

#### Streamlit Web Interface
```bash
# Launch interactive web interface
streamlit run app/agentic_app.py
# Features: Agent selection dropdown, search type selection, real-time results
```

#### FastAPI Server
```bash
# Start API server
uvicorn main:app --reload

# API endpoints:
# GET /agents - List available search agents
# POST /search - Perform search with selected agents
# GET /search/{search_id} - Get search results
```

### Adding New Search Agents

#### Create a New Search Agent
```bash
# Template for new search agent
python -c "
from data_scraper.search_tools import BaseSearchAgent
class LinkedInSearchAgent(BaseSearchAgent):
    agent_name = 'linkedin'
    description = 'Search LinkedIn profiles and company pages'
    supported_types = ['person', 'business']
    
    def search(self, query, search_type, **kwargs):
        # Implementation here
        pass
"
```

#### Register New Agent
```python
# In data_scraper/search_tools.py
SEARCH_AGENTS_REGISTRY = {
    'companies_house': CompanySearchTool,
    'wikipedia': WikipediaResearchTool, 
    'web': WebResearchTool,
    'linkedin': LinkedInSearchAgent,  # New agent
    'twitter': TwitterSearchAgent,    # New agent
    'github': GitHubSearchAgent,      # New agent
}
```

### Development and Testing

#### Code Quality
```bash
# Format code
black .
isort .

# Run type checking
mypy ai/ data_scraper/ utils/
```

#### Testing Search Agents
```bash
# Test individual search agent
python -c "
from data_scraper.search_tools import WikipediaResearchTool
from utils.common_config import EnhancedBusinessIntelligenceConfig
agent = WikipediaResearchTool(EnhancedBusinessIntelligenceConfig())
result = agent.search('Tesla Inc', 'business')
print(result)
"

# Test agent registration
python -c "
from data_scraper.search_tools import list_available_agents
print(list_available_agents())
"
```

## Core Components

### Base Search Agent Architecture
All search agents inherit from `BaseSearchAgent` and implement:
- **agent_name**: Unique identifier for the agent
- **description**: Human-readable description
- **supported_types**: List of supported search types (person, business, entity, etc.)
- **search()**: Main search method with unified interface
- **validate()**: Input validation logic

### Search Agent Registry (`data_scraper/search_tools.py`)
Dynamic registry system that:
- Auto-discovers available search agents
- Provides agent metadata (name, description, capabilities)
- Handles agent initialization and configuration
- Supports runtime agent registration

### Multi-Type Search Support
The system supports searching for:
- **Person**: Individual people (executives, public figures)
- **Business**: Companies and organizations  
- **Entity**: General entities (products, concepts, places)
- **Custom Types**: Extensible type system for specialized searches

### Agent Selection Interface
Users can choose search agents through:
- **Interactive CLI**: Menu-driven agent selection
- **Web Interface**: Dropdown with agent descriptions
- **API**: Programmatic agent specification
- **Batch Mode**: Agent combinations for comprehensive searches

## Configuration

### Required Environment Variables
```
# Core LLM Configuration
AZURE_OPENAI_KEY="your-azure-openai-api-key"
AZURE_OPENAI_ENDPOINT="https://your-resource.openai.azure.com/"
AZURE_OPENAI_DEPLOYMENT_NAME="gpt-4"

# Search Engine APIs
SERPER_API_KEY="your-serper-api-key"
COMPANIES_HOUSE_API_KEY="your-companies-house-key"

# Optional Agent-Specific Keys
LINKEDIN_API_KEY="your-linkedin-key"
TWITTER_API_KEY="your-twitter-key" 
GITHUB_API_KEY="your-github-key"

# System Configuration
OUTPUT_DIR="./search_results"
CACHE_EXPIRY_HOURS="24"
```

### Agent Configuration
Each agent can have specific configuration in `azure_config.json`:
```json
{
  "agents": {
    "wikipedia": {
      "enabled": true,
      "rate_limit": 10,
      "timeout": 15
    },
    "companies_house": {
      "enabled": true,
      "api_key": "your-key",
      "base_url": "https://api.companieshouse.gov.uk"
    },
    "linkedin": {
      "enabled": false,
      "reason": "API key not configured"
    }
  }
}
```

## Search Flow

1. **Agent Discovery**: System lists available and configured agents
2. **Agent Selection**: User chooses one or more agents for search
3. **Search Type Selection**: Specify search type (person/business/entity)
4. **Query Processing**: Input validation and preprocessing
5. **Multi-Agent Search**: Parallel or sequential agent execution
6. **Result Aggregation**: Combine results from multiple agents
7. **AI Analysis**: LLM synthesizes and structures findings
8. **Output Generation**: Unified format across all search types

## File Organization

- `ai/`: Core agent framework and implementations
  - `bi_agent/`: Base agent classes and LangChain integration
  - `search_agent/`: CLI interface and orchestration
- `data_scraper/`: Search agent implementations
  - `search_tools.py`: Agent registry and base classes
  - `get_data_ch.py`: Companies House specific implementation
- `app/`: Web interface for agent selection and search
- `utils/`: Configuration management and logging
- `data/`: Caching and result storage

## Adding New Search Agents

### Step 1: Implement Agent Class
```python
class NewSearchAgent(BaseSearchAgent):
    agent_name = 'new_agent'
    description = 'Search description'
    supported_types = ['person', 'business']
    
    def __init__(self, config):
        super().__init__(config)
        self.api_key = config.get('new_agent_api_key')
    
    def search(self, query: str, search_type: str, **kwargs):
        # Implement search logic
        return {
            'agent': self.agent_name,
            'query': query,
            'type': search_type,
            'results': [...],
            'metadata': {...}
        }
    
    def validate_query(self, query: str, search_type: str) -> bool:
        # Validation logic
        return True
```

### Step 2: Register Agent
Add to `SEARCH_AGENTS_REGISTRY` in `data_scraper/search_tools.py`

### Step 3: Add Configuration
Update environment variables and config files

### Step 4: Test Integration
```bash
python ai/search_agent/kyc_agent_main.py --list-agents
python ai/search_agent/kyc_agent_main.py --agent new_agent --search "test query" --type person
```

## Usage Examples

### CLI Examples
```bash
# Interactive mode with agent selection
python ai/search_agent/kyc_agent_main.py

# Search person across all agents
python ai/search_agent/kyc_agent_main.py --search "Tim Cook" --type person --agents all

# Business search with specific agents
python ai/search_agent/kyc_agent_main.py --search "Microsoft" --type business --agents companies_house,wikipedia,web

# Entity search with custom parameters
python ai/search_agent/kyc_agent_main.py --search "ChatGPT" --type entity --agents web --location global
```

### API Examples
```bash
# List available agents
curl http://localhost:8000/agents

# Submit search request
curl -X POST http://localhost:8000/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Satya Nadella", 
    "type": "person",
    "agents": ["wikipedia", "web"],
    "options": {"location": "USA"}
  }'
```

## Extension Points

1. **New Search Engines**: Add agents for LinkedIn, Twitter, GitHub, etc.
2. **Custom Search Types**: Define new search categories beyond person/business/entity
3. **Result Processors**: Add specialized processing for different data types
4. **Output Formats**: Extend output formats (JSON, XML, CSV, etc.)
5. **Authentication**: Implement OAuth and other auth methods for APIs
6. **Caching Strategies**: Agent-specific caching policies
7. **Rate Limiting**: Per-agent rate limiting and quota management

## Performance Considerations

- **Parallel Agent Execution**: Multiple agents can run concurrently
- **Intelligent Caching**: Per-agent and cross-agent result caching
- **Rate Limiting**: Configurable limits per search engine
- **Timeout Management**: Per-agent timeout configuration
- **Resource Pooling**: Connection pooling for HTTP requests
