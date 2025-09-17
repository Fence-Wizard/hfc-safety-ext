import argparse, json, os, pathlib, math
from typing import List, Dict
from pypdf import PdfReader
from sentence_transformers import SentenceTransformer
import numpy as np
import faiss

def read_pdf_chunks(pdf_path: pathlib.Path, max_chars=1000, stride=800):
    """Extract text per page; chunk with overlap."""
    reader = PdfReader(str(pdf_path))
    chunks = []
    for p, page in enumerate(reader.pages, start=1):
        txt = (page.extract_text() or "").strip()
        if not txt:
            continue
        i = 0
        n = len(txt)
        while i < n:
            chunk = txt[i:i+max_chars]
            if chunk.strip():
                chunks.append({"page": p, "text": chunk})
            i += stride
    return chunks

def build_index(pdf_dir: pathlib.Path, out_dir: pathlib.Path, base_pdf_url: str = ""):
    out_dir.mkdir(parents=True, exist_ok=True)
    model_name = "all-MiniLM-L6-v2"
    model = SentenceTransformer(model_name)

    vectors = []
    meta: List[Dict] = []
    pdfs = sorted(list(pdf_dir.glob("**/*.pdf")))
    if not pdfs:
        raise SystemExit(f"No PDFs found under: {pdf_dir}")

    for pdf in pdfs:
        product = pdf.stem
        chunks = read_pdf_chunks(pdf)
        for c in chunks:
            meta.append({
                "product": product,
                "page": c["page"],
                "pdf_hint": f"{base_pdf_url}{pdf.name}#page={c['page']}" if base_pdf_url else pdf.name,
                "source": str(pdf.relative_to(pdf_dir))
            })
            # collect raw text; embed later in batch
            vectors.append(c["text"])

    # Embed
    embs = model.encode(vectors, batch_size=64, show_progress_bar=True, normalize_embeddings=True)
    embs = np.array(embs, dtype="float32")
    dim = embs.shape[1]

    # Build FAISS (cosine via inner product on normalized vectors)
    index = faiss.IndexFlatIP(dim)
    index.add(embs)
    faiss.write_index(index, str(out_dir / "index.faiss"))

    # Write metadata (aligned by row id)
    with open(out_dir / "meta.jsonl", "w", encoding="utf-8") as f:
        for m in meta:
            f.write(json.dumps(m, ensure_ascii=False) + "\n")

    # Save model info for sanity
    with open(out_dir / "model.json", "w", encoding="utf-8") as f:
        json.dump({"model": model_name, "dim": dim, "count": int(index.ntotal)}, f)

    print(f"Index built: {out_dir}  (rows={index.ntotal}, dim={dim})")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf_dir", required=True, help="Folder with SDS PDFs")
    ap.add_argument("--out_dir", default="data/index", help="Output folder for index & metadata")
    ap.add_argument("--base_pdf_url", default="", help="Optional absolute base URL for PDFs (for pdf_hint links)")
    args = ap.parse_args()
    build_index(pathlib.Path(args.pdf_dir), pathlib.Path(args.out_dir), args.base_pdf_url)
