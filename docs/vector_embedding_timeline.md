# Vector Embedding Timeline

Vector embeddings evolved from word-level semantic similarity, to sentence and document retrieval, to cross-modal image-text matching, and now toward universal multimodal retrieval over text, images, documents, videos, and product data.

| Period | Stage | Representative examples | Main idea |
|---|---|---|---|
| Before 2013 | Statistical semantic vectors | LSA, matrix factorization, distributional semantics | Meaning can be represented by co-occurrence patterns. Similar words appear in similar contexts. |
| 2013-2017 | Static word embeddings | Word2vec, GloVe, FastText | Words are mapped into dense vectors. Similar words are close in vector space, but each word usually has one fixed meaning. |
| 2018-2020 | Contextual and sentence embeddings | BERT, USE, SBERT | Embeddings move from isolated words to sentences and passages. Meaning becomes context-dependent. |
| 2020-2022 | Dense retrieval embeddings | DPR, Contriever, GTR, E5 | Embeddings become a retrieval interface: encode query and document separately, then rank by vector similarity. |
| 2021-2022 | Vision-language embeddings | CLIP and related models | Images and text are aligned into a shared vector space, enabling text-to-image and image-to-text retrieval. |
| 2024-2025 | LLM-based text embeddings | Gecko, Gemini Embedding | LLMs are used to generate training data, add task instructions, mine hard negatives, and build stronger general-purpose text embeddings. |
| 2024-2025 | VLM-based multimodal embeddings | VLM2Vec, VLM2Vec-V2 | Vision-language models are adapted into universal embedders that accept text, image, video, and document-like inputs. |
| 2025-2026 | Product-level multimodal embedding APIs | Gemini Embedding 2, Qwen3-VL-Embedding, Seed1.6-Embedding | Embedding systems become practical infrastructure for mixed-modal retrieval over text, images, videos, documents, and product data. |

