import json

with open("food-agent.ipynb") as f:
    nb = json.load(f)

for cell in nb["cells"]:
    if cell["cell_type"] == "code":
        modified_source = []
        for line in cell["source"]:
            if line.startswith("!"):
                continue
            modified_source.append(line)
        print("".join(modified_source))
        print("\n# ---\n")
