# =================================================================
# AZURE OPENAI CONFIGURATION HELPER
# =================================================================

import json
import os
from pathlib import Path
from typing import Dict
import sys
from langchain_openai import AzureChatOpenAI
from dotenv import load_dotenv

# Custom Imports
# ========================================================
curr_path = Path(__file__).absolute()
parent_path = curr_path.parent.parent.absolute()
sys.path.append(str(parent_path))

env_file = os.path.join(str(parent_path), ".env")
if os.path.exists(env_file):
    try:
        load_dotenv(env_file)
    except Exception as e:
        raise e
    else:
        print("Loaded Environment Variables.")
        output_loc = str(parent_path)
# ========================================================

class AzureOpenAIHelper:
    """Helper class for Azure OpenAI configuration"""

    @staticmethod
    def setup_from_config_file(config_path: str = f"{output_loc}/azure_config.json") -> Dict[str, str]:
        """Load Azure OpenAI config from JSON file"""
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)

            required_keys = [
                "azure_openai_api_key",
                "azure_openai_endpoint",
                "azure_deployment_name"
            ]

            for key in required_keys:
                if key not in config:
                    raise ValueError(f"Missing required config: {key}")
                os.environ[key.upper()] = config[key]

            # Optional configs
            if "azure_openai_api_version" in config:
                os.environ["AZURE_OPENAI_VERSION"] = config["azure_openai_api_version"]

            if "serper_api_key" in config:
                os.environ["SERPER_API_KEY"] = config["serper_api_key"]

            print("✅ Azure OpenAI configuration loaded from file")
            return config

        except FileNotFoundError:
            print(f"❌ Config file {config_path} not found")
            print("📝 Create azure_config.json with your Azure OpenAI settings")
            return {}

    @staticmethod
    def create_sample_config():
        """Create a sample configuration file"""
        sample_config = {
            "azure_openai_api_key": "your-azure-openai-api-key",
            "azure_openai_endpoint": "https://your-resource-name.openai.azure.com/",
            "azure_openai_api_version": "2023-09-01-preview",
            "azure_deployment_name": "gpt-4",
            "serper_api_key": "your-serper-api-key"
        }

        with open(f"{output_loc}//azure_config_sample.json", 'w') as f:
            json.dump(sample_config, f, indent=2)

        print("📝 Sample config created: azure_config_sample.json")
        print("   Copy to azure_config.json and update with your values")

    @staticmethod
    def test_azure_connection(config) -> bool:
        """Test Azure OpenAI connection"""
        try:
            test_llm = AzureChatOpenAI(
                azure_endpoint=config.azure_openai_endpoint,
                azure_deployment=config.azure_deployment_name,
                api_version=config.azure_openai_api_version,
                api_key=config.azure_openai_api_key,
                temperature=0
            )

            response = test_llm.invoke("Hello, this is a test message.")
            print("✅ Azure OpenAI connection successful")
            print(f"📝 Test response: {response.content[:100]}...")
            return True

        except Exception as e:
            print(f"❌ Azure OpenAI connection failed: {e}")
            return False


# =================================================================
# CONFIGURATION
# =================================================================

class EnhancedBusinessIntelligenceConfig :
    """Configuration class for Business Intelligence Agent"""

    def __init__(self):
        # Azure OpenAI Configuration
        self.azure_openai_api_key = os.getenv("AZURE_OPENAI_KEY")
        self.azure_openai_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
        self.azure_openai_api_version = os.getenv("AZURE_OPENAI_VERSION")
        self.azure_deployment_name = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")

        # Other API keys
        self.serper_api_key = os.getenv("SERPER_API_KEY")

        # Configuration
        self.output_dir = os.getenv("OUTPUT_DIR")
        self.cache_expiry_hours = 24
        self.max_search_results = 10
        self.max_content_length = 8000

        # --- NEW ---
        self.news_api_keys = {
            "newsapi":   os.getenv("NEWSAPI_KEY"),
            "bing_news": os.getenv("BING_NEWS_KEY"),
            "serper":    os.getenv("SERPER_API_KEY")
        }

        self.adverse_media_config = {
            "search_timeframe_days": int(os.getenv("ADVERSE_TIMEFRAME_DAYS", 365))
        }

        # Create output directory
        Path(self.output_dir).mkdir(exist_ok=True)

        # Validate required Azure OpenAI configuration
        if not self.azure_openai_api_key:
            raise ValueError("AZURE_OPENAI_API_KEY environment variable is required")
        if not self.azure_openai_endpoint:
            raise ValueError("AZURE_OPENAI_ENDPOINT environment variable is required")
        if not self.azure_deployment_name:
            raise ValueError("AZURE_DEPLOYMENT_NAME environment variable is required")
        if not self.serper_api_key:
            raise ValueError("SERPER_API_KEY environment variable is required")

        print(f"✅ Azure OpenAI configured: {self.azure_openai_endpoint}")
        print(f"✅ Deployment: {self.azure_deployment_name}")
        print(f"✅ API Version: {self.azure_openai_api_version}")
