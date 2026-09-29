FROM eclipse-temurin:8-jdk-jammy AS jdk8

FROM ghcr.io/astral-sh/uv:python3.11-trixie

# Install build tools including cmake and minestudio dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    cmake \
    gcc \
    g++ \
    xvfb \
    mesa-utils \
    libegl1 \
    libgl1-mesa-dev \
    libglu1-mesa-dev \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

ENV JAVA_HOME=/opt/java/openjdk
COPY --from=jdk8 $JAVA_HOME $JAVA_HOME
ENV PATH="${JAVA_HOME}/bin:${PATH}"

RUN adduser agent
USER agent
WORKDIR /home/agent

COPY pyproject.toml uv.lock README.md ./
COPY MCU_benchmark MCU_benchmark
COPY src src


RUN \
    --mount=type=cache,target=/home/agent/.cache/uv,uid=1000 \
    uv sync --locked

# Download Minecraft engine during build
RUN uv run python src/engine_util.py
# Test Minecraft engine
RUN uv run python -m minestudio.simulator.entry


ENTRYPOINT ["uv", "run", "src/server.py"]
CMD ["--host", "0.0.0.0"]
EXPOSE 9009
