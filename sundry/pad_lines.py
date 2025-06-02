import sys

if len(sys.argv) != 2:
    print("Usage: python pad_lines.py <filename>")
    sys.exit(1)

filename = sys.argv[1]

try:
    with open(filename, "r", encoding="utf-8") as f:
        lines = f.readlines()

    with open(filename, "w", encoding="utf-8") as f:
        for line in lines:
            f.write(line.rstrip('\n').ljust(160) + '\n')

    print(f"Lines in '{filename}' have been right-padded to 160 characters.")
except Exception as e:
    print(f"Error: {e}")
    sys.exit(1)
