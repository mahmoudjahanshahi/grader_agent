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

## Repository Layout

```

grader_agent/
├── agents/
│   ├── a1_cleaner.py      # Cleans raw student text
│   ├── a2_alignment.py    # Aligns cleaned text to requirements
│   ├── a3_grader.py       # Grades against rubric
│   ├── a4_feedback.py     # Generates qualitative feedback
│   └── a5_reporter.py     # Summarizes output for delivery
├── tests/                 # Unit + integration tests
├── main.py                # Entry point for grading runs
└── requirements.txt

```

## Assignment Folder Structure

Each assignment folder must contain:

```

instructions.txt    # Natural language assignment description
rubric.json         # Grading rubric with criteria + max scores
submissions/        # One .txt or .md file per student

```

Example:

```

example/
├── instructions.txt
├── rubric.json
└── submissions/
├── student1.txt
└── student2.md
└── student3.txt

````

## Running the Grader

From the project root:

```bash
python main.py \
  --dir example \
  --mode csv \
  --grading-mode realistic \
  --tone encouraging \
````

### CLI Options

* `--dir` (required): Path to assignment folder
* `--mode`: `csv` (default) to write results to a file, or `canvas` to post directly via Canvas API (canvas mode is not developed/tested yet!)
* `--grading-mode`: `forgiving` (default), `realistic`, or `strict`
* `--tone`: Feedback tone for comments (`encouraging` (default), `neutral`, `formal`, `critical`)

## Output

* **CSV Mode**: Produces a CSV with columns `student_id, grade, comment`
* **Canvas Mode**: Posts grades and feedback comments directly to Canvas (canvas mode is not developed/tested yet!)
* **Artifacts**: For debugging, intermediate agent outputs (`a2`, `a3`, `a4`) are saved in `outputs/`
