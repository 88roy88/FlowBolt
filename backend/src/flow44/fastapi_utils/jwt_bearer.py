import logging
from collections.abc import Callable
from typing import Any

import jwt
from fastapi import Request, status
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials
from fastapi.security.utils import get_authorization_scheme_param


LOGGER = logging.getLogger(__name__)


class MissingBearerToken(Exception):
    def __init__(self) -> None:
        super().__init__("Empty token, or token not of 'bearer' schema")

    @property
    def http_status_code(self) -> int:
        return status.HTTP_403_FORBIDDEN


class TokenVerifyDeniedError(Exception):
    def __init__(self) -> None:
        super().__init__("Invalid token or expired token")

        @property
        def http_status_code(self) -> int:
            return status.HTTP_403_FORBIDDEN


class JWTData(HTTPAuthorizationCredentials):
    creds_dict: dict[str, str] = {}

    def get_item(self, item: str) -> str | None:
        return self.creds_dict.get(item, None)


class JWTBearer(APIKeyHeader):
    def __init__(
        self,
        validation_func: Callable[[str], Any],
        header_name: str,
        scope_field_name: str = "scp",
        force_validation: bool = False,
    ) -> None:
        self._validation_func = validation_func
        self._scope_field_name = scope_field_name
        self._force_validation = force_validation
        super().__init__(auto_error=True, name=header_name, scheme_name=header_name)

    async def __call__(self, request: Request) -> None:
        try:
            auth_data = self._get_requests_credentials_without_validation(request)
            if auth_data is None:
                if self._force_validation:
                    raise MissingBearerToken
                return
            await self._validation_func(auth_data.credentials)
            scope = set(auth_data.get_item(self._scope_field_name) or [])
        except BaseException as e:
            LOGGER.exception("%s JWT validation failed", self.model.name)
            raise TokenVerifyDeniedError from e
        setattr(request, self.scheme_name, auth_data)  # adding the JWTData instance to the request

    def _get_requests_credentials_without_validation(self, request: Request) -> JWTData | None:
        authorization = request.headers.get(self.model.name)
        if authorization is None:
            return None
        scheme, credentials = get_authorization_scheme_param(authorization)
        is_token_bearer = scheme.lower() == "bearer"
        if not credentials or not is_token_bearer:
            LOGGER.debug("Received bad token (%s, %s)", scheme, credentials)
            raise MissingBearerToken

        decoded = jwt.decode(
            credentials,
            algorithms=["RS256"],
            options={
                "verify_signature": False,
                "verify_aud": False,
                "verify_exp": False,
                "verify_iss": False,
            },
        )
        return JWTData(scheme=scheme, credentials=credentials, creds_dict=decoded)
