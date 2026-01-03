from dataclasses import dataclass

type RequestParam = dict[str, str]
type RequestData = dict[str, str]
type RequestHeader = dict[str, str]
type OAuthResponse = dict[str, str | bool | None]

