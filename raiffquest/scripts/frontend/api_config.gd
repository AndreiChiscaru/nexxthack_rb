extends RefCounted
## Shared transport configuration. Web stays on the current origin; native
## development uses a local backend unless RAIFF_API is explicitly configured.

const LOCAL_BASE := "http://127.0.0.1:8000"

static func resolve_base() -> String:
	if OS.has_feature("web"):
		var origin: Variant = JavaScriptBridge.eval("window.location.origin", true)
		return normalize_base(str(origin)) if origin is String else ""
	var configured := OS.get_environment("RAIFF_API").strip_edges()
	return normalize_base(configured if not configured.is_empty() else LOCAL_BASE)

static func normalize_base(value: String) -> String:
	var base := value.strip_edges().trim_suffix("/")
	var pattern := RegEx.new()
	pattern.compile("^https?://[^/?#@\\s]+(?:/[^?#\\s]*)?$")
	if pattern.search(base) == null:
		return ""
	return base

static func build_url(base: String, path: String, query: Dictionary = {}) -> String:
	var normalized := normalize_base(base)
	if normalized.is_empty() or not path.begins_with("/api/"):
		return ""
	if path.contains("?") or path.contains("#") or path.contains("..") or path.contains("\\") or path.contains(" ") or path.contains("\n") or path.contains("\r"):
		return ""
	var pairs := PackedStringArray()
	for key: Variant in query:
		if not key is String or not (query[key] is String or query[key] is int or query[key] is float or query[key] is bool):
			return ""
		pairs.append(str(key).uri_encode() + "=" + str(query[key]).uri_encode())
	return normalized + path + ("?" + "&".join(pairs) if not pairs.is_empty() else "")
