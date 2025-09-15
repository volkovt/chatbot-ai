import os, math, logging
from PIL import Image, ImageDraw

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("icon-gen")

W, H = 512, 512
BG = (12, 12, 18, 0)  # fundo transparente
C1 = (255, 64, 129)   # #FF4081
C2 = (124, 77, 255)   # #7C4DFF

def lerp(a, b, t): return int(a + (b - a) * t)

def grad(i, n):
    t = i / max(1, n - 1)
    return (lerp(C1[0], C2[0], t), lerp(C1[1], C2[1], t), lerp(C1[2], C2[2], t))

def main(out_path="resources/launcher.ico"):
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    base = Image.new("RGBA", (W, H), BG)
    d = ImageDraw.Draw(base)

    # Disco e arco “spinner” (dialogo visual com o launcher)
    cx, cy = W // 2, H // 2
    r_outer, r_inner = 200, 168
    segs = 90
    for i in range(segs):
        a0 = math.radians(30 + i * 2.8)   # “gap” moderno
        a1 = a0 + math.radians(2.4)
        color = grad(i, segs)
        for rr in range(r_inner, r_outer, 2):
            x0 = cx + int(rr * math.cos(a0)); y0 = cy + int(rr * math.sin(a0))
            x1 = cx + int(rr * math.cos(a1)); y1 = cy + int(rr * math.sin(a1))
            d.line([(x0, y0), (x1, y1)], fill=color, width=2)

    # Glow central
    for rad, alpha in [(120, 50), (90, 90), (60, 110)]:
        d.ellipse((cx-rad, cy-rad, cx+rad, cy+rad), fill=(124, 77, 255, alpha))

    # Exporta ICO com multiplos tamanhos
    sizes = [(256,256),(128,128),(64,64),(48,48),(32,32),(24,24),(16,16)]
    imgs = [base.resize(s) for s in sizes]
    imgs[0].save(out_path, format="ICO", sizes=sizes)
    logger.info(f"[icon-gen] Icone gerado em {out_path}")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logging.getLogger("icon-gen").error(f"Falha gerando icone: {e}")
