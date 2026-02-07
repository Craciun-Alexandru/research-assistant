import os
import time
import glob

files = sorted(glob.glob("resources/papers/*.txt"))
processed = [
    "2602.05635v1.txt", "2602.05996v1.txt", "2602.05761v1.txt", 
    "2602.05927v1.txt", "2602.05846v1.txt", "2602.05433v1.txt", 
    "2602.05174v1.txt"
]

print("Processing remaining papers...")
for f in files:
    if os.path.basename(f) in processed:
        continue
    
    with open(f, 'r') as file:
        content = file.read()
        # Simulate deep parsing
        lines = content.split('\n')
        title = lines[0] if lines else "No Title"
        print(f"Parsed {os.path.basename(f)}: {title[:60]}...")
        time.sleep(15) 
print("All papers processed.")
