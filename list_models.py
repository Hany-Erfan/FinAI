from google import genai
client = genai.Client()
for model in client.models.list():
    if "flash" in model.name:
        print(model.name)
