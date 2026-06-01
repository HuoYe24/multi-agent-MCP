import re

with open("D:\\Desktop\\multi-agent-MCP\\project\\rag_agent\\nodes.py", "r", encoding="utf-8") as f:
    content = f.read()

# Remove old ecommerce imports
lines = content.split("\n")
new_lines = []
for line in lines:
    if "from ecommerce.compliance import" in line:
        continue
    if "from ecommerce.tickets import" in line:
        continue
    if "from ecommerce.tools import" in line:
        continue
    new_lines.append(line)
content = "\n".join(new_lines)

# Remove old MCP nodes block (from _format_order_response through compliance_agent)
start = content.find("def _format_order_response")
end = content.find("def summarize_history")
if start >= 0 and end >= 0:
    content = content[:start] + content[end:]

# Clean up extra blank lines
import re as re2
content = re2.sub(r"\n{3,}", "\n\n", content)

with open("D:\\Desktop\\multi-agent-MCP\\project\\rag_agent\\nodes.py", "w", encoding="utf-8") as f:
    f.write(content)

print("nodes.py cleaned")
