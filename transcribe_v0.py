import os
import re
import time
import sys
import logging
import csv
import warnings
from datetime import datetime
from google import genai
from PIL import Image

# Gag the over-dramatic AFC warning from the SDK's warning module
warnings.filterwarnings("ignore", module="google.genai")
logging.getLogger("google.genai").setLevel(logging.ERROR)

client = genai.Client(api_key="AQ.Ab8RN6JWQhl37etDqaIa73Hf9xMKOSZOv89Bq4Jb_HGWcmciFQ") 

csv_path = r"G:\My Drive\Egg Slip Scanning\EggSlipReorganizationProject_FULL.xlsx - Full List.csv"
base_family_dir = r"G:\My Drive\Egg Slip Scanning\Family"

# --- 1. Load the Master CSV (Now capturing Family data) ---
print("Loading master CSV database... 🗄️")
db_records_by_enum = {}
db_records_by_row = {}
species_to_family = {} # Fast reverse-lookup dictionary

try:
    with open(csv_path, mode='r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row_num, row in enumerate(reader, start=2):
            cat_num = row.get('catalogNumber', '').strip().upper()
            if cat_num:
                db_records_by_enum[cat_num] = row
                db_records_by_row[row_num] = row
                
                # Extract taxonomy for exact pathfinding
                sci_name = row.get('Scientific Name', '').strip()
                family = row.get('Family', '').strip()
                if sci_name and family:
                    parts = sci_name.split()
                    if len(parts) >= 2:
                        species_name = f"{parts[0].capitalize()}_{parts[1].lower()}"
                        species_to_family[species_name.lower()] = family.capitalize()
                        
    print(f"Loaded {len(db_records_by_enum)} canonical records.")
except Exception as e:
    print(f"CRITICAL ERROR: Could not load CSV. Error: {e}")
    sys.exit()

# --- 2. User Input & Multi-Mode Routing ---
print("-" * 65)
user_input = input("Enter target (e.g., Lagopus_lagopus, E2695, E2695*, or 2-1000): ").strip()
print("-" * 65)

console_only = False
if user_input.endswith("*"):
    console_only = True
    user_input = user_input[:-1].strip()

targets_by_species = {}
process_all_in_species = None

range_match = re.match(r"^(\d+)-(\d+)$", user_input)
enum_match = re.match(r"^E\d+$", user_input, re.IGNORECASE)

if range_match:
    if console_only:
        print("Warning: Asterisk mode is for single cards only. Ignoring asterisk for batch run.")
        console_only = False
    
    start_row, end_row = int(range_match.group(1)), int(range_match.group(2))
    found_count = 0
    for r in range(start_row, end_row + 1):
        if r in db_records_by_row:
            record = db_records_by_row[r]
            e_num = record.get('catalogNumber', '').strip().upper()
            sci_name = record.get('Scientific Name', '').strip()
            
            if e_num and sci_name:
                parts = sci_name.split()
                if len(parts) >= 2:
                    species_name = f"{parts[0].capitalize()}_{parts[1].lower()}"
                    targets_by_species.setdefault(species_name, set()).add(e_num)
                    found_count += 1
    print(f"Mapped {found_count} specimens from rows {start_row}-{end_row}.")

elif enum_match:
    e_num = user_input.upper()
    record = db_records_by_enum.get(e_num)
    if not record:
        print(f"Error: {e_num} not found in the master CSV.")
        sys.exit()
        
    sci_name = record.get('Scientific Name', '').strip()
    if not sci_name:
        print(f"Error: No Scientific Name data for {e_num} in Column G.")
        sys.exit()
        
    parts = sci_name.split()
    if len(parts) < 2:
        print(f"Error: Scientific Name '{sci_name}' is too short to parse a folder name.")
        sys.exit()
        
    species_name = f"{parts[0].capitalize()}_{parts[1].lower()}"
    targets_by_species.setdefault(species_name, set()).add(e_num)
    
    if console_only:
        print(f"Asterisk detected. Outputting {e_num} strictly to console. 🚫💾")
    else:
        print(f"Mapped {e_num} -> {species_name}")

else:
    process_all_in_species = user_input
    if console_only:
        print("Warning: Asterisk mode is for single cards only. Ignoring asterisk for species run.")
        console_only = False

# --- 3. Base Prompt Definition ---
base_prompt_text = """
Extract the data from the provided oological specimen card(s). 
Return the data strictly in plain text. Do not use markdown formatting.

CRITICAL INSTRUCTIONS:
1. Strict Literal Transcription: Transcribe text EXACTLY as written on the card, including typos (e.g., "hairsleftup") and exact alphanumerics (e.g., "48i"). Read left to right and top to bottom. Do not expand abbreviations.
2. Dynamic Ordered Fields: Do not use a rigidly pre-defined list of fields. Instead, output the fields EXACTLY in the order they appear on the card. Use the printed label as the field name (e.g., "No.:", "Name:", "Collector:"). If a field is printed but left empty, output the field name followed by a hyphen (e.g., "Depth: -"). Omit fields that are not printed on this specific card.
3. Unsure Words: If you cannot make out a cursive word, do the best you can and put the difficult word in brackets [ ] to indicate uncertainty.
4. ANNOTATIONS: Log all extraneous marks, catalog numbers, blue stamps, crossed-out text, or un-fielded text in a field named "ANNOTATIONS:". You MUST include positional tags indicating where the mark is located (e.g., "(top left) 1748 crossed out"). 
5. BACK OF SLIP: If multiple images are provided, image 1 is the front. For a second image, put all of its text under a single field named "BACK OF SLIP:". If there are 3+ images, use "BACK OF SLIP 2:", etc.
6. TRANSCRIPTION NOTES: Always include a field at the very end named "TRANSCRIPTION NOTES:". Leave it empty unless there are general notes about the physical slip itself (e.g., unclear catalog record, or a run of multiple catalog numbers like E111_E112).

FORMAT EXPECTATION:
[Dynamically generated fields in card order]
ANNOTATIONS: 
[BACK OF SLIP: (if applicable)]
TRANSCRIPTION NOTES: 
"""

# --- 4. Master Processing Loop ---
species_list = [process_all_in_species] if process_all_in_species else list(targets_by_species.keys())

for target_species in species_list:
    # Use exact path construction via CSV lookup instead of os.walk
    family_name = species_to_family.get(target_species.lower())
    if not family_name:
        print(f"Error: Could not find Family for '{target_species}' in CSV. Skipping.")
        continue
        
    family_dir = os.path.join(base_family_dir, family_name)
    input_dir = os.path.join(family_dir, target_species, "JPEG")
    
    if not os.path.exists(input_dir):
        print(f"Error: Target path does not exist: {input_dir}. Skipping.")
        continue
        
    timestamp = datetime.now().strftime("%H%M-%d-%m-%y")
    output_file = os.path.join(family_dir, f"{target_species}_transcriptions_{timestamp}.txt")
    
    pattern = re.compile(r"^(.*?_E\d+)(?:\([A-Za-z0-9]+\))?\.jpe?g$", re.IGNORECASE)
    
    grouped_cards = {}
    for filename in os.listdir(input_dir):
        match = pattern.match(filename)
        if match:
            base_id = match.group(1)
            grouped_cards.setdefault(base_id, []).append(filename)
            
    if not process_all_in_species:
        allowed_enums = targets_by_species[target_species]
        filtered_groups = {}
        for bid, files in grouped_cards.items():
            match = re.search(r"_(E\d+)", bid, re.IGNORECASE)
            if match and match.group(1).upper() in allowed_enums:
                filtered_groups[bid] = files
        grouped_cards = filtered_groups

    if not grouped_cards:
        print(f"No target files found in {input_dir}. Skipping.")
        continue
        
    def extract_e_number(base_id):
        m = re.search(r"_E(\d+)", base_id)
        return int(m.group(1)) if m else 0
        
    sorted_base_ids = sorted(grouped_cards.keys(), key=extract_e_number)
    print(f"\n[{target_species}] Processing {len(grouped_cards)} card(s)...")

    out_f = None
    if not console_only:
        out_f = open(output_file, "a", encoding="utf-8")

    try:
        for base_id in sorted_base_ids:
            filenames = grouped_cards[base_id]
            print(f"  -> Processing {base_id} ({len(filenames)} side(s))...")
            
            e_num_int = extract_e_number(base_id)
            e_num_str = f"E{e_num_int}"
            
            dynamic_prompt = base_prompt_text
            record = db_records_by_enum.get(e_num_str)
            
            if record:
                geo_parts = [record.get('locality'), record.get('county'), record.get('stateProvince'), record.get('country')]
                geo_string = ", ".join([p.strip() for p in geo_parts if p and p.strip()])
                
                dynamic_prompt += f"""
                
=== GROUND TRUTH MATCH FOUND FOR {e_num_str} ===
- Collector: {record.get('Collector', '')}
- Geography: {geo_string}
- Scientific Name: {record.get('Scientific Name', '')}
================================================
"""
            
            contents = [dynamic_prompt]
            images_to_close = []
            output_text = ""
            
            try:
                for filename in filenames:
                    file_path = os.path.join(input_dir, filename)
                    img = Image.open(file_path)
                    img.thumbnail((2000, 2000)) 
                    contents.append(img)
                    images_to_close.append(img)
                
                max_retries = 5
                for attempt in range(max_retries):
                    try:
                        response = client.models.generate_content(
                            model="gemini-3.5-flash-lite", 
                            contents=contents,
                            config={"temperature": 0.1}
                        )
                        output_text = response.text.strip()
                        break 
                        
                    except Exception as api_e:
                        error_str = str(api_e)
                        if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str or "503" in error_str or "UNAVAILABLE" in error_str or "10054" in error_str:
                            wait_time = 10 * (attempt + 1)
                            print(f"  -> Rate limit/Server spike. Sleeping {wait_time}s... 😴")
                            time.sleep(wait_time)
                        else:
                            output_text = f"CRITICAL API ERROR: {error_str}"
                            print(f"  -> API Failed: {error_str}")
                            break
                else:
                    output_text = "CRITICAL ERROR: Skipped after 5 rate-limit retries."
                    
            except Exception as local_e:
                output_text = f"CRITICAL LOCAL ERROR: {str(local_e)}"
                print(f"  -> Image Load Failed: {local_e}")
                
            finally:
                for img in images_to_close:
                    img.close()

            # --- 5. Console Echo & File Write ---
            if console_only:
                print("\n" + "=" * 60)
                print(f"🎯 TARGET CARD OUTPUT ({base_id})")
                print("=" * 60)
                print(output_text)
                print("=" * 60 + "\n")

            if out_f:
                block = f"==================================================\n"
                block += f"ID: {base_id}\n"
                block += f"==================================================\n"
                block += f"{output_text}\n\n"
                
                out_f.write(block)
                out_f.flush() 
                
                # Throttle to stay under the 15 RPM radar
                time.sleep(4.1) 

    finally:
        if out_f:
            out_f.close()
            
print("\nBatch completed.")