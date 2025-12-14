import os
import random
from flask import Flask, request, jsonify, send_file, render_template, send_from_directory
from PIL import Image
import numpy as np

# --- 1. CONFIGURARE ---
try:
    from scipy.spatial import KDTree
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False
    print("!!! AVERTISMENT: Scipy nu este instalat. Recomand: pip install scipy !!!")

app = Flask(__name__)
UPLOAD_FOLDER = 'uploads'
TILE_FOLDER = 'tile_images'
OUTPUT_FOLDER = 'output'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['TILE_FOLDER'] = TILE_FOLDER

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)
os.makedirs(TILE_FOLDER, exist_ok=True)

TILE_SIZE = 32 

# --- 2. LOGICĂ PRELUCRARE IMAGINI ---
def calculate_average_color(image: Image.Image):
    img_array = np.array(image.convert("RGB"))
    avg_color = np.mean(img_array, axis=(0, 1)).astype(int)
    return tuple(avg_color)

def load_tile_images():
    print("Se încarcă dalele (poate dura puțin)...")
    tiles_data = {}
    valid_extensions = ('.jpg', '.png', '.jpeg')
    
    if not os.path.exists(TILE_FOLDER):
        return {}

    files = [f for f in os.listdir(TILE_FOLDER) if f.lower().endswith(valid_extensions)]
    if not files:
        return {}

    for filename in files:
        filepath = os.path.join(TILE_FOLDER, filename)
        try:
            img = Image.open(filepath).convert("RGB")
            img = img.resize((TILE_SIZE, TILE_SIZE))
            avg_color = calculate_average_color(img)
            tiles_data[avg_color] = img
        except Exception as e:
            print(f"Eroare la încărcarea dalei {filename}: {e}")
            
    print(f"Au fost încărcate {len(tiles_data)} dale unice.")
    return tiles_data

# --- 3. INIȚIALIZARE ---
TILE_IMAGES_DATA = load_tile_images()
TILE_COLORS = list(TILE_IMAGES_DATA.keys())

tree = None
if HAS_SCIPY and TILE_COLORS:
    print("Se construiește arborele KDTree...")
    tree = KDTree(TILE_COLORS)

def get_closest_tile(target_color):
    if tree:
        dist, index = tree.query(target_color)
        return TILE_COLORS[index]
    
    if not TILE_COLORS: return None
    tile_colors_array = np.array(TILE_COLORS)
    distances = np.sum((tile_colors_array - np.array(target_color))**2, axis=1)
    closest_index = np.argmin(distances)
    return TILE_COLORS[closest_index]

def generate_mosaic(main_image_path, tile_data):
    if not tile_data:
        raise Exception("Nu există dale încărcate!")

    print(f"Se începe generarea mozaicului...")
    main_img = Image.open(main_image_path).convert("RGB")
    width, height = main_img.size
    
    new_width = (width // TILE_SIZE) * TILE_SIZE
    new_height = (height // TILE_SIZE) * TILE_SIZE
    main_img = main_img.crop((0, 0, new_width, new_height))
    
    mosaic_img = Image.new('RGB', (new_width, new_height))
    
    for i in range(0, new_width, TILE_SIZE):
        for j in range(0, new_height, TILE_SIZE):
            box = (i, j, i + TILE_SIZE, j + TILE_SIZE)
            block = main_img.crop(box)
            avg_color = calculate_average_color(block)
            
            closest_color = get_closest_tile(avg_color)
            if closest_color:
                tile_image = tile_data[closest_color]
                mosaic_img.paste(tile_image, box)

    output_path = os.path.join(OUTPUT_FOLDER, "mosaic_output.jpeg")
    mosaic_img.save(output_path, 'JPEG', quality=95)
    return output_path

# --- 4. RUTE FLASK ---

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files: return jsonify({"error": "No file"}), 400
    file = request.files['file']
    if file.filename == '': return jsonify({"error": "No name"}), 400
    
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], 'main_image.jpg')
    img = Image.open(file).convert("RGB")
    img.save(filepath, 'JPEG')
    return jsonify({"message": "OK"}), 200

@app.route('/generate_mosaic', methods=['POST'])
def generate():
    main_path = os.path.join(app.config['UPLOAD_FOLDER'], 'main_image.jpg')
    if not os.path.exists(main_path): return jsonify({"error": "Lipsa imagine"}), 400
    
    global TILE_IMAGES_DATA
    if not TILE_IMAGES_DATA: TILE_IMAGES_DATA = load_tile_images()

    try:
        output = generate_mosaic(main_path, TILE_IMAGES_DATA)
        return send_file(output, mimetype='image/jpeg')
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- RUTE EFECTE VIZUALE ---

# Returnează lista de dale (Am crescut limita la 100 pentru a umple marginile)
@app.route('/api/random_tiles')
def get_random_tiles():
    files = [f for f in os.listdir(TILE_FOLDER) if f.lower().endswith(('.jpg', '.png', '.jpeg'))]
    if not files: return jsonify([])
    
    # Selectăm 100 de imagini sau câte există
    sample_size = min(len(files), 100)
    selected_files = random.sample(files, sample_size)
    return jsonify(selected_files)

# Servește imaginea efectivă
@app.route('/tile_content/<filename>')
def serve_tile_content(filename):
    return send_from_directory(app.config['TILE_FOLDER'], filename)

if __name__ == '__main__':
    print("Server pornit! http://127.0.0.1:5000")
    app.run(debug=True, port=5000)