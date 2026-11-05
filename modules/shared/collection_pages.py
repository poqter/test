"""Read complete REST collections with deterministic ordering."""
def collect_pages(fetch, params=None, keys=("id",)):
    query = dict(params or {})
    order = query.get("order", "")
    for key in keys:
        if not any(part.split(".")[0] == key for part in order.split(",")):
            order = (order + "," if order else "") + key + ".asc"
    query.update(order=order, limit="500")
    offset = int(query.get("offset", 0))
    result = []
    while True:
        query["offset"] = str(offset)
        batch = fetch(dict(query))
        if not batch:
            return result
        result.extend(batch)
        offset += len(batch)
