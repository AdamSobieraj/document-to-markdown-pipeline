# Document to Markdown Converter

System ETL do konwersji dokumentów (PDF, DOCX, XLSX, TXT) na Markdown z automatycznym parsowaniem, budową metadanych i zapisem do S3 lub lokalnego systemu plików.

---

## Kluczowe Funkcjonalności

*   **Modułowa architektura ETL:** Pipeline z jasno oddzielonymi etapami (Load → Parse → Save).
*   **Wieloźródłowa obsługa:**
    *   **S3/MinIO** - bucket + prefix
    *   **Lokalne pliki** - katalog + rekurencyjne skanowanie
*   **Inteligentny parser selector:** Automatyczny dobór parsera według rozszerzenia pliku.
*   **Profile konfiguracyjne:** Wczytywanie YAML z mergowaniem `default.yaml` + `<profile>.yaml`.
*   **Walidacja Pydantic:** Wszystkie parametry, wyniki i metadane są walidowane przed użyciem.
*   **Robust error handling:** Każda operacja zwraca strukturalny wynik (nigdy `None`), z logowaniem błędów.

---

## Wymagane biblioteki

### Bez uv
```bash
pip install pypdf python-docx openpyxl pandas  # parsery
pip install boto3 botocore  # S3
pip install pydantic pyyaml python-dotenv  # konfiguracja i walidacja
```

### Z użyciem uv
```bash
uv sync
```

---

## Konfiguracja

### 1. Struktura plików konfiguracyjnych

```
config/
├── default.yaml                    # Wspólne ustawienia
├── business_knowledge_base.yaml    # Profil 1
├── technical_knowledge_base.yaml   # Profil 2
└── message_schemas_knowledge_base.yaml  # Profil 3
```

### 2. Przykładowy `config/default.yaml`

```yaml
source-type: s3       # "s3" lub "local"
dest-type: s3         # opcjonalne, domyślnie = source-type
bucket: my-bucket
prefix: documents/
out-bucket: my-output-bucket  # opcjonalne, domyślnie = bucket
debug: false
```

### 3. Przykładowy `config/business_knowledge_base.yaml`

```yaml
# Merguje się z default.yaml
prefix: business/
out-bucket: ragmini-processed
```

### 4. Konfiguracja `.env`

Stwórz plik `.env` w katalogu głównym:

```ini
# --- S3 / MinIO ---
S3_ENDPOINT=https://s3.example.local:9000
S3_ACCESS_KEY_ID=your-access-key
S3_SECRET_ACCESS_KEY=your-secret-key
S3_REGION=us-east-1

# --- Opcjonalne: TLS dla prywatnego S3 ---
S3_CA_BUNDLE=/path/to/root-ca.pem
# lub
AWS_CA_BUNDLE=/path/to/root-ca.pem
```

**Uwagi:**
- Jeśli używasz prywatnego S3 z własnym CA, umieść plik `root-ca.pem` w głównym katalogu projektu – zostanie automatycznie wykryty.
- Dla lokalnych plików, sekcja S3 nie jest wymagana.

---

## Użycie

### Tryb CLI (rekomendowany)

```bash
# Konwersja z użyciem profilu
python MarkdownConverter.py

# Lub z flagami CLI (nadpisują YAML)
python MarkdownConverter.py --profile business_knowledge_base --bucket ragmini
```

### Tryb programowy

```python
from MarkdownConverter import MarkDownConverter

# Źródło: S3
converter = MarkDownConverter(
    source_type="s3",
    destination_type="s3",
    bucket_name="my-bucket",
    prefix="docs/",
    output_bucket="my-output-bucket"
)

# Lub źródło: lokalne
converter = MarkDownConverter(
    source_type="local",
    directory="./input_docs",
    output_directory="./output_markdown"
)

# Przetwórz wszystkie pliki
results = converter.process_all_files()

# Lub pojedynczy plik
result = converter.process_single_file("folder/document.pdf")
```

---

## Pipeline Processing Flow

```
┌─────────────────────────────────────────────────────────────┐
│ 1. LOAD: Pobierz plik z S3 lub dysku                       │
├─────────────────────────────────────────────────────────────┤
│ 2. SELECT PARSER: Wybierz parser (PDF/DOCX/XLSX/TXT)       │
├─────────────────────────────────────────────────────────────┤
│ 3. PARSE: Konwertuj dokument → Markdown + metadata         │
├─────────────────────────────────────────────────────────────┤
│ 4. SAVE:                                                    │
│    • Zapisz Markdown do S3/dysku                            │
│    • Zbuduj metadata (source_url, domain, timestamps)      │
│    • Zapisz metadata.json                                   │
│    • Wzbogać dokumenty o metadane                           │
└─────────────────────────────────────────────────────────────┘
```

---

## Obsługiwane formaty

| Format | Parser | Wymagana biblioteka |
|--------|--------|---------------------|
| `.pdf` | PDFParser | `pypdf` |
| `.docx` | DOCXParser | `python-docx` |
| `.xlsx` | XLSXParser | `openpyxl`, `pandas` |
| `.txt` | TXTParser | (built-in) |

---

## Struktura wyjściowa

### Przykład dla S3:

```
Źródło:   s3://my-bucket/business/report.pdf
Wyjście:  s3://my-bucket/business_markdown/report.md
          s3://my-bucket/business_markdown/report_metadata.json
```

### Przykład dla lokalnych plików:

```
Źródło:   ./inputs/docs/report.pdf
Wyjście:  ./inputs/docs_markdown/report.md
          ./inputs/docs_markdown/report_metadata.json
```

---

## Profile konfiguracyjne

### Business Knowledge Base

```bash
python MarkdownConverter.py --profile business_knowledge_base --bucket ragmini
```

**Oczekiwane:**
- Prefix: `business/`
- Wyjście: `business_markdown/`

### Technical Knowledge Base

```bash
python MarkdownConverter.py --profile technical_knowledge_base --bucket ragmini
```

**Oczekiwane:**
- Prefix według konfiguracji profilu
- Wyjście: `<prefix>_markdown/`

### Message Schemas Knowledge Base

```bash
python MarkdownConverter.py --profile message_schemas_knowledge_base --bucket ragmini
```

**Oczekiwane:**
- Prefix według konfiguracji profilu
- Wyjście: `<prefix>_markdown/`

---

## Expected Log Flow

Podczas poprawnego przebiegu zobaczysz logi podobne do:

```
INFO - Config profile loaded successfully: business_knowledge_base
INFO - MarkDownConverter initialized: S3 -> S3
INFO - Found 15 files. Starting processing pipeline...
INFO - Processing file 1/15: business/General/guide.pdf
DEBUG - Step 1: Loading raw data for business/General/guide.pdf
DEBUG - Step 2: Selecting parser for business/General/guide.pdf
DEBUG - Step 3: Parsing business/General/guide.pdf to Markdown
DEBUG - Step 4: Saving Markdown and building metadata
INFO - Metadata saved to: business/General_markdown/guide_metadata.json
INFO - Successfully processed business/General/guide.pdf: 5 documents
INFO - Pipeline completed. Success: 14, Errors: 1, Total: 15
```

---

## Troubleshooting

### Błędy certyfikatu S3 (Private S3)

**Problem:**
```
SSLError: certificate verify failed
```

**Rozwiązanie:**
1. Ustaw zmienną środowiskową:
   ```ini
   S3_CA_BUNDLE=/path/to/root-ca.pem
   # lub
   AWS_CA_BUNDLE=/path/to/root-ca.pem
   ```
2. Lub umieść plik `root-ca.pem` w głównym katalogu projektu (auto-detect).

### Brak danych po przetworzeniu

**Problem:**
```
WARNING - No data loaded for file.pdf
```

**Możliwe przyczyny:**
- Plik nie istnieje w źródle
- Brak uprawnień S3 (sprawdź `S3_ACCESS_KEY_ID`)
- Nieprawidłowy prefix w konfiguracji

**Rozwiązanie:**
```bash
# Sprawdź listę plików
aws s3 ls s3://my-bucket/business/ --recursive

# Sprawdź uprawnienia
aws s3 ls s3://my-bucket/
```

### Parser nie znaleziony

**Problem:**
```
ERROR - No parser available for unknown.xyz
```

**Rozwiązanie:**
- System obsługuje tylko: `.pdf`, `.docx`, `.xlsx`, `.txt`
- Dodaj własny parser w `parsers/` i zarejestruj w `ParserSelector`

### Metadata builder zwraca None

**Problem:**
```
ERROR - Metadata builder returned None for file.pdf
```

**Rozwiązanie:**
- To błąd wewnętrzny – sprawdź logi dla stack trace
- System automatycznie zwróci pusty dict `{}` jako fallback

---

## Struktura plików projektu

```
.
├── MarkdownConverter.py           # Główny pipeline orchestrator
├── LoadConfig.py                  # Loader konfiguracji YAML + ENV merge
├── builders/
│   └── metadata_builder.py        # Budowa metadanych dokumentów
├── interfaces/
│   ├── DataLoader.py              # Abstrakcja dla loaderów
│   └── DataSaver.py               # Abstrakcja dla saverów
├── loaders/
│   ├── DataLoaderS3.py            # Loader dla S3/MinIO
│   └── DataLoaderLocal.py         # Loader dla lokalnych plików
├── savers/
│   ├── DataSaverS3.py             # Saver dla S3/MinIO
│   └── DataSaverLocal.py          # Saver dla lokalnych plików
├── parsers/
│   ├── ParserSelector.py          # Factory parserów
│   ├── PDFParser.py
│   ├── DOCXParser.py
│   ├── XLSXParser.py
│   └── TXTParser.py
├── validators/
│   └── __init__.py                # Modele Pydantic (ConverterConfig, ProcessingResult)
└── config/
    ├── default.yaml
    └── <profile>.yaml
```

---

## Walidacja wyników

Każdy wynik przetwarzania jest walidowany przez Pydantic i zawiera:

```python
{
    "file_key": "business/file.pdf",
    "status": "success" | "error" | "empty",
    "document_count": 5,  # tylko dla success
    "metadata": {
        "source_url": "s3://bucket/business/file.pdf",
        "markdown_url": "s3://bucket/business_markdown/file.md",
        "domain": "business",
        "created_at": "2024-01-15T10:30:00Z",
        # ...
    },
    "documents": [...],  # lista Document objects
    "error": "..."  # tylko dla status=error
}
```

---

## Docker

### Minimal Dockerfile

```dockerfile
FROM python:3.12-slim

WORKDIR /app

# Opcjonalnie: dla prywatnego S3
COPY root-ca.pem /usr/local/share/ca-certificates/localca.crt
RUN apt-get update && apt-get install -y ca-certificates && \
    update-ca-certificates && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "MarkdownConverter.py"]
```

### Build & Run

```bash
# Build
docker build -t markdown-converter .

# Run z ENV
docker run --env-file .env markdown-converter

# Lub z volumeami dla lokalnych plików
docker run -v ./inputs:/app/inputs -v ./outputs:/app/outputs markdown-converter
```

---

## Licencja

MIT