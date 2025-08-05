from utils.common_config import EnhancedBusinessIntelligenceConfig 
from typing import Dict, List, Any, Optional
import json
from datetime import timedelta, datetime
from pathlib import Path
import re


class CacheManager:
	"""Tool for managing research cache"""

	def __init__(self, config: EnhancedBusinessIntelligenceConfig ):
		self.config = config

	def check_cache(self, company_name: str, location: str = "") -> Optional[Dict[str, Any]]:
		"""Check if cached data exists and is valid"""
		cache_key = f"{company_name}_{location}".strip("_")
		cache_file = self._get_cache_path(cache_key)
		metadata_file = self._get_metadata_path(cache_key)

		if not metadata_file.exists():
			return None

		try:
			with open(metadata_file, 'r', encoding='utf-8') as f:
				metadata = json.load(f)

			cached_time = datetime.fromisoformat(metadata['updated_at'])
			expiry_time = cached_time + timedelta(hours=self.config.cache_expiry_hours)

			if datetime.now() < expiry_time:
				# Load cached data
				with open(cache_file, 'r', encoding='utf-8') as f:
					cached_data = json.load(f)

				return {
					"cached": True,
					"metadata": metadata,
					"cache_age_hours": int((datetime.now() - cached_time).total_seconds() / 3600),
					"data": cached_data
				}

		except (json.JSONDecodeError, KeyError, FileNotFoundError):
			pass

		return None

	def save_to_cache(self, company_name: str, location: str, research_data: Dict[str, Any]) -> bool:
		"""Save research data to cache"""
		try:
			cache_key = f"{company_name}_{location}".strip("_")
			cache_file = self._get_cache_path(cache_key)
			metadata_file = self._get_metadata_path(cache_key)

			# Save research data
			with open(cache_file, 'w', encoding='utf-8') as f:
				json.dump(research_data, f, indent=2, ensure_ascii=False)

			# Save metadata
			metadata = {
				"company_name": company_name,
				"location": location,
				"updated_at": datetime.now().isoformat(),
				"sources_used": list(research_data.keys())
			}

			with open(metadata_file, 'w', encoding='utf-8') as f:
				json.dump(metadata, f, indent=2)

			return True

		except Exception as e:
			print(f"Cache save error: {e}")
			return False

	def _get_cache_path(self, cache_key: str) -> Path:
		"""Get cache file path"""
		safe_name = re.sub(r'[^\w\s-]', '', cache_key).strip()
		safe_name = re.sub(r'[-\s]+', '_', safe_name).lower()
		return Path(self.config.output_dir) / f"{safe_name}.json"

	def _get_metadata_path(self, cache_key: str) -> Path:
		"""Get metadata file path"""
		cache_path = self._get_cache_path(cache_key)
		return cache_path.with_suffix('.meta.json')

	def list_cached_companies(self) -> List[Dict[str, Any]]:
		"""List all cached companies"""
		cached_companies = []
		output_path = Path(self.config.output_dir)

		for meta_file in output_path.glob("*.meta.json"):
			try:
				with open(meta_file, 'r', encoding='utf-8') as f:
					metadata = json.load(f)

				cached_time = datetime.fromisoformat(metadata['updated_at'])
				age_hours = int((datetime.now() - cached_time).total_seconds() / 3600)

				cached_companies.append({
					"company_name": metadata.get("company_name", "Unknown"),
					"location": metadata.get("location", ""),
					"updated_at": metadata["updated_at"],
					"age_hours": age_hours,
					"expired": age_hours > self.config.cache_expiry_hours
				})
			except Exception:
				continue

		return sorted(cached_companies, key=lambda x: x["updated_at"], reverse=True)