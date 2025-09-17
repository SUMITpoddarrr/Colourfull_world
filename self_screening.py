import tkinter as tk
from tkinter import messagebox, Toplevel
from PIL import Image, ImageTk
import os, random
from datetime import datetime

BASE_DIR = r"test_imgs"
RG_DIR = os.path.join(BASE_DIR, "red-green")
CLASSIFY_DIR = os.path.join(BASE_DIR, "classify_red-green")
SOLUTIONS_DIR = r"actual_imgs"  

PHASE1_COUNT = 10
PHASE2_COUNT = 3


def pick_random(folder, n):
    files = [f for f in os.listdir(folder)
             if f.lower().endswith((".png", ".jpg", ".jpeg"))]
    chosen = random.sample(files, n)
    return [os.path.join(folder, f) for f in chosen]


class IshiharaApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Ishihara Color Vision Test")

        self.phase = 1
        self.plates = pick_random(RG_DIR, PHASE1_COUNT)
        self.solutions = [os.path.join(SOLUTIONS_DIR, os.path.basename(p)) for p in self.plates]
        self.responses = [None] * len(self.plates)
        self.index = 0

        self.classify_plates = []
        self.classify_solutions = []
        self.classify_responses = []
        self.deutan_hits = 0
        self.protan_hits = 0
        self.result_text = ""

        self.canvas = tk.Canvas(root, width=512, height=512)
        self.canvas.grid(row=0, column=0, columnspan=3, pady=10)

        self.label = tk.Label(root, text="Enter the number you see:")
        self.label.grid(row=1, column=0, columnspan=3)

        self.entry = tk.Entry(root)
        self.entry.grid(row=2, column=0, columnspan=2, sticky="we", padx=5)

        self.submit_btn = tk.Button(root, text="Submit / Next", command=self.submit_answer)
        self.submit_btn.grid(row=2, column=2, padx=5)

        self.prev_btn = tk.Button(root, text="Back", command=self.go_prev)
        self.prev_btn.grid(row=4, column=1, pady=5)

        self.progress = tk.Label(root)
        self.progress.grid(row=3, column=0, columnspan=3)

        self.restart_btn = tk.Button(root, text="Restart", command=self.restart_test)
        self.restart_btn.grid(row=4, column=0, pady=5)

        self.quit_btn = tk.Button(root, text="Quit", command=root.quit)
        self.quit_btn.grid(row=4, column=2, pady=5)

        self.review_win = None

        self.show_plate()

    def show_plate(self):
        img_path = self.current_list()[self.index]
        img = Image.open(img_path).resize((512, 512))
        self.tkimg = ImageTk.PhotoImage(img)
        self.canvas.create_image(0, 0, anchor="nw", image=self.tkimg)
        self.progress.config(text=f"Plate {self.index+1}/{len(self.current_list())}")
        self.entry.delete(0, tk.END)
        existing = self.current_responses()[self.index]
        if existing:
            self.entry.insert(0, existing)

    def current_list(self):
        return self.plates if self.phase == 1 else self.classify_plates

    def current_solutions(self):
        return self.solutions if self.phase == 1 else self.classify_solutions

    def current_responses(self):
        return self.responses if self.phase == 1 else self.classify_responses

    def submit_answer(self):
        ans = self.entry.get().strip()
        self.current_responses()[self.index] = ans

        if self.phase == 2:
            correct = os.path.splitext(os.path.basename(self.classify_plates[self.index]))[0]
            if ans:
                if ans[0] == correct[0]:
                    self.deutan_hits += 1
                if len(ans) > 1 and ans[1] == correct[1]:
                    self.protan_hits += 1

        if self.index < len(self.current_list()) - 1:
            self.index += 1
            self.show_plate()
        else:
            self.finish_phase()

    def go_prev(self):
        if self.index > 0:
            self.index -= 1
            self.show_plate()

    def finish_phase(self):
        if self.phase == 1:
            correct = 0
            for path, resp in zip(self.plates, self.responses):
                gt = os.path.splitext(os.path.basename(path))[0]
                if resp == gt:
                    correct += 1
            miss = len(self.plates) - correct
            if miss >= len(self.plates) / 2:
                self.phase = 2
                self.classify_plates = pick_random(CLASSIFY_DIR, PHASE2_COUNT)
                self.classify_solutions = [os.path.join(SOLUTIONS_DIR, os.path.basename(p))
                                           for p in self.classify_plates]
                self.classify_responses = [None] * PHASE2_COUNT
                self.index = 0
                messagebox.showinfo("Step 2", "Please answer a few more plates for classification.")
                self.show_plate()
            else:
                self.result_text = "Likely normal color vision"
                self.prepare_review()
        else:
            if self.deutan_hits >= 3:
                self.result_text = "Likely green (Dutan) deficiency"
            elif self.protan_hits >= 3:
                self.result_text = "Likely red (Protan) deficiency"
            else:
                self.result_text = "Red-green deficiency (type uncertain)"
            self.prepare_review()


    def prepare_review(self):
        messagebox.showinfo("Result", self.result_text)
        self.review_index = 0
        self.all_tests = self.plates + self.classify_plates
        self.all_solutions = self.solutions + self.classify_solutions
        self.all_responses = self.responses + self.classify_responses
        self.submit_btn.config(state="disabled")
        self.entry.config(state="disabled")
        if self.review_win and self.review_win.winfo_exists():
            self.review_win.destroy()
        self.review_win = Toplevel(self.root)
        self.review_win.title("Review Results")

        self.rev_img_left_lbl = tk.Label(self.review_win)
        self.rev_img_left_lbl.grid(row=0, column=0, padx=5, pady=5)
        self.rev_img_right_lbl = tk.Label(self.review_win)
        self.rev_img_right_lbl.grid(row=0, column=1, padx=5, pady=5)

        self.rev_status = tk.Label(self.review_win, text="")
        self.rev_status.grid(row=1, column=0, columnspan=2, pady=(0,5))
        self.rev_prev_btn = tk.Button(self.review_win, text="Previous", command=self.show_prev_review)
        self.rev_prev_btn.grid(row=2, column=0, pady=5)
        self.rev_next_btn = tk.Button(self.review_win, text="Next", command=self.show_next_review)
        self.rev_next_btn.grid(row=2, column=1, pady=5)
        self.rev_close_btn = tk.Button(self.review_win, text="Close", command=self.review_win.destroy)
        self.rev_close_btn.grid(row=3, column=0, columnspan=2, pady=5)
        self.show_next_review()

    def update_review_ui(self):
        total = len(self.all_tests)
        self.rev_prev_btn.config(state=("normal" if self.review_index > 0 else "disabled"))
        self.rev_next_btn.config(state=("normal" if self.review_index < total - 1 else "disabled"))
        paths = [self.all_tests[self.review_index], self.all_solutions[self.review_index]]
        imgs = []
        for path in paths:
            img = Image.open(path).resize((300, 300))
            imgs.append(ImageTk.PhotoImage(img))
        self.rev_left_img_ref = imgs[0]
        self.rev_right_img_ref = imgs[1]
        self.rev_img_left_lbl.config(image=self.rev_left_img_ref)
        self.rev_img_right_lbl.config(image=self.rev_right_img_ref)
        expected = os.path.splitext(os.path.basename(self.all_tests[self.review_index]))[0]
        user_answer = self.all_responses[self.review_index]
        user_answer_disp = "(blank)" if not user_answer else user_answer
        is_correct = (user_answer == expected)
        status_text = (
            f"Your answer: {user_answer_disp}\n"
            f"Correct answer: {expected}\n"
            f"{'Correct' if is_correct else 'Incorrect'}"
        )
        self.rev_status.config(text=status_text, fg=("green" if is_correct else "red"))

    def show_next_review(self):
        if self.review_index < len(self.all_tests) - 1:
            self.review_index += 1
        self.update_review_ui()

    def show_prev_review(self):
        if self.review_index > 0:
            self.review_index -= 1
        self.update_review_ui()

    def restart_test(self):
        self.phase = 1
        self.plates = pick_random(RG_DIR, PHASE1_COUNT)
        self.solutions = [os.path.join(SOLUTIONS_DIR, os.path.basename(p)) for p in self.plates]
        self.responses = [None] * len(self.plates)
        self.index = 0
        self.classify_plates = []
        self.classify_solutions = []
        self.classify_responses = []
        self.deutan_hits = 0
        self.protan_hits = 0
        self.result_text = ""
        if self.review_win and self.review_win.winfo_exists():
            self.review_win.destroy()
        self.review_win = None
        self.submit_btn.config(state="normal")
        self.entry.config(state="normal")
        self.entry.delete(0, tk.END)
        self.show_plate()


if __name__ == "__main__":
    root = tk.Tk()
    IshiharaApp(root)
    root.mainloop()
