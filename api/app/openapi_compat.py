def _nullables(node) -> None:
    if isinstance(node, list):
        for item in node:
            _nullables(item)
        return
    if not isinstance(node, dict):
        return
    options = node.get("anyOf")
    if isinstance(options, list):
        nulls = [item for item in options if isinstance(item, dict) and item.get("type") == "null"]
        rest = [item for item in options if item not in nulls]
        if len(nulls) == 1 and len(rest) == 1 and isinstance(rest[0], dict):
            chosen = dict(rest[0])
            node.pop("anyOf")
            if "$ref" in chosen and len(chosen) == 1:
                node["allOf"] = [{"$ref": chosen["$ref"]}]
            else:
                node.update(chosen)
            node["nullable"] = True
    if "const" in node:
        node["enum"] = [node.pop("const")]
    for value in node.values():
        _nullables(value)


def _drop_schema_titles(node) -> None:
    if isinstance(node, list):
        for item in node:
            _drop_schema_titles(item)
        return
    if not isinstance(node, dict):
        return
    node.pop("title", None)
    for value in node.values():
        _drop_schema_titles(value)


def as_openapi_30(schema: dict) -> dict:
    """Приводит документ к OpenAPI 3.0.3: nullable вместо anyOf null."""
    schema["openapi"] = "3.0.3"
    components = schema.get("components", {}).get("schemas", {})
    _drop_schema_titles(components)
    _nullables(schema)
    return schema
