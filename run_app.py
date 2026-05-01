import os
import webbrowser
import time
import threading

def run_streamlit():
    os.system("streamlit run app.py --server.headless true")

def open_browser():
    time.sleep(3)  # wait for server to start
    webbrowser.open("http://localhost:8501")

threading.Thread(target=run_streamlit).start()
threading.Thread(target=open_browser).start()