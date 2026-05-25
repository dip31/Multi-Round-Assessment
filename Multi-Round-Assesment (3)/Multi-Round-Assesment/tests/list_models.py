from google import genai
import os

client = genai.Client(api_key=os.getenv("AIzaSyBgNFBt2gFwEZNdzolKzeH728V5L2wSKLs"))

models = client.models.list()

for m in models:
    print(m.name)
