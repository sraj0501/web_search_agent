# KYC Agent with Modern Material Design
# =================================================================

import sys
import os
import streamlit as st
from pathlib import Path
import pandas as pd
import requests
import re
from urllib.parse import urlparse
from bs4 import BeautifulSoup
import time
from datetime import datetime, timedelta
import json
# import wikipedia  # Removed to avoid dependency issues

curr_path = Path(__file__).absolute()
parent_path = curr_path.parent.parent.absolute()
sys.path.append(str(parent_path))

from data_scraper import get_data_ch

# Load Custom CSS
# =================================================================
def load_css():
    """Load custom CSS for modern Material Design look"""
    css_file_path = Path(__file__).parent / "styles.css"
    
    if css_file_path.exists():
        with open(css_file_path, "r", encoding="utf-8") as css_file:
            st.markdown(f"<style>{css_file.read()}</style>", unsafe_allow_html=True)

# Initialize CSS
load_css()

# Static Variables
# =================================================================
if "res" not in st.session_state:
    st.session_state["res"] = None
    st.session_state["all_res"] = None
    st.session_state["form_submitted"] = False
    st.session_state["comp_name"] = ""
    st.session_state["manual_company_input"] = ""
    st.session_state["search_results"] = None
    st.session_state["scraped_data"] = None

REQ_COLS = ["title", "company_number", "company_status", "address.country"]

# Configuration
SERPER_API_KEY = os.getenv("SERPER_API_KEY")  # Set your Serper API key in environment variables
OUTPUT_DIR = os.getenv("OUTPUT_DIR", "./output")  # Default output directory
CACHE_EXPIRY_HOURS = 24  # Cache expires after 24 hours

# Utility Functions
# =================================================================
def get_cache_filename(query: str) -> str:
    """Generate cache filename based on query"""
    # Sanitize query for filename
    sanitized_query = re.sub(r'[^\w\s-]', '', query).strip()
    sanitized_query = re.sub(r'[-\s]+', '_', sanitized_query)
    return f"{sanitized_query.lower()}.txt"

def get_cache_metadata_filename(query: str) -> str:
    """Generate cache metadata filename"""
    cache_filename = get_cache_filename(query)
    return cache_filename.replace('.txt', '_metadata.json')

def is_cache_valid(query: str) -> bool:
    """Check if cached data exists and is still valid"""
    metadata_file = os.path.join(OUTPUT_DIR, get_cache_metadata_filename(query))
    
    if not os.path.exists(metadata_file):
        return False
    
    try:
        with open(metadata_file, 'r', encoding='utf-8') as f:
            metadata = json.load(f)
        
        cached_time = datetime.fromisoformat(metadata['updated_at'])
        expiry_time = cached_time + timedelta(hours=CACHE_EXPIRY_HOURS)
        
        return datetime.now() < expiry_time
    except (json.JSONDecodeError, KeyError, ValueError):
        return False

def load_cached_data(query: str) -> tuple[list, dict, dict]:
    """Load cached search results and scraped data"""
    cache_file = os.path.join(OUTPUT_DIR, get_cache_filename(query))
    metadata_file = os.path.join(OUTPUT_DIR, get_cache_metadata_filename(query))
    
    try:
        with open(metadata_file, 'r', encoding='utf-8') as f:
            metadata = json.load(f)
        
        # Return empty data structures for consistency, actual content is in the text file
        return metadata.get('search_results', []), {}, metadata
    except (FileNotFoundError, json.JSONDecodeError):
        return [], {}, {}

def scrape_wikipedia(query: str) -> dict:
    """
    Scrape complete Wikipedia content using direct API calls (no external package needed)
    Returns dict with full Wikipedia page data
    """
    try:
        # Wikipedia API endpoints
        opensearch_url = "https://en.wikipedia.org/w/api.php"
        
        # First, search for the page
        search_params = {
            'action': 'opensearch',
            'search': query,
            'limit': 3,
            'namespace': 0,
            'format': 'json'
        }
        
        search_response = requests.get(opensearch_url, params=search_params, timeout=10)
        search_response.raise_for_status()
        search_data = search_response.json()
        
        if not search_data[1]:  # No results found
            return {"error": "No Wikipedia pages found"}
        
        # Get the first result title
        page_title = search_data[1][0]
        page_url = search_data[3][0] if search_data[3] else ""

        for i, title in enumerate(search_data[1][:3]):  # Check first 3 results
            title_lower = title.lower()
            if any(term in title_lower for term in
                   ['inc', 'corp', 'company', 'limited', 'ltd', 'technologies', 'systems']):
                page_title = title
                break

        # Get page summary using REST API (for thumbnail and basic info)
        summary_url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{page_title.replace(' ', '_')}"
        try:
            summary_response = requests.get(summary_url, timeout=10)
            summary_response.raise_for_status()
            summary_data = summary_response.json()
        except:
            summary_data = {}
        
        # Get COMPLETE page content using MediaWiki API
        content_params = {
            'action': 'query',
            'format': 'json',
            'titles': page_title,
            'prop': 'extracts|categories|info|pageimages',
            'exintro': False,  # Get full content, not just intro
            'explaintext': True,  # Plain text format
            'exsectionformat': 'plain',
            'exchars': 50000,  # Increased to 50,000 characters for full content
            'cllimit': 10,  # Get more categories
            'inprop': 'url',  # Get page URL
            'piprop': 'thumbnail|original',  # Get page images
            'pithumbsize': 300
        }
        
        content_response = requests.get(opensearch_url, params=content_params, timeout=15)
        content_response.raise_for_status()
        content_data = content_response.json()
        
        # Extract content and metadata
        pages = content_data.get('query', {}).get('pages', {})
        page_data = next(iter(pages.values())) if pages else {}
        
        # Get full content
        full_content = page_data.get('extract', '')
        
        # If the content is truncated, try to get even more
        if len(full_content) >= 49000:  # Close to the limit, try to get more
            content_params['exchars'] = 100000  # Try for 100k characters
            try:
                extended_response = requests.get(opensearch_url, params=content_params, timeout=20)
                extended_response.raise_for_status()
                extended_data = extended_response.json()
                pages_extended = extended_data.get('query', {}).get('pages', {})
                page_data_extended = next(iter(pages_extended.values())) if pages_extended else {}
                extended_content = page_data_extended.get('extract', '')
                if len(extended_content) > len(full_content):
                    full_content = extended_content
            except:
                pass  # Use the original content if extended request fails
        
        # Extract categories
        categories = []
        if 'categories' in page_data:
            categories = [cat['title'].replace('Category:', '') for cat in page_data['categories']]
        
        # Extract sections for better organization (attempt to get sections)
        sections_params = {
            'action': 'parse',
            'format': 'json',
            'page': page_title,
            'prop': 'sections',
        }
        
        sections = []
        try:
            sections_response = requests.get(opensearch_url, params=sections_params, timeout=10)
            sections_response.raise_for_status()
            sections_data = sections_response.json()
            if 'parse' in sections_data and 'sections' in sections_data['parse']:
                sections = [section['line'] for section in sections_data['parse']['sections'][:10]]  # First 10 sections
        except:
            pass  # Continue without sections if this fails
        
        # Create comprehensive summary
        summary_text = summary_data.get('extract', '')
        if not summary_text and full_content:
            # Create summary from first paragraph if API summary not available
            paragraphs = full_content.split('\n\n')
            summary_text = paragraphs[0] if paragraphs else full_content[:500]
        
        return {
            "title": summary_data.get('title', page_title),
            "url": page_url or summary_data.get('content_urls', {}).get('desktop', {}).get('page', ''),
            "summary": summary_text[:1000],  # First 1000 chars as summary
            "content": full_content,  # COMPLETE page content
            "content_length": len(full_content),
            "categories": categories[:10],  # More categories
            "sections": sections,  # Page sections
            "thumbnail": summary_data.get('thumbnail', {}).get('source', '') if 'thumbnail' in summary_data else '',
            "description": summary_data.get('description', ''),
            "page_id": page_data.get('pageid', ''),
            "last_modified": page_data.get('touched', ''),
            "is_complete": len(full_content) < 99000  # Indicate if we got complete content
        }
        
    except requests.exceptions.RequestException as e:
        return {"error": f"Wikipedia API request failed: {str(e)}"}
    except (KeyError, IndexError, ValueError) as e:
        return {"error": f"Wikipedia data parsing error: {str(e)}"}
    except Exception as e:
        return {"error": f"Wikipedia scraping error: {str(e)}"}

def validate_text_input(text: str) -> tuple[bool, str]:
    """
    Validate if the input text is meaningful
    Returns: (is_valid, error_message)
    """
    if not text or text.strip() == "":
        return False, "Input cannot be empty or just whitespace."
    
    if len(text.strip()) < 2:
        return False, "Input must be at least 2 characters long."
    
    # Check if it's just special characters or numbers
    if re.match(r'^[^a-zA-Z]*$', text.strip()):
        return False, "Input must contain at least some alphabetic characters."
    
    return True, ""

def google_search_serper(query: str, num_results: int = 9) -> list:
    """
    Perform Google search using Serper API
    Returns list of search results with titles, links, and snippets
    Note: Default to 9 results to combine with Wikipedia for total of 10 sources
    """
    if not SERPER_API_KEY:
        st.error("Serper API key not found. Please set SERPER_API_KEY environment variable.")
        return []
    
    url = "https://google.serper.dev/search"
    payload = {
        "q": query,
        "num": num_results
    }
    headers = {
        "X-API-KEY": SERPER_API_KEY,
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        results = []
        if "organic" in data:
            for item in data["organic"][:num_results]:
                results.append({
                    "title": item.get("title", ""),
                    "link": item.get("link", ""),
                    "snippet": item.get("snippet", "")
                })
        
        return results
    except requests.exceptions.RequestException as e:
        st.error(f"Error performing search: {str(e)}")
        return []

def scrape_website_content(url: str) -> str:
    """
    Scrape text content from a website
    Returns cleaned text content
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Remove script and style elements
        for script in soup(["script", "style", "nav", "footer", "header"]):
            script.decompose()
        
        # Get text content
        text = soup.get_text()
        
        # Clean up text
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = ' '.join(chunk for chunk in chunks if chunk)
        
        return text[:5000]  # Limit to first 5000 characters to avoid huge files
        
    except Exception as e:
        return f"Error scraping {url}: {str(e)}"

def save_scraped_data(query: str, search_results: list, scraped_content: dict, wikipedia_data: dict):
    """
    Save all scraped data to a text file with caching
    """
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # Create filename based on query (for caching)
    cache_filename = get_cache_filename(query)
    cache_filepath = os.path.join(OUTPUT_DIR, cache_filename)
    
    # Create metadata file
    metadata_filename = get_cache_metadata_filename(query)
    metadata_filepath = os.path.join(OUTPUT_DIR, metadata_filename)
    
    try:
        # Save main content file
        with open(cache_filepath, 'w', encoding='utf-8') as f:
            f.write(f"KYC Research Data\n")
            f.write(f"Query: {query}\n")
            f.write(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Updated at: {datetime.now().isoformat()}\n")
            f.write("=" * 80 + "\n\n")
            
            # Add Wikipedia section first
            f.write("WIKIPEDIA INFORMATION:\n")
            f.write("=" * 40 + "\n")
            if "error" not in wikipedia_data:
                f.write(f"Title: {wikipedia_data.get('title', 'N/A')}\n")
                f.write(f"URL: {wikipedia_data.get('url', 'N/A')}\n")
                f.write(f"Page ID: {wikipedia_data.get('page_id', 'N/A')}\n")
                f.write(f"Last Modified: {wikipedia_data.get('last_modified', 'N/A')}\n")
                f.write(f"Content Length: {wikipedia_data.get('content_length', 0):,} characters\n")
                f.write(f"Complete Content: {wikipedia_data.get('is_complete', 'Unknown')}\n")
                f.write(f"Description: {wikipedia_data.get('description', 'N/A')}\n")
                f.write("-" * 40 + "\n")
                f.write("Summary:\n")
                f.write(wikipedia_data.get('summary', 'N/A'))
                f.write("\n" + "-" * 40 + "\n")
                
                # Add sections if available
                if wikipedia_data.get('sections'):
                    f.write("Main Sections:\n")
                    for i, section in enumerate(wikipedia_data['sections'], 1):
                        f.write(f"{i}. {section}\n")
                    f.write("-" * 40 + "\n")
                
                # Add categories
                if wikipedia_data.get('categories'):
                    f.write(f"Categories: {', '.join(wikipedia_data['categories'])}\n")
                    f.write("-" * 40 + "\n")
                
                # Add complete content
                f.write("COMPLETE WIKIPEDIA CONTENT:\n")
                f.write("-" * 40 + "\n")
                f.write(wikipedia_data.get('content', 'No content available'))
                f.write("\n" + "=" * 80 + "\n\n")
            else:
                f.write(f"Wikipedia Error: {wikipedia_data['error']}\n")
                f.write("=" * 80 + "\n\n")
            
            # Add Google search results
            f.write("GOOGLE SEARCH RESULTS:\n")
            f.write("=" * 40 + "\n")
            for i, result in enumerate(search_results, 1):
                f.write(f"RESULT {i}:\n")
                f.write(f"Title: {result['title']}\n")
                f.write(f"URL: {result['link']}\n")
                f.write(f"Snippet: {result['snippet']}\n")
                f.write("-" * 40 + "\n")
                
                url = result['link']
                if url in scraped_content:
                    f.write("SCRAPED CONTENT:\n")
                    f.write(scraped_content[url])
                    f.write("\n" + "=" * 80 + "\n\n")
                else:
                    f.write("Content could not be scraped.\n")
                    f.write("=" * 80 + "\n\n")
        
        # Save metadata file
        metadata = {
            "query": query,
            "updated_at": datetime.now().isoformat(),
            "search_results": search_results,
            "has_wikipedia": "error" not in wikipedia_data,
            "total_sources": len(search_results) + (1 if "error" not in wikipedia_data else 0)
        }
        
        with open(metadata_filepath, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
        
        return cache_filepath
    except Exception as e:
        st.error(f"Error saving file: {str(e)}")
        return None

# Callback Functions
# =================================================================
def display_results(comp_name: str):
    """Display search results with proper validation"""
    is_valid, error_msg = validate_text_input(comp_name)
    
    if not is_valid:
        st.error(error_msg)
        st.session_state["all_res"] = None
        return
    
    try:
        with st.spinner("Searching for companies..."):
            search_df_name = get_data_ch.search_all(comp_name)
            if search_df_name is not None and not search_df_name.empty:
                st.session_state["all_res"] = search_df_name[REQ_COLS]
                st.success(f"Found {len(search_df_name)} companies matching your search.")
            else:
                st.warning("No companies found matching your search criteria.")
                st.session_state["all_res"] = None
    except Exception as e:
        st.error(f"Error occurred during search: {str(e)}")
        st.session_state["all_res"] = None

def perform_research(research_query: str, is_manual_entry: bool = False):
    """Perform Google search and web scraping with caching"""
    if not is_manual_entry and not st.session_state["all_res"] is None:
        # Validate that the query matches a column title (only for dropdown selection)
        available_titles = st.session_state["all_res"]["title"].tolist()
        
        if research_query not in available_titles:
            st.error("Please enter a company name that exists in the search results table above.")
            return
    
    is_valid, error_msg = validate_text_input(research_query)
    if not is_valid:
        st.error(error_msg)
        return
    
    # For manual entry, extract the first word for search
    if is_manual_entry:
        search_keyword = research_query.strip().split()[0]
        st.info(f"🔍 Searching for: '{search_keyword}' (first word from your input: '{research_query}')")
    else:
        search_keyword = research_query
    
    # Check if cached data exists and is valid (use search_keyword for cache)
    if is_cache_valid(search_keyword):
        cache_file = os.path.join(OUTPUT_DIR, get_cache_filename(search_keyword))
        metadata_file = os.path.join(OUTPUT_DIR, get_cache_metadata_filename(search_keyword))
        
        with open(metadata_file, 'r', encoding='utf-8') as f:
            metadata = json.load(f)
        
        st.info(f"📁 Using cached data from {metadata['updated_at'][:19].replace('T', ' ')}")
        
        # Display cache information
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Cached Sources", metadata.get('total_sources', 0))
        with col2:
            st.metric("Wikipedia Included", "Yes" if metadata.get('has_wikipedia') else "No")
        with col3:
            cached_time = datetime.fromisoformat(metadata['updated_at'])
            hours_old = int((datetime.now() - cached_time).total_seconds() / 3600)
            st.metric("Cache Age", f"{hours_old}h")
        
        # Provide download button for cached file
        with open(cache_file, 'r', encoding='utf-8') as f:
            file_content = f.read()
        
        st.download_button(
            label="📥 Download Cached Research Data",
            data=file_content,
            file_name=os.path.basename(cache_file),
            mime="text/plain"
        )
        
        # Option to refresh data
        if st.button("🔄 Refresh Data (Perform New Search)", key="refresh_cache"):
            perform_fresh_research(search_keyword, research_query)
        
        # Store cached results for bottom display
        st.session_state["current_research"] = {
            "search_keyword": search_keyword,
            "original_query": research_query,
            "is_cached": True,
            "metadata": metadata,
            "cache_file": cache_file
        }
        
        return
    
    # Perform fresh research
    perform_fresh_research(search_keyword, research_query)

def perform_fresh_research(search_keyword: str, original_query: str = None):
    """Perform fresh research without cache"""
    display_query = original_query or search_keyword
    
    # Step 1: Scrape Wikipedia
    with st.spinner("🔍 Searching Wikipedia..."):
        wikipedia_data = scrape_wikipedia(search_keyword)
        
        if "error" not in wikipedia_data:
            st.success(f"✅ Wikipedia data found: {wikipedia_data['title']}")
        else:
            st.warning(f"⚠️ Wikipedia: {wikipedia_data['error']}")
    
    # Step 2: Google Search
    with st.spinner("🌐 Performing Google search..."):
        search_results = google_search_serper(search_keyword, 9)  # Get 9 Google results + 1 Wikipedia = 10 total
        
        if not search_results:
            st.error("No search results found or API error occurred.")
            return
        
        st.session_state["search_results"] = search_results
        
        # Display search results
        st.subheader("🔍 Search Results")
        
        if original_query and original_query != search_keyword:
            st.info(f"Searched for: **{search_keyword}** (from your input: '{original_query}')")
        
        # Calculate total sources
        total_sources = len(search_results) + (1 if "error" not in wikipedia_data else 0)
        st.info(f"📊 Found {total_sources} sources to scrape (Wikipedia + {len(search_results)} Google results)")
        
        # Show Wikipedia result first if available
        if "error" not in wikipedia_data:
            with st.expander(f"📖 Wikipedia: {wikipedia_data['title']}", expanded=True):
                st.write(f"**URL:** {wikipedia_data['url']}")
                st.write(f"**Summary:** {wikipedia_data['summary']}")
                if wikipedia_data.get('categories'):
                    st.write(f"**Categories:** {', '.join(wikipedia_data['categories'][:3])}")
                
                # Show content statistics
                content_length = wikipedia_data.get('content_length', 0)
                is_complete = wikipedia_data.get('is_complete', True)
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Content Length", f"{content_length:,} chars")
                with col2:
                    st.metric("Sections Found", len(wikipedia_data.get('sections', [])))
                with col3:
                    status = "✅ Complete" if is_complete else "⚠️ Truncated"
                    st.metric("Content Status", status)
                
                # Show sections if available
                if wikipedia_data.get('sections'):
                    st.write(f"**Main Sections:** {', '.join(wikipedia_data['sections'][:5])}")
                    if len(wikipedia_data['sections']) > 5:
                        st.write(f"...and {len(wikipedia_data['sections']) - 5} more sections")
        
        # Show Google results
        for i, result in enumerate(search_results, 1):
            with st.expander(f"🌐 {i}. {result['title'][:80]}..."):
                st.write(f"**URL:** {result['link']}")
                st.write(f"**Snippet:** {result['snippet']}")
    
    # Step 3: Scrape websites
    with st.spinner(f"📄 Scraping content from {total_sources} websites..."):
        scraped_content = {}
        
        # Create progress tracking
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        current_progress = 0
        total_to_scrape = len(search_results)
        
        # Scrape Google search results
        for i, result in enumerate(search_results):
            url = result['link']
            status_text.text(f"Scraping {i+1}/{total_to_scrape}: {url[:50]}...")
            scraped_content[url] = scrape_website_content(url)
            current_progress += 1
            progress_bar.progress(current_progress / total_to_scrape)
            time.sleep(1)  # Be respectful to websites
        
        status_text.text("✅ Scraping completed!")
        st.session_state["scraped_data"] = scraped_content
        
        # Save to file (with caching) - use search_keyword for cache filename
        filepath = save_scraped_data(search_keyword, search_results, scraped_content, wikipedia_data)
        
        if filepath:
            st.success(f"✅ Research data cached as: {os.path.basename(filepath)}")
            
            # Display comprehensive summary metrics
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                total_sources = len(search_results) + (1 if "error" not in wikipedia_data else 0)
                st.metric("Total Sources", total_sources)
            with col2:
                st.metric("Google Results", len(search_results))
            with col3:
                st.metric("Wikipedia", "✅" if "error" not in wikipedia_data else "❌")
            with col4:
                st.metric("Cache Valid", f"{CACHE_EXPIRY_HOURS}h")
            
            # Show detailed breakdown
            with st.expander("📋 Detailed Source Breakdown"):
                if "error" not in wikipedia_data:
                    st.write("🔹 **Wikipedia**: ✅ Scraped successfully")
                else:
                    st.write("🔹 **Wikipedia**: ❌ Failed to scrape")
                
                st.write(f"🔹 **Google Search Results**: {len(search_results)} websites")
                for i, result in enumerate(search_results, 1):
                    url = result['link']
                    status = "✅" if url in scraped_content and not scraped_content[url].startswith("Error") else "❌"
                    st.write(f"   {i}. {status} {result['title'][:60]}...")
            
            # Provide download button
            with open(filepath, 'r', encoding='utf-8') as f:
                file_content = f.read()
            
            st.download_button(
                label="📥 Download Complete Research Data",
                data=file_content,
                file_name=os.path.basename(filepath),
                mime="text/plain"
            )

# Main Functions
# =================================================================

# Modern Header with Material Design
st.markdown("""
<div class="kyc-header">
    <h1>🔍 KYC Research Application</h1>
    <p style="font-size: 1.1rem; color: var(--md-text-secondary); margin: 0;">
        Comprehensive company research with Wikipedia and web scraping
    </p>
</div>
""", unsafe_allow_html=True)

# User Input Section
st.markdown('<div class="kyc-section fade-in-up">', unsafe_allow_html=True)
st.markdown("### 📊 Step 1: Search for Companies")

with st.container(border=True):
    st.text_input(
        label="Company Name", 
        placeholder="Enter company name (e.g., Oxford, Microsoft, etc.)",
        key="comp_name",
        help="Enter at least 2 characters with alphabetic content"
    )

    col1, col2 = st.columns([1, 4])
    with col1:
        st.button(
            label="🔍 Submit", 
            type="primary",
            on_click=display_results, 
            args=[st.session_state["comp_name"]],
            key="submit_button",
            use_container_width=True
        )

st.markdown('</div>', unsafe_allow_html=True)

# Display Results Section
if st.session_state["all_res"] is not None:
    st.markdown('<div class="kyc-section slide-in">', unsafe_allow_html=True)
    st.markdown("### 📋 Search Results")
    
    st.dataframe(
        st.session_state["all_res"], 
        use_container_width=True,
        hide_index=True
    )
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Research Section
    st.markdown('<hr class="kyc-divider">', unsafe_allow_html=True)
    st.markdown('<div class="kyc-section fade-in-up">', unsafe_allow_html=True)
    st.markdown("### 🔬 Step 2: Research Company")
    
    with st.container(border=True):
        # Create selectbox with company titles for easier selection
        company_options = [""] + st.session_state["all_res"]["title"].tolist()
        
        selected_company = st.selectbox(
            "Select a company from the results above:",
            options=company_options,
            key="selected_company"
        )
        
        # Also allow manual input
        manual_input = st.text_input(
            "Or enter company name manually:",
            placeholder="Enter any company name (e.g., 'Apple Inc Corporation' - will search for 'Apple')",
            key="manual_company_input",
            help="You can enter any text. The search will use the first word of your input."
        )
        
        # Determine which input to use and whether it's manual
        if manual_input and manual_input.strip():
            research_query = manual_input.strip()
            is_manual = True
        elif selected_company:
            research_query = selected_company
            is_manual = False
        else:
            research_query = ""
            is_manual = False
        
        # Show what will be searched if manual input
        if is_manual and research_query:
            first_word = research_query.split()[0]
            st.caption(f"🔍 Will search for: **{first_word}** (first word from your input)")
        
        col1, col2 = st.columns([1, 4])
        with col1:
            st.button(
                label="🔍 Start Research", 
                type="secondary",
                on_click=perform_research,
                args=[research_query, is_manual],
                key="main_research_button",
                disabled=not research_query,
                help="Search Wikipedia + Google and scrape content",
                use_container_width=True
            )
    
        st.markdown('</div>', unsafe_allow_html=True)
        
        # Also allow manual input
        manual_input = st.text_input(
            "Or enter company name manually:",
            placeholder="Enter any company name (e.g., 'Apple Inc Corporation' - will search for 'Apple')",
            key="comp_num",
            help="You can enter any text. The search will use the first word of your input."
        )
        
        # Determine which input to use and whether it's manual
        if manual_input and manual_input.strip():
            research_query = manual_input.strip()
            is_manual = True
        elif selected_company:
            research_query = selected_company
            is_manual = False
        else:
            research_query = ""
            is_manual = False
        
        # Show what will be searched if manual input
        if is_manual and research_query:
            first_word = research_query.split()[0]
            st.caption(f"🔍 Will search for: **{first_word}** (first word from your input)")
        
        st.button(
            label="🔍 Start Research", 
            type="secondary",
            on_click=perform_research,
            args=[research_query, is_manual],
            key="research_button",
            disabled=not research_query,
            help="Search Wikipedia + Google and scrape content"
        )

# ================================================================================
# BOTTOM SECTION: DETAILED RESULTS AND CACHE MANAGEMENT
# ================================================================================

# Display detailed research results at the bottom
if st.session_state.get("current_research"):
    st.divider()
    st.header("📋 Detailed Research Results", divider=True)
    
    research_data = st.session_state["current_research"]
    
    # Check if this is cached or fresh data
    if research_data.get("is_cached"):
        st.info("📁 Displaying cached research data")
        metadata = research_data.get("metadata", {})
        
        # Display cache info
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Cached Sources", metadata.get('total_sources', 0))
        with col2:
            st.metric("Wikipedia Included", "Yes" if metadata.get('has_wikipedia') else "No")
        with col3:
            cached_time = datetime.fromisoformat(metadata['updated_at'])
            hours_old = int((datetime.now() - cached_time).total_seconds() / 3600)
            st.metric("Cache Age", f"{hours_old}h")
        with col4:
            st.metric("Cache Valid", f"{CACHE_EXPIRY_HOURS}h")
        
        # Provide download button for cached file
        cache_file = research_data.get("cache_file")
        if cache_file and os.path.exists(cache_file):
            with open(cache_file, 'r', encoding='utf-8') as f:
                file_content = f.read()
            
            col1, col2 = st.columns([1, 4])
            with col1:
                st.download_button(
                    label="📥 Download Cached Research Data",
                    data=file_content,
                    file_name=os.path.basename(cache_file),
                    mime="text/plain"
                )
            with col2:
                if st.button("🔄 Refresh Data (Perform New Search)", key="refresh_cache_bottom"):
                    perform_fresh_research(research_data.get("search_keyword"), research_data.get("original_query"))
                    st.rerun()
    
    else:
        # Fresh research results
        st.success("🆕 Fresh research completed")
        
        wikipedia_data = research_data.get("wikipedia_data", {})
        search_results = research_data.get("search_results", [])
        scraped_content = research_data.get("scraped_content", {})
        
        # Display comprehensive summary metrics
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Sources", research_data.get("total_sources", 0))
        with col2:
            st.metric("Google Results", len(search_results))
        with col3:
            st.metric("Wikipedia", "✅" if "error" not in wikipedia_data else "❌")
        with col4:
            st.metric("Cache Valid", f"{CACHE_EXPIRY_HOURS}h")
        
        # Show search info
        if research_data.get("original_query") and research_data.get("original_query") != research_data.get("search_keyword"):
            st.info(f"Searched for: **{research_data.get('search_keyword')}** (from your input: '{research_data.get('original_query')}')")
        
        # Display search results
        st.subheader("🔍 Search Results Details")
        
        # Show Wikipedia result first if available
        if "error" not in wikipedia_data:
            with st.expander(f"📖 Wikipedia: {wikipedia_data['title']}", expanded=False):
                st.write(f"**URL:** {wikipedia_data['url']}")
                st.write(f"**Summary:** {wikipedia_data['summary']}")
                if wikipedia_data.get('categories'):
                    st.write(f"**Categories:** {', '.join(wikipedia_data['categories'][:3])}")
                
                # Show content statistics
                content_length = wikipedia_data.get('content_length', 0)
                is_complete = wikipedia_data.get('is_complete', True)
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Content Length", f"{content_length:,} chars")
                with col2:
                    st.metric("Sections Found", len(wikipedia_data.get('sections', [])))
                with col3:
                    status = "✅ Complete" if is_complete else "⚠️ Truncated"
                    st.metric("Content Status", status)
                
                # Show sections if available
                if wikipedia_data.get('sections'):
                    st.write(f"**Main Sections:** {', '.join(wikipedia_data['sections'][:5])}")
                    if len(wikipedia_data['sections']) > 5:
                        st.write(f"...and {len(wikipedia_data['sections']) - 5} more sections")
        
        # Show Google results
        for i, result in enumerate(search_results, 1):
            with st.expander(f"🌐 {i}. {result['title'][:80]}..."):
                st.write(f"**URL:** {result['link']}")
                st.write(f"**Snippet:** {result['snippet']}")
        
        # Show detailed breakdown
        with st.expander("📋 Detailed Source Breakdown"):
            if "error" not in wikipedia_data:
                st.write("🔹 **Wikipedia**: ✅ Scraped successfully")
            else:
                st.write("🔹 **Wikipedia**: ❌ Failed to scrape")
            
            st.write(f"🔹 **Google Search Results**: {len(search_results)} websites")
            for i, result in enumerate(search_results, 1):
                url = result['link']
                status = "✅" if url in scraped_content and not scraped_content[url].startswith("Error") else "❌"
                st.write(f"   {i}. {status} {result['title'][:60]}...")
        
        # Provide download button
        filepath = research_data.get("filepath")
        if filepath and os.path.exists(filepath):
            with open(filepath, 'r', encoding='utf-8') as f:
                file_content = f.read()
            
            st.download_button(
                label="📥 Download Complete Research Data",
                data=file_content,
                file_name=os.path.basename(filepath),
                mime="text/plain"
            )

# Cache Management Section (moved to bottom)
st.divider()
st.header("🗂️ Cache Management", divider=True)
if os.path.exists(OUTPUT_DIR):
    cache_files = [f for f in os.listdir(OUTPUT_DIR) if f.endswith('.txt') and not f.endswith('_metadata.json')]
    
    if cache_files:
        st.write(f"**Found {len(cache_files)} cached research files:**")
        
        for cache_file in sorted(cache_files):
            metadata_file = cache_file.replace('.txt', '_metadata.json')
            metadata_path = os.path.join(OUTPUT_DIR, metadata_file)
            
            if os.path.exists(metadata_path):
                try:
                    with open(metadata_path, 'r', encoding='utf-8') as f:
                        metadata = json.load(f)
                    
                    cached_time = datetime.fromisoformat(metadata['updated_at'])
                    is_valid = datetime.now() < cached_time + timedelta(hours=CACHE_EXPIRY_HOURS)
                    
                    col1, col2, col3 = st.columns([3, 1, 1])
                    with col1:
                        status_icon = "🟢" if is_valid else "🔴"
                        st.write(f"{status_icon} **{metadata['query']}** - {cached_time.strftime('%Y-%m-%d %H:%M')}")
                    with col2:
                        file_path = os.path.join(OUTPUT_DIR, cache_file)
                        with open(file_path, 'r', encoding='utf-8') as f:
                            file_content = f.read()
                        st.download_button(
                            "📥",
                            data=file_content,
                            file_name=cache_file,
                            mime="text/plain",
                            key=f"download_{cache_file}"
                        )
                    with col3:
                        if st.button("🗑️", key=f"delete_{cache_file}", help="Delete cache"):
                            try:
                                os.remove(os.path.join(OUTPUT_DIR, cache_file))
                                os.remove(metadata_path)
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error deleting: {e}")
                
                except (json.JSONDecodeError, KeyError):
                    st.write(f"⚠️ {cache_file} - Invalid metadata")
    else:
        st.write("No cached files found.")
else:
    st.write("Cache directory not found.")

# Debug Information (remove in production)
if st.checkbox("Show Debug Info"):
    st.write("Session State:", st.session_state)