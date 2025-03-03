import tkinter as tk
from tkinter import messagebox, filedialog
from tkinter import ttk
import threading
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from axe_selenium_python import Axe
from urllib.parse import urljoin, urlparse
import time
import traceback  # Importiere das Modul für Fehlerbehandlung

log_content = ""  # Variable für gespeicherte Logs

# Funktion zum Abrufen aller Links auf einer Seite
def get_all_links(driver, base_url):
    links = set()
    elements = driver.find_elements("tag name", "a")
    
    for element in elements:
        href = element.get_attribute("href")
        if href:
            # Stelle sicher, dass href und base_url beide Strings sind
            if isinstance(href, str) and isinstance(base_url, str):
                full_url = urljoin(base_url, href)
                parsed_url = urlparse(full_url)

                # Überprüfe, ob der Hostname übereinstimmt
                if parsed_url.netloc == urlparse(base_url).netloc:
                    links.add(full_url)

    return links

# Funktion für den Barrierefreiheitstest
def test_accessibility():
    global log_content
    log_content = ""  # Log leeren
    test_button.config(state=tk.DISABLED)
    progress_bar.pack(pady=10)
    progress_bar.start()

    def run_test():
        url = url_entry.get()
        if not url:
            root.after(0, lambda: messagebox.showwarning("Fehler", "Bitte eine URL eingeben!"))
            root.after(0, progress_bar.stop)
            root.after(0, lambda: test_button.config(state=tk.NORMAL))
            return

        try:
            chrome_options = Options()
            chrome_options.add_argument("--headless")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--window-size=1920x1080")

            driver = webdriver.Chrome(options=chrome_options)
            driver.get(url)

            all_links = get_all_links(driver, url)
            all_links.add(url)

            violations = []

            for link in all_links:
                driver.get(link)
                time.sleep(2)

                axe = Axe(driver)
                axe.inject()
                results = axe.run()

                if results["violations"]:
                    violations.append((link, results["violations"]))

            root.after(0, update_output, violations)
            driver.quit()

        except Exception as e:
            error_message = traceback.format_exc()  # Detaillierte Fehlerausgabe
            print(f"Fehler: {error_message}")  # Fehler in der Konsole ausgeben
            root.after(0, lambda: messagebox.showerror("Fehler", f"Es gab einen Fehler:\n{error_message}"))
            root.after(0, progress_bar.stop)
            root.after(0, lambda: progress_bar.pack_forget())
            root.after(0, lambda: test_button.config(state=tk.NORMAL))

    threading.Thread(target=run_test, daemon=True).start()

# Funktion zum Aktualisieren des Textfelds
def update_output(violations):
    global log_content
    output_text.config(state=tk.NORMAL)
    output_text.delete(1.0, tk.END)
    log_content = ""  # Log zurücksetzen

    if violations:
        for link, issues in violations:
            entry = f"🔍 Ergebnisse für: {link}\n"
            output_text.insert(tk.END, entry, "bold")
            log_content += entry + "\n"

            for violation in issues:
                description = violation["description"]
                impact = violation["impact"]
                help_url = violation.get("help", "Keine Hilfe verfügbar")

                color = "red" if impact == "critical" else "orange" if impact == "moderate" else "blue"
                output_text.tag_configure(color, foreground=color)

                entry = f"  ⚠️ Fehler: {description}\n  🔴 Schwere: {impact.capitalize()}\n  📌 Hilfe: {help_url}\n\n"
                output_text.insert(tk.END, entry, color)
                log_content += entry + "\n"

                for node in violation["nodes"]:
                    entry = f"    🖹 Element: {str(node.get('html', 'Unbekannt'))}\n\n"
                    output_text.insert(tk.END, entry, color)
                    log_content += entry + "\n"

    else:
        messagebox.showinfo("Ergebnis", "✅ Keine Barrierefreiheitsverletzungen gefunden!")
        log_content = "✅ Keine Barrierefreiheitsverletzungen gefunden!"

    output_text.config(state=tk.DISABLED)

# Funktion zum Speichern des Logs
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

# GUI erstellen
root = tk.Tk()
root.title("🌍 Barrierefreiheitstester")
root.geometry("800x600")
root.configure(bg="#f0f0f0")

# Stil anpassen
style = ttk.Style()
style.configure("TButton", font=("Arial", 12), padding=10)
style.configure("TLabel", font=("Arial", 12), background="#f0f0f0")
style.configure("TEntry", padding=5, font=("Arial", 12))
style.configure("TFrame", background="#ffffff", relief="ridge", borderwidth=2)

# Header
header = ttk.Label(root, text="🌍 Barrierefreiheitstester", font=("Arial", 16, "bold"))
header.pack(pady=10)

# Container für Eingabefeld und Buttons
input_frame = ttk.Frame(root)
input_frame.pack(pady=10, padx=20, fill="x")

url_label = ttk.Label(input_frame, text="🔗 Webseite URL:")
url_label.pack(side="left", padx=10)

url_entry = ttk.Entry(input_frame, width=50)
url_entry.pack(side="left", padx=5, expand=True, fill="x")

test_button = ttk.Button(input_frame, text="🔍 Test starten", command=test_accessibility)
test_button.pack(side="right", padx=10)

# Ladebalken
progress_bar = ttk.Progressbar(root, orient="horizontal", length=400, mode="indeterminate")

# Container für das Textfeld und die Scrollbar
output_frame = ttk.Frame(root)
output_frame.pack(pady=10, padx=20, fill="both", expand=True)

output_text = tk.Text(output_frame, wrap="word", width=80, height=20, font=("Arial", 10))
output_text.pack(side="left", fill="both", expand=True, padx=5, pady=5)
output_text.config(state=tk.DISABLED)

scrollbar = ttk.Scrollbar(output_frame, orient="vertical", command=output_text.yview)
scrollbar.pack(side="right", fill="y")
output_text.config(yscrollcommand=scrollbar.set)

# Speichern-Button hinzufügen
save_button = ttk.Button(root, text="📂 Log speichern", command=save_log)
save_button.pack(pady=10)

# Textformatierungen für Farben und Überschriften
output_text.tag_configure("bold", font=("Arial", 10, "bold"))

# Hauptloop starten
root.mainloop()
