import json

with open("food-agent.ipynb") as f:
    nb = json.load(f)

for cell in nb["cells"]:
    if cell["cell_type"] == "code" and not cell["source"][0].startswith("!"):
        print("".join(cell["source"]))
        print("\n# ---\n")
