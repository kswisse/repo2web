"""Simple Streamlit application for testing."""
import streamlit as st

st.title("Hello World")
st.write("Welcome to Streamlit!")

if st.button("Click me"):
    st.success("Button clicked!")
