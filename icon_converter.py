from PIL import Image
import os

# Caminho para o arquivo PNG
png_file = "resources\\app.png"
# Caminho para o arquivo ICO de saída
ico_file = "resources\\app.ico"

# Converter PNG para ICO
img = Image.open(png_file)
img.save(ico_file)