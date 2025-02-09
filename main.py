from logging import exception

from PIL import Image
import streamlit as st
import pypyodbc as podbc
import os
import re
from groq import Groq
import time
import pandas as pd

st.set_page_config(layout="wide")
connection = None
cursor = None
try:
  connection = podbc.connect("Driver={ODBC Driver 17 for SQL Server};"
                               "Server=PONNU_LAP;"
                               "Database=Demo;"
                               "UID=streamlit_user;"
                               "PWD=Streamlit@0123;")
  cursor = connection.cursor()
  print("Connection successful")
except Exception as e:
    print(f"Connection failed: {e}")

if connection:
  os.environ['GROQ_API_KEY'] = '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'
  client = Groq()
else:
    print("Skipping Groq client initialization due to failed SQL Server connection.")
  
img1=Image.open('ai1.jpg')
img1_resize=img1.resize((700,150))
st.image(img1_resize,use_container_width=False)
img2=Image.open('ai2.jpg')
st.sidebar.image(img2,use_container_width=True)
st.sidebar.header("Filters")
table_name=st.sidebar.text_input("Table Name","Employee")
schema=st.sidebar.text_input("schema","[dbo]")

left_col,right_col=st.columns(2)
# 1st function - get column metadata & example sql query - by giving table name , scheme, connection

def exctract_col_metadata(table_name,schema):
    query = f"SELECT COLUMN_NAME, DATA_TYPE FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME='{table_name}'"
    cursor.execute(query)
    columns = cursor.fetchall()
    # wrap all columns in square brackets
    column_metadata = {f"[{col[0]}]": col[1] for col in columns}
    # print(column_metadata)
    Example_sql_query = f'''SELECT {', '.join(column_metadata.keys())} FROM {schema}.{table_name} WHERE [CONDITION] LIMIT 10;)'''
    # print(Example_sql_query)
    return column_metadata, Example_sql_query


# 2nd function - to extract sql only from agent response


def sql_only(as_res):
    query_only_sql = re.findall(r"SELECT.*?;", as_res, re.IGNORECASE | re.DOTALL)
    if query_only_sql:
        return query_only_sql[0].strip().rstrip(';')
    else:
        return ValueError("no sql found")


# 1st agent - to make 1 sql query - for given question from given metadata as given example sql query
def make_sql_query(question, column_metadata, Example_sql_query,schema):
    prompt = f'''create only one sql query for the given question: {question}
    from the column metadata: {column_metadata}
    the creating sql query example like: {Example_sql_query}
    the sql query should be in the T-SQL format'''
    response = client.chat.completions.create(
        model='llama-3.1-8b-instant',
        messages=[
            {
                "role": "system",
                "content": "you ara a helpful assistant."
            },
            {
                "role": "user",
                "content": "correct spelling of woord employee"
            },
            {
                "role": "system",
                "content": "employee is the correct spelling"
            },
            {
                "role": "user",
                "content": prompt
            }
        ]
    )
    as_res = response.choices[0].message.content
    print(sql_only(as_res))
    return sql_only(as_res)


# 3rd function
def dataframe_creation(sql_query):
    cursor.execute(sql_query)
    result = cursor.fetchall()
    columns = [col[0] for col in cursor.description]
    print(f"columns are involved in this question:{columns}")
    df = pd.DataFrame(result, columns=columns)
    return df


# 2nd agent -  answer given question by giving a df
def make_answer(df, question):
    prompt = f'''answer the given question: {question}
    from the given data: {df} answer the question, dont give any sql query while answering'''
    response = client.chat.completions.create(
        model='llama-3.1-8b-instant',
        messages=[
            {
                "role": "system",
                "content": "you ara a helpful assistant."
            },
            {
                "role": "user",
                "content": "correct spelling of woord employee"
            },
            {
                "role": "system",
                "content": "employee is the correct spelling"
            },
            {
                "role": "user",
                "content": prompt
            }
        ]
    )
    as_res = response.choices[0].message.content
    return as_res


# 4th fun - retries
def retries(question,retries=3):
    attempt=0
    success=False
    df=None
    answer=None
    while attempt < retries and not success:
        try:
            attempt += 1
            column_metadata, Example_sql_query = exctract_col_metadata(table_name, schema)
            sql_query = make_sql_query(question, column_metadata, Example_sql_query, schema)
            # display generated sql query
            st.subheader(f"generated sql query for (attempt - {attempt})")
            st.code(sql_query)
            df = dataframe_creation(sql_query)
            answer = make_answer(df, question)
            success = True
        except Exception as e:
            st.warning(f"attempt failed with error: {e}")
            time.sleep(1)
        if success:
            return df,answer
        else:
            st.error("failed to process request after 3 attempts")
            return None, None
with left_col:
    st.header("Ask a question")
    question=st.text_input("Enter your question","what are the names of employees in employee table?")
    if st.button("submit"):
        df,answer=retries(question)
        if df is not None and answer is not None:
            st.subheader("Answer")
            st.write(answer)
with right_col:
    st.header("Extracted data")
    if 'df' in locals() and df is not None:
        st.dataframe(df)



