from __future__ import annotations

import argparse
import json
from pathlib import Path

from rs_demo.catalogue_validation import CatalogueValidationConfig, CatalogueValidator, load_jsonl
from rs_demo.embeddings import (
    MockEmbeddingConfig,
    MockEmbeddingPipeline,
    MockQueryEmbeddingConfig,
    MockQueryEmbeddingPipeline,
    NumpyEmbeddingStore,
    NumpyQueryEmbeddingStore,
)
from rs_demo.evaluation import (
    RetrievalEvaluator,
    validate_query_embedding_alignment,
    write_evaluation_report,
)
from rs_demo.experiments import (
    ExperimentRunner,
    MMEBV2DownloadConfig,
    MMEBV2Vlm2VecSetupConfig,
    download_mmeb_v2,
    load_experiment_config,
    setup_mmeb_v2_vlm2vec_eval,
)
from rs_demo.gemini_embeddings import (
    GeminiEmbeddingConfig,
    GeminiProductEmbeddingPipeline,
    GeminiQueryEmbeddingConfig,
    GeminiQueryEmbeddingPipeline,
)
from rs_demo.image_cropping import ImageCropperConfig, ProductImageCropper
from rs_demo.markdown_export import MarkdownExportConfig, ProductMarkdownExporter
from rs_demo.pdf_extraction import PdfExtractionConfig, PdfExtractor
from rs_demo.product_parser import ProductParser, ProductParserConfig
from rs_demo.queries import EvalQueryLoader
from rs_demo.rag import (
    DEFAULT_FILE_SEARCH_EMBEDDING_MODEL,
    DEFAULT_RAG_GENERATION_MODEL,
    ProductImageRagCorpusBuilder,
    ProductMultimodalRagCorpusBuilder,
    ProductTextRagCorpusBuilder,
    RagImageCorpusConfig,
    RagMultimodalCorpusConfig,
    RagTextCorpusConfig,
    RagTextEvaluationConfig,
    RagTextEvaluationPipeline,
    RagTextStoreConfig,
    RagTextStoreIngestionPipeline,
    load_store_name,
)
from rs_demo.retrieval import ProductRetriever


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Whisky catalogue extraction and embedding tools.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    extract = subparsers.add_parser("extract-pdf", help="Extract page text and images from a PDF.")
    extract.add_argument("pdf", type=Path, help="Path to the PDF to inspect.")
    extract.add_argument("--out-dir", type=Path, default=Path("data/extracted/pymupdf_probe"))
    extract.add_argument("--max-pages", type=int, default=5)
    extract.add_argument("--zoom", type=float, default=2.0)

    parse_products = subparsers.add_parser("parse-products", help="Parse product records.")
    parse_products.add_argument("--input-dir", type=Path, default=Path("data/extracted/pymupdf_probe"))
    parse_products.add_argument("--out", type=Path, default=Path("data/extracted/product_parse_sample.jsonl"))

    crop = subparsers.add_parser("crop-images", help="Crop whitespace from product images.")
    crop.add_argument("--catalogue", type=Path, default=Path("data/extracted/product_parse_sample.jsonl"))
    crop.add_argument(
        "--out-catalogue",
        type=Path,
        default=Path("data/extracted/product_parse_sample.jsonl"),
    )
    crop.add_argument("--out-dir", type=Path, default=Path("data/extracted/product_image_crops"))
    crop.add_argument(
        "--manifest",
        type=Path,
        default=Path("data/extracted/product_image_crops_manifest.json"),
    )
    crop.add_argument("--source-root", type=Path, default=Path("data/extracted/pymupdf_probe"))
    crop.add_argument("--white-threshold", type=int, default=245)
    crop.add_argument("--padding", type=int, default=18)
    crop.add_argument("--min-component-pixels", type=int, default=250)

    validate = subparsers.add_parser("validate-catalogue", help="Generate validation report.")
    validate.add_argument("--catalogue", type=Path, default=Path("data/extracted/product_parse_sample.jsonl"))
    validate.add_argument("--manifest", type=Path, default=Path("data/extracted/pymupdf_probe/manifest.json"))
    validate.add_argument("--out", type=Path, default=Path("data/extracted/catalogue_validation_report.md"))

    export = subparsers.add_parser("export-markdown", help="Export manual-review Markdown files.")
    export.add_argument("--catalogue", type=Path, default=Path("data/extracted/product_parse_sample.jsonl"))
    export.add_argument("--out-dir", type=Path, default=Path("data/extracted/product_markdown"))

    embeddings = subparsers.add_parser("build-mock-embeddings", help="Build mock NumPy embeddings.")
    embeddings.add_argument("--input", type=Path, default=Path("data/extracted/product_parse_sample.jsonl"))
    embeddings.add_argument("--output", type=Path, default=Path("data/embeddings/mock"))
    embeddings.add_argument("--dimension", type=int, default=32)

    query_embeddings = subparsers.add_parser(
        "build-mock-query-embeddings",
        help="Build mock query embeddings for text, image, and image+text eval files.",
    )
    query_embeddings.add_argument("--text-queries", type=Path, default=Path("data/eval/text_queries.jsonl"))
    query_embeddings.add_argument("--image-queries", type=Path, default=Path("data/eval/image_queries.jsonl"))
    query_embeddings.add_argument(
        "--image-text-queries",
        type=Path,
        default=Path("data/eval/image_text_queries.jsonl"),
    )
    query_embeddings.add_argument(
        "--cropped-image-text-queries",
        type=Path,
        default=Path("data/eval/cropped_image_text_queries.jsonl"),
    )
    query_embeddings.add_argument("--output-dir", type=Path, default=Path("data/embeddings/mock/queries"))
    query_embeddings.add_argument("--dimension", type=int, default=32)
    query_embeddings.add_argument(
        "--allow-missing",
        action="store_true",
        help="Skip missing query files. Intended only for development.",
    )

    evaluate = subparsers.add_parser(
        "run-mock-evaluation",
        help="Rank products for mock query embeddings and write retrieval metrics.",
    )
    evaluate.add_argument("--product-embeddings", type=Path, default=Path("data/embeddings/mock"))
    evaluate.add_argument("--query-embeddings", type=Path, default=Path("data/embeddings/mock/queries"))
    evaluate.add_argument("--text-queries", type=Path, default=Path("data/eval/text_queries.jsonl"))
    evaluate.add_argument("--image-queries", type=Path, default=Path("data/eval/image_queries.jsonl"))
    evaluate.add_argument(
        "--image-text-queries",
        type=Path,
        default=Path("data/eval/image_text_queries.jsonl"),
    )
    evaluate.add_argument(
        "--cropped-image-text-queries",
        type=Path,
        default=Path("data/eval/cropped_image_text_queries.jsonl"),
    )
    evaluate.add_argument("--out", type=Path, default=Path("data/eval/mock_retrieval_report.json"))
    evaluate.add_argument("--top-k", type=int, default=10)
    evaluate.add_argument(
        "--allow-missing",
        action="store_true",
        help="Skip missing query files or embedding directories. Intended only for development.",
    )

    gemini_embeddings = subparsers.add_parser(
        "build-gemini-embeddings",
        help="Build real Gemini product embeddings for one mode.",
    )
    gemini_embeddings.add_argument("--input", type=Path, default=Path("data/extracted/product_parse_sample.jsonl"))
    gemini_embeddings.add_argument("--output", type=Path, default=Path("data/embeddings/gemini"))
    gemini_embeddings.add_argument("--mode", choices=["text", "image", "multimodal"], default="text")
    gemini_embeddings.add_argument("--dimension", type=int, default=768)
    gemini_embeddings.add_argument("--limit-products", type=int, default=None)
    gemini_embeddings.add_argument("--max-requests", type=int, default=None)
    gemini_embeddings.add_argument("--sleep-seconds", type=float, default=0.8)
    gemini_embeddings.add_argument("--force", action="store_true")

    gemini_queries = subparsers.add_parser(
        "build-gemini-query-embeddings",
        help="Build real Gemini query embeddings for one query mode.",
    )
    gemini_queries.add_argument(
        "--mode",
        choices=["text", "image", "image_text", "cropped_image_text"],
        default="text",
    )
    gemini_queries.add_argument("--text-queries", type=Path, default=Path("data/eval/text_queries.jsonl"))
    gemini_queries.add_argument("--image-queries", type=Path, default=Path("data/eval/image_queries.jsonl"))
    gemini_queries.add_argument(
        "--image-text-queries",
        type=Path,
        default=Path("data/eval/image_text_queries.jsonl"),
    )
    gemini_queries.add_argument(
        "--cropped-image-text-queries",
        type=Path,
        default=Path("data/eval/cropped_image_text_queries.jsonl"),
    )
    gemini_queries.add_argument("--output-dir", type=Path, default=Path("data/embeddings/gemini/queries"))
    gemini_queries.add_argument("--dimension", type=int, default=768)
    gemini_queries.add_argument("--limit-queries", type=int, default=None)
    gemini_queries.add_argument("--max-requests", type=int, default=None)
    gemini_queries.add_argument("--sleep-seconds", type=float, default=0.8)
    gemini_queries.add_argument("--force", action="store_true")

    gemini_eval = subparsers.add_parser(
        "run-gemini-evaluation",
        help="Rank products for Gemini embeddings and write retrieval metrics for one mode.",
    )
    gemini_eval.add_argument(
        "--mode",
        choices=[
            "text",
            "image",
            "image_text",
            "cropped_image_text_to_image",
            "cropped_image_text_to_multimodal",
        ],
        default="text",
    )
    gemini_eval.add_argument("--product-embeddings", type=Path, default=Path("data/embeddings/gemini"))
    gemini_eval.add_argument("--query-embeddings", type=Path, default=Path("data/embeddings/gemini/queries"))
    gemini_eval.add_argument("--text-queries", type=Path, default=Path("data/eval/text_queries.jsonl"))
    gemini_eval.add_argument("--image-queries", type=Path, default=Path("data/eval/image_queries.jsonl"))
    gemini_eval.add_argument(
        "--image-text-queries",
        type=Path,
        default=Path("data/eval/image_text_queries.jsonl"),
    )
    gemini_eval.add_argument(
        "--cropped-image-text-queries",
        type=Path,
        default=Path("data/eval/cropped_image_text_queries.jsonl"),
    )
    gemini_eval.add_argument("--out", type=Path, default=Path("data/eval/gemini_retrieval_report.json"))
    gemini_eval.add_argument("--top-k", type=int, default=10)

    experiment = subparsers.add_parser(
        "run-experiment",
        help="Run a config-driven multimodal embedding retrieval experiment.",
    )
    experiment.add_argument("config", type=Path, help="Path to an experiment TOML config.")

    mmeb_download = subparsers.add_parser(
        "download-mmeb-v2",
        help="Download MMEB-V2 files into the preserved external data tree.",
    )
    mmeb_download.add_argument("--repo-id", default="TIGER-Lab/MMEB-V2")
    mmeb_download.add_argument("--local-dir", type=Path, default=Path("data/external/mmeb-v2/hf-repo"))
    mmeb_download.add_argument(
        "--profile",
        choices=["metadata", "image-smoke", "vlm2vec-eval", "full"],
        default="metadata",
        help=(
            "metadata is small; image-smoke downloads the MMEB-V1 image tarball; "
            "vlm2vec-eval downloads official eval asset archives; full is large."
        ),
    )
    mmeb_download.add_argument("--revision", default=None)

    mmeb_vlm2vec_setup = subparsers.add_parser(
        "setup-mmeb-v2-vlm2vec",
        help="Download and unpack MMEB-V2 eval assets in the VLM2Vec layout.",
    )
    mmeb_vlm2vec_setup.add_argument("--repo-id", default="TIGER-Lab/MMEB-V2")
    mmeb_vlm2vec_setup.add_argument(
        "--local-dir",
        type=Path,
        default=Path("data/external/mmeb-v2/vlm2vec_eval"),
    )
    mmeb_vlm2vec_setup.add_argument("--revision", default=None)
    mmeb_vlm2vec_setup.add_argument(
        "--skip-download",
        action="store_true",
        help="Only unpack files already present under --local-dir.",
    )
    mmeb_vlm2vec_setup.add_argument(
        "--no-unpack",
        action="store_true",
        help="Download archives but do not unpack them.",
    )
    mmeb_vlm2vec_setup.add_argument(
        "--force-unpack",
        action="store_true",
        help="Re-extract archives even if setup markers already exist.",
    )

    rag_corpus = subparsers.add_parser(
        "build-rag-text-corpus",
        help="Build one text document per product for the File Search RAG baseline.",
    )
    rag_corpus.add_argument("--catalogue", type=Path, default=Path("data/extracted/product_parse_sample.jsonl"))
    rag_corpus.add_argument("--out-dir", type=Path, default=Path("data/rag/product_text_corpus"))
    rag_corpus.add_argument("--manifest", type=Path, default=None)
    rag_corpus.add_argument("--limit-products", type=int, default=None)

    rag_store = subparsers.add_parser(
        "create-rag-text-store",
        help="Create/upload the text-only product File Search store.",
    )
    rag_store.add_argument(
        "--corpus-manifest",
        type=Path,
        default=Path("data/rag/product_text_corpus/manifest.jsonl"),
    )
    rag_store.add_argument("--out", type=Path, default=Path("data/rag/rag_product_text_store.json"))
    rag_store.add_argument("--display-name", default="rag_product_text_store")
    rag_store.add_argument(
        "--store-name",
        default=None,
        help="Use an existing File Search store instead of creating a new one.",
    )
    rag_store.add_argument("--embedding-model", default=DEFAULT_FILE_SEARCH_EMBEDDING_MODEL)
    rag_store.add_argument("--limit-products", type=int, default=None)
    rag_store.add_argument("--no-wait", action="store_true")
    rag_store.add_argument("--poll-interval-seconds", type=float, default=5.0)
    rag_store.add_argument("--timeout-seconds", type=float, default=600.0)
    rag_store.add_argument("--sleep-seconds", type=float, default=0.5)
    rag_store.add_argument("--concurrency", type=int, default=1)
    rag_store.add_argument("--no-resume", action="store_true")
    rag_store.add_argument("--progress-every", type=int, default=25)

    rag_image_corpus = subparsers.add_parser(
        "build-rag-image-corpus",
        help="Build one compressed product image per product for the File Search image RAG baseline.",
    )
    rag_image_corpus.add_argument(
        "--catalogue",
        type=Path,
        default=Path("data/extracted/product_parse_sample.jsonl"),
    )
    rag_image_corpus.add_argument(
        "--out-dir",
        type=Path,
        default=Path("data/rag/product_image_corpus"),
    )
    rag_image_corpus.add_argument("--manifest", type=Path, default=None)
    rag_image_corpus.add_argument("--limit-products", type=int, default=None)

    rag_image_store = subparsers.add_parser(
        "create-rag-image-store",
        help="Create/upload the product image File Search store.",
    )
    rag_image_store.add_argument(
        "--corpus-manifest",
        type=Path,
        default=Path("data/rag/product_image_corpus/manifest.jsonl"),
    )
    rag_image_store.add_argument(
        "--out",
        type=Path,
        default=Path("data/rag/rag_product_image_store.json"),
    )
    rag_image_store.add_argument("--display-name", default="rag_product_image_store")
    rag_image_store.add_argument(
        "--store-name",
        default=None,
        help="Use an existing File Search store instead of creating a new one.",
    )
    rag_image_store.add_argument("--embedding-model", default=DEFAULT_FILE_SEARCH_EMBEDDING_MODEL)
    rag_image_store.add_argument("--limit-products", type=int, default=None)
    rag_image_store.add_argument("--no-wait", action="store_true")
    rag_image_store.add_argument("--poll-interval-seconds", type=float, default=5.0)
    rag_image_store.add_argument("--timeout-seconds", type=float, default=600.0)
    rag_image_store.add_argument("--sleep-seconds", type=float, default=0.0)
    rag_image_store.add_argument("--concurrency", type=int, default=5)
    rag_image_store.add_argument("--no-resume", action="store_true")
    rag_image_store.add_argument("--progress-every", type=int, default=25)

    rag_multimodal_corpus = subparsers.add_parser(
        "build-rag-multimodal-corpus",
        help="Build one PDF product sheet per product for the File Search multimodal RAG baseline.",
    )
    rag_multimodal_corpus.add_argument(
        "--catalogue",
        type=Path,
        default=Path("data/extracted/product_parse_sample.jsonl"),
    )
    rag_multimodal_corpus.add_argument(
        "--out-dir",
        type=Path,
        default=Path("data/rag/product_multimodal_corpus"),
    )
    rag_multimodal_corpus.add_argument("--manifest", type=Path, default=None)
    rag_multimodal_corpus.add_argument("--limit-products", type=int, default=None)

    rag_multimodal_store = subparsers.add_parser(
        "create-rag-multimodal-store",
        help="Create/upload the multimodal product PDF File Search store.",
    )
    rag_multimodal_store.add_argument(
        "--corpus-manifest",
        type=Path,
        default=Path("data/rag/product_multimodal_corpus/manifest.jsonl"),
    )
    rag_multimodal_store.add_argument(
        "--out",
        type=Path,
        default=Path("data/rag/rag_product_multimodal_store.json"),
    )
    rag_multimodal_store.add_argument("--display-name", default="rag_product_multimodal_store")
    rag_multimodal_store.add_argument(
        "--store-name",
        default=None,
        help="Use an existing File Search store instead of creating a new one.",
    )
    rag_multimodal_store.add_argument("--embedding-model", default=DEFAULT_FILE_SEARCH_EMBEDDING_MODEL)
    rag_multimodal_store.add_argument("--limit-products", type=int, default=None)
    rag_multimodal_store.add_argument("--no-wait", action="store_true")
    rag_multimodal_store.add_argument("--poll-interval-seconds", type=float, default=5.0)
    rag_multimodal_store.add_argument("--timeout-seconds", type=float, default=600.0)
    rag_multimodal_store.add_argument("--sleep-seconds", type=float, default=0.0)
    rag_multimodal_store.add_argument("--concurrency", type=int, default=5)
    rag_multimodal_store.add_argument("--no-resume", action="store_true")
    rag_multimodal_store.add_argument("--progress-every", type=int, default=25)

    rag_eval = subparsers.add_parser(
        "run-rag-text-evaluation",
        help="Run text queries against a File Search product text store.",
    )
    rag_eval.add_argument("--store-name", default=None)
    rag_eval.add_argument(
        "--store-manifest",
        type=Path,
        default=Path("data/rag/rag_product_text_store.json"),
        help="Read store_name from this manifest when --store-name is omitted.",
    )
    rag_eval.add_argument("--queries", type=Path, default=Path("data/eval/text_queries.jsonl"))
    rag_eval.add_argument("--catalogue", type=Path, default=Path("data/extracted/product_parse_sample.jsonl"))
    rag_eval.add_argument("--out", type=Path, default=Path("data/eval/gemini_rag_text_report.json"))
    rag_eval.add_argument("--top-k", type=int, default=5)
    rag_eval.add_argument("--model", default=DEFAULT_RAG_GENERATION_MODEL)
    rag_eval.add_argument("--sleep-seconds", type=float, default=0.0)
    rag_eval.add_argument("--limit-queries", type=int, default=None)
    rag_eval.add_argument("--no-resume", action="store_true")
    rag_eval.add_argument("--max-retries", type=int, default=2)
    rag_eval.add_argument("--retry-sleep-seconds", type=float, default=10.0)
    rag_eval.add_argument("--continue-on-error", action="store_true")

    rag_generic_eval = subparsers.add_parser(
        "run-rag-evaluation",
        help="Run any eval query file against a File Search store.",
    )
    rag_generic_eval.add_argument("--store-name", default=None)
    rag_generic_eval.add_argument(
        "--store-manifest",
        type=Path,
        default=Path("data/rag/rag_product_multimodal_store.json"),
        help="Read store_name from this manifest when --store-name is omitted.",
    )
    rag_generic_eval.add_argument("--queries", type=Path, required=True)
    rag_generic_eval.add_argument("--catalogue", type=Path, default=Path("data/extracted/product_parse_sample.jsonl"))
    rag_generic_eval.add_argument("--out", type=Path, required=True)
    rag_generic_eval.add_argument("--report-key", default="rag")
    rag_generic_eval.add_argument("--top-k", type=int, default=5)
    rag_generic_eval.add_argument("--model", default=DEFAULT_RAG_GENERATION_MODEL)
    rag_generic_eval.add_argument("--sleep-seconds", type=float, default=0.0)
    rag_generic_eval.add_argument("--limit-queries", type=int, default=None)
    rag_generic_eval.add_argument("--no-resume", action="store_true")
    rag_generic_eval.add_argument("--max-retries", type=int, default=2)
    rag_generic_eval.add_argument("--retry-sleep-seconds", type=float, default=10.0)
    rag_generic_eval.add_argument("--continue-on-error", action="store_true")

    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "extract-pdf":
        rows = PdfExtractor().extract(
            PdfExtractionConfig(
                pdf_path=args.pdf,
                output_dir=args.out_dir,
                max_pages=args.max_pages,
                zoom=args.zoom,
            )
        )
        for row in rows:
            print(
                f"page={row['page']} "
                f"text_chars={row['text_chars']} "
                f"embedded_images={row['embedded_image_count']}"
            )
            if row["text_snippet"]:
                print(f"  text: {row['text_snippet']}")
            print(f"  render: {row['rendered_page_path']}")
        print(f"\nManifest written to {args.out_dir / 'manifest.json'}")
        return

    if args.command == "parse-products":
        records = ProductParser().run(
            ProductParserConfig(input_dir=args.input_dir, output_path=args.out)
        )
        pages = sorted({record["source_page"] for record in records})
        print(f"records={len(records)} pages={len(pages)} out={args.out}")
        return

    if args.command == "crop-images":
        _, results = ProductImageCropper().run(
            ImageCropperConfig(
                catalogue_path=args.catalogue,
                output_catalogue_path=args.out_catalogue,
                output_dir=args.out_dir,
                manifest_path=args.manifest,
                source_root=args.source_root,
                white_threshold=args.white_threshold,
                padding=args.padding,
                min_component_pixels=args.min_component_pixels,
            )
        )
        cropped = sum(1 for result in results if result["status"] == "cropped")
        print(f"cropped={cropped} images={len(results)} catalogue={args.out_catalogue}")
        return

    if args.command == "validate-catalogue":
        CatalogueValidator().run(
            CatalogueValidationConfig(
                catalogue_path=args.catalogue,
                manifest_path=args.manifest,
                output_path=args.out,
            )
        )
        records = load_jsonl(args.catalogue)
        print(f"report={args.out} records={len(records)}")
        return

    if args.command == "export-markdown":
        records = ProductMarkdownExporter().run(
            MarkdownExportConfig(catalogue_path=args.catalogue, output_dir=args.out_dir)
        )
        print(f"out_dir={args.out_dir} products={len(records)}")
        return

    if args.command == "build-mock-embeddings":
        MockEmbeddingPipeline().run(
            MockEmbeddingConfig(
                input_path=args.input,
                output_dir=args.output,
                dimension=args.dimension,
            )
        )
        print(f"Wrote mock embeddings to {args.output}")
        return

    if args.command == "build-mock-query-embeddings":
        specs = {
            "text": args.text_queries,
            "image": args.image_queries,
            "image_text": args.image_text_queries,
            "cropped_image_text": args.cropped_image_text_queries,
        }
        for name, query_path in specs.items():
            if not query_path.exists():
                if args.allow_missing:
                    print(f"Skipping missing query file: {query_path}")
                    continue
                raise FileNotFoundError(f"missing {name} query file: {query_path}")
            output_dir = args.output_dir / name
            MockQueryEmbeddingPipeline().run(
                MockQueryEmbeddingConfig(
                    input_path=query_path,
                    output_dir=output_dir,
                    dimension=args.dimension,
                )
            )
            print(f"Wrote {name} query embeddings to {output_dir}")
        return

    if args.command == "run-mock-evaluation":
        product_batch = NumpyEmbeddingStore(args.product_embeddings).read()
        retriever = ProductRetriever(product_batch)
        loader = EvalQueryLoader()
        evaluator = RetrievalEvaluator(k_values=(1, 5, args.top_k))
        reports = {}

        specs = {
            "text": (args.text_queries, args.query_embeddings / "text", retriever.rank_text),
            "image": (args.image_queries, args.query_embeddings / "image", retriever.rank_image),
            "image_text": (
                args.image_text_queries,
                args.query_embeddings / "image_text",
                retriever.rank_multimodal,
            ),
            "cropped_image_text_to_image": (
                args.cropped_image_text_queries,
                args.query_embeddings / "cropped_image_text",
                retriever.rank_image,
            ),
            "cropped_image_text_to_multimodal": (
                args.cropped_image_text_queries,
                args.query_embeddings / "cropped_image_text",
                retriever.rank_multimodal,
            ),
        }
        for name, (query_path, embedding_dir, ranker) in specs.items():
            if not query_path.exists() or not embedding_dir.exists():
                if args.allow_missing:
                    print(f"Skipping {name}; missing {query_path} or {embedding_dir}")
                    continue
                raise FileNotFoundError(
                    f"missing {name} query file or embedding directory: "
                    f"{query_path}, {embedding_dir}"
                )
            queries = loader.load(query_path)
            query_batch = NumpyQueryEmbeddingStore(embedding_dir).read()
            validate_query_embedding_alignment(queries, query_batch)
            rankings = ranker(query_batch, top_k=args.top_k)
            reports[name] = evaluator.evaluate(queries, rankings)

        write_evaluation_report(args.out, reports)
        print(f"Wrote mock retrieval report to {args.out}")
        return

    if args.command == "build-gemini-embeddings":
        product_embedding_batch = GeminiProductEmbeddingPipeline().run(
            GeminiEmbeddingConfig(
                input_path=args.input,
                output_dir=args.output,
                mode=args.mode,
                dimension=args.dimension,
                limit=args.limit_products,
                max_requests=args.max_requests,
                sleep_seconds=args.sleep_seconds,
                force=args.force,
            )
        )
        print(
            f"Wrote Gemini {args.mode} product embeddings to "
            f"{args.output} records={len(product_embedding_batch.metadata)}"
        )
        return

    if args.command == "build-gemini-query-embeddings":
        query_paths = {
            "text": args.text_queries,
            "image": args.image_queries,
            "image_text": args.image_text_queries,
            "cropped_image_text": args.cropped_image_text_queries,
        }
        query_path = query_paths[args.mode]
        output_dir = args.output_dir / args.mode
        query_embedding_batch = GeminiQueryEmbeddingPipeline().run(
            GeminiQueryEmbeddingConfig(
                input_path=query_path,
                output_dir=output_dir,
                dimension=args.dimension,
                limit=args.limit_queries,
                max_requests=args.max_requests,
                sleep_seconds=args.sleep_seconds,
                force=args.force,
            )
        )
        print(
            f"Wrote Gemini {args.mode} query embeddings to "
            f"{output_dir} records={len(query_embedding_batch.metadata)}"
        )
        return

    if args.command == "run-gemini-evaluation":
        eval_specs = {
            "text": (args.text_queries, args.query_embeddings / "text", ProductRetriever.rank_text),
            "image": (args.image_queries, args.query_embeddings / "image", ProductRetriever.rank_image),
            "image_text": (
                args.image_text_queries,
                args.query_embeddings / "image_text",
                ProductRetriever.rank_multimodal,
            ),
            "cropped_image_text_to_image": (
                args.cropped_image_text_queries,
                args.query_embeddings / "cropped_image_text",
                ProductRetriever.rank_image,
            ),
            "cropped_image_text_to_multimodal": (
                args.cropped_image_text_queries,
                args.query_embeddings / "cropped_image_text",
                ProductRetriever.rank_multimodal,
            ),
        }
        product_batch = NumpyEmbeddingStore(args.product_embeddings).read()
        retriever = ProductRetriever(product_batch)
        query_path, embedding_dir, ranker = eval_specs[args.mode]
        queries = EvalQueryLoader().load(query_path)
        query_batch = NumpyQueryEmbeddingStore(embedding_dir).read()
        validate_query_embedding_alignment(queries, query_batch)
        rankings = ranker(retriever, query_batch, top_k=args.top_k)
        report = RetrievalEvaluator(k_values=(1, 5, args.top_k)).evaluate(queries, rankings)
        reports: dict[str, dict[str, object]] = {}
        if args.out.exists():
            reports = json.loads(args.out.read_text(encoding="utf-8"))
        reports[args.mode] = report.to_dict()
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(reports, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"Wrote Gemini {args.mode} retrieval report to {args.out}")
        return

    if args.command == "run-experiment":
        config = load_experiment_config(args.config)
        experiment_result = ExperimentRunner(config).run()
        print(
            f"Wrote experiment run to {experiment_result.run_dir} "
            f"dataset={experiment_result.dataset_id} model={experiment_result.model_id} "
            f"queries={experiment_result.metrics.query_count}"
        )
        return

    if args.command == "download-mmeb-v2":
        download_result = download_mmeb_v2(
            MMEBV2DownloadConfig(
                repo_id=args.repo_id,
                local_dir=args.local_dir,
                profile=args.profile,
                revision=args.revision,
            )
        )
        print(
            f"Downloaded MMEB-V2 profile={download_result.profile} "
            f"repo={download_result.repo_id} local_dir={download_result.local_dir}"
        )
        return

    if args.command == "setup-mmeb-v2-vlm2vec":
        setup_result = setup_mmeb_v2_vlm2vec_eval(
            MMEBV2Vlm2VecSetupConfig(
                repo_id=args.repo_id,
                local_dir=args.local_dir,
                revision=args.revision,
                download=not args.skip_download,
                unpack=not args.no_unpack,
                force_unpack=args.force_unpack,
            )
        )
        print(
            "Prepared MMEB-V2 VLM2Vec eval data "
            f"local_dir={setup_result.local_dir} unpacked={list(setup_result.unpacked)} "
            f"skipped={list(setup_result.skipped)} manifest={setup_result.manifest_path}"
        )
        return

    if args.command == "build-rag-text-corpus":
        documents = ProductTextRagCorpusBuilder().build(
            RagTextCorpusConfig(
                catalogue_path=args.catalogue,
                output_dir=args.out_dir,
                manifest_path=args.manifest,
                limit=args.limit_products,
            )
        )
        manifest = args.manifest or args.out_dir / "manifest.jsonl"
        print(f"Wrote RAG text corpus to {args.out_dir} documents={len(documents)} manifest={manifest}")
        return

    if args.command == "create-rag-text-store":
        manifest = RagTextStoreIngestionPipeline().run(
            RagTextStoreConfig(
                corpus_manifest_path=args.corpus_manifest,
                output_path=args.out,
                display_name=args.display_name,
                store_name=args.store_name,
                embedding_model=args.embedding_model,
                limit=args.limit_products,
                wait=not args.no_wait,
                poll_interval_seconds=args.poll_interval_seconds,
                timeout_seconds=args.timeout_seconds,
                sleep_seconds=args.sleep_seconds,
                concurrency=args.concurrency,
                resume=not args.no_resume,
                progress_every=args.progress_every,
            )
        )
        print(
            "Wrote RAG text store manifest to "
            f"{args.out} store_name={manifest['store_name']} documents={manifest['document_count']}"
        )
        return

    if args.command == "build-rag-image-corpus":
        documents = ProductImageRagCorpusBuilder().build(
            RagImageCorpusConfig(
                catalogue_path=args.catalogue,
                output_dir=args.out_dir,
                manifest_path=args.manifest,
                limit=args.limit_products,
            )
        )
        manifest = args.manifest or args.out_dir / "manifest.jsonl"
        print(f"Wrote RAG image corpus to {args.out_dir} documents={len(documents)} manifest={manifest}")
        return

    if args.command == "create-rag-image-store":
        manifest = RagTextStoreIngestionPipeline().run(
            RagTextStoreConfig(
                corpus_manifest_path=args.corpus_manifest,
                output_path=args.out,
                display_name=args.display_name,
                store_name=args.store_name,
                embedding_model=args.embedding_model,
                limit=args.limit_products,
                wait=not args.no_wait,
                poll_interval_seconds=args.poll_interval_seconds,
                timeout_seconds=args.timeout_seconds,
                sleep_seconds=args.sleep_seconds,
                concurrency=args.concurrency,
                resume=not args.no_resume,
                progress_every=args.progress_every,
            )
        )
        print(
            "Wrote RAG image store manifest to "
            f"{args.out} store_name={manifest['store_name']} documents={manifest['document_count']}"
        )
        return

    if args.command == "run-rag-text-evaluation":
        store_name = args.store_name or load_store_name(args.store_manifest)
        output = RagTextEvaluationPipeline().run(
            RagTextEvaluationConfig(
                store_name=store_name,
                query_path=args.queries,
                catalogue_path=args.catalogue,
                output_path=args.out,
                report_key="rag_text",
                top_k=args.top_k,
                model_name=args.model,
                sleep_seconds=args.sleep_seconds,
                limit=args.limit_queries,
                resume=not args.no_resume,
                max_retries=args.max_retries,
                retry_sleep_seconds=args.retry_sleep_seconds,
                continue_on_error=args.continue_on_error,
            )
        )
        print(
            f"Wrote RAG text evaluation report to {args.out} "
            f"queries={output.report.query_count} store_name={store_name}"
        )
        return

    if args.command == "run-rag-evaluation":
        store_name = args.store_name or load_store_name(args.store_manifest)
        output = RagTextEvaluationPipeline().run(
            RagTextEvaluationConfig(
                store_name=store_name,
                query_path=args.queries,
                catalogue_path=args.catalogue,
                output_path=args.out,
                report_key=args.report_key,
                top_k=args.top_k,
                model_name=args.model,
                sleep_seconds=args.sleep_seconds,
                limit=args.limit_queries,
                resume=not args.no_resume,
                max_retries=args.max_retries,
                retry_sleep_seconds=args.retry_sleep_seconds,
                continue_on_error=args.continue_on_error,
            )
        )
        print(
            f"Wrote RAG evaluation report to {args.out} "
            f"queries={output.report.query_count} store_name={store_name} report_key={args.report_key}"
        )
        return

    if args.command == "build-rag-multimodal-corpus":
        documents = ProductMultimodalRagCorpusBuilder().build(
            RagMultimodalCorpusConfig(
                catalogue_path=args.catalogue,
                output_dir=args.out_dir,
                manifest_path=args.manifest,
                limit=args.limit_products,
            )
        )
        manifest = args.manifest or args.out_dir / "manifest.jsonl"
        print(
            "Wrote RAG multimodal corpus to "
            f"{args.out_dir} documents={len(documents)} manifest={manifest}"
        )
        return

    if args.command == "create-rag-multimodal-store":
        manifest = RagTextStoreIngestionPipeline().run(
            RagTextStoreConfig(
                corpus_manifest_path=args.corpus_manifest,
                output_path=args.out,
                display_name=args.display_name,
                store_name=args.store_name,
                embedding_model=args.embedding_model,
                limit=args.limit_products,
                wait=not args.no_wait,
                poll_interval_seconds=args.poll_interval_seconds,
                timeout_seconds=args.timeout_seconds,
                sleep_seconds=args.sleep_seconds,
                concurrency=args.concurrency,
                resume=not args.no_resume,
                progress_every=args.progress_every,
            )
        )
        print(
            "Wrote RAG multimodal store manifest to "
            f"{args.out} store_name={manifest['store_name']} documents={manifest['document_count']}"
        )
        return

    parser.error(f"unknown command: {args.command}")
