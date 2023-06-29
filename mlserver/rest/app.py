from typing import Callable
from fastapi import FastAPI
from fastapi.responses import Response as FastAPIResponse
from fastapi.routing import APIRoute as FastAPIRoute
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import Resource, SERVICE_NAME
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter


from starlette_exporter import PrometheusMiddleware

from .endpoints import Endpoints, ModelRepositoryEndpoints
from .requests import Request
from .responses import Response
from .errors import _EXCEPTION_HANDLERS

from ..settings import Settings
from ..handlers import DataPlane, ModelRepositoryHandlers


class APIRoute(FastAPIRoute):
    """
    Custom route to use our own Request handler.
    """

    def __init__(
        self,
        *args,
        response_model_exclude_unset=True,
        response_model_exclude_none=True,
        **kwargs
    ):
        super().__init__(
            *args,
            response_model_exclude_unset=response_model_exclude_unset,
            response_model_exclude_none=response_model_exclude_none,
            **kwargs
        )

    def get_route_handler(self) -> Callable:
        original_route_handler = super().get_route_handler()

        async def custom_route_handler(request: Request) -> FastAPIResponse:
            request = Request(request.scope, request.receive)
            return await original_route_handler(request)

        return custom_route_handler


def create_app(
    settings: Settings,
    data_plane: DataPlane,
    model_repository_handlers: ModelRepositoryHandlers,
) -> FastAPI:
    endpoints = Endpoints(data_plane)
    model_repository_endpoints = ModelRepositoryEndpoints(model_repository_handlers)

    routes = [
        # Model ready
        APIRoute(
            "/v2/models/{model_name}/ready",
            endpoints.model_ready,
        ),
        APIRoute(
            "/v2/models/{model_name}/versions/{model_version}/ready",
            endpoints.model_ready,
        ),
        # Model infer
        APIRoute(
            "/v2/models/{model_name}/infer",
            endpoints.infer,
            methods=["POST"],
        ),
        APIRoute(
            "/v2/models/{model_name}/versions/{model_version}/infer",
            endpoints.infer,
            methods=["POST"],
        ),
        # Model metadata
        APIRoute(
            "/v2/models/{model_name}",
            endpoints.model_metadata,
        ),
        APIRoute(
            "/v2/models/{model_name}/versions/{model_version}",
            endpoints.model_metadata,
        ),
        # Model docs
        APIRoute(
            "/v2/models/{model_name}/docs/dataplane.json",
            endpoints.model_openapi,
        ),
        APIRoute(
            "/v2/models/{model_name}/versions/{model_version}/docs/dataplane.json",
            endpoints.model_openapi,
        ),
        APIRoute(
            "/v2/models/{model_name}/docs",
            endpoints.model_docs,
        ),
        APIRoute(
            "/v2/models/{model_name}/versions/{model_version}/docs",
            endpoints.model_docs,
        ),
        # Liveness and readiness
        APIRoute("/v2/health/live", endpoints.live),
        APIRoute("/v2/health/ready", endpoints.ready),
        # Server docs
        APIRoute(
            "/v2/docs/dataplane.json",
            endpoints.openapi,
        ),
        APIRoute(
            "/v2/docs",
            endpoints.docs,
        ),
        # Server metadata
        APIRoute(
            "/v2",
            endpoints.metadata,
        ),
    ]

    routes += [
        # Model Repository API
        APIRoute(
            "/v2/repository/index",
            model_repository_endpoints.index,
            methods=["POST"],
        ),
        APIRoute(
            "/v2/repository/models/{model_name}/load",
            model_repository_endpoints.load,
            methods=["POST"],
        ),
        APIRoute(
            "/v2/repository/models/{model_name}/unload",
            model_repository_endpoints.unload,
            methods=["POST"],
        ),
    ]

    app = FastAPI(
        debug=settings.debug,
        routes=routes,  # type: ignore
        default_response_class=Response,
        exception_handlers=_EXCEPTION_HANDLERS,  # type: ignore
        docs_url=None,
        redoc_url=None,
    )

    resource = Resource(attributes={
        SERVICE_NAME: "mlserver-actual"
    })
    tracer_provider = TracerProvider(resource=resource)
    otel_exporter = OTLPSpanExporter(insecure=True, endpoint="localhost:4317")
    tracer_provider.add_span_processor(BatchSpanProcessor(otel_exporter))

    FastAPIInstrumentor.instrument_app(
        app,
        tracer_provider=tracer_provider,
        excluded_urls="unimportant"  # comma delimited
    )

    app.router.route_class = APIRoute
    app.add_middleware(GZipMiddleware)
    if settings.cors_settings is not None:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_settings.allow_origins,
            allow_origin_regex=settings.cors_settings.allow_origin_regex,
            allow_credentials=settings.cors_settings.allow_credentials,
            allow_methods=settings.cors_settings.allow_methods,
            allow_headers=settings.cors_settings.allow_headers,
            max_age=settings.cors_settings.max_age,
        )

    if settings.metrics_endpoint:
        app.add_middleware(
            PrometheusMiddleware,
            app_name="mlserver",
            prefix=settings.metrics_rest_server_prefix,
            # TODO: Should we also exclude model's health endpoints?
            skip_paths=[
                settings.metrics_endpoint,
                "/v2/health/live",
                "/v2/health/ready",
            ],
        )

    return app
