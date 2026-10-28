from PIL import Image, ImageDraw, ImageFont

def make_matrix_image(title, row_labels, col_labels, values, filename):
    cell_w = 160
    cell_h = 70
    left_w = 190
    top_h = 120

    width = left_w + cell_w * len(col_labels)
    height = top_h + cell_h * len(row_labels) + 80

    img = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(img)

    try:
        title_font = ImageFont.truetype("arial.ttf", 28)
        header_font = ImageFont.truetype("arial.ttf", 20)
        cell_font = ImageFont.truetype("arial.ttf", 22)
        small_font = ImageFont.truetype("arial.ttf", 18)
    except:
        title_font = ImageFont.load_default()
        header_font = ImageFont.load_default()
        cell_font = ImageFont.load_default()
        small_font = ImageFont.load_default()

    draw.text((30, 25), title, fill="black", font=title_font)
    draw.text((left_w + 120, 80), "Predicted Class", fill="black", font=small_font)
    draw.text((20, top_h + 80), "Actual Class", fill="black", font=small_font)

    # Column headers
    for j, label in enumerate(col_labels):
        x = left_w + j * cell_w
        y = top_h - cell_h
        draw.rectangle([x, y, x + cell_w, y + cell_h], outline="black", fill="#f1f1f1")
        draw.text((x + 35, y + 22), label, fill="black", font=header_font)

    # Row headers and cells
    max_value = max(max(row) for row in values)

    for i, row_label in enumerate(row_labels):
        y = top_h + i * cell_h

        draw.rectangle([0, y, left_w, y + cell_h], outline="black", fill="#f1f1f1")
        draw.text((30, y + 22), row_label, fill="black", font=header_font)

        for j, value in enumerate(values[i]):
            x = left_w + j * cell_w

            if value == 0:
                fill = "#ffffff"
            elif value == max_value:
                fill = "#d9ead3"
            else:
                fill = "#fff2cc"

            draw.rectangle([x, y, x + cell_w, y + cell_h], outline="black", fill=fill)

            text = str(value)
            bbox = draw.textbbox((0, 0), text, font=cell_font)
            text_w = bbox[2] - bbox[0]
            text_h = bbox[3] - bbox[1]

            draw.text(
                (x + (cell_w - text_w) / 2, y + (cell_h - text_h) / 2),
                text,
                fill="black",
                font=cell_font
            )

    img.save(filename)
    print(f"Saved {filename}")


make_matrix_image(
    title="Incident Type Confusion Matrix",
    row_labels=["Medical", "Fire", "Crime"],
    col_labels=["Medical", "Fire", "Crime"],
    values=[
        [132, 0, 0],
        [0, 132, 0],
        [0, 0, 132]
    ],
    filename="incident_type_confusion_matrix.png"
)

make_matrix_image(
    title="Severity Confusion Matrix",
    row_labels=["Low", "High", "Critical"],
    col_labels=["Low", "High", "Critical"],
    values=[
        [131, 1, 0],
        [0, 132, 0],
        [0, 0, 132]
    ],
    filename="severity_confusion_matrix.png"
)