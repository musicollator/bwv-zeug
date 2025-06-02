import re
import sys
import os

def pad_all_words(text, pad_width=12):
    def pad_match(match):
        word = match.group(0).strip()          # remove any accidental spaces
        return word.ljust(pad_width)           # pad the cleaned word

    # This pattern matches only target words, not surrounding punctuation or spaces
    pattern = r"\b[a-z',]+\b\s*"
    return re.sub(pattern, pad_match, text)

def main():
    if len(sys.argv) != 2:
        print("Usage: python pad_all_words.py <input_file>")
        sys.exit(1)

    input_path = sys.argv[1]
    if not os.path.isfile(input_path):
        print(f"File not found: {input_path}")
        sys.exit(1)

    with open(input_path, "r", encoding="utf-8") as f:
        content = f.read()

    padded_content = pad_all_words(content)

    with open(input_path, "w", encoding="utf-8") as f:
        f.write(padded_content)

    print(f"File overwritten with padded content: {input_path}")

if __name__ == "__main__":
    main()
