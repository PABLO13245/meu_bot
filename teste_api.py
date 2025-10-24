import os  
import requests  

API_TOKEN = os.getenv("SPORTMONKS_TOKEN")  

url = f"https://api.sportmonks.com/v3/football/fixtures?api_token={API_TOKEN}&include=league,season,participants"  

response = requests.get(url)  

print("Status:", response.status_code)  
print(response.text)
