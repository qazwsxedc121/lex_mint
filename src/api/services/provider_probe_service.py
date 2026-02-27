"""
Provider endpoint probing service.

Implements strict endpoint diagnostics for providers that may expose
multiple region/domain base URLs.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Optional

import httpx

from src.api.models.model_config import (
    Provider,
    ProviderEndpointProbeRequest,
    ProviderEndpointProbeResponse,
    ProviderEndpointProbeResult,
)
from src.api.services.model_config_service import ModelConfigService


class ProviderProbeService:
    """Endpoint diagnostics and recommendation service."""

    _PROVIDER_DEFAULT_PROBE_METHODS: dict[str, str] = {
        "stepfun": "openai_models",
        "minimax": "openai_models",
        "zhipu": "openai_models",
    }

    def __init__(self, model_service: ModelConfigService):
        self._model_service = model_service

    async def probe(
        self,
        provider: Provider,
        request: ProviderEndpointProbeRequest,
        api_key: str,
    ) -> ProviderEndpointProbeResponse:
        candidates = self._build_candidates(provider, request)
        tasks = [self._probe_candidate(candidate, api_key=api_key, strict=request.strict) for candidate in candidates]
        results = await asyncio.gather(*tasks)

        recommended = self._pick_recommended_result(results, request.client_region_hint)
        success_count = len([item for item in results if item.success])
        if success_count:
            summary = f"Found {success_count} reachable endpoint(s)"
            if recommended:
                summary += f"; recommended: {recommended.base_url}"
        else:
            summary = "No reachable endpoint. Check API key, network, or endpoint URL."

        return ProviderEndpointProbeResponse(
            provider_id=provider.id,
            results=results,
            recommended_endpoint_profile_id=recommended.endpoint_profile_id if recommended else None,
            recommended_base_url=recommended.base_url if recommended else None,
            summary=summary,
        )

    def _build_candidates(
        self,
        provider: Provider,
        request: ProviderEndpointProbeRequest,
    ) -> list[dict[str, Any]]:
        endpoint_profiles = self._model_service.get_endpoint_profiles_for_provider(provider)
        by_id = {profile.id: profile for profile in endpoint_profiles}

        candidates: list[dict[str, Any]] = []
        if request.mode == "auto":
            if endpoint_profiles:
                candidates = [
                    {
                        "endpoint_profile_id": profile.id,
                        "label": profile.label,
                        "base_url": profile.base_url,
                        "priority": profile.priority,
                        "region_tags": profile.region_tags,
                        "probe_method": profile.probe_method or self._PROVIDER_DEFAULT_PROBE_METHODS.get(provider.id, "openai_models"),
                    }
                    for profile in endpoint_profiles
                ]
            else:
                candidates = [self._build_custom_candidate(provider.base_url, provider.endpoint_profile_id)]
        else:
            if request.base_url_override:
                candidates = [self._build_custom_candidate(request.base_url_override, request.endpoint_profile_id)]
            elif request.endpoint_profile_id:
                profile = by_id.get(request.endpoint_profile_id)
                if not profile:
                    raise ValueError(f"Unknown endpoint profile '{request.endpoint_profile_id}'")
                candidates = [
                    {
                        "endpoint_profile_id": profile.id,
                        "label": profile.label,
                        "base_url": profile.base_url,
                        "priority": profile.priority,
                        "region_tags": profile.region_tags,
                        "probe_method": profile.probe_method or self._PROVIDER_DEFAULT_PROBE_METHODS.get(provider.id, "openai_models"),
                    }
                ]
            else:
                candidates = [self._build_custom_candidate(provider.base_url, provider.endpoint_profile_id)]

        deduped: list[dict[str, Any]] = []
        seen = set()
        for candidate in candidates:
            normalized = self._normalize_url(candidate["base_url"])
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            deduped.append(candidate)
        return deduped

    @staticmethod
    def _build_custom_candidate(base_url: str, endpoint_profile_id: Optional[str]) -> dict[str, Any]:
        return {
            "endpoint_profile_id": endpoint_profile_id if endpoint_profile_id else "custom",
            "label": "Custom Endpoint" if not endpoint_profile_id else f"Profile: {endpoint_profile_id}",
            "base_url": base_url,
            "priority": 1000,
            "region_tags": [],
            "probe_method": "openai_models",
        }

    async def _probe_candidate(
        self,
        candidate: dict[str, Any],
        *,
        api_key: str,
        strict: bool,
    ) -> ProviderEndpointProbeResult:
        base_url = str(candidate.get("base_url", "")).strip()
        if not base_url:
            return ProviderEndpointProbeResult(
                endpoint_profile_id=candidate.get("endpoint_profile_id"),
                label=candidate.get("label", "Unknown"),
                base_url=base_url,
                success=False,
                classification="endpoint_mismatch",
                message="Missing base URL",
                priority=int(candidate.get("priority", 100)),
                region_tags=[str(tag) for tag in candidate.get("region_tags", [])],
            )

        probe_method = str(candidate.get("probe_method", "openai_models"))
        start_time = time.perf_counter()
        if probe_method == "openai_models":
            result = await self._probe_openai_models(base_url=base_url, api_key=api_key, strict=strict)
        else:
            result = {
                "success": False,
                "classification": "unknown",
                "http_status": None,
                "message": f"Unsupported probe method '{probe_method}'",
                "detected_model_count": None,
            }
        latency_ms = int((time.perf_counter() - start_time) * 1000)

        return ProviderEndpointProbeResult(
            endpoint_profile_id=candidate.get("endpoint_profile_id"),
            label=candidate.get("label", "Unknown"),
            base_url=base_url,
            success=bool(result["success"]),
            classification=str(result["classification"]),
            http_status=result.get("http_status"),
            latency_ms=latency_ms,
            message=str(result["message"]),
            detected_model_count=result.get("detected_model_count"),
            priority=int(candidate.get("priority", 100)),
            region_tags=[str(tag) for tag in candidate.get("region_tags", [])],
        )

    async def _probe_openai_models(
        self,
        *,
        base_url: str,
        api_key: str,
        strict: bool,
    ) -> dict[str, Any]:
        url = self._normalize_url(base_url)
        models_url = f"{url}/models"
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}

        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                response = await client.get(models_url, headers=headers)

            if response.status_code in (401, 403):
                return {
                    "success": False,
                    "classification": "auth_invalid",
                    "http_status": response.status_code,
                    "message": "Authentication failed",
                    "detected_model_count": None,
                }
            if response.status_code == 404:
                return {
                    "success": False,
                    "classification": "endpoint_mismatch",
                    "http_status": 404,
                    "message": "Endpoint not found",
                    "detected_model_count": None,
                }
            if response.status_code >= 400:
                return {
                    "success": False,
                    "classification": "http_error",
                    "http_status": response.status_code,
                    "message": f"HTTP {response.status_code}",
                    "detected_model_count": None,
                }

            data = response.json()
            model_count = len(data.get("data", [])) if isinstance(data, dict) else 0
            if model_count <= 0 and strict:
                return {
                    "success": False,
                    "classification": "empty_models",
                    "http_status": response.status_code,
                    "message": "API responded but returned no models",
                    "detected_model_count": model_count,
                }
            return {
                "success": True,
                "classification": "ok",
                "http_status": response.status_code,
                "message": "Connection successful",
                "detected_model_count": model_count,
            }
        except httpx.TimeoutException:
            return {
                "success": False,
                "classification": "network_timeout",
                "http_status": None,
                "message": "Connection timeout",
                "detected_model_count": None,
            }
        except httpx.ConnectError as exc:
            text = str(exc).lower()
            if any(token in text for token in ("getaddrinfo", "name or service not known", "nodename", "dns")):
                classification = "network_dns"
                message = "DNS lookup failed"
            else:
                classification = "network_timeout"
                message = "Network connection failed"
            return {
                "success": False,
                "classification": classification,
                "http_status": None,
                "message": message,
                "detected_model_count": None,
            }
        except Exception as exc:
            return {
                "success": False,
                "classification": "unknown",
                "http_status": None,
                "message": f"Unexpected error: {exc}",
                "detected_model_count": None,
            }

    @staticmethod
    def _normalize_url(value: str) -> str:
        return str(value or "").strip().rstrip("/")

    @staticmethod
    def _pick_recommended_result(
        results: list[ProviderEndpointProbeResult],
        client_region_hint: str,
    ) -> Optional[ProviderEndpointProbeResult]:
        successful = [item for item in results if item.success]
        if not successful:
            return None

        hint = (client_region_hint or "unknown").strip().lower()

        return sorted(
            successful,
            key=lambda item: (
                0 if hint != "unknown" and hint in [tag.lower() for tag in item.region_tags] else 1,
                item.latency_ms if item.latency_ms is not None else 1_000_000,
                item.priority,
            ),
        )[0]

