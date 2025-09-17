import argparse, json, os, pathlib
from typing import List, Dict
from pypdf import PdfReader
from sentence_transformers import SentenceTransformer
import numpy as np
import faiss

def read_pdf_chunks(pdf_path: pathlib.Path, max_chars=1000, stride=800):
    """Extract text per page with sliding window overlap."""
    reader = PdfReader(str(pdf_path))
    chunks = []
    for page_number, page in enumerate(reader.pages, start=1):
        txt = (page.extract_text() or "").strip()
        if not txt:
            continue
        i = 0
        n = len(txt)
        while i < n:
            chunk = txt[i:i + max_chars]
            if chunk.strip():
                chunks.append({"page": page_number, "text": chunk})
            i += stride
    return chunks

def build_index(pdf_dir: pathlib.Path, out_dir: pathlib.Path, base_pdf_url: str = ""):
    out_dir.mkdir(parents=True, exist_ok=True)
    model_name = "all-MiniLM-L6-v2"
    model = SentenceTransformer(model_name)

    texts: List[str] = []
    meta: List[Dict] = []
    pdfs = sorted(pdf_dir.glob("**/*.pdf"))
    if not pdfs:
        raise SystemExit(f"No PDFs found under: {pdf_dir}")

    for pdf in pdfs:
        product = pdf.stem
        for chunk in read_pdf_chunks(pdf):
            page = chunk["page"]
            first_line = chunk["text"].splitlines()[0].strip() if chunk["text"].strip() else ""
            meta.append({
                "product": product,
                "section": first_line,
                "page_start": page,
                "page_end": page,
                "pdf_hint": f"{base_pdf_url}{pdf.name}#page={page}" if base_pdf_url else f"{pdf.name}#page={page}",
                "source": str(pdf.relative_to(pdf_dir))
            })
            texts.append(chunk["text"])

    embeddings = model.encode(texts, batch_size=64, show_progress_bar=True, normalize_embeddings=True)
    embeddings = np.array(embeddings, dtype="float32")
    dim = embeddings.shape[1]

    index = faiss.IndexFlatIP(dim)
    index.add(embeddings)
    faiss_path = out_dir / "faiss.index"
    faiss.write_index(index, str(faiss_path))

    meta_path = out_dir / "meta.jsonl"
    with open(meta_path, "w", encoding="utf-8") as f:
        for entry in meta:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    model_path = out_dir / "model.json"
    with open(model_path, "w", encoding="utf-8") as f:
        json.dump({
            "model": model_name,
            "dim": dim,
            "count": int(index.ntotal)
        }, f)

    print(f"Index built: {out_dir} (rows={index.ntotal}, dim={dim})")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf_dir", required=True, help="Folder with SDS PDFs")
    parser.add_argument("--out_dir", default="data/index", help="Output folder for index & metadata")
    parser.add_argument("--base_pdf_url", default="", help="Optional absolute base URL for PDFs")
    args = parser.parse_args()
    build_index(pathlib.Path(args.pdf_dir), pathlib.Path(args.out_dir), args.base_pdf_url)
