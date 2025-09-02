# LangGraphPOC
Analyst Agent: pulls margin anomalies and summarizes risk. Finance Agent: decides to escalate and opens a ticket if loss > threshold.

Ask it to investigate; it calls fetch_margin_anomalies.
If loss > 500, the Finance agent raises a ticket, then ends with FINAL.
If you tweak min_loss or DATA, you’ll see different behaviors.
Optional: wire to ClickHouse later

Replace fetch_margin_anomalies with a real ClickHouse query (clickhouse-connect) and compute losses in SQL.
Swap raise_ticket with a Power Automate HTTP action or Teams/Planner API call.

When you use it, please add the open ai api key or use openrouter one. 
ChatOpenAI(api_key="sk-or-v1-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",base_url="https://openrouter.ai/api/v1")
