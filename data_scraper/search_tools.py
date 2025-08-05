import re
from datetime import time
from typing import Dict, List, Any
import time
import requests
from bs4 import BeautifulSoup

from data_scraper import get_data_ch as gdc
from utils.common_config import EnhancedBusinessIntelligenceConfig 


# =================================================================
# CORE RESEARCH TOOLS
# =================================================================



class CompanySearchTool:
	"""Tool for searching company databases and official sources"""

	def __init__(self, config: EnhancedBusinessIntelligenceConfig ):
		self.config = config

	def search_company_house(self, company_name: str, location: str = "") -> Dict[str, Any]:
		"""Search UK Companies House for official company information"""
		try:
			# Validate input
			if not self._validate_input(company_name):
				return {"error": "Invalid company name provided", "source": "Companies House API"}

			search_query = f"{company_name} {location}".strip()

			# Use actual Companies House data via gdc module if available
			if gdc:
				company_data = gdc.search_all(search_query, "json")
				return {
					"source": "UK Companies House",
					"search_query": search_query,
					"found": True,
					"company_data": company_data
				}
			else:
				# Fallback to basic search if gdc module not available
				return {
					"source": "UK Companies House (Limited Search)",
					"search_query": search_query,
					"found": False,
					"message": "Companies House module not available - using web search fallback"
				}

		except Exception as e:
			return {"error": f"Companies House search failed: {str(e)}", "source": "Companies House API"}

	def _validate_input(self, text: str) -> bool:
		"""Validate input text"""
		if not text or len(text.strip()) < 2:
			return False
		if re.match(r'^[^a-zA-Z]*$', text.strip()):
			return False
		return True


class WikipediaResearchTool:
	"""Tool for comprehensive Wikipedia research"""

	def __init__(self, config: EnhancedBusinessIntelligenceConfig ):
		self.config = config

	def research_company(self, company_name: str, location: str = "") -> Dict[str, Any]:
		"""Get comprehensive Wikipedia data about a company"""
		try:
			# Improve search query for companies
			if "inc" not in company_name.lower() and "corp" not in company_name.lower() and "ltd" not in company_name.lower():
				search_query = f"{company_name} Inc company {location}".strip()
			else:
				search_query = f"{company_name} {location}".strip()

			# Search for Wikipedia page
			search_url = "https://en.wikipedia.org/w/api.php"
			search_params = {
				'action': 'opensearch',
				'search': search_query,
				'limit': 5,  # Get more results to find the right one
				'namespace': 0,
				'format': 'json'
			}

			response = requests.get(search_url, params=search_params, timeout=10)
			response.raise_for_status()
			search_data = response.json()

			if not search_data[1]:
				return {"error": "No Wikipedia page found", "source": "Wikipedia API", "search_query": search_query}

			# Try to find the best match (look for company-related terms)
			page_title = search_data[1][0]  # Default to first result

			# Look for better matches that might be companies
			for i, title in enumerate(search_data[1][:3]):  # Check first 3 results
				title_lower = title.lower()
				if any(term in title_lower for term in
					   ['inc', 'corp', 'company', 'limited', 'ltd', 'technologies', 'systems']):
					page_title = title
					break

			page_url = search_data[3][0] if search_data[3] else ""

			# Get comprehensive page content
			content_params = {
				'action': 'query',
				'format': 'json',
				'titles': page_title,
				'prop': 'extracts|categories|info|pageimages',
				'exintro': False,
				'explaintext': True,
				'exchars': 50000,
				'cllimit': 15,
				'inprop': 'url',
				'piprop': 'thumbnail'
			}

			content_response = requests.get(search_url, params=content_params, timeout=15)
			content_response.raise_for_status()
			content_data = content_response.json()

			pages = content_data.get('query', {}).get('pages', {})
			page_data = next(iter(pages.values())) if pages else {}

			# Extract and structure data focused on business intelligence
			result = {
				"source": "Wikipedia",
				"search_query": search_query,
				"title": page_title,
				"url": page_url,
				"content": page_data.get('extract', ''),
				"content_length": len(page_data.get('extract', '')),
				"categories": [cat['title'].replace('Category:', '')
							   for cat in page_data.get('categories', [])],
				"found": True
			}

			return result

		except Exception as e:
			return {"error": f"Wikipedia research failed: {str(e)}", "source": "Wikipedia API"}


class WebResearchTool:
	"""Tool for comprehensive web research focused on business intelligence"""

	def __init__(self, config: EnhancedBusinessIntelligenceConfig ):
		self.config = config

	def research_business_intelligence(self, company_name: str, location: str = "") -> Dict[str, Any]:
		"""Perform targeted web research for business intelligence"""
		try:
			# Create targeted search queries for different aspects
			search_queries = [
				f'"{company_name}" {location} products services',
				f'"{company_name}" {location} business model customers',
				f'"{company_name}" {location} employees turnover revenue',
				f'"{company_name}" {location} company information about'
			]

			all_results = []
			all_content = {}

			for query in search_queries:
				results = self._google_search(query)
				if results:
					all_results.extend(results)

					# Scrape content from top results
					for result in results[:3]:  # Top 3 per query
						url = result['link']
						if url not in all_content:
							content = self._scrape_website(url)
							all_content[url] = content
							time.sleep(1)  # Be respectful

			# Remove duplicates based on URL
			unique_results = []
			seen_urls = set()
			for result in all_results:
				if result['link'] not in seen_urls:
					unique_results.append(result)
					seen_urls.add(result['link'])

			return {
				"source": "Web Research (Google + Scraping)",
				"search_queries": search_queries,
				"search_results": unique_results[:self.config.max_search_results],
				"scraped_content": all_content,
				"total_sources": len(unique_results)
			}

		except Exception as e:
			return {"error": f"Web research failed: {str(e)}", "source": "Web Research"}

	def _google_search(self, query: str) -> List[Dict]:
		"""Perform Google search using Serper API"""
		url = "https://google.serper.dev/search"
		payload = {"q": query, "num": 10}
		headers = {
			"X-API-KEY": self.config.serper_api_key,
			"Content-Type": "application/json"
		}

		try:
			response = requests.post(url, json=payload, headers=headers, timeout=10)
			response.raise_for_status()
			data = response.json()

			results = []
			if "organic" in data:
				for item in data["organic"]:
					results.append({
						"title": item.get("title", ""),
						"link": item.get("link", ""),
						"snippet": item.get("snippet", "")
					})

			return results
		except Exception as e:
			print(f"Google search error for '{query}': {e}")
			return []

	def _scrape_website(self, url: str) -> str:
		"""Scrape content from a website"""
		try:
			headers = {
				'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
			}

			response = requests.get(url, headers=headers, timeout=15)
			response.raise_for_status()

			soup = BeautifulSoup(response.content, 'html.parser')

			# Remove unwanted elements
			for element in soup(["script", "style", "nav", "footer", "header", "aside"]):
				element.decompose()

			# Extract text
			text = soup.get_text()
			lines = (line.strip() for line in text.splitlines())
			chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
			clean_text = ' '.join(chunk for chunk in chunks if chunk)

			return clean_text[:self.config.max_content_length]

		except Exception as e:
			return f"Error scraping {url}: {str(e)}"
