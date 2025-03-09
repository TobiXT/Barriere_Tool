import tkinter as tk
from tkinter import messagebox, filedialog
from tkinter import ttk
import threading
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from axe_selenium_python import Axe
from urllib.parse import urljoin, urlparse
import time
import traceback  
import json

log_content = ""

# Selenium WebDriver Optionen
chrome_options = Options()
chrome_options.add_argument("--headless")
chrome_options.add_argument("--disable-gpu")
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")
chrome_options.add_argument("--ignore-certificate-errors")
chrome_options.add_argument("--disable-web-security")
chrome_options.add_argument("--disable-software-rasterizer")

# Funktion zum Laden der Übersetzungen aus der JSON-Datei
def load_translations():
    try:
        with open("translations.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Fehler beim Laden der Übersetzungen: {e}")
        return {}

# Lade die Übersetzungen zu Beginn des Programms
translations = load_translations()

# Übersetzungsfunktion
def translate_text(text):
    return translations.get(text, text)  # Wenn keine Übersetzung vorhanden ist, Originaltext beibehalten


def get_all_links(driver, base_url):
    links = set()
    for a in driver.find_elements(By.CSS_SELECTOR, "a[href]"):
        href = a.get_attribute("href")
        if isinstance(href, str) and isinstance(base_url, str):  # Nur wenn beide Strings sind
            links.add(urljoin(base_url, href))
    return links

# Funktion zum Testen des Farbkontrasts
def test_color_contrast(driver, url):
    axe = Axe(driver)
    axe.inject()
    results = axe.run()
    
    contrast_violations = []
    
    for violation in results.get("violations", []):
        if "color contrast" in violation.get("id", ""):
            for node in violation.get("nodes", []):
                html = node.get("html", "")
                contrast_violations.append({
                    "element": html,
                    "description": violation.get("description"),
                    "impact": violation.get("impact")
                })

    return contrast_violations

# Funktion zur Berechnung der Helligkeit einer Farbe (Luminance)
def lumincance(hex_color):
    rgb = [int(hex_color[i:i+2], 16) / 255.0 for i in (1, 3, 5)]  # Konvertiere Hex nach RGB
    rgb = [((color / 12.92) if (color <= 0.03928) else ((color + 0.055) / 1.055) ** 2.4) for color in rgb]
    return 0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2]

# Hilfsfunktion zur Umwandlung von Hex nach RGB
def hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))  # Konvertiere Hex nach RGB

# Umwandlung der RGBA-Farbe in RGB
def rgba_to_rgb(rgba):
    rgba = rgba.replace("rgba(", "").replace(")", "").split(",")
    return tuple(int(c) for c in rgba[:3])  # Nur RGB ohne Alpha-Wert

# Funktion zur Berechnung des Kontrastverhältnisses
def contrast_ratio(color1, color2):
    # Wenn die Farben RGBA sind, konvertiere sie in RGB, sonst in HEX
    if "rgba" in color1:
        color1_rgb = rgba_to_rgb(color1)
    else:
        color1_rgb = hex_to_rgb(color1.lstrip("#"))

    if "rgba" in color2:
        color2_rgb = rgba_to_rgb(color2)
    else:
        color2_rgb = hex_to_rgb(color2.lstrip("#"))

    L1 = lumincance(rgb_to_hex(*color1_rgb))
    L2 = lumincance(rgb_to_hex(*color2_rgb))

    if L1 > L2:
        return (L1 + 0.05) / (L2 + 0.05)
    else:
        return (L2 + 0.05) / (L1 + 0.05)

# Hilfsfunktion zur Umwandlung von RGB nach Hex
def rgb_to_hex(r, g, b):
    return "#{:02x}{:02x}{:02x}".format(r, g, b)


# Funktion zur Überprüfung des Kontrasts und Ausgabe von Fehlern
def check_contrast(driver):
    elements = driver.find_elements("xpath", "//*")  # Alle Elemente auf der Seite
    violations = []
    
    for element in elements:
        try:
            color = element.value_of_css_property('color')  # Textfarbe
            background_color = element.value_of_css_property('background-color')  # Hintergrundfarbe

            # Überprüfen, ob Farben vorhanden sind
            if not color or not background_color:
                continue
            
            # Umwandlung der RGBA-Farbe in HEX für die Berechnung
            if "rgba" in color:
                color = rgb_to_hex(*rgba_to_rgb(color))
            if "rgba" in background_color:
                background_color = rgb_to_hex(*rgba_to_rgb(background_color))

            # Berechne das Kontrastverhältnis
            ratio = contrast_ratio(color, background_color)
            
            if ratio < 4.5:  # Wenn der Kontrast unter 4.5:1 ist, einen Fehler melden
                violations.append({
                    "element": element,
                    "text": element.text,
                    "color": color,
                    "background_color": background_color,
                    "contrast_ratio": ratio
                })
        except Exception as e:
            continue

    return violations   

# Funktion, die aufgerufen wird, wenn die Checkbox geändert wird
def toggle_contrast_check():
    global contrast_check_enabled
    contrast_check_enabled = contrast_check_var.get()  # Setzt den Status der Checkbox

# Funktion zum Testen der Barrierefreiheit (inkl. Kontrast-Check)
def test_accessibility():
    global log_content
    log_content = ""
    test_button.config(state=tk.DISABLED)
    progress_bar["value"] = 0
    progress_bar.pack(pady=10)
    status_label.config(text="🔍 Test läuft...")

    def run_test():
        url = url_entry.get()
        if not url:
            root.after(0, lambda: messagebox.showwarning("Fehler", "Bitte eine URL eingeben!"))
            root.after(0, reset_ui)
            return

        try:
            driver = webdriver.Chrome(options=chrome_options)
            driver.get(url)

            all_links = get_all_links(driver, url)
            all_links.add(url)
            total_links = len(all_links)

            violations = []
            contrast_violations = []

            for index, link in enumerate(all_links, start=1):
                driver.get(link)
                time.sleep(2)

                axe = Axe(driver)
                axe.inject()
                results = axe.run()

                # Fortschritt aktualisieren
                root.after(0, update_progress_step, index, total_links, f"Prüfe Link: {link}")

                if results["violations"]:
                    violations.append((link, results["violations"]))

                # Kontrast-Check nur durchführen, wenn aktiviert
                if contrast_check_enabled:
                    contrast_results = check_contrast(driver)
                    if contrast_results:
                        contrast_violations.append((link, contrast_results))

            root.after(0, update_output, violations, contrast_violations)
            driver.quit()

        except Exception as e:
            error_message = traceback.format_exc()
            print(f"Fehler: {error_message}")
            root.after(0, lambda: messagebox.showerror("Fehler", f"Es gab einen Fehler:\n{error_message}"))
            root.after(0, reset_ui)

    threading.Thread(target=run_test, daemon=True).start()

def update_progress_step(current, total, step_name):
    # Berechnung des Fortschritts
    progress_value = (current / total) * 100
    progress_bar["value"] = progress_value
    
    # Update der Prozentanzeige
    progress_percentage.config(text=f"{int(progress_value)}%")
    
    # Update des Status-Labels mit dem aktuellen Schritt
    status_label.config(text=f"📌 {current}/{total} - Prüfe: {step_name}")
    
    root.update_idletasks()  # Stelle sicher, dass die Anzeige sofort aktualisiert wird.

    if current == 1:  # Wenn der Fortschritt zum ersten Mal startet
        progress_bar.pack(pady=10)  # Stelle sicher, dass der Fortschrittsbalken angezeigt wird



def update_output(violations, contrast_violations):
    global log_content
    output_text.config(state=tk.NORMAL)
    output_text.delete(1.0, tk.END)
    log_content = ""

    # Barrierefreiheitsprobleme anzeigen
    if violations:
        for link, issues_list in violations:
            entry = f"🔍 Ergebnisse für: {link}\n"
            output_text.insert(tk.END, entry, "bold")
            log_content += entry + "\n"

            for violation in issues_list:
                description = violation.get("description", "Keine Beschreibung verfügbar")
                impact = violation.get("impact", "Unbekannt")
                help_url = violation.get("help", "Keine Hilfe verfügbar")

                impact_translation = {
                    "critical": "Kritisch",
                    "serious": "Ernst",
                    "moderate": "Moderat",
                    "minor": "Gering"
                }
                
                impact_de = impact_translation.get(impact, "Unbekannt")
                description_de = translate_text(description)
                help_de = translate_text(help_url)

                color = "red" if impact == "critical" else "orange" if impact == "moderate" else "blue"

                output_text.tag_configure(color, foreground=color)

                entry = f"  ⚠️ Fehler: {description_de}\n  🔴 Schweregrad: {impact_de}\n  📌 Hilfe: {help_de}\n\n"
                output_text.insert(tk.END, entry, color)
                log_content += entry + "\n"

                for node in violation.get("nodes", []):
                    entry = f"    🖹 Element: {str(node.get('html', 'Unbekannt'))}\n\n"
                    output_text.insert(tk.END, entry, color)
                    log_content += entry + "\n"

    else:
        messagebox.showinfo("Ergebnis", "✅ Keine Barrierefreiheitsprobleme gefunden!")
        log_content = "✅ Keine Barrierefreiheitsprobleme gefunden!"

    # Kontrastprobleme anzeigen
    if contrast_violations:
        for link, contrast_issues in contrast_violations:
            entry = f"🔍 Kontrast-Probleme für: {link}\n"
            output_text.insert(tk.END, entry, "bold")
            log_content += entry + "\n"

            for issue in contrast_issues:
             # Versuche, mehr Details aus dem WebElement zu bekommen
             description = issue.get("description", "Keine Beschreibung verfügbar")
             impact = issue.get("impact", "Unbekannt")
             element = str(issue.get("element", "Unbekanntes Element"))

             if isinstance(issue.get("element"), webdriver.remote.webelement.WebElement):
              # Extrahiere tag_name oder text, um mehr Klarheit zu bieten
              element = issue["element"].tag_name + " - " + (issue["element"].text[:30] if issue["element"].text else "Kein Text vorhanden")

             entry = f"  ⚠️ Fehler: {description}\n  🔴 Schweregrad: {impact}\n  📌 Element: {element}\n\n"
             output_text.insert(tk.END, entry, "red")
             log_content += entry + "\n"

    output_text.config(state=tk.DISABLED)
    reset_ui()

# Stelle sicher, dass der Fortschrittsbalken immer sichtbar ist
def reset_ui():
    test_button.config(state=tk.NORMAL)
    progress_bar["value"] = 0  # Setze den Fortschritt auf 0 zurück
    status_label.config(text="Bereit für den nächsten Test")
    root.update_idletasks()  # UI sofort aktualisieren

def save_log():
    global log_content
    if not log_content.strip():
        messagebox.showwarning("Fehler", "Kein Log zum Speichern vorhanden!")
        return

    file_path = filedialog.asksaveasfilename(
        defaultextension=".txt",
        filetypes=[("Textdateien", "*.txt"), ("Alle Dateien", "*.*")]
    )

    if file_path:
        with open(file_path, "w", encoding="utf-8") as file:
            file.write(log_content)
        messagebox.showinfo("Gespeichert", f"Log gespeichert unter:\n{file_path}")

root = tk.Tk()
root.title("🌍 Barrierefreiheitstester")
root.geometry("800x800")
root.configure(bg="#f0f0f0")

style = ttk.Style()
style.configure("TButton", font=("Arial", 12), padding=10)
style.configure("TLabel", font=("Arial", 12), background="#f0f0f0")
style.configure("TEntry", padding=5, font=("Arial", 12))
style.configure("TFrame", background="#ffffff", relief="ridge", borderwidth=2)

header = ttk.Label(root, text="🌍 Barrierefreiheitstester", font=("Arial", 16, "bold"))
header.pack(pady=10)

input_frame = ttk.Frame(root)
input_frame.pack(pady=10, padx=20, fill="x")

url_label = ttk.Label(input_frame, text="🔗 Webseite URL:")
url_label.pack(side="left", padx=10)

url_entry = ttk.Entry(input_frame, width=50)
url_entry.pack(side="left", padx=5, expand=True, fill="x")

test_button = ttk.Button(input_frame, text="🔍 Test starten", command=test_accessibility)
test_button.pack(side="right", padx=10)

# Füge die Progressbar direkt zu Beginn hinzu, nicht nur während des Tests
progress_bar = ttk.Progressbar(root, orient="horizontal", length=400, mode="determinate")
progress_bar.pack(pady=10)
# Füge ein Label hinzu, um die Prozentanzeige anzuzeigen
progress_percentage = ttk.Label(root, text="0%", font=("Arial", 12))
progress_percentage.pack(pady=5)
status_label = ttk.Label(root, text="Bereit für den nächsten Test", font=("Arial", 10))
status_label.pack(pady=10)

output_frame = ttk.Frame(root)
output_frame.pack(pady=10, padx=20, fill="both", expand=True)

output_text = tk.Text(output_frame, wrap="word", width=80, height=20, font=("Arial", 10))
output_text.pack(side="left", fill="both", expand=True, padx=5, pady=5)
output_text.config(state=tk.DISABLED)

scrollbar = ttk.Scrollbar(output_frame, orient="vertical", command=output_text.yview)
scrollbar.pack(side="right", fill="y")
output_text.config(yscrollcommand=scrollbar.set)

# Variable zum Verfolgen, ob der Kontrast-Check aktiviert ist
contrast_check_enabled = tk.BooleanVar(value=True)  # Standardmäßig aktiviert
# Checkbox für den Kontrast-Check
contrast_check_var = tk.BooleanVar(value=True)  # Initialisiert mit aktiviertem Kontrast-Check
contrast_check_checkbox = ttk.Checkbutton(root, text="Kontrast-Check aktivieren", variable=contrast_check_var, command=toggle_contrast_check)
contrast_check_checkbox.pack(pady=5)

save_button = ttk.Button(root, text="📂 Log speichern", command=save_log)
save_button.pack(pady=10)

output_text.tag_configure("bold", font=("Arial", 10, "bold"))

root.mainloop()
