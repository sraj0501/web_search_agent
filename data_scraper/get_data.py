import sys
import requests
import os
from dotenv import load_dotenv
from pathlib import Path


def main():
	# url = f"https://api.company-information.service.gov.uk/company/{'11486287'}"
	url = "https://api.company-information.service.gov.uk/search?q=natwest"
	api_key = os.getenv('CH_API_KEY').strip()
	print(url)

	response = requests.get(url, auth=(api_key, ''))
	print(response)
	json_resp = response.json()

	for data in json_resp:
		print(data)
		print(json_resp[data])
		print("*"*10)

if __name__ == "__main__":
	env_file = os.path.join(Path(__file__).parent.parent.absolute(), ".env")
	if os.path.exists(env_file):
		load_dotenv(env_file)
		print(main())
	else:
		print(f"Unable to load environment file {env_file}.")
		sys.exit()