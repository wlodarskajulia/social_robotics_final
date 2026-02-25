def parse_text(text: str) -> list[tuple[str, str]]:
    # list[tuple[label, text_to_say]]
    # labels = [TRIGGER1, ..., TRIGGER5, NO_TRIGGER]
    trigger_words = ["TRIGGER1", "TRIGGER2", "TRIGGER3", "TRIGGER4", "TRIGGER5"]
    indexed_text = []

    # Split the text into words
    words = text.split()
    current_segment = []
    current_label = "NO_TRIGGER"

    for word in words:
        if word in trigger_words:
            # If we have accumulated words, save them with the previous label
            if current_segment:
                indexed_text.append((current_label, " ".join(current_segment)))
                current_segment = []
            # Start new segment with the trigger label
            current_label = word
        else:
            current_segment.append(word)
    
    # Append the last segment
    if current_segment:
        indexed_text.append((current_label, " ".join(current_segment)))
    
    return indexed_text

text = "TRIGGER1 Hi my name is Julia! TRIGGER2 Could you specify what you mean? TRIGGER2 If not that bye"
print(parse_text(text))