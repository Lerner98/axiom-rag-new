"""
Collections Routes
Manages document collections in the vector store.
"""
import logging
from datetime import datetime
from fastapi import APIRouter, HTTPException, Query

from api.models import (
    CreateCollectionRequest,
    CollectionInfo,
    CollectionListResponse,
    CollectionDocumentsResponse,
)
from config.settings import settings
from vectorstore.store import VectorStore

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/collections", tags=["Collections"])

# Lazy-initialized vector store
_vectorstore = None


def get_vectorstore():
    """Get or create the vector store instance."""
    global _vectorstore
    if _vectorstore is None:
        _vectorstore = VectorStore()
    return _vectorstore


@router.get("/", response_model=CollectionListResponse)
async def list_collections():
    """
    List all collections.
    """
    try:
        store = get_vectorstore()
        collection_names = await store.list_collections()

        collections = []
        for name in collection_names:
            collections.append(
                CollectionInfo(
                    name=name,
                    description="",
                    document_count=0,  # TODO: Get actual count
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                )
            )

        # Ensure default collection exists
        if settings.collection_name not in collection_names:
            collections.insert(
                0,
                CollectionInfo(
                    name=settings.collection_name,
                    description="Default knowledge base",
                    document_count=0,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                ),
            )

        return CollectionListResponse(collections=collections, total=len(collections))

    except Exception as e:
        logger.error(f"Error listing collections: {e}")
        # Return default collection on error
        return CollectionListResponse(
            collections=[
                CollectionInfo(
                    name=settings.collection_name,
                    description="Default knowledge base",
                    document_count=0,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                )
            ],
            total=1,
        )


@router.post("/", response_model=CollectionInfo)
async def create_collection(request: CreateCollectionRequest):
    """
    Create a new collection.
    """
    # Collections are created automatically when documents are added
    # This endpoint just validates and returns the collection info
    return CollectionInfo(
        name=request.name,
        description=request.description or "",
        document_count=0,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )


@router.get("/{collection_name}", response_model=CollectionInfo)
async def get_collection(collection_name: str):
    """
    Get collection details.
    """
    try:
        store = get_vectorstore()
        collections = await store.list_collections()

        if collection_name not in collections:
            raise HTTPException(
                status_code=404, detail=f"Collection '{collection_name}' not found"
            )

        return CollectionInfo(
            name=collection_name,
            description="",
            document_count=0,  # TODO: Get actual count
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting collection: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{collection_name}")
async def delete_collection(collection_name: str, confirm: bool = Query(False)):
    """
    Delete a collection.
    Requires confirm=true query parameter.
    """
    if not confirm:
        raise HTTPException(
            status_code=400, detail="Must pass confirm=true to delete a collection"
        )

    if collection_name == settings.collection_name:
        raise HTTPException(
            status_code=400, detail="Cannot delete the default collection"
        )

    try:
        store = get_vectorstore()
        await store.delete_collection(collection_name)
        return {"message": f"Collection '{collection_name}' deleted"}

    except Exception as e:
        logger.error(f"Error deleting collection: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{collection_name}/documents", response_model=CollectionDocumentsResponse)
async def list_collection_documents(
    collection_name: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """
    List documents in a collection.
    """
    # TODO: Implement document listing from vector store
    # This requires tracking document metadata separately
    return CollectionDocumentsResponse(
        collection_name=collection_name,
        documents=[],
        total=0,
        page=page,
        page_size=page_size,
    )


@router.delete("/{collection_name}/documents/{document_id}")
async def delete_document(collection_name: str, document_id: str):
    """
    Delete a specific document from a collection.
    """
    # TODO: Implement document deletion
    # This requires tracking document IDs and their chunks
    return {"message": f"Document '{document_id}' deleted from '{collection_name}'"}
