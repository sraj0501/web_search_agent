import asyncio
import json
from datetime import datetime
from typing import Dict, List, Any, Optional
import sys
import io

from langchain.agents import Tool, AgentExecutor, create_react_agent
from langchain.callbacks.base import BaseCallbackHandler
from langchain.prompts import PromptTemplate
from langchain.schema import AgentAction, AgentFinish
from langchain_core.messages import HumanMessage, AIMessage
from langchain_openai import AzureChatOpenAI

from data.cache_mgr import CacheManager
from data_scraper.search_tools import CompanySearchTool, WikipediaResearchTool, WebResearchTool
from utils.agent_logger import AgentExecutorLogger
from ai.adverse_media.AdverseMediaTool import AdverseMediaTool

# =================================================================
# AI AGENT IMPLEMENTATION
# =================================================================

class BusinessIntelligenceCallbacks(BaseCallbackHandler):
	"""Enhanced callbacks for Business Intelligence Agent with comprehensive logging"""

	def __init__(self, logger: AgentExecutorLogger):
		self.research_steps = []
		self.logger = logger

	def on_agent_action(self, action: AgentAction, **kwargs):
		"""Called when agent takes an action"""
		step = {
			"tool": action.tool,
			"input": action.tool_input,
			"timestamp": datetime.now().isoformat()
		}
		self.research_steps.append(step)

		# Log to our comprehensive logger
		self.logger.log_agent_action(action)
		self.logger.log_console_output(f"🔍 Using tool: {action.tool}")

		# Extract reasoning from agent log if available
		if hasattr(action, 'log') and action.log:
			self.logger.log_ai_reasoning(action.log)

		print(f"🔍 Using tool: {action.tool}")

	def on_agent_finish(self, finish: AgentFinish, **kwargs):
		"""Called when agent finishes"""
		self.logger.log_agent_finish(finish)
		self.logger.log_console_output("✅ Research completed")
		print("✅ Research completed")

	def on_tool_start(self, serialized: Dict[str, Any], input_str: str, **kwargs):
		"""Called when a tool starts"""
		tool_name = serialized.get('name', 'unknown_tool')
		self.logger.log_console_output(f"🔧 Starting tool: {tool_name} with input: {input_str[:100]}...")

	def on_tool_end(self, output: str, **kwargs):
		"""Called when a tool ends"""
		self.logger.log_console_output(f"✅ Tool completed with output length: {len(output)} characters")

	def on_tool_error(self, error: Exception, **kwargs):
		"""Called when a tool encounters an error"""
		error_msg = f"Tool error: {str(error)}"
		self.logger.log_error(error_msg)
		print(f"❌ {error_msg}")

	def on_llm_start(self, serialized: Dict[str, Any], prompts: List[str], **kwargs):
		"""Called when LLM starts"""
		self.logger.log_console_output("🤖 LLM processing started")

	def on_llm_end(self, response, **kwargs):
		"""Called when LLM ends"""
		if hasattr(response, 'generations') and response.generations:
			output = response.generations[0][0].text if response.generations[0] else ""
			self.logger.log_console_output(f"🤖 LLM completed. Output length: {len(output)} characters")

	def on_llm_error(self, error: Exception, **kwargs):
		"""Called when LLM encounters an error"""
		error_msg = f"LLM error: {str(error)}"
		self.logger.log_error(error_msg)
		print(f"❌ {error_msg}")

class BusinessIntelligenceAgent:
	"""Main Business Intelligence AI Agent"""

	def __init__(self, config):
		self.config = config

		# Adding the Adverse media search tool.
		self.adverse_media_tool = AdverseMediaTool(config)

		# Initialize logger
		self.logger = AgentExecutorLogger(config)

		# Initialize callbacks with logger
		self.callbacks = BusinessIntelligenceCallbacks(self.logger)

		# Initialize tools
		self.company_search = CompanySearchTool(config)
		self.wikipedia_research = WikipediaResearchTool(config)
		self.web_research = WebResearchTool(config)
		self.cache_manager = CacheManager(config)

		# Initialize LLM with Azure OpenAI
		self.llm = AzureChatOpenAI(
			azure_endpoint=config.azure_openai_endpoint,
			azure_deployment=config.azure_deployment_name,
			api_version=config.azure_openai_api_version,
			api_key=config.azure_openai_api_key,
			temperature=0.1,
			max_tokens=4000
		)

		# Initialize conversation history (replacing deprecated memory)
		self.conversation_history = []

		# Create agent
		self.agent_executor = self._create_agent()

	def _create_agent(self) -> AgentExecutor:
		"""Create the LangChain agent"""
		tools = self._create_tools()
		prompt = self._create_prompt()

		# Create partial prompt with tool names
		tool_names = [tool.name for tool in tools]
		partial_prompt = prompt.partial(tool_names=", ".join(tool_names))

		agent = create_react_agent(
			llm=self.llm,
			tools=tools,
			prompt=partial_prompt
		)

		return AgentExecutor(
			agent=agent,
			tools=tools,
			callbacks=[self.callbacks],
			verbose=True,
			max_iterations=8,
			early_stopping_method="generate",
			handle_parsing_errors=True
		)

	def _create_tools(self) -> List[Tool]:
		"""Create LangChain tools from our research tools"""
		return [
			Tool(
				name="check_cache",
				description="Check if we have cached research data for a company and location. Use this FIRST. Input: 'company_name|location'",
				func=self._check_cache_wrapper
			),
			Tool(
				name="company_house_search",
				description="Search UK Companies House for official company registration data. Input: 'company_name|location'",
				func=self._company_search_wrapper
			),
			Tool(
				name="wikipedia_research",
				description="Research a company on Wikipedia for background information. Input: 'company_name|location'",
				func=self._wikipedia_wrapper
			),
			Tool(
				name="web_intelligence_research",
				description="Perform comprehensive web research for business intelligence. Input: 'company_name|location'",
				func=self._web_research_wrapper
			),
			Tool(
				name="save_research",
				description="Save completed research to cache. Input: 'company_name|location|research_data_json'",
				func=self._save_research_wrapper
			),
			Tool(
				name="adverse_media_search",
				description="Check negative news / sanctions about a company. Input: 'company_name|location'",
				func=self._adverse_media_wrapper
			)
		]

	def _create_prompt(self) -> PromptTemplate:
		"""Create the agent prompt template"""
		return PromptTemplate.from_template("""
			You are a Business Intelligence AI agent specializing in company research. Your goal is to gather specific business information about companies.
	
			TOOLS AVAILABLE:
			{tools}
	
			TOOL NAMES: {tool_names}
	
			REQUIRED OUTPUT FORMAT:
			You must provide the following information in a structured format:
	
			1. **Products and Services**: List the main products/services the business provides
			2. **Customer Type**: Whether it sells to retail customers, other businesses (B2B/wholesale), or both
			3. **Geographic Scope**: Whether it sells only in the UK or internationally
			4. **Employee Count**: Estimated number of employees
			5. **Turnover Estimate**: Estimated annual revenue/turnover
			6. **Cash Estimate**: Estimated cash position/financial health
			7. **Data Sources & Reasoning**: Description of sources used and your analytical reasoning
	
			IMPORTANT: You must use the following format for your reasoning and actions:
	
			Question: the input question you must answer
			Thought: you should always think about what to do
			Action: the action to take, should be one of [{tool_names}]
			Action Input: the input to the action
			Observation: the result of the action
			... (this Thought/Action/Action Input/Observation can repeat N times)
			Thought: I now know the final answer
			Final Answer: the final answer to the original input question
	
			RESEARCH PROTOCOL:
			1. ALWAYS check cache first using check_cache tool
			2. If cached data exists and is recent, use it for analysis
			3. If no cached data, perform research using available tools
			4. Analyze all gathered data to extract the required business intelligence
			5. Provide structured output in the required format
	
			USER REQUEST: {input}
	
			PREVIOUS CONVERSATION:
			{chat_history}
	
			{agent_scratchpad}""")

	def _check_cache_wrapper(self, input_data: str) -> str:
		"""Wrapper for cache check"""
		try:
			parts = input_data.split("|")
			company_name = parts[0].strip()
			location = parts[1].strip() if len(parts) > 1 else ""

			result = self.cache_manager.check_cache(company_name, location)
			if result:
				return f"Cache found for {company_name}: {json.dumps(result, indent=2)}"
			else:
				return f"No cached data found for {company_name}"
		except Exception as e:
			return f"Cache check error: {str(e)}"

	def _company_search_wrapper(self, input_data: str) -> str:
		"""Wrapper for company search"""
		try:
			parts = input_data.split("|")
			company_name = parts[0].strip()
			location = parts[1].strip() if len(parts) > 1 else ""

			result = self.company_search.search_company_house(company_name, location)
			return json.dumps(result, indent=2)
		except Exception as e:
			return f"Company search error: {str(e)}"

	def _wikipedia_wrapper(self, input_data: str) -> str:
		"""Wrapper for Wikipedia research"""
		try:
			parts = input_data.split("|")
			company_name = parts[0].strip()
			location = parts[1].strip() if len(parts) > 1 else ""

			result = self.wikipedia_research.research_company(company_name, location)
			if 'content' in result and len(result['content']) > 2000:
				result['content'] = result['content'][:2000] + "... [truncated]"
			return json.dumps(result, indent=2)
		except Exception as e:
			return f"Wikipedia research error: {str(e)}"

	def _web_research_wrapper(self, input_data: str) -> str:
		"""Wrapper for web research"""
		try:
			parts = input_data.split("|")
			company_name = parts[0].strip()
			location = parts[1].strip() if len(parts) > 1 else ""

			result = self.web_research.research_business_intelligence(company_name, location)
			if 'scraped_content' in result:
				for url, content in result['scraped_content'].items():
					if len(content) > 1000:
						result['scraped_content'][url] = content[:1000] + "... [truncated]"
			return json.dumps(result, indent=2)
		except Exception as e:
			return f"Web research error: {str(e)}"

	def _save_research_wrapper(self, input_data: str) -> str:
		"""Wrapper for save research"""
		try:
			parts = input_data.split("|", 2)
			if len(parts) != 3:
				return "Error: Input should be 'company_name|location|research_data_json'"

			company_name, location, research_json = parts
			research_data = json.loads(research_json)

			success = self.cache_manager.save_to_cache(company_name.strip(), location.strip(), research_data)
			return f"Research data {'saved' if success else 'failed to save'} to cache"

		except Exception as e:
			return f"Error saving research: {str(e)}"

	def _adverse_media_wrapper(self, input_data: str) -> str:  # NEW
		company, *rest = input_data.split("|")
		location = rest[0] if rest else ""
		# run synchronously inside agent via asyncio.run
		result = asyncio.run(self.adverse_media_tool.search(company.strip(), location.strip()))
		# shorten long lists for prompt
		if len(result["adverse_findings"]) > 15:
			result["adverse_findings"] = result["adverse_findings"][:15] + [{"note": "...truncated"}]
		return json.dumps(result, indent=2)

	def research_business(self, company_name: str, location: str = "", include_adverse_media: bool = False) -> Dict[str, Any]:
		"""Main method to research a business with comprehensive logging"""
		try:
			# Start logging session
			self.logger.start_session(company_name, location)

			# Reset callback tracking
			self.callbacks.research_steps = []

			# Construct input for the agent
			user_input = f"Research business intelligence for: {company_name}"
			if location:
				user_input += f" located in {location}"

			user_input += """
							Please provide:
							1. Products and services offered
							2. Customer type (retail, B2B, or both)
							3. Geographic scope (UK only or international)
							4. Employee count estimate
							5. Turnover/revenue estimate
							6. Cash position estimate
							7. Data sources and reasoning
							"""

			# Log the user input
			self.logger.log_console_output(f"User Input: {user_input}")

			# Prepare chat history for the prompt
			chat_history = self._format_chat_history()

			# Capture stdout/stderr during agent execution
			old_stdout = sys.stdout
			old_stderr = sys.stderr

			stdout_buffer = io.StringIO()
			stderr_buffer = io.StringIO()

			try:
				# Redirect output to capture agent logs
				sys.stdout = stdout_buffer
				sys.stderr = stderr_buffer

				# Run the agent
				result = self.agent_executor.invoke({
					"input": user_input,
					"chat_history": chat_history
				})

				if include_adverse_media:
					adverse_result = asyncio.run(
						self.adverse_media_tool.search(company_name, location)
					)
					self.logger.log_adverse_media(adverse_result)

			finally:
				# Restore stdout/stderr
				sys.stdout = old_stdout
				sys.stderr = old_stderr

				# Capture the output
				stdout_content = stdout_buffer.getvalue()
				stderr_content = stderr_buffer.getvalue()

				if stdout_content:
					self.logger.log_console_output(f"Agent Stdout:\n{stdout_content}")
				if stderr_content:
					self.logger.log_error(f"Agent Stderr:\n{stderr_content}")

			# Update conversation history
			self.conversation_history.append(HumanMessage(content=user_input))
			self.conversation_history.append(AIMessage(content=result["output"]))

			# Keep only last 6 messages (3 exchanges)
			if len(self.conversation_history) > 6:
				self.conversation_history = self.conversation_history[-6:]

			# End logging session successfully
			self.logger.end_session(success=True)

			return {
				"success": True,
				"company_name": company_name,
				"location": location,
				"response": result["output"],
				"adverse_media": adverse_result,
				"research_steps": self.callbacks.research_steps,
				"timestamp": datetime.now().isoformat(),
				"session_id": self.logger.current_session["session_id"]
			}

		except Exception as e:
			# Log the error and end session
			error_msg = str(e)
			self.logger.log_error(f"Research failed: {error_msg}")
			self.logger.end_session(success=False)

			return {
				"success": False,
				"company_name": company_name,
				"location": location,
				"error": error_msg,
				"research_steps": self.callbacks.research_steps,
				"timestamp": datetime.now().isoformat(),
				"session_id": self.logger.current_session["session_id"]
			}

	def get_log_files(self) -> List[Dict[str, Any]]:
		"""Get list of all agent log files"""
		return self.logger.list_log_files()

	def view_log_file(self, session_id: str) -> Optional[Dict[str, Any]]:
		"""View a specific log file by session ID"""
		log_file = self.logger.logs_dir / f"agent_log_{session_id}.json"

		if log_file.exists():
			try:
				with open(log_file, 'r', encoding='utf-8') as f:
					return json.load(f)
			except Exception as e:
				print(f"❌ Error reading log file: {e}")
				return None
		else:
			print(f"❌ Log file not found: {log_file}")
			return None

	def _format_chat_history(self) -> str:
		"""Format conversation history for the prompt"""
		if not self.conversation_history:
			return "No previous conversation."

		formatted = []
		for msg in self.conversation_history[-4:]:  # Last 2 exchanges
			if isinstance(msg, HumanMessage):
				formatted.append(f"Human: {msg.content}")
			elif isinstance(msg, AIMessage):
				formatted.append(f"Assistant: {msg.content[:200]}...")  # Truncate for brevity

		return "\n".join(formatted)

	def get_conversation_history(self) -> List[str]:
		"""Get conversation history"""
		return [f"{type(msg).__name__}: {msg.content}" for msg in self.conversation_history]

	def clear_memory(self):
		"""Clear conversation memory"""
		self.conversation_history = []