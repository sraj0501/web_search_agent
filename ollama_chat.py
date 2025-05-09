import os

from langchain_core.output_parsers import StrOutputParser
from langchain_ollama import ChatOllama
from langchain_core.prompts import PromptTemplate
from utils import encode_decode as ed

os.environ["LANGCHAIN_TRACING_V2"] = "false"

llm = ChatOllama(
    model = "llama3",
    temperature= 0
)

enc = ed.detect_file_encoding("natwest.txt")
print(f"Detected encoding {enc[0]} with {enc[1]*100}% accuracy.")

with open("natwest.txt", "r", encoding=enc[0]) as f:
    information = f.read()

# print(information[20])

summary_template = """From the Given {information}, I need the following details, if available. 
If Not, provide the heading and leave data as NA

The output should be in the form of a Python Dictionary provided below. 
The information should be precise and concise. 

{{products:[list of products],
services:[list of services],
target_customers:[retail/businesses/both],
operation_region:[UK/Outside_UK],
employee_count:[no of employees],
estimated_turnover:[turnover estimated],
cash_estimate: [cash estimate]}}

--- description of data sources and any agent reasoning
"""

summary_prompt_template =  PromptTemplate(
    input_variables=["information"], template=summary_template
)

chain = summary_prompt_template | llm | StrOutputParser()
res = chain.invoke(input={"information": information})

print(res)