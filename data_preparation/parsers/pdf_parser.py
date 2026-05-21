import base64
import io
import logging
import os
import sys
import time
import json
from typing import Dict, List, Optional, Tuple, Union

from dotenv import load_dotenv
from langchain_core.documents import Document

from .base_parser import BaseDocumentParser

load_dotenv()

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stdout)

try:
    import fitz  # PyMuPDF

    FITZ_AVAILABLE = True
except ImportError:
    FITZ_AVAILABLE = False
    logger.error("PyMuPDF (fitz) jest wymagany do konwersji PDF na obrazy.")

try:
    from openai import OpenAI

    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    logger.error("Biblioteka 'openai' jest wymagana do komunikacji z endpointem vision.")


class PdfParser(BaseDocumentParser):
    """
    PDF parser using a local OpenAI-compatible vision model.
    """

    def __init__(
        self,
        temperature: float = 0.0,
        dpi_scale: float = 1.2,
        top_margin_crop: float = 50.0,
        bottom_margin_crop: float = 60.0,
        left_margin_crop: float = 0.0,
        right_margin_crop: float = 0.0,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        custom_headers: Optional[Dict[str, str]] = None,
    ):
        if not FITZ_AVAILABLE or not OPENAI_AVAILABLE:
            raise ImportError("Zainstaluj wymagania: pip install pymupdf openai")

        self.temperature = temperature
        self.dpi_scale = dpi_scale
        self.base_url = base_url or os.getenv("LLM_BASE_URL") or os.getenv("CHAT_BASE_URL")
        self.model_name = model or os.getenv("LLM_MODEL") or os.getenv("CHAT_MODEL")
        self.api_key = (
            api_key
            or os.getenv("LLM_API_KEY")
            or os.getenv("CHAT_API_KEY")
            or os.getenv("OPENAI_API_KEY")
        )

        if not self.base_url:
            raise ValueError(
                "Brak konfiguracji URL dla parsera PDF. "
                "Ustaw LLM_BASE_URL albo CHAT_BASE_URL."
            )
        if not self.model_name:
            raise ValueError(
                "Brak konfiguracji modelu dla parsera PDF. "
                "Ustaw LLM_MODEL albo CHAT_MODEL."
            )
        if not self.api_key:
            # The OpenAI SDK requires a non-empty api_key even for local
            # OpenAI-compatible servers that ignore authorization.
            self.api_key = "EMPTY"
            logger.info(
                "PdfParser: brak jawnego API key; uzywam placeholdera dla %s.",
                self.base_url,
            )

        # ────────────────────────────────────────────────────────
        # DODANE: Odczyt custom headers z ENV przez DEFAULT_HEADERS
        # ────────────────────────────────────────────────────────
        self.custom_headers = custom_headers or {}

        default_headers_json = os.getenv("DEFAULT_HEADERS")
        if default_headers_json:
            try:
                parsed_headers = json.loads(default_headers_json)
                self.custom_headers.update(parsed_headers)
                logger.info("Dodano custom headers z DEFAULT_HEADERS: %s", list(parsed_headers.keys()))
            except json.JSONDecodeError as e:
                logger.warning("Nie można sparsować DEFAULT_HEADERS z ENV: %s", e)
        # ────────────────────────────────────────────────────────

        # Timeout na 10 minut, żeby połączenie nie zerwało się przy trudnych stronach
        self.client = OpenAI(
            base_url=self.base_url,
            api_key=self.api_key,
            timeout=600.0,
            default_headers=self.custom_headers if self.custom_headers else None,
        )
        # ── Marginesy ────────────────────────────────────────────
        self._top_margin = top_margin_crop
        self._bottom_margin = bottom_margin_crop
        self._left_margin = left_margin_crop
        self._right_margin = right_margin_crop
        self._margins_enabled = any(
            [top_margin_crop, bottom_margin_crop, left_margin_crop, right_margin_crop]
        )

        logger.info(
            "Vision parser zainicjalizowany (URL: %s, Model: %s, Headers: %s).",
            self.base_url,
            self.model_name,
            list(self.custom_headers.keys()) if self.custom_headers else "brak",
        )

        self.system_prompt = (
            "You are an expert document OCR and layout parsing assistant. "
            "Extract the text, tables, and formatting from the provided document image "
            "and output it EXACTLY as clean Markdown. "
            "Rules:\n"
            "- Preserve heading levels (#, ##, etc.)\n"
            "- Convert tables to Markdown tables.\n"
            "- Do not add ANY conversational filler (e.g., 'Here is the markdown:').\n"
            "- Stop generating immediately when you reach the end of the page content."
        )
    # ══════════════════════════════════════════════════════════════
    # INTERFEJS PUBLICZNY
    # ══════════════════════════════════════════════════════════════
    def parse(
        self,
        file_source: Union[str, io.BytesIO, bytes],
        **kwargs,
    ) -> List[Document]:
        source_name = self._get_source_name(file_source)
        documents: List[Document] = []

        try:
            pdf_doc, original_page_dims = self._load_and_precrop_pdf(file_source)
            total_pages = len(pdf_doc)
            # --- WYRAŹNY LOG STARTOWY ---
            logger.info("=" * 60)
            logger.info("ROZPOCZETO PRZETWARZANIE: %s", source_name)
            logger.info("Liczba stron do przetworzenia: %s", total_pages)
            logger.info("=" * 60)

            for page_idx in range(total_pages):
                page_no = page_idx + 1
                page = pdf_doc[page_idx]

                logger.info("\n[STRONA %s/%s] Przygotowywanie obrazu...", page_no, total_pages)
                start_time = time.time()
                 # Konwersja strony PDF do Base64 JPEG
                base64_image = self._pdf_page_to_base64(page)
                payload_mb = len(base64_image) / (1024 * 1024)

                logger.info(
                    "[STRONA %s/%s] Wysylanie do endpointu vision (Rozmiar: %.2f MB)...",
                    page_no,
                    total_pages,
                    payload_mb,
                )

                md_text = self._call_vision_llm(base64_image)
                elapsed_time = time.time() - start_time

                if md_text:
                    logger.info(
                        "[STRONA %s/%s] Zakonczono sukcesem! (Czas: %.1f sek.)",
                        page_no,
                        total_pages,
                        elapsed_time,
                    )

                    metadata = {
                        "page_number": page_no,
                        "total_pages": total_pages,
                        "source": source_name,
                        "parser": "openai_compatible_vision",
                        "margin_top_pt": self._top_margin,
                        "margin_bottom_pt": self._bottom_margin,
                    }
                    if original_page_dims and page_no in original_page_dims:
                        metadata["original_page_width_pt"] = original_page_dims[page_no][0]
                        metadata["original_page_height_pt"] = original_page_dims[page_no][1]

                    documents.append(
                        Document(page_content=md_text.strip(), metadata=metadata)
                    )
                else:
                    logger.error(
                        "[STRONA %s/%s] Blad! Zwrocono pusty tekst. (Czas: %.1f sek.)",
                        page_no,
                        total_pages,
                        elapsed_time,
                    )

            pdf_doc.close()

            logger.info("=" * 60)
            logger.info(
                "ZAKONCZONO PRZETWARZANIE: %s (Sukces: %s/%s stron)",
                source_name,
                len(documents),
                total_pages,
            )
            logger.info("=" * 60)

            return documents
        except Exception as exc:
            logger.error("Blad parsera vision (%s): %s", source_name, exc, exc_info=True)
            return documents

    def diagnostics(self) -> Dict[str, str]:
        return {
            "engine": "OpenAI-compatible Vision",
            "model_name_requested": self.model_name,
            "base_url": self.base_url,
            "dpi_scale": str(self.dpi_scale),
            "margins_enabled": str(self._margins_enabled),
            "custom_headers": str(list(self.custom_headers.keys())) if self.custom_headers else "brak",
        }
    # ══════════════════════════════════════════════════════════════
    # WARSTWA 1: Wczytywanie i PRE-CROP (PyMuPDF cropbox)
    # ══════════════════════════════════════════════════════════════
    def _load_and_precrop_pdf(
        self, file_source: Union[str, io.BytesIO, bytes]
    ) -> Tuple["fitz.Document", Dict[int, Tuple[float, float]]]:
        if isinstance(file_source, str):
            pdf_doc = fitz.Document(file_source)
        elif isinstance(file_source, bytes):
            pdf_doc = fitz.Document(stream=file_source, filetype="pdf")
        elif isinstance(file_source, io.BytesIO):
            file_source.seek(0)
            pdf_doc = fitz.Document(stream=file_source.read(), filetype="pdf")
        else:
            raise ValueError(f"Nieobslugiwany typ: {type(file_source)}")

        original_dims: Dict[int, Tuple[float, float]] = {}

        for page_idx, page in enumerate(pdf_doc):
            rect = page.rect
            original_dims[page_idx + 1] = (rect.width, rect.height)

            if self._margins_enabled:
                new_x0 = rect.x0 + self._left_margin
                new_y0 = rect.y0 + self._top_margin
                new_x1 = rect.x1 - self._right_margin
                new_y1 = rect.y1 - self._bottom_margin

                if (new_x1 - new_x0) > 100 and (new_y1 - new_y0) > 100:
                    page.set_cropbox(fitz.Rect(new_x0, new_y0, new_x1, new_y1))

        return pdf_doc, original_dims

    def _pdf_page_to_base64(self, page: "fitz.Page") -> str:
        mat = fitz.Matrix(self.dpi_scale, self.dpi_scale)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        img_data = pix.tobytes("jpeg")
        return base64.b64encode(img_data).decode("utf-8")

    # ══════════════════════════════════════════════════════════════
    # WYWOŁANIE LLM (Vision API)
    # ══════════════════════════════════════════════════════════════
    def _call_vision_llm(self, base64_image: str) -> Optional[str]:
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {
                        "role": "system",
                        "content": self.system_prompt,
                    },
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": "Extract all text and layout from this document page into Markdown.",
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}"
                                },
                            },
                        ],
                    },
                ],
                temperature=self.temperature,
                max_tokens=4000,
                # ZABEZPIECZENIA PRZED NIESKOŃCZONĄ PĘTLĄ HALUCYNACJI:
                top_p=0.1,  # Zmniejsza losowość do minimum
                stop=["<|im_end|>", "<|endoftext|>", "</s>", "```\n\nUser:"],
            )
            return response.choices[0].message.content
        except Exception as exc:
            logger.error("Blad polaczenia z serwerem wizyjnym: %s", exc)
            return None

    @staticmethod
    def _get_source_name(file_source: Union[str, io.BytesIO, bytes]) -> str:
        if isinstance(file_source, str):
            return os.path.basename(file_source)
        return "strumien_pamieci"
