import sys
import pandas as pd
import streamlit as st
from pathlib import Path

curr_path = Path(__file__).absolute()
parent_path = curr_path.parent.parent.absolute()
# print(curr_path)
# print(parent_path)

sys.path.append(str(parent_path))
from data_scraper import get_data_ch

# Static Variables
# =================================================================
if "res" not in st.session_state:
    st.session_state["res"] = None

# Callback Functions
# =================================================================
def get_result(company_name, company_loc):
    # We already have the values from args, so use those directly
    if company_name:
        search_df_name = get_data_ch.search_all(company_name)
        filtered_result = get_data_ch.filter_company(search_df_name, company_name)
        st.session_state["res"] = filtered_result
    else:
        st.error("Please enter a company name.")


# Main Functions
# =================================================================

with st.container(border=True):
    col1, col2 = st.columns(2)
    with col1:
        st.text_input(label="Enter the Company Name", placeholder="Oxford",
                      key="comp_name")

    with col2:
        st.text_input(label="Enter the Company Location", placeholder="England",
                      key="comp_loc")

    st.button(label="Submit", type="primary",
              on_click=get_result, args=(st.session_state["comp_name"],
                                         st.session_state["comp_loc"]),
              key="submit_button")


with st.container(border=True):
    if st.session_state["res"] is not None:
       st.dataframe(st.session_state["res"])
    else:
       st.write("No results to display yet. Enter a company name and location, then click Submit.")

if st.session_state["res"] is not None:
    with st.container(border=True):
        st.text_input(label="Enter Company Number",
                      placeholder="0000006",
                      key="search_comp")

# For debugging
# st.write("Session state:", st.session_state)