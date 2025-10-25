import json
import pickle
import time
from pathlib import Path
from typing import List, Tuple, Dict
import numpy as np

class RAGSystem:
    def __init__(self, documents_dir: str = "documents", embeddings_dir: str = "embeddings"):
        """
        Initialize RAG system with document and embeddings directories.
        
        Args:
            documents_dir: Directory containing your CV, projects, experiences
            embeddings_dir: Directory to store pre-computed embeddings
        """
        self.documents_dir = Path(documents_dir)
        self.embeddings_dir = Path(embeddings_dir)
        self.embeddings_dir.mkdir(exist_ok=True)
        
        self.model = None
        self.document_chunks = []
        self.embeddings = None
        self.metadata = []
        
        print(">>> Initializing RAG system...")
        
    def load_model(self):
        """Load the sentence transformer model (lightweight and fast)"""
        try:
            from sentence_transformers import SentenceTransformer
            print(">>> Loading embedding model...")
            self.model = SentenceTransformer('all-MiniLM-L6-v2')
            print("[POSITIVE] Embedding model loaded!")
            return True
        except ImportError:
            print("[NEGATIVE] sentence-transformers not installed!")
            print("           Run: pip install sentence-transformers")
            return False
        except Exception as e:
            print(f"[NEGATIVE] Error loading model: {e}")
            return False
    
    def load_documents(self) -> bool:
        """
        Load and chunk all documents from the documents directory.
        Supports: .txt, .md files (PDF/DOCX support can be added)
        """
        print(f">>> Loading documents from {self.documents_dir}...")
        
        if not self.documents_dir.exists():
            print(f"[NEGATIVE] Documents directory not found: {self.documents_dir}")
            return False
        
        all_chunks = []
        all_metadata = []
        
        for file_path in self.documents_dir.glob("*.txt"):
            print(f"   Reading {file_path.name}...")
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Split into chunks (by sections marked with ##)
                chunks = self._chunk_document(content, file_path.name)
                all_chunks.extend(chunks)
                
                # Store metadata for each chunk
                for chunk in chunks:
                    all_metadata.append({
                        'source': file_path.name,
                        'type': self._get_document_type(file_path.name)
                    })
                
                print(f"      [POSITIVE] Loaded {len(chunks)} chunks from {file_path.name}")
            except Exception as e:
                print(f"      [NEGATIVE] Error reading {file_path.name}: {e}")
        
        # Also support markdown files
        for file_path in self.documents_dir.glob("*.md"):
            print(f"   Reading {file_path.name}...")
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                chunks = self._chunk_document(content, file_path.name)
                all_chunks.extend(chunks)
                
                for chunk in chunks:
                    all_metadata.append({
                        'source': file_path.name,
                        'type': self._get_document_type(file_path.name)
                    })
                
                print(f"      [POSITIVE] Loaded {len(chunks)} chunks from {file_path.name}")
            except Exception as e:
                print(f"      [NEGATIVE] Error reading {file_path.name}: {e}")
        
        if not all_chunks:
            print("[NEGATIVE] No documents loaded! Please add your CV, projects, and experiences to the documents/ folder.")
            return False
        
        self.document_chunks = all_chunks
        self.metadata = all_metadata
        print(f"[POSITIVE] Loaded {len(all_chunks)} total chunks from {len(list(self.documents_dir.glob('*.txt')) + list(self.documents_dir.glob('*.md')))} files")
        return True
    
    def _chunk_document(self, content: str) -> List[str]:
        """
        Split document into semantic chunks.
        Uses headers (##) as natural boundaries.
        """
        chunks = []
        
        # Split by headers (## or #)
        lines = content.split('\n')
        current_chunk = []
        
        for line in lines:
            # Check if it's a header
            if line.startswith('##') or line.startswith('#'):
                # Save previous chunk if it exists
                if current_chunk:
                    chunk_text = '\n'.join(current_chunk).strip()
                    if chunk_text and len(chunk_text) > 20:  # Minimum chunk size
                        chunks.append(chunk_text)
                
                # Start new chunk with header
                current_chunk = [line]
            else:
                current_chunk.append(line)
        
        # Add the last chunk
        if current_chunk:
            chunk_text = '\n'.join(current_chunk).strip()
            if chunk_text and len(chunk_text) > 20:
                chunks.append(chunk_text)
        
        # If no headers found, split by paragraph (double newline)
        if not chunks:
            paragraphs = content.split('\n\n')
            chunks = [p.strip() for p in paragraphs if p.strip() and len(p.strip()) > 20]
        
        return chunks
    
    def _get_document_type(self, filename: str) -> str:
        """Determine document type from filename"""
        filename_lower = filename.lower()
        if 'cv' in filename_lower or 'resume' in filename_lower:
            return 'cv'
        elif 'project' in filename_lower:
            return 'projects'
        elif 'experience' in filename_lower:
            return 'experiences'
        else:
            return 'general'
    
    def create_embeddings(self) -> bool:
        """Create embeddings for all document chunks"""
        if not self.model:
            print("[NEGATIVE] Model not loaded!")
            return False
        
        if not self.document_chunks:
            print("[NEGATIVE] No documents loaded!")
            return False
        
        print(f">>> Creating embeddings for {len(self.document_chunks)} chunks...")
        start_time = time.time()
        
        try:
            # Create embeddings (batched for efficiency)
            self.embeddings = self.model.encode(
                self.document_chunks,
                show_progress_bar=True,
                convert_to_numpy=True
            )
            
            elapsed = time.time() - start_time
            print(f"[POSITIVE] Created embeddings in {elapsed:.2f}s")
            
            # Save embeddings to disk for faster startup next time
            self._save_embeddings()
            
            return True
        except Exception as e:
            print(f"[NEGATIVE] Error creating embeddings: {e}")
            return False
    
    def _save_embeddings(self):
        """Save embeddings and metadata to disk"""
        try:
            embeddings_file = self.embeddings_dir / "embeddings.pkl"
            metadata_file = self.embeddings_dir / "metadata.json"
            chunks_file = self.embeddings_dir / "chunks.json"
            
            # Save embeddings
            with open(embeddings_file, 'wb') as f:
                pickle.dump(self.embeddings, f)
            
            # Save metadata
            with open(metadata_file, 'w', encoding='utf-8') as f:
                json.dump(self.metadata, f, indent=2)
            
            # Save chunks
            with open(chunks_file, 'w', encoding='utf-8') as f:
                json.dump(self.document_chunks, f, indent=2, ensure_ascii=False)

            print(f"[POSITIVE] Saved embeddings to {self.embeddings_dir}")
        except Exception as e:
            print(f"[NEGATIVE] Could not save embeddings: {e}")

    def load_embeddings(self) -> bool:
        """Load pre-computed embeddings from disk"""
        try:
            embeddings_file = self.embeddings_dir / "embeddings.pkl"
            metadata_file = self.embeddings_dir / "metadata.json"
            chunks_file = self.embeddings_dir / "chunks.json"
            
            if not all([embeddings_file.exists(), metadata_file.exists(), chunks_file.exists()]):
                print(">>> No cached embeddings found, will create new ones")
                return False
            
            print(">>> Loading cached embeddings...")
            
            # Load embeddings
            with open(embeddings_file, 'rb') as f:
                self.embeddings = pickle.load(f)
            
            # Load metadata
            with open(metadata_file, 'r', encoding='utf-8') as f:
                self.metadata = json.load(f)
            
            # Load chunks
            with open(chunks_file, 'r', encoding='utf-8') as f:
                self.document_chunks = json.load(f)
            
            print(f"[POSITIVE] Loaded {len(self.document_chunks)} chunks from cache")
            return True
        except Exception as e:
            print(f"[NEGATIVE] Could not load cached embeddings: {e}")
            return False
    
    def retrieve(self, query: str, top_k: int = 3) -> List[Tuple[str, Dict, float]]:
        """
        Retrieve most relevant document chunks for a query.
        
        Args:
            query: The interview question or topic
            top_k: Number of top results to return (default: 3)
        
        Returns:
            List of (chunk_text, metadata, similarity_score) tuples
        """
        if not self.model:
            print("[NEGATIVE] Model not loaded!")
            return []
        
        if self.embeddings is None or not self.document_chunks:
            print("[NEGATIVE] No embeddings available!")
            return []
        
        start_time = time.time()
        
        try:
            # Encode the query
            query_embedding = self.model.encode([query], convert_to_numpy=True)[0]
            
            # Calculate cosine similarity
            similarities = np.dot(self.embeddings, query_embedding) / (
                np.linalg.norm(self.embeddings, axis=1) * np.linalg.norm(query_embedding)
            )
            
            # Get top-k indices
            top_indices = np.argsort(similarities)[-top_k:][::-1]
            
            # Prepare results
            results = []
            for idx in top_indices:
                results.append((
                    self.document_chunks[idx],
                    self.metadata[idx],
                    float(similarities[idx])
                ))
            
            elapsed = (time.time() - start_time) * 1000  # Convert to ms
            print(f"[POSITIVE] Retrieved {top_k} chunks in {elapsed:.1f}ms")
            
            return results
        except Exception as e:
            print(f"[NEGATIVE] Error during retrieval: {e}")
            return []
    
    def initialize(self) -> bool:
        """
        Initialize the RAG system completely.
        Load model, documents, and create/load embeddings.
        """
        # Load model
        if not self.load_model():
            return False
        
        # Try to load cached embeddings
        if self.load_embeddings():
            print("[POSITIVE] RAG system ready!")
            return True
        
        # If no cache, load documents and create embeddings
        if not self.load_documents():
            return False
        
        if not self.create_embeddings():
            return False

        print("[POSITIVE] RAG system ready!")
        return True
    
    def format_context(self, results: List[Tuple[str, Dict, float]]) -> str:
        """
        Format retrieved chunks into context string for the AI prompt.
        
        Args:
            results: List of (chunk_text, metadata, score) from retrieve()
        
        Returns:
            Formatted context string
        """
        if not results:
            return ""
        
        context_parts = ["### RELEVANT CONTEXT FROM YOUR BACKGROUND:\n"]
        
        for i, (chunk, meta, score) in enumerate(results, 1):
            source = meta.get('source', 'unknown')
            doc_type = meta.get('type', 'general')
            
            # Only include high-confidence results (similarity > 0.3)
            if score > 0.3:
                context_parts.append(f"\n**From {source} ({doc_type}):**")
                context_parts.append(chunk)
                context_parts.append("")  # Empty line for separation
        
        return "\n".join(context_parts)


# Global RAG instance (will be initialized at startup)
_rag_system = None

def get_rag_system() -> RAGSystem:
    """Get or create the global RAG system instance"""
    global _rag_system
    if _rag_system is None:
        _rag_system = RAGSystem()
    return _rag_system

def initialize_rag() -> bool:
    """Initialize the RAG system at startup"""
    rag = get_rag_system()
    return rag.initialize()

def retrieve_context(query: str, top_k: int = 3) -> str:
    """
    Retrieve relevant context for a query.
    
    Args:
        query: The interview question or topic
        top_k: Number of chunks to retrieve
    
    Returns:
        Formatted context string to add to prompt
    """
    rag = get_rag_system()
    results = rag.retrieve(query, top_k=top_k)
    return rag.format_context(results)
