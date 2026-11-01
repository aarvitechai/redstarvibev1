# 0004: RAG pipeline written directly, without LlamaIndex

Accepted, deviates from the guide. The pipeline is small: chunk, embed, hybrid search with reciprocal rank fusion, then generate.
Writing it directly keeps the tenant filter explicit in the SQL, which is the security critical part, and avoids a large
dependency. LlamaIndex can still be added behind `app/ai/rag` if advanced retrieval becomes necessary.
