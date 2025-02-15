from flask import Flask, render_template, request, jsonify
from transformers import pipeline
import json
import hashlib
import os
import re
from langchain.prompts import PromptTemplate

app = Flask(__name__)

# Load the AI model
generator = pipeline("text-generation", model="gpt2")  # Use GPT-2 as a placeholder
print("Generator loaded successfully.")

# JSON File for storing reports
REPORTS_FILE = "investment_reports.json"

# Function to generate a unique hash for the report
def generate_report_id(report_text):
    return hashlib.sha256(report_text.encode()).hexdigest()

# Function to save report to JSON file
def save_report(report_data):
    try:
        # Load existing reports if file exists
        if os.path.exists(REPORTS_FILE):
            with open(REPORTS_FILE, "r") as f:
                reports = json.load(f)
        else:
            reports = {}

        # Add new report
        report_id = report_data["report_id"]
        reports[report_id] = report_data

        # Save back to file
        with open(REPORTS_FILE, "w") as f:
            json.dump(reports, f, indent=4)

        print(f"Report saved successfully with ID: {report_id}")
    except Exception as e:
        print(f"Error saving report: {e}")
        raise

# Function to load past reports
def load_reports():
    try:
        if os.path.exists(REPORTS_FILE):
            with open(REPORTS_FILE, "r") as f:
                return json.load(f)
        return {}
    except Exception as e:
        print(f"Error loading reports: {e}")
        return {}

# Dynamic prompt based on client risk tolerance
def get_portfolio_summary_prompt(client_profile):
    risk_tolerance = client_profile.get("risk_tolerance", "moderate")
    
    if risk_tolerance == "conservative":
        risk_note = "Given the client's conservative risk tolerance, the focus is on capital preservation and low-risk investments."
    elif risk_tolerance == "aggressive":
        risk_note = "Given the client's aggressive risk tolerance, the focus is on high-growth investments with higher risk."
    else:
        risk_note = "Given the client's moderate risk tolerance, the portfolio is balanced between growth and stability."

    return PromptTemplate(
        input_variables=[
            "portfolio_name", "client_profile", "benchmark", "asset_allocation",
            "return_net", "return_benchmark", "risk_metrics", "top_holdings",
            "underperforming_holdings", "date_range"
        ],
        template=f"""
Provide a detailed portfolio performance summary for {{date_range}}.

Portfolio Name: {{portfolio_name}}
Client Profile: {{client_profile}}
Benchmark: {{benchmark}}
Asset Allocation: {{asset_allocation}}
Net Return: {{return_net}} (Benchmark Return: {{return_benchmark}})
Risk Metrics: {{risk_metrics}}
Top Holdings: {{top_holdings}}
Underperforming Holdings: {{underperforming_holdings}}

{risk_note}

Instructions:
- Clearly state how the portfolio performed relative to the benchmark.
- Identify key risk metrics and their impact on performance.
- Summarize the top-performing and underperforming assets.
- Provide a professional financial report summary.
"""
    )

# Define the client insights prompt
client_insights_prompt = PromptTemplate(
    input_variables=["client_profile", "portfolio_summary", "risk_metrics", "market_outlook"],
    template="""
Client Profile: {client_profile}
Portfolio Summary: {portfolio_summary}
Risk Metrics: {risk_metrics}
Market Outlook: {market_outlook}

Instructions:
- Analyze the client's profile and portfolio performance.
- Provide insights tailored to the client's risk tolerance and investment goals.
- Highlight any significant risks or opportunities based on the market outlook.
- Avoid repeating information from the portfolio summary.
"""
)

# Define the recommendations prompt
recommendations_prompt = PromptTemplate(
    input_variables=["client_profile", "portfolio_summary", "risk_metrics", "market_outlook"],
    template="""
Client Profile: {client_profile}
Portfolio Summary: {portfolio_summary}
Risk Metrics: {risk_metrics}
Market Outlook: {market_outlook}

Instructions:
- Provide actionable recommendations based on the client's profile and portfolio performance.
- Suggest adjustments to the portfolio if necessary.
- Include a forward-looking outlook based on the market conditions.
- Be specific and avoid generic advice.
"""
)

# Compliance disclosures based on regulations
def get_disclosures_prompt(region):
    if region == "US":
        compliance_note = "This report complies with SEC regulations, including disclosures on risk and performance."
    elif region == "EU":
        compliance_note = "This report complies with MiFID II regulations, including disclosures on costs, risks, and performance."
    else:
        compliance_note = "This report includes standard risk and performance disclosures."

    return PromptTemplate(
        input_variables=["client_profile", "investment_products", "risk_metrics"],
        template=f"""
Client Profile: {{client_profile}}
Investment Products: {{investment_products}}
Risk Metrics: {{risk_metrics}}

Instructions:
1. Provide standard risk disclosures. Be specific about the risks, including those related to the risk metrics.
2. {compliance_note}
3. Avoid including outdated or irrelevant information.
"""
    )

# --- Flask Routes ---

@app.route("/", methods=["GET", "POST"])
def index():
    report = None
    report_id = None

    if request.method == "POST":
        try:
            data = request.form
            input_data = {
                "portfolio_name": data.get("portfolio_name"),
                "client_profile": {
                    "name": data.get("client_name"),
                    "risk_tolerance": data.get("risk_tolerance", "moderate"),
                    "investment_goals": data.get("investment_goals"),
                },
                "benchmark": data.get("benchmark"),
                "asset_allocation": data.get("asset_allocation"),
                "return_net": data.get("return_net"),
                "return_benchmark": data.get("return_benchmark"),
                "risk_metrics": data.get("risk_metrics"),
                "top_holdings": data.get("top_holdings"),
                "underperforming_holdings": data.get("underperforming_holdings"),
                "investment_products": data.get("investment_products"),
                "market_outlook": data.get("market_outlook"),
                "date_range": data.get("date_range"),
                "region": data.get("region", "US")  # Default to US for compliance
            }

            # Debugging: Print input data
            print("Input Data:", input_data)

            # Validate required fields
            if not all([input_data["portfolio_name"], input_data["client_profile"]["name"], input_data["date_range"]]):
                raise ValueError("Missing required fields: portfolio_name, client_name, or date_range.")

            # Generate portfolio summary with dynamic prompt
            portfolio_summary_prompt = get_portfolio_summary_prompt(input_data["client_profile"])
            portfolio_summary_text = generator(portfolio_summary_prompt.format(**input_data), max_length=1000)[0]['generated_text']

            # Extract portfolio summary
            match = re.search(r"(.*)(Instructions:|1\.|[A-Z][a-z]+\s*:)", portfolio_summary_text, re.DOTALL)
            portfolio_summary = match.group(1).strip() if match else portfolio_summary_text.strip()

            input_data["portfolio_summary"] = portfolio_summary

            # Generate client insights
            client_insights = generator(client_insights_prompt.format(**input_data), max_length=1000)[0]['generated_text']

            # Generate recommendations
            recommendations = generator(recommendations_prompt.format(**input_data), max_length=1000)[0]['generated_text']

            # Generate compliance disclosures with region-specific prompt
            disclosures_prompt = get_disclosures_prompt(input_data["region"])
            disclosures = generator(disclosures_prompt.format(**input_data), max_length=1000)[0]['generated_text']

            # Combine report sections
            report_text = f"{portfolio_summary}\n{client_insights}\n{recommendations}\n{disclosures}"
            report_id = generate_report_id(report_text)

            # Save report
            report_data = {
                "report_id": report_id,
                "portfolio_summary": portfolio_summary,
                "client_insights": client_insights,
                "recommendations": recommendations,
                "disclosures": disclosures,
                "input_data": input_data
            }
            save_report(report_data)

            # Format report for display
            report = f"""
            <h2>Investment Report - {input_data['portfolio_name']} - {input_data['date_range']}</h2>
            <h3>Report ID: {report_id}</h3>
            <h3>Portfolio Performance Summary</h3>
            <pre>{portfolio_summary}</pre>
            <h3>Client-Specific Insights</h3>
            <pre>{client_insights}</pre>
            <h3>Recommendations and Outlook</h3>
            <pre>{recommendations}</pre>
            <h3>Compliance Disclosures</h3>
            <pre>{disclosures}</pre>
            """
        except Exception as e:
            report = f"<p style='color:red;'>Error generating report: {e}</p>"

    return render_template("index.html", report=report, report_id=report_id)

# --- Run the App ---

if __name__ == "__main__":
    app.run(debug=True)