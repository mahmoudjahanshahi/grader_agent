# Assignment Grader Agent

## Azure Setup

1. Create a new resource group
2. Open Azure OpenAI and create a new OpenAI resource
3. Navigate to your OpenAI resource in Azure AI Foundry and go to Deployments tab
4. Deploy a GPT model (e.g. gpt-5-chat)

## Environment Setup

1. Navigate to settings tab in your repository
2. Under Secrets and variables, choose Codespaces
3. Add new repository secrets using the credentials from your Azure gpt model deployment page
4. Name you secrets. For gpt-5-chat example:
    - AZURE_OPENAI_ENDPOINT=https://res-oai-grader.openai.azure.com/
    - AZURE_OPENAI_API_KEY=<your-api-key>
    - AZURE_OPENAI_API_VERSION=2025-01-01-preview
    - AZURE_OPENAI_DEPLOYMENT=gpt-5-chat
5. Test your setup by running `python tests/00_openai.py` in the terminal.
