from .repository import ModelRepository, SchemalessModelRepository
from ..settings import Settings
from pydantic import PyObject


class ModelRepositoryFactory:
    @staticmethod
    def resolve_model_repository(settings: Settings) -> ModelRepository:
        model_repository_implementation: PyObject = SchemalessModelRepository

        if settings.model_repository_implementation:
            model_repository_implementation = settings.model_repository_implementation

        model_repository = model_repository_implementation(
            root=settings.model_repository_root,
            **settings.model_repository_implementation_args,
        )
        return model_repository
