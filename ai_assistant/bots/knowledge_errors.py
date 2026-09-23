"""Public, stable Knowledge processing errors shared by all upload adapters."""


class KnowledgeProcessingError(ValueError):
    def __init__(self, message, code="processing_failed", status=400):
        super().__init__(message)
        self.code = code
        self.status = status


class KnowledgeQuotaError(KnowledgeProcessingError):
    def __init__(self, storage):
        self.storage = storage
        super().__init__(
            "Knowledge storage limit reached.", "knowledge_quota_exceeded", 403
        )
