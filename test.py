import os

for entry in os.scandir("C:/"):
    print(entry.name, "<DIR>" if entry.is_dir() else "<FILE>")
