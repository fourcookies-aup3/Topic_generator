# Topic Generator für Präsentationen

Erzeugt ein Präsentations-Topic mit **beliebig vielen Unterkapiteln** und gibt Tipps für den Vortrag. Es gibt **keine Limits** bei der Auswahl: ein einziges Unterkapitel genauso wie 100 oder mehr. Grosse Auswahlen werden automatisch in Teilen (je 8 Unterkapitel) bei Groq angefragt, bei Rate-Limit wartet das Programm selbst und versucht es erneut.

Vorgegeben sind 27 Unterkapitel (eigene fügst du links unten mit **+ Eigenes** hinzu, Rechtsklick entfernt sie wieder):
- **Regionen (7):** Europa, Nordamerika, Südamerika, Asien, Afrika, Ozeanien, Naher Osten
- **Themen (20):** Geschichte, Technik, Natur, Mensch, Gesellschaft, Wirtschaft, Politik, Kultur, Wissenschaft, Umwelt & Klima, Gesundheit, Bildung, Kunst & Architektur, Religion & Philosophie, Sport, Medien & Kommunikation, Energie, Mobilität & Verkehr, Ethik & Recht, Zukunft & Ausblick

Die Vorgaben kannst du dauerhaft in `groq_client.py` unter `CATEGORY_GROUPS` ändern.

## Oberfläche
Dunkles Fantasy-Design (Violett, abgeschnittene Ecken, Rahmen) nach dem Vorbild des Fantasy-Style-GUI-Packs. Die Antwort entsteht live im Fenster: Titel, Zusammenfassung und jedes Unterkapitel erscheinen als Karte, sobald Groq es fertig hat. Ein Fortschrittsbalken zeigt, wie viele Unterkapitel schon da sind. Im Terminal wird nichts ausgegeben.
Ist eine Fantasy-Schrift installiert (z. B. MedievalSharp, Metamorphous oder Cinzel), wird sie für Überschriften genutzt, sonst Georgia.

## Einrichtung
1. Python 3.9+ installieren (tkinter ist bei Windows dabei, keine weiteren Pakete nötig).
2. `.env.example` kopieren, in `.env` umbenennen und den Groq API Key eintragen:
   `GROQ_API_KEY=gsk_...`
3. `start.bat` doppelklicken (oder `python topic_generator.py`).

## Nutzung
Themenbereich (optional), Zielgruppe, Dauer, Sprache und Unterkapitel wählen (beliebig viele) -> **Topic generieren** -> optional **Tipps generieren** -> **Als Datei speichern**.

## Modell
Standard ist `openai/gpt-oss-120b` (Groq hat `llama-3.3-70b-versatile` am 16.08.2026 abgeschaltet, das gab HTTP 404).
Ist ein Modell nicht verfügbar, probiert das Programm automatisch `qwen/qwen3.6-27b` und danach `openai/gpt-oss-20b`.
Eigenes Modell: in der `.env` die Zeile `GROQ_MODEL=modellname` ergänzen (Modelle: console.groq.com/docs/models).

## Key-Nutzung (strikt begrenzt)
Der Key wird in `groq_client.py` nur für zwei Zwecke verwendet: `topic` und `tips`.
Jeder andere Zweck wird blockiert (`ALLOWED_PURPOSES`). Der Key wird nie ausgegeben oder gespeichert ausser in deiner `.env`.
Teile die `.env` nie und lade sie nicht auf GitHub hoch (steht in `.gitignore`).
