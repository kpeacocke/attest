FROM python:3.14-slim@sha256:51dafde81dbdb6ebde285137a295cf18a47ca95234fe388a343719cb97305b3d AS build

WORKDIR /src
RUN pip install --no-cache-dir poetry==2.2.1
COPY pyproject.toml poetry.lock README.md LICENSE ./
COPY src ./src
COPY scripts/runtime_constraints.py ./scripts/runtime_constraints.py
RUN poetry build && python scripts/runtime_constraints.py > dist/constraints.txt

FROM build AS test

COPY tests ./tests
RUN poetry install --no-interaction && poetry run ruff check . && poetry run pytest -q

FROM python:3.14-slim@sha256:51dafde81dbdb6ebde285137a295cf18a47ca95234fe388a343719cb97305b3d AS cli

COPY --from=build /src/dist /tmp/dist
RUN pip install --no-cache-dir --constraint /tmp/dist/constraints.txt /tmp/dist/*.whl \
    && rm -rf /tmp/dist \
    && groupadd --gid 10001 attest \
    && useradd --uid 10001 --gid attest --no-create-home attest \
    && mkdir -p /work /data \
    && chown attest:attest /work
USER 10001:10001
WORKDIR /work
ENTRYPOINT ["attest"]
CMD ["--help"]

FROM cli AS dashboard

EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
    CMD python -c "from urllib.request import urlopen; urlopen('http://127.0.0.1:8080/dashboard.html', timeout=3).close()"
CMD ["dashboard", "serve", "/data", "--port", "8080"]