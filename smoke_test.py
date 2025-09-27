import os
from openai import AzureOpenAI

client = AzureOpenAI(
    api_key=os.environ["AZURE_OPENAI_API_KEY"],
    api_version=os.environ["AZURE_OPENAI_API_VERSION"],
    azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
)

resp = client.chat.completions.create(
    model=os.environ["AZURE_OPENAI_DEPLOYMENT"],
    messages=[
        {"role":"system","content":"You are a test agent."},
        {"role":"user","content":"Reply exactly with READY"}
    ],
    temperature=0
)

if len(resp.choices[0].message.content) > 0:
    print("The OpenAI setup is", resp.choices[0].message.content)
else:
    print("Your setup is not working as intended!")
