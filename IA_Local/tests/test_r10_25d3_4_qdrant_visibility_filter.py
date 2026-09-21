from types import SimpleNamespace

from enterprise_ai.vector_store import QdrantVectorStore


class PointProbe:
    def __init__(self, point_id, payload, score=1.0):
        self.id = point_id
        self.payload = payload
        self.score = score


class QueryResultProbe:
    def __init__(self, points):
        self.points = points


def visible_points():
    return [
        PointProbe(
            "company-visible",
            {
                "company_id": "company-a",
                "user_id": "owner-a",
                "scope": "company",
            },
        ),
        PointProbe(
            "own-user-visible",
            {
                "company_id": "company-a",
                "user_id": "user-a",
                "scope": "user",
            },
        ),
    ]


class QueryPointsClientProbe:
    def __init__(self):
        self.calls = []

    def query_points(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return QueryResultProbe(visible_points())


class FallbackClientProbe:
    def __init__(self):
        self.query_calls = []
        self.search_calls = []

    def query_points(self, *args, **kwargs):
        self.query_calls.append((args, kwargs))
        raise RuntimeError("force legacy search fallback")

    def search(self, *args, **kwargs):
        self.search_calls.append((args, kwargs))
        return visible_points()


class DefenseClientProbe:
    def query_points(self, *args, **kwargs):
        return QueryResultProbe(
            visible_points()
            + [
                PointProbe(
                    "other-user-hidden",
                    {
                        "company_id": "company-a",
                        "user_id": "user-b",
                        "scope": "user",
                    },
                )
            ]
        )


def principal():
    return SimpleNamespace(
        company_id="company-a",
        user_id="user-a",
    )


def make_store(client):
    store = object.__new__(QdrantVectorStore)
    store.client = client
    store._collection = lambda kind: f"probe-{kind}"
    return store


def condition_values(conditions):
    return {
        condition.key: condition.match.value
        for condition in (conditions or [])
    }


def assert_visibility_filter(qfilter):
    assert condition_values(qfilter.must) == {
        "company_id": "company-a",
    }

    assert condition_values(qfilter.should) == {
        "scope": "company",
        "user_id": "user-a",
    }


def test_query_points_pushes_visibility_and_uses_exact_limit():
    client = QueryPointsClientProbe()
    store = make_store(client)

    result = store.search(
        "memory",
        [1.0, 0.0],
        principal(),
        limit=7,
    )

    assert len(client.calls) == 1
    _, kwargs = client.calls[0]

    assert kwargs["limit"] == 7
    assert_visibility_filter(kwargs["query_filter"])

    assert [item["vector_id"] for item in result] == [
        "company-visible",
        "own-user-visible",
    ]


def test_legacy_search_fallback_uses_same_filter_and_exact_limit():
    client = FallbackClientProbe()
    store = make_store(client)

    result = store.search(
        "document",
        [1.0, 0.0],
        principal(),
        limit=5,
    )

    assert len(client.query_calls) == 1
    assert len(client.search_calls) == 1

    _, query_kwargs = client.query_calls[0]
    _, search_kwargs = client.search_calls[0]

    assert query_kwargs["limit"] == 5
    assert search_kwargs["limit"] == 5

    assert_visibility_filter(query_kwargs["query_filter"])
    assert_visibility_filter(search_kwargs["query_filter"])

    assert [item["vector_id"] for item in result] == [
        "company-visible",
        "own-user-visible",
    ]


def test_python_post_filter_remains_defense_in_depth():
    store = make_store(DefenseClientProbe())

    result = store.search(
        "memory",
        [1.0, 0.0],
        principal(),
        limit=10,
    )

    assert [item["vector_id"] for item in result] == [
        "company-visible",
        "own-user-visible",
    ]
