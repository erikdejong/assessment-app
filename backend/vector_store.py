import os
import re
import logging
from typing import List
from dotenv import load_dotenv
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def load_document(db_name: str, documents: List[str]) -> Chroma:
    all_docs = []
    for document in documents:
        loader = PyPDFLoader(document)
        docs = loader.load()

        # Extract year from filename
        match = re.search(r"(20\d{2})", document)
        year = int(match.group(1)) if match else None

        for d in docs:
            d.metadata["year"] = year
            d.metadata["source_file"] = document

        all_docs.extend(docs)

    splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=150)
    chunks = splitter.split_documents(all_docs)

    model = os.getenv("EMBEDDING_MODEL", "text-embedding-3-large")
    embeddings = OpenAIEmbeddings(model=model)

    if os.path.exists(db_name):
        Chroma(persist_directory=db_name, embedding_function=embeddings).delete_collection()

    collection_name = os.getenv("VECTOR_COLLECTION", "documents")
    vectorstore = Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        persist_directory=db_name,
        collection_name=collection_name,
    )

    return vectorstore


if __name__ == "__main__":
    load_dotenv()

    memory_dir = os.getenv("MEMORY_DIR", ".")
    vector_store_dir = os.getenv("VECTOR_STORE_DIR", ".")

    documents = [
        os.path.join(memory_dir, "knowledge", "Annual Report 2025.pdf"),
        os.path.join(memory_dir, "knowledge", "Annual Report 2024.pdf"),
        os.path.join(memory_dir, "knowledge", "Annual Report 2023.pdf"),
        os.path.join(memory_dir, "knowledge", "Annual Report 2022 (EN).pdf"),
    ]

    db_name = os.path.join(vector_store_dir, "vector_store.db")
    vectorstore = load_document(db_name, documents)

    logger.info(f"Vectorstore created with {vectorstore._collection.count()} documents")
