import requests
import os
from dotenv import load_dotenv
from pathlib import Path
import json
from typing import Any
import pandas as pd
import sys

curr_path = Path(__file__).absolute()
parent_path = curr_path.parent.parent.absolute()
sys.path.append(str(parent_path))
print(curr_path)
print(parent_path)

from utils import ch_urls

env_file = os.path.join(str(parent_path), ".env")
if os.path.exists(env_file):
	try:
		load_dotenv(env_file)
	except Exception as e:
		raise e
	else:
		print("Loaded Environment Variables.")
		api_key = os.getenv('CH_API_KEY')


def call_api(url:str, user_name:str, passwd:str='') -> Any:
	try:
		response = requests.get(url, auth=(user_name, passwd))
	except Exception as e:
		print("Unable to get API data.")
		raise e
	else:
		print(response)
	return response.json()


def search_all(company_name:str, output_format:str = "dataframe") -> pd.DataFrame | str|  None:
	"""output format = dataframe / json"""
	final_url = ch_urls.SEARCH_ALL+company_name
	print(final_url)
	company_list = call_api(final_url, api_key)
	company_df = pd.json_normalize(company_list["items"])
	# f_name = os.path.join(output_loc, f"ch_{company_name.lower()}_{datetime.now().date()}.csv")
	# company_df.to_csv(f_name, index=False)
	if output_format == "dataframe":
		return company_df
	elif output_format == "json":
		return company_list
	return None


def filter_company(df: pd.DataFrame,comp_num: str):
	req_cols = ["title","company_number","company_status","address.country"]
	filtered_df = df[req_cols][df["company_number"].str.strip().str.lower() == comp_num.strip().lower()]

	return filtered_df, df[req_cols]


if __name__ == "__main__":
	print("\n")
	comp_name = input("Enter the name of company to search : ")
	comp_loc = input("Enter the location of the company: ")
	output_dir = os.getenv("OUTPUT_DIR")
	kw, *args = comp_name.strip().lower().split()
	search_df = search_all(kw)
	fil_df, all_df = filter_company(search_df, comp_loc, *args)
