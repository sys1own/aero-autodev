import os

def compile_recipe(file_path, run=True):
    """Natively parses and verifies incoming text recipes to simulate local compilation gates"""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Target recipe file missing: {file_path}")
        
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
        
    # Standard environmental syntax gate: Ensure header definitions are valid
    if "[project]" not in content:
        raise SyntaxError("Compiler validation failure: Missing required [project] declaration header.")
        
    # Stack machine syntax verification pass
    lines = content.split("\n")
    for line in lines:
        if "op =" in line and not any(x in line for x in ["print", "call"]):
            raise ValueError(f"AeroVM Tokenizer Fault: Unsupported operational primitive detected on line: {line}")
            
    return True
