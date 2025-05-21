import requests
import os
from dotenv import load_dotenv
from pathlib import Path
from datetime import datetime
from utils import ch_urls
from typing import Any
import pandas as pd

env_file = os.path.join(Path(__file__).parent.parent.absolute(), ".env")
if os.path.exists(env_file):
	try:
		load_dotenv(env_file)
	except Exception as e:
		raise e
	else:
		print("Loaded Environment Variables.")
		api_key = os.getenv('CH_API_KEY').strip()

def call_api(url:str, user_name:str, passwd:str='') -> Any:
	try:
		response = requests.get(url, auth=(user_name, passwd))
	except Exception as e:
		print("Unable to get API data.")
		raise e
	else:
		print(response)
	return response.json()


def search_all(company_name:str) -> str:
	final_url = ch_urls.SEARCH_ALL+company_name
	company_list = call_api(final_url, api_key)
	company_df = pd.json_normalize(company_list["items"])
	f_name = f"../output/ch_{company_name.lower()}_{datetime.now().date()}.csv"
	company_df.to_csv(f_name, index=False)
	return f_name


def filter_company(df_name: str, c_name: str, c_loc: str=None):
	try:
		print(df_name)
		df = pd.read_csv(df_name)
	except Exception as e:
		raise e

	filtered_df = df[["title","company_number","company_status","address.country"]]
	return filtered_df

if __name__ == "__main__":
	print("\n")
	comp_name = input("Enter the name of company to search : ")
	comp_loc = input("Enter the location of the company: ")
	search_df = search_all(comp_name)
	print(filter_company(search_df,comp_name ))
