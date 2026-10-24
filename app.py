from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pandas as pd
import plotly.express as px
import requests
import streamlit as st

ROOT = Path(__file__).parent
SAMPLE_FILE = ROOT / "data" / "sample_biogas_operations.csv"
OLLAMA_URL = "http://localhost:11434"
DEFAULT_MODEL = "qwen2.5:3b"

st.set_page_config(page_title="Offline AI Dashboard Agent", page_icon="📊", layout="wide")


def ollama_models() -> list[str]:
    try:
        response = requests.get(f"{OLLAMA_URL}/api/tags", timeout=1.5)
        response.raise_for_status()
        return [item.get("name", "") for item in response.json().get("models", [])]
    except (requests.RequestException, ValueError):
        return []


def schema_summary(df: pd.DataFrame) -> dict[str, Any]:
    numeric = df.select_dtypes(include="number").columns.tolist()
    dates = [c for c in df.columns if pd.api.types.is_datetime64_any_dtype(df[c])]
    categorical = [c for c in df.columns if c not in numeric and c not in dates]
    return {
        "rows": len(df), "columns": list(df.columns), "numeric": numeric,
        "dates": dates, "categorical": categorical,
        "examples": {c: [str(v)[:80] for v in df[c].dropna().head(3).tolist()] for c in df.columns},
    }


def choose_column(columns: list[str], words: tuple[str, ...], default: str | None = None) -> str | None:
    for col in columns:
        if any(word in col.lower().replace("_", " ") for word in words):
            return col
    return default


def default_command(schema: dict[str, Any]) -> str:
    nums, cats, dates = schema["numeric"], schema["categorical"], schema["dates"]
    metric = choose_column(nums, ("sales", "revenue", "profit", "income", "wines", "meat", "purchases", "output", "production", "quantity", "amount"))
    if metric is None:
        metric = next((c for c in nums if not re.search(r"\b(id|year|code|zip)\b", c.lower().replace("_", " "))), nums[0] if nums else None)
    group = choose_column(cats, ("region", "education", "product", "category", "country", "customer"), cats[0] if cats else None)
    if metric and group:
        aggregation = "average" if "income" in metric.lower() else "total"
        return f"Compare {aggregation} {metric} by {group}"
    if metric:
        return f"Show the monthly {metric} trend" if dates else f"Show {metric}"
    return "Explore this dataset"


def rule_plan(command: str, schema: dict[str, Any]) -> dict[str, Any]:
    """Plan a view; all values are calculated from the actual dataframe."""
    lower = command.lower()
    nums, cats, dates = schema["numeric"], schema["categorical"], schema["dates"]
    safe_nums = [c for c in nums if not re.search(r"\b(id|year|code|zip)\b", c.lower().replace("_", " "))]
    metric = choose_column(nums, ("profit", "revenue", "sales", "income", "wine", "meat", "fruit", "fish", "sweet", "gold", "output", "production", "cost", "expense", "quantity", "amount"), safe_nums[0] if safe_nums else (nums[0] if nums else None))
    for words in (("cost", "expense"), ("profit", "margin"), ("sales", "revenue"), ("income",), ("wine",), ("meat",), ("fruit",), ("fish",), ("sweet",), ("gold",), ("production", "output", "manure", "gas")):
        if any(w in lower for w in words):
            metric = choose_column(nums, words, metric)
    if any(w in lower for w in ("average", "avg", "mean")):
        aggregation = "mean"
    elif any(w in lower for w in ("count", "number of", "how many")):
        aggregation = "count"
    else:
        aggregation = "sum"
    if any(w in lower for w in ("month", "monthly", "trend", "over time", "daily", "weekly")) and dates:
        group, period = dates[0], "month" if any(w in lower for w in ("month", "monthly")) else "day"
        chart = "line"
    elif cats:
        group = choose_column(cats, ("region", "education", "product", "category", "shift", "plant", "country", "customer"), cats[0])
        period, chart = None, "bar"
    else:
        group, period, chart = None, None, "bar"
    title = f"{aggregation.title()} of {metric or 'records'}" + (f" by {group}" if group else "")
    return {"title": title, "metric": metric, "aggregation": aggregation, "group_by": group, "period": period, "chart": chart}


def ai_plan(command: str, schema: dict[str, Any], model: str) -> dict[str, Any] | None:
    prompt = {
        "command": command,
        "schema": {k: schema[k] for k in ("columns", "numeric", "dates", "categorical", "examples")},
        "required_output": {"title": "string", "metric": "existing column or null", "aggregation": "sum|mean|count", "group_by": "existing column or null", "period": "day|month|null", "chart": "bar|line|pie|scatter"},
    }
    system = ("You plan charts for a local dashboard. Return one JSON object only. Choose column names exactly from the schema. "
              "Never invent or calculate data. Use only sum, mean, count and day or month.")
    try:
        response = requests.post(f"{OLLAMA_URL}/api/chat", json={
            "model": model, "stream": False, "format": "json",
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": json.dumps(prompt, ensure_ascii=False)}],
            "options": {"temperature": 0},
        }, timeout=90)
        response.raise_for_status()
        return json.loads(response.json()["message"]["content"])
    except (requests.RequestException, ValueError, KeyError, TypeError):
        return None


def validate_plan(plan: dict[str, Any], df: pd.DataFrame, command: str = "") -> dict[str, Any]:
    numeric = df.select_dtypes(include="number").columns.tolist()
    dates = [c for c in df.columns if pd.api.types.is_datetime64_any_dtype(df[c])]
    categorical = [c for c in df.columns if c not in numeric and c not in dates]
    p = {k: plan.get(k) for k in ("title", "metric", "aggregation", "group_by", "period", "chart")}
    if p["metric"] not in df.columns and p["aggregation"] != "count":
        p["metric"] = numeric[0] if numeric else None
    if p["group_by"] not in df.columns:
        p["group_by"] = None
    p["aggregation"] = p["aggregation"] if p["aggregation"] in ("sum", "mean", "count") else "sum"
    p["chart"] = p["chart"] if p["chart"] in ("bar", "line", "pie", "scatter") else "bar"
    p["period"] = p["period"] if p["period"] in ("day", "month") else None
    if p["period"] and p["group_by"] not in dates:
        p["period"] = None
    # Cross-check clear time-series requests. A fluent AI title must not turn a
    # regional comparison into a claimed monthly trend.
    if dates and re.search(r"\b(month|monthly|week|weekly|day|daily|trend|over time)\b", command, re.I):
        p["group_by"] = dates[0]
        p["period"] = "month" if re.search(r"\b(month|monthly)\b", command, re.I) else "day"
        p["chart"] = "line"
    if re.search(r"\b(average|avg|mean)\b", command, re.I):
        p["aggregation"] = "mean"
    elif re.search(r"\b(count|number of|how many)\b", command, re.I):
        p["aggregation"] = "count"
    metric_hints = (
        (("income",), ("income",)),
        (("sales", "revenue"), ("sales", "revenue")),
        (("profit", "margin"), ("profit", "margin")),
        (("cost", "expense"), ("cost", "expense")),
        (("wine",), ("wine",)),
        (("meat",), ("meat",)),
        (("fruit",), ("fruit",)),
        (("fish",), ("fish",)),
        (("sweet",), ("sweet",)),
        (("gold",), ("gold",)),
        (("production", "output"), ("production", "output", "manure", "gas")),
    )
    for cues, column_terms in metric_hints:
        if any(re.search(rf"\b{re.escape(cue)}\b", command, re.I) for cue in cues):
            match = choose_column(numeric, column_terms)
            if match:
                p["metric"] = match
            break
    for cue in ("region", "education", "country", "product", "category", "marital"):
        if re.search(rf"\b{cue}\b", command, re.I):
            match = choose_column(categorical, (cue,))
            if match:
                p["group_by"] = match
            break
    p["title"] = str(p["title"] or "Dashboard view")[:120]
    if p["aggregation"] != "count" and p["metric"] not in numeric:
        p["metric"] = numeric[0] if numeric else None
    if p["group_by"] in dates and p["period"]:
        period_label = {"month": "Monthly", "day": "Daily"}.get(p["period"], p["period"].title())
        p["title"] = f"{period_label} trend of {p['metric']}"
    return p


def aggregate_data(df: pd.DataFrame, plan: dict[str, Any]) -> tuple[pd.DataFrame, str]:
    group, metric, agg = plan.get("group_by"), plan.get("metric"), plan["aggregation"]
    if agg != "count" and (metric is None or metric not in df.select_dtypes(include="number").columns):
        raise ValueError("The selected metric is not numeric in this dataset.")
    work = df.copy()
    if group and plan.get("period"):
        work[group] = pd.to_datetime(work[group], errors="coerce")
        work = work.dropna(subset=[group])
        work["__dashboard_group"] = work[group].dt.to_period("M").dt.to_timestamp() if plan["period"] == "month" else work[group].dt.date
        group = "__dashboard_group"
    if group:
        if agg == "count":
            output, value = work.groupby(group, dropna=False).size().rename("Record count").reset_index(), "Record count"
        else:
            output, value = work.groupby(group, dropna=False)[metric].agg(agg).reset_index(), metric
        return output.sort_values(group, kind="stable"), value
    if agg == "count":
        return pd.DataFrame({"Measure": ["All records"], "Record count": [len(work)]}), "Record count"
    return pd.DataFrame({"Measure": [f"{agg.title()} of {metric}"], metric: [work[metric].agg(agg)]}), metric


def read_upload(uploaded, local_path: str = "") -> pd.DataFrame:
    if uploaded is None and local_path.strip():
        source = Path(local_path.strip()).expanduser()
        if not source.is_file():
            raise FileNotFoundError(f"File not found: {source}")
        if source.suffix.lower() in (".xlsx", ".xls"):
            frame = pd.read_excel(source)
        elif source.suffix.lower() == ".csv":
            frame = pd.read_csv(source)
        else:
            raise ValueError("Choose a CSV, XLSX, or XLS file.")
    elif uploaded is None:
        return pd.read_csv(SAMPLE_FILE, parse_dates=["Date"])
    elif uploaded.name.lower().endswith((".xlsx", ".xls")):
        frame = pd.read_excel(uploaded)
    else:
        frame = pd.read_csv(uploaded)
    for col in frame.columns:
        if re.search(r"date|time", str(col), re.I):
            frame[col] = pd.to_datetime(frame[col], errors="coerce", format="mixed", dayfirst=True)
            continue
        if re.search(r"\b(id|code|zip|postal)\b", str(col), re.I):
            continue
        values = frame[col].astype("string").str.strip()
        numeric_values = pd.to_numeric(values.str.replace(r"[$₹€£,\s]", "", regex=True), errors="coerce")
        nonempty = values.notna() & values.ne("")
        if nonempty.any() and numeric_values[nonempty].notna().mean() >= 0.9:
            frame[col] = numeric_values
    return frame


st.title("📊 Offline AI Dashboard Agent")
st.caption("Describe the view you need. Your data stays on this PC; Ollama is optional and local.")
models = ollama_models()
with st.sidebar:
    st.header("Data and local AI")
    upload = st.file_uploader("Use your own CSV or Excel file", type=["csv", "xlsx", "xls"])
    local_path = st.text_input("Or enter a local file path", placeholder=r"C:\Data\marketing_data.csv", help="The dashboard reads this file directly from this PC; it does not copy it.")
    st.caption("Or leave both inputs empty to use the included sample data.")
    if models:
        default_idx = next((i for i, name in enumerate(models) if name.startswith(DEFAULT_MODEL)), 0)
        model = st.selectbox("Ollama model", models, index=default_idx)
        st.success("Ollama is available on this computer.")
    else:
        model = DEFAULT_MODEL
        st.warning("Ollama is unavailable. Rule-based planning is active; charts still work.")
    st.divider()
    st.markdown("**Local-first behavior**\n\n- Calculations run in Python.\n- No GPT API key or cloud AI is used.\n- Ollama receives the command and column details through its local API.")

try:
    data = read_upload(upload, local_path)
except Exception as exc:
    st.error(f"Could not read this file: {exc}")
    st.stop()
data = data.dropna(how="all")
if upload is None and not local_path.strip():
    st.info("Sample biogas figures are illustrative demo data only, not plant measurements or profitability estimates.")
schema = schema_summary(data)
missing_by_column = data.isna().sum()
missing_by_column = missing_by_column[missing_by_column > 0]
if not missing_by_column.empty:
    missing_total = int(missing_by_column.sum())
    st.warning(f"This dataset has {missing_total:,} missing cells across {len(missing_by_column)} column(s). Aggregations skip missing numeric values; inspect the source data before relying on results.")
source_name = upload.name if upload else local_path.strip() if local_path.strip() else SAMPLE_FILE.name
dataset_signature = (source_name, len(data), tuple(data.columns))
if st.session_state.get("dataset_signature") != dataset_signature:
    st.session_state.dataset_signature = dataset_signature
    st.session_state.command_text = default_command(schema)
    st.session_state.pop("dashboard_plan", None)
    st.session_state.pop("dashboard_mode", None)
if data.empty:
    st.warning("This dataset has no rows yet.")
    st.stop()
if not schema["numeric"]:
    st.error("This dataset has no numeric columns to chart. Add a numeric measure, such as sales or quantity.")
    st.dataframe(data.head(20), width="stretch")
    st.stop()

if schema["dates"]:
    date_col = schema["dates"][0]
    parsed = pd.to_datetime(data[date_col], errors="coerce").dropna()
    if not parsed.empty:
        with st.sidebar:
            selected_dates = st.date_input("Date range", value=(parsed.min().date(), parsed.max().date()), min_value=parsed.min().date(), max_value=parsed.max().date())
        if isinstance(selected_dates, (tuple, list)) and len(selected_dates) == 2:
            valid_dates = pd.to_datetime(data[date_col], errors="coerce").dt.date
            data = data.loc[valid_dates.between(*selected_dates)].copy()

st.subheader("Ask for a dashboard")
command = st.text_input("Your command", key="command_text", placeholder="e.g., Show total sales by region")
make = st.button("Generate dashboard", type="primary")
if make:
    if models:
        with st.spinner("Planning with Ollama locally. The first CPU-only response may take a little while…"):
            candidate = ai_plan(command, schema, model)
    else:
        candidate = None
    st.session_state.dashboard_plan = validate_plan(candidate or rule_plan(command, schema), data, command)
    st.session_state.dashboard_mode = "Ollama local model" if candidate else "Rule-based fallback"
elif "dashboard_plan" not in st.session_state:
    st.session_state.dashboard_plan = validate_plan(rule_plan(command, schema), data, command)
    st.session_state.dashboard_mode = "Rule-based fallback"
plan = validate_plan(st.session_state.dashboard_plan, data, command)
st.markdown(f"### {plan['title']}")
st.caption(f"Plan source: **{st.session_state.dashboard_mode}** · Values are calculated from the current dataset in Python. Check the selected metric and source rows before relying on conclusions.")

filter_col = next((c for c in schema["categorical"] if c != plan.get("group_by") and data[c].nunique(dropna=True) <= 30), None)
if filter_col:
    choices = sorted(data[filter_col].dropna().astype(str).unique().tolist())
    selected = st.multiselect(f"Filter {filter_col}", choices, default=choices, key=f"filter_{filter_col}")
    data = data[data[filter_col].astype(str).isin(selected)]
try:
    chart_data, value_col = aggregate_data(data, plan)
except ValueError as exc:
    st.error(str(exc))
    st.stop()

if plan["aggregation"] == "mean" and plan.get("metric"):
    metric_value = pd.to_numeric(data[plan["metric"]], errors="coerce").mean()
elif plan["aggregation"] == "count":
    metric_value = len(data)
else:
    metric_value = pd.to_numeric(chart_data[value_col], errors="coerce").sum()
c1, c2, c3 = st.columns(3)
c1.metric("Rows in view", f"{len(data):,}")
c2.metric(f"{plan['aggregation'].title()} · {value_col}", f"{metric_value:,.2f}")
c3.metric("Data columns", f"{len(data.columns)}")
if plan.get("group_by"):
    x_col = "__dashboard_group" if "__dashboard_group" in chart_data.columns else plan["group_by"]
    chart = plan["chart"]
    if chart == "pie":
        fig = px.pie(chart_data, names=x_col, values=value_col, title=plan["title"])
    elif chart == "scatter":
        fig = px.scatter(chart_data, x=x_col, y=value_col, title=plan["title"], labels={x_col: plan["group_by"], value_col: value_col})
    elif chart == "line":
        fig = px.line(chart_data, x=x_col, y=value_col, markers=True, title=plan["title"], labels={x_col: plan["group_by"], value_col: value_col})
    else:
        fig = px.bar(chart_data, x=x_col, y=value_col, title=plan["title"], labels={x_col: plan["group_by"], value_col: value_col})
    st.plotly_chart(fig, width="stretch")
else:
    st.info("This command produces a single summary. Add ‘by region’ or ‘monthly trend’ to create a comparison chart.")

with st.expander("Inspect the calculation and source rows"):
    data_source = upload.name if upload else Path(local_path).name if local_path.strip() else SAMPLE_FILE.name
    st.write({"aggregation": plan["aggregation"], "metric": plan.get("metric"), "group_by": plan.get("group_by"), "rows_used": len(data), "file": data_source})
    st.dataframe(chart_data, width="stretch")
    st.dataframe(data.head(100), width="stretch")

