def parse_text(text: str, max_meanigful_length: int = 12) -> list[tuple[str, str]]:
    # list[tuple[label, text_to_say]]
    # labels = [TRIGGER1, ..., TRIGGER5, NO_TRIGGER]
    # In the text, the trigger has to be in front of the statement that we want to trigger
    # e.g. "TRIGGER1 Hi my name is Julia! TRIGGER2 Could you specify that? TRIGGER2 If not that bye"

    trigger_words = ["NOD", "SHAKE", "THINK", "POINT", "WAVE"]
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
    
    final_text = []
    for label, segment in indexed_text:
        if label in trigger_words:
            # split that text into first group of 12 and then rest
            # the first group is still with trigger word, but the other is with NO_TRIGGER
            segment_words = segment.split()
            if len(segment_words) >= max_meanigful_length:
                final_text.append((label, " ".join(segment_words[:12])))
                final_text.append(("NO_TRIGGER", " ".join(segment_words[12:])))
            else:
                final_text.append((label, segment))
        else:
            final_text.append((label, segment))
    
    return final_text

text = "WAVE Hello I am Julia NO_TRIGGER I am td dh dh dhdgd bdhdg djddjdg djdjd dhdh dhdhd dhdh dhdd dhdh dhd hdhhd dhdhdh dhdhd POINT I am td dh dh dhdgd bdhdg djddjdg djdjd dhdh dhdhd dhdh dhdd dhdh dhd hdhhd dhdhdh dhdhd dgdgdg dgdgdgd dgdgdg"
print(parse_text(text))