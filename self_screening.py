
import tkinter as tk
from tkinter import messagebox
from PIL import Image, ImageDraw, ImageTk, ImageFont
import numpy as np
import random
import csv
import os
from datetime import datetime

PLATE_SIZE = 512         
DOT_COUNT = 1800      
DOT_MIN = 6              
DOT_MAX = 12             
NUM_PLATES = 10          
FONT_PATH = None          


# color helpers
def clamp_color(c):
    return tuple(int(max(0, min(255, v))) for v in c)

def rgb(r,g,b):
    return clamp_color((r,g,b))

PALETTE = {
    'rg_foreground': rgb(200, 40, 40),   # red-ish foreground 
    'rg_background': rgb(100, 180, 90),  # green-ish background
    'by_foreground': rgb(40, 100, 220),  # blue-ish foreground 
    'by_background': rgb(220, 200, 60),  # yellow-ish background
    'neutral_fg': rgb(50, 50, 50),
    'neutral_bg': rgb(220, 220, 220),
    'high_fg': rgb(10, 10, 10),
    'high_bg': rgb(240, 240, 240),
}

DIGITS = list(range(1,10))

def generate_plate(plate_spec):
    size = PLATE_SIZE
    image = Image.new("RGB", (size, size), PALETTE['neutral_bg'])
    draw = ImageDraw.Draw(image)

    mask = Image.new("L", (size, size), 0)
    mask_draw = ImageDraw.Draw(mask)

    digit = plate_spec.get('digit')
    if digit is not None:
        text = str(digit)
        
        font_size = int(size * 0.6)  
        font = None
        
        font_paths = [
            "C:/Windows/Fonts/arial.ttf",
            "C:/Windows/Fonts/calibri.ttf", 
            "C:/Windows/Fonts/verdana.ttf",
            "C:/Windows/Fonts/tahoma.ttf"
        ]
        
        for font_path in font_paths:
            try:
                font = ImageFont.truetype(font_path, font_size)
                break
            except:
                continue

        if font is None:
            font = ImageFont.load_default()
            temp_img = Image.new("L", (size, size), 0)
            temp_draw = ImageDraw.Draw(temp_img)
            temp_bbox = temp_draw.textbbox((0, 0), text, font=font)
            temp_w, temp_h = temp_bbox[2] - temp_bbox[0], temp_bbox[3] - temp_bbox[1]
            
            scale_factor = min(size * 0.4 / temp_w, size * 0.4 / temp_h)
            scaled_size = int(font_size * scale_factor)
            
            center_x, center_y = size // 2, size // 2
            for dx in range(-2, 3):
                for dy in range(-2, 3):
                    pos = (center_x + dx - temp_w//2, center_y + dy - temp_h//2)
                    mask_draw.text(pos, text, fill=255, font=font)
        else:
            bbox = mask_draw.textbbox((0, 0), text, font=font)
            w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
            pos = ((size - w) // 2, (size - h) // 2)
            mask_draw.text(pos, text, fill=255, font=font)
    else:
        pass

    mask_arr = np.array(mask) / 255.0  # 0..1

    fg = plate_spec.get('fg', PALETTE['neutral_fg'])
    bg = plate_spec.get('bg', PALETTE['neutral_bg'])

    rng = np.random.default_rng()
    for _ in range(DOT_COUNT):
        r = int(rng.integers(DOT_MIN, DOT_MAX + 1))
        x = int(rng.integers(0, size))
        y = int(rng.integers(0, size))
        if 0 <= x < size and 0 <= y < size and mask_arr[y, x] > 0.5:
            color = fg
        else:
            color = bg

        jitter = lambda c: clamp_color((c[0] + rng.integers(-14,15), c[1] + rng.integers(-14,15), c[2] + rng.integers(-14,15)))
        color_j = jitter(color)

        # draw ellipse
        bbox = [x - r, y - r, x + r, y + r]
        draw.ellipse(bbox, fill=color_j, outline=None)

    return image

def build_plate_specs(n):
    specs = []
    # distribution: more RG and BY probes, some neutral and control
    types_list = (['prot'] * 3) + (['deut'] * 3) + (['trit'] * 2) + (['normal'] * 2) + (['control'] * 1)
    random.shuffle(types_list)
    chosen = types_list[:n]
    for t in chosen:
        if t in ('prot', 'deut'):
            d = random.choice(DIGITS)
            spec = {'type': t, 'digit': d, 'fg': PALETTE['rg_foreground'], 'bg': PALETTE['rg_background']}
        elif t == 'trit':
            d = random.choice(DIGITS)
            spec = {'type': t, 'digit': d, 'fg': PALETTE['by_foreground'], 'bg': PALETTE['by_background']}
        elif t == 'normal':
            d = random.choice(DIGITS)
            spec = {'type': t, 'digit': d, 'fg': PALETTE['neutral_fg'], 'bg': PALETTE['neutral_bg']}
        else:  # control
            # big high-contrast digit meant to be readable by everyone
            d = random.choice(DIGITS)
            spec = {'type': 'control', 'digit': d, 'fg': PALETTE['high_fg'], 'bg': PALETTE['high_bg']}
        specs.append(spec)
    return specs


def classify_responses(plates, responses):

    # Tally expected correctness per plate type
    totals = {'prot':0, 'deut':0, 'trit':0, 'normal':0, 'control':0}
    correct = {'prot':0, 'deut':0, 'trit':0, 'normal':0, 'control':0}

    for spec, resp in zip(plates, responses):
        typ = spec['type']
        totals[typ] += 1
        expected = str(spec['digit']) if spec['digit'] is not None else ''
        # treat empty / "?" as no response
        if resp is None or resp.strip() == '':
            # wrong / no answer
            continue

        resp_d = ''.join(ch for ch in resp if ch.isdigit())
        if resp_d == expected and expected != '':
            correct[typ] += 1

    # Compute scores per category
    scores = {}
    for k in totals:
        scores[k] = (correct[k] / totals[k]) if totals[k] > 0 else None

    classification = "Uncertain"
    reasons = []
    # thresholds (heuristic)
    fail_threshold = 0.5   # less than 50% correct considered failing that type
    strong_diff = 0.25   

    control_ok = scores['control'] is not None and scores['control'] >= 0.6
    normal_ok = scores['normal'] is not None and scores['normal'] >= 0.6

    prot_fail = scores['prot'] is not None and scores['prot'] < fail_threshold
    deut_fail = scores['deut'] is not None and scores['deut'] < fail_threshold
    trit_fail = scores['trit'] is not None and scores['trit'] < fail_threshold

    # average red-green probes
    rg_scores = []
    if scores['prot'] is not None: rg_scores.append(scores['prot'])
    if scores['deut'] is not None: rg_scores.append(scores['deut'])
    avg_rg = sum(rg_scores)/len(rg_scores) if rg_scores else None

    # make decisions
    if not control_ok:
        classification = "Possible severe color vision deficiency or test invalid"
        reasons.append("Failed control plates (low score) — could be severe deficiency or poor testing conditions.")
    else:
        # prefer red-green detection if avg_rg much lower than normal plates
        if avg_rg is not None and scores['normal'] is not None:
            if avg_rg + strong_diff < scores['normal']:
                classification = "Likely red-green color vision deficiency (protan/deutan)"
                reasons.append(f"Red-green probe score {avg_rg:.2f} is noticeably lower than neutral score {scores['normal']:.2f}.")
        # tritan case
        if trit_fail and scores['normal'] is not None and scores['normal'] - scores['trit'] >= strong_diff:
            # if we already flagged rg, append; otherwise set
            if "Likely red-green" in classification:
                classification += " (with additional blue-yellow issues)"
            else:
                classification = "Likely blue-yellow color vision deficiency (tritan)"
            reasons.append(f"Tritan plate score {scores['trit']:.2f} is much lower than neutral {scores['normal']:.2f}.")

        # if both RG probes fail
        if prot_fail and deut_fail and (classification == "Uncertain"):
            classification = "Likely red-green color vision deficiency (protan/deutan)"
            reasons.append("Both protan and deutan style plates showed low recognition.")

        # fallback to normal if all good
        if classification == "Uncertain":
            # check for overall good performance
            good_counts = 0
            total_types = 0
            for k in ['prot','deut','trit','normal','control']:
                if scores[k] is not None:
                    total_types += 1
                    if scores[k] >= 0.6:
                        good_counts += 1
            if total_types > 0 and good_counts / total_types >= 0.8:
                classification = "Likely normal color vision"
                reasons.append("High score across probe types.")
            else:
                classification = "Inconclusive"
                reasons.append("Results are mixed and inconclusive.")

    # Confidence heuristic: distance from threshold and number of plates
    confidence = 0.5
    if "Likely" in classification:
        # compute confidence by how low the failing scores are
        low_scores = []
        for k in ['prot','deut','trit']:
            if scores[k] is not None:
                low_scores.append(1 - scores[k])
        avg_low = sum(low_scores)/len(low_scores) if low_scores else 0.3
        confidence = min(0.95, 0.5 + avg_low * 0.6)
    elif "Likely normal" in classification:
        avg_all = 0
        count = 0
        for k in scores:
            if scores[k] is not None:
                avg_all += scores[k]; count += 1
        avg_all = avg_all / count if count else 0.5
        confidence = min(0.95, 0.4 + avg_all * 0.6)
    else:
        confidence = 0.45

    return {
        'classification': classification,
        'reasons': reasons,
        'scores': scores,
        'confidence': confidence
    }

class ScreeningApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Color Vision Self-Screening (Prototype)")
        self.plate_specs = build_plate_specs(NUM_PLATES)
        self.plates_images = [generate_plate(s) for s in self.plate_specs]
        self.responses = [None] * len(self.plate_specs)
        self.index = 0

        # UI elements
        self.canvas = tk.Canvas(root, width=PLATE_SIZE, height=PLATE_SIZE)
        self.canvas.grid(row=0, column=0, columnspan=3, padx=10, pady=10)
        self.tkimg = None

        tk.Label(root, text="Enter the digit you see (or leave blank / type '?' if you cannot):").grid(row=1, column=0, columnspan=3)
        self.entry = tk.Entry(root)
        self.entry.grid(row=2, column=0, columnspan=2, sticky='we', padx=5)
        self.submit_btn = tk.Button(root, text="Submit / Next", command=self.submit_answer)
        self.submit_btn.grid(row=2, column=2, padx=5)

        self.progress_label = tk.Label(root, text=f"Plate 1 of {len(self.plates_images)}")
        self.progress_label.grid(row=3, column=0, columnspan=3)

        self.show_plate(self.index)

        self.save_btn = tk.Button(root, text="Save Responses (CSV)", command=self.save_responses)
        self.save_btn.grid(row=4, column=0, pady=6)

        self.restart_btn = tk.Button(root, text="Restart", command=self.restart)
        self.restart_btn.grid(row=4, column=1, pady=6)

        self.quit_btn = tk.Button(root, text="Quit", command=root.quit)
        self.quit_btn.grid(row=4, column=2, pady=6)

    def show_plate(self, idx):
        img = self.plates_images[idx]
        # Resize for display while keeping resolution if needed
        disp = img.resize((PLATE_SIZE, PLATE_SIZE), Image.Resampling.NEAREST)
        self.tkimg = ImageTk.PhotoImage(disp)
        self.canvas.create_image(0, 0, anchor='nw', image=self.tkimg)
        self.progress_label.config(text=f"Plate {idx+1} of {len(self.plates_images)}")
        # Clear entry
        self.entry.delete(0, tk.END)

    def submit_answer(self):
        ans = self.entry.get().strip()
        self.responses[self.index] = ans
        self.index += 1
        if self.index >= len(self.plates_images):
            # finish
            self.finish()
        else:
            self.show_plate(self.index)

    def finish(self):
        result = classify_responses(self.plate_specs, self.responses)
        msg_lines = [
            f"Classification: {result['classification']}",
            f"Confidence (approx): {result['confidence']*100:.0f}%",
            "",
            "Details (scores per plate type):"
        ]
        for k, v in result['scores'].items():
            if v is None:
                s = "N/A"
            else:
                s = f"{v*100:.0f}% correct"
            msg_lines.append(f"  {k}: {s}")
        if result['reasons']:
            msg_lines.append("")
            msg_lines.append("Reasoning:")
            for r in result['reasons']:
                msg_lines.append(" - " + r)

        fullmsg = "\n".join(msg_lines)
        messagebox.showinfo("Screening Result", fullmsg)

        # Offer to save responses
        if messagebox.askyesno("Save", "Do you want to save your responses to CSV?"):
            self.save_responses(auto=True)
        # after completion, disable submit
        self.submit_btn.config(state='disabled')

    def save_responses(self, auto=False):
        # Save a simple CSV in current directory with timestamp
        fname = f"color_screen_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        rows = []
        for i, (spec, resp) in enumerate(zip(self.plate_specs, self.responses)):
            rows.append({
                'index': i+1, 'type': spec['type'], 'digit': spec['digit'], 'response': resp
            })
        keys = ['index','type','digit','response']
        with open(fname, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            writer.writerows(rows)
        if not auto:
            messagebox.showinfo("Saved", f"Responses saved to {os.path.abspath(fname)}")
        else:
            # silent for auto saves
            pass

    def restart(self):
        if messagebox.askyesno("Restart", "Restart the screening? This will clear current answers."):
            self.plate_specs = build_plate_specs(NUM_PLATES)
            self.plates_images = [generate_plate(s) for s in self.plate_specs]
            self.responses = [None] * len(self.plate_specs)
            self.index = 0
            self.submit_btn.config(state='normal')
            self.show_plate(self.index)


if __name__ == "__main__":
    root = tk.Tk()
    app = ScreeningApp(root)
    root.mainloop()
