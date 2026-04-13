"""Fetch GraphQL introspection schemas from the Plus Suite API."""
from __future__ import annotations

import requests

URL_TEMPLATE = "https://uon-api.{env}.allocate.plus/{env}/plus/graphql/{api}"
VALID_ENVS = ("npe", "prd")
VALID_APIS = ("aplus", "suite")

INTROSPECTION_QUERY = """
query IntrospectionQuery {
  __schema {
    queryType { name }
    mutationType { name }
    subscriptionType { name }
    types {
      ...FullType
    }
    directives {
      name
      description
      locations
      args { ...InputValue }
    }
  }
}

fragment FullType on __Type {
  kind
  name
  description
  fields(includeDeprecated: true) {
    name
    description
    args { ...InputValue }
    type { ...TypeRef }
    isDeprecated
    deprecationReason
  }
  inputFields { ...InputValue }
  interfaces { ...TypeRef }
  enumValues(includeDeprecated: true) {
    name
    description
    isDeprecated
    deprecationReason
  }
  possibleTypes { ...TypeRef }
}

fragment InputValue on __InputValue {
  name
  description
  type { ...TypeRef }
  defaultValue
}

fragment TypeRef on __Type {
  kind
  name
  ofType {
    kind
    name
    ofType {
      kind
      name
      ofType {
        kind
        name
        ofType {
          kind
          name
        }
      }
    }
  }
}
"""


def parse_target(target: str) -> tuple[str, str] | None:
    """Return (env, api) if `target` matches 'env:api', else None."""
    if not target or ":" not in target:
        return None
    env, _, api = target.partition(":")
    if env in VALID_ENVS and api in VALID_APIS:
        return env, api
    return None


def resolve_url(env: str, api: str) -> str:
    if env not in VALID_ENVS:
        raise ValueError(f"unknown env {env!r}; expected one of {VALID_ENVS}")
    if api not in VALID_APIS:
        raise ValueError(f"unknown api {api!r}; expected one of {VALID_APIS}")
    return URL_TEMPLATE.format(env=env, api=api)


def fetch_schema(
    env: str,
    api: str,
    *,
    api_key: str,
    jwt_token: str,
    timeout: int = 30,
) -> dict:
    """POST the introspection query and return the full response dict."""
    url = resolve_url(env, api)
    headers = {
        "x-api-key": api_key,
        "Authorization": f"Bearer {jwt_token}",
        "Content-Type": "application/json",
    }
    resp = requests.post(
        url,
        headers=headers,
        json={"query": INTROSPECTION_QUERY},
        timeout=timeout,
    )
    if resp.status_code != 200:
        raise RuntimeError(
            f"introspection fetch failed for {env}:{api} "
            f"({resp.status_code}): {resp.text[:500]}"
        )
    payload = resp.json()
    if "errors" in payload:
        raise RuntimeError(
            f"introspection returned GraphQL errors for {env}:{api}: {payload['errors']}"
        )
    return payload
