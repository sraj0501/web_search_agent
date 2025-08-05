# =================================================================
# COMPREHENSIVE LOGGING SYSTEM
# =================================================================
import json
import re
from typing import Dict, List, Any

from langchain.schema import AgentAction, AgentFinish
from datetime import datetime
from pathlib import Path

class AgentExecutorLogger:
	"""Comprehensive logger for Agent Executor Chain and AI outputs"""

	def __init__(self, config):
		self.config = config
		self.logs_dir = Path(config.output_dir) / "agent_logs"
		self.logs_dir.mkdir(exist_ok=True)

		# Current session data
		self.current_session = {
			"search_term": "",
			"location": "",
			"start_time": None,
			"end_time": None,
			"agent_chain_log": [],
			"console_output": "",
			"tool_calls": [],
			"ai_reasoning": [],
			"final_output": "",
			"error_log": "",
			"session_id": ""
		}

	def start_session(self, company_name: str, location: str = ""):
		"""Start a new logging session"""
		timestamp = datetime.now()
		session_id = f"{timestamp.strftime('%Y%m%d_%H%M%S')}_{self._sanitize_filename(company_name)}"

		self.current_session = {
			"search_term": company_name,
			"location": location,
			"start_time": timestamp.isoformat(),
			"end_time": None,
			"agent_chain_log": [],
			"console_output": "",
			"tool_calls": [],
			"ai_reasoning": [],
			"final_output": "",
			"error_log": "",
			"session_id": session_id
		}

		print(f"📝 Started logging session: {session_id}")

	def log_agent_action(self, action: AgentAction, observation: str = ""):
		"""Log agent actions and observations"""
		log_entry = {
			"timestamp": datetime.now().isoformat(),
			"type": "action",
			"tool": action.tool,
			"tool_input": action.tool_input,
			"log": action.log,
			"observation": observation
		}
		self.current_session["agent_chain_log"].append(log_entry)
		self.current_session["tool_calls"].append({
			"tool": action.tool,
			"input": action.tool_input,
			"timestamp": log_entry["timestamp"]
		})

	def log_agent_finish(self, finish: AgentFinish):
		"""Log agent completion"""
		log_entry = {
			"timestamp": datetime.now().isoformat(),
			"type": "finish",
			"return_values": finish.return_values,
			"log": finish.log
		}
		self.current_session["agent_chain_log"].append(log_entry)
		self.current_session["final_output"] = finish.return_values.get("output", "")

	def log_ai_reasoning(self, reasoning: str):
		"""Log AI reasoning steps"""
		self.current_session["ai_reasoning"].append({
			"timestamp": datetime.now().isoformat(),
			"reasoning": reasoning
		})

	def log_console_output(self, output: str):
		"""Log console output"""
		self.current_session["console_output"] += f"[{datetime.now().isoformat()}] {output}\n"

	def log_error(self, error: str):
		"""Log errors"""
		error_entry = f"[{datetime.now().isoformat()}] ERROR: {error}\n"
		self.current_session["error_log"] += error_entry
		self.current_session["console_output"] += error_entry

	def end_session(self, success: bool = True):
		"""End the current session and save logs"""
		self.current_session["end_time"] = datetime.now().isoformat()
		self.current_session["success"] = success

		# Calculate duration
		start_time = datetime.fromisoformat(self.current_session["start_time"])
		end_time = datetime.fromisoformat(self.current_session["end_time"])
		duration = (end_time - start_time).total_seconds()
		self.current_session["duration_seconds"] = duration

		# Save to file
		self._save_session_log()

		print(f"📝 Ended logging session: {self.current_session['session_id']} (Duration: {duration:.2f}s)")

	def _save_session_log(self):
		"""Save the current session log to file"""
		try:
			# Create detailed log filename
			session_id = self.current_session["session_id"]
			log_filename = f"agent_log_{session_id}.json"
			log_filepath = self.logs_dir / log_filename

			# Add metadata
			self.current_session["metadata"] = {
				"agent_version": "Business Intelligence AI Agent v1.0",
				"log_format_version": "1.0",
				"total_tool_calls": len(self.current_session["tool_calls"]),
				"total_reasoning_steps": len(self.current_session["ai_reasoning"]),
				"has_errors": bool(self.current_session["error_log"])
			}

			# Save JSON log
			with open(log_filepath, 'w', encoding='utf-8') as f:
				json.dump(self.current_session, f, indent=2, ensure_ascii=False)

			# Also save a human-readable version
			readable_filepath = self.logs_dir / f"agent_log_{session_id}.txt"
			self._save_readable_log(readable_filepath)

			print(f"💾 Agent logs saved:")
			print(f"   📄 JSON: {log_filepath}")
			print(f"   📄 Readable: {readable_filepath}")

		except Exception as e:
			print(f"❌ Failed to save agent logs: {e}")

	def _save_readable_log(self, filepath: Path):
		"""Save a human-readable version of the log"""
		try:
			with open(filepath, 'w', encoding='utf-8') as f:
				session = self.current_session

				f.write("BUSINESS INTELLIGENCE AI AGENT - EXECUTION LOG\n")
				f.write("=" * 80 + "\n\n")

				# Session Info
				f.write(f"Session ID: {session['session_id']}\n")
				f.write(f"Search Term: {session['search_term']}\n")
				f.write(f"Location: {session['location'] or 'Not specified'}\n")
				f.write(f"Start Time: {session['start_time']}\n")
				f.write(f"End Time: {session['end_time']}\n")
				f.write(f"Duration: {session.get('duration_seconds', 0):.2f} seconds\n")
				f.write(f"Success: {session.get('success', False)}\n")
				f.write(f"Total Tool Calls: {len(session['tool_calls'])}\n\n")

				# Agent Chain Log
				f.write("AGENT EXECUTOR CHAIN LOG\n")
				f.write("-" * 40 + "\n\n")

				for i, log_entry in enumerate(session['agent_chain_log'], 1):
					f.write(f"Step {i}: {log_entry['type'].upper()}\n")
					f.write(f"Time: {log_entry['timestamp']}\n")

					if log_entry['type'] == 'action':
						f.write(f"Tool: {log_entry['tool']}\n")
						f.write(f"Input: {log_entry['tool_input']}\n")
						if log_entry.get('log'):
							f.write(f"Agent Log: {log_entry['log']}\n")
						if log_entry.get('observation'):
							f.write(
								f"Observation: {log_entry['observation'][:500]}{'...' if len(log_entry['observation']) > 500 else ''}\n")
					elif log_entry['type'] == 'finish':
						f.write(f"Final Output: {log_entry['return_values']}\n")
						if log_entry.get('log'):
							f.write(f"Agent Log: {log_entry['log']}\n")

					f.write("\n" + "-" * 40 + "\n\n")

				# AI Reasoning
				if session['ai_reasoning']:
					f.write("AI REASONING STEPS\n")
					f.write("-" * 40 + "\n\n")
					for i, reasoning in enumerate(session['ai_reasoning'], 1):
						f.write(f"Reasoning {i} ({reasoning['timestamp']}):\n")
						f.write(f"{reasoning['reasoning']}\n\n")

				# Final AI Output
				f.write("FINAL AI OUTPUT\n")
				f.write("-" * 40 + "\n\n")
				f.write(session['final_output'])
				f.write("\n\n")

				# Console Output
				if session['console_output']:
					f.write("CONSOLE OUTPUT\n")
					f.write("-" * 40 + "\n\n")
					f.write(session['console_output'])
					f.write("\n\n")

				# Errors
				if session['error_log']:
					f.write("ERROR LOG\n")
					f.write("-" * 40 + "\n\n")
					f.write(session['error_log'])
					f.write("\n\n")

				# Tool Calls Summary
				f.write("TOOL CALLS SUMMARY\n")
				f.write("-" * 40 + "\n\n")
				for i, tool_call in enumerate(session['tool_calls'], 1):
					f.write(f"{i}. {tool_call['tool']} ({tool_call['timestamp']})\n")
					f.write(f"   Input: {tool_call['input']}\n\n")

		except Exception as e:
			print(f"❌ Failed to save readable log: {e}")

	def _sanitize_filename(self, filename: str) -> str:
		"""Sanitize filename for safe file system usage"""
		# Remove or replace invalid characters
		safe_name = re.sub(r'[^\w\s-]', '', filename).strip()
		safe_name = re.sub(r'[-\s]+', '_', safe_name).lower()
		return safe_name[:50]  # Limit length

	def list_log_files(self) -> List[Dict[str, Any]]:
		"""List all available log files"""
		log_files = []

		for log_file in self.logs_dir.glob("agent_log_*.json"):
			try:
				# Extract info from filename
				filename = log_file.stem
				parts = filename.replace("agent_log_", "").split("_", 3)

				if len(parts) >= 4:
					date_part = parts[0]
					time_part = parts[1]
					company_part = "_".join(parts[2:])

					# Get file stats
					stat = log_file.stat()

					log_files.append({
						"filename": log_file.name,
						"filepath": str(log_file),
						"company": company_part.replace("_", " ").title(),
						"date": f"{date_part[:4]}-{date_part[4:6]}-{date_part[6:8]}",
						"time": f"{time_part[:2]}:{time_part[2:4]}:{time_part[4:6]}",
						"size_bytes": stat.st_size,
						"modified": datetime.fromtimestamp(stat.st_mtime).isoformat()
					})
			except Exception:
				continue

		return sorted(log_files, key=lambda x: x["modified"], reverse=True)

	def log_adverse_media(self, adverse_result: Dict[str, Any]):
		self.current_session.setdefault("adverse_media", adverse_result)
		self.log_console_output(
			f"🚨 Adverse media: {len(adverse_result['adverse_findings'])} findings, "
			f"risk_score={adverse_result['risk_score']}"
		)