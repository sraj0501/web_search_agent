import sys
import traceback
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

import streamlit as st

# Page config - must be first Streamlit command
st.set_page_config(
	page_title="Agentic KYC Application",
	page_icon="🤖",
	layout="wide",
	initial_sidebar_state="expanded"
)

# Initialize session state early
if 'agent' not in st.session_state:
	st.session_state.agent = None
if 'agent_initialized' not in st.session_state:
	st.session_state.agent_initialized = False
if 'research_results' not in st.session_state:
	st.session_state.research_results = []
if 'import_error' not in st.session_state:
	st.session_state.import_error = None


# Try to import the required modules
@st.cache_resource
def import_modules():
	"""Import modules with error handling"""
	try:
		# Path setup - adjust based on your project structure
		curr_path = Path(__file__).absolute()
		parent_path = curr_path.parent.parent.absolute()

		# Add to path if not already there
		if str(parent_path) not in sys.path:
			sys.path.append(str(parent_path))

		# Try importing - adjust import paths as needed for your project
		from utils.common_config import AzureOpenAIHelper, EnhancedBusinessIntelligenceConfig
		from ai.bi_agent.BIAgent import BusinessIntelligenceAgent

		return {
			'AzureOpenAIHelper': AzureOpenAIHelper,
			'EnhancedBusinessIntelligenceConfig': EnhancedBusinessIntelligenceConfig,
			'BusinessIntelligenceAgent': BusinessIntelligenceAgent,
			'success': True,
			'error': None
		}

	except ImportError as e:
		return {
			'success': False,
			'error': f"Import Error: {str(e)}",
			'traceback': traceback.format_exc()
		}
	except Exception as e:
		return {
			'success': False,
			'error': f"Unexpected Error: {str(e)}",
			'traceback': traceback.format_exc()
		}


# Custom CSS
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(90deg, #1f4e79, #2980b9);
        padding: 1rem;
        border-radius: 10px;
        color: white;
        text-align: center;
        margin-bottom: 2rem;
    }
    .success-box {
        background-color: #d4edda;
        border: 1px solid #c3e6cb;
        color: #155724;
        padding: 1rem;
        border-radius: 5px;
        margin: 1rem 0;
    }
    .error-box {
        background-color: #f8d7da;
        border: 1px solid #f5c6cb;
        color: #721c24;
        padding: 1rem;
        border-radius: 5px;
        margin: 1rem 0;
    }
    .info-box {
        background-color: #d1ecf1;
        border: 1px solid #bee5eb;
        color: #0c5460;
        padding: 1rem;
        border-radius: 5px;
        margin: 1rem 0;
    }
</style>
""", unsafe_allow_html=True)


def show_import_error_page(import_result):
	"""Show import error details"""
	st.error("❌ **Failed to import required modules**")

	st.markdown("### 🔍 Error Details:")
	st.code(import_result['error'])

	st.markdown("### 📋 Full Traceback:")
	st.code(import_result['traceback'])

	st.markdown("### 🛠️ Troubleshooting Steps:")
	st.markdown("""
    1. **Check File Structure**: Ensure your Streamlit app is in the correct directory relative to your imports
    2. **Verify Import Paths**: The app expects this structure:
       ```
       project_root/
       ├── utils/
       │   └── common_config.py
       ├── ai/
       │   └── bi_agent/
       │       └── BIAgent.py
       └── your_streamlit_app.py
       ```
    3. **Install Dependencies**: Make sure all required packages are installed
    4. **Python Path**: Verify the path adjustments in the code match your project structure
    """)

	st.markdown("### 🔧 Quick Fixes:")

	# Path debugging
	st.markdown("#### Current Python Path:")
	for i, path in enumerate(sys.path):
		st.text(f"{i}: {path}")

	# File structure check
	st.markdown("#### Current Directory Structure:")
	try:
		current_dir = Path.cwd()
		st.text(f"Current working directory: {current_dir}")

		# Show nearby files
		files = list(current_dir.rglob("*.py"))[:20]  # Limit to 20 files
		for file in files:
			st.text(f"Found: {file.relative_to(current_dir)}")

	except Exception as e:
		st.text(f"Could not analyze directory structure: {e}")


def setup_agent(modules):
	"""Setup and initialize the agent"""
	try:
		AzureOpenAIHelper = modules['AzureOpenAIHelper']
		EnhancedBusinessIntelligenceConfig = modules['EnhancedBusinessIntelligenceConfig']
		BusinessIntelligenceAgent = modules['BusinessIntelligenceAgent']

		with st.spinner("🔧 Loading Azure OpenAI configuration..."):
			config_data = AzureOpenAIHelper.setup_from_config_file()

		if not config_data:
			st.error("❌ Configuration not found. Please create azure_config.json with your credentials.")
			st.info(
				"📋 Setup Instructions:\n1. Create azure_config.json with your credentials\n2. Ensure you have the required API keys")
			return None

		with st.spinner("🔧 Initializing configuration..."):
			config = EnhancedBusinessIntelligenceConfig()

		with st.spinner("🧪 Testing Azure OpenAI connection..."):
			if not AzureOpenAIHelper.test_azure_connection(config):
				st.error("❌ Azure OpenAI connection failed. Please check your configuration.")
				return None

		with st.spinner("🤖 Initializing Business Intelligence Agent..."):
			agent = BusinessIntelligenceAgent(config)

		st.success("✅ Agent initialized successfully!")
		return agent

	except Exception as e:
		st.error(f"❌ Setup failed: {e}")
		st.info(
			"📋 Setup Instructions:\n1. Create azure_config.json with your credentials\n2. Ensure you have the required API keys\n3. Check your Azure OpenAI deployment name and endpoint")
		st.markdown("### 🔧 Show full error:")
		st.code(traceback.format_exc())
		return None


def display_research_results(result: Dict[str, Any]):
	"""Display research results"""
	if result["success"]:
		st.markdown('<div class="success-box">', unsafe_allow_html=True)
		st.markdown("✅ **RESEARCH COMPLETED SUCCESSFULLY**")
		st.markdown('</div>', unsafe_allow_html=True)

		st.markdown("### 📄 Research Report")
		st.markdown(result["response"])

		# Show metadata
		col1, col2, col3 = st.columns(3)
		with col1:
			st.metric("📊 Research Steps", len(result['research_steps']))
		with col2:
			st.metric("🕒 Completed", result['timestamp'][:19])
		with col3:
			st.metric("📝 Session ID", result['session_id'][:8] + "...")

		# Show research steps in expander
		if result['research_steps']:
			with st.expander("📋 Research Steps Taken"):
				for i, step in enumerate(result['research_steps'], 1):
					st.write(f"{i}. **{step['tool']}** - {step['timestamp'][:19]}")

		# Download button for report
		report_content = f"""BUSINESS INTELLIGENCE REPORT
{'=' * 50}
Company: {result['company_name']}
Location: {result['location'] or 'Not specified'}
Generated: {result['timestamp']}
Session ID: {result['session_id']}
Research Steps: {len(result['research_steps'])}
{'=' * 50}

{result["response"]}

{'=' * 50}
Report generated by Business Intelligence AI Agent
"""

		st.download_button(
			label="💾 Download Report",
			data=report_content,
			file_name=f"business_report_{result['company_name'].replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
			mime="text/plain"
		)

	else:
		st.markdown('<div class="error-box">', unsafe_allow_html=True)
		st.markdown("❌ **RESEARCH FAILED**")
		st.markdown(f"**Error:** {result['error']}")
		st.markdown(f"**Session ID:** {result['session_id']}")
		if result['research_steps']:
			st.markdown(f"**Research steps attempted:** {len(result['research_steps'])}")
		st.markdown('</div>', unsafe_allow_html=True)


def show_cached_companies(agent):
	"""Display cached companies"""
	try:
		cached_companies = agent.cache_manager.list_cached_companies()

		if not cached_companies:
			st.info("📭 No cached companies found.")
			return

		st.subheader(f"📋 Cached Companies ({len(cached_companies)} total)")

		# Create simple table format
		for company in cached_companies:
			status = '✅ VALID' if not company['expired'] else '❌ EXPIRED'
			location_text = f" ({company['location']})" if company['location'] else ""

			col1, col2, col3 = st.columns([3, 2, 2])
			with col1:
				st.write(f"{status} **{company['company_name']}**{location_text}")
			with col2:
				st.write(f"Updated: {company['updated_at'][:19]}")
			with col3:
				st.write(f"Age: {company['age_hours']}h")
	except Exception as e:
		st.error(f"❌ Error displaying cached companies: {e}")


def show_agent_logs(agent):
	"""Display agent execution logs"""
	try:
		log_files = agent.get_log_files()

		if not log_files:
			st.info("📭 No agent logs found.")
			return

		st.subheader(f"📋 Agent Execution Logs ({len(log_files)} total)")

		# Show logs in a simple format
		for i, log_file in enumerate(log_files[:20], 1):  # Show latest 20
			session_id = log_file['filename'].replace('agent_log_', '').replace('.json', '')
			size_str = f"{log_file['size_bytes']:,}B"

			col1, col2, col3, col4 = st.columns([1, 3, 2, 2])
			with col1:
				st.write(f"**{i}**")
			with col2:
				st.write(f"**{log_file['company'][:30]}**")
			with col3:
				st.write(f"{log_file['date']} {log_file['time']}")
			with col4:
				st.write(f"{size_str}")

			if st.button(f"View Log", key=f"view_{session_id}"):
				st.session_state[f"view_log_{session_id}"] = True

		if len(log_files) > 20:
			st.info(f"Showing latest 20 of {len(log_files)} total logs.")

	except Exception as e:
		st.error(f"❌ Error displaying logs: {e}")


def main():
	"""Main application"""
	# Header
	st.markdown("""
    <div class="main-header">
        <h1>🏢 Agentic KYC Application</h1>
        <p>Advanced Business Research & Analysis Platform</p>
    </div>
    """, unsafe_allow_html=True)

	# Try to import modules
	import_result = import_modules()

	if not import_result['success']:
		show_import_error_page(import_result)
		return

	# Get the imported modules
	modules = import_result

	# Sidebar
	with st.sidebar:
		st.header("🛠️ Agent Setup")

		if not st.session_state.agent_initialized:
			if st.button("🚀 Initialize Agent", type="primary"):
				agent = setup_agent(modules)
				if agent:
					st.session_state.agent = agent
					st.session_state.agent_initialized = True
					st.rerun()
		else:
			st.success("✅ Agent Ready")

			# Agent actions
			st.header("🔧 Agent Actions")

			if st.button("🧹 Clear Memory"):
				try:
					st.session_state.agent.clear_memory()
					st.success("🧹 Conversation memory cleared")
				except Exception as e:
					st.error(f"❌ Error clearing memory: {e}")

			if st.button("🔄 Reinitialize Agent"):
				st.session_state.agent = None
				st.session_state.agent_initialized = False
				st.rerun()

	# Main content
	if not st.session_state.agent_initialized:
		st.warning("⚠️ Please initialize the agent first using the sidebar.")

		st.markdown("""
        ### 📋 Setup Instructions:
        1. Create `azure_config.json` with your credentials
        2. Ensure you have the required API keys
        3. Check your Azure OpenAI deployment name and endpoint
        4. Click "Initialize Agent" in the sidebar
        """)
		return

	# Main tabs
	tab1, tab2, tab3 = st.tabs(["🔍 Research", "💾 Cache", "📋 Logs"])

	with tab1:
		st.header("Company Research")

		col1, col2 = st.columns([2, 1])

		with col1:
			company_name = st.text_input("📝 Company Name", placeholder="Enter company name...")

		with col2:
			location = st.text_input("📍 Location (Optional)", placeholder="Enter location...")

		if st.button("🔍 Start Research", type="primary", disabled=not company_name.strip()):
			if company_name.strip():
				try:
					with st.spinner(f"🔍 Researching {company_name}..."):
						result = st.session_state.agent.research_business(company_name.strip(), location.strip())
						st.session_state.research_results.append(result)
						display_research_results(result)
				except Exception as e:
					st.error(f"❌ Research failed: {e}")
					st.markdown("### 🔧 Error details:")
					st.code(traceback.format_exc())

		# Show recent results
		if st.session_state.research_results:
			st.subheader("📚 Recent Research Results")
			for i, result in enumerate(reversed(st.session_state.research_results[-3:]), 1):
				st.markdown(
					f"**{result['company_name']}** - {result['timestamp'][:19]} {'✅' if result['success'] else '❌'}")
				if result["success"]:
					st.success("✅ Research completed successfully")
					st.text(f"Research Steps: {len(result['research_steps'])}")
					st.text(f"Session ID: {result['session_id'][:8]}...")
				else:
					st.error(f"❌ Research failed: {result['error']}")
					st.text(f"Session ID: {result['session_id'][:8]}...")
				st.divider()

	with tab2:
		st.header("💾 Cached Companies")

		if st.button("🔄 Refresh Cache"):
			st.rerun()

		show_cached_companies(st.session_state.agent)

	with tab3:
		st.header("📋 Agent Execution Logs")

		if st.button("🔄 Refresh Logs"):
			st.rerun()

		show_agent_logs(st.session_state.agent)


if __name__ == "__main__":
	try:
		main()
	except Exception as e:
		st.error(f"❌ Application Error: {e}")
		st.markdown("### 🔧 Full error details:")
		st.code(traceback.format_exc())

		st.markdown("### 🛠️ Troubleshooting:")
		st.markdown("1. Check that all required files are in the correct locations")
		st.markdown("2. Verify that all dependencies are installed")
		st.markdown("3. Make sure you're running from the correct directory")