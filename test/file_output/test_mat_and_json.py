# -*- coding: utf-8 -*-
"""
hdsemg_select Output Verification Script

Dieses Skript überprüft, ob die von hdsemg_select erzeugte bereinigte .mat-Datei
nur die Kanäle enthält, die in der .json-Auswahldatei als 'selected: true'
markiert sind, und ob die Daten dieser ausgewählten Kanäle mit den Daten der
ursprünglichen .mat-Datei übereinstimmen.

Anforderungen:
- scipy (für das Laden von .mat-Dateien)
- numpy (für die Datenüberprüfung)
- json (Standard-Python-Bibliothek)
- tkinter (Standard-Python-Bibliothek für Dateidialoge)
"""

import json
import scipy.io
import numpy as np
import tkinter as tk
from tkinter import filedialog
import os

# --- Helferfunktion zum Öffnen eines Dateidialogs ---
def select_file(title, filetypes):
    """Öffnet einen Dateidialog zur Auswahl einer Datei."""
    root = tk.Tk()
    root.withdraw()  # Hauptfenster verstecken
    filepath = filedialog.askopenfilename(title=title, filetypes=filetypes)
    root.destroy()   # Wurzelobjekt zerstören
    return filepath

# --- Dateipfade vom Benutzer auswählen lassen ---
print("Bitte wählen Sie die Dateien über die folgenden Dialogfenster aus:")

json_path = select_file("Wählen Sie die JSON-Auswahl-Datei (.json)", [("JSON-Dateien", "*.json")])
if not json_path:
    print("JSON-Dateiauswahl abgebrochen.")
    # Beende das Skript, wenn keine JSON-Datei ausgewählt wurde
    # Dies ist eine einfache Form der Fehlerbehandlung in einem Notebook-Kontext
    # In einer komplexeren Anwendung würdest du vielleicht eine Ausnahme werfen
    # oder einen anderen Fluss steuern.
    raise FileNotFoundError("Es muss eine JSON-Datei ausgewählt werden.")


original_mat_path = select_file("Wählen Sie die ORIGINAL .mat-Datei mit allen Kanälen", [("MATLAB-Dateien", "*.mat")])
if not original_mat_path:
    print("Original .mat-Dateiauswahl abgebrochen.")
    raise FileNotFoundError("Es muss die ursprüngliche .mat-Datei ausgewählt werden.")


cleaned_mat_path = select_file("Wählen Sie die BEREINIGTE .mat-Datei (Output von hdsemg_select)", [("MATLAB-Dateien", "*.mat")])
if not cleaned_mat_path:
    print("Bereinigte .mat-Dateiauswahl abgebrochen.")
    raise FileNotFoundError("Es muss die bereinigte .mat-Datei ausgewählt werden.")

print("\nAusgewählte Dateien:")
print(f"JSON-Datei: {json_path}")
print(f"Original MAT-Datei: {original_mat_path}")
print(f"Bereinigte MAT-Datei: {cleaned_mat_path}")

# --- 1. JSON-Datei laden und ausgewählte Kanal-Indices extrahieren ---
print("\n--- Lade JSON-Auswahl ---")
selected_channel_indices = []
try:
    with open(json_path, 'r', encoding='utf-8') as f:
        selection_data = json.load(f)

    # Annahme: Die Kanalauswahl-Informationen befinden sich unter dem Schlüssel 'total_channels_summary'
    # und jedes Element hat einen 'channel_index' und einen 'selected' Status.
    if 'total_channels_summary' in selection_data:
        for channel_info in selection_data['total_channels_summary']:
            # Überprüfe, ob 'selected' True ist. Verwende .get() für Robustheit.
            # channel_index wird für die Indizierung von NumPy-Arrays verwendet (0-basiert)
            if channel_info.get('selected', False):
                selected_channel_indices.append(channel_info.get('channel_index'))

        # Filtere None-Werte heraus, falls 'channel_index' fehlt (sollte nicht passieren, aber zur Sicherheit)
        selected_channel_indices = [idx for idx in selected_channel_indices if idx is not None]

        print(f"Erfolgreich geladen. {len(selected_channel_indices)} Kanäle sind laut JSON ausgewählt ('selected: true').")
        if not selected_channel_indices:
            print("Warnung: Laut JSON wurden keine Kanäle ausgewählt.")

    else:
        print("Fehler: JSON-Struktur unerwartet. Schlüssel 'total_channels_summary' nicht gefunden.")
        selection_data = None # Markiere als Fehlerfall

except FileNotFoundError:
    print(f"Fehler: JSON-Datei nicht gefunden unter {json_path}")
    selection_data = None
except json.JSONDecodeError:
    print(f"Fehler: JSON-Datei konnte nicht dekodiert werden. Ist die Datei gültig? {json_path}")
    selection_data = None
except KeyError as e:
    print(f"Fehler: Fehlender erwarteter Schlüssel in der JSON-Struktur des Kanaleintrags: {e}")
    selection_data = None
except Exception as e:
    print(f"Ein unerwarteter Fehler trat beim Laden der JSON-Datei auf: {e}")
    selection_data = None


# --- 2. Originale und bereinigte .mat-Dateien laden ---
print("\n--- Lade .mat-Dateien ---")
original_mat_data = None
cleaned_mat_data = None
original_data_array = None
cleaned_data_array = None

# Annahme: Der Hauptdatenarray in den .mat-Dateien heißt 'data'.
# Wenn dein Datenarray einen anderen Namen hat, ändere 'data_key'
data_key = 'Data'

if selection_data is not None: # Nur fortfahren, wenn JSON erfolgreich geladen wurde
    try:
        original_mat_data = scipy.io.loadmat(original_mat_path)
        print(f"Original .mat-Datei geladen: {original_mat_path}")

        if data_key in original_mat_data:
             original_data_array = original_mat_data[data_key]
             print(f"Shape der Originaldaten: {original_data_array.shape}")
        else:
             print(f"Fehler: Schlüssel '{data_key}' nicht in der ursprünglichen .mat-Datei gefunden.")
             print("Verfügbare Schlüssel:", original_mat_data.keys())
             original_mat_data = None # Markiere als Fehlerfall


        cleaned_mat_data = scipy.io.loadmat(cleaned_mat_path)
        print(f"Bereinigte .mat-Datei geladen: {cleaned_mat_path}")

        if data_key in cleaned_mat_data:
            cleaned_data_array = cleaned_mat_data[data_key]
            print(f"Shape der bereinigten Daten: {cleaned_data_array.shape}")
        else:
            print(f"Fehler: Schlüssel '{data_key}' nicht in der bereinigten .mat-Datei gefunden.")
            print("Verfügbare Schlüssel:", cleaned_mat_data.keys())
            cleaned_mat_data = None # Markiere als Fehlerfall


    except FileNotFoundError:
        print("Fehler beim Laden der .mat-Dateien. Überprüfen Sie die Pfade.")
        original_mat_data = None
        cleaned_mat_data = None
    except Exception as e: # Andere potenzielle Ladefehler abfangen
         print(f"Ein unerwarteter Fehler trat beim Laden der .mat-Dateien auf: {e}")
         original_mat_data = None
         cleaned_mat_data = None


# --- 3. Überprüfungen durchführen ---
print("\n--- Führe Überprüfungen durch ---")

if original_data_array is not None and cleaned_data_array is not None and selected_channel_indices is not None:

    # Überprüfung 1: Anzahl der Kanäle in der bereinigten Datei vs. erwartete Anzahl
    expected_num_channels = len(selected_channel_indices)
    # Annahme: Kanäle sind die 2. Dimension (Spalten) im Datenarray
    actual_num_channels = cleaned_data_array.shape[1]

    print(f"Erwartete Anzahl Kanäle in bereinigter Datei (laut JSON): {expected_num_channels}")
    print(f"Tatsächliche Anzahl Kanäle in bereinigter Datei: {actual_num_channels}")

    if expected_num_channels == actual_num_channels:
        print("Überprüfung 1 (Anzahl Kanäle): PASSED.")
    else:
        print("Überprüfung 1 (Anzahl Kanäle): FAILED. Die Anzahl der Kanäle in der bereinigten Datei stimmt nicht mit der Auswahl in der JSON überein.")

    # Überprüfung 2: Dateninhalt der bereinigten Kanäle vs. Originaldaten der ausgewählten Kanäle
    # Diese Überprüfung macht nur Sinn, wenn die Anzahl der Kanäle übereinstimmt
    if expected_num_channels == actual_num_channels:
        try:
            # Extrahiere die Daten der ausgewählten Kanäle aus dem Original-Array
            # Stelle sicher, dass die Indices sortiert sind, falls die App die Kanäle neu anordnet (unwahrscheinlich, aber sicher ist sicher)
            # sorted_selected_indices = sorted(selected_channel_indices) # Normalerweise nicht nötig, wenn Indices 0-basiert sind und die App einfach die ausgewählten Spalten nimmt.
            # Wir verwenden die Indices, wie sie aus der JSON kommen, da das die Reihenfolge sein sollte, die die App verwendet.
            original_data_selected = original_data_array[:, selected_channel_indices]

            # Vergleiche die extrahierten Originaldaten mit den Daten aus der bereinigten Datei
            # numpy.allclose ist besser für Floating-Point-Vergleiche als ==
            # rtol (relative tolerance) und atol (absolute tolerance) können angepasst werden,
            # falls es durch Speichern/Laden zu minimalen Rundungsfehlern kommt.
            tolerance_rtol = 1e-5 # Standardwert
            tolerance_atol = 1e-8 # Standardwert

            if np.allclose(original_data_selected, cleaned_data_array, rtol=tolerance_rtol, atol=tolerance_atol):
                print("Überprüfung 2 (Dateninhalt): PASSED. Die Daten der ausgewählten Kanäle stimmen überein.")
            else:
                print("Überprüfung 2 (Dateninhalt): FAILED. Die Daten in der bereinigten Datei stimmen NICHT exakt mit den Daten der ausgewählten Kanäle aus der Originaldatei überein.")
                # Optional: Mehr Details zum Unterschied anzeigen
                # diff = original_data_selected - cleaned_data_array
                # print(f"Maximale absolute Differenz: {np.max(np.abs(diff))}")
                # print(f"Summe der absoluten Differenzen: {np.sum(np.abs(diff))}")

        except IndexError:
            print("Überprüfung 2 (Dateninhalt): FAILED. Fehler bei der Indizierung. Stimmen die channel_index-Werte in der JSON mit der Shape der Originaldaten überein?")
            print(f"Originaldaten Shape: {original_data_array.shape}, JSON-Indices: {selected_channel_indices}")
        except Exception as e:
            print(f"Überprüfung 2 (Dateninhalt): FAILED. Ein unerwarteter Fehler trat während des Datenvergleichs auf: {e}")
    else:
        print("Überprüfung 2 (Dateninhalt): Übersprungen, da die Anzahl der Kanäle nicht übereinstimmt.")

else:
    print("\nÜberprüfungen konnten nicht durchgeführt werden, da Dateien nicht geladen oder JSON nicht korrekt gelesen werden konnte.")

print("\n--- Überprüfung abgeschlossen ---")