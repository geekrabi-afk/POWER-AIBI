# Offline AI Dashboard Agent

A local Windows dashboard that turns a plain-language request into a chart plan. Python performs every displayed calculation against the selected dataset. Ollama is optional and local; if it is missing, a rule-based planner keeps the dashboard working.

## First run

1. Run `setup_windows.bat` once while connected to the internet. It creates a project-local `.venv` and installs the dashboard packages.
2. Run `pull_model.bat` to download Qwen2.5 3B into Ollama. The model download is several gigabytes; Ollama must be installed and running.
3. Run `run_dashboard.bat`. The dashboard opens in your browser at a local address.

If the model is absent or Ollama is stopped, the dashboard remains usable with the rule-based planner. There is no GPT API key, and no application data is sent to a cloud service.

## Use it

- Try the included sample biogas operations dataset, or upload a CSV/Excel workbook.
- You can also enter an absolute local file path in the sidebar to read the file directly without copying it into this project.
- Describe a view, for example: “Compare daily sales by region” or “Show the monthly manure production trend.”
- Check the selected columns and calculations under “Inspect the calculation and source rows.”
- The sample figures are illustrative only; replace them with verified operating data before making decisions.

## GitHub demonstration

The repository includes a small synthetic biogas dataset so the dashboard can be previewed without private data. Keep your own CSV and Excel files outside the repository. The Git ignore rules exclude spreadsheet files, marketing CSVs, and all files in `data/` except the synthetic starter dataset.

This is a Windows desktop demonstration. GitHub hosts the source code; it does not run the local Ollama model. To run the app, clone the repository to a Windows PC and follow **First run** above.

## Privacy and limitations

The local model receives the command and column names/sample values to plan a view. It does not receive file contents through an external service. Aggregations run locally in pandas. The current version handles a single flat CSV or the first sheet of an Excel file; database connections, scheduled refresh, saved dashboards, alerts, and forecasting are later extensions.

## Hardware

Qwen2.5 3B is the starting model configured for the requested 16 GB RAM Windows PC without an NVIDIA GPU. Local inference speed depends on CPU and memory bandwidth. Model download and Python package installation need internet once; the dashboard itself is local.

