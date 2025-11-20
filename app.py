import os
from flask import Flask, request, jsonify, send_file
from PIL import Image
import numpy as np

# --- Configurare ---
app = Flask(__name__)
UPLOAD_FOLDER = 'uploads'
TILE_FOLDER = 'tile_images'
OUTPUT_FOLDER = 'output'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)
# Presupunem că 'tile_images' este deja populat cu imagini

# --- Constante ---
# 💡 MODIFICARE 1: Reducem TILE_SIZE pentru o rezoluție mai bună a mozaicului
TILE_SIZE = 16  # Dimensiunea la care vom redimensiona toate dalele (ex. 16x16)
# O valoare mai mică (ex. 8 sau 16) va genera un mozaic mai CLAR.

# ... (funcțiile calculate_average_color, load_tile_images, get_closest_tile rămân neschimbate) ...

def calculate_average_color(image: Image.Image):
    """Calculează culoarea medie RGB a unei imagini."""
    img_array = np.array(image.convert("RGB"))
    avg_color = np.mean(img_array, axis=(0, 1)).astype(int)
    return tuple(avg_color)

def load_tile_images():
    """Încarcă toate dalele, le redimensionează și le pre-calculează culorile medii."""
    tiles_data = {}
    for filename in os.listdir(TILE_FOLDER):
        if filename.endswith(('.jpg', '.png', '.jpeg')):
            filepath = os.path.join(TILE_FOLDER, filename)
            try:
                img = Image.open(filepath).convert("RGB")
                # Redimensionare uniformă pentru a asigura dimensiunea TILE_SIZE x TILE_SIZE
                img = img.resize((TILE_SIZE, TILE_SIZE))
                
                avg_color = calculate_average_color(img)
                tiles_data[avg_color] = img
            except Exception as e:
                print(f"Eroare la încărcarea dalei {filename}: {e}")
    return tiles_data

# Se execută o singură dată la pornirea serverului
TILE_IMAGES_DATA = load_tile_images()
TILE_COLORS = list(TILE_IMAGES_DATA.keys()) # Lista cu culorile medii ale dalelor

def get_closest_tile(target_color, tile_colors):
    """Găsește culoarea dalei cea mai apropiată de culoarea țintă (folosind distanța euclidiană)."""
    target_r, target_g, target_b = target_color
    
    tile_colors_array = np.array(tile_colors)
    
    # Distanța Euclidiană pătratică
    distances = np.sum((tile_colors_array - np.array(target_color))**2, axis=1)
    
    closest_index = np.argmin(distances)
    
    return tile_colors[closest_index]


def generate_mosaic(main_image_path, tile_data):
    """Generează imaginea mozaic."""
    main_img = Image.open(main_image_path).convert("RGB")
    width, height = main_img.size
    
    # Asigurăm că dimensiunile sunt multipli de TILE_SIZE
    new_width = (width // TILE_SIZE) * TILE_SIZE
    new_height = (height // TILE_SIZE) * TILE_SIZE
    main_img = main_img.crop((0, 0, new_width, new_height))
    
    mosaic_img = Image.new('RGB', (new_width, new_height))
    
    for i in range(0, new_width, TILE_SIZE):
        for j in range(0, new_height, TILE_SIZE):
            # 1. Extrage blocul (porțiunea) din imaginea principală
            box = (i, j, i + TILE_SIZE, j + TILE_SIZE)
            block = main_img.crop(box)
            
            # 2. Calculează culoarea medie a blocului
            avg_color = calculate_average_color(block)
            
            # 3. Găsește cea mai apropiată dală
            closest_color = get_closest_tile(avg_color, TILE_COLORS)
            tile_image = tile_data[closest_color]
            
            # 4. Plasează dala în imaginea mozaic
            mosaic_img.paste(tile_image, box)

    # Salvează imaginea generată
    output_path = os.path.join(OUTPUT_FOLDER, "mosaic_output.jpeg")
    
    # 💡 MODIFICARE 2: Creștem calitatea la salvare (implicit e 75, max e 95)
    mosaic_img.save(output_path, 'JPEG', quality=95) 
    
    return output_path


# ... (rutele Flask rămân neschimbate) ...

@app.route('/upload', methods=['POST'])
def upload_file():
    """Ruta pentru încărcarea imaginii principale."""
    if 'file' not in request.files:
        return jsonify({"error": "Nu s-a găsit fișierul în cerere"}), 400
        
    file = request.files['file']
    
    if file.filename == '':
        return jsonify({"error": "Numele fișierului este gol"}), 400
        
    if file:
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], 'main_image.jpg')
        try:
            img = Image.open(file).convert("RGB")
            img.save(filepath, 'JPEG')
            return jsonify({
                "message": "Imaginea a fost încărcată cu succes!", 
                "path": filepath
            }), 200
        except Exception as e:
            return jsonify({"error": f"Eroare la salvarea fișierului: {e}"}), 500


@app.route('/generate_mosaic', methods=['POST'])
def generate():
    """Ruta pentru generarea mozaicului."""
    main_image_path = os.path.join(app.config['UPLOAD_FOLDER'], 'main_image.jpg')
    
    if not os.path.exists(main_image_path):
        return jsonify({"error": "Imaginea principală nu a fost încărcată. Folosiți /upload prima dată."}), 400
        
    if not TILE_IMAGES_DATA:
        return jsonify({"error": "Nu s-au găsit imagini de dale în directorul tile_images."}), 500

    try:
        output_path = generate_mosaic(main_image_path, TILE_IMAGES_DATA)
        return send_file(output_path, mimetype='image/jpeg', as_attachment=True, download_name='mozaic_generat.jpeg')
        
    except Exception as e:
        print(f"Eroare la generarea mozaicului: {e}")
        return jsonify({"error": f"Eroare la generarea mozaicului: {e}"}), 500


# --- Rularea Aplicației ---
if __name__ == '__main__':
    print(f"Dalele încărcate: {len(TILE_IMAGES_DATA)} imagini.")
    app.run(debug=True, port=5000)