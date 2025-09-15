from PIL import Image
import os

# Caminho para o arquivo PNG
png_file = ["launcher\\matrix\\resources\\chatbot_ai.png"
            ,"launcher\\matrix\\resources\\data_ai.png"
            ,"launcher\\matrix\\resources\\task_ai.png"]
ico_file = ["launcher\\matrix\\resources\\chatbot_ai.ico",
            "launcher\\matrix\\resources\\data_ai.ico",
            "launcher\\matrix\\resources\\task_ai.ico"]

for i in range(len(png_file)):
    if not os.path.exists(png_file[i]):
        print(f"Arquivo {png_file[i]} não encontrado.")
        continue
    img = Image.open(png_file[i])
    img.save(ico_file[i])